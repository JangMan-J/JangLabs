# Arc Dark Source/Render Correlation

Arc Dark confirms why exact matching is too strict for a general
terminal-to-Kvantum mapper. The important KvArcDark desktop surfaces are mostly
near the Gogh terminal neutral ramp, not exact terminal colors.

## Source-Only Crosswalk

Command:

```bash
tools/source-color-crosswalk.py samples/sources/gogh-arc-dark.kitty.conf /usr/share/color-schemes/KvArcDark.colors /usr/share/Kvantum/KvArcDark/KvArcDark.kvconfig /usr/share/Kvantum/KvArcDark/KvArcDark.svg --family arc --base dark --accent blue --json derived/arc-dark-gogh-to-kvarcdark.crosswalk.json
```

Important source relationships:

| KvArcDark color | Role | Nearest Gogh terminal role | Interpretation |
| --- | --- | --- | --- |
| `#383C4A` | `GeneralColors.window.color` | `color8` `#3B4D68`, distance 34.612 | Window/chrome surface is extrapolated from bright black/neutral, not terminal background. |
| `#404552` | `GeneralColors.base.color` | `color8` `#3B4D68`, distance 23.937 | Main view surface strongly tracks neutral ramp. |
| `#3C434F` | `GeneralColors.alt.base.color` | `color8` `#3B4D68`, distance 26.944 | Alternate surface tracks neutral ramp. |
| `#414654` | `GeneralColors.button.color` | `color8` `#3B4D68`, distance 22.023 | Button surface tracks neutral ramp. |
| `#5294E2` | `GeneralColors.highlight.color` | `color12` `#3063D9`, distance 60.316 | Accent/highlight is a desktop blue extrapolation, not an exact ANSI blue. |
| `#009DFF` | `GeneralColors.link.color` | `color6` `#24BAC3`, distance 75.743 | Link color is related to cyan/blue family but source-specific. |

Only `color15` (`#FFFFFF`) is an exact normal terminal-role match for broad
KDE/Kvantum text sources. This makes Arc Dark a useful counterweight to
Catppuccin: exact terminal matches are sparse, but weighted role correlation is
still strong.

## Rendered Kvantum Preview Check

> Archival note: this was a one-time render verification of the source
> correlation above. The capture, point map, and sampled output were removed
> when the manual-screenshot methodology was retired; the conclusions below are
> retained because they are confirmed by the source crosswalk. Render
> verification now happens through the deterministic-canvas Gate 2 path in
> `tools/theme-research.py`.

Reliable rendered samples (from the original buttons-normal capture):

| UI role | Sampled color | Source match | Nearest Gogh terminal role | Interpretation |
| --- | --- | --- | --- | --- |
| `view_background` | `#404552` | `GeneralColors.base.color` | `color8` `#3B4D68`, distance 23.937 | Main rendered surface validates neutral-ramp extrapolation. |
| `button_background` | `#444A58` | SVG/widget rendered shade near button colors | `color8` `#3B4D68`, distance 18.601 | Button rendering uses a nearby neutral surface shade. |
| `default_button_background` | `#444A58` | SVG/widget rendered shade near button colors | `color8` `#3B4D68`, distance 18.601 | Default button is neutral here, not accent. |
| `toggle_button_background` | `#5294E2` | `GeneralColors.highlight.color` | `color12` `#3063D9`, distance 60.316 | Toggled state uses Kvantum highlight/accent. |
| `progress_fill` | `#5294E2` | `GeneralColors.highlight.color` | `color12` `#3063D9`, distance 60.316 | Progress fill uses the same accent/highlight. |
| `progress_track` | `#2D303B` | SVG inventory | `color8` `#3B4D68`, distance 55.335; `background` `#0D1117`, distance 57.28 | Track is a rendered dark neutral between background and neutral ramp. |

Some text point samples landed on antialiased or background pixels. Do not use
those as text evidence; source files already establish text-color behavior
well enough for this slice.

## Mapping Consequence

For Arc Dark, the mapper should not ask whether GUI surfaces exactly match the
terminal background. They do not. It should infer:

- base desktop surfaces from the terminal neutral ramp, especially `color8`
- deeper tracks/borders from interpolation between terminal background and the
  neutral ramp
- active/toggled/progress surfaces from the blue accent family, not exact ANSI
  blue

This is enough evidence to reduce manual testing. The next implementation slice
should automate source correlation and nearest-neighbor scoring, then use one
or two screenshots only to verify that Kvantum renders the expected source
roles.
