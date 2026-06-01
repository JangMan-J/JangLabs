# Terminal Palette Role Significance

A terminal color scheme is a weighted evidence set, not a flat palette of equal
importance. For terminal-to-desktop mapping, role designation matters as much as
the color value.

## Core Model

Terminal schemes usually expose several different color classes:

- default display colors: `background`, `foreground`
- terminal interaction colors: `selection_background`,
  `selection_foreground`, `cursor`, and sometimes `cursor_text_color`
- ANSI/indexed color table: `color0` through `color15`, with normal and bright
  variants
- emulator-specific UI extras: tabs, marks, URLs, hints, search, bell, and
  window chrome colors

The first two groups are direct terminal UI roles. The ANSI table is a compact
API that terminal programs address by convention. A program emitting ANSI red is
asking for terminal slot red, not necessarily for the theme's most important red
design token.

## Role Weights

| Tier | Terminal roles | Mapping significance |
| --- | --- | --- |
| 1 | `background`, `foreground` | Strongest evidence for desktop base surface and primary text. These dominate ordinary terminal display. |
| 2 | `selection_background`, `selection_foreground`, `cursor`, `cursor_text_color` | Strong evidence for selected rows/text, insertion cursor, focus, and active affordances. Treat as terminal interaction roles, not ordinary ANSI colors. |
| 3 | `color0`, `color8`, `color7`, `color15` | Neutral ramp evidence. Often more useful for GUI surfaces, borders, disabled text, secondary text, and contrast than their ANSI names imply. |
| 4 | `color1`, `color2`, `color3` and bright pairs | High-confidence semantic status evidence: error/destructive, success/addition, warning/attention. |
| 5 | `color4`, `color5`, `color6` and bright pairs | Medium-confidence accents: links, headings, prompts, paths, info, special syntax, and navigation. Interpret per theme. |
| 6 | unused or duplicated bright variants | Weak evidence unless the theme family clearly uses bright slots as independent semantic tokens. |

## ANSI Pair Families

Treat the 16 ANSI slots as eight families before treating them as independent
colors:

| Family | Normal | Bright | Common interpretation |
| --- | --- | --- | --- |
| black | `color0` | `color8` | dark neutral, muted text, disabled text, low-contrast surfaces |
| red | `color1` | `color9` | error, destructive, removed, failed |
| green | `color2` | `color10` | success, added, executable, OK state |
| yellow | `color3` | `color11` | warning, modified, attention |
| blue | `color4` | `color12` | links, directories, headings, primary prompt/accent |
| magenta | `color5` | `color13` | special syntax, branch/prompt identity, secondary accent |
| cyan | `color6` | `color14` | info, paths, symlinks, types, secondary accent |
| white | `color7` | `color15` | light neutral, secondary/primary foreground variants |

Bright colors may be true brighter variants, high-contrast fallbacks, duplicated
values, or extra palette slots. Do not assume `color9` through `color15` are
independent desktop roles unless captures or theme-family evidence support it.

## Design Implications

In a colorful terminal theme, the quiet dark and gray colors can be more
structurally important than the vivid hues. They carry the display field,
contrast ladder, inactive states, borders, and text hierarchy. The colorful ANSI
slots often define personality and status, but they usually occupy smaller GUI
regions.

For missing desktop neutrals such as Catppuccin `mantle`, `crust`, `surface0`,
and `overlay2`, extrapolate from:

- terminal `background`
- neutral ANSI slots `color0`, `color8`, `color7`, `color15`
- relative lightness and contrast relationships
- repeated GUI capture evidence

Do not derive missing desktop surfaces from the most colorful accent slots just
because those colors are visually distinctive.

## Application Evidence

Common terminal applications reinforce the weighted model:

- shells and prompts mostly use default foreground/background plus a small
  number of accent/status slots
- `ls`/`dircolors` maps file types and suffixes onto ANSI/status conventions
- git and many CLIs strongly load red/green/yellow for removal/addition/warning
- editors and TUIs may use ANSI fallback palettes, 256-color palettes, or
  truecolor themes, so the terminal scheme is strongest evidence for the host
  palette rather than proof that every TUI uses every slot equally
- tmux and ncurses-style apps are useful bridge cases because they map terminal
  palette entries onto status bars, panes, selected rows, alerts, and focused
  widgets

## Mapping Rule

Infer a structural ladder first, then semantic status colors, then optional
accent/decorative colors:

1. Map `background` and `foreground`.
2. Map selection and cursor behavior separately.
3. Build a neutral/surface/text ramp from `background`, `foreground`,
   `color0`, `color8`, `color7`, and `color15`.
4. Map red, green, and yellow families to status roles.
5. Consider blue, magenta, and cyan families for links, info, navigation,
   prompts, headings, and secondary accents.
6. Treat bright variants as family evidence unless proven independent.

This should guide UI probing: prioritize surfaces, text, disabled text, borders,
selection, focus, status affordances, and control states before treating every
ANSI hue as a candidate for broad desktop application.
