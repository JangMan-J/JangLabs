# Phase 0a — JSM Linux build + clean runtime — RESULT: PASS

**Date:** 2026-05-31 · **Host:** CachyOS (Arch), Wayland, NVIDIA (open) · gcc 16.1.1 / **clang 22.1.6** / cmake 4.3.3
**Source:** `JangsJyro-JSM` @ `branch-a-port` (`github.com/JangMan-J/JangsJyro-JSM`), HEAD **`ae7accc`**.

## Outcome
- **configure rc=0, build rc=0.** Binary: `build-linux/JoyShockMapper/JoyShockMapper`
  (~1.8 M x86-64 ELF, clang 22, SDL3 `release-3.4.8` from source via CPM).
- **Starts clean** — SDL up (`0 devices connected`), command FIFO, AUTOLOAD, and the GTK-free
  libayatana-appindicator-**glib** tray all initialize; **no SIGSEGV** (3/3 runs survive 12s).
- **Stops clean** — on SIGTERM/SIGINT/QUIT the process exits with status 0, **no `terminate`, no core**
  (3/3); the tray + PollingThread destructors now run end-to-end without deadlock.

Verdict upgraded from the initial "PASS (build)" to **PASS (build + clean start/stop runtime)** after
fixing four crashes and migrating the deprecated tray lib (below). The oracle (JSM on Linux) is viable.

## Recipe (the load-bearing bits)
- **clang for BOTH C and C++** (`-DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++`). gcc 16.1.1 +
  SDL3-on-Wayland C source ICEs; clang avoids it.
- `CPM_SOURCE_CACHE=$HOME/.cache/CPM` so SDL3 persists across clean build-dir wipes.
- `hidapi` **not** needed (SDL bundles HIDAPI); `xscrnsaver` (the handoff's "first failure point") already satisfied.
- CMake 4.3.3: CMP0169 / `cmake_minimum_required < 3.10` on CPM sub-deps are **warnings**, not fatal.
- Tray runtime dep: **`libayatana-appindicator-glib`** (AUR `2.0.1-2`) — the GLib/GIO reimplementation,
  not the deprecated GTK `libayatana-appindicator`.

## Port work — now a committed 5-commit arc on `branch-a-port`
| Commit | What |
|--------|------|
| `ad11ea0` | Build glue: clang/libstdc++-16 missing includes (`<chrono>`, `<algorithm>`, `<iomanip>`) + accept ayatana appindicator in `LinuxConfig.cmake` |
| `0eb7fac` | Two startup crashes: **AutoConnect ctor race** (base ctor started the poll thread before `jsl` init) + **tray dangling capture** (lambda captured an rvalue-ref `beforeShow` by reference) |
| `683a8c7` | **Tray migration** to `libayatana-appindicator-glib` — drops the deprecated GTK lib; GMenu + GSimpleActionGroup (`indicator.` namespace) on a GLib main loop. Supersedes the `ad11ea0` `__has_include`/ayatana glue. |
| `15f8e64` | **AutoLoad SIGSEGV** (this session) — `XInternAtom(NULL,…)` on Wayland/tty. See `jsm-autoload-segv-backtrace.txt`. |
| `ae7accc` | **Clean-exit `std::terminate`** (this session) — static `std::thread` destroyed joinable at `exit()`. See `jsm-shutdown-terminate-backtrace.txt`. |

**Uncommitted (yours):** `JoyShockMapper/CMakeLists.txt` SDL3 pin `release-3.4.4` → `release-3.4.8`.
All commits are non-semantic w.r.t. mapping behavior and `win32/` is untouched — upstream-worthy.

## Crashes fixed (real-runtime evidence, gdb/core backtraces archived)
1. **AutoConnect ctor race** (`0eb7fac`) — `Start()` moved into the derived ctor body after `jsl` is set; base ctor passed `start=false`. Artifact: `jsm-segv-backtrace.txt`.
2. **Tray dangling capture** (`0eb7fac`) — lambda on `thread_` now captures `beforeShow` **by move**.
3. **AutoLoad SIGSEGV** (`15f8e64`) — `GetActiveWindowName()`: one-shot init flag, validate all six dlsym'd X11 pointers, guard the null `Display`, single-fire "autoload disabled" notice. Artifact: `jsm-autoload-segv-backtrace.txt`.
4. **Clean-exit terminate** (`ae7accc`) — `.detach()` the static console forwarder threads (`join()` would deadlock on blocking `getline`). Artifact: `jsm-shutdown-terminate-backtrace.txt`.

## Durable fact (candidate for `findings/`)
JSM's per-application AutoLoad uses **X11-only active-window detection** (`GetActiveWindowName` → Xlib).
On pure Wayland / tty there is no usable X `Display`, so the feature is **structurally unavailable** —
JSM now no-ops it with a one-time notice instead of crashing. This is concrete validation of the lab's
**evdev/uinput-first thesis** (`vision/INDEX.md` — compositor-agnostic observation): the active-window
approach is exactly the Wayland-fragile path the conversion lab is designed to avoid.

## Known non-blocking issues
- **Version string** `v-128-NOTFOUND…` — `git_describe --tags` finds no tags on the fork. Cosmetic.
- **`terminateHandler` async-signal-safety** (`src/linux/Init.cpp:15-24`) — calls `WriteToConsole()`, which
  locks a `std::mutex` inside the SIGTERM/SIGINT handler. Not async-signal-safe; latent deadlock if a signal
  races the lock. Did not cause any observed crash. A hardening would use a `sig_atomic_t`/`atomic<bool>`
  quit flag polled by the main loop. Flagged by the shutdown workflow; out of scope for the crash fixes.
- **`gtk+-3.0`** still linked in `LinuxConfig.cmake` (`PkgConfig::Gtkmm`) though the tray no longer needs GTK.
  Possibly removable now; unverified.

## Next (Phase 0, still open)
- **0a runtime smoke:** drive `S=SPACE` / `ZR=LMOUSE` and observe at evdev (keyboard/mouse output only —
  Linux virtual-gamepad output is a stub). Needs the physical 8BitDo or a synthetic uinput pad.
- **0b (the crux):** can Steam Input be driven by a synthetic controller and observed at evdev?
- ~~Decision: commit the build-glue patches~~ — **RESOLVED**: committed as `ad11ea0`…`ae7accc`; only the SDL3 pin remains yours to land.
