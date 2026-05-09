# Tools — runnable scripts

Python scripts. Run from the lab root (`Gamepad-Lab/`) unless a script's docstring says otherwise. This file supersedes the partly-stale tool list in `../docs/README.md`.

## VDF tooling (Steam Input config)

| Script | Purpose | Notes |
|--------|---------|-------|
| `vdf_clean.py` | Steam Input VDF cleaner. Strips orphan groups, renumbers stale layer refs, optional deep-clean of cosmetic junk. Now emits two outputs per run: conservative `clean.vdf` + aggressive `dedup.vdf`. | Stdlib only. CLI: `--out-aggressive`. |
| `test_vdf_clean.py` | Unittest harness for the cleaner. One TestCase per pass + integration test against the Jangman fixture. | Run with `python -m unittest tools.test_vdf_clean` from lab root. |

## Gyro / HID probes

| Script | Purpose | Notes |
|--------|---------|-------|
| `gyro_meter.py` | Live IMU angular-velocity monitor — zone strip, virtual-cursor mockup, polling-rate auto-detect. Auto-selects SDL sensor path (NS mode) vs raw HID (DInput mode). | Requires `pysdl2`, `pysdl2-dll`, `hidapi` (DInput path). |
| `gyro_enum.py` | SDL device enumeration. Lists every joystick SDL sees, whether it's a GameController, and whether it exposes a gyro sensor. | Requires `pysdl2`. |
| `gyro_probe_hid.py` | Raw-HID byte-change probe, three-phase (idle / sticks / rotate). Pinpoints gyro bytes in the input report. Writes `hid_probe_report.txt`. | Requires `hidapi`. |

## Input timing

| Script | Purpose | Notes |
|--------|---------|-------|
| `inventory_input_test.py` | Pygame click-latency tool. Measures `first_move_ms` post-click to distinguish gyro-freeze race losses from filter-bleed (Ouija Effect). | Requires `pygame`. Companion writeup: `inventory_input_test.md`. |
| `inventory_input_test.md` | Test methodology and result interpretation for `inventory_input_test.py`. | Not runnable. |

## Bridge / mapping logic

| Script | Purpose | Notes |
|--------|---------|-------|
| `controller_mapper.py` | Controller-input mapping / event translation. Large file — read its top docstring before assuming intent. | |
| `jsm_bridge.py` | Bridge between mappers; ViGEm-DS4 wrapper logic. The viability plan (`docs/superpowers/plans/2026-04-20-jsm-sdl3-viability.md`) evaluates whether to retire this in favor of pad → SDL3 → JSM direct. | Windows-side: depends on ViGEm. |

## Internal helpers

| File | Purpose |
|------|---------|
| `_inventory.py` | Internal utility (leading underscore — do not import as a public module). |

## Configs (not scripts)

| File | Purpose |
|------|---------|
| `jsm_sdl3_config.txt` | A JSM config file used during SDL3 substrate testing. Not Python. |

## Things this list does *not* include

The earlier `docs/README.md` references `mouse_meter.py` and `gyro_probe_dinput.py`. Neither exists in this directory; treat those references as historical.
