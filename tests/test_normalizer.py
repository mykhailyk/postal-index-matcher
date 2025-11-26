import unittest
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search.normalizer import TextNormalizer

class TestTextNormalizer(unittest.TestCase):
    def setUp(self):
        self.normalizer = TextNormalizer()

    def test_normalize_city(self):
        self.assertEqual(self.normalizer.normalize_city("м. Київ"), "киів")
        self.assertEqual(self.normalizer.normalize_city("місто Львів"), "львів")
        self.assertEqual(self.normalizer.normalize_city("с. Петрівка"), "петрівка")
        self.assertEqual(self.normalizer.normalize_city("Київ"), "киів")

    def test_normalize_street(self):
        self.assertEqual(self.normalizer.normalize_street("вул. Шевченка"), "шевченка")
        self.assertEqual(self.normalizer.normalize_street("проспект Перемоги"), "перемоги")
        self.assertEqual(self.normalizer.normalize_street("провулок Тихий"), "тихий")
        self.assertEqual(self.normalizer.normalize_street("Шевченка вул."), "шевченка вул")

    def test_normalize_text(self):
        self.assertEqual(self.normalizer.normalize_text("  Привіт   Світ  "), "привіт світ")
        self.assertEqual(self.normalizer.normalize_text("Test-123"), "test-123")

if __name__ == '__main__':
    unittest.main()
