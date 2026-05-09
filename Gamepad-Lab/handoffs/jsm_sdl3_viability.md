# JSM + SDL3 viability — in-progress handoff

## TL;DR

Executing `docs/superpowers/plans/2026-04-20-jsm-sdl3-viability.md`. Phase 1
(source verification) is **done**, verdict **YELLOW** with 3 watch items.
Phase 2 Task 6 (toolchain install) and Task 7 (clone + build JSM) are **done**.
Next up: **Task 8** (clone SDL3 at pinned SHA and build `testcontroller.exe`
for the isolation probe).

## Current status by task

| Phase | Task | Status |
|-------|------|--------|
| 1 | 1–5 static source verification | done — `findings/jsm_sdl3_source_verification.md` (YELLOW) |
| 2 | 6 toolchain install | done |
| 2 | 7 clone + build JSM | done, binary verified |
| 2 | 8 side-build SDL3 testcontroller | **next** |
| 2 | 9 prep environment (exit tray app + Steam, DInput mode, `gyro_meter.py` baseline) | pending |
| 2 | 10 SDL3 isolation probe via testcontroller | pending |
| 2 | 11 Gate 2b decision | pending |
| 2 | 12 JSM live probes | pending |
| 2 | 13 Phase 2 finding | pending |
| 3 | 14–16 branch selection + artifacts | pending |

## Pinned SHAs (from Phase 1)

- **JSM master:** `bb69784488937e0a5e21988b966eccd9f04d504e`
- **SDL3 ref:** `release-3.4.4` (**amended** from the plan's implicit `release-3.2.x` — the
  `SDL_hidapi_8bitdo.c` driver only exists on 3.4.x+; amendment documented in
  `findings/jsm_sdl3_source_verification.md` header)
- **SDL3 SHA:** `5848e584a1b606de26e3dbd1c7e4ecbc34f807a6`

## Toolchain installed

- **CMake:** 4.3.1 at `C:\Program Files\CMake\bin\cmake.exe` (not on PATH in
  plain bash — export `PATH="/c/Program Files/CMake/bin:$PATH"` per shell)
- **VS 2022 BuildTools:** 17.14.30 with MSVC v14.44.35207 at
  `C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\`
- **Git:** 2.54.0 (pre-existing)
- **Windows 11 SDK:** 22621 component (per winget install spec)

## Build output (Task 7)

- `%USERPROFILE%\Claude\JangsJyro-JSM\build\JoyShockMapper\Release\JoyShockMapper.exe` — 1011712 bytes
- `%USERPROFILE%\Claude\JangsJyro-JSM\build\JoyShockMapper\Release\SDL3.dll` — 2701824 bytes
- dumpbin confirms `SDL3.dll` as first dependent of the exe
- SDL3 joystick drivers enabled: dinput, gameinput, hidapi, rawinput, virtual, wgi, xinput

## Plan deviations / things the next session should know

1. **`-DSDL=ON` is required on Windows.** Plan Step 7.3 runs
   `cmake .. -G "Visual Studio 17 2022" -A x64` with no flags. That fails:
   JSM's `JoyShockMapper/CMakeLists.txt:60` uses `if(SDL)` on the Windows
   branch (not `if(SDL OR NOT DEFINED SDL)` like the Linux branch), so an
   undefined `SDL` variable falls through to the JSL path and the configure
   errors out with "No target 'JoyShockLibrary'". Fix: reconfigure with
   `-DSDL=ON`. This worked, produced the full build.

2. **SDL3 pin patch location** — the amendment changes only one line in
   `%USERPROFILE%\Claude\JangsJyro-JSM\JoyShockMapper\CMakeLists.txt:178`:
   `GIT_TAG release-3.2.x` → `GIT_TAG release-3.4.4`. Already applied in the
   current build. If you wipe the JSM clone, re-apply before reconfiguring.

3. **Build warnings are noise.** The build emits warnings about unicode
   conversions in `main.cpp:2766` and deprecation warnings from CPM's
   `FetchContent_Populate` calls (magic_enum, pocket_fsm, GamepadMotionHelpers
   have old `cmake_minimum_required` versions). None are blocking.

4. **Phase 1 watch items still pending verification** (from the source
   verification finding):
   - W1: actual SDL3 sample rate + timestamp correctness → Task 10.6
   - W2: gyro axis polarity (yaw right = mouse right; pitch down = mouse up) → Task 12.6
   - W3: which `SDL_GAMEPAD_BUTTON_*` constant each of L4/R4/PL/PR maps to
     (may be MISC, not PADDLE; JSM only polls PADDLE in most type branches) → Task 10.3

## How to resume

The plan is linear. Read `docs/superpowers/plans/2026-04-20-jsm-sdl3-viability.md`
from **Task 8** onward. Key inputs Task 8 needs:
- SDL3 pin from above (SHA `5848e584...`)
- Target clone path: `%USERPROFILE%\Claude\SDL\` (must not exist — confirm first)
- Target binary: `%USERPROFILE%\Claude\SDL\build\test\Release\testcontroller.exe`
- Configure flags: `-G "Visual Studio 17 2022" -A x64 -DSDL_TESTS=ON`
- Build only the testcontroller target: `cmake --build . --config Release --parallel --target testcontroller`

Before Tasks 9–12 (live tests), remind the user to:
- Right-click 8BitDo Ultimate Software tray icon → **Exit** (not minimize)
- Right-click Steam tray icon → **Exit** (fully, not close window)
- Power pad off, hold **B** while pressing power → DInput LED confirmed

## References

- Plan: `docs/superpowers/plans/2026-04-20-jsm-sdl3-viability.md`
- Spec: `docs/superpowers/specs/2026-04-20-jsm-sdl3-viability-design.md`
- Phase 1 finding: `findings/jsm_sdl3_source_verification.md`
- Prior substrate research: `findings/jsm_wrapper_substrate.md`
- Raw-HID reference: `findings/gyro_hid.md`
- Superseded plan: `docs/superpowers/plans/2026-04-19-jsm-master-sdl3-build.md` (toolchain troubleshooting)
