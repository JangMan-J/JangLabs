# theme

Data-first lab for mapping a terminal/TUI color scheme to desktop/app theme
configs. Given a terminal palette, infer which colors are structurally important
and produce plausible KDE Plasma / Kvantum UI role mappings — for generic
terminal schemes, not just families that ship a matching desktop theme.

Catppuccin Mocha is the calibration target (terminal, KDE, and Kvantum themes
exist from one design source). Arc Dark is the generalization check (Gogh
terminal scheme + real `KvArcDark` Kvantum sources). The model stays generic so
other families can be added.

## Objective

Translate terminal color-scheme **source files** into desktop theme **config
fields**, by:

- treating the terminal palette as a weighted semantic API, not 16 flat colors;
- correlating terminal roles to GUI source fields by exact match **and** weighted
  nearest-neighbor distance;
- keeping GUI runtime accent (KDE `AccentColor`) as a separate input axis.

The work is source-driven. Screenshots are a one-time calibration aid, not the
research loop.

## Layout

- `config/` — role weights (`roles.json`) and the fingerprint/scene fixtures
  (`theme-fingerprint-fixtures.json`).
- `samples/sources/` — terminal/GUI source files used as corpus inputs.
- `derived/` — generated indexes, canvases, fingerprints, previews, and
  validation rasters (git-ignored, regenerable).
- `findings/` — durable conclusions.
- `tools/` — small CLI programs.
- `tests/` — regression tests for lab tooling.
- `docs/aegis/` — planning/execution records.

## The Pipeline (`tools/theme-research.py`)

A deterministic, content-hashed pipeline from source corpus to comparable
fingerprint:

1. **index** — import a source corpus into JSONL rows. Adapters: `kitty_conf`,
   `gogh_json`, `kvantum_config`. Each row records a raw source-file hash and a
   canonical record hash.
2. **build** — resolve role/field references (with terminal and Kvantum
   fallbacks from the fixtures) into a deterministic **virtual canvas**, then a
   comparable **fingerprint** JSON. TUI canvases model a fastfetch-style screen;
   Kvantum canvases model `kvantumpreview`.
3. **preview** — render the canvas to HTML for human inspection.
4. **fingerprint** — compute weighted color-occupancy + contrast pairs.
5. **record-gate1 / gate1-status** — record/inspect manual acceptance of three
   previews per backend (the human-in-the-loop quality gate).
6. **validate-gate2** — rasterize an accepted preview with **Python** Playwright
   and sample it with Pillow; require ≥90% occupancy agreement with the virtual
   canvas. After Gate 2 passes, full research uses no screenshots.

Other source tools:

- `tools/source-color-crosswalk.py` — terminal → KDE/Kvantum source correlation
  report (exact matches + nearest weighted roles).
- `tools/kvantum-source-summary.py` — summarize a Kvantum theme's source colors.
- `tools/kde-store-tool` — search/download KDE Store archives (Kvantum + Plasma
  color schemes) to grow the source corpus.

## Tooling

Install dependencies (Pillow; Playwright only for the Gate 2 calibration step):

```bash
python -m pip install -r requirements.txt
```

Run tests:

```bash
python -m unittest discover -s tests
```

Build a source crosswalk (example: Catppuccin):

```bash
tools/source-color-crosswalk.py ~/.config/kitty/themes/Catppuccin-Mocha.conf \
  ~/.local/share/color-schemes/CatppuccinMochaSapphire.colors \
  ~/.config/Kvantum/catppuccin-mocha-sapphire/catppuccin-mocha-sapphire.kvconfig \
  ~/.config/Kvantum/catppuccin-mocha-sapphire/catppuccin-mocha-sapphire.svg \
  --json derived/catppuccin-mocha-kitty-to-kde-kvantum.crosswalk.json
```

The crosswalk treats only `background`, `foreground`, `selection_*`, `cursor`,
and `color0`–`color15` as terminal palette input; Kitty tab/mark/border/URL
fields are reported separately as emulator-specific extras.

Search and download KDE Store archives:

```bash
tools/kde-store-tool search "Utterly Nord" --limit 5
tools/kde-store-tool download "Utterly Nord" --category "Plasma Color Schemes" \
  --extract --json derived/kde-store-downloads/utterly-nord-colors.report.json
```
