#!/usr/bin/env python3
import argparse
import configparser
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


HEX_COLOR = re.compile(r"#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?")
KITTY_COLOR_LINE = re.compile(r"^([A-Za-z0-9_]+)\s+(#[0-9A-Fa-f]{6})\b")
RGB_VALUE = re.compile(r"^\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*$")
TERMINAL_PALETTE_ROLES = [
    "background",
    "foreground",
    "selection_background",
    "selection_foreground",
    "cursor",
    "color0",
    "color1",
    "color2",
    "color3",
    "color4",
    "color5",
    "color6",
    "color7",
    "color8",
    "color9",
    "color10",
    "color11",
    "color12",
    "color13",
    "color14",
    "color15",
]
REFERENCE_GUI_PALETTES = {
    "mocha": {
        "rosewater": "#F5E0DC",
        "flamingo": "#F2CDCD",
        "pink": "#F5C2E7",
        "mauve": "#CBA6F7",
        "red": "#F38BA8",
        "maroon": "#EBA0AC",
        "peach": "#FAB387",
        "yellow": "#F9E2AF",
        "green": "#A6E3A1",
        "teal": "#94E2D5",
        "sky": "#89DCEB",
        "sapphire": "#74C7EC",
        "blue": "#89B4FA",
        "lavender": "#B4BEFE",
        "text": "#CDD6F4",
        "subtext1": "#BAC2DE",
        "subtext0": "#A6ADC8",
        "overlay2": "#9399B2",
        "overlay1": "#7F849C",
        "overlay0": "#6C7086",
        "surface2": "#585B70",
        "surface1": "#45475A",
        "surface0": "#313244",
        "base": "#1E1E2E",
        "mantle": "#181825",
        "crust": "#11111B",
    }
}


def normalize_hex(value):
    return value.upper()


def base_hex(value):
    return normalize_hex(value[:7])


def hex_to_rgb(value):
    color = base_hex(value).lstrip("#")
    return tuple(int(color[index : index + 2], 16) for index in (0, 2, 4))


def color_distance(left, right):
    return round(
        sum(
            (left_channel - right_channel) ** 2
            for left_channel, right_channel in zip(hex_to_rgb(left), hex_to_rgb(right))
        )
        ** 0.5,
        3,
    )


def rgb_to_hex(value):
    match = RGB_VALUE.match(value)
    if not match:
        return None
    channels = [int(part) for part in match.groups()]
    if any(channel < 0 or channel > 255 for channel in channels):
        return None
    return "#{:02X}{:02X}{:02X}".format(*channels)


def parse_kitty(path):
    colors = {}
    with Path(path).open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            match = KITTY_COLOR_LINE.match(line)
            if match:
                colors[match.group(1)] = normalize_hex(match.group(2))
    return colors


def read_ini(path):
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    parser.read(path, encoding="utf-8")
    return parser


def parse_kde_colors(path):
    colors = {}
    parser = read_ini(path)
    for section in parser.sections():
        for key, value in parser.items(section):
            color = rgb_to_hex(value)
            if color:
                colors[f"{section}.{key}"] = color
    return colors


def parse_kvconfig(path):
    colors = {}
    parser = read_ini(path)
    for section in parser.sections():
        for key, value in parser.items(section):
            matches = HEX_COLOR.findall(value)
            if matches:
                colors[f"{section}.{key}"] = [normalize_hex(match) for match in matches]
    return colors


def parse_svg(path):
    text = Path(path).read_text(encoding="utf-8")
    colors = defaultdict(int)
    for match in HEX_COLOR.finditer(text):
        colors[normalize_hex(match.group(0))] += 1
    return dict(sorted(colors.items()))


def add_match(index, color, source, field, value):
    indexed = base_hex(color)
    index[indexed].append(
        {
            "source": source,
            "field": field,
            "value": normalize_hex(value),
        }
    )


def build_target_index(kde_colors, kvconfig_colors, svg_colors):
    index = defaultdict(list)
    for field, color in kde_colors.items():
        add_match(index, color, "kde_colors", field, color)
    for field, values in kvconfig_colors.items():
        for value in values:
            add_match(index, value, "kvantum_config", field, value)
    for color, count in svg_colors.items():
        indexed = base_hex(color)
        index[indexed].append(
            {
                "source": "kvantum_svg",
                "field": "color_inventory",
                "value": normalize_hex(color),
                "count": count,
            }
        )
    return index


def build_reverse_terminal_index(terminal_colors):
    reverse = defaultdict(list)
    for role, color in terminal_colors.items():
        reverse[base_hex(color)].append(role)
    return reverse


def nearest_terminal_matches(color, terminal_colors, limit=3):
    matches = [
        {
            "role": role,
            "hex": hex_value,
            "distance": color_distance(color, hex_value),
        }
        for role, hex_value in terminal_colors.items()
    ]
    return sorted(matches, key=lambda item: (item["distance"], item["role"]))[:limit]


def build_reverse_reference_palette_index(family, base):
    if family != "catppuccin":
        return {}
    palette = REFERENCE_GUI_PALETTES.get(base, {})
    reverse = defaultdict(list)
    for name, color in palette.items():
        reverse[base_hex(color)].append(name)
    return reverse


def classify_target_color(color, terminal_index, reference_palette_index, accent):
    if color in terminal_index:
        return "terminal_direct"
    palette_roles = reference_palette_index.get(color, [])
    if accent in palette_roles:
        return "accent_axis"
    if palette_roles:
        return "reference_gui_palette"
    return "derived_or_artifact"


def build_crosswalk(
    kitty_path,
    kde_colors_path,
    kvconfig_path,
    svg_path,
    family="catppuccin",
    base="mocha",
    accent="sapphire",
):
    kitty_colors = parse_kitty(kitty_path)
    kde_colors = parse_kde_colors(kde_colors_path)
    kvconfig_colors = parse_kvconfig(kvconfig_path)
    svg_colors = parse_svg(svg_path)

    terminal_colors = {
        role: kitty_colors[role] for role in TERMINAL_PALETTE_ROLES if role in kitty_colors
    }
    extra_kitty_colors = {
        role: color
        for role, color in kitty_colors.items()
        if role not in TERMINAL_PALETTE_ROLES
    }

    target_index = build_target_index(kde_colors, kvconfig_colors, svg_colors)
    terminal_index = build_reverse_terminal_index(terminal_colors)
    reference_palette_index = build_reverse_reference_palette_index(family, base)

    terminal_roles = []
    for role in TERMINAL_PALETTE_ROLES:
        if role not in terminal_colors:
            continue
        color = terminal_colors[role]
        terminal_roles.append(
            {
                "role": role,
                "hex": color,
                "target_matches": target_index.get(base_hex(color), []),
            }
        )

    target_only = []
    for color, matches in sorted(target_index.items()):
        if color not in terminal_index:
            target_only.append(
                {
                    "hex": color,
                    "classification": classify_target_color(
                        color, terminal_index, reference_palette_index, accent
                    ),
                    "reference_palette_roles": reference_palette_index.get(color, []),
                    "nearest_terminal_roles": nearest_terminal_matches(color, terminal_colors),
                    "extra_kitty_roles": [
                        role
                        for role, value in sorted(extra_kitty_colors.items())
                        if base_hex(value) == color
                    ],
                    "target_matches": matches,
                }
            )

    return {
        "schema_version": 1,
        "theme": {
            "family": family,
            "base": base,
            "accent": accent,
        },
        "terminal_roles": terminal_roles,
        "extra_kitty_colors": [
            {
                "role": role,
                "hex": color,
                "target_matches": target_index.get(base_hex(color), []),
            }
            for role, color in sorted(extra_kitty_colors.items())
        ],
        "target_only_colors": target_only,
        "metadata": {
            "kitty_source": str(Path(kitty_path).expanduser()),
            "kde_colors_source": str(Path(kde_colors_path).expanduser()),
            "kvantum_config_source": str(Path(kvconfig_path).expanduser()),
            "kvantum_svg_source": str(Path(svg_path).expanduser()),
            "source_scope": "terminal_roles excludes Kitty UI extras such as tabs, borders, marks, and URL colors",
            "matching": "exact RGB matches, with 8-digit hex matched by RGB base",
            "target_only_classifications": [
                "reference_gui_palette",
                "accent_axis",
                "derived_or_artifact",
            ],
            "reference_palette_scope": "Catppuccin GUI palettes are calibration evidence, not a required input for generic terminal schemes",
        },
    }


def write_json(path, output):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(output, handle, indent=2)
        handle.write("\n")


def main():
    parser = argparse.ArgumentParser(
        description="Map Kitty terminal theme colors to KDE/Kvantum source fields."
    )
    parser.add_argument("kitty_path", type=Path, help="Kitty theme .conf file")
    parser.add_argument("kde_colors_path", type=Path, help="KDE .colors file")
    parser.add_argument("kvconfig_path", type=Path, help="Kvantum .kvconfig file")
    parser.add_argument("svg_path", type=Path, help="Kvantum SVG file")
    parser.add_argument("--family", default="catppuccin")
    parser.add_argument("--base", default="mocha")
    parser.add_argument("--accent", default="sapphire")
    parser.add_argument("--json", dest="json_path", type=Path)
    args = parser.parse_args()

    output = build_crosswalk(
        args.kitty_path,
        args.kde_colors_path,
        args.kvconfig_path,
        args.svg_path,
        family=args.family,
        base=args.base,
        accent=args.accent,
    )
    if args.json_path:
        write_json(args.json_path, output)
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
