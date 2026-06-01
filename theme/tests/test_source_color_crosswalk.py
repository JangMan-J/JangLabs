import importlib.util
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


LAB_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = LAB_ROOT / "tools" / "source-color-crosswalk.py"


def load_crosswalk_module():
    spec = importlib.util.spec_from_file_location("source_color_crosswalk", TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


source_color_crosswalk = load_crosswalk_module()


class SourceColorCrosswalkTest(unittest.TestCase):
    def write_sources(self, root):
        kitty_path = root / "Catppuccin-Mocha.conf"
        kde_path = root / "CatppuccinMochaSapphire.colors"
        kvconfig_path = root / "theme.kvconfig"
        svg_path = root / "theme.svg"

        kitty_path.write_text(
            textwrap.dedent(
                """
                foreground #CDD6F4
                background #1E1E2E
                color0 #45475A
                color1 #F38BA8
                mark3_background #74C7EC
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        kde_path.write_text(
            textwrap.dedent(
                """
                [Colors:View]
                BackgroundNormal=30, 30, 46
                ForegroundNormal=205, 214, 244

                [Colors:Selection]
                BackgroundNormal=116,199,236

                [Colors:Window]
                BackgroundNormal=24,24,37
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        kvconfig_path.write_text(
            textwrap.dedent(
                """
                [GeneralColors]
                window.color=#1E1E2E
                text.color=#CDD6F4
                highlight.color=#74C7EC4D
                link.color=#74C7EC

                [HeaderSection]
                text.focus.color=#74C7EC
                visited.link.color=#86CAEE
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        svg_path.write_text(
            '<svg><rect style="fill:#74C7EC"/><rect style="fill:#313244"/></svg>\n',
            encoding="utf-8",
        )
        return kitty_path, kde_path, kvconfig_path, svg_path

    def test_builds_crosswalk_across_terminal_kde_and_kvantum_sources(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            sources = self.write_sources(Path(temp_dir))

            output = source_color_crosswalk.build_crosswalk(*sources)

            self.assertEqual(output["schema_version"], 1)
            by_role = {item["role"]: item for item in output["terminal_roles"]}
            self.assertEqual(by_role["background"]["hex"], "#1E1E2E")
            self.assertIn(
                {
                    "source": "kde_colors",
                    "field": "Colors:View.BackgroundNormal",
                    "value": "#1E1E2E",
                },
                by_role["background"]["target_matches"],
            )
            self.assertNotIn("mark3_background", by_role)
            extra_by_role = {item["role"]: item for item in output["extra_kitty_colors"]}
            self.assertIn(
                {
                    "source": "kvantum_config",
                    "field": "GeneralColors.highlight.color",
                    "value": "#74C7EC4D",
                },
                extra_by_role["mark3_background"]["target_matches"],
            )
            target_only = {item["hex"]: item for item in output["target_only_colors"]}
            self.assertEqual(target_only["#74C7EC"]["extra_kitty_roles"], ["mark3_background"])
            self.assertEqual(target_only["#74C7EC"]["classification"], "accent_axis")
            self.assertEqual(target_only["#74C7EC"]["reference_palette_roles"], ["sapphire"])
            self.assertEqual(
                target_only["#181825"]["classification"],
                "reference_gui_palette",
            )
            self.assertEqual(target_only["#181825"]["reference_palette_roles"], ["mantle"])
            self.assertEqual(target_only["#86CAEE"]["classification"], "derived_or_artifact")
            self.assertEqual(target_only["#86CAEE"]["reference_palette_roles"], [])
            self.assertEqual(target_only["#86CAEE"]["nearest_terminal_roles"][0]["role"], "foreground")
            self.assertEqual(target_only["#86CAEE"]["nearest_terminal_roles"][0]["distance"], 72.256)
            self.assertIn("#313244", target_only)

    def test_cli_writes_crosswalk_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sources = self.write_sources(root)
            output_path = root / "derived" / "crosswalk.json"

            result = subprocess.run(
                [
                    sys.executable,
                    str(TOOL_PATH),
                    *(str(source) for source in sources),
                    "--json",
                    str(output_path),
                ],
                check=False,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            written = json.loads(output_path.read_text(encoding="utf-8"))
            printed = json.loads(result.stdout)
            self.assertEqual(written, printed)
            self.assertEqual(written["theme"]["base"], "mocha")


if __name__ == "__main__":
    unittest.main()
