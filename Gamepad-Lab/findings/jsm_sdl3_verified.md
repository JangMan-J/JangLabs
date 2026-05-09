# JSM + SDL3 direct DInput — verified and adopted

**Date:** 2026-04-20 (Branch B adoption); 2026-04-22 (Branch A promotion)
**Supersedes open questions in:** `findings/jsm_wrapper_substrate.md` (2026-04-19)
**JSM SHA:** `bb69784488937e0a5e21988b966eccd9f04d504e`
**SDL3 SHA:** `5848e584a1b606de26e3dbd1c7e4ecbc34f807a6` (release-3.4.4)
**Match:** Branch A (21/21 physical inputs — 17 standard + 4 extended, gyro unchanged from Branch B)

## Verified characteristics

- **Button coverage:** 21 of 21 physical inputs reachable via JSM bindings (17 standard + 4 extended).
  - Standard 17 (D-pad × 4, face × 4, L/R, ZL/ZR, L3/R3, HOME, `-`, `+`): same keywords as Branch B. `-`/`+` bound via literal characters, not `MINUS`/`PLUS` — see Config quirks below.
  - Extended 4 (L4 / R4 / PL / PR): reachable as `LMINI` / `RMINI` / `LSL` / `RSR` ButtonIDs via the
    Ultimate 2 type case at `SDLWrapper.cpp:620-626`. Paddle-slot SDL events
    `SDL_GAMEPAD_BUTTON_LEFT_PADDLE1/2` + `RIGHT_PADDLE1/2` map through `JSOFFSET_*`
    to these ButtonIDs.
  - CAPTURE: pad has no physical capture button on the Ultimate 2 Wireless — not a
    coverage regression.
- **Gyro:** unchanged from Branch B. Present via `SDL_SENSOR_GYRO`, standard
  directionality (no sign flip). `MOUSE_X_FROM_GYRO_AXIS = Y` and
  `MOUSE_Y_FROM_GYRO_AXIS = X` (JSM defaults) produce natural aim-style cursor travel.
- **Gyro scale:** full ±2000 dps, no clipping, no correction factor needed.
  Peak of ~730 °/s observed in testcontroller during fast rotation.
- **Sample rate:** ~1000 Hz at SDL3 layer (8× the ~114–127 Hz raw-HID baseline
  measured via `gyro_meter.py`). JSM polls via `SDL_UpdateGamepads` without
  added rate-limiting (`SDLWrapper.cpp:260`); qualitative feel matches the
  SDL3-layer rate.

## Local JSM tree state for this build

JSM tree at `%USERPROFILE%\Claude\JangsJyro-JSM\`, branch `branch-a-port`,
18 commits ahead of `master` (`bb69784`). Composed of 11 cherry-picks from
`evan1mclean/JSM_custom_curve` (preserving original Ceski / evan.mclean authorship)
+ 3 local JangMan fix commits. See the Branch A achieved section below for the
full commit manifest.

### Local patches (Branch B baseline, still required)

Both carried forward into the Branch A tree via the `09b84db` "local patches
re-apply" commit:

1. `JoyShockMapper/CMakeLists.txt` — SDL3 `GIT_TAG` `release-3.2.x` → `release-3.4.4`.
   Required because `SDL_hidapi_8bitdo.c` does not exist in 3.2.x.
2. `JoyShockMapper/src/SDLWrapper.cpp:408` — `GetTouchState` guarded on
   `SDL_GetNumGamepadTouchpads == 0` to prevent per-frame `CERR` flood on pads
   without a touchpad surface.

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

## Branch A achieved (2026-04-22)

21/21 coverage reached by cherry-picking 11 commits from `evan1mclean/JSM_custom_curve`
(v2.1.0-jsm-gui fork) onto the JSM tree at `branch-a-port`, plus 3 local JangMan fix
commits. Not a wholesale fork adoption.

| Local SHA | Author | Fork SHA | Subject |
|-----------|--------|----------|---------|
| `437476f` | ceski | `f88664f` | Update button flags to 64-bit (prereq) |
| `44091ec` | ceski | `dfb5f17` | Add JS_TYPE_UNKNOWN |
| `2c07c5e` | ceski | `b0160a6` | Add device bus definitions |
| `8628395` | ceski | `7fa8fb0` | Clean up existing VID/PID values |
| `439dc1e` | ceski | `78d7848` | Add capacitive touch, mini shoulder, misc buttons |
| `41ba070` | ceski | `a68cbff` | Update default mapping for unknown controllers |
| `c501407` | evan.mclean | `fc51c0d` | Fix missing break in vendor switch + uint64 expand |
| `b368fa5` | ceski | `a4c7e63` | All 8BitDo controllers (Ultimate 2 + SF30/SN30/Pro/Pro2/Pro3) |
| `6b7f923` | ceski | `66557f6` | Flydigi (Apex 5, Vader 3/4/5 Pro) |
| `dc07961` | ceski | `b8579b4` | Fix Switch pro controller mapping |
| `afbea5f` | ceski | `3d36aa7` | Switch 2 Pro controller (USB only) |

Local JangMan commits on top:

- `09b84db` — Local patches re-apply (SDL3 pin `release-3.4.4`, touchpad guard)
- `4d8927e` — Fix merge artifacts in vendor switch (duplicate `case JS_VENDOR_NINTENDO`
  + missing `break` after `JS_VENDOR_GAMESIR`)
- `3979fed` — Restore missing `SDL_GUID _guid;` member in `ControllerDevice`

### Fork commits that became empty no-ops

- `3ed4c09` (Fix paddles for default controllers) — content absorbed into `f88664f` ripple
- `97c1a0b` (GameSir G7 Pro 8K) — content absorbed into `fc51c0d` resolution
- `704aa81` (HORI Steam Controller) — content absorbed into `fc51c0d` resolution

### Verified scope

- Ultimate 2 Wireless 21/21 + gyro live-verified 2026-04-22 (see
  `findings/jsm_sdl3_live_verification.md` Phase 2d).
- Other ported controllers (Flydigi Apex 5 / Vader 3/4/5 Pro, GameSir G7 Pro 8K,
  HORI Steam Controller, Switch 2 Pro, Switch Pro mapping fix, 8BitDo
  SF30/SN30/Pro/Pro2/Pro3): **structurally present, untested** — code paths
  exist but no hardware on hand.

### Git-bisect hazard

Intermediate commits on `branch-a-port` won't compile in isolation — resolving the
`fc51c0d` equivalent (`c501407`) pulled in symbols that later commits add. Tip
compiles cleanly. For upstream PR prep, re-derive from the fork directly in DAG
order, not from our branch.

## Config quirks

Non-obvious syntax the JSM 3.6.1 parser expects — not documented in the JSM README
in a discoverable way:

- **MINUS / PLUS** are registered as `-` and `+` keywords, not as the literal strings
  `MINUS` / `PLUS`. See `JoyShockMapper/src/operators.cpp:41-50` — the `<<` / `>>`
  overloads for `ButtonID` map `ButtonID::MINUS ↔ "-"` and `ButtonID::PLUS ↔ "+"`.
  Using `MINUS = G` in a config file produces `Unrecognized command`.
- **MOUSE_X_FROM_GYRO_AXIS / MOUSE_Y_FROM_GYRO_AXIS** take axis-coordinate keywords
  `X` / `Y` (or compound forms `WORLD_X` / `PLAYER_Y` etc.), not `YAW` / `PITCH`.
  `MOUSE_X_FROM_GYRO_AXIS = YAW` produces `Error assigning YAW to MOUSE_X_FROM_GYRO_AXIS`.
- **Gyro ratchet pattern**: `HOME = ^GYRO_OFF` makes gyro always-on with HOME as the
  momentary-disable modifier. `GYRO_ON = Tap` is also accepted but less predictable.
- **PowerShell invocation**: needs the `&` call operator before a quoted path to the
  exe (`& "...\JoyShockMapper.exe" "...config.txt"`). `cmd.exe` works without it.

## References

- `findings/jsm_sdl3_source_verification.md` (Phase 1)
- `findings/jsm_sdl3_live_verification.md` (Phase 2)
- `docs/superpowers/specs/2026-04-20-jsm-sdl3-viability-design.md`
- `handoffs/jsm_branch_a_port_state.md` (this-session state + Step 7+ plan)
