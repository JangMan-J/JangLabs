# JangMan's Steam Input / gyro workspace

Personal workspace for investigations and tooling around Steam Input,
gyro controllers, and controller-to-game input pipelines.

Primary focus: tuning Steam Input layouts (Arc Raiders on an 8BitDo
Ultimate 2 Wireless), diagnosing gyro pipeline artifacts (wiggle,
echo, drift, stepping), and reading controller IMU data across
controller modes (NS / DInput / raw HID).

## Layout

| Path | Contents |
|------|----------|
| `CLAUDE.md` | Project conventions for Claude sessions |
| `BACKLOG.md` | Running list of things to investigate |
| `FINDINGS/` | Durable knowledge learned across sessions |
| `HANDOFFS/` | Paused-investigation context seeds |
| `tools/` | Python tools built in this workspace |
| `reference/` | User-submitted raw data (USB dumps, logs, etc.) |
| `.claude/` | Claude Code settings and permissions for this project |

## Tools

All Python, in `tools/`. Run from the project root unless noted.

- **`gyro_meter.py`** — live IMU angular-velocity monitor with zone
  strip, virtual-cursor mockup, and polling-rate detector. Auto-
  selects between SDL sensor path (controller in NS mode) and raw
  HID (controller in DInput mode).
  Requires: `pysdl2`, `pysdl2-dll`, and `hidapi` for the DInput path.
- **`mouse_meter.py`** — live raw-mouse-delta monitor for the output
  side of the Steam Input gyro pipeline. Shows implied °/s by back-
  solving through DP360 × sens. Windows only.
- **`gyro_enum.py`** — SDL device enumeration diagnostic. Shows every
  joystick SDL sees, whether it is a GameController, and whether it
  exposes a gyro sensor.
- **`gyro_probe_dinput.py`** — SDL-joystick-axis byte-change probe
  for detecting whether any HID axes respond to rotation (used when
  SDL's sensor path is unavailable). Writes `probe_report.txt` on
  exit.
- **`gyro_probe_hid.py`** — raw-HID byte-change probe, three-phase
  (idle / sticks / rotate) for pinpointing gyro bytes inside the HID
  input report. Writes `hid_probe_report.txt`. Requires `hidapi`.
- **`vdf_clean.py`** — Steam Input VDF cleaner. Strips orphan groups,
  renumbers stale layer refs, optional deep-clean of cosmetic junk
  (empty `name`/`description`, empty `disabled_activators`, non-
  English localization).
- **`inventory_input_test.py`** — pygame click-latency tool for
  investigating gyro-freeze race conditions during inventory drags.
  Measures `first_move_ms` post-click to distinguish race losses
  from filter bleed (Ouija Effect).

## Starting points for a new session

1. Read `BACKLOG.md` for open items.
2. Read the relevant `FINDINGS/*.md` before probing or reverse-
   engineering in those domains — they contain non-obvious facts
   learned across sessions that Claude won't have from training.
3. Check `HANDOFFS/` if resuming a paused investigation. Each handoff
   is self-contained: a fresh Claude session can pick it up cold by
   reading only that file.
