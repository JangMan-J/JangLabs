import importlib.util
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


LAB_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = LAB_ROOT / "tools" / "kvantum-source-summary.py"


def load_kvantum_module():
    spec = importlib.util.spec_from_file_location("kvantum_source_summary", TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


kvantum_source_summary = load_kvantum_module()


class KvantumSourceSummaryTest(unittest.TestCase):
    def write_sources(self, root):
        config_path = root / "theme.kvconfig"
        svg_path = root / "theme.svg"
        config_path.write_text(
            textwrap.dedent(
                """
                [GeneralColors]
                window.color=#1E1E2E
                base.color=#181825
                button.color=#313244
                highlight.color=#74C7EC4D
                text.color=#CDD6F4
                link.color=#74C7EC
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        svg_path.write_text(
            '<svg><rect style="fill:#74C7EC"/><rect style="fill:#313244"/></svg>\n',
            encoding="utf-8",
        )
        return config_path, svg_path

    def test_builds_source_summary_from_kvconfig_and_svg(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path, svg_path = self.write_sources(Path(temp_dir))

            output = kvantum_source_summary.build_summary(
                config_path,
                svg_path,
                family="catppuccin",
                base="mocha",
                accent="sapphire",
                source_name="catppuccin-mocha-sapphire",
            )

            self.assertEqual(output["schema_version"], 1)
            self.assertEqual(output["theme"]["accent"], "sapphire")
            self.assertEqual(output["metadata"]["source_format"], "kvantum")
            self.assertEqual(output["general_colors"]["link.color"], "#74C7EC")
            self.assertEqual(output["general_colors"]["highlight.color"], "#74C7EC4D")
            self.assertIn("#74C7EC", output["svg_colors"])
            self.assertIn("#313244", output["svg_colors"])
            self.assertNotIn("#3DAEE9", output["svg_colors"])

    def test_cli_writes_summary_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path, svg_path = self.write_sources(root)
            output_path = root / "derived" / "summary.json"

            result = subprocess.run(
                [
                    sys.executable,
                    str(TOOL_PATH),
                    str(config_path),
                    str(svg_path),
                    "--family",
                    "catppuccin",
                    "--base",
                    "mocha",
                    "--accent",
                    "sapphire",
                    "--source-name",
                    "catppuccin-mocha-sapphire",
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
            self.assertEqual(written["general_colors"]["button.color"], "#313244")


if __name__ == "__main__":
    unittest.main()
