# Tools — Linux HID/SDL diagnostics

Three Python scripts for poking at the 8BitDo Ultimate 2's input plumbing. Each was originally written during Windows-side investigations but is platform-portable and useful for the current Linux-side input-latency work.

Run from the lab root (`Gamepad-Lab/`).

| Script | Purpose | Linux deps |
|--------|---------|------------|
| `gyro_enum.py` | SDL device enumeration. Lists every joystick SDL sees, whether it's a GameController, and whether it exposes a gyro sensor. **Use first** — confirms whether SDL is even seeing the controller as a sensor-bearing device. | `pysdl2`, `pysdl2-dll` |
| `gyro_probe_hid.py` | Raw-HID byte-change probe. Three phases (idle / sticks / rotate); pinpoints which bytes in the input report carry gyro. Writes `hid_probe_report.txt`. **Use to confirm the hidraw path is reachable** and the 34-byte sensor-bearing report shape matches `findings/gyro_hid.md`. | `hidapi` |
| `gyro_meter.py` | Live IMU angular-velocity monitor — zone strip, virtual-cursor mockup, polling-rate auto-detect. Auto-selects SDL sensor path vs raw HID. Useful as a live-feedback tool when toggling kernel modules / udev rules. | `pysdl2`, `pysdl2-dll`, `hidapi` |

## Linux-specific notes

- The kernel's `hid-generic` / `xpad` driver may claim the device before user-space code can open `/dev/hidraw*` — see `../8bitdo-ultimate2-arch-linux-troubleshooting.md`. If `gyro_probe_hid.py` returns "Permission denied" or no device, the udev rule from that doc is likely missing.
- Run as your normal user once udev grants `MODE="0666"` for the relevant VID/PID. `sudo` is not required.
- Wayland and X11 sessions both work for these scripts (none of them grab keyboard/mouse input).

## Install

The minimum for `gyro_probe_hid.py` alone:

```sh
pip install hidapi
```

For SDL-based scripts:

```sh
pip install pysdl2 pysdl2-dll
```

System SDL3 packages are not required — `pysdl2-dll` ships its own. Confirm SDL availability with `gyro_enum.py` before reaching for `gyro_meter.py`.
