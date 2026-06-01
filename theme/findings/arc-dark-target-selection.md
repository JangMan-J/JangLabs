# Arc Dark Target Selection

Arc Dark is the next cross-theme validation target.

## Why Arc Dark

- Gogh includes `Arc Dark` as a dark terminal color scheme.
- Kvantum includes `KvArcDark` with a real widget-engine source set:
  `KvArcDark.kvconfig`, `KvArcDark.svg`, and `KvArcDark.colors`.
- The Kvantum source is not just a Plasma `.colors` file; it defines widget
  elements, button assets, slider/progress assets, scrollbars, tabs, menus, and
  rendered control states.

This makes Arc Dark a better generalization test than Solarized for the current
lab. Solarized has usable KDE/terminal evidence, but no credible standalone
Solarized Kvantum source was found.

## Source Leads

Terminal source:

- Gogh page: `Arc Dark`
- Observed Gogh ANSI colors:
  - `#0D1117`, `#C32424`, `#24C391`, `#C3A924`
  - `#2455C3`, `#C224C3`, `#24BAC3`, `#E8ECF2`
  - `#3B4D68`, `#D93030`, `#30D9A4`, `#D9BD30`
  - `#3063D9`, `#D930D9`, `#30D1D9`, `#FFFFFF`

Kvantum source:

- `KvArcDark.kvconfig`
- `KvArcDark.svg`
- `KvArcDark.colors`
- Known source location from public mirror:
  `bin/themes/kvantum/KvArcDark/`

Important Kvantum colors observed in `KvArcDark.kvconfig`:

- `window.color`: `#383c4a`
- `base.color`: `#404552`
- `alt.base.color`: `#3c434f`
- `button.color`: `#414654`
- `highlight.color`: `#5294e2`
- `text.color`: `#ffffffc8`
- `disabled.text.color`: `#ffffff73`
- `link.color`: `#009DFF`
- `link.visited.color`: `#9E4FFF`

## Expected Test Value

Arc Dark should test whether the mapper can generalize beyond Catppuccin:

- terminal `background`/neutral slots are much darker than Kvantum's main
  desktop surfaces, so near-neighbor/extrapolated surface logic matters
- Kvantum's main surface ramp uses several close blue-gray values
- text and disabled text use alpha-bearing white values, so comparison needs to
  account for RGBA source values and rendered RGB samples
- `highlight.color` and link colors are related to, but not identical to, Gogh
  ANSI blue/cyan values

## Initial Capture Slice

1. Build or fetch Arc Dark terminal source into the same expected-mapping format
   used for Kitty/Catppuccin.
2. Fetch/install `KvArcDark.kvconfig`, `KvArcDark.svg`, and `KvArcDark.colors`.
3. Run the source crosswalk against terminal, KDE color scheme, Kvantum config,
   and SVG inventory.
4. Capture Kvantum Preview for:
   - `buttons-normal`
   - `buttons-hover`
   - `buttons-pressed`
   - `inputs-focused`
   - `sliders-scrolls-progress-dial`
5. Capture Dolphin with the selected `KvArcDark` theme using the existing shared
   file-manager point map.

The first question is correlation strength: whether Arc Dark's terminal
background/neutral ramp predicts Kvantum's desktop surface ramp better than its
colorful ANSI accent slots do.
