# Steam Input output on Linux — observation plane (Beta + SteamRT3 + Wayland)

Durable real-runtime finding from **Phase 0b** of the mapper-conversion lab. Answers crux **R1**:
*can Steam Input be driven by a controller and its keyboard/mouse output observed at the kernel evdev
plane?* Tested 2026-06-01 on this box. Companion to `jsm_linux_port.md` (the JSM lane).

## Setup tested (NOT stock Steam — the whole point was to test, not assume)
- Steam **Beta** + **experimental Steam Runtime 3 (sniper)**, native pacman install on CachyOS,
  Wayland + KWin, NVIDIA. The Steam **client itself runs inside pressure-vessel**
  (`…/Steam/steamrt64/steam` via `pv-run.sh` + `steam-runtime-launcher-service`) — a bubblewrap
  container with its own mount namespace. This is why lib paths show up as `/run/host/usr/...` and why
  `/proc/<pid>/{maps,environ,fd}` reads are opaque (`dumpable=0` + namespacing).
- Real 8BitDo Ultimate 2 (D-Input, `2dc8:6012`, evdev `event24`), Steam Input enabled for it, one face
  button bound to keyboard **F9** in the Desktop layout.

## Result: output is NOT on the evdev plane; it IS on the Wayland/XI2 plane
Both planes observed simultaneously (background observers) while the bound button was pressed 11×.
`event24` showed `BTN_B` ×11 press/release → **press confirmed** independently.

| Plane | Observer | F9 seen? |
|---|---|---|
| **evdev** (`/dev/input/event*`) | `tools/evdev_capture.py` (all nodes) | **0** — no `KEY_F9` on any node; **Steam created no new uinput device** at any point (pre/post-press `list` diff clean) |
| **X11 / Xwayland (XI2)** | `xinput test-xi2 --root` | **11× `KeyPress` keycode 75 (F9)** + 11× release, matching the presses 1:1 |

**The F9 arrived on XI2 device `id=9 xwayland-keyboard:10`** (the Xwayland seat) — the same device that
carries physical keystrokes, so Steam's injected F9 is **indistinguishable from physical input at the X
layer**. It is definitively **not evdev/uinput** (no node ever created, no `KEY_F9` on any node).

**Mechanism (X11 XTEST vs libei/EIS) is UNDETERMINED — do not over-read the device-id.** A follow-up
self-test (`tools/xi2_capture.py` + `xdotool key F9`, which is *pure XTEST*) showed XTEST **also** lands
on `id=9`, **not** on `id=5 "Virtual core XTEST keyboard"`. So on this EIS-enabled Xwayland (KWin +
recent Xwayland), XTEST is itself rerouted to the seat, and the XI2 device-id **cannot** separate XTEST
from libei. (`steamui.so` links `libXtst`/`XTestFake*`, so an XTEST path is plausible but unproven.) The
robust, lab-relevant result is the **plane** (XI2 yes, evdev no), not the injector.

## Consequences (load-bearing for the lab)
1. **"Observe at evdev" (plan §2.4) does NOT cover the Steam-Input lane on Wayland.** It holds for the
   **JSM lane** (JSM emits real uinput devices `JoyShockMapper_KEYBOARD/_MOUSE`, evdev-visible — see
   `jsm_linux_port.md`), but Steam Input's kbd/mouse output never reaches `/dev/input/event*` here. The
   two oracle lanes are observed on **different planes**: JSM = evdev; Steam Input = XI2 / Wayland seat.
   The comparator/normalizer must accept two capture sources and normalize both to key/mouse events.
2. **`extest` relevance is UNDETERMINED — a testable follow-up, not settled.** extest re-routes X11
   `XTestFake*` calls to uinput; **if** Steam Input uses the XTEST path (plausible but unproven — see
   above), preloading the **64-bit** extest into the client could surface its output at evdev and unify
   both lanes there. The Phase-0b preload attempt does **not** settle it: it used the **32-bit**
   `/usr/lib32/libextest.so`, which ELF-rejects into the 64-bit client (`wrong ELF class: ELFCLASS32`)
   and never loaded. Proper test = `LD_PRELOAD=/usr/lib/libextest.so` (64-bit) on the Steam client, then
   look for an `extest fake device` evdev node + `KEY_F9` at evdev. extest here was a user experiment,
   not part of Steam.
3. **Steam does NOT `EVIOCGRAB` the controller's evdev node** — `event24` `grab()` succeeds and its raw
   `BTN_B` stays readable by other processes. Only Steam's *output* is off-evdev; the physical pad
   remains observable (useful: a trace runner can read the pad while Steam Input consumes it).
4. **Steam-lane observer = `tools/xi2_capture.py`** (built 2026-06-01; parses `xinput test-xi2 --root`
   under `stdbuf -oL`, resolves keysym + source device) — not `evdev_capture.py`. Open follow-ups:
   (a) preload **64-bit** extest to test whether Steam's output can be forced onto evdev (consequence
   2); (b) retest under an **X11 (non-Wayland) session**, which *might* route Steam via the legacy XTEST
   device — still not evdev.

## Method note (avoiding false negatives — these traps bit twice before the clean run)
- **Blocking foreground captures miss user-driven stimuli** that happen between conversation turns. Use
  **background observers that span the turn**; have the user act, then stop+read.
- **Confirm the stimulus independently before trusting an output-absence** (here: `event24 BTN_*`).
  Early "no F9" runs were inconclusive because the button hadn't been pressed *during* the window.
- **XI2 device-id reveals the PLANE, not the upstream injector on EIS-Xwayland.** `xwayland-keyboard:N`
  = the seat — XTEST, libei, *and* physical all surface there (verified: `xdotool key F9`, pure XTEST,
  lands on the seat, not on `Virtual core XTEST keyboard`). A new `/dev/input/event*` node = uinput. Use
  it to confirm "X11/XI2 vs evdev"; do **not** over-read it as "libei not XTEST."
- **Don't trust `pgrep steam` from a shell whose command line contains "steam"** — it self-matches.
  Match by `comm`.

Reproduce / artifacts: `runs/20260601T070951Z-phase0b-steam-input/`.
