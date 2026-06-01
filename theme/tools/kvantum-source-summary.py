#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path


HEX_COLOR = re.compile(r"#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?")


def normalize_hex(value):
    return value.upper()


def parse_kvconfig_general_colors(path):
    colors = {}
    section = None
    with Path(path).open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1]
                continue
            if section != "GeneralColors" or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip()
            if HEX_COLOR.fullmatch(value):
                colors[key.strip()] = normalize_hex(value)
    return colors


def parse_svg_colors(path):
    text = Path(path).read_text(encoding="utf-8")
    return sorted({normalize_hex(match.group(0)) for match in HEX_COLOR.finditer(text)})


def build_summary(
    config_path,
    svg_path,
    family="catppuccin",
    base="mocha",
    accent="sapphire",
    source_name=None,
):
    return {
        "schema_version": 1,
        "theme": {
            "family": family,
            "base": base,
            "accent": accent,
            "surface": "kvantum-preview",
            "app": "kvantum",
        },
        "general_colors": parse_kvconfig_general_colors(config_path),
        "svg_colors": parse_svg_colors(svg_path),
        "metadata": {
            "source": source_name or Path(config_path).stem,
            "source_format": "kvantum",
            "config": str(Path(config_path).expanduser()),
            "svg": str(Path(svg_path).expanduser()),
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
        description="Summarize Kvantum source colors from a .kvconfig and SVG asset."
    )
    parser.add_argument("config_path", type=Path, help="Kvantum .kvconfig file")
    parser.add_argument("svg_path", type=Path, help="Kvantum SVG asset file")
    parser.add_argument("--family", default="catppuccin", help="Theme family metadata")
    parser.add_argument("--base", default="mocha", help="Theme base metadata")
    parser.add_argument("--accent", default="sapphire", help="Theme accent metadata")
    parser.add_argument("--source-name", help="Stable source label to store in metadata")
    parser.add_argument("--json", dest="json_path", type=Path, help="Optional JSON output path")
    args = parser.parse_args()

    output = build_summary(
        args.config_path,
        args.svg_path,
        family=args.family,
        base=args.base,
        accent=args.accent,
        source_name=args.source_name,
    )

    if args.json_path:
        write_json(args.json_path, output)

    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
