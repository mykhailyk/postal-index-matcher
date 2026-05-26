import unittest
from unittest.mock import MagicMock
import sys
import os

# Додаємо кореневу директорію в sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search.hybrid_search import HybridSearch
from search.ukrposhta_classifier import ClassifierCity, ClassifierStreet, PostOffice
from models.address import Address
from models.magistral_record import MagistralRecord

class TestHybridSearch(unittest.TestCase):
    def setUp(self):
        # Мокаємо завантажувач щоб не читати реальний файл
        self.search = HybridSearch(lazy_load=True)
        self.search.loader = MagicMock()
        self.search.loader.index_by_city_prefix = {}
        self.search.loader.index_by_region = {}
        self.search._is_loaded = True # Імітуємо що завантажено
        
    def test_classifier_results_are_added_as_search_candidates(self):
        class FakeClassifier:
            def get_addresses_by_postcode(self, postcode):
                return []

            def get_cities_by_name(self, city):
                return [ClassifierCity(region="Запорізька", district="", city="Запоріжжя", city_id="1")]

            def get_streets_by_name(self, city_id, street):
                return [ClassifierStreet(region="Запорізька", city="Запоріжжя", street="Гданська", street_type_short="вул.", street_id="10")]

            def get_houses_by_street_id(self, street_id, house_number=""):
                return [("5", "69089")]

        self.search.classifier = FakeClassifier()

        results = self.search._get_classifier_results(Address(city="Запоріжжя", street="ГДАНСЬКА", building="5"))

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['index'], '69089')
        self.assertEqual(results[0]['source'], 'ukrposhta_classifier')

    def test_post_office_recommendation_prefers_nearest_working_office(self):
        class FakeClassifier:
            def get_cities_by_name(self, city):
                return [ClassifierCity(region="Київська", city="Вишневе", city_id="1")]

            def get_post_offices_by_city_id(self, city_id):
                return [
                    PostOffice(postcode="08133", city="Вишневе", street="Центральна", house_number="1", lock_code="1"),
                    PostOffice(postcode="08134", city="Вишневе", street="Святошинська", house_number="27", lock_code="0"),
                    PostOffice(postcode="08140", city="Вишневе", street="Європейська", house_number="2", lock_code="0"),
                ]

        self.search.classifier = FakeClassifier()
        anchor = {
            'index': '08133',
            'city': 'Вишневе',
            'region': 'Київська',
            'not_working': 'Тимчасово не функціонує',
        }

        result = self.search._find_post_office_recommendation(Address(city="Вишневе"), anchor, [anchor])

        self.assertIsNotNone(result)
        self.assertEqual(result['index'], '08134')
        self.assertTrue(result['is_post_office_recommendation'])

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

    def test_find_auto_result_prefers_single_very_high_match(self):
        address = Address(city="Кам'янське", street="Ромашкова", building="37")

        results = [
            {'index': '51912', 'confidence': 100, 'score': 1.0, 'buildings': '35,36,37,38'},
            {'index': '51918', 'confidence': 90, 'score': 0.90, 'buildings': '33,37,39'},
        ]

        result = self.search._find_auto_result(address, results)

        self.assertIsNotNone(result)
        self.assertEqual(result['index'], '51912')

    def test_find_auto_result_allows_exact_index_correction(self):
        address = Address(city="Житомир", street="пр-т Миру", building="2", index="10001")

        results = [{
            'index': '10020',
            'confidence': 100,
            'score': 1.0,
            'buildings': '1,1Б,2,3',
        }]

        result = self.search._find_auto_result(address, results)

        self.assertIsNotNone(result)
        self.assertEqual(result['index'], '10020')

    def test_find_auto_result_does_not_correct_real_index_with_general_result(self):
        address = Address(city="Старий Білоус", street="Невідома", building="43", index="01001")

        results = [{
            'index': '15504',
            'confidence': 98,
            'score': 0.98,
            'buildings': '',
            'is_general': True,
        }]

        result = self.search._find_auto_result(address, results)

        self.assertIsNone(result)

    def test_find_auto_result_uses_unique_best_confidence(self):
        address = Address(city="Запоріжжя", street="ГДАНСЬКА", building="5")

        results = [
            {'index': '69089', 'confidence': 100, 'score': 1.0, 'buildings': '1,2,3,4,5'},
            {'index': '69039', 'confidence': 99, 'score': 1.0, 'buildings': '1,2,3,4,5'},
            {'index': '69083', 'confidence': 91, 'score': 0.91, 'buildings': '5'},
        ]

        result = self.search._find_auto_result(address, results)

        self.assertIsNotNone(result)
        self.assertEqual(result['index'], '69089')

    def test_find_auto_result_keeps_equal_best_confidence_manual(self):
        address = Address(city="Василівка", street="МИРУ", building="16")

        results = [
            {'index': '51273', 'confidence': 100, 'score': 1.0, 'buildings': '1,2,16'},
            {'index': '28115', 'confidence': 100, 'score': 1.0, 'buildings': '1,2,16'},
            {'index': '71602', 'confidence': 99, 'score': 0.99, 'buildings': '16'},
        ]

        result = self.search._find_auto_result(address, results)

        self.assertIsNone(result)

    def test_deduplicate_equivalent_general_results_prefers_lower_index(self):
        results = [
            {
                'region': 'Чернігівська',
                'district': 'Чернігівський',
                'city': 'с. Старий Білоус',
                'street': 'Загальний для н.п. (вулицю не знайдено)',
                'building': '',
                'buildings': '',
                'index': '15504',
                'score': 0.89,
                'confidence': 89,
                'is_general': True,
            },
            {
                'region': 'Чернігівська',
                'district': 'Чернігівський',
                'city': 'с. Старий Білоус',
                'street': 'Загальний для н.п. (вулицю не знайдено)',
                'building': '',
                'buildings': '',
                'index': '15304',
                'score': 0.89,
                'confidence': 89,
                'is_general': True,
            },
        ]

        deduped = self.search._deduplicate_equivalent_results(results)

        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]['index'], '15304')

    def test_create_result_caps_fuzzy_street_at_99_confidence(self):
        address = Address(city="Запоріжжя", street="ГДАНСЬКА", building="5")
        record = MagistralRecord(
            city="м. Запоріжжя",
            street="вул. Громадянська",
            buildings="1,2,3,4,5",
            city_index="69039",
        )
        record.normalized_street = self.search.normalizer.normalize_street(record.street)

        result = self.search._create_result(record, 1.0, address)

        self.assertEqual(result['confidence'], 99)

    def test_create_result_keeps_exact_street_at_100_confidence(self):
        address = Address(city="Запоріжжя", street="ГДАНСЬКА", building="5")
        record = MagistralRecord(
            city="м. Запоріжжя",
            street="вул. Гданська",
            buildings="1,2,3,4,5",
            city_index="69089",
        )
        record.normalized_street = self.search.normalizer.normalize_street(record.street)

        result = self.search._create_result(record, 1.0, address)

        self.assertEqual(result['confidence'], 100)

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
