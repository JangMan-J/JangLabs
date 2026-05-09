# JSM + SDL3 source verification — 8BitDo Ultimate 2 Wireless (DInput)

**Date:** 2026-04-20
**JSM SHA:** `bb69784488937e0a5e21988b966eccd9f04d504e`
**SDL3 ref:** `release-3.4.4`
**SDL3 SHA:** `5848e584a1b606de26e3dbd1c7e4ecbc34f807a6`
**Read targets:**
- SDL3 `src/joystick/hidapi/SDL_hidapi_8bitdo.c`
- JSM `JoyShockMapper/src/SDLWrapper.cpp`

> **PLAN AMENDMENT — SDL3 pin changed to release-3.4.4:**
> JSM's `CMakeLists.txt` pins `GIT_TAG release-3.2.x`, which predates
> `SDL_hidapi_8bitdo.c`. That driver only exists on `release-3.4.x` and
> `main`. Phase 1 was re-run against SDL3 `release-3.4.4` (SHA
> `5848e584a1b606de26e3dbd1c7e4ecbc34f807a6`). **Task 7** will include a
> local patch of `JoyShockMapper/JoyShockMapper/CMakeLists.txt` replacing
> `GIT_TAG release-3.2.x` with `GIT_TAG release-3.4.4` before cmake
> configure.

---

## Summary

| # | Question | Verdict | Evidence (file:line) | Notes |
|---|----------|---------|----------------------|-------|
| 1 | VID/PID match `2DC8:6012` | **clear** | `SDL_hidapi_8bitdo.c:140,149`; `usb_ids.h` (VID `0x2dc8`, PID `0x6012`) | PID `0x6013` (standalone dongle) not listed separately; driver likely presents under `0x6012` regardless |
| 2 | 34-byte v1.03 report parsed, sensor block at offsets 15–26 | **clear** | `SDL_hidapi_8bitdo.c:168–183` (report size gate `>= 34`), line 464–468 (report ID `0x01` accepted), line 591 (`ABITDO_SENSORS *sensors = (ABITDO_SENSORS *)&data[15]`) | Packed struct fields at offsets 15–25 match `findings/gyro_hid.md` exactly; onboard tick read from offsets 27–30 (line 595) |
| 3 | Gyro → `SDL_SendJoystickSensor(SDL_SENSOR_GYRO, ...)` | **clear** | `SDL_hidapi_8bitdo.c:625–628` | All three axes routed with pitch/yaw/roll remapping; data origin traced to `sGyroX/Y/Z` packed fields |
| 4 | Scale preserved (full ±2000 dps → ±34.9 rad/s) | **clear** | `SDL_hidapi_8bitdo.c:52,286–287,321` — `DEG2RAD(2000) / INT16_MAX ≈ 1.0653e-3 rad/s per raw unit` | Algebraically exact match to `(2000 × π) / (180 × 32767)`; fixed constant, no per-device calibration |
| 5 | Button coverage count + extras mapping | **clear** | `SDL_hidapi_8bitdo.c:511–532` — 15 buttons dispatched (11 standard + `PL`, `PR` at lines 518–519; `L4`, `R4` at lines 531–532) | All 4 extras guarded by `size > 10` so only fire on 34-byte (v1.03+) reports; correct |
| 6 | Sample-rate pass-through (no throttle / coalesce) | **partial** | `SDL_hidapi_8bitdo.c:272–278` (nominal 1000 Hz for dongle), line 656 (non-blocking drain, no rate limiter); timestamp correction at lines 593–609 (per-packet delta if firmware exposes onboard tick) | Driver assumes 1 ms interval absent firmware tick — would run ~8× fast at empirical ~125 Hz. If firmware enables `SDL_8BITDO_SENSOR_TIMESTAMP_ENABLE` handshake (line 595), per-packet delta self-corrects. Needs empirical check |
| 7 | JSM calls `SDL_SetGamepadSensorEnabled(..., SDL_SENSOR_GYRO, true)` | **clear** | `SDLWrapper.cpp:65–74` (inside `ControllerDevice` constructor, guarded by `SDL_GamepadHasSensor`) | Fires on every pad connect; stable SDL3 API name confirmed present in 3.2 and 3.4.4 |
| 8 | JSM reads sensor data (poll or event) | **clear** | `SDLWrapper.cpp:385` (`SDL_GetGamepadSensorData`); polling thread at line 260 (`SDL_UpdateGamepads` each tick → callback → `GetIMUState`) | Polling, not event-based; no `SDL_EVENT_GAMEPAD_SENSOR_UPDATE` handling anywhere in wrapper |
| 9 | Gyro value reaches JSM's GYRO binding (sign/units correct) | **partial** | `SDLWrapper.cpp:378–400` — rad/s → deg/s via `180/π`; no sign flips applied; `main.cpp:~1925–1932` passes positionally to `ProcessMotion` | Unit conversion correct. Axis ordering/polarity not explicitly documented in JSM source and requires empirical rotation test to confirm pitch/yaw direction |
| 10 | JSM iterates button extras (paddles/MISC) | **partial** | `SDLWrapper.cpp:444–507` — Stage 1 maps 15 standard buttons; Stage 2 per-type switch: `JS_TYPE_PRO_CONTROLLER` case (lines 470–505) queries all four paddle slots (`LEFT_PADDLE1/2`, `RIGHT_PADDLE1/2`) | In Switch Pro mode, all four extras likely visible if SDL3 3.4.4 maps L4/R4/PL/PR to those constants. `default:` case (Xbox/others) misses `LEFT_PADDLE1/2`. 8BitDo DInput mode: no `JS_TYPE_8BITDO` — handled via emulated type |

---

## Overall verdict

**YELLOW** — proceed to Phase 2 with 3 watch items.

All core plumbing exists: VID/PID matched, report parsed, gyro routed to `SDL_SENSOR_GYRO` at correct scale, sensors enabled on connect, polling read confirmed. Three items need live empirical verification before adoption confidence is high:

1. **Q6 — Sample rate / timestamp behavior:** Driver synthesizes timestamps at 1 ms intervals when firmware does not expose the onboard tick, but actual HID delivery is ~125 Hz. Whether current dongle firmware enables the `SDL_8BITDO_SENSOR_TIMESTAMP_ENABLE` handshake (which would self-correct to ~8 ms intervals) is not determinable from source alone. Verify with `testcontroller` sample-rate measurement (Phase 2 Task 10.6).

2. **Q9 — Axis polarity:** JSM wrapper passes `gyro[0/1/2]` straight through (no sign flips). Whether SDL3's internal axis → physical orientation mapping aligns with JSM's `ProcessMotion` coordinate expectations needs one rotation test (yaw right should move mouse right; pitch down should move mouse up). Phase 2 Task 12.6.

3. **Q10 — Per-button SDL gamepad constant mapping:** 8BitDo driver dispatches extras at custom enum constants `SDL_GAMEPAD_BUTTON_8BITDO_L4/R4/PL/PR` (enum 11–14). These are four physically distinct buttons: L4/R4 are **back triggers** (below ZL/ZR), PL/PR are **paddle switches** (grip). SDL's gamepad mapping layer may route them to different standard constants — L4/R4 could map to `MISC` rather than `PADDLE` given they aren't paddles. JSM's wrapper only polls `LEFT_PADDLE1/2` / `RIGHT_PADDLE1/2` in its `JS_TYPE_PRO_CONTROLLER` branch, so any extras mapped to `MISC` would be invisible without a wrapper patch. Task 10.3 must record the specific `SDL_GAMEPAD_BUTTON_*` constant each of the four maps to, not just whether they appear. Also: JSM's `default:` controller-type branch omits `LEFT_PADDLE1/2`, so any path that doesn't land on `JS_TYPE_PRO_CONTROLLER` will miss two extras even among the paddle-mapped ones.

---

## Watch items for Phase 2

| # | Watch item | Phase 2 task | Pass condition |
|---|------------|--------------|----------------|
| W1 | Actual SDL3 sample rate + timestamp correctness | Task 10.6 | ≥60 Hz; timestamps advance at ~hardware cadence |
| W2 | Axis polarity (yaw/pitch direction) | Task 12.6 | Yaw right → mouse right; pitch down → mouse up |
| W3 | Per-button SDL gamepad constant mapping for all 4 extras | Task 10.3 | For each of L4, R4, PL, PR: record which SDL_GAMEPAD_BUTTON_* constant it maps to (PADDLE, MISC, or raw-only). L4/R4 are back triggers, not paddles — they may map to MISC rather than PADDLE. JSM only polls PADDLE constants in most type branches, so MISC-mapped extras would be invisible to JSM without a wrapper patch. |

---

## References

- `findings/gyro_hid.md` — 34-byte report layout, axis mapping, exclusive-access gotchas
- `findings/jsm_wrapper_substrate.md` — prior research identifying JSM+SDL3 as the recommended path
- `docs/superpowers/specs/2026-04-20-jsm-sdl3-viability-design.md` — spec this finding feeds into
- `docs/superpowers/plans/2026-04-20-jsm-sdl3-viability.md` — implementation plan (Phase 2 tasks referenced above)
