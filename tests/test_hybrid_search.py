import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Додаємо кореневу директорію в sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search.hybrid_search import HybridSearch
from models.address import Address
from models.magistral_record import MagistralRecord
import config

class TestHybridSearch(unittest.TestCase):
    def setUp(self):
        # Мокаємо завантажувач щоб не читати реальний файл
        self.search = HybridSearch(lazy_load=True)
        self.search.loader = MagicMock()
        self.search.loader.index_by_city_prefix = {}
        self.search.loader.index_by_region = {}
        self.search._is_loaded = True # Імітуємо що завантажено
        
    def test_calculate_score_strict_perfect_match(self):
        """Тест ідеального співпадіння"""
        address = Address(city="Київ", street="Хрещатик", building="1")
        record = MagistralRecord(
            region="Київ", new_district="Київ", city="м. Київ", 
            street="вул. Хрещатик", buildings="1", city_index="01001"
        )
        # Мокаємо нормалізацію
        record.normalized_city = "киів"
        record.normalized_street = "хрещатик"
        
        score = self.search._calculate_score_strict(address, record)
        self.assertGreaterEqual(score, 0.95)

    def test_calculate_score_strict_partial_match(self):
        """Тест часткового співпадіння (помилка в вулиці)"""
        address = Address(city="Київ", street="Хрещ", building="1") # Помилка
        record = MagistralRecord(
            region="Київ", new_district="Київ", city="м. Київ", 
            street="вул. Хрещатик", buildings="1", city_index="01001"
        )
        record.normalized_city = "киів"
        record.normalized_street = "хрещатик"
        
        score = self.search._calculate_score_strict(address, record)
        self.assertTrue(0.5 < score < 1.0)

    def test_find_auto_result_success(self):
        """Тест успішної автопідстановки"""
        address = Address(city="Київ", street="Хрещатик", building="1")
        
        # Один ідеальний результат
        results = [{
            'index': '01001',
            'city': 'м. Київ',
            'street': 'вул. Хрещатик',
            'building': '1',
            'buildings': '1, 3, 5',
            'confidence': 99,
            'score': 0.99
        }]
        
        result = self.search._find_auto_result(address, results)
        self.assertIsNotNone(result)
        self.assertEqual(result['index'], '01001')

    def test_find_auto_result_ambiguous(self):
        """Тест коли є кілька ідеальних результатів (неоднозначність)"""
        address = Address(city="Київ", street="Хрещатик", building="1")
        
        # Два ідеальних результати
        results = [
            {'index': '01001', 'confidence': 99, 'buildings': '1'},
            {'index': '01002', 'confidence': 99, 'buildings': '1'}
        ]
        
        result = self.search._find_auto_result(address, results)
        self.assertIsNone(result)

    def test_find_auto_result_wrong_building(self):
        """Тест коли будинок не співпадає"""
        address = Address(city="Київ", street="Хрещатик", building="999")
        
        results = [{
            'index': '01001',
            'confidence': 99,
            'buildings': '1, 3, 5' # 999 немає
        }]
        
        result = self.search._find_auto_result(address, results)
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
