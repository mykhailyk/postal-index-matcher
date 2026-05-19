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

    def test_load_file_drops_rows_that_are_empty_after_fillna(self):
        self.assertIn("non_empty_rows = self.df.apply", self.source)
        self.assertIn("any(str(value).strip() for value in row)", self.source)

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

    def test_save_file_falls_back_from_xls_to_xlsx(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "legacy.xls"
            fallback_path = Path(tmpdir) / "legacy.xlsx"

            handler = ExcelHandler()
            handler.df = pd.DataFrame({"index": ["01001"]})
            handler.save_file(str(path))

            self.assertTrue(fallback_path.exists())
            self.assertEqual(handler.file_path, str(fallback_path))

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
