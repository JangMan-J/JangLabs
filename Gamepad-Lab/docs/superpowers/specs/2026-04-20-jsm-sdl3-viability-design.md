# JSM + SDL3 direct DInput viability — design

**Date:** 2026-04-20
**Related prior work:** `findings/jsm_wrapper_substrate.md` (2026-04-19), `findings/gyro_hid.md`
**Supersedes:** the 6-step task breakdown in `findings/jsm_wrapper_substrate.md` §"Proposed follow-up task breakdown"

## Context

The 8BitDo Ultimate 2 Wireless (VID `0x2DC8` / PID `0x6012`) currently
reaches JoyShockMapper (JSM) through a Python bridge at
`tools/jsm_bridge.py`. The bridge reads raw HID in the pad's DInput
mode and feeds a virtual DS4 via ViGEmBus into JSM. This path works,
but carries three durable costs:

- **4 of 17 physical inputs are unreachable** (L4, R4, PL, PR) — DS4
  has no slots for them.
- **ViGEmBus was archived 2023-11-02**; the bridge depends on an
  unmaintained kernel driver.
- **Python process in the input hot path** — an extra live component
  between the pad and JSM that must be started/stopped alongside JSM.

Prior research on 2026-04-19 (`findings/jsm_wrapper_substrate.md`)
identified a more direct candidate: JSM master has migrated off
JoyShockLibrary onto SDL3 as the default backend, and SDL3 ships a
dedicated HIDAPI driver (`SDL_hidapi_8bitdo.c`) for this pad. If the
pad (DInput mode) → SDL3 → JSM path delivers gyro at usable scale and
covers all 17 inputs, it eliminates all three costs at once.

The prior research validated that the scaffolding exists in both
codebases but left three linchpin unknowns: whether SDL3 actually
plumbs the pad's sensors through as `SDL_SENSOR_GYRO` at usable scale,
whether all 17 inputs surface through JSM's binding layer, and whether
the DInput-mode VID/PID alignment holds on a live build. Earlier
notes in `findings/gyro_hid.md` state that older SDL versions did not
surface gyro from this pad in DInput mode — the new SDL3 driver
post-dates that note, but the caveat has not been retested.

This spec defines the plan to answer those unknowns, with a **static
source-verification gate before any build commitment** and an
**explicit decision tree** for each possible live-test outcome
including partial wins.

## Goals

End-state: an evidence-backed verdict on whether to adopt the
pad → SDL3 → JSM direct path in place of the ViGEm-DS4 bridge.

On parity-or-better outcomes, adoption produces:
- A new findings doc recording the result, pinned SHAs, and
  measured characteristics (button coverage, gyro scale, sample rate).
- A JSM config scaffold matching the user's current Steam Input
  layout, expressed in Steam-Input-style terminology (precision speed,
  movement threshold, etc. — not VDF field names).
- A deprecation header appended to `tools/jsm_bridge.py` (not a
  deletion — the bridge remains available as fallback reference).
- Updates to `findings/gyro_hid.md` superseding the earlier caveat
  with the tested SHA and date.

On non-adoption outcomes, adoption produces a concrete escalation
path (upstream issue, patch sketch) and keeps `jsm_bridge.py` as
primary.

## Non-goals

- JSL-fork path (research already ruled this out — JSM's JSL backend
  is legacy, JSL frozen since 2023-09).
- Virtual DualSense driver work (blocked on driver signing; not
  cost-effective).
- Commercial tools (DSX+, reWASD — wrong shape for synthetic input).
- Migrating the user's full Steam Input layout into a finished JSM
  config (scaffold only; user tunes the feel).
- Non-Windows builds.
- Pad modes other than DInput (NS/Switch, PC/XInput are not tested).
- **Bluetooth transport** — dongle-only is in scope.

## Approach

Three-phase linear plan with an explicit SDL3 isolation step inside
Gate 2:

```
Phase 1   Static source verification  (SDL3 + JSM, no build)
            |
            v
Phase 2a  Build JSM master (+ bundled SDL3) locally
Phase 2b  Side-build SDL3 with SDL_TESTS=ON; run testcontroller
          against pad (isolates SDL3-vs-JSM faults)
Phase 2c  Run JSM against pad; probe buttons / gyro / scale / rate
            |
            v
Phase 3   Adoption (per branch tree) or fallback + escalation
```

The SDL3 isolation step (Phase 2b) cleanly separates "SDL3 doesn't
plumb sensors for this pad" from "JSM doesn't wire SDL3's sensors to
gyro bindings" — two very different escalation paths (libsdl-org
issue vs JSM patch/fork). The `testcontroller` binary falls out of
a small side-build of SDL3, so the diagnostic cost is minimal.

## Phase 1 — Static source verification (Gate 1)

**Intent:** before touching a build toolchain, answer from source
alone — pinned to specific SHAs — whether the HID-bytes-to-gyro-
binding plumbing actually exists for this pad.

### Artifacts to read

Pinned to whatever SHAs are current at start of Phase 1:

- **SDL3** (the version JSM master's `CMakeLists.txt` references —
  `release-3.2.x` branch as of last research):
  - `src/joystick/hidapi/SDL_hidapi_8bitdo.c` — the driver itself
  - `src/joystick/hidapi/SDL_hidapi_joystick.c` — driver framework,
    sensor-emission helpers
  - `include/SDL3/SDL_gamepad.h` — public sensor API surface
    (`SDL_SetGamepadSensorEnabled`, `SDL_GetGamepadSensorData`)
  - `src/joystick/usb_ids.h` — VID/PID constants
  - Joystick internals for `SDL_SendJoystickSensor`, scale conventions
- **JSM master** (current HEAD):
  - `JoyShockMapper/CMakeLists.txt` — SDL3 pin, build options
  - `JoyShockMapper/src/SDLWrapper.cpp` (or equivalent) — the SDL3 ↔
    JSM bridge
  - Headers defining the gyro/binding surface
  - Main loop / event pump where sensor data flows into JSM processing

### The 10 questions

Each gets a file:line citation and a verdict (clear / partial / gap /
unknown).

**SDL3 side:**
1. Does the driver's VID/PID table match `0x2DC8 / 0x6012`?
2. Does it recognize the 34-byte v1.03 report? (cross-check against
   `findings/gyro_hid.md` offset layout for the sensor block at
   offsets 15–26)
3. Does parsed gyro reach `SDL_SendJoystickSensor` with type
   `SDL_SENSOR_GYRO`?
4. What scale is applied? SDL's sensor convention is rad/s; raw is
   ±2000 dps at int16. Is the full ±2000 dps range preserved through
   the conversion?
5. How many buttons does the driver expose, and via what mapping?
   All 17 reachable, or only the standard 13 with the extras lost or
   routed to `SDL_GAMEPAD_BUTTON_MISC*` / paddle slots?
6. **Does the driver respect the pad's sensor delivery cadence, or does
   it throttle/coalesce?** Trace from HID read thread to
   `SDL_SendJoystickSensor` — any timer, rate-limit, or merge that
   would decimate below the ~125 Hz raw-HID baseline?

**JSM side:**
7. Does JSM call `SDL_SetGamepadSensorEnabled(..., SDL_SENSOR_GYRO,
   true)` on pad connection?
8. Does JSM read sensor data via `SDL_GetGamepadSensorData` or via
   `SDL_EVENT_GAMEPAD_SENSOR_UPDATE` events each frame?
9. Does the sensor value reach JSM's `GYRO` binding with correct
   sign/units? (Any sign flips needed vs. raw HID convention — see
   `findings/gyro_hid.md` axis-mapping block.)
10. Does JSM iterate only the standard 13 `SDL_GAMEPAD_BUTTON_*` enum,
    or does it also handle extras (`MISC*`, paddles) — i.e., will the
    4 Ultimate 2 extras be bindable even if SDL3 does surface them?

### Parallelism

Single session recommended. The SDL3 and JSM codebases are small
(the 8BitDo driver is a single file; JSM's SDL wrapper is small), and
the real value is cross-referencing SDL3's public API with JSM's call
sites — a single session does that more naturally than two subagents.
Subagent dispatch remains a valid opt-in if the reads turn out
heavier than expected.

### Output artifact

`findings/jsm_sdl3_source_verification.md`:
- SHAs pinned (JSM + SDL3)
- Summary table: 10 rows, one per question, `verdict | file:line | notes`
- Overall verdict: green (proceed to Gate 2) / yellow (proceed, watch
  for X) / red (stop, escalate)
- Escalation plan if yellow or red: specific upstream-issue sketch,
  patch sketch, and interim plan (keep `jsm_bridge.py`)

### Exit criteria

- All 10 questions answered with source-grounded evidence.
- One-line verdict published.
- If not green: escalation path documented; `BACKLOG.md` updated;
  Phase 2 deferred.

## Phase 2 — Build + isolated SDL3 test + JSM live test (Gate 2)

**Precondition:** Phase 1 verdict is green or yellow. Red stops here.

### Phase 2a — Toolchain + build

Install if not present:
- Visual Studio 2022 Build Tools, workload "Desktop development with
  C++" (includes MSVC v143 + Windows 10/11 SDK)
- CMake 3.x
- Git

Install preference: `winget` where possible, for quiet/reproducible
install.

Build JSM master:

```
git clone https://github.com/Electronicks/JoyShockMapper.git
cd JoyShockMapper
git rev-parse HEAD                   # pin the SHA in the finding doc
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
```

Expected output: `build/**/JoyShockMapper.exe` + `SDL3.dll` together.

### Phase 2b — SDL3 isolation test

JSM's CMake does **not** enable `SDL_TESTS` in its SDL3 subdirectory
fetch, so `testcontroller` isn't produced by JSM's build. Side-build
at the same SDL3 SHA JSM pulled:

```
git clone --branch <SDL3-tag-or-SHA> https://github.com/libsdl-org/SDL.git sdl3
cmake -S sdl3 -B sdl3/build -DCMAKE_BUILD_TYPE=Release -DSDL_TESTS=ON
cmake --build sdl3/build --target testcontroller --config Release
```

Fallback if the side-build is awkward: a ~30-line standalone C probe
using public SDL3 API (`SDL_Init`, enumerate joysticks, enable gyro,
print timestamped sensor values). More targeted for our purposes.

**Preconditions before running** (from `findings/gyro_hid.md`):
- Exit Steam completely — not just Big Picture. Steam Input hides
  controllers from SDL.
- Exit 8BitDo Ultimate Software tray app (right-click → Exit, not
  minimize). The tray app claims HID exclusively.
- Put pad in **DInput mode** (hold B while powering on; verify mode
  LED).
- Verify pad mode via `hid.enumerate()` — expect VID/PID `2DC8:6012`,
  not `057E:2009` (which would indicate Switch mode).

**Run the isolation probe. Record:**

| Check | What to look for |
|---|---|
| Device enumerated | Pad appears in joystick list; name matches `8BitDo Ultimate 2 Wireless` (or driver's string) |
| Gamepad layout | Mapped to `SDL_Gamepad` (not "joystick only") |
| Standard buttons | 13-button layout populated |
| Extras | Paddles (`LEFT_PADDLE{1,2}`, `RIGHT_PADDLE{1,2}`) or `MISC*` buttons present for L4/R4/PL/PR? |
| Sensor — gyro | `SDL_SENSOR_GYRO` enabled returns non-zero values when pad rotated |
| Sensor — scale | At a known rotation, compare dps via raw HID (`tools/gyro_meter.py`) to rad/s via SDL3; ratio should be π/180 |
| **Sensor — rate (first-class)** | Timestamp every update; report mean inter-arrival time + std-dev + histogram; compare to raw-HID baseline (~125 Hz per `findings/gyro_hid.md`) |
| Transport | Dongle (USB 2.4 GHz) only — Bluetooth is out of scope |

**Outcomes:**
- Pad not detected → SDL3 VID/PID or report-layout match failed;
  **file libsdl-org issue**, stop here (Phase 3 Branch F).
- Pad detected, no sensors → SDL3 driver doesn't plumb sensors;
  **file libsdl-org issue**, stop here (Branch F).
- Pad detected with sensors → SDL3 path works; **proceed to 2c**.

### Phase 2c — JSM live probes

**Preconditions:** same as 2b (Steam/tray quit, pad in DInput mode,
mode verified via `hid.enumerate()`).

**Minimal test config:** each of 17 physical inputs bound to a
distinct key/mouse action so the console log shows exactly which
registers; gyro bound to mouse X/Y with simple conversion for the
directionality probe. `--verbose` or equivalent flag to log every
button event.

(Exact JSM keyword syntax pulled from JSM's README at execution time.)

**Probes:**

| Probe | Method | Pass criterion |
|---|---|---|
| **P1: Identification** | Launch JSM with test config | Console reports pad connected; name matches SDL3's |
| **P2: Standard buttons** | Press each of 13 standard inputs | All register with bound action |
| **P3: Extras (L4/R4/PL/PR)** | Press each | Register — or fail, noting which SDL3 slot they would have arrived in (cross-ref 2b) |
| **P4: Gyro directionality** | Rotate yaw/pitch/roll | Mouse moves in expected direction per `findings/gyro_hid.md` axis mapping; flag any sign flips |
| **P5: Gyro scale** | Sustained rotation; compare JSM mouse dps to `gyro_meter.py` | JSM value consistent with SDL3's scale from 2b |
| **P6: Sample rate (first-class)** | Measure mouse-event rate under sustained steady rotation | Tracks SDL3's cadence from 2b; does not drop below it |

### Operational gotchas (both 2b and 2c)

- Steam fully exited (not just Big Picture)
- 8BitDo Ultimate Software tray app fully exited (not minimized)
- DInput mode LED confirmed; `hid.enumerate()` shows `2DC8:6012`
- If admin privileges are needed for HID access, document in the
  finding doc

### Output artifact

`findings/jsm_sdl3_live_verification.md`:
- Date + host + JSM SHA + SDL3 SHA + VS toolchain version
- Phase 2a: build status, binary paths, warnings of note
- Phase 2b: SDL3 isolation table with verdicts and raw numbers
- Phase 2c: JSM probe table with verdicts and observed behavior
- If stopped at 2b: 2c section marked "not run; SDL3 blocked at <layer>"

### Exit criteria

- Build produced usable binaries (or Branch G fired).
- Phase 2b gives a clear SDL3-level verdict.
- If 2b passed, Phase 2c gives a full probe table.
- Results consolidated in the finding doc, ready for Phase 3.

## Phase 3 — Adoption / fallback decision tree

Flexible threshold — each Phase 2 outcome maps to a specific branch.

### Branch A — Total win

**Trigger:** all 17 buttons register + gyro works at full ±2000 dps
scale. Sample rate is documented but does not gate adoption (see
"Sample rate interpretation" below).

**Actions:**
1. Write `findings/jsm_sdl3_verified.md` — supersedes prior open
   questions; records SHAs, button mapping, sensor scale, measured
   sample rate.
2. Update `findings/gyro_hid.md` — new section noting SDL3 exposes
   sensors on Ultimate 2 DInput mode as of SHA X; supersede earlier
   caveat.
3. Add "superseded by" pointer at top of
   `findings/jsm_wrapper_substrate.md`.
4. Write `tools/jsm_sdl3_config.txt` — JSM config scaffold matching
   current Steam Input layout (all 17 bindings + gyro behaviors using
   Steam-Input-style terminology).
5. Append deprecation header to `tools/jsm_bridge.py` (single comment
   block; do not delete). Header points at the new path and notes
   adoption date.
6. Update `BACKLOG.md` — mark verification item done, link to finding.

### Branch B — Parity win

**Trigger:** ≥13 standard buttons + gyro works at full scale; some
or all of L4/R4/PL/PR unreachable. Sample rate is documented but
does not gate adoption.

**Actions:** Same as Branch A, but:
- Finding doc explicitly documents which extras are unreachable and
  at which layer.
- Config scaffold omits unreachable bindings with a comment per
  omission.
- **Escalation:** file one upstream issue per root cause
  - Missing at SDL3 layer → libsdl-org issue (patch sketch from
    Phase 1 Q5 notes)
  - Missing at JSM layer → Electronicks/JoyShockMapper issue
- Deprecate `jsm_bridge.py` noting both paths share the same 4-button
  ceiling but JSM+SDL3 has fewer moving parts.

### Branch C — Gyro OK, new kind of button gap

**Trigger:** gyro works, but missing buttons are *not* the bridge's
set (e.g., a standard face button failed, or a different extra).

**Actions:**
- **Do not adopt as primary** — worse coverage profile than bridge.
- File upstream issue at the layer where the gap is.
- `jsm_bridge.py` remains primary.
- Document gap in `findings/jsm_sdl3_live_verification.md`.
- Revisit after upstream fix.

### Branch D — Gyro works at wrong scale

**Trigger:** gyro direction OK, but dps reported differs by a
non-unit factor (e.g., ×2, ÷(π/180) missing, clipped to ±1000).

**Actions:**
- If factor is clean and correctable at JSM config level (sensitivity
  multiplier), adopt per Branch A/B with compensation factor
  documented in config and finding doc.
- If factor indicates clipping/truncation (loss of range), treat as
  bug → file at whichever layer introduces it (likely SDL3); keep
  bridge as primary; do not adopt.
- Document observed scale and hypothesized conversion chain.

### Branch E — Gyro silent at JSM, OK at SDL3

**Trigger:** Phase 2b shows SDL3 sensors flowing; Phase 2c shows JSM
doesn't drive gyro binding.

**Actions:**
- Do not adopt.
- File JSM issue with reproducer (`testcontroller` works, JSM
  doesn't).
- `jsm_bridge.py` remains primary.
- Optional: draft patch to JSM's SDLWrapper (if Phase 1 identified
  the likely call site) → save in `handoffs/jsm_sdl3_upstream_patch.md`
  for later pickup.

### Branch F — Gyro silent at SDL3 layer

**Trigger:** Phase 2b shows no sensor data.

**Actions:**
- Do not adopt.
- File libsdl-org issue with reproducer.
- `jsm_bridge.py` remains primary.
- Update `findings/gyro_hid.md` — reaffirm earlier caveat (SDL3's
  Ultimate 2 driver plumbs sensors in code but not in practice —
  note SHA tested).

### Branch G — Build fails

**Trigger:** JSM or SDL3 build errors.

**Actions:**
- Diagnose (toolchain version, SDL3 SHA mismatch, CMake config).
- If fix is local (environment), fix and retry from Phase 2a.
- If fix is in upstream source, file upstream.
- `jsm_bridge.py` remains primary.

### Branch H — Build succeeds but JSM crashes/misbehaves on connect

**Trigger:** JSM exits, hangs, or errors when pad connects.

**Actions:**
- Capture error; file as JSM issue.
- Isolation check: does `testcontroller` also fail? If yes →
  SDL3 issue, not JSM.
- `jsm_bridge.py` remains primary.

### Sample rate interpretation

Sample rate is measured in Phase 2b/2c and recorded as a characteristic
of the adopted path, not a hard gate on adoption. Guideline:

- **≈125 Hz (parity with raw HID):** no caveat.
- **60–120 Hz (decimated but usable):** adopt with a caveat in the
  config scaffold ("gyro cadence below raw-HID baseline — may feel
  slightly chunkier on fast motion"); optionally open an upstream
  investigation but don't block adoption.
- **<60 Hz (significantly degraded):** revisit the adoption call. If
  the pad is otherwise fully functional, prefer fixing upstream before
  adoption; keep `jsm_bridge.py` as primary in the interim. Treat as
  a de-facto Branch C (don't adopt, escalate).

### Cross-branch notes

- **Handoff discipline:** each branch produces artifacts a future
  session can pick up without chat history.
- **Revert discipline:** on non-adoption branches, no changes to
  local tools (`jsm_bridge.py` untouched unless deprecating).
  `findings/` and `BACKLOG.md` updates are additive.
- **Upstream links:** finding docs link back to issue URLs so future
  status checks don't require re-discovering context.

## Session boundaries

Three natural session breaks:

1. **Phase 1 session** — static source reading only. No toolchain.
   Output: `findings/jsm_sdl3_source_verification.md`. Ends with
   verdict + (if not green) escalation notes.
2. **Phase 2 session** — build + live test. Toolchain install at
   session start if needed. Phases 2a, 2b, 2c in one sitting with pad
   plugged in. If 2b fails, 2c skipped; session ends with SDL3-level
   findings and pivots to Phase 3 Branch F. Output:
   `findings/jsm_sdl3_live_verification.md`.
3. **Phase 3 session** — adoption or fallback execution per matched
   branch. Mostly documentation + small file edits.

Handoff docs at boundaries: if a phase straddles a session boundary
or pauses mid-work, promote to `handoffs/jsm_sdl3_phaseN_wip.md`.
Completed handoffs get a one-line `BACKLOG.md` pointer.

## Artifacts

**Always produced:**
- `findings/jsm_sdl3_source_verification.md` — Phase 1
- `findings/jsm_sdl3_live_verification.md` — Phase 2 (truncated if
  2b fails; still produced)
- `BACKLOG.md` update — phase status, links

**Produced only on adoption branches (A, B, scale-correctable D):**
- `tools/jsm_sdl3_config.txt` — JSM config scaffold
- Deprecation header appended to `tools/jsm_bridge.py`
- Update to `findings/gyro_hid.md`
- "Superseded by" pointer on `findings/jsm_wrapper_substrate.md`

**Produced only on escalation branches (C, scale-clipping D, E, F, G, H):**
- Upstream issue URL(s) captured in live-verification finding
- Optional: `handoffs/jsm_sdl3_upstream_patch.md` draft PR/patch

## Risks and mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | SDL3 driver recognizes pad but silently drops gyro (earlier `findings/gyro_hid.md` caveat still applies on current SHA) | Medium — linchpin unknown | High — blocks adoption | Phase 1 static gate catches before build; if static looks fine but live fails, 2b isolation localizes fault cheaply |
| 2 | All 17 inputs surface but sample rate decimated by SDL3 below 125 Hz | Medium | Medium — gyro feel degraded, but adoption still possible with documented characteristic | 2b measures inter-arrival cadence with timestamps (not subjective feel); 2c verifies JSM doesn't further decimate |
| 3 | JSM master HEAD moves between Phase 1 and Phase 2 | Low (JSM not highly active) | Low | Pin SHA in Phase 1 finding; Phase 2 checks out same SHA |
| 4 | Build toolchain install slow or fails (VS Build Tools ~8 GB) | Low | Low | Install in advance as part of Phase 2 prep; winget failures fall back to manual installer |
| 5 | Steam or 8BitDo Ultimate Software silently re-acquires HID after close | Low | Medium — confuses results | At start of 2b, verify with `tools/gyro_meter.py` (reads raw HID) — if it sees the pad, HID is free |
| 6 | SDL3's `SDL_hidapi_8bitdo.c` changes between Phase 1 read and Phase 2 run | Low | Low-Medium | Pin SDL3 SHA in Phase 1; side-build uses pinned SHA |
| 7 | `testcontroller` side-build fails (edge case of SDL3 test CMake) | Low | Low | Fall back to ~30-line standalone probe using public SDL3 API |
| 8 | Pad mode ambiguity mid-test | Low | Medium — wrong-mode results look like failure | At start of every 2b/2c probe, verify `hid.enumerate()` shows `2DC8:6012` |

### Non-risks (explicitly flagged)

- **EPP / Windows pointer curve:** Steam Input bypasses the OS
  pointer pipeline; JSM's gyro-to-mouse path is relative-motion
  injection and also not affected. No caveat attached.
- **Anti-cheat flagging:** JSM doesn't inject virtual hardware on
  this path; it emits mouse/keyboard via user-mode Windows APIs.
  No concern.

## Definition of done

Plan complete when one of:
- Adoption branch (A, B, or scale-correctable D) executed and all
  adoption artifacts in place → user has working JSM+SDL3 setup
  matching or exceeding bridge capability.
- Non-adoption branch (C, E, F, G, H, or clipping D) executed and
  fallback/escalation artifacts in place → user has clear next
  steps and upstream filings; `jsm_bridge.py` remains primary.

## References

- `findings/jsm_wrapper_substrate.md` — prior research (2026-04-19)
  identifying JSM+SDL3 as the recommended path; contains the 6-step
  task breakdown this spec supersedes.
- `findings/gyro_hid.md` — HID report layout for the 34-byte v1.03
  report, axis-mapping conventions, exclusive-access gotchas
  (Steam Input, 8BitDo Ultimate Software).
- `tools/jsm_bridge.py` — current ViGEm-DS4 bridge, to be deprecated
  (not deleted) on adoption.
- `tools/gyro_meter.py` — raw-HID reader; ground truth for scale and
  sample-rate measurements.
- JSM: https://github.com/Electronicks/JoyShockMapper
- SDL3: https://github.com/libsdl-org/SDL (driver:
  `src/joystick/hidapi/SDL_hidapi_8bitdo.c`)
