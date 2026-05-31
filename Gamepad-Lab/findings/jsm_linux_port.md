# JoyShockMapper on Linux — port facts (JangsJyro fork)

Durable, non-obvious facts learned bringing the `JangsJyro-JSM` fork
(`github.com/JangMan-J/JangsJyro-JSM`, branch `branch-a-port`) up on a fresh
Arch/CachyOS + Wayland + NVIDIA box. Companion to `findings/gyro_hid.md`
(hardware/HID) — this file is about the **software port + Linux runtime**.

## Updated 2026-05-31 — builds AND runs clean (start + stop)

JSM builds with **SDL3 `release-3.4.8`** (from source via CPM) and now starts
and stops cleanly on Linux. Fork HEAD at time of writing: `ae7accc`.

### Build: clang for BOTH C and C++ is load-bearing
`-DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++`. gcc 16.1.1 **ICEs**
compiling SDL3's C sources on Wayland; clang 22 does not. Setting only the C++
compiler is not enough — SDL3 is C. Other build glue (all committed): missing
includes the newer libstdc++ 16 no longer pulls transitively (`<chrono>`,
`<algorithm>`, `<iomanip>`); `hidapi` is **not** needed (SDL bundles HIDAPI);
CMake 4.3.3 CMP0169 messages on CPM sub-deps are warnings, not fatal.

### Tray: use libayatana-appindicator-**glib**, not the GTK lib
The deprecated GTK `libayatana-appindicator` was replaced by
**`libayatana-appindicator-glib`** (AUR `2.0.1-2`) — a GLib/GIO reimplementation
with no GTK dependency. The tray is a `GMenu` + `GSimpleActionGroup` (the
`indicator.` action namespace) serviced by a GLib main loop on its own thread
(commit `683a8c7`). `LinuxConfig.cmake` still links `gtk+-3.0`; likely
removable now (unverified).

## The big one: AutoLoad active-window detection is X11-only → unusable on Wayland

JSM's per-application AutoLoad calls `GetActiveWindowName()`
(`src/linux/InputHelpers.cpp`), which `dlopen`s **libX11** and uses
`XOpenDisplay` / `XGetInputFocus` / `XFetchName` / `XGetWindowProperty` to read
the focused window's executable name. On a **pure Wayland session or a tty there
is no usable X `Display`** (`XOpenDisplay(nullptr)` returns `NULL`), so the
feature is **structurally unavailable** — there is no portable Wayland API for
"name of the focused window" (it's compositor-specific / behind portals).

The original code dereferenced the null `Display` (`XInternAtom(NULL,…)`) and
**SIGSEGV'd on every poll**; it now no-ops with a one-time stderr notice
(commit `15f8e64`). **Implication for the lab:** this is concrete validation of
the **evdev/uinput-first thesis** in `vision/INDEX.md` — observing/driving input
at the kernel evdev plane is compositor-agnostic precisely because the
active-window / X11 path it replaces is this fragile. Any future autoload-by-app
on Wayland needs a different mechanism (portal, compositor protocol, or
process-side heuristic), not Xlib.

## Crash classes fixed (all from real-runtime evidence: gdb / core backtraces)

| Crash | Root cause | Fix (commit) |
|-------|-----------|--------------|
| AutoConnect ctor SIGSEGV | base `PollingThread` ctor started the poll thread before the derived `jsl` member was initialized (construction-order race) | `Start()` moved into derived ctor body; base gets `start=false` (`0eb7fac`) |
| Tray SIGSEGV | lambda on the tray thread captured an rvalue-ref `beforeShow` **by reference** → dangling | capture **by move** (`0eb7fac`) |
| AutoLoad SIGSEGV | `XInternAtom` on a null X `Display` on Wayland/tty (see above) | one-shot init flag + validate all 6 dlsym'd pointers + null-Display guard (`15f8e64`) |
| Clean-exit `std::terminate` + core | a file-static `std::thread` (`ttyForwardThread`, `initConsole()`) destroyed **joinable** by `__cxa_finalize` at `exit()` → `terminate()`. Fires on ANY clean quit, not just SIGTERM. | `.detach()` the static forwarder threads (matches the FIFO listener idiom; `join()` would deadlock on the blocking `getline`) (`ae7accc`) |

**Pattern worth remembering:** JSM's threading is a mix — `PollingThread` (AutoLoad/
AutoConnect) owns a `unique_ptr<thread>` and **joins** in its dtor; the tray
**joins** after quitting its GLib loop; the FIFO listener **detaches**. The bugs
were the two bare static `std::thread`s (`ttyForwardThread` live,
`consoleForwardThread` dormant) that did neither. On Linux, `exit()` runs
`__cxa_finalize` over static-duration objects **without unwinding `main()`'s
stack**, so only static/global thread owners (not `main`-locals) are the
terminate/deadlock risks at shutdown.

### Latent (noted, not fixed)
`terminateHandler` (`src/linux/Init.cpp`) calls `WriteToConsole()` — which locks a
`std::mutex` — **inside a signal handler**. Not async-signal-safe; latent deadlock
if a signal races the lock. Replace with a `sig_atomic_t`/`atomic<bool>` quit flag
polled by the main loop if it ever bites.

## Quick reproduce / verify

```
# build (out-of-tree)
cd ~/Projects/JangsJyro-JSM
cmake -S . -B build-linux -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++
cmake --build build-linux -j
# clean start (no SIGSEGV; "[AUTOLOAD] No X11 display available" prints once)
timeout 5 build-linux/JoyShockMapper/JoyShockMapper
# clean stop (status 0, no "terminate called", no core)
build-linux/JoyShockMapper/JoyShockMapper & sleep 3; kill -TERM %1; wait
```
Backtrace artifacts for the two 2026-05-31 fixes live in
`runs/20260531T135337Z-phase0-oracle-feasibility/`.
