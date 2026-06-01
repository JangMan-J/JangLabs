#!/usr/bin/env python3
import argparse
import configparser
import hashlib
import html
import json
import math
import re
import sys
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path


TOOL_VERSION = "theme-research-v1"
DEFAULT_FIXTURE_CONFIG = Path(__file__).resolve().parents[1] / "config" / "theme-fingerprint-fixtures.json"
HEX_COLOR = re.compile(r"#[0-9A-Fa-f]{3}(?:[0-9A-Fa-f]{3})?(?:[0-9A-Fa-f]{2})?\b")
KITTY_COLOR_LINE = re.compile(r"^([A-Za-z0-9_]+)\s+(#[0-9A-Fa-f]{3}(?:[0-9A-Fa-f]{3})?(?:[0-9A-Fa-f]{2})?)\b")
CSS_NAMED_COLORS = {
    "black": "#000000",
    "white": "#FFFFFF",
    "transparent": "#00000000",
}
TERMINAL_ROLES = [
    "background",
    "foreground",
    "selection_background",
    "selection_foreground",
    "cursor",
    "cursor_text_color",
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
GOGH_COLOR_MAP = {
    f"color_{index:02d}": f"color{index - 1}" for index in range(1, 17)
}
KVANTUM_CORE_FIELDS = [
    "window.color",
    "base.color",
    "alt.base.color",
    "button.color",
    "light.color",
    "mid.light.color",
    "dark.color",
    "mid.color",
    "highlight.color",
    "inactive.highlight.color",
    "text.color",
    "window.text.color",
    "button.text.color",
    "disabled.text.color",
    "tooltip.text.color",
    "highlight.text.color",
    "link.color",
    "link.visited.color",
    "progress.indicator.text.color",
]


def read_bytes(path):
    return Path(path).expanduser().read_bytes()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha256_canonical(value):
    return sha256_bytes(canonical_json(value))


def slugify(value):
    slug = []
    previous_dash = False
    for character in value.casefold():
        if character.isalnum():
            slug.append(character)
            previous_dash = False
        elif not previous_dash:
            slug.append("-")
            previous_dash = True
    return "".join(slug).strip("-") or "theme"


def normalize_hex(value):
    if value is None:
        return None
    text = value.strip()
    named = CSS_NAMED_COLORS.get(text.casefold())
    if named:
        return named
    if not text.startswith("#"):
        return None
    digits = text[1:]
    if len(digits) == 3:
        digits = "".join(character * 2 for character in digits)
    if len(digits) not in (6, 8):
        return None
    if not re.fullmatch(r"[0-9A-Fa-f]+", digits):
        return None
    return "#" + digits.upper()


def rgb_tuple(color):
    normalized = normalize_hex(color)
    if not normalized:
        raise ValueError(f"invalid color {color!r}")
    digits = normalized[1:7]
    return tuple(int(digits[index : index + 2], 16) for index in (0, 2, 4))


def rgba_tuple(color):
    normalized = normalize_hex(color)
    rgb = rgb_tuple(normalized)
    alpha = int(normalized[7:9], 16) if len(normalized) == 9 else 255
    return rgb + (alpha,)


def rgb_hex(rgb):
    return "#{:02X}{:02X}{:02X}".format(*[max(0, min(255, int(round(channel)))) for channel in rgb])


def composite_color(foreground, background):
    foreground = normalize_hex(foreground)
    background = normalize_hex(background)
    if not foreground:
        raise ValueError("missing foreground color")
    if len(foreground) == 7:
        return foreground
    fg_red, fg_green, fg_blue, alpha = rgba_tuple(foreground)
    bg_red, bg_green, bg_blue = rgb_tuple(background or "#000000")
    weight = alpha / 255
    return rgb_hex(
        (
            fg_red * weight + bg_red * (1 - weight),
            fg_green * weight + bg_green * (1 - weight),
            fg_blue * weight + bg_blue * (1 - weight),
        )
    )


def css_color(color):
    normalized = normalize_hex(color)
    if len(normalized) == 7:
        return normalized
    red, green, blue, alpha = rgba_tuple(normalized)
    return f"rgba({red}, {green}, {blue}, {alpha / 255:.3f})"


def luminance(color):
    def channel(value):
        value = value / 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = rgb_tuple(color)
    return 0.2126 * channel(red) + 0.7152 * channel(green) + 0.0722 * channel(blue)


def contrast(left, right):
    left_luminance = luminance(left)
    right_luminance = luminance(right)
    low, high = sorted((left_luminance, right_luminance))
    return round((high + 0.05) / (low + 0.05), 3)


def hue_bucket(color):
    red, green, blue = [channel / 255 for channel in rgb_tuple(color)]
    maximum = max(red, green, blue)
    minimum = min(red, green, blue)
    delta = maximum - minimum
    if delta < 0.06:
        return "neutral"
    if maximum == red:
        hue = (60 * ((green - blue) / delta) + 360) % 360
    elif maximum == green:
        hue = 60 * ((blue - red) / delta + 2)
    else:
        hue = 60 * ((red - green) / delta + 4)
    if hue < 30 or hue >= 330:
        return "red"
    if hue < 75:
        return "yellow"
    if hue < 165:
        return "green"
    if hue < 200:
        return "cyan"
    if hue < 260:
        return "blue"
    if hue < 330:
        return "magenta"
    return "neutral"


def bucket(value, cuts):
    for label, low, high in cuts:
        if low <= value < high:
            return label
    return cuts[-1][0]


def parse_kitty_theme_text(text):
    colors = {}
    extras = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = KITTY_COLOR_LINE.match(line)
        if not match:
            continue
        key = match.group(1)
        color = normalize_hex(match.group(2))
        if not color:
            continue
        if key in TERMINAL_ROLES:
            colors[key] = color
        else:
            extras[key] = color
    return colors, extras


def parse_kvconfig(path):
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    parser.read(Path(path).expanduser(), encoding="utf-8")
    colors = {}
    if not parser.has_section("GeneralColors"):
        return colors
    for key, value in parser.items("GeneralColors"):
        color = normalize_hex(value)
        if color:
            colors[f"GeneralColors.{key}"] = color
    return colors


def parse_svg_colors(path):
    path = Path(path).expanduser()
    if not path.exists():
        return {}
    colors = defaultdict(int)
    text = path.read_text(encoding="utf-8", errors="replace")
    for match in HEX_COLOR.finditer(text):
        color = normalize_hex(match.group(0))
        if color:
            colors[color] += 1
    return dict(sorted(colors.items()))


def make_index_row(adapter, backend, display_name, source_uri, source_files, record, metadata=None):
    normalized_record = json.loads(json.dumps(record, sort_keys=True))
    record_hash = sha256_canonical(normalized_record)
    source_file_hash = sha256_canonical(
        [{"path": item["path"], "sha256": item["sha256"]} for item in source_files]
    )
    return {
        "schema_version": 1,
        "adapter": adapter,
        "backend": backend,
        "display_name": display_name,
        "slug": slugify(display_name),
        "source_uri": source_uri,
        "source_file_hash": source_file_hash,
        "source_files": source_files,
        "record_hash": record_hash,
        "record": normalized_record,
        "metadata": metadata or {},
    }


def index_kitty_path(path):
    path = Path(path).expanduser()
    rows = []
    if path.is_file() and zipfile.is_zipfile(path):
        archive_hash = sha256_bytes(path.read_bytes())
        with zipfile.ZipFile(path) as archive:
            names = sorted(
                name for name in archive.namelist() if name.endswith(".conf") and "/themes/" in name
            )
            for name in names:
                data = archive.read(name)
                colors, extras = parse_kitty_theme_text(data.decode("utf-8", errors="replace"))
                if not colors:
                    continue
                display_name = Path(name).stem.replace("_", " ")
                source_files = [
                    {
                        "path": str(path),
                        "member": name,
                        "sha256": sha256_bytes(data),
                    }
                ]
                rows.append(
                    make_index_row(
                        "kitty_conf",
                        "tui",
                        display_name,
                        f"zip://{path}#{name}",
                        source_files,
                        {"colors": colors, "extras": extras},
                        {"archive_sha256": archive_hash},
                    )
                )
        return rows

    paths = [path] if path.is_file() else sorted(path.rglob("*.conf"))
    for theme_path in paths:
        data = theme_path.read_bytes()
        colors, extras = parse_kitty_theme_text(data.decode("utf-8", errors="replace"))
        if not colors:
            continue
        display_name = theme_path.stem.replace("_", " ")
        rows.append(
            make_index_row(
                "kitty_conf",
                "tui",
                display_name,
                str(theme_path),
                [{"path": str(theme_path), "sha256": sha256_bytes(data)}],
                {"colors": colors, "extras": extras},
            )
        )
    return rows


def index_gogh_json(path):
    path = Path(path).expanduser()
    data = path.read_bytes()
    source_hash = sha256_bytes(data)
    table = json.loads(data.decode("utf-8"))
    rows = []
    for index, item in enumerate(table):
        colors = {}
        for source_field, terminal_role in GOGH_COLOR_MAP.items():
            color = normalize_hex(item.get(source_field, ""))
            if color:
                colors[terminal_role] = color
        for key in ("background", "foreground", "cursor"):
            color = normalize_hex(item.get(key, ""))
            if color:
                colors[key] = color
        display_name = item.get("name") or f"gogh-{index}"
        rows.append(
            make_index_row(
                "gogh_json",
                "tui",
                display_name,
                f"{path}#{index}",
                [{"path": str(path), "sha256": source_hash}],
                {
                    "colors": colors,
                    "source_fields": {
                        key: value
                        for key, value in item.items()
                        if key.startswith("color_") or key in ("background", "foreground", "cursor")
                    },
                },
                {
                    "source_table_hash": source_hash,
                    "table_index": index,
                    "variant": item.get("variant", ""),
                    "author": item.get("author", ""),
                },
            )
        )
    return rows


def find_kvantum_pairs(path, names=None):
    root = Path(path).expanduser()
    selected = set(names or [])
    pairs = []
    if root.is_file() and root.suffix == ".kvconfig":
        svg = root.with_suffix(".svg")
        return [(root, svg if svg.exists() else None)]
    for config_path in sorted(root.rglob("*.kvconfig")):
        theme_name = config_path.stem
        if selected and theme_name not in selected and config_path.parent.name not in selected:
            continue
        svg_path = config_path.with_suffix(".svg")
        if not svg_path.exists():
            parent_svg = config_path.parent / f"{theme_name}.svg"
            svg_path = parent_svg if parent_svg.exists() else None
        pairs.append((config_path, svg_path))
    return pairs


def index_kvantum_path(path, names=None):
    rows = []
    for config_path, svg_path in find_kvantum_pairs(path, names=names):
        source_files = [
            {"path": str(config_path), "sha256": sha256_bytes(config_path.read_bytes())}
        ]
        if svg_path:
            source_files.append({"path": str(svg_path), "sha256": sha256_bytes(svg_path.read_bytes())})
        colors = parse_kvconfig(config_path)
        svg_colors = parse_svg_colors(svg_path) if svg_path else {}
        display_name = config_path.stem
        rows.append(
            make_index_row(
                "kvantum_config",
                "kvantum",
                display_name,
                str(config_path),
                source_files,
                {
                    "general_colors": colors,
                    "svg_colors": svg_colors,
                },
                {
                    "svg": str(svg_path) if svg_path else None,
                    "theme_dir": str(config_path.parent),
                },
            )
        )
    return rows


def load_fixture_config(path=DEFAULT_FIXTURE_CONFIG):
    path = Path(path).expanduser()
    data = json.loads(path.read_text(encoding="utf-8"))
    data["_config_path"] = str(path)
    data["_config_hash"] = sha256_bytes(path.read_bytes())
    return data


def source_colors_for_row(row):
    if row["backend"] == "tui":
        return row["record"].get("colors", {})
    if row["backend"] == "kvantum":
        return row["record"].get("general_colors", {})
    raise ValueError(f"unsupported backend {row['backend']!r}")


def fallback_map_for_backend(config, backend):
    if backend == "tui":
        return config.get("terminal_fallbacks", {})
    if backend == "kvantum":
        return config.get("kvantum_fallbacks", {})
    return {}


def resolve_ref(color_ref, row, config, stack=None):
    colors = source_colors_for_row(row)
    stack = stack or []
    if color_ref in colors:
        return {
            "color": colors[color_ref],
            "requested_ref": color_ref,
            "resolved_ref": color_ref,
            "evidence_class": "authored_theme_value",
            "resolution_path": stack + [color_ref],
        }
    fallbacks = fallback_map_for_backend(config, row["backend"]).get(color_ref, [])
    for fallback_ref in fallbacks:
        if fallback_ref in stack:
            continue
        resolved = resolve_ref(fallback_ref, row, config, stack + [color_ref])
        if resolved.get("color"):
            resolved = dict(resolved)
            resolved["requested_ref"] = color_ref
            resolved["resolution_path"] = stack + [color_ref] + resolved["resolution_path"]
            return resolved
    return {
        "color": "#000000",
        "requested_ref": color_ref,
        "resolved_ref": None,
        "evidence_class": "unresolved_default",
        "resolution_path": stack + [color_ref],
    }


def element_area(element):
    return round(
        float(element["width"]) * float(element["height"]) * float(element.get("area_scale", 1.0)),
        3,
    )


def resolve_element(definition, row, config, canvas_background):
    color = resolve_ref(definition["color_ref"], row, config)
    background_ref = definition.get("background_ref")
    background = resolve_ref(background_ref, row, config) if background_ref else canvas_background
    display_color = composite_color(color["color"], background["display_color"] if "display_color" in background else background["color"])
    return {
        "id": definition["id"],
        "kind": definition.get("kind", "rect"),
        "placement": definition["placement"],
        "x": definition["x"],
        "y": definition["y"],
        "width": definition["width"],
        "height": definition["height"],
        "area": element_area(definition),
        "text": definition.get("text", ""),
        "source": color,
        "background_source": background,
        "source_color": color["color"],
        "display_color": display_color,
        "css_color": css_color(color["color"]),
        "include_in_identity_fingerprint": True,
        "include_in_field_correlation": color["evidence_class"] == "authored_theme_value",
    }


def resolve_pair(definition, row, config):
    foreground = resolve_ref(definition["foreground_ref"], row, config)
    background = resolve_ref(definition["background_ref"], row, config)
    foreground_display = composite_color(foreground["color"], background["color"])
    background_display = composite_color(background["color"], "#000000")
    return {
        "id": definition["id"],
        "placement": definition["placement"],
        "weight": definition["weight"],
        "foreground_source": foreground,
        "background_source": background,
        "foreground_color": foreground["color"],
        "background_color": background["color"],
        "foreground_display_color": foreground_display,
        "background_display_color": background_display,
        "contrast": contrast(foreground_display, background_display),
        "include_in_identity_fingerprint": True,
        "include_in_field_correlation": (
            foreground["evidence_class"] == "authored_theme_value"
            and background["evidence_class"] == "authored_theme_value"
        ),
    }


def rect_element(element_id, placement, x, y, width, height, color_ref, background_ref=None, area_scale=None):
    element = {
        "id": element_id,
        "kind": "rect",
        "placement": placement,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "color_ref": color_ref,
    }
    if background_ref:
        element["background_ref"] = background_ref
    if area_scale is not None:
        element["area_scale"] = area_scale
    return element


def text_element(element_id, placement, x, y, width, height, color_ref, background_ref, text, area_scale=0.22):
    return {
        "id": element_id,
        "kind": "text",
        "placement": placement,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "color_ref": color_ref,
        "background_ref": background_ref,
        "text": text,
        "area_scale": area_scale,
    }


FASTFETCH_LOGO = [
    "   .+====================.",
    "  :++===++==============-",
    " :++===+++=============-",
    "-*++===--++++++++=====:",
    "=*+++=======---------:",
    "-**++=-----",
    ".+*+++===::          .=++=:",
    " :+++=====-:          -*****+",
    ":++======-.           .=+**+",
    "+==========-.             --=-",
    ":++++++====-           -==",
    "  :++=========.       -++++++",
    "    .-==========:    -*******+",
    "      -===========: .+*******:",
    "       .-============+++++++-",
    "          -===========+++-",
]
FASTFETCH_FACTS = [
    ("OS", "CachyOS x86_64", "color6"),
    ("Host", "ROG Strix SCAR 18 G834JYR", "color6"),
    ("Kernel", "Linux 7.0.10", "color6"),
    ("Uptime", "7 hours, 55 mins", "color6"),
    ("Packages", "11 (brew), 10 (flatpak), 1789 (pacman)", "color6"),
    ("Shell", "fish 4.7.1", "color6"),
    ("Display", "2560x1600 @ 240 Hz", "color6"),
    ("DE", "KDE Plasma 6.6.5", "color6"),
    ("WM", "KWin (Wayland)", "color6"),
    ("Theme", "MateriaDark [Qt], Breeze-Dark [GTK2]", "color6"),
    ("Icons", "WhiteSur-orange-dark", "color6"),
    ("Font", "Fira Sans (14pt), MonaspaceAr NF", "color6"),
    ("Cursor", "breeze (24px)", "color6"),
    ("Terminal", "kitty 0.46.2", "color6"),
    ("Terminal Font", "MonaspaceArNFM-Regular (11pt)", "color6"),
    ("CPU", "Intel Core i9-14900HX (32) @ 5.80 GHz", "color6"),
    ("GPU 1", "NVIDIA GeForce RTX 4090 Laptop", "color6"),
    ("GPU 2", "Intel Raptor Lake-S UHD Graphics", "color6"),
    ("Memory", "8.95 GiB / 30.95 GiB (29%)", "color6"),
    ("Swap", "427.28 MiB / 30.95 GiB (1%)", "color6"),
    ("Disk (/)", "197.29 GiB / 1.86 TiB (10%) - btrfs", "color6"),
    ("Local IP", "192.168.0.123/24", "color6"),
    ("Battery", "91% [AC Connected]", "color6"),
    ("Locale", "en_US.UTF-8", "color6"),
]


def generated_fastfetch_tui_scene():
    width = 1500
    height = 840
    elements = [
        rect_element("terminal_background", "dominant_surface", 0, 0, width, height, "background"),
        rect_element("window_frame", "border_separator", 70, 58, 1360, 706, "color8", "background", area_scale=0.3),
        rect_element("titlebar", "secondary_surface", 72, 60, 1356, 44, "color0", "background"),
        text_element("window_title", "primary_text", 708, 69, 90, 24, "foreground", "color0", "~ - fish", 0.2),
    ]
    left_x = 124
    top_y = 132
    char_w = 10
    line_h = 22
    logo_roles = ["color6", "color14", "color6", "color2", "color6", "color14"]
    for row_index, line in enumerate(FASTFETCH_LOGO):
        x = left_x
        for segment_index, segment in enumerate(re.findall(r" +|[^ ]+", line)):
            segment_width = max(1, len(segment) * char_w)
            if segment.strip():
                role = logo_roles[(row_index + segment_index) % len(logo_roles)]
                elements.append(
                    text_element(
                        f"fastfetch_logo_{row_index}_{segment_index}",
                        "accent_candidate",
                        x,
                        top_y + row_index * line_h,
                        segment_width,
                        line_h,
                        role,
                        "background",
                        segment,
                        0.28,
                    )
                )
            x += segment_width
    facts_x = 650
    for index, (label, value, label_role) in enumerate(FASTFETCH_FACTS):
        y = 135 + index * 23
        elements.append(
            text_element(
                f"fastfetch_label_{index}",
                "link_info",
                facts_x,
                y,
                max(70, len(label) * 10),
                21,
                label_role,
                "background",
                label + ":",
                0.24,
            )
        )
        value_role = "foreground"
        if any(token in value for token in ("29%", "1%", "10%", "91%")):
            value_role = "color2"
        elements.append(
            text_element(
                f"fastfetch_value_{index}",
                "secondary_text",
                facts_x + 96,
                y,
                min(680, max(120, len(value) * 10)),
                21,
                value_role,
                "background",
                value,
                0.21,
            )
        )
    swatch_roles = [f"color{index}" for index in range(8)] + [f"color{index}" for index in range(8, 16)]
    swatch_x = facts_x
    swatch_y = 688
    swatch_w = 30
    swatch_h = 22
    for index, role in enumerate(swatch_roles):
        row = index // 8
        col = index % 8
        elements.append(
            rect_element(
                f"fastfetch_swatch_{index}",
                "accent_candidate" if index not in (0, 7, 8, 15) else "secondary_surface",
                swatch_x + col * swatch_w,
                swatch_y + row * swatch_h,
                swatch_w,
                swatch_h,
                role,
                "background",
            )
        )
    elements.extend(
        [
            text_element("prompt_path", "link_info", 84, 716, 16, 22, "color4", "background", "~", 0.24),
            text_element("prompt_symbol", "accent_candidate", 84, 744, 16, 22, "color5", "background", "❯", 0.24),
            rect_element("prompt_cursor", "focus_indicator", 108, 746, 3, 20, "cursor", "background"),
        ]
    )
    return {
        "width": width,
        "height": height,
        "canvas_background": "background",
        "font_family": "MonaspaceAr NF, Fira Code, monospace",
        "elements": elements,
        "pairs": [
            {"id": "primary_on_background", "placement": "primary_text", "foreground_ref": "foreground", "background_ref": "background", "weight": 16},
            {"id": "fastfetch_labels", "placement": "link_info", "foreground_ref": "color6", "background_ref": "background", "weight": 12},
            {"id": "logo_cyan", "placement": "accent_candidate", "foreground_ref": "color6", "background_ref": "background", "weight": 10},
            {"id": "logo_green", "placement": "status_success", "foreground_ref": "color2", "background_ref": "background", "weight": 5},
            {"id": "muted_text", "placement": "muted_text", "foreground_ref": "color8", "background_ref": "background", "weight": 6},
            {"id": "prompt_accent", "placement": "accent_candidate", "foreground_ref": "color5", "background_ref": "background", "weight": 3},
        ],
    }


KVANTUM_WIDGET_TABS = [
    ("Push buttons", ["Button Box", "Simple push button", "Toggle push button", "Default push button", "Flat buttons", "Push button with menu", "Multi-line push button"]),
    ("Tool buttons", ["Simple toolbutton", "Auto-raise", "Text under icon", "Menu button popup", "Toggle toolbutton", "Arrow button", "Icon beside text"]),
    ("Radio/Check buttons", ["Simple radio button", "Multi-line radio button", "Radio with icon", "Simple check box", "Tri-state check box", "Check box with icon"]),
    ("Combos/Spins/Inputs", ["Standard combo box", "Frameless combo", "Editable combo box", "Line-edit", "Spin box", "Date-time edit"]),
    ("Sliders/Scrolls/Progress/Dial", ["Vertical slider", "Horizontal slider", "Scroll bar", "Progress bar", "Busy indicator", "Dial"]),
    ("Containers", ["Tree view", "List view", "Table widget", "Tab widget", "Tool box", "Dock widget", "Group box", "Subwindow"]),
]


def widget_card(elements, prefix, x, y, width, height, title, control_kind, selected=False, disabled=False):
    bg = "GeneralColors.alt.base.color" if selected else "GeneralColors.base.color"
    elements.append(rect_element(f"{prefix}_card", "secondary_surface", x, y, width, height, bg, "GeneralColors.window.color"))
    elements.append(rect_element(f"{prefix}_topline", "border_separator", x, y, width, 2, "GeneralColors.light.color", bg))
    text_role = "GeneralColors.disabled.text.color" if disabled else "GeneralColors.text.color"
    elements.append(text_element(f"{prefix}_title", "primary_text", x + 14, y + 10, width - 28, 20, text_role, bg, title, 0.2))
    control_y = y + 42
    if control_kind == "button":
        fill = "GeneralColors.mid.color" if disabled else "GeneralColors.button.color"
        elements.append(rect_element(f"{prefix}_button", "control_disabled" if disabled else "control_fill", x + 14, control_y, 112, 30, fill, bg))
        elements.append(text_element(f"{prefix}_button_text", "muted_text" if disabled else "primary_text", x + 32, control_y + 6, 76, 18, "GeneralColors.disabled.text.color" if disabled else "GeneralColors.button.text.color", fill, "Action", 0.22))
    elif control_kind == "toggle":
        fill = "GeneralColors.highlight.color" if selected else "GeneralColors.button.color"
        elements.append(rect_element(f"{prefix}_toggle", "control_pressed" if selected else "control_fill", x + 14, control_y, 126, 30, fill, bg))
        elements.append(text_element(f"{prefix}_toggle_text", "selection_text" if selected else "primary_text", x + 32, control_y + 6, 86, 18, "GeneralColors.highlight.text.color" if selected else "GeneralColors.button.text.color", fill, "Enabled" if selected else "Toggle", 0.22))
    elif control_kind == "check":
        box_color = "GeneralColors.highlight.color" if selected else "GeneralColors.window.color"
        elements.append(rect_element(f"{prefix}_check_box", "selection_fill" if selected else "control_fill", x + 16, control_y + 4, 18, 18, box_color, bg))
        elements.append(text_element(f"{prefix}_check_text", "primary_text", x + 44, control_y + 2, width - 60, 20, text_role, bg, "Checked option" if selected else "Option", 0.2))
    elif control_kind == "input":
        elements.append(rect_element(f"{prefix}_input", "control_fill", x + 14, control_y, width - 28, 30, "GeneralColors.window.color", bg))
        elements.append(rect_element(f"{prefix}_input_line", "border_separator", x + 14, control_y, width - 28, 2, "GeneralColors.light.color", "GeneralColors.window.color"))
        elements.append(text_element(f"{prefix}_input_text", "secondary_text", x + 26, control_y + 6, width - 52, 18, text_role, "GeneralColors.window.color", "Editable value", 0.2))
    elif control_kind == "slider":
        elements.append(rect_element(f"{prefix}_track", "control_fill", x + 18, control_y + 13, width - 52, 8, "GeneralColors.mid.color", bg))
        elements.append(rect_element(f"{prefix}_fill", "accent_candidate", x + 18, control_y + 13, int((width - 52) * 0.58), 8, "GeneralColors.highlight.color", "GeneralColors.mid.color"))
        elements.append(rect_element(f"{prefix}_knob", "control_hover", x + int((width - 52) * 0.58), control_y + 7, 18, 20, "GeneralColors.light.color", bg))
    elif control_kind == "progress":
        elements.append(rect_element(f"{prefix}_progress_track", "control_fill", x + 14, control_y, width - 28, 24, "GeneralColors.mid.color", bg))
        elements.append(rect_element(f"{prefix}_progress_fill", "accent_candidate", x + 14, control_y, int((width - 28) * 0.62), 24, "GeneralColors.highlight.color", "GeneralColors.mid.color"))
        elements.append(text_element(f"{prefix}_progress_text", "selection_text", x + width // 2 - 18, control_y + 4, 40, 16, "GeneralColors.progress.indicator.text.color", "GeneralColors.highlight.color", "62%", 0.2))
    elif control_kind == "list":
        for row in range(3):
            row_y = control_y + row * 24
            row_fill = "GeneralColors.highlight.color" if row == 1 and selected else ("GeneralColors.window.color" if row % 2 == 0 else "GeneralColors.alt.base.color")
            elements.append(rect_element(f"{prefix}_row_{row}", "selection_fill" if row == 1 and selected else "secondary_surface", x + 14, row_y, width - 28, 22, row_fill, bg))
            elements.append(text_element(f"{prefix}_row_text_{row}", "selection_text" if row == 1 and selected else "secondary_text", x + 24, row_y + 2, width - 48, 16, "GeneralColors.highlight.text.color" if row == 1 and selected else text_role, row_fill, f"Item {row + 1}", 0.19))


def generated_kvantum_preview_scene():
    width = 1500
    height = 980
    elements = [
        rect_element("preview_window", "dominant_surface", 0, 0, width, height, "GeneralColors.window.color"),
        rect_element("menubar", "elevated_surface", 0, 0, width, 32, "GeneralColors.button.color", "GeneralColors.window.color"),
        text_element("menu_file", "primary_text", 18, 7, 42, 18, "GeneralColors.button.text.color", "GeneralColors.button.color", "&File", 0.2),
        text_element("menu_sub", "primary_text", 78, 7, 82, 18, "GeneralColors.button.text.color", "GeneralColors.button.color", "&Submenu", 0.2),
        rect_element("toolbar_1", "control_fill", 0, 32, width, 48, "GeneralColors.window.color", "GeneralColors.button.color"),
        rect_element("toolbar_button_1", "control_fill", 18, 42, 92, 28, "GeneralColors.button.color", "GeneralColors.window.color"),
        rect_element("toolbar_button_2", "control_pressed", 120, 42, 112, 28, "GeneralColors.highlight.color", "GeneralColors.window.color"),
        text_element("toolbar_text_1", "primary_text", 38, 47, 48, 18, "GeneralColors.button.text.color", "GeneralColors.button.color", "Open", 0.2),
        text_element("toolbar_text_2", "selection_text", 142, 47, 70, 18, "GeneralColors.highlight.text.color", "GeneralColors.highlight.color", "Doc Mode", 0.2),
        rect_element("tab_bar", "secondary_surface", 0, 80, width, 42, "GeneralColors.base.color", "GeneralColors.window.color"),
    ]
    tab_width = width // len(KVANTUM_WIDGET_TABS)
    for index, (name, _) in enumerate(KVANTUM_WIDGET_TABS):
        tab_x = index * tab_width
        active = index == 0
        elements.append(rect_element(f"tab_{index}", "control_pressed" if active else "control_fill", tab_x + 2, 86, tab_width - 4, 32, "GeneralColors.alt.base.color" if active else "GeneralColors.button.color", "GeneralColors.base.color"))
        elements.append(text_element(f"tab_text_{index}", "primary_text", tab_x + 16, 93, tab_width - 32, 16, "GeneralColors.text.color", "GeneralColors.alt.base.color" if active else "GeneralColors.button.color", name, 0.18))
    area_y = 138
    card_w = 210
    card_h = 106
    gap = 20
    control_cycle = ["button", "toggle", "check", "input", "slider", "progress", "list"]
    card_index = 0
    for group_index, (group_name, widgets) in enumerate(KVANTUM_WIDGET_TABS):
        group_x = 28 + (group_index % 2) * 724
        group_y = area_y + (group_index // 2) * 260
        elements.append(rect_element(f"group_{group_index}", "elevated_surface", group_x, group_y, 696, 238, "GeneralColors.base.color", "GeneralColors.window.color"))
        elements.append(text_element(f"group_title_{group_index}", "primary_text", group_x + 18, group_y + 12, 300, 22, "GeneralColors.text.color", "GeneralColors.base.color", group_name, 0.2))
        for widget_index, widget_name in enumerate(widgets[:6]):
            col = widget_index % 3
            row = widget_index // 3
            x = group_x + 18 + col * (card_w + gap)
            y = group_y + 44 + row * 88
            control = control_cycle[(card_index + widget_index) % len(control_cycle)]
            widget_card(
                elements,
                f"widget_{group_index}_{widget_index}",
                x,
                y,
                card_w,
                76,
                widget_name,
                control,
                selected=(widget_index + group_index) % 3 == 1,
                disabled=(widget_index + group_index) % 7 == 3,
            )
        card_index += len(widgets)
    elements.extend(
        [
            rect_element("dock_widget", "secondary_surface", 980, 720, 450, 176, "GeneralColors.alt.base.color", "GeneralColors.window.color"),
            text_element("dock_title", "primary_text", 1002, 738, 110, 20, "GeneralColors.text.color", "GeneralColors.alt.base.color", "Dock Widget", 0.2),
            rect_element("tooltip_shadow", "border_separator", 1040, 778, 230, 76, "GeneralColors.dark.color", "GeneralColors.window.color", 0.35),
            rect_element("tooltip_body", "elevated_surface", 1032, 770, 230, 76, "GeneralColors.dark.color", "GeneralColors.window.color"),
            text_element("tooltip_text", "primary_text", 1054, 796, 150, 20, "GeneralColors.tooltip.text.color", "GeneralColors.dark.color", "Tooltip preview", 0.22),
            text_element("link_text", "link_info", 1002, 862, 180, 18, "GeneralColors.link.color", "GeneralColors.alt.base.color", "https://kde.org", 0.2),
            text_element("visited_text", "link_info", 1202, 862, 130, 18, "GeneralColors.link.visited.color", "GeneralColors.alt.base.color", "visited link", 0.2),
        ]
    )
    return {
        "width": width,
        "height": height,
        "canvas_background": "GeneralColors.window.color",
        "font_family": "Fira Sans, Inter, Arial, sans-serif",
        "model_source": {
            "name": "KvantumPreviewBase.ui",
            "url": "https://raw.githubusercontent.com/tsujan/Kvantum/master/Kvantum/kvantumpreview/KvantumPreviewBase.ui",
            "description": "Widget categories mirrored from upstream kvantumpreview UI.",
        },
        "elements": elements,
        "pairs": [
            {"id": "text_on_base", "placement": "primary_text", "foreground_ref": "GeneralColors.text.color", "background_ref": "GeneralColors.base.color", "weight": 20},
            {"id": "window_text_on_window", "placement": "primary_text", "foreground_ref": "GeneralColors.window.text.color", "background_ref": "GeneralColors.window.color", "weight": 10},
            {"id": "button_text_on_button", "placement": "primary_text", "foreground_ref": "GeneralColors.button.text.color", "background_ref": "GeneralColors.button.color", "weight": 18},
            {"id": "disabled_text_on_mid", "placement": "muted_text", "foreground_ref": "GeneralColors.disabled.text.color", "background_ref": "GeneralColors.mid.color", "weight": 8},
            {"id": "highlight_pair", "placement": "selection_text", "foreground_ref": "GeneralColors.highlight.text.color", "background_ref": "GeneralColors.highlight.color", "weight": 14},
            {"id": "link_pair", "placement": "link_info", "foreground_ref": "GeneralColors.link.color", "background_ref": "GeneralColors.base.color", "weight": 5},
            {"id": "visited_link_pair", "placement": "link_info", "foreground_ref": "GeneralColors.link.visited.color", "background_ref": "GeneralColors.base.color", "weight": 4},
            {"id": "tooltip_pair", "placement": "primary_text", "foreground_ref": "GeneralColors.tooltip.text.color", "background_ref": "GeneralColors.dark.color", "weight": 5},
            {"id": "progress_pair", "placement": "selection_text", "foreground_ref": "GeneralColors.progress.indicator.text.color", "background_ref": "GeneralColors.highlight.color", "weight": 6},
        ],
    }


def scene_for_backend(config, backend):
    configured = config["scenes"][backend]
    if backend == "tui" and configured.get("model") == "fastfetch":
        return generated_fastfetch_tui_scene()
    if backend == "kvantum" and configured.get("model") == "kvantumpreview":
        return generated_kvantum_preview_scene()
    return configured


def build_canvas(row, config):
    scene = scene_for_backend(config, row["backend"])
    canvas_background = resolve_ref(scene["canvas_background"], row, config)
    canvas_background["display_color"] = composite_color(canvas_background["color"], "#000000")
    elements = [
        resolve_element(definition, row, config, canvas_background)
        for definition in scene["elements"]
    ]
    pairs = [resolve_pair(definition, row, config) for definition in scene.get("pairs", [])]
    return {
        "schema_version": 1,
        "backend": row["backend"],
        "adapter": row["adapter"],
        "display_name": row["display_name"],
        "slug": row["slug"],
        "source": {
            "source_uri": row["source_uri"],
            "source_file_hash": row["source_file_hash"],
            "source_files": row["source_files"],
            "record_hash": row["record_hash"],
        },
        "versions": {
            "tool_version": TOOL_VERSION,
            "adapter_version": f"{row['adapter']}-v1",
            "canvas_schema_version": config["canvas_schema_version"],
            "fingerprint_schema_version": config["fingerprint_schema_version"],
            "preview_renderer_version": config["preview_renderer_version"],
            "fixture_config_hash": config["_config_hash"],
        },
        "width": scene["width"],
        "height": scene["height"],
        "font_family": scene.get("font_family", "sans-serif"),
        "background": canvas_background,
        "elements": elements,
        "pairs": pairs,
        "metadata": {
            **row.get("metadata", {}),
            **({"model_source": scene["model_source"]} if "model_source" in scene else {}),
        },
    }


def weighted_percent_map(values):
    total = sum(values.values()) or 1
    return {
        key: {
            "weight": round(weight, 3),
            "percent": round(weight / total, 6),
        }
        for key, weight in sorted(values.items(), key=lambda item: (-item[1], item[0]))
    }


def build_fingerprint(canvas):
    occupancy_by_color = defaultdict(float)
    occupancy_by_source_color = defaultdict(float)
    occupancy_by_placement = defaultdict(float)
    occupancy_by_hue = defaultdict(float)
    luminance_values = defaultdict(float)
    neutral_candidates = defaultdict(float)

    for element in canvas["elements"]:
        if not element.get("include_in_identity_fingerprint", True):
            continue
        area = float(element["area"])
        display_color = element["display_color"]
        occupancy_by_color[display_color] += area
        occupancy_by_source_color[element["source_color"]] += area
        occupancy_by_placement[element["placement"]] += area
        occupancy_by_hue[hue_bucket(display_color)] += area
        luminance_bucket = bucket(
            luminance(display_color),
            [
                ("0.0-0.2", 0.0, 0.2),
                ("0.2-0.4", 0.2, 0.4),
                ("0.4-0.6", 0.4, 0.6),
                ("0.6-0.8", 0.6, 0.8),
                ("0.8-1.0", 0.8, 1.01),
            ],
        )
        luminance_values[luminance_bucket] += area
        if hue_bucket(display_color) == "neutral":
            neutral_candidates[display_color] += area

    pair_weights = defaultdict(float)
    contrast_buckets = defaultdict(float)
    pair_details = []
    for pair in canvas["pairs"]:
        if not pair.get("include_in_identity_fingerprint", True):
            continue
        weight = float(pair["weight"])
        key = f"{pair['foreground_display_color']} on {pair['background_display_color']}"
        pair_weights[key] += weight
        contrast_buckets[
            bucket(
                pair["contrast"],
                [
                    ("0-3", 0, 3),
                    ("3-4.5", 3, 4.5),
                    ("4.5-7", 4.5, 7),
                    ("7-12", 7, 12),
                    ("12+", 12, 1000),
                ],
            )
        ] += weight
        pair_details.append(
            {
                "id": pair["id"],
                "placement": pair["placement"],
                "foreground": pair["foreground_display_color"],
                "background": pair["background_display_color"],
                "contrast": pair["contrast"],
                "weight": pair["weight"],
            }
        )

    neutral_ramp = [
        {
            "color": color,
            "luminance": round(luminance(color), 6),
            "weight": round(weight, 3),
        }
        for color, weight in sorted(neutral_candidates.items(), key=lambda item: luminance(item[0]))
    ]

    return {
        "schema_version": 1,
        "backend": canvas["backend"],
        "adapter": canvas["adapter"],
        "display_name": canvas["display_name"],
        "source": canvas["source"],
        "versions": canvas["versions"],
        "metrics": {
            "canvas_area": canvas["width"] * canvas["height"],
            "weighted_element_area": round(sum(element["area"] for element in canvas["elements"]), 3),
            "occupancy_by_display_color": weighted_percent_map(occupancy_by_color),
            "occupancy_by_source_color": weighted_percent_map(occupancy_by_source_color),
            "occupancy_by_placement": weighted_percent_map(occupancy_by_placement),
            "hue_cluster_stats": weighted_percent_map(occupancy_by_hue),
            "luminance_histogram": weighted_percent_map(luminance_values),
            "pair_frequency": weighted_percent_map(pair_weights),
            "contrast_histogram": weighted_percent_map(contrast_buckets),
            "neutral_ramp": neutral_ramp,
            "pair_details": pair_details,
        },
    }


def preview_html(canvas):
    elements = []
    for element in canvas["elements"]:
        left = element["x"]
        top = element["y"]
        width = element["width"]
        height = element["height"]
        style = [
            "position:absolute",
            f"left:{left}px",
            f"top:{top}px",
            f"width:{width}px",
            f"height:{height}px",
            "box-sizing:border-box",
        ]
        classes = ["element", element["kind"], element["placement"]]
        if element.get("kind") == "text":
            style.extend(
                [
                    f"color:{element['css_color']}",
                    "background:transparent",
                    f"font-size:{max(12, min(22, round(height * 0.72)))}px",
                    f"line-height:{height}px",
                    "white-space:nowrap",
                    "overflow:hidden",
                ]
            )
            content = html.escape(element.get("text") or "")
        else:
            style.append(f"background:{element['css_color']}")
            if element["placement"] in ("control_fill", "control_pressed", "control_disabled", "selection_fill"):
                style.append("border-radius:6px")
            elif element["placement"] in ("dominant_surface", "secondary_surface", "elevated_surface"):
                style.append("border-radius:4px")
            content = ""
        elements.append(
            f'<div class="{" ".join(classes)}" style="{";".join(style)}">{content}</div>'
        )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(canvas["display_name"])}</title>
<style>
  html, body {{
    margin: 0;
    min-height: 100%;
    background: #111;
  }}
  body {{
    display: grid;
    place-items: center;
    padding: 24px;
  }}
  .scene {{
    position: relative;
    width: {canvas["width"]}px;
    height: {canvas["height"]}px;
    overflow: hidden;
    font-family: {canvas["font_family"]};
    background: {css_color(canvas["background"]["color"])};
    box-shadow: 0 24px 70px rgba(0,0,0,.35);
  }}
  .text {{
    font-weight: 500;
    letter-spacing: 0;
  }}
</style>
</head>
<body>
  <div class="scene">
    {"".join(elements)}
  </div>
</body>
</html>
"""


def squared_distance(left, right):
    return sum(
        (left_channel - right_channel) ** 2
        for left_channel, right_channel in zip(rgb_tuple(left), rgb_tuple(right))
    )


def nearest_color(color, candidates):
    return min(candidates, key=lambda candidate: squared_distance(color, candidate))


def canvas_expected_occupancy(canvas):
    width = int(canvas["width"])
    height = int(canvas["height"])
    background = composite_color(canvas["background"]["color"], "#000000")
    pixels = [background] * (width * height)
    text_colors = set()
    for element in canvas["elements"]:
        if not element.get("include_in_identity_fingerprint", True):
            continue
        if element.get("kind") == "text":
            text_colors.add(element["display_color"])
            continue
        left = max(0, int(round(element["x"])))
        top = max(0, int(round(element["y"])))
        right = min(width, int(round(element["x"] + element["width"])))
        bottom = min(height, int(round(element["y"] + element["height"])))
        color = element["display_color"]
        for y in range(top, bottom):
            start = y * width + left
            end = y * width + right
            pixels[start:end] = [color] * max(0, end - start)

    weights = defaultdict(float)
    for color in pixels:
        weights[color] += 1
    for color in text_colors:
        weights.setdefault(color, 0)
    total = width * height or 1
    return {color: weight / total for color, weight in weights.items()}


def sample_png_occupancy(path, expected_colors, max_distance=18):
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Gate 2 image sampling requires Pillow") from exc

    expected = list(expected_colors)
    counts = defaultdict(int)
    unmatched = 0
    with Image.open(path) as image:
        image = image.convert("RGB")
        width, height = image.size
        pixels = image.load()
        for y in range(height):
            for x in range(width):
                color = rgb_hex(pixels[x, y])
                nearest = nearest_color(color, expected)
                if math.sqrt(squared_distance(color, nearest)) <= max_distance:
                    counts[nearest] += 1
                else:
                    unmatched += 1

    total = sum(counts.values()) + unmatched or 1
    sampled = {color: count / total for color, count in counts.items()}
    if unmatched:
        sampled["__unmatched__"] = unmatched / total
    return sampled


def compare_occupancy(expected, sampled):
    colors = set(expected) | {color for color in sampled if color != "__unmatched__"}
    overlap = sum(min(expected.get(color, 0), sampled.get(color, 0)) for color in colors)
    unmatched = sampled.get("__unmatched__", 0)
    return {
        "overlap": round(overlap, 6),
        "unmatched": round(unmatched, 6),
        "distance": round(1 - overlap, 6),
    }


def rasterize_preview_with_playwright(html_path, png_path, width, height):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Gate 2 rasterization requires optional Playwright: "
            "python -m pip install playwright && python -m playwright install chromium"
        ) from exc

    html_path = Path(html_path).resolve()
    png_path = Path(png_path).resolve()
    png_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": width + 48, "height": height + 48}, device_scale_factor=1)
        page.goto(html_path.as_uri())
        page.locator(".scene").screenshot(path=str(png_path))
        browser.close()
    return png_path


def validate_gate2(canvas_path, html_path, png_path=None, tolerance=0.9, max_distance=18):
    canvas = json.loads(Path(canvas_path).read_text(encoding="utf-8"))
    expected = canvas_expected_occupancy(canvas)
    cleanup = None
    if png_path is None:
        cleanup = tempfile.TemporaryDirectory()
        png_path = Path(cleanup.name) / "preview.png"
        rasterize_preview_with_playwright(html_path, png_path, canvas["width"], canvas["height"])
    else:
        png_path = Path(png_path)
        if not png_path.exists():
            rasterize_preview_with_playwright(html_path, png_path, canvas["width"], canvas["height"])
    sampled = sample_png_occupancy(png_path, expected, max_distance=max_distance)
    comparison = compare_occupancy(expected, sampled)
    passed = comparison["overlap"] >= tolerance
    output = {
        "schema_version": 1,
        "backend": canvas["backend"],
        "adapter": canvas["adapter"],
        "display_name": canvas["display_name"],
        "record_hash": canvas["source"]["record_hash"],
        "versions": canvas["versions"],
        "tolerance": tolerance,
        "max_distance": max_distance,
        "pass": passed,
        "comparison": comparison,
        "expected_occupancy": {
            color: round(percent, 6) for color, percent in sorted(expected.items(), key=lambda item: (-item[1], item[0]))
        },
        "sampled_occupancy": {
            color: round(percent, 6) for color, percent in sorted(sampled.items(), key=lambda item: (-item[1], item[0]))
        },
        "canvas": str(canvas_path),
        "html": str(html_path),
        "png": str(png_path) if cleanup is None else None,
    }
    if cleanup:
        cleanup.cleanup()
    return output


def write_json(path, output):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def read_jsonl(path):
    with Path(path).expanduser().open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def output_paths(base_dir, row, preview=False):
    base = Path(base_dir)
    record_hash = row["record_hash"]
    adapter = row["adapter"]
    prefix = record_hash[:12]
    slug = row["slug"]
    return {
        "canvas": base / "canvases" / adapter / f"{record_hash}.canvas.json",
        "fingerprint": base / "fingerprints" / adapter / f"{record_hash}.fingerprint.json",
        "preview": base / "previews" / adapter / f"{slug}-{prefix}.html" if preview else None,
    }


def build_outputs(rows, config, out_dir, preview=False, record_hashes=None, limit=None):
    selected_hashes = set(record_hashes or [])
    written = []
    count = 0
    for row in rows:
        if selected_hashes and row["record_hash"] not in selected_hashes:
            continue
        canvas = build_canvas(row, config)
        fingerprint = build_fingerprint(canvas)
        paths = output_paths(out_dir, row, preview=preview)
        write_json(paths["canvas"], canvas)
        write_json(paths["fingerprint"], fingerprint)
        preview_path = paths["preview"]
        if preview_path:
            preview_path.parent.mkdir(parents=True, exist_ok=True)
            preview_path.write_text(preview_html(canvas), encoding="utf-8")
        written.append(
            {
                "record_hash": row["record_hash"],
                "display_name": row["display_name"],
                "adapter": row["adapter"],
                "canvas": str(paths["canvas"]),
                "fingerprint": str(paths["fingerprint"]),
                "preview": str(preview_path) if preview_path else None,
            }
        )
        count += 1
        if limit and count >= limit:
            break
    return written


def record_gate1(path, canvas_path, result):
    canvas = json.loads(Path(canvas_path).read_text(encoding="utf-8"))
    path = Path(path)
    if path.exists():
        gate = json.loads(path.read_text(encoding="utf-8"))
    else:
        gate = {"schema_version": 1, "gate1": []}
    gate["gate1"].append(
        {
            "backend": canvas["backend"],
            "adapter": canvas["adapter"],
            "display_name": canvas["display_name"],
            "record_hash": canvas["source"]["record_hash"],
            "result": result,
            "versions": canvas["versions"],
            "canvas": str(Path(canvas_path)),
        }
    )
    write_json(path, gate)
    return gate


def gate1_status(path, fixture_config):
    gate = json.loads(Path(path).read_text(encoding="utf-8"))
    config_hash = fixture_config["_config_hash"]
    passed = [
        item
        for item in gate.get("gate1", [])
        if item.get("result") == "pass"
        and item.get("versions", {}).get("fixture_config_hash") == config_hash
    ]
    counts = defaultdict(int)
    for item in passed:
        counts[item["backend"]] += 1
    return {
        "schema_version": 1,
        "fixture_config_hash": config_hash,
        "passed_counts": dict(counts),
        "gate1_ready": all(counts.get(backend, 0) >= 3 for backend in ("tui", "kvantum")),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Import theme corpora, build deterministic virtual canvases, fingerprints, and optional previews."
    )
    parser.add_argument("--fixture-config", type=Path, default=DEFAULT_FIXTURE_CONFIG)
    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index", help="Import a source corpus into JSONL index rows")
    index_parser.add_argument("adapter", choices=("kitty", "gogh", "kvantum"))
    index_parser.add_argument("source", type=Path)
    index_parser.add_argument("--name", action="append", help="Kvantum theme name filter; may repeat")
    index_parser.add_argument("--jsonl", required=True, type=Path)

    build_parser = subparsers.add_parser("build", help="Build canvases/fingerprints from an index")
    build_parser.add_argument("index_jsonl", type=Path)
    build_parser.add_argument("--out-dir", type=Path, default=Path("derived/theme-research"))
    build_parser.add_argument("--record-hash", action="append")
    build_parser.add_argument("--limit", type=int)
    build_parser.add_argument("--preview", action="store_true")
    build_parser.add_argument("--json", dest="json_path", type=Path)

    preview_parser = subparsers.add_parser("preview", help="Render preview HTML from a saved canvas")
    preview_parser.add_argument("canvas", type=Path)
    preview_parser.add_argument("--html", required=True, type=Path)

    fingerprint_parser = subparsers.add_parser("fingerprint", help="Compute fingerprint JSON from a saved canvas")
    fingerprint_parser.add_argument("canvas", type=Path)
    fingerprint_parser.add_argument("--json", required=True, type=Path)

    gate_parser = subparsers.add_parser("record-gate1", help="Record manual Gate 1 preview acceptance")
    gate_parser.add_argument("canvas", type=Path)
    gate_parser.add_argument("--result", choices=("pass", "fail"), required=True)
    gate_parser.add_argument("--gate-json", type=Path, default=Path("derived/validation/theme-preview-gates.json"))

    gate_status_parser = subparsers.add_parser("gate1-status", help="Show Gate 1 readiness for current fixture config")
    gate_status_parser.add_argument("--gate-json", type=Path, default=Path("derived/validation/theme-preview-gates.json"))

    gate2_parser = subparsers.add_parser(
        "validate-gate2",
        help="Raster/sample one accepted preview and compare sampled occupancy to the virtual canvas",
    )
    gate2_parser.add_argument("canvas", type=Path)
    gate2_parser.add_argument("html", type=Path)
    gate2_parser.add_argument(
        "--png",
        type=Path,
        help="Scene PNG path. Existing files are sampled; missing files are created by rasterizing the HTML.",
    )
    gate2_parser.add_argument("--tolerance", type=float, default=0.9)
    gate2_parser.add_argument("--max-distance", type=float, default=18)
    gate2_parser.add_argument("--json", dest="json_path", type=Path)

    args = parser.parse_args()
    config = load_fixture_config(args.fixture_config)

    if args.command == "index":
        if args.adapter == "kitty":
            rows = index_kitty_path(args.source)
        elif args.adapter == "gogh":
            rows = index_gogh_json(args.source)
        else:
            rows = index_kvantum_path(args.source, names=args.name)
        write_jsonl(args.jsonl, rows)
        print(json.dumps({"rows": len(rows), "jsonl": str(args.jsonl)}, indent=2))
        return 0

    if args.command == "build":
        rows = list(read_jsonl(args.index_jsonl))
        output = build_outputs(
            rows,
            config,
            args.out_dir,
            preview=args.preview,
            record_hashes=args.record_hash,
            limit=args.limit,
        )
        if args.json_path:
            write_json(args.json_path, output)
        print(json.dumps(output, indent=2))
        return 0

    if args.command == "preview":
        canvas = json.loads(args.canvas.read_text(encoding="utf-8"))
        args.html.parent.mkdir(parents=True, exist_ok=True)
        args.html.write_text(preview_html(canvas), encoding="utf-8")
        print(json.dumps({"html": str(args.html)}, indent=2))
        return 0

    if args.command == "fingerprint":
        canvas = json.loads(args.canvas.read_text(encoding="utf-8"))
        output = build_fingerprint(canvas)
        write_json(args.json, output)
        print(json.dumps(output, indent=2))
        return 0

    if args.command == "record-gate1":
        output = record_gate1(args.gate_json, args.canvas, args.result)
        print(json.dumps(output, indent=2))
        return 0

    if args.command == "gate1-status":
        output = gate1_status(args.gate_json, config)
        print(json.dumps(output, indent=2))
        return 0

    if args.command == "validate-gate2":
        output = validate_gate2(
            args.canvas,
            args.html,
            png_path=args.png,
            tolerance=args.tolerance,
            max_distance=args.max_distance,
        )
        if args.json_path:
            write_json(args.json_path, output)
        print(json.dumps(output, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
