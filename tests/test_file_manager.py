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


if __name__ == "__main__":
    unittest.main()
