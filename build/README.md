# build/ — workspace build output

This is the **one sanctioned exception** to the JangLabs root rule that every
top-level non-dot directory must be a git submodule. `build/` is **not** a lab and
**not** a submodule: it is a shared output directory where compiled binaries and
build artifacts produced by the labs' tools land.

## Rules

- **Only this `README.md` is tracked.** Everything else under `build/` is git-ignored
  (see the root `.gitignore`) because it is regenerable. Don't commit binaries here.
- **Namespace by lab.** Put a lab's outputs under `build/<lab>/…` (e.g.
  `build/gamepad/`, `build/jangsjyro/JoyShockMapper`) so artifacts from different labs
  don't collide.
- **Source stays in its lab.** A lab's build *system* (CMake files, scripts, sources)
  lives inside that lab's submodule; only the *output* is redirected here. Point a
  lab's build at `../build/<lab>/` rather than writing artifacts back into the lab.
- **Disposable.** Anything here can be deleted and rebuilt. Don't treat it as
  source-of-record for anything.

## Why it exists

Keeping compiled output in one ignored, lab-namespaced tree keeps each lab's submodule
clean (no stray build artifacts churning its git status) and gives cross-lab tooling a
single predictable place to find binaries. It is the only non-submodule directory
permitted at the workspace root — see [`../CLAUDE.md`](../CLAUDE.md).
