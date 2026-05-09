# Gamepad-Lab — agent conventions

This lab investigates Steam Input vs JoyShockMapper (JSM) behavior on a real controller (8BitDo Ultimate 2 Wireless), and ports tuned Steam Input layouts to JSM. The thesis: **real-runtime behavioral comparison, not syntax-level translation.** Configs that parse identically still feel different in practice; runtime traces are the only acceptable evidence.

## Read first, in this order

1. **`2026-04-29-gamepad-mapper-conversion-lab-design.md`** — current design doc. Phase plan, agent roles, artifact contracts, validation policy.
2. **`handoffs/INDEX.md`** — what investigations are paused mid-flight, with current step.
3. **`findings/INDEX.md`** — durable knowledge surfaced across sessions.
4. **`docs/superpowers/plans/INDEX.md`** — active plans and supersession graph.
5. **`tools/README.md`** — runnable Python scripts and their dependencies.

`docs/README.md` is **partly stale** (references `BACKLOG.md`, `mouse_meter.py`, `gyro_probe_dinput.py` that no longer exist; uppercases `FINDINGS/`/`HANDOFFS/` while disk is lowercase). The INDEX files above are authoritative.

## Sacred files

- **`handoffs/*`** — context seeds for resuming paused work cold. Add new ones; don't mutate existing ones casually. If state has moved on, write a new handoff and mark the old one superseded in `handoffs/INDEX.md`.
- **`findings/*`** — append-only durable knowledge. Edit only to mark superseded with a forward link, or to fix factual errors. Adding a new finding is preferred to rewriting an old one.

## Test device + pinned versions

- **Controller:** 8BitDo Ultimate 2 Wireless, **VID `0x2DC8` / PID `0x6012`**, DInput mode (B+Home at startup). Firmware v1.09 minimum (v1.03+ for the 34-byte sensor-bearing report — see `findings/gyro_hid.md`).
- **JSM:** branched off master at `bb69784488937e0a5e21988b966eccd9f04d504e`, plus the `branch-a-port` cherry-picks live-verified 2026-04-22 (21/21 inputs).
- **SDL3:** `release-3.4.4` at `5848e584a1b606de26e3dbd1c7e4ecbc34f807a6` (3.4.x is required — `SDL_hidapi_8bitdo.c` doesn't exist on 3.2.x).

Don't change pinned SHAs without updating `findings/jsm_sdl3_source_verification.md` and noting the rebuild in a new finding.

## Evidence rules

- **No parity claim without runtime evidence.** Static source review is a *gate*, not a verdict — see how Phase 1 yielded a YELLOW verdict in `findings/jsm_sdl3_source_verification.md` despite the code reading correctly.
- **Live verifications cite a log file** under `reference/JSM_JangManJ/` (e.g. `run2.txt` for 21/21 confirmation). New verifications must produce a similar artifact.
- **Adversarial trace generation** (per design doc § "Adversarial Trace Generation"): produce traces that try to expose drift between Steam Input and JSM, not traces that confirm equivalence on easy paths.

## Runtime gotchas (Windows test rig)

- **8BitDo Ultimate Software** tray app holds the pad's HID interface exclusively → tray → **Exit** (not minimize) before any test.
- **Steam** claims HID controllers via Steam Input even when not focused → fully exit Steam (tray → Exit) for live tests.
- **CMake** lives at `C:\Program Files\CMake\bin\cmake.exe` and is *not* on PATH in plain bash — `export PATH="/c/Program Files/CMake/bin:$PATH"` per shell.
- **Bluetooth is out of scope.** 2.4GHz dongle only.

## Where things go

| Change | Where |
|--------|-------|
| New durable observation | `findings/<topic>.md` + add line to `findings/INDEX.md` |
| New paused-investigation seed | `handoffs/<topic>.md` + add line to `handoffs/INDEX.md` |
| Implementation plan | `docs/superpowers/plans/<date>-<topic>.md` + add line to plans `INDEX.md` |
| Design doc that informs a plan | `docs/superpowers/specs/<date>-<topic>-design.md` |
| New runnable script | `tools/<name>.py` + add line to `tools/README.md` |
| Raw user-supplied artifact | `reference/<grouping>/...` (logs, VDFs, screenshots, HID dumps) |
| Per-run trace artifacts | `docs/superpowers/runs/<run-id>/` (dir created on first use) |
