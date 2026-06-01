# Source Color Crosswalk

The lab's final translation target is terminal/TUI color scheme input to GUI
theme config output. The terminal palette is narrower than Catppuccin's full GUI
palette, so the crosswalk must distinguish:

- colors present in the terminal palette and therefore directly available
- colors present only in Kitty UI extras such as tab, border, mark, or URL fields
- colors present in KDE/Kvantum targets but absent from terminal palette input

Generated inspection report:

- Tool: `tools/source-color-crosswalk.py`
- Local output: `derived/catppuccin-mocha-kitty-to-kde-kvantum.crosswalk.json`
- Kitty source: `~/.config/kitty/themes/Catppuccin-Mocha.conf`
- KDE source: `~/.local/share/color-schemes/CatppuccinMochaSapphire.colors`
- Kvantum source: `~/.config/Kvantum/catppuccin-mocha-sapphire/catppuccin-mocha-sapphire.kvconfig`
- Kvantum SVG: `~/.config/Kvantum/catppuccin-mocha-sapphire/catppuccin-mocha-sapphire.svg`

The tool treats only these as terminal palette input:

- `background`, `foreground`, `selection_background`, `selection_foreground`,
  `cursor`, and `color0` through `color15`

Kitty-specific fields such as `active_tab_background`, `inactive_tab_background`,
`mark3_background`, and `url_color` are reported separately and should not make a
GUI color count as translatable from a normal terminal palette.

## Directly Available Terminal Colors

These terminal colors have exact RGB matches in KDE and/or Kvantum sources:

| Terminal role | Hex | Target evidence |
| --- | --- | --- |
| `background` | `#1E1E2E` | KDE view/tooltip active background; Kvantum `GeneralColors.window.color`; SVG inventory |
| `foreground` | `#CDD6F4` | KDE normal foreground; many Kvantum text roles; SVG inventory |
| `selection_foreground` | `#1E1E2E` | Same target matches as `background` |
| `color0` | `#45475A` | Kvantum light/mid-light/inactive-highlight; SVG inventory |
| `color1`, `color9` | `#F38BA8` | KDE negative foreground; SVG inventory |
| `color2`, `color10` | `#A6E3A1` | KDE positive foreground |
| `color3`, `color11` | `#F9E2AF` | KDE neutral foreground |
| `color8` | `#585B70` | Kvantum disabled text; SVG inventory |
| `color15` | `#A6ADC8` | KDE inactive foreground and inactive window blend; SVG inventory |

These are viable direct terminal-to-GUI source mappings.

## Terminal Colors Without Exact GUI Source Matches

These terminal palette colors did not have exact KDE/Kvantum source matches in
the Catppuccin Mocha Sapphire sources inspected:

- `selection_background`: `#F5E0DC`
- `cursor`: `#F5E0DC`
- `color4`, `color12`: `#89B4FA`
- `color5`, `color13`: `#F5C2E7`
- `color6`, `color14`: `#94E2D5`
- `color7`: `#BAC2DE`

They may still be useful for terminal-specific output, but they are not current
evidence for KDE/Kvantum GUI fields.

## Target Colors Missing From Terminal Palette

These important KDE/Kvantum target colors are absent from the terminal palette.
The crosswalk now classifies them by whether they are recoverable from the
Catppuccin Mocha GUI reference palette, require an explicit GUI accent axis, or
look derived/artifact-like. This is calibration evidence from Catppuccin's
published TUI and GUI themes, not a requirement that generic terminal schemes
provide a separate canonical palette.

| Target color | Classification | Reference role | Meaning in KDE/Kvantum sources | Notes |
| --- | --- | --- | --- | --- |
| `#181825` | `reference_gui_palette` | `mantle` | KDE window/header/complementary backgrounds; Kvantum base/dark/mid colors | Appears only as Kitty `inactive_tab_background`, not terminal palette |
| `#11111B` | `reference_gui_palette` | `crust` | KDE alternate/background and selection foreground fields | Appears only in Kitty tab UI fields |
| `#313244` | `reference_gui_palette` | `surface0` | KDE button background and decoration hover; Kvantum button color; SVG inventory | Absent from terminal palette |
| `#74C7EC` | `accent_axis` | `sapphire` | KDE focus/link/selection/accent fields; Kvantum link/highlight and many SVG assets | Absent from terminal palette, though Kitty has non-palette `mark3_background` with this value |
| `#FAB387` | `reference_gui_palette` | `peach` | KDE active foreground fields | Absent from terminal palette |
| `#9399B2` | `reference_gui_palette` | `overlay2` | Kvantum normal tab text | Absent from terminal palette |
| `#86CAEE` | `derived_or_artifact` | none | Kvantum visited link | Derived/variant Sapphire; absent from terminal palette |

Conclusion: a translator from terminal palette alone can preserve many text,
semantic status, disabled, and primary background mappings, but it cannot
reconstruct every field of the full KDE/Kvantum Catppuccin config from the
terminal palette alone. Catppuccin is useful because the same design source has
published terminal and desktop themes, so it shows how a terminal color scheme
might naturally project into desktop roles. For generic terminal schemes, the
terminal palette itself is usually the available palette; inferred desktop roles
should be learned from this calibration evidence and validated with captures,
not filled from a hidden canonical lookup. GUI accent still remains a separate
axis, and derived values such as `#86CAEE` need either source-specific rules or
explicit target evidence.

## High-Value Target Fields

These source fields matter most for user-visible mapping and are the priority
outputs for the correlation model:

- `GeneralColors.window.color` / KDE `Colors:View.BackgroundNormal` ->
  main content background
- `GeneralColors.base.color` -> alternate/panel/list background
- `GeneralColors.button.color` -> button background
- `GeneralColors.text.color` and `button.text.color` -> primary text
- `GeneralColors.disabled.text.color` -> disabled text
- KDE/Kvantum focus/link/accent fields -> mark as GUI-only or palette-lookup
  dependent, not terminal-palette direct

## Color Relationship Taxonomy

Every candidate mapping from a terminal source color to a GUI target field is
classified by relationship strength. This taxonomy is the shared vocabulary used
across the crosswalk tool, the correlation scoring, and the fingerprint model:

- `terminal_direct`: the target color exactly matches a normal terminal role.
  Strongest evidence; safe to map directly.
- `terminal_near_neighbor`: the target color is close to a terminal role and
  reads as a desktop extrapolation of it (e.g. KvArcDark surfaces near Gogh
  `color8`). The general case for surfaces; score by weighted nearest-neighbor
  distance, not exact match.
- `reference_gui_palette`: the target color matches a published GUI reference
  palette for the family (e.g. Catppuccin `mantle`/`surface0`) but is absent
  from normal terminal roles. Only available when the family ships a GUI palette;
  not assumable for generic terminal schemes.
- `accent_axis`: the target color follows a runtime GUI accent selection (KDE
  `AccentColor`), not the terminal palette. Must be modeled as a separate input,
  never derived from the terminal scheme. Confirmed for Kvantum focus rings,
  selection, and slider/progress fills, which track KDE accent in both
  directions.
- `derived_or_artifact`: the target color appears produced by blending,
  antialiasing, shadows, or widget rendering (e.g. a path-bar inset shade, a
  visited-link variant). Useful mainly to avoid false direct mappings.

The mapper should never derive a missing desktop surface from the most colorful
accent slot just because it is visually distinctive; prefer the neutral ramp and
the relationships above. See `findings/terminal-palette-role-significance.md` for
the role weighting these relationships build on, and
`findings/arc-dark-source-render-correlation.md` for a worked non-Catppuccin
example where exact matches are sparse but weighted correlation is strong.
