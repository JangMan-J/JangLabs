# Gamepad-Lab

Gamepad input investigations on the 8BitDo Ultimate 2 Wireless.

## Current focus

**Linux-side input latency and gyro on a fresh Arch install.** See [`8bitdo-ultimate2-arch-linux-troubleshooting.md`](./8bitdo-ultimate2-arch-linux-troubleshooting.md) — root-cause analysis (kernel HID driver claiming the device before Steam can hidraw it), connection-mode capability matrix, and a step-by-step udev-rule fix.

This is the same Arch install documented in [`../ArchLinux-Lab/`](../ArchLinux-Lab/).

## Long-term direction

Preserved in [`vision/`](./vision/): a comprehensive design for an agent-first lab that compares **real Steam Input** vs **real JSM** behaviorally. The full design doc is 492 lines; [`vision/INDEX.md`](./vision/INDEX.md) surfaces the load-bearing concepts (mapper lanes, agent roles, validation policy, artifact contracts, phase gates) with line anchors so future plans can cite specific sections without re-reading the whole thing.

The vision is **preserved, not active.** Current effort is the Linux-side troubleshooting above.

## Layout

```
.
├── README.md                                          (this file)
├── CLAUDE.md                                          (agent conventions)
├── 8bitdo-ultimate2-arch-linux-troubleshooting.md     (current focus — living doc)
├── vision/                                            (preserved long-term direction)
│   ├── 2026-04-29-gamepad-mapper-conversion-lab-design.md
│   └── INDEX.md
├── vdf/                                               (preserved-active: VDF→JSM tooling + translation knowledge for reuse)
│   ├── README.md
│   ├── vdf_clean.py
│   ├── test_vdf_clean.py
│   ├── translation_audit.md
│   └── reference/   (source-of-truth tuned VDFs)
├── findings/                                          (durable knowledge)
│   └── gyro_hid.md
├── reference/                                         (raw user-supplied artifacts)
│   └── 8bitdo_dinput_usbTree.txt
└── tools/                                             (Linux HID/SDL diagnostics)
    ├── README.md
    ├── gyro_enum.py
    ├── gyro_meter.py
    └── gyro_probe_hid.py
```

## Hardware reference (durable)

- **Controller:** 8BitDo Ultimate 2 Wireless
- **VID / PID:** `0x2DC8 / 0x6012` (2.4 GHz dongle, D-Input mode)
- Other PIDs in use: `0x310B` (USB wired), `0x6013` (dongle alone). Bluetooth disables gyro and caps polling at 125 Hz.
- **D-Input activation:** hold **Home + B** on power-on (X-Input is the default and exposes neither gyro nor the extra buttons).
- **Firmware floor:** v1.03+ for the 34-byte sensor-bearing HID report (`findings/gyro_hid.md`).

## Surviving tools

Three Linux-friendly hardware diagnostics — see [`tools/README.md`](./tools/README.md). Useful for verifying the kernel-driver-conflict hypothesis from the troubleshooting doc (e.g. `gyro_enum.py` to confirm SDL sees the gyro sensor, `gyro_probe_hid.py` to confirm the hidraw path is reachable).
