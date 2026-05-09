# Gyro HID interface — 8BitDo Ultimate 2 Wireless + general notes

## SDL3 status on the Ultimate 2 Wireless (DInput) — updated 2026-04-20

As of JSM master @ SHA `bb69784488937e0a5e21988b966eccd9f04d504e` with SDL3 @
SHA `5848e584a1b606de26e3dbd1c7e4ecbc34f807a6` (release-3.4.4), SDL3's
`SDL_hidapi_8bitdo.c` driver **does** surface the pad's gyro via
`SDL_SENSOR_GYRO` in DInput mode, at full ±2000 dps scale and ~1000 Hz sample
rate. This supersedes the earlier caveat below that SDL did not plumb sensors
for this pad. The raw-HID path is still the reference for tools that need
direct HID access (e.g. `gyro_meter.py`) — the layout table, scale factors,
and axis mapping elsewhere in this document remain correct for anything that
reads HID directly.

See `findings/jsm_sdl3_verified.md`.

---

Pragmatic knowledge for reading gyro from game controllers on Windows.
Controller-specific details in the first sections, generalizable
gotchas at the bottom.

---

## Device identification

| Field | Value |
|-------|-------|
| Vendor | Shenzhen 8Bitdo Tech Co., Ltd. |
| VID | 0x2DC8 |
| PID | 0x6012 (controller) / 0x6013 (dongle alone) |
| HID usage page / usage | 0x01 / 0x05 (Generic Desktop / Gamepad) |
| USB | Declares 2.0, runs at Full-Speed (12 Mbit/s) |
| bInterval | 1 ms on both IN and OUT (1000 Hz bus polling) |
| Measured host-side polling | ~1006 Hz avg, 0.10 ms jitter (stdev) |

## Mode map (Ultimate 2 Wireless)

Hold a button during power-on to select:

- **NS / Switch mode — hold Y.** Pad emulates a Nintendo Switch Pro
  Controller: VID 0x057E, PID 0x2009, SDL GUID prefix `0300bb977e05…`.
  Gyro is readable via SDL's `SDL_GameControllerGetSensorData`
  (underlying driver: `HIDAPI_DriverSwitch` in SDL source).
- **DInput mode — hold B.** Native 8BitDo VID/PID. Gyro is embedded
  in the raw HID input report and is NOT surfaced by SDL's
  GameController sensor API. Read via Python `hidapi`.
- **PC / XInput mode — default.** No gyro at all. XInput has no gyro
  axis or sensor API.

## DInput HID report layout (v1.09 firmware)

- Report ID: 0x01
- Total length: 34 bytes (sensor-capable firmware ≥ v1.03)
- Pre-v1.03: 12 bytes, no sensor block. v1.03 was the cutoff that
  added sensors to DInput mode.

| Offset | Bytes | Field |
|--------|-------|-------|
| 0      | 1 | Report ID (0x01) |
| 1      | 1 | Header / status (~0x0F) |
| 2      | 1 | L-stick X |
| 3      | 1 | L-stick Y |
| 4      | 1 | R-stick X |
| 5      | 1 | R-stick Y |
| 6      | 1 | L-trigger |
| 7      | 1 | R-trigger |
| 8–13   | 6 | Button bitmap + misc |
| 14     | 1 | Frame header (~0x53) |
| 15–16  | 2 | sAccelX (int16 LE) |
| 17–18  | 2 | sAccelY (int16 LE) |
| 19–20  | 2 | sAccelZ (int16 LE) |
| 21–22  | 2 | sGyroX  (int16 LE) |
| 23–24  | 2 | sGyroY  (int16 LE) |
| 25–26  | 2 | sGyroZ  (int16 LE) |
| 27–33  | 7 | Padding / reserved |

## Actual sensor delivery rate

**~125 Hz** in both 2.4 GHz dongle and Bluetooth paths, despite the
1 ms bus poll interval. Likely the IMU chip is sampling at 125 Hz
internally, OR the dongle firmware coalesces to a BT-like cadence for
protocol symmetry.

Either way: the "1000 Hz gyro" marketing refers to chip spec, not
what reaches the host. Measure the fresh-sample rate from the
application side before trusting the bInterval number.

## Scale factors

```python
GYRO_SCALE  = 2000.0 / 32767.0   # int16 → °/s
ACCEL_SCALE =    1.0 /  4096.0   # int16 → g
```

## Axis mapping (matches SDL driver convention)

Raw HID fields are NOT pitch/yaw/roll directly. Apply:

```python
pitch = -sGyroY
yaw   = +sGyroZ
roll  = -sGyroX

accel_pitch = -sAccelY
accel_yaw   = +sAccelZ
accel_roll  = -sAccelX
```

Using this mapping keeps DInput raw-HID output identical to SDL's
Switch-mode sensor output, so downstream code doesn't have to know
which source is active.

## Integration paths (Windows)

| Method | Applicable when | Output | Notes |
|--------|-----------------|--------|-------|
| SDL `SDL_GameControllerGetSensorData` | SDL has a HIDAPI driver for this pad (DualSense, Switch Pro, Steam Deck, 8BitDo-as-Switch-Pro) | rad/s | No generic fallback; if the driver doesn't match, gyro is invisible. |
| Raw HID via `hidapi` Python binding | HID interface is accessible | int16 (scale + axis-map as above) | Works for 8BitDo in DInput mode. |
| XInput | Never for gyro | — | Axes only; gyro is not part of XInput protocol. |
| SDL `SDL_JoystickGetAxis` | Always, but only sees axes declared as Generic Desktop in HID descriptor | int16 | 8BitDo in DInput mode declares 6 standard axes (sticks + triggers) and NO gyro axes → SDL Joystick path sees no gyro. |

## Exclusive-access gotchas

- **8BitDo Ultimate Software** (tray app) claims the HID interface
  exclusively while running. `hid.enumerate()` returns empty as long
  as it's alive. Right-click tray → **Exit** (not minimize) to release.
- **Steam Input** hides controllers from SDL while running and
  re-exposes them via Steam's own SDL shim for games it owns.
  Non-Steam apps need to be added as a Non-Steam Shortcut to receive
  Steam Input's forwarded gyro. Otherwise: quit Steam.

## Python `hidapi` vs `hid` packaging footgun

Two PyPI packages both provide a module named `hid`:

- `pip install hidapi` — compiled Cython binding with `hidapi.dll`
  bundled. **Preferred on Windows.**
- `pip install hid` — pure-Python ctypes wrapper. Does NOT bundle the
  DLL. Fails at import time with "DLL load failed" unless libhidapi
  is installed system-wide.

If BOTH are installed, one shadows the other and import behavior is
confused. Fix:

```
pip uninstall -y hid
# keep 'hidapi'
```

API also differs slightly; defensive code should feature-detect:

```python
if hasattr(hid, "Device"):
    # pure-Python 'hid' package
    dev = hid.Device(path=p); data = dev.read(64, timeout=50)
else:
    # Cython 'hidapi' package
    dev = hid.device(); dev.open_path(p); data = dev.read(64, timeout_ms=50)
```

## Generic gyro-controller gotchas

- **SDL gyro support requires a dedicated HIDAPI driver per device.**
  A "generic HID gamepad" entry in SDL's mapping database is NOT
  enough — the driver itself is the sensor layer. Without it,
  `SDL_GameControllerHasSensor()` returns false.
- **HID descriptors declare gyro under varied usage codes.** Typical
  options: extra Generic Desktop axes (rX/rY/rZ, slider, dial),
  Motion usage page 0x05, or vendor-defined pages. SDL's Joystick
  path only picks up Generic Desktop. Motion-page gyro is invisible
  to SDL without a product-specific driver.
- **Advertised polling rate on 2.4 GHz / BT paths is often aspirational.**
  Dongle firmware frequently coalesces samples; measure the
  fresh-sample rate from the application side before trusting the
  spec number.
- **Some 8BitDo pads need a feature report to enable sensors.**
  SF30 Pro, SN30 Pro, Pro 2, Pro 3 use a `0x06` feature report; SDL
  handles this per-product in `SDL_hidapi_8bitdo.c`. The Ultimate 2
  Wireless does NOT — sensors flow automatically on compatible
  firmware.
- **If SDL can't see gyro, the fastest diagnostic is a raw HID byte-
  change probe.** Record HID bytes across three phases (idle, sticks-
  only, rotate-only) and flag bytes whose motion spikes during
  rotate-only. Gyro candidates appear as pairs of adjacent bytes
  (int16 pairs) with high delta-sum during rotate.
