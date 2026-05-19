import ast
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_WINDOW_PATH = PROJECT_ROOT / "ui" / "main_window.py"
RESULTS_PANEL_PATH = PROJECT_ROOT / "ui" / "widgets" / "results_panel.py"


class TestMainWindowStructure(unittest.TestCase):
    def setUp(self):
        self.source = MAIN_WINDOW_PATH.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)

    def test_main_window_has_no_duplicate_methods(self):
        main_window = next(
            node for node in self.tree.body
            if isinstance(node, ast.ClassDef) and node.name == "MainWindow"
        )

        methods = {}
        duplicates = []
        for node in main_window.body:
            if isinstance(node, ast.FunctionDef):
                if node.name in methods:
                    duplicates.append(node.name)
                methods[node.name] = node.lineno

        self.assertEqual(duplicates, [])

    def test_auto_processing_callback_uses_table_panel(self):
        self.assertNotIn("self.table.item", self.source)
        self.assertIn("self.table_panel.table.item", self.source)

    def test_status_label_is_not_called_as_statusbar_method(self):
        self.assertNotIn("self.status_bar()", self.source)

    def test_row_processed_callback_accepts_processing_mode(self):
        main_window = next(
            node for node in self.tree.body
            if isinstance(node, ast.ClassDef) and node.name == "MainWindow"
        )
        callback = next(
            node for node in main_window.body
            if isinstance(node, ast.FunctionDef) and node.name == "_on_row_processed"
        )

        args = [arg.arg for arg in callback.args.args]
        self.assertEqual(args, ["self", "row_idx", "index", "mode"])

    def test_results_panel_keeps_show_results_api(self):
        source = RESULTS_PANEL_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        results_panel = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "ResultsPanel"
        )
        methods = {
            node.name
            for node in results_panel.body
            if isinstance(node, ast.FunctionDef)
        }

        self.assertIn("show_results", methods)
        self.assertIn("display_results", methods)


if __name__ == "__main__":
    unittest.main()
