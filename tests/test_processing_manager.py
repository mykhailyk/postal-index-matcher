import os
import sys
import unittest

import pandas as pd
from PyQt5.QtWidgets import QApplication

from handlers.excel_handler import ExcelHandler
from ui.managers.processing_manager import ProcessingManager
from utils.undo_manager import UndoManager


OLD_INDEX_COL = "\u0421\u0442\u0430\u0440\u0438\u0439 \u0456\u043d\u0434\u0435\u043a\u0441"


class TestProcessingManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def make_manager(self):
        handler = ExcelHandler()
        handler.df = pd.DataFrame({
            "city": ["Kyiv", "Lviv"],
            "street": ["Main", "Svobody"],
            "building": ["1", "2"],
            "index": ["01001", "79000"],
            OLD_INDEX_COL: ["01001", "79000"],
        })
        handler.set_column_mapping({
            "city": [0],
            "street": [1],
            "building": [2],
            "index": [3],
        })
        undo = UndoManager()
        return ProcessingManager(handler, undo), handler, undo

    def test_auto_processing_skips_rows_that_already_differ_from_old_index(self):
        manager, handler, _ = self.make_manager()
        handler.df.loc[1, "index"] = "79001"

        def search_func(address, auto_apply):
            return {
                "mode": "auto",
                "applied": True,
                "auto_result": {
                    "index": "02002",
                    "city": address.city,
                    "street": address.street,
                    "building": address.building,
                    "not_working": "",
                },
                "total_found": 1,
                "manual_results": [],
            }

        processed = []
        manager.on_row_processed = lambda row, index, mode: processed.append((row, index, mode))

        stats = manager.start_auto_processing(0, len(handler.df), search_func)

        self.assertEqual(handler.df.loc[0, "index"], "02002")
        self.assertEqual(handler.df.loc[1, "index"], "79001")
        self.assertEqual(stats["auto_applied"], 1)
        self.assertEqual(stats["skipped"], 1)
        self.assertEqual(processed, [(0, "02002", "auto")])

    def test_apply_index_pushes_undo_and_updates_dataframe(self):
        manager, handler, undo = self.make_manager()

        self.assertTrue(manager.apply_index(0, "03003"))

        self.assertEqual(handler.df.loc[0, "index"], "03003")
        self.assertTrue(undo.can_undo())
        action = undo.peek_undo()
        self.assertEqual(action["old_values"]["index"], "01001")
        self.assertEqual(action["new_values"]["index"], "03003")

    def test_determine_index_handles_not_working_redirects(self):
        manager, _, _ = self.make_manager()

        self.assertEqual(
            manager._determine_index({
                "index": "01001",
                "not_working": "Тимчасово не функціонує",
            }),
            "*",
        )
        self.assertEqual(
            manager._determine_index({
                "index": "01001",
                "not_working": "ВПЗ тимчасово не працює, перенаправлення 02002",
            }),
            "02002",
        )
        self.assertEqual(
            manager._determine_index({
                "index": "01001",
                "not_working": "",
            }),
            "01001",
        )


if __name__ == "__main__":
    unittest.main()
