import importlib.util
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
import zipfile
from pathlib import Path


LAB_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = LAB_ROOT / "tools" / "theme-research.py"
FIXTURE_PATH = LAB_ROOT / "config" / "theme-fingerprint-fixtures.json"


def load_theme_research_module():
    spec = importlib.util.spec_from_file_location("theme_research", TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


theme_research = load_theme_research_module()


class ThemeResearchTest(unittest.TestCase):
    def test_kitty_index_accepts_alpha_short_hex_and_last_wins(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            archive_path = root / "kitty-themes.zip"
            theme_text = textwrap.dedent(
                """
                background #111111
                foreground #eeeeee
                cursor #eee
                selection_background #817c9c26
                selection_foreground #111111
                color0 #000000
                color1 #AA0000
                color2 #00AA00
                color3 #AAAA00
                color4 #0000AA
                color5 #AA00AA
                color6 #00AAAA
                color7 #AAAAAA
                color8 #555555
                color9 #FF5555
                color10 #55FF55
                color10 #66FF66
                color11 #FFFF55
                color12 #5555FF
                color13 #FF55FF
                color14 #55FFFF
                color15 #FFFFFF
                active_tab_background #333333
                """
            ).strip()
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("kitty-themes-master/themes/Test.conf", theme_text)

            rows = theme_research.index_kitty_path(archive_path)

            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["adapter"], "kitty_conf")
            self.assertEqual(row["backend"], "tui")
            self.assertEqual(row["record"]["colors"]["cursor"], "#EEEEEE")
            self.assertEqual(row["record"]["colors"]["selection_background"], "#817C9C26")
            self.assertEqual(row["record"]["colors"]["color10"], "#66FF66")
            self.assertEqual(row["record"]["extras"]["active_tab_background"], "#333333")
            self.assertIn("source_file_hash", row)
            self.assertIn("record_hash", row)

    def test_gogh_index_normalizes_ordered_slots_and_table_hash(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "themes.json"
            record = {
                "name": "Gogh Sample",
                "author": "",
                "variant": "Dark",
                "background": "#010203",
                "foreground": "#F0F1F2",
                "cursor": "#AABBCC",
                "hash": "0" * 64,
            }
            for index in range(1, 17):
                record[f"color_{index:02d}"] = f"#{index:02X}{index:02X}{index:02X}"
            path.write_text(json.dumps([record]), encoding="utf-8")

            rows = theme_research.index_gogh_json(path)

            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["adapter"], "gogh_json")
            self.assertEqual(row["record"]["colors"]["color0"], "#010101")
            self.assertEqual(row["record"]["colors"]["color15"], "#101010")
            self.assertEqual(row["record"]["colors"]["background"], "#010203")
            self.assertIn("source_table_hash", row["metadata"])
            self.assertEqual(row["source_files"][0]["sha256"], row["metadata"]["source_table_hash"])

    def test_kvantum_index_handles_named_colors_alpha_and_svg_inventory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            theme_dir = Path(temp_dir) / "KvSample"
            theme_dir.mkdir()
            config_path = theme_dir / "KvSample.kvconfig"
            svg_path = theme_dir / "KvSample.svg"
            config_path.write_text(
                textwrap.dedent(
                    """
                    [GeneralColors]
                    window.color=#383c4a
                    base.color=#404552
                    alt.base.color=#2E353D78
                    button.color=#414654
                    light.color=#5f677f
                    mid.light.color=#313131
                    dark.color=black
                    mid.color=#191919
                    highlight.color=#5294e2
                    inactive.highlight.color=#5294e2
                    text.color=#ffffffc8
                    window.text.color=#ffffffc8
                    button.text.color=#ffffffc8
                    disabled.text.color=#ffffff73
                    tooltip.text.color=#eefcff
                    highlight.text.color=white
                    link.color=#009DFF
                    link.visited.color=#9E4FFF
                    progress.indicator.text.color=white
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            svg_path.write_text('<svg><rect fill="#5294e2"/></svg>\n', encoding="utf-8")

            rows = theme_research.index_kvantum_path(Path(temp_dir), names=["KvSample"])

            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["adapter"], "kvantum_config")
            colors = row["record"]["general_colors"]
            self.assertEqual(colors["GeneralColors.dark.color"], "#000000")
            self.assertEqual(colors["GeneralColors.highlight.text.color"], "#FFFFFF")
            self.assertEqual(colors["GeneralColors.text.color"], "#FFFFFFC8")
            self.assertEqual(colors["GeneralColors.alt.base.color"], "#2E353D78")
            self.assertEqual(row["record"]["svg_colors"]["#5294E2"], 1)

    def test_build_canvas_fingerprint_and_preview_for_kvantum(self):
        config = theme_research.load_fixture_config(FIXTURE_PATH)
        row = theme_research.make_index_row(
            "kvantum_config",
            "kvantum",
            "KvSample",
            "memory://KvSample",
            [{"path": "KvSample.kvconfig", "sha256": "a" * 64}],
            {
                "general_colors": {
                    "GeneralColors.window.color": "#383C4A",
                    "GeneralColors.base.color": "#404552",
                    "GeneralColors.alt.base.color": "#3C434F",
                    "GeneralColors.button.color": "#414654",
                    "GeneralColors.light.color": "#5F677F",
                    "GeneralColors.mid.light.color": "#313131",
                    "GeneralColors.dark.color": "#000000",
                    "GeneralColors.mid.color": "#191919",
                    "GeneralColors.highlight.color": "#5294E2",
                    "GeneralColors.inactive.highlight.color": "#5294E2",
                    "GeneralColors.text.color": "#FFFFFFC8",
                    "GeneralColors.window.text.color": "#FFFFFFC8",
                    "GeneralColors.button.text.color": "#FFFFFFC8",
                    "GeneralColors.disabled.text.color": "#FFFFFF73",
                    "GeneralColors.tooltip.text.color": "#EEFCFF",
                    "GeneralColors.highlight.text.color": "#FFFFFF",
                    "GeneralColors.link.color": "#009DFF",
                    "GeneralColors.link.visited.color": "#9E4FFF",
                    "GeneralColors.progress.indicator.text.color": "#FFFFFF",
                },
                "svg_colors": {},
            },
        )

        canvas = theme_research.build_canvas(row, config)
        fingerprint = theme_research.build_fingerprint(canvas)
        preview = theme_research.preview_html(canvas)

        self.assertEqual(canvas["backend"], "kvantum")
        self.assertEqual(canvas["versions"]["fixture_config_hash"], config["_config_hash"])
        self.assertGreater(len(canvas["elements"]), 180)
        self.assertEqual(canvas["width"], 1500)
        self.assertIn("model_source", canvas["metadata"])
        self.assertEqual(canvas["metadata"]["model_source"]["name"], "KvantumPreviewBase.ui")
        self.assertIn("occupancy_by_display_color", fingerprint["metrics"])
        self.assertIn("pair_frequency", fingerprint["metrics"])
        self.assertIn("KvantumPreviewBase.ui", json.dumps(canvas["metadata"]))
        self.assertIn("Push buttons", preview)
        self.assertNotIn("source_file_hash", preview)

    def test_tui_canvas_uses_fastfetch_model(self):
        config = theme_research.load_fixture_config(FIXTURE_PATH)
        row = theme_research.make_index_row(
            "kitty_conf",
            "tui",
            "MaterialDark",
            "memory://MaterialDark",
            [{"path": "MaterialDark.conf", "sha256": "b" * 64}],
            {
                "colors": {
                    "background": "#222221",
                    "foreground": "#E4E4E4",
                    "cursor": "#16AEC9",
                    "selection_background": "#DEDEDE",
                    "selection_foreground": "#222221",
                    "color0": "#212121",
                    "color1": "#B7141E",
                    "color2": "#457B23",
                    "color3": "#F5971D",
                    "color4": "#134EB2",
                    "color5": "#550087",
                    "color6": "#0E707C",
                    "color7": "#EEEEEE",
                    "color8": "#424242",
                    "color9": "#E83A3F",
                    "color10": "#7ABA39",
                    "color11": "#FEE92E",
                    "color12": "#53A4F3",
                    "color13": "#A94DBB",
                    "color14": "#26BAD1",
                    "color15": "#D8D8D8",
                },
                "extras": {},
            },
        )

        canvas = theme_research.build_canvas(row, config)
        preview = theme_research.preview_html(canvas)

        self.assertEqual(canvas["backend"], "tui")
        self.assertGreater(len(canvas["elements"]), 90)
        self.assertEqual(canvas["width"], 1500)
        self.assertIn("CachyOS x86_64", preview)
        self.assertIn("Terminal", preview)

    def test_gate2_occupancy_comparison(self):
        expected = {"#000000": 0.6, "#FFFFFF": 0.4}
        sampled = {"#000000": 0.55, "#FFFFFF": 0.35, "__unmatched__": 0.1}

        comparison = theme_research.compare_occupancy(expected, sampled)

        self.assertEqual(comparison["overlap"], 0.9)
        self.assertEqual(comparison["unmatched"], 0.1)
        self.assertEqual(comparison["distance"], 0.1)

    def test_gate2_rasterizes_to_missing_png_path(self):
        calls = []

        def fake_rasterize(html_path, png_path, width, height):
            calls.append((html_path, png_path, width, height))
            Path(png_path).parent.mkdir(parents=True, exist_ok=True)
            Path(png_path).write_bytes(b"fake")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            canvas_path = root / "canvas.json"
            html_path = root / "preview.html"
            png_path = root / "preview.png"
            canvas_path.write_text(
                json.dumps(
                    {
                        "backend": "tui",
                        "adapter": "kitty_conf",
                        "display_name": "Sample",
                        "source": {"record_hash": "a" * 64},
                        "versions": {},
                        "width": 100,
                        "height": 100,
                        "background": {"color": "#000000"},
                        "elements": [
                            {
                                "display_color": "#000000",
                                "area": 100,
                                "x": 0,
                                "y": 0,
                                "width": 100,
                                "height": 100,
                                "include_in_identity_fingerprint": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            html_path.write_text("<html></html>", encoding="utf-8")

            original_rasterize = theme_research.rasterize_preview_with_playwright
            original_sample = theme_research.sample_png_occupancy
            try:
                theme_research.rasterize_preview_with_playwright = fake_rasterize
                theme_research.sample_png_occupancy = lambda path, expected, max_distance=18: {
                    "#000000": 1.0
                }

                output = theme_research.validate_gate2(canvas_path, html_path, png_path=png_path)
            finally:
                theme_research.rasterize_preview_with_playwright = original_rasterize
                theme_research.sample_png_occupancy = original_sample

            self.assertEqual(len(calls), 1)
            self.assertTrue(png_path.exists())
            self.assertTrue(output["pass"])

    def test_cli_indexes_builds_and_records_gate1(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            theme_path = root / "Simple.conf"
            theme_path.write_text(
                textwrap.dedent(
                    """
                    background #111111
                    foreground #eeeeee
                    cursor #eeeeee
                    selection_background #333333
                    selection_foreground #eeeeee
                    color0 #000000
                    color1 #AA0000
                    color2 #00AA00
                    color3 #AAAA00
                    color4 #0000AA
                    color5 #AA00AA
                    color6 #00AAAA
                    color7 #AAAAAA
                    color8 #555555
                    color9 #FF5555
                    color10 #55FF55
                    color11 #FFFF55
                    color12 #5555FF
                    color13 #FF55FF
                    color14 #55FFFF
                    color15 #FFFFFF
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            index_path = root / "index.jsonl"
            out_dir = root / "out"
            build_report = root / "build.json"

            result = subprocess.run(
                [
                    sys.executable,
                    str(TOOL_PATH),
                    "index",
                    "kitty",
                    str(theme_path),
                    "--jsonl",
                    str(index_path),
                ],
                check=False,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            result = subprocess.run(
                [
                    sys.executable,
                    str(TOOL_PATH),
                    "build",
                    str(index_path),
                    "--out-dir",
                    str(out_dir),
                    "--preview",
                    "--json",
                    str(build_report),
                ],
                check=False,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            built = json.loads(build_report.read_text(encoding="utf-8"))
            self.assertEqual(len(built), 1)
            self.assertTrue(Path(built[0]["canvas"]).exists())
            self.assertTrue(Path(built[0]["fingerprint"]).exists())
            self.assertTrue(Path(built[0]["preview"]).exists())

            gate_path = root / "gate.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(TOOL_PATH),
                    "record-gate1",
                    built[0]["canvas"],
                    "--result",
                    "pass",
                    "--gate-json",
                    str(gate_path),
                ],
                check=False,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            gate = json.loads(gate_path.read_text(encoding="utf-8"))
            self.assertEqual(gate["gate1"][0]["result"], "pass")


if __name__ == "__main__":
    unittest.main()
