# Phase 0a — JSM runtime smoke (real pad → evdev) — RESULT: PASS

**Date:** 2026-06-01 · **Host:** CachyOS (Arch), Wayland + KDE, NVIDIA · **JSM:** `JangsJyro-JSM` @ `branch-a-port` HEAD `ae7accc`
**Device:** real 8BitDo Ultimate 2 Wireless, **D-Input mode** (`2dc8:6012`), evdev `event24` / `js1`.

Closes the runtime half of the Phase-0a gate left open by the build run
(`runs/20260531T135337Z-phase0-oracle-feasibility/`): *does real JSM emit an evdev-observable
event from a real controller input?* — **Yes.**

## What ran
`smoke.config`: `RESET_MAPPINGS` · `S = SPACE` · `ZR = LMOUSE` (keyboard/mouse output only — Linux
virtual-gamepad output is a stub, per the plan §5).

- JSM launched headless under `stdbuf -oL` (stdout is block-buffered when not a tty; the lone
  `fopen /dev/tty` stderr line is the console-input forwarder, which we detach — **FIFO is the
  command channel**). SDL detected the pad: `[AUTOCONNECT] Going from 0 devices to 1` / `1 device connected`.
- Mappings injected via the command FIFO **`/tmp/jsm_command_fifo`** (Linux JSM ignores `argv` —
  `main.cpp:2860`). JSM acked `S mapped to SPACE` / `ZR mapped to LMOUSE`.
- Capture: `tools/evdev_capture.py` watching the pad (`event24`, **read-only** so JSM keeps reading it)
  plus JSM's two output devices **`JoyShockMapper_KEYBOARD`** (`event26`) and **`JoyShockMapper_MOUSE`**
  (`event25`), **EVIOCGRAB on only the JSM outputs** (`--grab-name JoyShockMapper`) so the synthetic
  SPACE/clicks never reached the compositor.

## Result — exact count + order, sub-frame digital latency
689 events captured. Causal correlation, pad input → JSM output:

| Pad input (event24) | JSM output (evdev) | count | digital latency |
|---|---|---|---|
| `BTN_A` (South face btn) press/release | `JoyShockMapper_KEYBOARD` `KEY_SPACE` | 3 → 3 | **+1.1 / +3.1 / +1.3 ms** |
| `BTN_TR2` + `ABS_RZ`/`ABS_GAS` (right trigger) | `JoyShockMapper_MOUSE` `BTN_LEFT` | 4 → 4 | see note |

- **Negative control:** the stick-click presses (`BTN_THUMBL`, `BTN_THUMBR`) the tester also pressed
  produced **zero** JSM output — JSM emits only for the two *bound* controls. Strong evidence the chain
  is the mapping, not incidental passthrough.
- **Output mechanism confirmed at runtime (not just source):** keyboard/mouse output is real
  **libevdev/uinput** (`JoyShockMapper_*` evdev nodes), so it is **compositor-agnostic** — works on this
  Wayland session exactly as the source review (`InputHelpers.cpp`) predicted. Contrast the X11-only
  *window-detection* path that no-ops on Wayland (see `findings/jsm_linux_port.md`).
- **Clean shutdown:** JSM exited on SIGTERM with **no new coredump** (the only cores present are the
  2026-05-31 crashes already fixed in `15f8e64`/`ae7accc`).

## Behavioral finding (durable — matters for the converter)
JSM's **`ZR` fires off the analog trigger threshold** (`ABS_RZ`/`ABS_GAS` ramp), **not** the pad's own
digital `BTN_TR2` latch. On a fast full squeeze the analog threshold is crossed *before* the pad latches
`BTN_TR2`, so JSM's `BTN_LEFT` timestamp lands ~13–16 ms **earlier** than `BTN_TR2` (pairs #3/#4 below).
On slower pulls (#1/#2) they coincide (~1 ms). ⇒ trigger-as-button equivalence is governed by JSM's
threshold, and the right reference signal for trigger traces is the **analog axis**, not the controller's
internal digital button. (Steam Input exposes a configurable trigger "soft pull / full pull" point — a
direct comparison axis for a future trace.)

```
South(BTN_A) -> SPACE:        #1 +1.1ms   #2 +3.1ms   #3 +1.3ms
RightTrig(BTN_TR2) -> LMOUSE:  #1 +1.1ms   #2 +1.5ms   #3 -16.4ms  #4 -12.7ms   (negative = analog-threshold leads digital latch)
```

## Artifacts
- `smoke.config` — the two mappings.
- `capture-0a.jsonl` / `capture-0a.txt` — full evdev capture (pad input + JSM output, timestamped).
- `jsm.stdout.log` — JSM startup banner + FIFO acks.
- Tool: `tools/evdev_capture.py` (`list` / `capture --name … --grab-name … --jsonl …`).

## Phase 0 gate status
- **0a (JSM lane): PASS** — real JSM emits an evdev-observable event from a real controller input,
  on Wayland, ~1–3 ms digital latency.
- **0b (Steam Input lane): PENDING** — the concentrated crux (R1). Can Steam Input be driven by a
  controller and observed at evdev? Research workflow `steam-input-observability-r1` ran to scope the
  runtime test; real-runtime confirmation still required before the Phase-0 gate closes.

> Note on the smoke vs. a *synthetic* trace: this run used the real pad (tester pressed the buttons),
> which proves the JSM→evdev output chain end-to-end. Fully-synthetic *input* injection (uinput pad, or
> the `uhid` 8BitDo spoof for gyro per R2/Phase 6) is a separate capability not exercised here.
