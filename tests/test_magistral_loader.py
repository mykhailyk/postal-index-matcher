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


if __name__ == "__main__":
    unittest.main()
