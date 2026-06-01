# Tools — Linux HID/SDL diagnostics

Three Python scripts for poking at the 8BitDo Ultimate 2's input plumbing. Each was originally written during Windows-side investigations but is platform-portable and useful for the current Linux-side input-latency work.

Run from the lab root (`Gamepad-Lab/`).

| Script | Purpose | Linux deps |
|--------|---------|------------|
| `gyro_enum.py` | SDL device enumeration. Lists every joystick SDL sees, whether it's a GameController, and whether it exposes a gyro sensor. **Use first** — confirms whether SDL is even seeing the controller as a sensor-bearing device. | `pysdl2`, `pysdl2-dll` |
| `gyro_probe_hid.py` | Raw-HID byte-change probe. Three phases (idle / sticks / rotate); pinpoints which bytes in the input report carry gyro. Writes `hid_probe_report.txt`. **Use to confirm the hidraw path is reachable** and the 34-byte sensor-bearing report shape matches `findings/gyro_hid.md`. | `hidapi` |
| `gyro_meter.py` | Live IMU angular-velocity monitor — zone strip, virtual-cursor mockup, polling-rate auto-detect. Auto-selects SDL sensor path vs raw HID. Useful as a live-feedback tool when toggling kernel modules / udev rules. | `pysdl2`, `pysdl2-dll`, `hidapi` |
| `evdev_capture.py` | **The mapper-conversion-lab output observer.** `list` enumerates every readable `/dev/input/event*` with a capability tag (keyboard / mouse / gamepad) so you can spot a mapper's virtual output devices (`JoyShockMapper_KEYBOARD`/`_MOUSE`, Steam's `extest fake device`, …); `capture` `select()`s over chosen devices and logs KEY/REL/ABS events with timestamps (`--name`/`--exclude` filter by name, `--grab`/`--grab-name` EVIOCGRAB so synthetic output doesn't leak to the compositor, `--seconds`, `--jsonl`). Compositor-agnostic — the basis for observing mapper output on Wayland. | `python-evdev`, `input` group |
| `xi2_capture.py` | **The Steam-Input-lane observer** (X11/XInput2 counterpart to `evdev_capture.py`). `devices` lists XI2 devices with seat/XTEST flags; `capture` parses `xinput test-xi2 --root` (under `stdbuf -oL`) and logs key/button events with their **source device**, so the X11/XI2 plane is distinguishable from evdev. Needed because **Steam Input on Wayland emits at the compositor seat (XI2-observable), not at evdev** (`findings/steam_input_linux.md`). | `xorg-xinput`; `python-xlib` (optional, keysym names); an X/Xwayland display |

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
