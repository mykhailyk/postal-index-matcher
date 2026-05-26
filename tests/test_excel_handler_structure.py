import unittest
import tempfile
from pathlib import Path

import pandas as pd

from handlers.excel_handler import ExcelHandler


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXCEL_HANDLER_PATH = PROJECT_ROOT / "handlers" / "excel_handler.py"


class TestExcelHandlerStructure(unittest.TestCase):
    def setUp(self):
        self.source = EXCEL_HANDLER_PATH.read_text(encoding="utf-8")

    def test_load_file_preserves_empty_rows_inside_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.xlsx"
            pd.DataFrame({
                "city": ["Київ", "", "Львів"],
                "street": ["Хрещатик", "", "Городоцька"],
                "building": ["1", "", "2"],
                "index": ["01001", "", "79000"],
            }).to_excel(path, index=False)

            handler = ExcelHandler()
            handler.load_file(str(path))

        self.assertEqual(len(handler.df), 3)
        self.assertEqual(handler.df.loc[1, "city"], "")
        self.assertEqual(handler.df.loc[2, "index"], "79000")

    def test_load_file_preserves_leading_zero_indices(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.xlsx"
            pd.DataFrame({
                "city": ["Київ"],
                "street": ["Хрещатик"],
                "building": ["1"],
                "index": ["01001"],
            }).to_excel(path, index=False)

            handler = ExcelHandler()
            handler.load_file(str(path))

        self.assertEqual(handler.df.loc[0, "index"], "01001")

    def test_headerless_file_preserves_first_row_and_saves_without_fake_header(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "headerless.xlsx"
            saved_path = Path(tmpdir) / "saved.xlsx"
            pd.DataFrame([
                ["30019905", "Київ", "Хрещатик 1", "01001"],
                ["30017648", "Львів", "Городоцька 2", "79000"],
            ]).to_excel(path, index=False, header=False)

            handler = ExcelHandler()
            handler.load_file(str(path))
            handler.save_file(str(saved_path))

            reloaded = pd.read_excel(
                saved_path,
                header=None,
                dtype=str,
                keep_default_na=False,
                na_filter=False,
                engine="openpyxl",
            )

        self.assertFalse(handler.has_header)
        self.assertEqual(list(handler.df.columns), ["1", "2", "3", "4"])
        self.assertEqual(handler.df.loc[0, "1"], "30019905")
        self.assertEqual(reloaded.iloc[0, 0], "30019905")
        self.assertEqual(reloaded.iloc[0, 3], "01001")
        self.assertEqual(len(reloaded), 2)

    def test_save_file_falls_back_from_xls_to_xlsx(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "legacy.xls"
            fallback_path = Path(tmpdir) / "legacy.xlsx"

            handler = ExcelHandler()
            handler.df = pd.DataFrame({"index": ["01001"]})
            handler.save_file(str(path))

            self.assertTrue(fallback_path.exists())
            self.assertEqual(handler.file_path, str(fallback_path))

    def test_save_file_preserves_text_values_on_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "saved.xlsx"

            handler = ExcelHandler()
            handler.df = pd.DataFrame({
                "index": ["01001"],
                "client_id": ["300199050000123"],
                "building": ["24-КОРП3"],
                "mixed_code": ["00123А"],
            })
            handler.save_file(str(path))

            reloaded = pd.read_excel(
                path,
                dtype=str,
                keep_default_na=False,
                na_filter=False,
                engine="openpyxl",
            )

        self.assertEqual(reloaded.loc[0, "index"], "01001")
        self.assertEqual(reloaded.loc[0, "client_id"], "300199050000123")
        self.assertEqual(reloaded.loc[0, "building"], "24-КОРП3")
        self.assertEqual(reloaded.loc[0, "mixed_code"], "00123А")

    def test_loading_different_file_structure_resets_stale_mapping(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            first = Path(tmpdir) / "first.xlsx"
            second = Path(tmpdir) / "second.xlsx"
            pd.DataFrame({"city": ["Київ"], "index": ["01001"]}).to_excel(first, index=False)
            pd.DataFrame({"index": ["01001"], "city": ["Київ"]}).to_excel(second, index=False)

            handler = ExcelHandler()
            handler.load_file(str(first))
            handler.set_column_mapping({"city": [0], "index": [1]})
            handler.load_file(str(second))

        self.assertIsNone(handler.column_mapping)

    def test_column_filter_preserves_old_index_column(self):
        handler = ExcelHandler()
        handler.df = pd.DataFrame({
            "city": ["Київ"],
            "street": ["Хрещатик"],
            "building": ["1"],
            "index": ["01001"],
        })
        handler.set_column_mapping({
            "city": [0],
            "street": [1],
            "building": [2],
            "index": [3],
        })
        handler.df["Старий індекс"] = handler.df["index"].copy()

        handler.apply_column_filter()

        self.assertEqual(
            list(handler.df.columns),
            ["_original_row_index", "city", "street", "building", "index", "Старий індекс"],
        )
        self.assertEqual(handler.column_mapping["index"], [4])


    def test_column_filter_preserves_shared_source_columns(self):
        handler = ExcelHandler()
        handler.df = pd.DataFrame({
            "city": ["Kyiv"],
            "street_with_building": ["Main 12"],
            "index": ["01001"],
        })
        handler.set_column_mapping({
            "city": [0],
            "street": [1],
            "building": [1],
            "index": [2],
        })

        handler.apply_column_filter()

        self.assertEqual(handler.column_mapping["street"], handler.column_mapping["building"])
        self.assertEqual(handler.get_address_from_row(0).street, "Main 12")
        self.assertEqual(handler.get_address_from_row(0).building, "Main 12")


if __name__ == "__main__":
    unittest.main()
