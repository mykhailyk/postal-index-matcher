import unittest
import importlib.util
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEARCH_MANAGER_PATH = PROJECT_ROOT / "ui" / "managers" / "search_manager.py"

spec = importlib.util.spec_from_file_location("search_manager_module", SEARCH_MANAGER_PATH)
search_manager_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(search_manager_module)
SearchManager = search_manager_module.SearchManager


class StubLogger:
    def info(self, message):
        pass

    def error(self, message):
        pass


class TestSearchManager(unittest.TestCase):
    def test_get_magistral_records_loads_lazy_engine(self):
        manager = SearchManager.__new__(SearchManager)
        manager.logger = StubLogger()

        class FakeEngine:
            def __init__(self):
                self.magistral_records = []
                self.loaded = False

            def _ensure_loaded(self):
                self.loaded = True
                self.magistral_records = ["record"]

        engine = FakeEngine()
        manager.search_engine = engine

        self.assertEqual(manager.get_magistral_records(), ["record"])
        self.assertTrue(engine.loaded)

    def test_refresh_cache_updates_engine_records(self):
        manager = SearchManager.__new__(SearchManager)
        manager.logger = StubLogger()

        loader = SimpleNamespace(load=lambda force_reload=True: ["fresh"])
        manager.search_engine = SimpleNamespace(
            loader=loader,
            magistral_records=["stale"],
            _is_loaded=False,
        )

        manager.refresh_cache(force_reload=True)

        self.assertEqual(manager.search_engine.magistral_records, ["fresh"])
        self.assertTrue(manager.search_engine._is_loaded)


if __name__ == "__main__":
    unittest.main()
