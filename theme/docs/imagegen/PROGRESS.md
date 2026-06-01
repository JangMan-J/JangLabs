# Imagegen — Progress & Resume Notes

Status: 2026-05-29. The *function* of the renders is now settled (see "What the
renders are for"). Next concrete step is nailing the two scenes. This file lets
the work resume cold.

## Goal of this work

Generate **headless, automated mockups** that render a terminal scheme and a
KDE/Kvantum theme *as they'd actually look in use*, so the **statistical color
distribution ("fingerprint")** extracted from each render is representative. The
render is the human-auditable proxy for that data. Replaces codex's HTML/CSS
approximations, which the user rejected as unrealistic.

Method decisions:
- GUI mockup → **real Kvantum render** (offscreen Qt), zero installs.
- Terminal mockup → **freeze** (real ANSI→image).
- Output form → **separate per-surface PNGs**.
- Fidelity check → **calibrate against installed themes** (catppuccin-mocha, KvArcDark).

## What the renders are for (resolved)

The data model is **#2: a measured color distribution/occupancy over a realistic
scene** — input a theme → render an artificial-but-representative scene → analyze
pixel color distribution → that *is* the theme fingerprint. Two downstream analyses
consume it:

- **(a) Brute-force matching** TUI↔GUI with no filename — "were these two themes
  likely drawn from the same palette?"
- **(b) Role correlation** — across many matched pairs, learn which GUI element each
  terminal color field most drives (e.g. `color1 → highlight text`).

Both break if a scene packs colors unnaturally: prominence becomes fiction, so (a)
matches on fake proportions and (b) over-weights elements nobody really sees.
**Realism = data fidelity, not aesthetics.** No window chrome unrelated to the theme.

## Field→element attribution: perturbation probe (the method for (b))

Kvantum is gradient/SVG-based, so a literal color in the theme file (e.g.
`#383C4A`) often **never appears verbatim** as a pixel — it seeds a gradient.
Therefore don't search the render for the color; **perturb one theme line at a
time to a loud unique probe color (e.g. pure magenta), re-render, diff vs the
baseline.** The changed pixels localize the element regardless of gradient
transform. Properties:

- **Region → semantic label is free** — we author the scene, so we already know
  "those pixels are the selected row / toolbar / view background." Yields
  field → *element*, not just field → coordinates.
- **Disambiguates the source surface.** A Kvantum look is driven by THREE files —
  KDE `.colors` scheme, `.kvconfig`, `.svg` gradients — and which one owns an
  element depends on config flags. Perturb-and-see-what-moves resolves this
  empirically (otherwise it requires reverse-engineering Kvantum internals).
- **1:N and N:1 fall out** — one field changing many regions = color reuse; a
  region resolving only after several perturbations = layered gradients.
- **Occupancy and coverage are DIFFERENT requirements (decouple them).** The
  fingerprint needs realistic *proportions* (typical use); attribution needs only
  *presence + identity* — perturbation localizes a region regardless of its size.
  So "less-used" elements (sliders, progress, tabs, disabled/hover states) must
  still appear *somewhere* or we get zero attribution data for them — but they go
  in an **instrumentation region excluded from the occupancy sample** (the same
  trick as the palette bar), so they don't distort the fingerprint. Bonus: the
  probe yields prominence for free — a field that changes pixels in the sampled
  region is prominent; one that only changes the instrumentation region is rare.
- The proven offscreen-Kvantum + temp-`XDG_CONFIG_HOME` machinery (below) is
  literally the probe engine: loop lines → write modified theme to throwaway
  config → render → diff. Start with `.kvconfig`/`.colors` lines; extend to `.svg`
  fills/stops (where much gradient color actually lives) in a second pass.

## Proven (both render halves work)

### GUI — real headless Kvantum render  ✅
- Env (before Qt starts): `QT_QPA_PLATFORM=offscreen`, `QT_STYLE_OVERRIDE=kvantum`,
  `XDG_CONFIG_HOME=<tmpdir>`. Write `<tmpdir>/Kvantum/kvantum.kvconfig` =
  `[General]` + `theme=<Name>`. PySide6 → `w.show()` → `processEvents()` → `w.grab().save()`.
- Verified palette inherited exactly (Mocha `#1e1e2e`/`#cdd6f4`/sapphire `#74c7ec`);
  temp XDG **isolates from live config**; assets resolve from `/usr/share/Kvantum`.
  A *generated* theme dir dropped in `<tmpdir>/Kvantum/<Name>/` renders in isolation.
- Spike: `docs/imagegen/spike-kvantum.py`. Memory: `method-headless-kvantum-render.md`.

### Terminal — freeze render  ✅
- freeze v0.2.2 (AUR; `vhs` 0.11.0 is the heavier official-repo real-PTY alt).
- No ANSI-palette config key → bake exact colors as **24-bit truecolor FG**
  (`\e[38;2;r;g;bm`); set bg via `--background '#RRGGBB'`.
- **Feed ANSI via STDIN, NOT `--execute`:** `freeze -b '#1e1e2e' -o out.png < scene.ans`.
  In this box's bash-tool env `freeze --execute "<cmd>"` HANGS ("no command output"),
  and `cat` is aliased to `bat` — avoid both; stdin redirect is reliable.
- freeze renders ~2x DPI (a ~46-col scene came out 2069x1431); normalize to the canvas:
  `magick raw.png -resize 1280x600 -background '#1e1e2e' -gravity center -extent 1280x600 out.png`
  (fit + pad, never crop).
- `-p/--padding` panics on truecolor-BG content — use fg block glyphs / `--margin`.
- Scene generator: `docs/imagegen/scene-terminal.py` (fastfetch-style + palette bar).

## Scene design — current (catppuccin-mocha calibration, canvas 1280×600)

No transient states (hover/pressed). Not tied to kvantumpreview. A sparse realistic
window over-boosts background, so the GUI scene is a DENSE, balanced widget showcase.
Both surfaces render to the same **1280×600** canvas.

- **GUI** = `docs/imagegen/scene-gui-gallery.py` — reproduction of the official Qt
  Widgets Gallery (4 group boxes: radios/checks, push buttons + command link,
  table+text-edit tabs, full input column + profile list; progress bar). Top groups
  collapse to content so dead background is minimal. Real Qt widgets, real Kvantum,
  offscreen. Dense + balanced → serves as the fingerprint scene and broad coverage.
  Render: `XDG_CONFIG_HOME=<tmp> QT_QPA_PLATFORM=offscreen QT_STYLE_OVERRIDE=kvantum
  python scene-gui-gallery.py out.png <theme> 1280 600`. **User-approved.**
- **Terminal** = `docs/imagegen/scene-terminal.py` — fastfetch-style (logo + sysinfo =
  natural usage) + the **16-swatch palette bar = instrumentation strip** (every color
  present; EXCLUDE from the occupancy sample). bg-dominant = realistic. Truecolor FG;
  stdin freeze + magick normalize (see terminal notes above). **Drafted, pending lock.**
- Outputs: `derived/previews/scene-gui-gallery-catppuccin-mocha.png`,
  `derived/previews/scene-terminal-catppuccin-mocha.png`.
- Instrumentation regions (palette bar; any GUI coverage panel) are present for
  attribution but EXCLUDED from the occupancy sample, so they don't distort the
  fingerprint. Occupancy ≠ coverage.
- Defaults chosen autonomously ("you sort it out"): synthetic fastfetch layout
  (real-fastfetch-recolor deferred), neutral placeholder logo — trivial to swap.

## Next steps to resume

1. **Nail the two realistic scenes** (GUI app-window, terminal window).
2. Baseline render → extract occupancy fingerprint (sampled region excludes any
   palette-reference strip).
3. **Perturbation probe** across `.kvconfig`/`.colors` lines (then `.svg`) to build
   the field→element map and learn which source file owns each element.
4. Promote spikes → `tools/render-kvantum.py`, `tools/render-terminal.py`; wire to
   `tools/theme-research.py`; outputs to `derived/previews/` (git-ignored).
5. Calibrate against installed catppuccin-mocha + KvArcDark vs one real screenshot each.
