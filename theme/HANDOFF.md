# Theme-Lab Handoff

Single source of truth for project state — read this first. Render-pipeline detail
lives in `docs/imagegen/PROGRESS.md`; durable conclusions in `findings/`; aegis
records under `docs/aegis/` explain *why* past changes were made.

## Final goal

Learn the mapping from a **terminal (TUI) color scheme** to a **GUI (Kvantum/KDE)
theme**, in two parts:

- **(a) Palette matching** — given a TUI theme and a corpus of GUI themes, with **no
  filenames**, decide with reasonable confidence whether a TUI theme and a GUI theme
  were likely derived from the same color palette. Pair them by color evidence alone.
- **(b) Role correlation** — across many matched TUI↔GUI pairs, learn which GUI element
  each terminal color field most strongly drives (e.g. terminal `color1` → highlight /
  selected text). This correlation *is* the deliverable mapping.

Catppuccin Mocha is calibration evidence; Arc Dark is the generalization check. The
method must work for generic terminal schemes that ship no separate "canonical palette."

## Method / direction

Data model = **a measured color distribution ("fingerprint") over an
artificial-but-representative rendered scene.** We fingerprint what *renders*, not the
raw source values, because Kvantum is gradient/SVG-based — a theme's literal color
often never appears as a pixel, and what a user actually sees is what matters.

1. **Render** a theme into a representative scene (real engine, headless), per surface.
2. **Fingerprint** = the statistical color occupancy of that render → feeds matching (a).
3. The render doubles as the **human-auditable proxy**: the user verifies the scene
   mirrors real usage, so the data is trustworthy before any matching/correlation is
   believed. **Realism = data fidelity, not aesthetics.**
4. **Attribution for (b) via perturbation**: change one theme line at a time to a loud
   probe color, re-render, diff against baseline — the changed pixels localize which
   GUI element that field controls, and which source file (`.colors`/`.kvconfig`/`.svg`)
   owns it. Handles gradients (you detect *where a change propagates*, not the color).
   This is a **one-time calibration**, not per-theme.

### Occupancy vs coverage (key distinction)
- **Occupancy** (fingerprint / matching) needs *realistic proportions* → typical use;
  don't force colors in. A sparse scene over-boosts background and lies about the data.
- **Coverage** (attribution) needs only *presence + identity* → a rare element just has
  to appear *somewhere*; perturbation localizes it regardless of size.
- Reconcile with **instrumentation regions**: present but **excluded from the occupancy
  sample** (the terminal palette bar; a GUI coverage panel if needed).

### Analysis priors (from `findings/`)
Treat the terminal palette as a **weighted semantic API**, not 16 equal colors; match
by **weighted nearest-neighbor**, not exact equality (Arc Dark's surfaces cluster near
Gogh `color8`, not the terminal background); keep GUI runtime accent (KDE `AccentColor`)
as a **separate input axis**.

## Scenes (the renders) — current state

Both surfaces render to a common **1280×600** canvas (calibration theme
catppuccin-mocha-sapphire). No transient states (hover/pressed) are needed.

- **GUI** = `docs/imagegen/scene-gui-gallery.py` — a reproduction of the official **Qt
  Widgets Gallery**, real Qt widgets painted by **real Kvantum** offscreen
  (`QT_QPA_PLATFORM=offscreen`, `QT_STYLE_OVERRIDE=kvantum`, theme written into a
  throwaway `XDG_CONFIG_HOME`). Dense + balanced — a sparse single window (the earlier
  file-manager attempt) over-boosted background. Output:
  `derived/previews/scene-gui-gallery-catppuccin-mocha.png`. **User-approved.**
- **Terminal** = `docs/imagegen/scene-terminal.py` — fastfetch-style (logo + sysinfo =
  natural usage) + the 16-swatch **palette bar = instrumentation strip** (excluded from
  the occupancy sample). Exact palette baked as truecolor; rendered by **freeze** via
  stdin, normalized to 1280×600 with ImageMagick. Output:
  `derived/previews/scene-terminal-catppuccin-mocha.png`. **Drafted, pending final lock.**

## Proven mechanisms
- **Headless real Kvantum render**: offscreen Qt + `QT_STYLE_OVERRIDE=kvantum` + a
  throwaway `XDG_CONFIG_HOME` holding `Kvantum/kvantum.kvconfig` → renders any theme
  (incl. generated ones) in isolation; palette inherited exactly. (Memory:
  `method-headless-kvantum-render.md`.)
- **freeze terminal render** via stdin (`freeze -b '#1e1e2e' -o out.png < scene.ans`) +
  magick normalize. Gotchas: freeze `--execute` *hangs* here; `cat` is aliased to `bat`;
  `-p/--padding` panics on truecolor-bg content. (Detail in `docs/imagegen/PROGRESS.md`.)

## Scale (after the gates)
Once the scenes are verified representative and the method calibrates against installed
themes, the user will run the pipeline over **hundreds** of theme files. Bulk = one
representative render + source parse per theme, applying the **one-time**
perturbation-learned field→element map. Process-per-theme, parallelizable.

## Done / next

Done: render method proven for both surfaces; GUI scene approved; terminal scene
drafted; data model and direction settled; scene scripts + outputs under
`docs/imagegen/` and `derived/previews/`.

Next:
1. Lock the terminal scene (optional logo/content/density tweaks).
2. **Fingerprint extractor** — sample each render's color occupancy (excluding the
   instrumentation strip) → comparable per-theme histogram (Pillow is available).
3. **Perturbation attribution** harness → field→element map across `.kvconfig`/`.colors`
   (then `.svg`).
4. **Calibration gates** — render catppuccin-mocha + KvArcDark, compare to one real
   Plasma screenshot each; tune until faithful.
5. **Bulk** over the corpus → palette matching (a) + role correlation (b).

## Repo / conventions
- Active branch: `feature/kitty-expected-mapping` (commits unpushed).
- Tools under `tools/`; generated artifacts under `derived/` (git-ignored); durable
  conclusions under `findings/`; render WIP under `docs/imagegen/`. The screenshot-era
  methodology was retired earlier (history in git / `docs/aegis/`).
- Validation: `python -m unittest discover -s tests`.

## Read first
1. This file, then `docs/imagegen/PROGRESS.md` (render pipeline + gotchas).
2. `findings/terminal-palette-role-significance.md`
3. `findings/source-color-crosswalk.md`
4. `findings/arc-dark-source-render-correlation.md`
