# Project: theme

> **Lab scope — `theme/`** · nested repo [`JangLabs-theme`](https://github.com/JangMan-J/JangLabs-theme). This file is the authority for work *inside this lab* and **overrides** the workspace root [`../CLAUDE.md`](../CLAUDE.md). Stay in this lab — don't reach into or edit sibling labs from here. Entry point for a fresh session: [`HANDOFF.md`](./HANDOFF.md).

This lab is a data-first research lab. The goal is a **source-driven** mapper
from a terminal/TUI color scheme to desktop/app theme configs (KDE Plasma
`.colors`, Kvantum `.kvconfig`/SVG). Keep changes focused on source adapters,
the deterministic canvas/fingerprint model, correlation scoring, and durable
findings.

## Scope

- Inputs are theme **source files**, not screenshots: terminal schemes (Kitty
  `.conf`, Gogh JSON) and GUI sources (Kvantum `.kvconfig`/`.colors`/SVG).
- Catppuccin Mocha is calibration evidence; Arc Dark is the generalization
  check. Neither is a runtime dependency — the mapper must work for generic
  terminal schemes that ship no separate "canonical palette."
- Treat the terminal palette as a weighted semantic API, not 16 equal colors
  (see `findings/terminal-palette-role-significance.md`).
- Treat GUI runtime accent (KDE `AccentColor`) as a separate input axis, never
  derived from the terminal palette.

## Conventions

- Source corpora and corpus inputs live under `samples/sources/`.
- Generated artifacts (indexes, canvases, fingerprints, previews, validation
  rasters) live under `derived/` and are git-ignored — they are regenerable.
- Durable conclusions live under `findings/`.
- Tools live under `tools/` and stay small CLI programs.
- Prefer structured JSON inputs/outputs over ad hoc notes.
- Screenshots/rasterization are a one-time **calibration aid only** (Gate 2).
  The main research loop does not sample real-app screenshots.

## Validation

Run this before handing off tool changes:

```bash
python -m unittest discover -s tests
```

If Pillow is missing:

```bash
python -m pip install -r requirements.txt
```
