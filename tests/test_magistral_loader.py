import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config
from search.magistral_loader import MagistralLoader


class TestMagistralLoader(unittest.TestCase):
    def test_load_from_csv_accepts_trimmed_headers(self):
        headers = [
            "Область",
            "Адміністративний район(старий)",
            "Адміністративний район(новий)",
            "Найменування ОТГ(довідково)",
            "Населений пункт",
            "Індекс НП",
            "Назва вулиці",
            "№ будинку",
            "сортувальний центр 1 рівня",
            "сортувальний центр 2 рівня",
            "Адміністративний район доставки(вручення)",
            "Технологічний індекс ОПЗ доставки(вручення)",
            "Особливості функціонування ВПЗ",
            "Тимчасово не функціонує",
        ]
        row = [
            "Київ",
            "",
            "Київ",
            "",
            "м. Київ",
            "01001",
            "вул. Хрещатик",
            "1",
            "",
            "",
            "",
            "",
            "",
            "",
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "magistral.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(headers)
                writer.writerow(row)

            loader = MagistralLoader()
            with patch.object(config, "MAGISTRAL_CSV_PATH", str(csv_path)):
                with patch("search.magistral_loader.print"):
                    loader._load_from_csv()

        self.assertEqual(len(loader.records), 1)
        record = loader.records[0]
        self.assertEqual(record.region, "Київ")
        self.assertEqual(record.city, "м. Київ")
        self.assertEqual(record.city_index, "01001")
        self.assertEqual(record.street, "вул. Хрещатик")
        self.assertEqual(record.buildings, "1")

    def test_postcode_index_returns_exact_candidates(self):
        headers = [
            "Область",
            "Адміністративний район(старий)",
            "Адміністративний район(новий)",
            "Найменування ОТГ(довідково)",
            "Населений пункт",
            "Індекс НП",
            "Назва вулиці",
            "№ будинку",
            "сортувальний центр 1 рівня",
            "сортувальний центр 2 рівня",
            "Адміністративний район доставки(вручення)",
            "Технологічний індекс ОПЗ доставки(вручення)",
            "Особливості функціонування ВПЗ",
            "Тимчасово не функціонує",
        ]
        rows = [
            ["Київ", "", "Київ", "", "м. Київ", "01001", "вул. Хрещатик", "1", "", "", "", "", "", ""],
            ["Київ", "", "Київ", "", "м. Київ", "01024", "вул. Велика Васильківська", "2", "", "", "", "", "", ""],
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "magistral.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(headers)
                writer.writerows(rows)

            loader = MagistralLoader()
            with patch.object(config, "MAGISTRAL_CSV_PATH", str(csv_path)):
                with patch("search.magistral_loader.print"):
                    loader._load_from_csv()
                    loader._build_indexes()

        exact = loader.get_candidates_by_postcode("01001")
        without_leading_zero = loader.get_candidates_by_postcode("1024")

        self.assertEqual(len(exact), 1)
        self.assertEqual(exact[0].city_index, "01001")
        self.assertEqual(len(without_leading_zero), 1)
        self.assertEqual(without_leading_zero[0].city_index, "01024")
        self.assertEqual(loader.get_candidates_by_postcode("01000"), [])
        self.assertEqual(loader.get_candidates_by_postcode("*"), [])


if __name__ == "__main__":
    unittest.main()
