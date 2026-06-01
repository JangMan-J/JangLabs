import importlib.util
import importlib.machinery
import tempfile
import textwrap
import unittest
import zipfile
from pathlib import Path


LAB_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = LAB_ROOT / "tools" / "kde-store-tool"


def load_kde_store_module():
    loader = importlib.machinery.SourceFileLoader("kde_store_tool", str(TOOL_PATH))
    spec = importlib.util.spec_from_loader("kde_store_tool", loader)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


kde_store_tool = load_kde_store_module()


SEARCH_XML = textwrap.dedent(
    """
    <?xml version="1.0" encoding="UTF-8"?>
    <ocs>
      <data>
        <content details="summary">
          <id>1917079</id>
          <name>Utterly Nord Light</name>
          <version>1.1</version>
          <typeid>9001</typeid>
          <typename>Plasma Color Schemes</typename>
          <xdg_type>plasma_color_schemes</xdg_type>
          <personid>himdek</personid>
          <created>2022-10-08T06:52:47+00:00</created>
          <changed>2025-05-01T03:29:16+00:00</changed>
          <downloads>46312</downloads>
          <score>50</score>
          <summary>A Light Nordic Color Scheme for Plasma</summary>
          <detailpage>https://store.kde.org/p/1917079</detailpage>
          <tags>unix,theme,colorscheme,gplv2-later,original-product,plasma,linux,kde</tags>
          <downloadlink1>https://example.invalid/light.tar.gz</downloadlink1>
          <downloadname1>Utterly-Nord-Light-Colors.tar.gz</downloadname1>
          <downloadmd5sum1>light-md5</downloadmd5sum1>
          <download_version1>1.1</download_version1>
          <downloadtags1>data##mimetype=application/gzip</downloadtags1>
        </content>
        <content details="summary">
          <id>1903937</id>
          <name>Utterly Nord</name>
          <version>1.1</version>
          <typeid>9001</typeid>
          <typename>Plasma Color Schemes</typename>
          <xdg_type>plasma_color_schemes</xdg_type>
          <personid>himdek</personid>
          <created>2022-09-13T14:28:17+00:00</created>
          <changed>2025-05-01T03:30:10+00:00</changed>
          <downloads>110048</downloads>
          <score>58</score>
          <summary>A Nordic Color Scheme for Plasma</summary>
          <detailpage>https://store.kde.org/p/1903937</detailpage>
          <tags>kde,linux,unix,theme,original-product,nord,nordic,plasma,colorful,colorscheme,gplv2-later</tags>
          <downloadlink1>https://example.invalid/dark.tar.gz</downloadlink1>
          <downloadname1>Utterly-Nord-Colors.tar.gz</downloadname1>
          <downloadmd5sum1>dark-md5</downloadmd5sum1>
          <download_version1>1.1</download_version1>
          <downloadtags1>data##mimetype=application/gzip</downloadtags1>
        </content>
        <content details="summary">
          <id>1905813</id>
          <name>Utterly Nord</name>
          <version>1.2</version>
          <typeid>9002</typeid>
          <typename>Kvantum</typename>
          <xdg_type>kvantum_themes</xdg_type>
          <personid>himdek</personid>
          <created>2022-09-18T08:00:00+00:00</created>
          <changed>2025-05-01T03:29:20+00:00</changed>
          <downloads>903</downloads>
          <score>50</score>
          <summary>A Kvantum theme with Nordic Colors</summary>
          <detailpage>https://store.kde.org/p/1905813</detailpage>
          <tags>kvantum,linux,gplv2-later,original-product,theme,unix</tags>
          <downloadlink1>https://example.invalid/kvantum.zip</downloadlink1>
          <downloadname1>Utterly-Nord-kvantum.zip</downloadname1>
          <downloadmd5sum1>kvantum-md5</downloadmd5sum1>
          <download_version1>1.2</download_version1>
          <downloadtags1>data##mimetype=application/zip</downloadtags1>
        </content>
      </data>
    </ocs>
    """
).strip().encode("utf-8")


CATEGORIES_XML = textwrap.dedent(
    """
    <?xml version="1.0" encoding="UTF-8"?>
    <ocs>
      <data>
        <category>
          <id>9001</id>
          <name>KDE Color Scheme KDE4</name>
          <display_name>Plasma Color Schemes</display_name>
          <parent_id></parent_id>
          <xdg_type>plasma_color_schemes</xdg_type>
        </category>
        <category>
          <id>9003</id>
          <name>Global Themes (Plasma 6)</name>
          <display_name>Global Themes (Plasma 6)</display_name>
          <parent_id></parent_id>
          <xdg_type></xdg_type>
        </category>
      </data>
    </ocs>
    """
).strip().encode("utf-8")


class KdeStoreToolTest(unittest.TestCase):
    def test_parses_plasma_color_scheme_search_response(self):
        products = kde_store_tool.parse_products(SEARCH_XML)

        self.assertEqual(len(products), 3)
        self.assertEqual(products[1].product_id, "1903937")
        self.assertEqual(products[1].name, "Utterly Nord")
        self.assertEqual(products[1].type_id, "9001")
        self.assertEqual(products[1].type_name, "Plasma Color Schemes")
        self.assertEqual(products[1].person_id, "himdek")
        self.assertEqual(products[1].score, "58")
        self.assertEqual(products[1].tags.split(",")[0], "kde")
        self.assertEqual(products[1].downloads[0].name, "Utterly-Nord-Colors.tar.gz")
        self.assertEqual(products[1].downloads[0].md5, "dark-md5")

    def test_parses_category_list_without_local_constants(self):
        categories = kde_store_tool.parse_categories(CATEGORIES_XML)

        self.assertEqual(categories[0]["id"], "9001")
        self.assertEqual(categories[0]["display_name"], "Plasma Color Schemes")
        self.assertEqual(categories[1]["name"], "Global Themes (Plasma 6)")

    def test_default_filter_is_broad_across_product_types(self):
        products = kde_store_tool.parse_products(SEARCH_XML)

        filtered = kde_store_tool.filter_products(products)

        self.assertEqual(
            [product.product_id for product in filtered],
            ["1917079", "1903937", "1905813"],
        )

    def test_filters_products_by_category_tag_creator_and_name(self):
        products = kde_store_tool.parse_products(SEARCH_XML)

        filtered = kde_store_tool.filter_products(
            products,
            categories=("kvantum",),
            exact_name="Utterly Nord",
            tag="kvantum",
            creator="himdek",
            has_download=True,
        )

        self.assertEqual([product.product_id for product in filtered], ["1905813"])

    def test_select_product_rejects_ambiguous_exact_name(self):
        original_search = kde_store_tool.search_products
        try:
            kde_store_tool.search_products = (
                lambda query, page_size=100, categories=None, **kwargs: kde_store_tool.filter_products(
                    kde_store_tool.parse_products(SEARCH_XML),
                    categories=categories,
                )
            )

            with self.assertRaisesRegex(ValueError, "multiple exact KDE Store products"):
                kde_store_tool.select_product("Utterly Nord")
        finally:
            kde_store_tool.search_products = original_search

    def test_select_product_can_target_plasma_color_scheme_category_by_name(self):
        original_search = kde_store_tool.search_products
        try:
            kde_store_tool.search_products = (
                lambda query, page_size=100, categories=None, **kwargs: kde_store_tool.filter_products(
                    kde_store_tool.parse_products(SEARCH_XML),
                    categories=categories,
                )
            )

            product = kde_store_tool.select_product(
                "Utterly Nord",
                categories=("Plasma Color Schemes",),
            )

            self.assertEqual(product.product_id, "1903937")
            self.assertEqual(product.type_name, "Plasma Color Schemes")
        finally:
            kde_store_tool.search_products = original_search

    def test_select_product_can_target_kvantum_category(self):
        original_search = kde_store_tool.search_products
        try:
            kde_store_tool.search_products = (
                lambda query, page_size=100, categories=None, **kwargs: kde_store_tool.filter_products(
                    kde_store_tool.parse_products(SEARCH_XML),
                    categories=categories,
                )
            )

            product = kde_store_tool.select_product("Utterly Nord", categories=("kvantum",))

            self.assertEqual(product.product_id, "1905813")
            self.assertEqual(product.type_name, "Kvantum")
        finally:
            kde_store_tool.search_products = original_search

    def test_category_filter_can_still_target_numeric_type_id(self):
        products = kde_store_tool.parse_products(SEARCH_XML)

        filtered = kde_store_tool.filter_products(products, categories=("9001",))

        self.assertEqual([product.product_id for product in filtered], ["1917079", "1903937"])

    def test_safe_extract_tar_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            archive_path = root / "bad.tar.gz"
            payload_path = root / "payload.txt"
            payload_path.write_text("bad\n", encoding="utf-8")

            import tarfile

            with tarfile.open(archive_path, "w:gz") as archive:
                archive.add(payload_path, arcname="../payload.txt")

            with self.assertRaisesRegex(ValueError, "unsafe path"):
                kde_store_tool.safe_extract_tar(archive_path, root / "extract")

    def test_safe_extract_tar_rejects_links(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            archive_path = root / "bad-link.tar.gz"

            import tarfile

            member = tarfile.TarInfo("external-link")
            member.type = tarfile.SYMTYPE
            member.linkname = "/etc/passwd"

            with tarfile.open(archive_path, "w:gz") as archive:
                archive.addfile(member)

            with self.assertRaisesRegex(ValueError, "link path"):
                kde_store_tool.safe_extract_tar(archive_path, root / "extract")

    def test_safe_extract_zip_extracts_normal_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            archive_path = root / "theme.zip"

            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("Theme/Theme.kvconfig", "[GeneralColors]\n")

            extracted = kde_store_tool.safe_extract_archive(archive_path, root / "extract")

            self.assertEqual(len(extracted), 1)
            self.assertTrue((root / "extract" / "Theme" / "Theme.kvconfig").exists())

    def test_safe_extract_zip_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            archive_path = root / "bad.zip"

            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("../bad.kvconfig", "bad\n")

            with self.assertRaisesRegex(ValueError, "unsafe path"):
                kde_store_tool.safe_extract_archive(archive_path, root / "extract")


if __name__ == "__main__":
    unittest.main()
