"""
Гібридний пошук адрес
Комбінує Jaro-Winkler, приголосні, вагову систему
ВИПРАВЛЕНА ВЕРСІЯ - не завантажує дані при ініціалізації
"""
from typing import List, Dict, Tuple
from models.address import Address
from models.magistral_record import MagistralRecord
from search.normalizer import TextNormalizer
from search.similarity import SimilarityCalculator
from search.magistral_loader import MagistralLoader
from utils.logger import Logger
import config


class HybridSearch:
    """Гібридний пошук з ваговою системою"""
    
    def __init__(self, lazy_load: bool = True):
        """
        Ініціалізація пошуку
        
        Args:
            lazy_load: Якщо True - НЕ завантажує дані одразу
        """
        self.normalizer = TextNormalizer()
        self.similarity = SimilarityCalculator()
        self.loader = MagistralLoader()
        self.logger = Logger()
        
        self.magistral_records = []
        self._is_loaded = False
        
        # Завантажуємо тільки якщо НЕ lazy
        if not lazy_load:
            self._ensure_loaded()
    
    def _ensure_loaded(self):
        """Завантажує дані якщо ще не завантажені"""
        if not self._is_loaded:
            self.logger.info("Завантаження magistral.csv...")
            self.magistral_records = self.loader.load()
            self._is_loaded = True
            self.logger.info(f"Завантажено {len(self.magistral_records)} записів")
    
    def search(self, address: Address, max_results: int = None) -> List[Dict]:
        """
        Головний метод пошуку
        
        Args:
            address: Адреса для пошуку
            max_results: Максимум результатів (None = використати config)
            
        Returns:
            Список результатів з score
        """
        # Перевіряємо що дані завантажені
        self._ensure_loaded()
        
        if not self.magistral_records:
            self.logger.error("Magistral records порожні!")
            return []
        
        if max_results is None:
            max_results = config.MAX_SEARCH_RESULTS
        
        self.logger.debug(f"Пошук для: {address}")
        
        # 1. Отримуємо кандидатів (швидке фільтрування)
        candidates = self._get_candidates(address)
        self.logger.debug(f"Кандидатів знайдено: {len(candidates)}")
        
        if not candidates:
            return []
        
        # 2. Обчислюємо score для кожного кандидата
        scored_results = []
        for candidate in candidates:
            score = self._calculate_score(address, candidate)
            
            if score >= config.SIMILARITY_THRESHOLD:
                result = self._create_result(candidate, score)
                scored_results.append(result)
        
        # 3. Сортуємо за score
        scored_results.sort(key=lambda x: x['score'], reverse=True)
        
        self.logger.debug(f"Результатів після фільтрації: {len(scored_results)}")
        
        return scored_results[:max_results]
    
    def _get_candidates(self, address: Address) -> List[MagistralRecord]:
        """
        Швидке фільтрування кандидатів
        Використовує індекси для швидкості
        """
        candidates = []
        
        # Стратегія 1: Пошук по префіксу міста
        if address.city and len(address.city) >= 2:
            city_candidates = self.loader.get_candidates_by_city_prefix(address.city)
            candidates.extend(city_candidates)
        
        # Стратегія 2: Пошук по області
        if address.region:
            region_candidates = self.loader.get_candidates_by_region(address.region)
            
            # Додаємо тільки унікальні
            existing_ids = {id(c) for c in candidates}
            for rc in region_candidates:
                if id(rc) not in existing_ids:
                    candidates.append(rc)
        
        # Обмежуємо кількість кандидатів для продуктивності
        if len(candidates) > config.MAX_CANDIDATES:
            candidates = candidates[:config.MAX_CANDIDATES]
        
        return candidates
    
    def _calculate_score(self, address: Address, record: MagistralRecord) -> float:
        """
        Обчислює комплексний score з ваговою системою
        
        Нова вагова система:
        - Місто: 40%
        - Вулиця: 35%
        - Будинок: 15% (підвищено!)
        - Область: 10%
        """
        total_score = 0.0
        
        # Нормалізуємо запит
        query_city = self.normalizer.normalize_city(address.city)
        query_street = self.normalizer.normalize_street(address.street)
        query_region = self.normalizer.normalize_region(address.region)
        query_building = self.normalizer.normalize_text(address.building) if address.building else ""
        
        # 1. Місто (40%)
        city_similarity = 0.0
        if query_city and record.normalized_city:
            city_similarity = self.similarity.jaro_winkler_similarity(
                query_city, 
                record.normalized_city
            )
            
            # ЖОРСТКИЙ ФІЛЬТР: якщо місто зовсім не збігається
            if city_similarity < 0.7:
                return city_similarity * 0.3  # Максимум 21% score
            
            total_score += city_similarity * 0.40
        
        # 2. Вулиця (35%)
        street_similarity = 0.0
        if query_street and record.normalized_street:
            street_similarity = self.similarity.jaro_winkler_similarity(
                query_street, 
                record.normalized_street
            )
            total_score += street_similarity * 0.35
        
        # 3. Будинок (15%) - КРИТИЧНО ВАЖЛИВО!
        building_bonus = 0.0
        if query_building and record.buildings:
            # Перевіряємо чи є будинок у списку
            buildings_list = [b.strip().upper().replace("-", "").replace(" ", "") 
                             for b in record.buildings.split(',')]
            query_building_clean = query_building.upper().replace("-", "").replace(" ", "")
            
            if query_building_clean in buildings_list:
                # ТОЧНЕ СПІВПАДІННЯ - повний бонус
                building_bonus = 0.15
                total_score += building_bonus
            else:
                # Часткове співпадіння (наприклад, "27А" містить "27")
                for building in buildings_list:
                    if query_building_clean in building or building in query_building_clean:
                        building_bonus = 0.10
                        total_score += building_bonus
                        break
        
        # 4. Область (10%)
        if query_region and record.normalized_region:
            region_similarity = self.similarity.jaro_winkler_similarity(
                query_region, 
                record.normalized_region
            )
            total_score += region_similarity * 0.10
        
        # БОНУС: якщо місто, вулиця і будинок співпадають на 100% - додаємо +5%
        if city_similarity > 0.95 and street_similarity > 0.80 and building_bonus >= 0.15:
            total_score += 0.05
        
        return min(total_score, 1.0)  # Обмежуємо до 100%
    
    def _create_result(self, record: MagistralRecord, score: float) -> Dict:
        """Створює результат з усією інформацією"""
        return {
            'region': record.region,
            'district': record.new_district or record.old_district,
            'city': record.city,
            'city_ua': record.city,
            'street': record.street,
            'street_ua': record.street,
            'building': record.buildings,
            'buildings': record.buildings,
            'index': record.city_index,
            'score': score,
            'confidence': int(score * 100),
            'features': record.features,
            'not_working': record.not_working,
            'is_working': record.is_working()
        }
    
    def get_statistics(self) -> Dict:
        """Повертає статистику системи"""
        self._ensure_loaded()
        return {
            'total_records': len(self.magistral_records),
            'indexed_cities': len(self.loader.index_by_city_prefix),
            'indexed_regions': len(self.loader.index_by_region)
        }