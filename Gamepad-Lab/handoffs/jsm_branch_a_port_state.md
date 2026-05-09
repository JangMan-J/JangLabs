# JSM Branch A port — session state (2026-04-22)

Compact snapshot of in-progress work. Plan file is authoritative for design;
this doc captures SHAs, discovered config quirks, and execution progress.

Plan file: `%USERPROFILE%\.claude\plans\alright-claude-i-want-buzzing-mccarthy.md`

## TL;DR

Branch A is **live and live-verified 2026-04-22** on the 8BitDo Ultimate 2
Wireless. 21/21 physical inputs (17 standard + 4 extended paddles) fire correct ButtonIDs, gyro feel unchanged
from Branch B. Code work complete. **Workspace artifacts (Step 7) landed
2026-04-22** — findings promoted, live-verification doc appended, config
scaffold updated, BACKLOG reconciled. Step 8 (upstream PR prep) is the next
item but is **paused per user request**. Step 6 (timer QoL) done 2026-04-23.

## Build state

- JSM tree: `%USERPROFILE%\Claude\JangsJyro-JSM\`
- Branch: `branch-a-port` (18 commits ahead of `master` @ `bb69784`)
- Binary: `build/JoyShockMapper/Release/JoyShockMapper.exe` (~1.01 MB, built 2026-04-22 07:59)
- SDL3.dll: alongside the exe, release-3.4.4
- Fork remote: `custom_curve` → `https://github.com/evan1mclean/JSM_custom_curve` (branch is `main` not `master`)

## branch-a-port commits (oldest → newest)

11 cherry-picks + 3 local JangMan fixes. All cherry-picks preserve original
authorship (Ceski / evan.mclean).

| Local SHA | Author | Fork SHA | Subject |
|-----------|--------|----------|---------|
| `437476f` | ceski | `f88664f` | Update button flags to 64-bit (prereq) |
| `44091ec` | ceski | `dfb5f17` | Add JS_TYPE_UNKNOWN |
| `2c07c5e` | ceski | `b0160a6` | Add device bus definitions |
| `8628395` | ceski | `7fa8fb0` | Clean up existing VID/PID values |
| `439dc1e` | ceski | `78d7848` | Add capacitive touch, mini shoulder, misc buttons |
| `41ba070` | ceski | `a68cbff` | Update default mapping for unknown controllers |
| `c501407` | evan.mclean | `fc51c0d` | Fix missing break in vendor switch + uint64 expand |
| `b368fa5` | ceski | `a4c7e63` | **All 8BitDo controllers** (Ultimate 2 + SF30/SN30/Pro/Pro2/Pro3) |
| `6b7f923` | ceski | `66557f6` | Flydigi (Apex 5, Vader 3/4/5 Pro) |
| `dc07961` | ceski | `b8579b4` | Fix Switch pro controller mapping |
| `afbea5f` | ceski | `3d36aa7` | Switch 2 Pro controller (USB only) |
| `09b84db` | JangMan | — | Local patches re-apply (SDL3 pin `release-3.4.4`, touchpad guard) |
| `4d8927e` | JangMan | — | Fix merge artifacts in vendor switch (duplicate case JS_VENDOR_NINTENDO + missing break after JS_VENDOR_GAMESIR) |
| `3979fed` | JangMan | — | Restore missing `SDL_GUID _guid;` member in `ControllerDevice` |

### Fork commits that became empty no-ops

Three cherry-picks skipped because the fork's DAG absorbed their content into
earlier commits during conflict resolution (not a loss — spec review verified
the effects landed). Document for upstream PR prep: when re-deriving for
upstream, take these directly from the fork in DAG order so each commit
compiles in isolation.

- `3ed4c09` (Fix paddles for default controllers) — content absorbed into `f88664f` ripple
- `97c1a0b` (GameSir G7 Pro 8K) — content absorbed into `fc51c0d` resolution
- `704aa81` (HORI Steam Controller) — content absorbed into `fc51c0d` resolution

### Known git-bisect hazard

Intermediate commits on our branch won't compile in isolation (resolving
`fc51c0d` pulled in symbols that later commits add). Tip compiles cleanly.
For upstream PR prep, re-derive from the fork directly in DAG order, not
from our branch.

## Live verification (2026-04-22)

**Config file:** `%USERPROFILE%\test_jsm.txt`

**Procedure:** pad in DInput mode (B+power), 8BitDo Ultimate Software exited,
Steam exited, pad paddle macros cleared in Ultimate Software. Launched with
`& "%USERPROFILE%\Claude\JangsJyro-JSM\build\JoyShockMapper\Release\JoyShockMapper.exe" "%USERPROFILE%\test_jsm.txt"` (PowerShell — `&` call operator required).

**Results (see `reference/JSM_JangManJ/run2.txt` for raw output + final paddle log):**
- 13 standard buttons all fire correct keystrokes (dpad, face, L/R/ZL/ZR, L3/R3)
- `-` and `+` (MINUS/PLUS) fire correctly
- HOME toggles gyro off (ratchet modifier)
- CAPTURE: pad has no physical capture button (not a regression)
- **L4 → LMINI → emits `1`** ✓
- **R4 → RMINI → emits `2`** ✓
- **PL → LSL → emits `3`** ✓
- **PR → RSR → emits `4`** ✓
- Gyro: "great", cursor smooth, full scale, feels identical to Branch B

## Config syntax quirks (discovered this session)

Not obvious from the plan template — worth capturing in the findings doc:

- **MINUS/PLUS** are registered as `-` and `+` keywords, NOT "MINUS" / "PLUS". The operator overload at `operators.cpp:43-46` maps `ButtonID::MINUS → "-"` and `ButtonID::PLUS → "+"` in both directions.
- **MOUSE_X_FROM_GYRO_AXIS / MOUSE_Y_FROM_GYRO_AXIS** take `Y` / `X` (or `WORLD_Y` / `PLAYER_Y` etc.) — NOT `YAW` / `PITCH`. The Phase 2 Task 12 plan template had the wrong keywords; JSM 3.6.1 rejects `YAW`/`PITCH`.
- **Gyro ratchet**: `HOME = ^GYRO_OFF` makes gyro always-on and HOME the momentary-disable modifier. Do NOT use `GYRO_ON = Tap` (also accepted but less predictable).
- **PowerShell invocation**: needs `&` call operator before the quoted exe path. `cmd.exe` is fine without it.

## Pad-side gotcha (cost us one test iteration)

8BitDo Ultimate Software paddle-macro profiles override native paddle events.
If paddles fire as standard-button macros (e.g. L4 → "LT + Y", R4 → "BACK",
PL/PR → stick clicks), the pad firmware/Ultimate Software has macros assigned.
Clear paddle macros in Ultimate Software, then the pad will emit native
`SDL_GAMEPAD_BUTTON_LEFT_PADDLE1/2` + `RIGHT_PADDLE1/2` and the JSM-side
Ultimate 2 type case at `SDLWrapper.cpp:620-626` maps them to LMINI/RMINI/LSL/RSR.

## Remaining work

### Step 7 — Update workspace artifacts (DONE 2026-04-22)

Landed as 4 parallel subagent edits in the JangsJyro workspace. Per-file
outcomes:

1. **`findings/jsm_sdl3_verified.md`** — promoted Branch B → Branch A.
   Header Match line now reads "Branch A (21/21 physical inputs, gyro
   unchanged from Branch B)". Verified-characteristics rewritten for 21/21
   (paddles routed via `SDLWrapper.cpp:620-626`, CAPTURE reclassified as
   "not present on pad"). Branch-B patches kept under a new subheading,
   flagged as carried by `09b84db`. New `## Branch A achieved (2026-04-22)`
   section with full 11-row commit table (local SHA / author / fork SHA /
   subject), 3 JangMan commits, empty-no-op list, verified-scope
   (tested vs. structurally-present-untested), git-bisect hazard. New
   `## Config quirks` section with all 4 items. References list adds
   handoff pointer.
2. **`findings/jsm_sdl3_live_verification.md`** — new Phase 2d section
   (lines 144-201, between Phase 3 branch match and References). 17-button
   results table with all 4 paddles mapped to LMINI/RMINI/LSL/RSR + test
   keys. Single-line gyro "unchanged from Phase 2c" note. Pad-side-gotcha
   subsection on the firmware-macro interception + clear-in-Ultimate-Software
   resolution. Reference-log paragraph honest about `run2.txt` contents (it
   captures a mid-session run with firmware override exposed, not the final
   21/21 pass — that was user-interactive without log capture).
3. **`tools/jsm_sdl3_config.txt`** — header dual-dated (Branch B 2026-04-20,
   Branch A 2026-04-22). "Requires JSM built from master" line now points
   to `branch-a-port` (11 cherry-picks + 3 local patches). The old
   "Unreachable via this path" paddle block is replaced with active (uncommented)
   `LMINI =`, `RMINI =`, `LSL =`, `RSR =` bindings (blank values for user),
   each with inline physical-input comments. CAPTURE noted as absent on the
   pad. Gyro section untouched.
4. **`BACKLOG.md`** — old Open fork-evaluation item removed. New Done entry
   for the Branch A port (2026-04-22) placed above the amended 2026-04-20
   Branch B entry. Branch B entry now carries "(2026-04-20, promoted to
   Branch A 2026-04-22)" and a "**Superseded 2026-04-22**" sentence. Other
   Open and Done items untouched.

Original Step 7 spec (for reference / audit):

1. **`findings/jsm_sdl3_verified.md`** — current state: Branch B adoption doc. Promote:
   - `**Match:** Branch B (...)` → `**Match:** Branch A (21/21 inputs, gyro unchanged)`
   - Button coverage: 17/21 → 21/21 (17 standard + 4 extended paddles). List L4/R4/PL/PR as working with exact SDL→JSOFFSET→ButtonID routing
   - Remove the "Branch A lookahead" section at the bottom; replace with "Branch A achieved (2026-04-22)" section listing the 11 ported fork commits (original fork SHA + author + our local SHA) and the 3 JangMan commits (merge-artifact fix, `_guid` restore, local patches re-apply)
   - Mention the 3 empty no-op cherry-picks and the "structurally present, untested" status of the other ported controllers (Flydigi, GameSir G7, HORI Steam, Switch 2 Pro, Switch Pro mapping fix, SF30/SN30/Pro variants)
   - Add the config quirks subsection (MINUS/PLUS = `-`/`+`, MOUSE_X/Y = `Y`/`X`, HOME ratchet pattern)

2. **`findings/jsm_sdl3_live_verification.md`** — append a new section `## Phase 2d — Branch A re-verification (2026-04-22)` with the 17-button results table and a one-line "Gyro: unchanged from Phase 2c (feel, scale, rate)". Reference `reference/JSM_JangManJ/run2.txt` for the raw output.

3. **`tools/jsm_sdl3_config.txt`** — uncomment and correct paddle bindings:
   - Replace the `# PADDLE1/2/3/4 =` comment block + "Unreachable via this path" disclaimer with live bindings using the correct keywords: `LMINI =`, `RMINI =`, `LSL =`, `RSR =` (leave values blank for user to fill with their preferred keys)
   - Remove the "Branch A upgrade candidate: evan1mclean/JSM_custom_curve..." note — supersed­ed
   - Update the header comment: "Adopted: 2026-04-20 (Branch B), promoted to Branch A 2026-04-22"

4. **`BACKLOG.md`** —
   - Open item "Evaluate evan1mclean/JSM_custom_curve v2.1.0-jsm-gui as a Branch A upgrade" (lines 68-85): move to Done, mark `[x]`, note outcome: "Minimal 11-commit port applied to JSM tree at branch-a-port, NOT wholesale fork adoption. See findings/jsm_sdl3_verified.md and this handoff."
   - Done item "Verify JSM-from-master + SDL3 default backend" (lines 89-97): update outcome from "Branch B" to "Branch A (21/21 via custom_curve fork port, 2026-04-22)"

**Style guidance (per `CLAUDE.md`):** findings are factual, not narrative. One claim per section, with evidence (SHAs, file:line refs). Dates absolute. Handoffs self-contained.

### Step 8 — Upstream PR prep (PAUSED per user 2026-04-22)

User paused before this work starts. Target: `handoffs/jsm_upstream_pr_prep.md`
— a staged 3-PR proposal for `Electronicks/JoyShockMapper`. See plan file
Step 8 for the detailed template. Key point: re-derive commits from the fork
in DAG order (not from our branch) to preserve per-commit compile-ability +
authorship.

### Step 6 — Timer QoL (DONE 2026-04-23)

4 commits from ceski landed during a session that ended in a blue screen;
verified correct and live-tested 2026-04-23. Branch is now 18 commits ahead
of `master`. Commits (all touch `SDLWrapper.cpp` only):
- `5d805e9` — Raise process/thread priority
- `57bf168` — Honor timer resolution on Windows 11 (disable EcoQoS)
- `45b776e` — Set max timer resolution via `ZwSetTimerResolution` (ntdll)
- `ce16c58` — Replace fixed delay with sleep + busy-wait polling timer

## Key reference files

**In the JangsJyro workspace:**
- `findings/jsm_sdl3_verified.md` — Branch B adoption doc (to be promoted in Step 7)
- `findings/jsm_sdl3_live_verification.md` — Phase 2 verification (to be appended in Step 7)
- `findings/jsm_sdl3_source_verification.md` — Phase 1 static source verification (unchanged)
- `findings/jsm_wrapper_substrate.md` — prior substrate research (unchanged)
- `tools/jsm_sdl3_config.txt` — config scaffold (to be updated in Step 7)
- `tools/jsm_bridge.py` — deprecated bridge (unchanged)
- `BACKLOG.md` — has open fork-eval item to close + Done item to amend (Step 7)
- `reference/JSM_JangManJ/run2.txt` — final paddle-firing log (captures the 21/21 verification)
- `reference/first_run.txt` — initial run log (pre-config-fixes)

**In the JSM tree (%USERPROFILE%\Claude\JangsJyro-JSM\):**
- `JoyShockMapper/src/SDLWrapper.cpp` — vendor detection (`82-158`), GetButtons + per-type paddle switch (`532-662`), Ultimate 2 case (`620-626`)
- `JoyShockMapper/include/JslWrapper.h` — `JS_VENDOR_*` / `JS_PRODUCT_*` / `JS_TYPE_*` (`81-115`), `JSOFFSET_*` (`167-203`)
- `JoyShockMapper/include/JoyShockMapper.h` — `ButtonID` enum (LMINI/RMINI/LTOUCH/RTOUCH/MISC1-6 at `63-72`)
- `JoyShockMapper/src/operators.cpp:41-50` — `<<` / `>>` for ButtonID (MINUS ↔ `-`, PLUS ↔ `+`)
- `JoyShockMapper/src/Mapping.cpp:111,115` — `: true` / `: false` debug output on button state change
- `JoyShockMapper/src/ButtonHelp.cpp:5-64` — `buttonHelpMap` with new button help text
- `JoyShockMapper/CMakeLists.txt:178` — SDL3 tag pinned `release-3.4.4` (local patch)
- `.custom_curve_diff.txt` (not committed) — full fork divergence list, 266 commits
