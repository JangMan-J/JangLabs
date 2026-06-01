# Phase 0b — Steam Input observation plane (R1) — RESULT: ANSWERED

**Date:** 2026-06-01 · **Host:** CachyOS, Wayland + KWin, NVIDIA · **Steam:** Beta + **experimental
SteamRT3 (sniper)**, native pacman, client runs in **pressure-vessel** (`steamrt64` + `pv-run.sh`).
**Device:** real 8BitDo Ultimate 2 (D-Input `2dc8:6012`, `event24`), Steam Input ON, a face button
bound to keyboard **F9** in the Desktop layout.

## Question (crux R1)
Can Steam Input be driven by a controller and its **keyboard/mouse output observed at the kernel evdev
plane** (`/dev/input/event*`)? If not, the lab's "observe at evdev" thesis (plan §2.4) doesn't cover
the Steam lane.

## Answer
**No at evdev; yes at the X11/XI2 (Wayland-seat) plane.** Steam Input's F9 output never appears at evdev
(no uinput node, no `KEY_F9` on any node); it is observable via XI2 on the Xwayland seat. The *upstream
injector* (X11 XTEST vs libei/EIS) is **undetermined** — see the correction under Evidence.

## Evidence (dual-plane simultaneous capture; button pressed 11×)
| Plane | Observer | F9 |
|---|---|---|
| press proof | `evdev_capture.py` on `event24` | `BTN_B` ×11 press/release ✓ (press happened in-window) |
| **evdev** all nodes | `evdev_capture.py --types key` | **0 `KEY_F9`**; no new uinput node created (pre/post `list` diff clean) |
| **X11/XI2** | `xinput test-xi2 --root` | **11× KeyPress kc75 (F9)** + 11× release, 1:1 with presses |

F9 surfaced on XI2 **`id=9 xwayland-keyboard:10`** (the Xwayland seat); uinput would have made an evdev
node + `KEY_F9` — neither happened, so it is **not** evdev. **Correction (post-build self-test):** my
first read inferred "id=9 not id=5 ⇒ libei, not XTEST" — that is **wrong**. Verifying `tools/xi2_capture.py`
with `xdotool key F9` (*pure XTEST*) showed XTEST **also** lands on `id=9`, not on `id=5 "Virtual core
XTEST keyboard"`: on this EIS-enabled Xwayland, XTEST is rerouted to the seat, so the device-id cannot
separate XTEST from libei. **Mechanism = undetermined**; the robust result is the plane (XI2, not evdev).

## How the result was made trustworthy (dead-ends, for the record)
1. **Timing false-negatives (twice).** Blocking foreground captures missed presses that occurred
   between chat turns; `event24` was silent not because of a grab but because the button wasn't pressed
   *during* the window. Fix: **background observers spanning the turn** + independent press-proof.
2. **`pgrep steam` self-match** — a shell whose command contained "steam"/"steamwebhelper" matched
   itself → false "RUNNING". Fix: match by `comm`.
3. **extest delivery bitness.** First launched `LD_PRELOAD=/usr/lib32/libextest.so steam`; the env
   *did* propagate (remapped to `/run/host/usr/lib32/...`) but every Steam process is **64-bit**, so
   `ld.so: wrong ELF class: ELFCLASS32: ignored`. Then found via `/proc/*/maps` that the XTEST-linked
   UI proc is 64-bit — refuting the research's "steamui.so is 32-bit". (The 32-vs-64-bit detail doesn't
   change the verdict; extest's *relevance* stays undetermined — point 4.)
4. **extest: relevance UNDETERMINED (not "irrelevant").** It re-routes X11 `XTestFake*`→uinput; whether
   that would surface Steam's output at evdev depends on whether Steam uses XTEST (unproven — id can't
   tell). The Phase-0b preload was invalid anyway: 32-bit lib into a 64-bit client (`ELFCLASS32`,
   never loaded). Follow-up = preload the **64-bit** `/usr/lib/libextest.so`. extest was the user's own
   experiment, not Steam.
5. **`/proc` opacity** — pressure-vessel container + `dumpable=0` make Steam's `maps/environ/fd` flaky
   to read; sidestepped by querying the evdev/XI2 planes directly instead of introspecting Steam.

## Consequence for the lab
- The **two oracle lanes are observed on different planes**: **JSM = evdev** (real uinput devices —
  Phase 0a PASS), **Steam Input = XI2 / Wayland seat**. The comparator/normalizer must take two capture
  sources and normalize both to key/mouse events. Promoted to `findings/steam_input_linux.md`.
- Steam does **not** `EVIOCGRAB` the pad (`event24.grab()` OK) → the physical controller stays
  readable while Steam Input consumes it (a trace runner can watch the pad directly).
- **Next observer to build:** `tools/xi2_capture.py` (parse `xinput test-xi2 --root`, or a libei/EIS
  receiver) for the Steam lane. Optionally retest under an **X11 session** (Steam may then use XTEST —
  still not evdev).

## Phase 0 gate
- **0a (JSM lane): PASS** (evdev). See `runs/20260601T065426Z-phase0-runtime-smoke/`.
- **0b (Steam lane): observable, but at XI2/Wayland — NOT evdev.** R1 does not "collapse" the oracle;
  it **forks the observation plane per lane.** Plan §2.4/§5/§6-R1 to be updated accordingly.

## Artifacts
`evdev-baseline.txt`, `evdev-with-steaminput.txt`, `evdev-after-f9-presses.txt`,
`r1-press-capture.jsonl`, `r1-press-keys-only.jsonl`, `r1-final.jsonl` (evdev), `r1-xinput.log` (XI2),
`steam-launch.log` (the ELFCLASS32 errors).
