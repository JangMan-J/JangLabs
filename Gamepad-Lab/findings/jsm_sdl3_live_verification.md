# JSM + SDL3 live verification — 8BitDo Ultimate 2 Wireless (DInput)

**Date:** 2026-04-20
**Host:** Windows 11 Pro 10.0.26200
**JSM SHA:** `bb69784488937e0a5e21988b966eccd9f04d504e`
**SDL3 SHA:** `5848e584a1b606de26e3dbd1c7e4ecbc34f807a6` (release-3.4.4)
**VS toolchain:** VS 2022 BuildTools 17.14.30, MSVC 14.44.35207
**Pad firmware:** v1.09
**Pad mode:** DInput (VID `2DC8` / PID `6012`)
**Transport:** 2.4 GHz dongle only (Bluetooth out of scope)

## Phase 2a — Build

- JSM binary: `%USERPROFILE%\Claude\JangsJyro-JSM\build\JoyShockMapper\Release\JoyShockMapper.exe`
- SDL3.dll: verified as dependency (adjacent to both `JoyShockMapper.exe` and `testcontroller.exe`)
- testcontroller: `%USERPROFILE%\Claude\SDL\build\test\Release\testcontroller.exe`
- Local JSM patches applied before Phase 2c:
  - `JoyShockMapper/CMakeLists.txt` — SDL3 `GIT_TAG` bumped `release-3.2.x` → `release-3.4.4` (required for `SDL_hidapi_8bitdo.c`, which does not exist in 3.2.x; noted in Phase 1 plan amendment)
  - `JoyShockMapper/src/SDLWrapper.cpp:408` — `GetTouchState` guarded on `SDL_GetNumGamepadTouchpads(sdlController) == 0` to prevent per-frame `CERR` flood ("Cannot get finger state: Parameter 'touchpad' is invalid") when the pad has no touchpad surface. Candidate upstream PR.
- Build warnings of note: none that affected functionality.

## Phase 2b — SDL3 isolation (testcontroller.exe)

| Check | Result |
|-------|--------|
| Pad detected by SDL3 | yes — 8BitDo Ultimate 2 Wireless, Xbox-layout identification |
| Gamepad layout populated | yes |
| Standard 13-button coverage | 13 of 13 |
| Paddle / MISC slots for extras | all 4 fire as `LEFT PADDLE 1/2` + `RIGHT PADDLE 1/2` (resolves Phase 1 watch item W3 favorably at SDL3 layer) |
| Gyro sensor active | yes — `SDL_SENSOR_GYRO` populated |
| Scale (360°/s-ish rotation) | peak observed **~729.94 °/s** (screenshot) — consistent with the driver's `DEG2RAD(2000)/INT16_MAX` constant, full ±2000 dps scale preserved, **no clipping** |
| Sample rate (SDL3 layer) | **~1000 Hz**, ~8× the raw-HID baseline (114–127 Hz measured via `gyro_meter.py` before build). Resolves Phase 1 watch item W1 very favorably: SDL3's `SDL_8BITDO_SENSOR_TIMESTAMP_ENABLE` handshake is apparently negotiated and per-packet ticks are respected by this firmware |

## Phase 2c — JSM live probes

### P1 — identification

JSM's console prints device count only (`1 device connected`), not per-device name strings.
SDL3-layer identification (from testcontroller, Phase 2b) is authoritative: Xbox-layout.

### P2 + P3 — button coverage

Per-input results via distinct mapped keys in `test_jsm.txt`, echoed to JSM console:

| Physical input | JSM keyword | Fires at JSM? |
|----------------|-------------|----------------|
| D-pad up       | `UP`        | yes |
| D-pad down     | `DOWN`      | yes |
| D-pad left     | `LEFT`      | yes |
| D-pad right    | `RIGHT`     | yes |
| Face N (Y/△)   | `N`         | yes |
| Face E (B/○)   | `E`         | yes |
| Face S (A/✕)   | `S`         | yes |
| Face W (X/□)   | `W`         | yes |
| Shoulder L     | `L`         | yes |
| Shoulder R     | `R`         | yes |
| Trigger ZL     | `ZL`        | yes |
| Trigger ZR     | `ZR`        | yes |
| L-stick click  | `L3`        | yes |
| R-stick click  | `R3`        | yes |
| Back / `-`     | `-`         | yes |
| Start / `+`    | `+`         | yes |
| Home / guide   | `HOME` (bound to `^GYRO_OFF`) | yes — toggles gyro state on every tap |
| L4 (rear)      | — (none tried — nothing fires) | **no** |
| R4 (rear)      | —                                 | **no** |
| PL (paddle L)  | —                                 | **no** |
| PR (paddle R)  | —                                 | **no** |
| CAPTURE        | —                                 | **no** |

**Totals:**
- Standard 13-button set: **13 / 13** reachable
- Extras (L4, R4, PL, PR, CAPTURE): **0 / 5** reachable at JSM layer (all 4 paddles visible at SDL3 layer — see Phase 2b)

**Root cause — paddles visible at SDL3 but invisible at JSM:** `SDLWrapper.cpp:472–508`.
JSM polls the 13 standard SDL gamepad buttons in a shared table (lines 452–466), but
additional-slot polling (`SDL_GAMEPAD_BUTTON_LEFT_PADDLE1/2`, `RIGHT_PADDLE1/2`,
`MISC1`) lives inside per-controller-type branches (`JS_TYPE_PRO_CONTROLLER`, etc.).
The Ultimate 2 is identified under the Xbox-layout type, which falls through the
default case and does not iterate paddle slots. This is a JSM bug, in-scope for a
local patch (similar to our touchpad guard) and an upstream PR. Left unpatched here
because it aligns with the existing ViGEm-DS4 bridge's capability (the DS4 report
format also has no slots for these 4 physical paddles), so it is **bridge parity**.

### P4 — gyro directionality

User-reported:

| Axis motion | Observed cursor | Natural for… |
|-------------|-----------------|--------------|
| Yaw right (pad rotates right) | mouse right | aim-style, matches Steam Input gyro-camera defaults |
| Yaw left | mouse left | " |
| Pitch nose up | mouse up | " |
| Pitch nose down | mouse down | " |

Default `MOUSE_X_FROM_GYRO_AXIS = Y` and `MOUSE_Y_FROM_GYRO_AXIS = X` (JSM defaults)
produce this mapping. No inversion, no axis swap needed. Note: this is non-inverted
aim-style, not FPS-flight-inverted; matches user's Steam Input preference.

### P5 — gyro scale

- `GYRO_SENS = 2` and `GYRO_SENS = 1` both produced "very reasonable" cursor travel.
- No clipping observed during normal and fast rotation.
- SDL3 peak measured at ~729.94 °/s in Phase 2b — full-scale `±2000 dps` headroom preserved through to JSM.
- No non-unit scale factor observed requiring compensation (rules out D-correctable / D-clipping).

### P6 — sample rate (JSM layer)

- No concrete counter captured (JSM has no built-in event-rate readout and the user was probing by feel).
- Qualitative user report: "Impressed with smoothness for the high polling and sensitivity."
- Given Phase 2b measured ~1000 Hz at the SDL3 layer and JSM's polling thread
  drains via `SDL_UpdateGamepads` without an added rate limiter
  (`SDLWrapper.cpp:260`), no JSM-layer decimation below ~125 Hz is expected. A
  precise JSM-layer event-rate count is not a blocker for the branch decision.

## Summary and Phase 3 input

- **Button coverage:** 13/13 standard, 0/4 paddles (bridge parity — the ViGEm-DS4
  bridge's DS4 format cannot surface these 4 physical paddles either; neither path
  can expose them to the user's Steam Input configurator without additional work
  outside the scope of the current question).
- **Gyro:** works at full ±2000 dps scale, natural directionality, no clipping,
  no sign flips needed.
- **Sample rate:** ~1000 Hz at SDL3 layer (8× raw-HID baseline). JSM pass-through
  appears clean; qualitative feel matches.

→ **Preliminary Phase 3 branch: B** — "Gyro full scale, ≥13 standard buttons,
L4/R4/PL/PR missing (bridge parity)" per the decision table in Task 14 row 9.

## Phase 3 branch match

Matched branch: **B** — decision table rule 9 ("Gyro full scale, ≥13 standard
buttons, L4/R4/PL/PR missing, bridge parity").

Rationale: gyro at full ±2000 dps scale with natural directionality and
~1000 Hz sample rate; all 13 standard SDL gamepad buttons reach JSM; the 4
physical paddles are visible at SDL3 (as `LEFT/RIGHT PADDLE 1/2`) but invisible
at JSM due to the type-gated paddle polling at `SDLWrapper.cpp:472–508` —
matching the existing ViGEm-DS4 bridge's capability (the DS4 report format
also has no slots for those 4 paddles), so direct JSM+SDL3 achieves bridge
parity with none of the Python/ViGEm overhead.

Route: Task 15 adoption.

## Phase 2d — Branch A re-verification (2026-04-22)

**Date:** 2026-04-22
**JSM build:** `%USERPROFILE%\Claude\JangsJyro-JSM\build\JoyShockMapper\Release\JoyShockMapper.exe` (~1.01 MB, built 2026-04-22 07:59)
**JSM branch:** `branch-a-port` (14 commits ahead of `master` @ `bb69784` — 11 fork cherry-picks + 3 local JangMan fixes; see `findings/jsm_sdl3_verified.md` §"Branch A achieved")
**SDL3:** release-3.4.4 (unchanged from Phase 2c)
**Pad firmware / mode / transport:** unchanged from Phase 2c
**Config:** `%USERPROFILE%\test_jsm.txt` (user's scratch config — not the workspace scaffold)
**Procedure:** pad in DInput mode (B+power), 8BitDo Ultimate Software exited, Steam exited, pad paddle macros **cleared** in Ultimate Software (see "Pad-side gotcha" below). Launched via PowerShell with the `&` call operator before the quoted exe path.

### Button coverage

| Physical input | JSM keyword / ButtonID | Test key | Fires at JSM? |
|----------------|------------------------|----------|----------------|
| D-pad up       | `UP`           | W | yes |
| D-pad down     | `DOWN`         | S | yes |
| D-pad left     | `LEFT`         | A | yes |
| D-pad right    | `RIGHT`        | D | yes |
| Face N (Y/△)   | `N`            | I | yes |
| Face S (A/✕)   | `S`            | K | yes |
| Face E (B/○)   | `E`            | L | yes |
| Face W (X/□)   | `W`            | J | yes |
| Shoulder L     | `L`            | Q | yes |
| Shoulder R     | `R`            | E | yes |
| Trigger ZL     | `ZL`           | Z | yes |
| Trigger ZR     | `ZR`           | C | yes |
| L-stick click  | `L3`           | U | yes |
| R-stick click  | `R3`           | O | yes |
| Back / `-`     | `-`            | G | yes |
| Start / `+`    | `+`            | F | yes |
| Home / guide   | `HOME` (→ `^GYRO_OFF`) | — | yes — toggles gyro state on every tap |
| L4 (rear mini) | `LMINI`        | 1 | yes |
| R4 (rear mini) | `RMINI`        | 2 | yes |
| PL (paddle L)  | `LSL`          | 3 | yes |
| PR (paddle R)  | `RSR`          | 4 | yes |
| CAPTURE        | (n/a)          | — | n/a — Ultimate 2 Wireless has no physical capture button |

**Totals:** 21 / 21 physical inputs present on the pad reachable at JSM layer (17 standard + 4 extended paddles). Coverage gain vs. Phase 2c: +4 extended paddles (L4, R4, PL, PR) via the Ultimate 2 type case at `SDLWrapper.cpp:620-626`, which maps `SDL_GAMEPAD_BUTTON_LEFT_PADDLE1/2` + `RIGHT_PADDLE1/2` + additional misc slots through `JSOFFSET_*` constants to `LMINI` / `RMINI` / `LSL` / `RSR` ButtonIDs (see `JoyShockMapper/include/JoyShockMapper.h:63-72` for ButtonID enum and `JoyShockMapper/include/JslWrapper.h:167-203` for JSOFFSET constants).

### Gyro

**Gyro: unchanged from Phase 2c** — feel, scale, directionality, and qualitative sample rate all match. No regression from the Branch A commits (expected: none of the 11 cherry-picks touch the sensor path).

### Pad-side gotcha

8BitDo Ultimate Software paddle-macro profiles override native paddle events at the firmware/driver level. When the pad has paddle macros assigned, L4/R4/PL/PR fire as standard-button chords (e.g. L4 → `ZL + W`, R4 → `-`, PL → `L3`, PR → `R3`) instead of native `SDL_GAMEPAD_BUTTON_LEFT_PADDLE1/2` + `RIGHT_PADDLE1/2` events. The Branch A code path requires native paddle events to hit the Ultimate 2 type case at `SDLWrapper.cpp:620-626`. Resolution: clear paddle macros in 8BitDo Ultimate Software (not in JSM config). After clearing, paddles emit native events and map correctly to `LMINI/RMINI/LSL/RSR`.

### Reference log

`reference/JSM_JangManJ/run2.txt` captures a mid-session run where the corrected config keywords (`- / + / Y / X` rather than `MINUS / PLUS / YAW / PITCH`) were confirmed working for the 13 standard buttons + `-`/`+`/HOME, and the paddle-firmware override was observed (L4 firing as `ZL + W`, R4 as `-`, PL as `L3`, PR as `R3`). The 21/21 final state (17 standard + 4 extended paddles) was verified interactively by the user after clearing the pad firmware macros (no log file captured for that final pass — the firmware-clear fix was the last variable). See also `reference/JSM_JangManJ/first_run.txt` for the earlier run that exposed the config-keyword errors.

### Config quirks discovered this session

Corrections applied to `%USERPROFILE%\test_jsm.txt` after `first_run.txt` exposed the errors (canonical list in `findings/jsm_sdl3_verified.md` §"Config quirks"):

- `MINUS` / `PLUS` → `-` / `+` (literal characters, not the words).
- `YAW` / `PITCH` → axis-coordinate keywords `Y` / `X`.
- Mapping `HOME = ^GYRO_OFF` = gyro always-on with HOME as momentary-disable.

## References

- `findings/jsm_sdl3_source_verification.md` — Phase 1 source verification
- `docs/superpowers/specs/2026-04-20-jsm-sdl3-viability-design.md` — spec (decision tree in Phase 3 section)
- `findings/gyro_hid.md` — axis mapping reference
