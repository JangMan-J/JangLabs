# JSM + SDL3 direct DInput viability — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decide whether to adopt a pad (DInput mode) → SDL3 → JSM direct input path in place of the existing ViGEm-DS4 bridge (`tools/jsm_bridge.py`), using a static source-verification gate before committing build effort and an explicit decision tree for each live-test outcome.

**Architecture:** Three-phase linear plan. Phase 1 reads SDL3 + JSM source at pinned SHAs to answer 10 specific questions about the HID-to-gyro-binding plumbing — no toolchain needed. Phase 2 builds JSM master + a side-build of SDL3, runs SDL3's `testcontroller` against the pad to isolate SDL3 from JSM faults, then runs JSM live and probes buttons / gyro / scale / sample rate. Phase 3 selects a branch (adoption or escalation) based on Phase 2 results and executes the matching artifact set.

**Tech Stack:** CMake 3.28+, Visual Studio 2022 17.10+ Build Tools (MSVC v143) with the "Desktop development with C++" workload, Git 2.x, Python + `hidapi` package (already present in this workspace — used for pad-mode verification and raw-HID baseline via `tools/gyro_meter.py`).

**Supersedes:** `docs/superpowers/plans/2026-04-19-jsm-master-sdl3-build.md` (incorporates its toolchain/build steps and adds a static-verification gate, an SDL3 isolation step, first-class sample-rate measurement, a full decision tree, and adoption artifacts). Cross-reference the prior plan for exhaustive toolchain-install troubleshooting if Task 6 steps surface edge cases not covered here.

**Spec reference:** `docs/superpowers/specs/2026-04-20-jsm-sdl3-viability-design.md` — the design doc this plan implements. Goals, non-goals, risks, and rate-interpretation guideline live there.

---

## Environmental facts (repeat from prior plan — still apply)

- **JSM `README.md` says "Visual Studio 16 2019" — that is stale.** Root `CMakeLists.txt` requires `cmake_minimum_required 3.28` and C++23. VS 2022 17.10+ is required.
- **JSM has no GitHub Actions CI** on master. No prebuilt artifacts exist; source build is the only path.
- **8BitDo Ultimate Software** tray app holds the pad's HID interface exclusively. Right-click tray → **Exit** (not minimize) before any test run.
- **Steam** claims HID controllers via Steam Input and will shim the pad away from SDL3 even when not actively focused. Fully exit Steam (tray → Exit) for the duration of every live test.
- **Pad firmware:** v1.09 (v1.03 or later required for the 34-byte sensor-bearing report — per `findings/gyro_hid.md`).
- **Bluetooth is out of scope.** Dongle only.

---

## File structure

**Source trees (outside workspace, not polluting project):**
- `%USERPROFILE%\Claude\JangsJyro-JSM\` — JSM clone (created Task 7, ~100 MB with build)
- `%USERPROFILE%\Claude\SDL\` — SDL3 side-clone for `testcontroller` (created Task 8, ~50 MB with build)

**Artifacts produced inside workspace:**
- Always: `findings/jsm_sdl3_source_verification.md` (Task 4), `findings/jsm_sdl3_live_verification.md` (Task 13), `BACKLOG.md` updates
- Adoption branches only (A/B/D-correctable): `tools/jsm_sdl3_config.txt` (scaffold), modification to `tools/jsm_bridge.py` (deprecation header), modification to `findings/gyro_hid.md` (SDL3-status section), modification to `findings/jsm_wrapper_substrate.md` (superseded-by pointer)
- Escalation branches only: optional `handoffs/jsm_sdl3_upstream_patch.md`

**Ephemeral working files:**
- `%USERPROFILE%\Claude\JangsJyro-JSM\build\...\JoyShockMapper.exe` + `SDL3.dll`
- `%USERPROFILE%\Claude\SDL\build\test\Release\testcontroller.exe`
- `%USERPROFILE%\test_jsm.txt` — JSM test config (Task 12; delete after)

**Note on git:** the JangsJyro workspace itself is not a git repository, so artifact changes are "save file" operations, not `git commit`. The JSM and SDL3 clones are their own git repos; SHAs are recorded with `git rev-parse HEAD` for the findings.

---

## PHASE 1 — Static source verification (Gate 1)

Goal: answer, from source code alone at pinned SHAs, whether the pad-to-JSM-binding plumbing exists. Produce a verdict (green / yellow / red). Red stops the plan.

### Task 1: Pin SHAs and identify read targets

**Files:** scratch notes only — nothing committed this task.

#### Step 1.1: Find JSM master HEAD without cloning

- [ ] Run: `git ls-remote https://github.com/Electronicks/JoyShockMapper.git refs/heads/master`

Expected: one line — `<40-char-sha>\trefs/heads/master`. Record this SHA; it becomes the JSM pin in Task 4's finding.

#### Step 1.2: Find the SDL3 version JSM master references

- [ ] Fetch JSM's CPM/SDL declaration without cloning:

```
curl -sSL "https://raw.githubusercontent.com/Electronicks/JoyShockMapper/master/JoyShockMapper/CMakeLists.txt" | grep -iE "sdl|cpm" | head -40
```

Expected: a `CPMAddPackage(... libsdl-org/SDL ... GIT_TAG ... )` block or similar. Record the `GIT_TAG` / branch / version string — it's the SDL3 pin.

If JSM pulls a branch (e.g. `release-3.2.x`) rather than a fixed tag, resolve it to a concrete SHA:

```
git ls-remote https://github.com/libsdl-org/SDL.git release-3.2.x
```

Record this SHA as the SDL3 pin.

#### Step 1.3: Write a scratch pins file

- [ ] Create a scratch file at `%USERPROFILE%\Claude\JangsJyro\.phase1-pins.txt` containing the two SHAs and the SDL3 branch/tag JSM references. Delete after Task 4 (pin values migrate into the finding doc).

```
JSM master:   <sha>
SDL3 ref:     <branch or tag>
SDL3 SHA:     <sha>
```

---

### Task 2: Read SDL3 driver — answer Q1–Q6

**Files:** read-only inspection of SDL3 source at pinned SHA. Scratch notes accumulate toward Task 4's finding.

#### Step 2.1: Open `SDL_hidapi_8bitdo.c` at the pinned SHA

- [ ] Fetch: `curl -sSL "https://raw.githubusercontent.com/libsdl-org/SDL/<SDL3-SHA>/src/joystick/hidapi/SDL_hidapi_8bitdo.c" > %USERPROFILE%\Claude\JangsJyro\.phase1-scratch\SDL_hidapi_8bitdo.c`

Expected: file saved, non-empty. Create the `.phase1-scratch` directory first if missing.

#### Step 2.2: Answer Q1 — VID/PID match

- [ ] In the fetched file, grep for `0x2DC8` and `0x6012` (or the symbolic constant `USB_PRODUCT_8BITDO_ULTIMATE2_WIRELESS` if the driver uses that).

Expected: at least one match, inside a VID/PID dispatch table or an `HIDAPI_DriverXBox_IsSupportedDevice`-style function. Record file:line citation and verdict (clear / partial / gap / unknown).

#### Step 2.3: Answer Q2 — 34-byte v1.03 report recognition

- [ ] In the fetched file, grep for `34`, `0x22` (hex 34), or a `size ==` / `sizeof(...)` comparison in the HID-report handling function. Cross-reference the sensor block offsets (15–26) documented in `findings/gyro_hid.md`.

Expected: a report-parsing path that (a) checks report ID `0x01`, (b) only proceeds if the buffer is ≥ 34 bytes, and (c) extracts `sGyro{X,Y,Z}` and `sAccel{X,Y,Z}` at or near offsets 15–26. Record file:line citations and verdict.

#### Step 2.4: Answer Q3 — gyro reaches `SDL_SendJoystickSensor` with `SDL_SENSOR_GYRO`

- [ ] Grep: `SDL_SendJoystickSensor` in the fetched driver file.

Expected: a call like `SDL_SendJoystickSensor(timestamp, joystick, SDL_SENSOR_GYRO, sensor_timestamp, data, 3)`. Record file:line and whether the `data` array values can be traced to the `sGyro{X,Y,Z}` raw fields. Verdict.

#### Step 2.5: Answer Q4 — scale preservation

- [ ] From the data path identified in Step 2.4, trace the conversion from raw int16 to the float array passed to `SDL_SendJoystickSensor`. Expect `(raw / 32767.0f) * 2000.0f * (pi / 180.0f)` or algebraically equivalent — that is, raw int16 → dps (×2000/32767) → rad/s (×π/180). SDL's sensor convention is rad/s.

Expected: file:line citations for each multiplication. Record the full composed scale as a numeric factor (should equal `2000.0 * π / (180.0 * 32767.0)` ≈ `1.0654e-3` rad/s per raw unit). Verdict: **clear** if factor is correct and full ±2000 dps maps to ±34.9 rad/s; **partial** if range is clipped; **gap** if scale is algebraically wrong.

#### Step 2.6: Answer Q5 — button coverage

- [ ] Grep the fetched driver for `SDL_SendJoystickButton`, `SDL_GAMEPAD_BUTTON_`, and `SDL_HAT_`. Count the distinct button-dispatch sites and list the SDL_Gamepad enum values each one emits.

Expected: 13 standard buttons plus (if implemented) `SDL_GAMEPAD_BUTTON_LEFT_PADDLE{1,2}`, `RIGHT_PADDLE{1,2}`, or `MISC1..6` for L4/R4/PL/PR. Record file:line citations, the list of enum values emitted, and count total distinct buttons surfaced. Verdict: **clear** at 17, **partial** at 13–16 with exact missing mapping, **gap** below 13.

#### Step 2.7: Answer Q6 — sample-rate handling (first-class)

- [ ] In the fetched driver's read/poll loop, trace from HID read (`SDL_hid_read`, `hid_read_timeout`, or similar) to the `SDL_SendJoystickSensor` call. Look for:
  - Any `SDL_GetTicks`-based rate limit / deadline check
  - Any `if (last_sensor_time + interval > now) return;` pattern
  - Any sample-coalescing (averaging multiple reads before one send)
  - Any explicit `SDL_Delay` in the sensor path

Expected: a pass-through — raw HID read arrives, sensor emitted immediately, no throttling. Record file:line citations for the read-to-emit path. Verdict: **clear** if pass-through, **partial** if only light debouncing, **gap** if there's a rate limit below ~500 Hz.

---

### Task 3: Read JSM SDL wrapper — answer Q7–Q10

**Files:** read-only inspection of JSM source at pinned SHA.

#### Step 3.1: Open JSM's SDL wrapper file

- [ ] First, locate the file. JSM's layout usually has `JoyShockMapper/src/SDLWrapper.cpp` or `SDL2Wrapper.cpp`. Probe:

```
curl -sSL "https://api.github.com/repos/Electronicks/JoyShockMapper/git/trees/<JSM-SHA>?recursive=1" | grep -iE "sdl.*wrapper|jslwrapper|controller" | head -20
```

Expected: one or more candidate paths. Fetch the most likely one (`SDLWrapper.cpp` preferred) to `.phase1-scratch\`. If JSM has renamed the wrapper, adjust.

#### Step 3.2: Answer Q7 — sensor enable

- [ ] In the fetched wrapper, grep for `SDL_SetGamepadSensorEnabled`, `SDL_GameControllerSetSensorEnabled`, or any `SDL_SENSOR_GYRO` reference being passed to a "set enabled" call.

Expected: a call enabling gyro on controller open/connect (usually inside a `connect` or `init` routine that runs per-pad). Record file:line and verdict.

#### Step 3.3: Answer Q8 — sensor read

- [ ] Grep for `SDL_GetGamepadSensorData`, `SDL_GameControllerGetSensorData`, or `SDL_EVENT_GAMEPAD_SENSOR_UPDATE` event handling.

Expected: either a polling read inside JSM's per-frame update loop or an event-pump handler for sensor-update events. Record file:line and which mechanism JSM uses. Verdict.

#### Step 3.4: Answer Q9 — gyro binding routing

- [ ] Starting from Q8's read site, trace where the three-float gyro array flows. Search for JSM's gyro-binding identifiers (`GYRO_X`, `GYRO_Y`, `gyroX`, `gyroY`, `sensorGyro`, or similar per JSM's vocabulary).

Expected: values reach the gyro-to-mouse or gyro-to-stick processing code. Record:
- file:line of each downstream assignment
- any sign flips (negations) — cross-check against `findings/gyro_hid.md` axis-mapping block: `pitch = -sGyroY; yaw = +sGyroZ; roll = -sGyroX`
- any unit conversions (rad/s → dps → JSM-internal sensitivity-scaled units)

Verdict.

#### Step 3.5: Answer Q10 — button extras iteration

- [ ] Grep JSM's controller/button handling for `SDL_GAMEPAD_BUTTON_MAX`, `SDL_GAMEPAD_BUTTON_LEFT_PADDLE1`, `PADDLE`, `MISC`, or any iteration over button slots.

Expected: either (a) a loop iterating `SDL_GAMEPAD_BUTTON_MAX` slots covering all 17+ SDL3 standard-plus-extras, or (b) a hand-rolled enumeration hitting only the classic 13. Record file:line and verdict — **clear** if all extras bindable, **partial** if extras partially bound, **gap** if only 13 standard slots handled.

---

### Task 4: Write Phase 1 finding doc + verdict

**Files:**
- Create: `%USERPROFILE%\Claude\JangsJyro\findings\jsm_sdl3_source_verification.md`
- Delete: `%USERPROFILE%\Claude\JangsJyro\.phase1-pins.txt` and `.phase1-scratch\` (consolidated into the finding)

#### Step 4.1: Write the finding doc

- [ ] Create `findings/jsm_sdl3_source_verification.md` with this structure — all 10 rows populated from Tasks 2 and 3:

```markdown
# JSM + SDL3 source verification — 8BitDo Ultimate 2 Wireless (DInput)

**Date:** <YYYY-MM-DD>
**JSM SHA:** <from Task 1.1>
**SDL3 ref:** <branch/tag from Task 1.2>
**SDL3 SHA:** <from Task 1.2>
**Read targets:**
- SDL3 `src/joystick/hidapi/SDL_hidapi_8bitdo.c`
- JSM `JoyShockMapper/src/SDLWrapper.cpp` (or actual wrapper filename)

## Summary

| # | Question | Verdict | Evidence (file:line) | Notes |
|---|----------|---------|----------------------|-------|
| 1 | VID/PID match `2DC8:6012` | clear/partial/gap/unknown | SDL_hidapi_8bitdo.c:N | ... |
| 2 | 34-byte v1.03 report parsed, sensor block at offsets 15–26 | ... | ... | ... |
| 3 | Gyro → `SDL_SendJoystickSensor(SDL_SENSOR_GYRO, ...)` | ... | ... | ... |
| 4 | Scale preserved (full ±2000 dps → ±34.9 rad/s) | ... | ... | ... |
| 5 | Button coverage count + extras mapping | ... | ... | ... |
| 6 | Sample-rate pass-through (no throttle / coalesce) | ... | ... | ... |
| 7 | JSM calls `SDL_SetGamepadSensorEnabled(..., SDL_SENSOR_GYRO, true)` | ... | ... | ... |
| 8 | JSM reads sensor data (poll or event) | ... | ... | ... |
| 9 | Gyro value reaches JSM's GYRO binding (sign/units correct) | ... | ... | ... |
| 10 | JSM iterates button extras (paddles/MISC) | ... | ... | ... |

## Overall verdict

**<GREEN / YELLOW / RED>**

- **Green** — all 10 clear; proceed directly to Phase 2.
- **Yellow** — proceed with flagged watch-items: <list specific Qs and what to verify live in Phase 2>.
- **Red** — blocking gap at <layer>; do not build. See Escalation below.

## Escalation (only if Yellow or Red)

<Specific upstream-issue sketch: which repo (libsdl-org/SDL or Electronicks/JoyShockMapper), which file, what's broken, what the fix shape looks like. Interim plan: keep `tools/jsm_bridge.py` as primary.>

## References

- `findings/gyro_hid.md` — 34-byte report layout, axis mapping, exclusive-access gotchas
- `findings/jsm_wrapper_substrate.md` — prior research identifying JSM+SDL3 as the recommended path
- `docs/superpowers/specs/2026-04-20-jsm-sdl3-viability-design.md` — spec this finding feeds into
```

#### Step 4.2: Delete the scratch artifacts

- [ ] Run: `rm %USERPROFILE%\Claude\JangsJyro\.phase1-pins.txt && rm -rf %USERPROFILE%\Claude\JangsJyro\.phase1-scratch`

Expected: both removed. Pin values are now in the finding doc.

#### Step 4.3: Update BACKLOG

- [ ] In `BACKLOG.md`, under the JSM-verification item, append a sub-bullet:

```markdown
  - [~] Phase 1 static source verification complete (YYYY-MM-DD): <verdict>.
    See `findings/jsm_sdl3_source_verification.md`.
```

Expected: the `[ ]` item becomes `[~]` (in progress) if verdict is green/yellow, or `[x]` (done, but non-adoption) if red.

---

### Task 5: Gate 1 decision

**Files:** none — this is a branch point.

#### Step 5.1: Read the verdict from the finding doc

- [ ] Open `findings/jsm_sdl3_source_verification.md` and confirm the "Overall verdict" line.

#### Step 5.2: Route

- [ ] **If verdict is RED:** stop. The escalation section of the finding is the next action (file an upstream issue per the sketch). `jsm_bridge.py` remains primary. Update BACKLOG to mark the JSM verification item Done with outcome "substrate path blocked at <layer>". Do NOT proceed to Task 6.
- [ ] **If verdict is YELLOW:** record the watch-items in a checklist at the top of Task 10's notes (Phase 2b will verify them live). Proceed to Task 6.
- [ ] **If verdict is GREEN:** proceed directly to Task 6.

- [ ] **STOP for user checkpoint.** Share the verdict, the evidence, and which route is being taken. Do not silently proceed to toolchain install on a red-verdict finding.

---

## PHASE 2 — Build + SDL3 isolation + JSM live test (Gate 2)

Goal: build JSM master and a side-build of SDL3, run SDL3's `testcontroller` to isolate SDL3-vs-JSM faults, then run JSM live and measure button coverage, gyro, scale, and sample rate.

### Task 6: Install / verify toolchain

Condensed from the prior plan (`docs/superpowers/plans/2026-04-19-jsm-master-sdl3-build.md` Task 1). Cross-reference it if any step below surfaces an edge case.

**Files:** none — environment setup.

#### Step 6.1: Check current CMake

- [ ] Run: `cmake --version`

Expected: version line ≥ 3.28. If below 3.28 or not found, continue to Step 6.2.

#### Step 6.2: Install CMake (only if Step 6.1 failed)

- [ ] Run: `winget install --id Kitware.CMake --exact --accept-source-agreements --accept-package-agreements`
- [ ] Open a new shell. Confirm: `cmake --version` prints 3.28+.

#### Step 6.3: Check Visual Studio Build Tools

- [ ] Run: `"/c/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe" -latest -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`

Expected: non-empty path. Empty means install needed — continue to Step 6.4.

#### Step 6.4: Install VS 2022 Build Tools with C++ workload (only if Step 6.3 empty)

- [ ] Run:

```
winget install --id Microsoft.VisualStudio.2022.BuildTools --exact --override "--quiet --wait --add Microsoft.VisualStudio.Workload.VCTools --add Microsoft.VisualStudio.Component.VC.Tools.x86.x64 --add Microsoft.VisualStudio.Component.Windows11SDK.22621 --includeRecommended" --accept-source-agreements --accept-package-agreements
```

Runtime: 10–20 minutes. Expected final output: `Successfully installed`. Re-run Step 6.3 to confirm.

#### Step 6.5: Check Git

- [ ] Run: `git --version`. Expected 2.x line. If missing: `winget install --id Git.Git --exact` then new shell.

- [ ] **STOP for user checkpoint.** Confirm CMake ≥ 3.28, VS Build Tools with C++ workload, and Git are all present before Task 7.

---

### Task 7: Clone JSM master and build

**Files:**
- Create: `%USERPROFILE%\Claude\JangsJyro-JSM\` (git clone target)
- Create: `%USERPROFILE%\Claude\JangsJyro-JSM\build\JoyShockMapper\Release\JoyShockMapper.exe` + `SDL3.dll`

#### Step 7.1: Verify clone target does not exist

- [ ] Run: `ls "$HOME/Claude/JangsJyro-JSM" 2>&1`

Expected: `No such file or directory`. If it exists, **stop and ask the user** whether to delete / reuse / pick a different path.

#### Step 7.2: Clone at the Phase-1-pinned SHA

- [ ] Run:

```
git clone https://github.com/Electronicks/JoyShockMapper.git "$HOME/Claude/JangsJyro-JSM"
cd "$HOME/Claude/JangsJyro-JSM"
git checkout <JSM-SHA-from-Phase-1>
git rev-parse HEAD
```

Expected: the echoed SHA matches the Phase 1 pin exactly. If the SHA has moved since Phase 1 (upstream pushed to master), **stop and ask the user** whether to re-run Phase 1 at the new SHA or proceed with the old SHA.

#### Step 7.2.5: Apply the Phase 1 SDL3-pin amendment

- [ ] In `%USERPROFILE%\Claude\JangsJyro-JSM\JoyShockMapper\CMakeLists.txt`, change the single line `GIT_TAG release-3.2.x` to `GIT_TAG release-3.4.4`. The `release-3.2.x` pin predates `SDL_hidapi_8bitdo.c`; the Phase 1 finding was produced against `release-3.4.4` (SHA `5848e584a1b606de26e3dbd1c7e4ecbc34f807a6`).

Expected: exactly one line changed. If the plan or Phase 1 finding ever updates to a newer SDL3 pin, use that SHA instead.

#### Step 7.3: Configure CMake

- [ ] Run (from `%USERPROFILE%\Claude\JangsJyro-JSM\`):

```
mkdir -p build && cd build
cmake .. -G "Visual Studio 17 2022" -A x64 -DSDL=ON
```

`-DSDL=ON` is **required on Windows**. JSM's Windows branch at `JoyShockMapper/CMakeLists.txt:60` uses `if(SDL)`, not `if(SDL OR NOT DEFINED SDL)` (which is what the Linux branch uses). Without the explicit flag, configure falls through to the JSL path and errors with `No target "JoyShockLibrary"`.

Expected signals (all four should appear):
1. `-- The CXX compiler identification is MSVC 19.4x.xxxxx`
2. `[CPM] Adding package SDL@3.2.x (release-3.2.x)` and a clone-from-libsdl-org line (first time only; 2–4 min)
3. `[CPM] Adding package ViGEmClient`
4. `-- Configuring done` / `-- Generating done`

If configure fails, cross-reference the prior plan's troubleshooting list at `docs/superpowers/plans/2026-04-19-jsm-master-sdl3-build.md:226-236`.

#### Step 7.4: Build

- [ ] Run (from `build/`): `cmake --build . --config Release --parallel`

Expected runtime: 3–8 minutes. Final lines: `0 Error(s)` and a build summary.

#### Step 7.5: Verify outputs

- [ ] Run: `ls "$HOME/Claude/JangsJyro-JSM/build/JoyShockMapper/Release/"`

Expected: `JoyShockMapper.exe`, `SDL3.dll`, and possibly a `GyroConfigs/` folder. Exe size ~2–4 MB.

#### Step 7.6: Confirm SDL3 is dynamically linked

- [ ] Run:

```
"/c/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Tools/MSVC/"*"/bin/Hostx64/x64/dumpbin.exe" /dependents "$HOME/Claude/JangsJyro-JSM/build/JoyShockMapper/Release/JoyShockMapper.exe" | head -40
```

Expected: `SDL3.dll` appears in the dependents list. If not, SDL3 didn't link — cross-reference the JSM CMake option (`option(SDL "..." ON)`) and re-run Task 7.3 with `-DSDL=ON` explicitly.

- [ ] **STOP for user checkpoint.** Confirm build produced JSM + SDL3.dll and dumpbin shows SDL3 as dependency.

---

### Task 8: Side-build SDL3 with SDL_TESTS=ON for testcontroller

JSM's CMake does not enable SDL3's test targets. A separate clone at the SHA JSM used produces `testcontroller.exe` for the isolation probe.

**Files:**
- Create: `%USERPROFILE%\Claude\SDL\` (git clone target)
- Create: `%USERPROFILE%\Claude\SDL\build\test\Release\testcontroller.exe`

#### Step 8.1: Verify SDL3 side-clone target does not exist

- [ ] Run: `ls "$HOME/Claude/SDL" 2>&1`

Expected: `No such file or directory`. If it exists, ask the user.

#### Step 8.2: Clone SDL3 at the Phase-1-pinned SHA

- [ ] Run:

```
git clone https://github.com/libsdl-org/SDL.git "$HOME/Claude/SDL"
cd "$HOME/Claude/SDL"
git checkout <SDL3-SHA-from-Phase-1>
git rev-parse HEAD
```

Expected: the echoed SHA matches the Phase 1 pin.

#### Step 8.3: Configure with tests enabled

- [ ] Run (from `%USERPROFILE%\Claude\SDL\`):

```
mkdir -p build && cd build
cmake .. -G "Visual Studio 17 2022" -A x64 -DSDL_TESTS=ON
```

Expected: `-- Configuring done` / `-- Generating done`. The `SDL_TESTS=ON` option enables `test/` subdirectory build.

#### Step 8.4: Build only testcontroller

- [ ] Run (from `build/`): `cmake --build . --config Release --parallel --target testcontroller`

Expected runtime: 2–5 minutes (builds SDL3 first, then testcontroller). Final: `0 Error(s)`.

#### Step 8.5: Verify binary

- [ ] Run: `ls "$HOME/Claude/SDL/build/test/Release/testcontroller.exe"`

Expected: file exists. If the build structure differs (SDL3's test-exe output path can vary by generator), run: `find "$HOME/Claude/SDL/build" -name "testcontroller.exe"` to locate it.

#### Step 8.6: Fallback — standalone probe

- [ ] **Only if Step 8.4 failed irrecoverably:** write a minimal C probe at `%USERPROFILE%\Claude\SDL\probe\probe.c`:

```c
#include <SDL3/SDL.h>
#include <stdio.h>

int main(void) {
    if (!SDL_Init(SDL_INIT_GAMEPAD | SDL_INIT_SENSOR)) return 1;
    int count = 0;
    SDL_JoystickID *ids = SDL_GetJoysticks(&count);
    for (int i = 0; i < count; i++) {
        SDL_Gamepad *gp = SDL_OpenGamepad(ids[i]);
        if (!gp) continue;
        printf("Gamepad: %s (id=%u)\n", SDL_GetGamepadName(gp), ids[i]);
        SDL_SetGamepadSensorEnabled(gp, SDL_SENSOR_GYRO, true);
        Uint64 start = SDL_GetTicks();
        Uint64 last = 0;
        int updates = 0;
        while (SDL_GetTicks() - start < 10000) {
            SDL_PumpEvents();
            float data[3];
            if (SDL_GetGamepadSensorData(gp, SDL_SENSOR_GYRO, data, 3)) {
                Uint64 now = SDL_GetTicksNS();
                if (last) printf("+%llu ns gyro=%.3f,%.3f,%.3f rad/s\n", now - last, data[0], data[1], data[2]);
                last = now;
                updates++;
            }
            SDL_Delay(1);
        }
        printf("Total updates in 10s: %d (≈%d Hz)\n", updates, updates / 10);
        SDL_CloseGamepad(gp);
    }
    SDL_free(ids);
    SDL_Quit();
    return 0;
}
```

Compile against the side-built SDL3 (details depend on shell; use `cl /I<sdl-include> probe.c /link <sdl3.lib>` from a VS dev prompt) and use this in place of `testcontroller` for Task 10.

---

### Task 9: Prep environment for live tests

**Files:** none — environment setup.

#### Step 9.1: Exit interfering software

- [ ] Right-click 8BitDo Ultimate Software tray icon → **Exit** (not minimize).
- [ ] Right-click Steam tray icon → **Exit** (fully, not just close window).

#### Step 9.2: Pad mode

- [ ] Power pad off. Hold **B** while pressing the power button. Confirm mode LED shows DInput.

#### Step 9.3: Verify pad VID/PID

- [ ] Run:

```
python -c "import hid; print([d for d in hid.enumerate(0x2DC8, 0x6012) if d.get('usage_page')==1 and d.get('usage')==5])"
```

Expected: a non-empty list with `'product_string': '8BitDo Ultimate 2 ...'`. Empty means the tray app or Steam is still holding HID — re-check Step 9.1.

#### Step 9.4: Baseline raw-HID rate

- [ ] Run: `python "%USERPROFILE%\Claude\JangsJyro\tools\gyro_meter.py"` for 10 seconds, rotating the pad continuously.

Expected: the tool reports an update rate around 125 Hz (per `findings/gyro_hid.md`). Record this number — it's the baseline for Task 10.6's rate comparison.

Press Ctrl+C to exit. If `gyro_meter.py` doesn't report rate directly, observe the update cadence visually or use `gyro_probe_hid.py` / `gyro_enum.py` as alternatives.

---

### Task 10: Phase 2b — SDL3 isolation probe

**Files:** none — this is a live test.

#### Step 10.1: Run testcontroller

- [ ] Run: `"$HOME/Claude/SDL/build/test/Release/testcontroller.exe"`

Expected: a window opens showing detected controllers. The Ultimate 2 should appear with a name like "8BitDo Ultimate 2 Wireless Controller for PC" (SDL3's driver) — record the exact string.

If the pad doesn't appear, re-check Task 9 preconditions.

#### Step 10.2: Verify gamepad layout

- [ ] In testcontroller, select the pad. Expected: a standard gamepad visual with face buttons, d-pad, shoulders, triggers, sticks populated.

- [ ] Record: does the visual show paddle / MISC slots for L4/R4/PL/PR, and do those slots light up when you press the corresponding physical buttons?

#### Step 10.3: Exercise all 17 physical buttons

- [ ] Press each of the 17 physical inputs in sequence. For each: record whether testcontroller registers it, and if so, under which SDL3 enum (standard gamepad button, paddle, MISC, or raw joystick button).

Expected table columns: physical input | fires in testcontroller? | SDL3 slot.

#### Step 10.4: Sensor check — gyro present

- [ ] In testcontroller's sensor display (usually a sidebar or menu option for showing sensor data), enable gyro display. Rotate the pad.

Expected: gyro x/y/z values change smoothly in response to rotation. Record: scale visible (e.g. `~0.5 rad/s` during a moderate rotation, up to `~34.9 rad/s` during a fast spin).

#### Step 10.5: Scale check

- [ ] Perform a single sustained rotation at a known rate (e.g. rotate the pad at roughly 360°/sec on one axis). Record the peak rad/s reading from testcontroller.

Expected: ~6.28 rad/s (equal to 360°/s × π/180). Cross-check the Task 9.4 raw-HID baseline — the ratio between `gyro_meter.py`'s dps output and testcontroller's rad/s output should be π/180 ≈ 0.01745.

#### Step 10.6: Sample-rate measurement (first-class)

- [ ] Hold the pad steady. Switch testcontroller to a mode that prints timestamped sensor updates, or use the standalone probe from Task 8.6 which already prints inter-arrival times.

If testcontroller lacks timestamp output, rely on the standalone probe instead. Either way, collect ≥10 seconds of samples during sustained rotation.

Expected table row: `SDL3 layer: <mean inter-arrival> ms ±<stdev>, yielding ~<X> Hz`. Compare to the Task 9.4 raw-HID baseline.

Interpretation (per spec's rate-interpretation guideline):
- ~125 Hz → parity with raw HID
- 60–120 Hz → decimated but usable (adoption caveat later)
- <60 Hz → significantly degraded (re-escalate in Task 14)

#### Step 10.7: Close testcontroller

- [ ] Exit testcontroller. Leave the pad plugged in and in DInput mode for Task 12.

---

### Task 11: Gate 2b decision

**Files:** none — branch point.

#### Step 11.1: Tally Task 10 results

- [ ] Review Task 10 recordings:
  - Pad detected (10.1)? Y/N
  - Gamepad layout populated (10.2)? Y/N
  - Gyro sensor present (10.4)? Y/N
  - Scale sane (10.5)? Y/N

#### Step 11.2: Route

- [ ] **If pad not detected, OR sensor absent:** SDL3 does not plumb this pad / its sensors. Skip Task 12. Record the SDL3-level results in Task 13 and proceed directly to Task 14 which will route to **Branch F** (SDL3-level escalation).
- [ ] **If pad detected with working sensor:** proceed to Task 12.

- [ ] **STOP for user checkpoint.** Share the Task 10 findings and the route decision.

---

### Task 12: Phase 2c — JSM live probes

**Files:**
- Create: `%USERPROFILE%\test_jsm.txt` (JSM test config; deleted after test)

#### Step 12.1: Write minimal test config

- [ ] Create `%USERPROFILE%\test_jsm.txt` with each physical input bound to a distinct printable key plus a gyro-to-mouse binding:

```
RESET_MAPPINGS
UP = W
DOWN = S
LEFT = A
RIGHT = D
N = I
S = K
E = L
W = J
L = Q
R = E
ZL = Z
ZR = C
PLUS = F
MINUS = G
HOME = H
CAPTURE = V
LSL = U
LSR = O

# Paddles / extras — JSM keyword syntax varies; consult JSM's README at execution
# time. For SDL3 paddle slots JSM may use PADDLE1, PADDLE2, PADDLE3, PADDLE4 or
# numeric JOYB_N for out-of-standard-layout buttons. Fill in per JSM version.
# PADDLE1 = 1
# PADDLE2 = 2
# PADDLE3 = 3
# PADDLE4 = 4

GYRO_ON = Tap
GYRO_SENS = 2
MOUSE_X_FROM_GYRO_AXIS = YAW
MOUSE_Y_FROM_GYRO_AXIS = PITCH
```

Expected: file saved. Leave TODO-style commented lines for paddle bindings — Task 12.4 resolves exact JSM keyword syntax at execution time.

#### Step 12.2: Launch JSM with verbose logging

- [ ] Open a console (not a VS dev prompt) and run:

```
SDL_LOG_PRIORITY=VERBOSE "$HOME/Claude/JangsJyro-JSM/build/JoyShockMapper/Release/JoyShockMapper.exe" "%USERPROFILE%\test_jsm.txt"
```

Expected: JSM prints banner (version, `Using SDL3 backend`), then enumerates the pad with the name recorded in Task 10.1. The SDL3 verbose output should mention opening the HIDAPI 8BitDo driver.

If JSM prints `No controllers detected`: re-check Task 9 preconditions and the Task 7 build (particularly the `SDL3.dll` dependency from Step 7.6).

#### Step 12.3: Probe P1 — identification

- [ ] Record the exact pad name JSM reports. Compare to Task 10.1's testcontroller string — should match. Mismatch indicates JSM is taking a different SDL path than testcontroller (rare but investigate).

#### Step 12.4: Probe P2 — standard button coverage

- [ ] Press each of the 13 standard-layout physical inputs (not paddles/extras). For each, watch JSM's console for a "pressed" line and confirm the mapped key fires (the console will echo keystrokes as they emit).

Record a table: physical input | fires? | JSM-reported name.

#### Step 12.5: Probe P3 — extras (L4/R4/PL/PR)

- [ ] Press each of the 4 extras once. From JSM's console output, identify the JSM keyword it uses for each extra (common: `L4`, `R4`, `PL`, `PR`, `PADDLE1..4`, or `JOYB_NN`). Amend `%USERPROFILE%\test_jsm.txt` with bindings for any that JSM recognized but the config didn't bind (add lines like `PADDLE1 = 1`), save, and type `RELOAD` in JSM's console to apply.

Re-press each extra after reload to confirm the binding fires. Record: input | JSM name | fires?

#### Step 12.6: Probe P4 — gyro directionality

- [ ] Rotate pad yaw left/right, pitch up/down, roll cw/ccw. For each, observe mouse cursor motion.

Expected directions (per `findings/gyro_hid.md` axis mapping):
- yaw right → mouse moves right (positive X)
- yaw left → mouse moves left (negative X)
- pitch down (nose down) → mouse moves up (negative Y, following game FPS convention)
- pitch up → mouse moves down
- roll: no motion expected unless `ROLL_SENS` is nonzero

Record any axis where direction is inverted or dead. Sign flips are cosmetic (fixable in config) but should be noted.

#### Step 12.7: Probe P5 — gyro scale

- [ ] Repeat the ~360°/s rotation from Task 10.5. Observe mouse travel distance (pixels). Compare to expected:

Mouse-X travel per second ≈ (gyro dps) × (GYRO_SENS config value) × (JSM internal scale). For `GYRO_SENS = 2`, a 360°/s yaw should produce a consistent, calibratable mouse movement. The exact number is less important than consistency — the JSM value should be a clean multiple of SDL3's rad/s reading from Task 10.5.

Record: observed peak mouse dps (computable from cursor travel / time) vs testcontroller peak rad/s. Flag non-unit factors.

#### Step 12.8: Probe P6 — sample rate at JSM layer

- [ ] Under sustained steady rotation, count mouse events emitted per second by JSM. Methods:
  - If JSM has a `DEBUG = ON` or similar diagnostic flag, enable it and capture per-frame event logs
  - Otherwise: run a small window-timer process on the side (e.g. `python -c "import win32api; ..."` to sample cursor position at 1000 Hz and log changes), infer JSM's effective event rate from cursor-change cadence

Expected: rate matches Task 10.6's SDL3-layer measurement (JSM pass-through). A lower rate indicates JSM is decimating further — flag for the finding.

#### Step 12.9: Exit JSM, clean up

- [ ] In JSM console: `QUIT` or close the window.
- [ ] Delete test config: `rm %USERPROFILE%\test_jsm.txt`

---

### Task 13: Write Phase 2 finding doc

**Files:**
- Create: `%USERPROFILE%\Claude\JangsJyro\findings\jsm_sdl3_live_verification.md`

#### Step 13.1: Write the finding

- [ ] Create `findings/jsm_sdl3_live_verification.md`:

```markdown
# JSM + SDL3 live verification — 8BitDo Ultimate 2 Wireless (DInput)

**Date:** <YYYY-MM-DD>
**Host:** <Windows version, e.g. Windows 11 Pro 10.0.26200>
**JSM SHA:** <from Task 7.2>
**SDL3 SHA:** <from Task 8.2>
**VS toolchain:** <from vswhere in Task 6.3>
**Pad firmware:** v1.09
**Pad mode:** DInput (VID 2DC8 / PID 6012)
**Transport:** 2.4 GHz dongle only (Bluetooth out of scope)

## Phase 2a — Build

- JSM binary: `%USERPROFILE%\Claude\JangsJyro-JSM\build\JoyShockMapper\Release\JoyShockMapper.exe` (<size> MB)
- SDL3.dll: verified as dependency via dumpbin
- testcontroller: `%USERPROFILE%\Claude\SDL\build\test\Release\testcontroller.exe`
- Build warnings of note: <list or "none">

## Phase 2b — SDL3 isolation

| Check | Result |
|-------|--------|
| Pad detected by SDL3 | yes/no — "<name string>" |
| Gamepad layout populated | yes/no |
| Standard 13-button coverage | N of 13 |
| Paddle/MISC slots for extras | <list of slots populated, or "none"> |
| Gyro sensor active | yes/no |
| Scale (360°/s rotation) | ~<X> rad/s (expected ~6.28) |
| Sample rate (SDL3 layer) | <Y> Hz, std <Z> ms (baseline raw HID: ~125 Hz) |

## Phase 2c — JSM live probes

(Omit this section if Phase 2b blocked and 2c was skipped.)

### P1 — identification
JSM reported pad as: "<verbatim name>"

### P2+P3 — button coverage

| Physical input | JSM keyword | Fires? |
|----------------|-------------|--------|
| (all 17 rows; fill from Tasks 12.4 and 12.5)               |

Total: <X> of 17 reachable.

### P4 — gyro directionality
| Axis | Expected | Observed | Notes |
|------|----------|----------|-------|
| yaw right | mouse right | — | — |
| yaw left | mouse left | — | — |
| pitch down | mouse up | — | — |
| pitch up | mouse down | — | — |

### P5 — gyro scale
- JSM mouse dps at 360°/s rotation: ~<X> dps
- SDL3 peak (Task 10.5): ~<Y> rad/s
- Ratio matches π/180 conversion? yes/no
- Any non-unit factor observed: <description or "none">

### P6 — sample rate (JSM layer)
- JSM effective event rate: ~<X> Hz
- SDL3 layer rate from 2b: ~<Y> Hz
- JSM decimation factor: <X/Y>

## Summary and Phase 3 input

- Button coverage: <all 17 / 13–16 with extras missing / <13 with standard button missing>
- Gyro: <works at full scale / works with scale-correctable factor / works with clipping / silent at JSM / silent at SDL3>
- Sample rate: <≈125 Hz / 60–120 Hz / <60 Hz>

→ Phase 3 branch (Task 14 decides): <preliminary match, to be confirmed in Task 14>

## References

- `findings/jsm_sdl3_source_verification.md` — Phase 1 source verification
- `docs/superpowers/specs/2026-04-20-jsm-sdl3-viability-design.md` — spec (decision tree in Phase 3 section)
- `findings/gyro_hid.md` — axis mapping reference
```

#### Step 13.2: Update BACKLOG

- [ ] In `BACKLOG.md`, append a sub-bullet under the JSM-verification item:

```markdown
  - [~] Phase 2 live verification complete (YYYY-MM-DD): coverage <X>/17,
    gyro <status>, rate <X> Hz. See `findings/jsm_sdl3_live_verification.md`.
```

- [ ] **STOP for user checkpoint.** Share the Phase 2 finding and the preliminary Phase 3 branch match before Task 14 locks in the decision.

---

## PHASE 3 — Adoption or fallback (Gate 3)

Goal: based on Phase 2 results, execute the matching branch from the decision tree. Adoption branches (A, B, D-correctable) produce usage artifacts and deprecate the bridge. Escalation branches (C, D-clipping, E, F, G, H) file upstream and keep the bridge as primary.

### Task 14: Select Phase 3 branch

**Files:** none — decision point.

#### Step 14.1: Match results to a branch

- [ ] Open `findings/jsm_sdl3_live_verification.md`. Run through this decision table in order — first match wins:

| # | Condition | Branch | Route |
|---|-----------|--------|-------|
| 1 | Build failed (Task 7 or 8) | G | Task 16 |
| 2 | JSM crashed/misbehaved on connect (Task 12.2) | H | Task 16 |
| 3 | Gyro silent at SDL3 layer (Task 10.4 "no") | F | Task 16 |
| 4 | Gyro works at SDL3 but silent at JSM (Task 10.4 "yes" + Task 12.6 no motion) | E | Task 16 |
| 5 | Gyro works at wrong scale, clipping/truncation (Task 10.5 or 12.7 shows ±1000 or similar) | D-clip | Task 16 |
| 6 | Standard button missing (Task 12.4 shows a non-extra input dead), or extras missing that are NOT the ViGEm bridge's set | C | Task 16 |
| 7 | Gyro works, sample rate <60 Hz (Task 10.6) | C (rate-escalation, per spec) | Task 16 |
| 8 | Gyro works with clean correctable factor (e.g. off by π/180, fixable in config) | D-correctable | Task 15 |
| 9 | Gyro full scale, ≥13 standard buttons, L4/R4/PL/PR missing (bridge parity) | B | Task 15 |
| 10 | Gyro full scale + all 17 buttons | A | Task 15 |

#### Step 14.2: Record the matched branch

- [ ] Append to `findings/jsm_sdl3_live_verification.md`:

```markdown

## Phase 3 branch match

Matched branch: **<letter>** — <rule # from Step 14.1>.
Rationale: <one sentence>.
Route: <Task 15 adoption | Task 16 escalation>.
```

- [ ] **STOP for user checkpoint.** Confirm the matched branch with the user before executing Task 15 or 16.

---

### Task 15: Adoption execution (Branches A, B, D-correctable)

**Files:**
- Create: `%USERPROFILE%\Claude\JangsJyro\findings\jsm_sdl3_verified.md`
- Create: `%USERPROFILE%\Claude\JangsJyro\tools\jsm_sdl3_config.txt`
- Modify: `%USERPROFILE%\Claude\JangsJyro\findings\gyro_hid.md` (new SDL3-status section)
- Modify: `%USERPROFILE%\Claude\JangsJyro\findings\jsm_wrapper_substrate.md` (superseded-by pointer at top)
- Modify: `%USERPROFILE%\Claude\JangsJyro\tools\jsm_bridge.py` (deprecation header comment block)
- Modify: `%USERPROFILE%\Claude\JangsJyro\BACKLOG.md` (mark item Done)

#### Step 15.1: Write the verified-adoption finding

- [ ] Create `findings/jsm_sdl3_verified.md`:

```markdown
# JSM + SDL3 direct DInput — verified and adopted

**Date:** <YYYY-MM-DD>
**Supersedes open questions in:** `findings/jsm_wrapper_substrate.md` (2026-04-19)
**JSM SHA:** <from live verification>
**SDL3 SHA:** <from live verification>
**Match:** Branch <A/B/D-correctable>

## Verified characteristics

- **Button coverage:** <X> of 17 physical inputs reachable via JSM bindings.
  <For Branch B: list exactly which of L4/R4/PL/PR are unreachable and at which layer (SDL3 or JSM).>
- **Gyro:** present via `SDL_SENSOR_GYRO`, direction <standard / sign flip in <axis>>.
- **Gyro scale:** <full ±2000 dps / correctable via `GYRO_SENS` multiplier of <N>>.
- **Sample rate:** <Y> Hz at SDL3 layer, <Y> Hz at JSM (no additional decimation).
  <Rate caveat if 60–120 Hz: "Below raw-HID baseline of ~125 Hz — gyro feel may be slightly chunkier on very fast motion; not a blocker.">

## Config scaffold

See `tools/jsm_sdl3_config.txt` for a layout matching the user's Steam Input
preferences. Tune sensitivity / threshold values to taste.

## What this supersedes

- The ViGEm-DS4 bridge at `tools/jsm_bridge.py` is no longer the primary path.
  A deprecation header has been added to that file; the file is kept as fallback
  reference until this path has been field-used for a reasonable period.
- The earlier caveat in `findings/gyro_hid.md` that SDL did not surface gyro
  for the Ultimate 2 in DInput mode is now superseded — see the new SDL3-status
  section added to that file.

## References

- `findings/jsm_sdl3_source_verification.md` (Phase 1)
- `findings/jsm_sdl3_live_verification.md` (Phase 2)
- `docs/superpowers/specs/2026-04-20-jsm-sdl3-viability-design.md`
```

#### Step 15.2: Write the JSM config scaffold

- [ ] Create `tools/jsm_sdl3_config.txt`. Base template (the user will tune sensitivity/threshold values; use their Steam-Input-style terminology per `CLAUDE.md` convention):

```
# JSM config — 8BitDo Ultimate 2 Wireless (DInput mode via SDL3)
# Matches user's Steam Input layout.
# Adopted: <YYYY-MM-DD>. See findings/jsm_sdl3_verified.md.

RESET_MAPPINGS

# --- Face buttons (use the user's Steam-Input vocabulary, not VDF field names) ---
N =
E =
S =
W =

# --- D-pad ---
UP =
DOWN =
LEFT =
RIGHT =

# --- Shoulders / triggers ---
L =
R =
ZL =
ZR =

# --- Stick clicks ---
LSL =
LSR =

# --- System buttons ---
MINUS =
PLUS =
HOME =
CAPTURE =

# --- Extras (Branch A only; for Branch B, comment out with a note per omission) ---
# JSM keyword discovered in Phase 2c Task 12.5: <fill in exact names>
# PADDLE1 =   # physical L4
# PADDLE2 =   # physical R4
# PADDLE3 =   # physical PL
# PADDLE4 =   # physical PR

# --- Gyro (use the user's Steam Input vocabulary for these behaviors) ---
# "Precision speed" (Steam Input) ≈ GYRO_SENS scaling factor
GYRO_SENS = 2
# "Movement threshold" ≈ GYRO_CUTOFF_RECOVERY
GYRO_CUTOFF_RECOVERY = 0
# "Smooth fine movements" ≈ GYRO_SMOOTH_THRESHOLD
GYRO_SMOOTH_THRESHOLD = 0

GYRO_ON = Tap
MOUSE_X_FROM_GYRO_AXIS = YAW
MOUSE_Y_FROM_GYRO_AXIS = PITCH

# <For Branch D-correctable: add the compensation factor here with a comment explaining why.>
```

The scaffold leaves action bindings blank — the user fills these in against their Steam Input layout. Save the file.

#### Step 15.3: Append deprecation header to jsm_bridge.py

- [ ] Open `tools/jsm_bridge.py`. At the very top, above the existing module docstring or code, insert this comment block:

```python
# ============================================================================
# DEPRECATED as of <YYYY-MM-DD> — superseded by the direct JSM + SDL3 path.
#
# JSM master with its default SDL3 backend reaches this pad natively via
# SDL3's SDL_hidapi_8bitdo driver (verified Phase 2 live, matching Branch
# <A/B/D-correctable>). The Python + virtual-DS4 hop is no longer needed.
#
# See findings/jsm_sdl3_verified.md for adoption details and the JSM config
# scaffold at tools/jsm_sdl3_config.txt. This file is kept as fallback
# reference in case a regression surfaces — do not delete without updating
# the finding.
# ============================================================================
```

Do **not** modify any code below the header. Save.

#### Step 15.4: Update findings/gyro_hid.md

- [ ] At the top of `findings/gyro_hid.md`, before the first `##` heading, insert:

```markdown
## SDL3 status on the Ultimate 2 Wireless (DInput) — updated <YYYY-MM-DD>

As of JSM master @ SHA `<JSM-SHA>` with SDL3 @ SHA `<SDL3-SHA>`, SDL3's
`SDL_hidapi_8bitdo.c` driver **does** surface the pad's gyro via
`SDL_SENSOR_GYRO` in DInput mode. This supersedes the earlier caveat below
that SDL did not plumb sensors for this pad. The raw-HID path is still the
reference for tools that need direct HID access (e.g. `gyro_meter.py`) — the
layout table, scale factors, and axis mapping elsewhere in this document
remain correct for anything that reads HID directly.

See `findings/jsm_sdl3_verified.md`.

---

```

Save.

#### Step 15.5: Add superseded-by pointer to jsm_wrapper_substrate.md

- [ ] At the very top of `findings/jsm_wrapper_substrate.md`, before the first `#` heading, insert:

```markdown
> **Superseded (<YYYY-MM-DD>):** the substrate question is closed. See
> `findings/jsm_sdl3_verified.md`. Open questions listed below in
> "Unknowns" are resolved in the Phase 1 and Phase 2 findings.

```

Save.

#### Step 15.6: Update BACKLOG

- [ ] In `BACKLOG.md`, find the JSM-verification item. Replace its current description with:

```markdown
- [x] **Verify JSM-from-master + SDL3 default backend with the 8BitDo
  Ultimate 2 Wireless** (<YYYY-MM-DD>). Adopted — Branch <A/B/D-correctable>.
  See `findings/jsm_sdl3_verified.md`.
```

Move it to the Done section. Save.

- [ ] **STOP for user checkpoint.** Summarize: which adoption branch, what's in the config scaffold, what artifacts landed. Do not proceed to any further work without user sign-off on the adoption.

---

### Task 16: Escalation execution (Branches C, D-clipping, E, F, G, H)

**Files:**
- Modify: `%USERPROFILE%\Claude\JangsJyro\findings\jsm_sdl3_live_verification.md` (append escalation plan)
- Optional create: `%USERPROFILE%\Claude\JangsJyro\handoffs\jsm_sdl3_upstream_patch.md`
- Modify: `%USERPROFILE%\Claude\JangsJyro\BACKLOG.md` (mark item Done with escalation pointer)

Bridge remains primary — `tools/jsm_bridge.py` is **not** modified on any escalation branch.

#### Step 16.1: Append escalation plan to the live-verification finding

- [ ] In `findings/jsm_sdl3_live_verification.md`, append this section:

```markdown

## Escalation

**Branch:** <C | D-clip | E | F | G | H>
**Layer where fault lives:** <SDL3 / JSM / build environment>
**Upstream issue to file:**
- Repo: <libsdl-org/SDL | Electronicks/JoyShockMapper>
- Summary: <one-line title for the issue>
- Body draft:

  ```
  <concrete reproducer steps, test environment details, expected vs actual behavior,
  citations from findings/jsm_sdl3_source_verification.md where applicable>
  ```

**Interim plan:** `tools/jsm_bridge.py` remains the primary path; the ViGEm-DS4
bridge's known limitations (4-button deficit, ViGEmBus archived status) are
accepted until the upstream issue is resolved.

**Revisit after:** <specific signal — upstream merge, new SDL3 release tag, new
JSM release, etc.>

**Upstream issue URL:** <fill in after filing>
```

- [ ] File the upstream issue on GitHub (via web or `gh issue create`). Paste the final issue URL back into the finding doc.

#### Step 16.2: Optional — draft patch sketch

- [ ] If Phase 1 identified a specific code location for the fix (Branches C or E where JSM/SDL3 lacks an iteration or call), create `handoffs/jsm_sdl3_upstream_patch.md`:

```markdown
# Patch sketch — <SDL3 | JSM> fix for <Branch>

## Context

Live verification on <date> matched Branch <letter>. Root cause: <one-line>.

## Target

- File: <repo>/<path>:<line-range>
- Function: <name>

## Proposed change

<pseudo-code or diff sketch showing the minimal edit — e.g. "iterate SDL_GAMEPAD_BUTTON_MAX instead of 13" or "add sensor-enable call in the connect path">

## Testing

- Reproducer: `testcontroller` shows <X>, after patch it shows <Y>.
- JSM live test: re-run Phase 2 Task 12, expect <Z>.

## Status

- [ ] Patch drafted
- [ ] PR opened (URL: ... )
- [ ] Merged (date, SHA: ... )
```

#### Step 16.3: Update BACKLOG

- [ ] In `BACKLOG.md`, replace the JSM-verification item with:

```markdown
- [x] **Verify JSM-from-master + SDL3 default backend with the 8BitDo
  Ultimate 2 Wireless** (<YYYY-MM-DD>). Outcome: Branch <letter> — not adopted;
  `tools/jsm_bridge.py` remains primary. Upstream issue: <URL>. See
  `findings/jsm_sdl3_live_verification.md`.
```

Move to Done section. Save.

- [ ] **STOP for user checkpoint.** Summarize: which escalation branch, what issue was filed, what remains primary. Confirm the user has no additional escalation asks before closing the plan.

---

## When to stop and ask

- **Task 5 Gate 1 RED verdict:** always stop. Do not silently skip to Phase 2.
- **Task 6 install failures:** report the exact winget error and the installer log path (`%TEMP%\dd_bootstrapper_*.log`). Do not guess.
- **Task 7.2 or 8.2 SHA mismatch:** upstream has moved since Phase 1. Ask the user whether to re-run Phase 1 at the new SHA or proceed with the old SHA checked out.
- **Task 7.6 SDL3 not linked:** JSM's build fell through to the JSL path. Do not proceed to Task 8 until this is resolved.
- **Task 11 Gate 2b fail:** the SDL3 isolation probe failed. Skip Task 12; proceed to Task 13/14 → Branch F.
- **Task 14 ambiguous match:** if Phase 2 results don't cleanly match one of the 10 decision-table rules, ask the user — don't invent an 11th branch.
- **Any observed pad behavior surprising enough to undermine prior findings:** stop and surface it. The `findings/` corpus is cumulative — contradictions are signal, not noise.
