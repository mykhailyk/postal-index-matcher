import tempfile
import unittest
from pathlib import Path

import pandas as pd

from ui.managers.file_manager import FileManager


class TestFileManager(unittest.TestCase):
    def test_save_xls_without_parent_falls_back_to_xlsx(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "legacy.xls"
            fallback_path = Path(tmpdir) / "legacy.xlsx"

            manager = FileManager()
            manager.excel_handler.df = pd.DataFrame({"index": ["01001"]})

            self.assertTrue(manager.save_file(str(path), parent=None))
            self.assertTrue(fallback_path.exists())
            self.assertEqual(manager.current_file, str(fallback_path))

    def test_save_xlsx_updates_current_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "saved.xlsx"

            manager = FileManager()
            manager.excel_handler.df = pd.DataFrame({"index": ["01001"]})

            self.assertTrue(manager.save_file(str(path), parent=None))
            self.assertTrue(path.exists())
            self.assertEqual(manager.current_file, str(path))

    def test_smart_save_preserves_unfiltered_rows_and_text_values(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "saved.xlsx"

            manager = FileManager()
            manager.excel_handler.original_df = pd.DataFrame({
                "city": ["Київ", "", "Львів"],
                "index": ["01001", "", "79000"],
                "_original_row_index": [0, 1, 2],
            })
            manager.excel_handler.df = pd.DataFrame({
                "_original_row_index": [0, 2],
                "city": ["Київ", "Львів"],
                "index": ["01002", "079000"],
            })

            self.assertTrue(manager.save_file(str(path), parent=None))
            reloaded = pd.read_excel(
                path,
                dtype=str,
                keep_default_na=False,
                na_filter=False,
                engine="openpyxl",
            )

        self.assertEqual(len(reloaded), 3)
        self.assertEqual(reloaded.loc[0, "index"], "01002")
        self.assertEqual(reloaded.loc[1, "index"], "")
        self.assertEqual(reloaded.loc[2, "index"], "079000")


if __name__ == "__main__":
    unittest.main()
