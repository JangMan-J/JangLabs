# Arc Dark Cross-Theme Handoff

## Final Objective

Build a practical mapper from terminal/TUI color schemes to desktop/app theme
configs.

The mapper should ingest a terminal color scheme, infer which colors are
structurally important based on terminal role designation, and produce plausible
KDE/Kvantum/app UI role mappings. It should work for generic terminal schemes
that do not have a separate published "canonical palette." Catppuccin is
calibration evidence, not a runtime dependency.

## Approach Shift

Earlier work asked whether GUI colors exactly matched terminal palette colors.
That was useful for Catppuccin, but it does not generalize well.

The current model is:

1. Treat the terminal palette as a weighted semantic API, not 16 equal colors.
2. Infer a structural neutral/surface/text ladder first.
3. Use red/green/yellow as high-confidence status semantics.
4. Use blue/magenta/cyan as medium-confidence accent/navigation/syntax families.
5. Score GUI target colors by exact match and nearest terminal-role neighbors.
6. Use Kvantum source files first, then minimal screenshots only to verify
   rendered source roles.

This reduces manual capture work. The efficient pattern is source correlation
plus one rendered validation screenshot per theme/state family.

## Key Realizations

- `background` and `foreground` have much higher significance than arbitrary
  ANSI hue slots because they dominate ordinary terminal display.
- `selection_background`, `selection_foreground`, and `cursor` are first-class
  terminal interaction roles, not ordinary ANSI colors.
- `color0`, `color8`, `color7`, and `color15` are often the useful neutral ramp
  for desktop surfaces, borders, disabled text, and secondary text.
- Bright ANSI variants are usually family/emphasis evidence, not independent
  desktop roles unless proven by the theme.
- GUI desktop surfaces may intentionally not equal terminal `background`.
  Arc Dark proves this: KvArcDark surfaces cluster near Gogh `color8`, not the
  Gogh terminal background.
- Kvantum is the important validation surface because it owns most of the
  widget-engine behavior. KDE `.colors` alone is insufficient.

## Evidence Collected

### Catppuccin Calibration

Catppuccin Mocha remains useful because terminal, KDE, and Kvantum themes exist
from the same design source.

Evidence already established:

- Kitty Catppuccin Mocha ANSI grid and selection captures passed exact checks.
- Catppuccin terminal roles all match the published Mocha palette exactly.
- GUI-only colors such as `mantle`, `crust`, `surface0`, `overlay2`, and
  Sapphire accent are not necessarily present as normal terminal roles.
- Kvantum focused-input accent follows KDE runtime `AccentColor`, not just the
  static terminal palette.
- Dolphin showed selected Kvantum theme surfaces:
  - main view: Catppuccin base/background
  - sidebar/toolbar: Catppuccin mantle-like darker surface
  - path bar: rendered/derived near-neighbor shade

Important files:

- `findings/source-color-crosswalk.md`
- `findings/dolphin-kvantum-theme-comparison.md`
- `findings/catppuccin-accent-axis.md`

### Terminal Role Weighting

Subagent research converged on the same model: ANSI 16 is not a flat palette.
The role designation matters.

Important files:

- `findings/terminal-palette-role-significance.md`
- `config/roles.json`
- `config/capture-sequence.md`

`config/roles.json` now records `terminal_role_weights`.

### Arc Dark Target

Solarized had good terminal/KDE evidence but no credible standalone Kvantum
theme source. The target changed to Arc Dark.

Arc Dark was selected because:

- Gogh includes a dark `Arc Dark` terminal scheme.
- Local system has real Kvantum sources:
  - `/usr/share/Kvantum/KvArcDark/KvArcDark.kvconfig`
  - `/usr/share/Kvantum/KvArcDark/KvArcDark.svg`
  - `/usr/share/color-schemes/KvArcDark.colors`
- KvArcDark exercises real widget-engine surfaces and states.

Important files:

- `findings/arc-dark-target-selection.md`
- `samples/sources/gogh-arc-dark.kitty.conf`

### Arc Dark Source Correlation

Source crosswalk command:

```bash
tools/source-color-crosswalk.py samples/sources/gogh-arc-dark.kitty.conf /usr/share/color-schemes/KvArcDark.colors /usr/share/Kvantum/KvArcDark/KvArcDark.kvconfig /usr/share/Kvantum/KvArcDark/KvArcDark.svg --family arc --base dark --accent blue --json derived/arc-dark-gogh-to-kvarcdark.crosswalk.json
```

Main source-only result:

- KvArcDark `window.color` `#383C4A` is nearest Gogh `color8` `#3B4D68`.
- KvArcDark `base.color` `#404552` is nearest Gogh `color8` `#3B4D68`.
- KvArcDark `button.color` `#414654` is nearest Gogh `color8` `#3B4D68`.
- KvArcDark `highlight.color` `#5294E2` is nearest Gogh `color12` `#3063D9`,
  with blue/cyan-family neighbors.

This confirms that exact matching is too strict. Correlation strength should be
measured by weighted nearest-neighbor roles.

Important files:

- `tools/source-color-crosswalk.py`
- `tests/test_source_color_crosswalk.py`
- `findings/arc-dark-source-render-correlation.md`

### Arc Dark Rendered Evidence

Usable capture:

- `reference/captures/arc__dark__blue__kvantum-preview__kvantum__buttons-normal__2026-05-27__002.png`

Point map:

- `samples/arc-dark-kvantum-buttons-normal-2026-05-27.json`

Sample output:

- `derived/arc-dark-kvantum-buttons-normal.samples.json`

Reliable sampled results:

- `view_background`: `#404552`, exact KvArcDark `GeneralColors.base.color`,
  nearest Gogh `color8`.
- `button_background`: `#444A58`, rendered neutral shade near Gogh `color8`.
- `default_button_background`: `#444A58`, same neutral rendered shade.
- `toggle_button_background`: `#5294E2`, exact KvArcDark highlight.
- `progress_fill`: `#5294E2`, exact KvArcDark highlight.
- `progress_track`: `#2D303B`, dark rendered neutral between terminal
  background and neutral ramp.

Do not use:

- `reference/captures/arc__dark__blue__kvantum-preview__kvantum__buttons-normal__2026-05-27__001.png`

That capture accidentally grabbed Mousepad before Kvantum Preview was focused.

## Current Validation State

Latest verified command:

```bash
python -m unittest discover -s tests
```

Result: 12 tests passing.

JSON checked:

- `config/capture-plan.json`
- `config/roles.json`
- `samples/arc-dark-kvantum-buttons-normal-2026-05-27.json`

Note: `samples/sources/gogh-arc-dark.kitty.conf` is intentionally Kitty-style
source text, not JSON.

## Recommended Next Slice

Implement automated source correlation so the project can move away from manual
screen capture:

1. Add a reusable nearest-neighbor/correlation report that summarizes:
   - exact terminal matches
   - nearest weighted terminal roles
   - distance by role family
   - source fields matched by each GUI color
2. Apply it to Catppuccin and Arc Dark.
3. Promote a small list of generated GUI-role candidates from source-only data.
4. Use one Kvantum Preview capture only as render verification for each target
   theme.

Manual capture should now be limited to validating whether Kvantum renders the
expected source role, not discovering every role by hand.

## Open Caution

**Resolved (2026-06-01):** the stray root-level `assets/` directory (which held
`assets/icons/dolphin-modern-glass.png`) has been removed. Under the JangLabs
nested-repo-only policy, nothing but lab submodules may live at the workspace
root, so the directory was deleted. It was never part of the Arc Dark
source-correlation slice.
