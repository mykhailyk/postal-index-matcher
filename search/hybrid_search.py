"""
Гібридний пошук адрес v3.0 - з рівнями впевненості
Комбінує Jaro-Winkler, Levenshtein, Fuzzy matching, N-grams
"""
from typing import List, Dict, Tuple, Optional
from models.address import Address
from models.magistral_record import MagistralRecord
from search.normalizer import TextNormalizer
from search.similarity import SimilarityCalculator
from search.magistral_loader import MagistralLoader
from utils.logger import Logger
import config


class HybridSearch:
    """Гібридний пошук з автоматичною та ручною підстановкою"""
    
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
            self.logger.info("=" * 80)
            self.logger.info("📂 ЗАВАНТАЖЕННЯ ДАНИХ З magistral.csv")
            self.magistral_records = self.loader.load()
            self._is_loaded = True
            self.logger.info(f"✓ Завантажено записів: {len(self.magistral_records)}")
            self.logger.info(f"✓ Проіндексовано міст: {len(self.loader.index_by_city_prefix)}")
            self.logger.info(f"✓ Проіндексовано областей: {len(self.loader.index_by_region)}")
            self.logger.info("=" * 80 + "\n")
    
    def search(self, address: Address, max_results: int = None) -> List[Dict]:
        """
        LEGACY метод - для зворотної сумісності
        Повертає тільки список результатів
        """
        result = self.search_with_confidence(address, max_results)
        return result['manual']
    
    def search_with_confidence(self, address: Address, max_results: int = None) -> Dict:
        """
        НОВИЙ метод - пошук з рівнями впевненості
        
        Args:
            address: Адреса для пошуку
            max_results: Максимум результатів для ручного вибору
            
        Returns:
            {
                'auto': Dict or None,     # Результат для автопідстановки
                'manual': List[Dict],     # Результати для ручного вибору
                'total_found': int,       # Загальна кількість знайдених
                'search_mode': str        # 'auto' або 'manual'
            }
        """
        self._ensure_loaded()
        
        if not self.magistral_records:
            self.logger.error("❌ Magistral records порожні!")
            return self._empty_result()
        
        if max_results is None:
            max_results = config.MAX_SEARCH_RESULTS
        
        # ============ ЛОГУВАННЯ ЗАПИТУ ============
        self.logger.info("=" * 80)
        self.logger.info("🔍 ПОШУК АДРЕСИ")
        self.logger.info("=" * 80)
        self.logger.info("📍 Запит користувача:")
        self.logger.info(f"   Місто:    '{address.city or ''}'")
        self.logger.info(f"   Вулиця:   '{address.street or ''}'")
        self.logger.info(f"   Будинок:  '{address.building or ''}'")
        self.logger.info(f"   Індекс:   '{address.index or ''}'")
        self.logger.info(f"   Область:  '{address.region or ''}'")
        self.logger.info("-" * 80)
        
        # 1. Отримуємо кандидатів
        candidates = self._get_candidates(address)
        
        if not candidates:
            self.logger.info("❌ Кандидатів не знайдено")
            self.logger.info("=" * 80 + "\n")
            return self._empty_result()
        
        # 2. Обчислюємо ЖОРСТКИЙ score
        scored_results = []
        for candidate in candidates:
            score = self._calculate_score_strict(address, candidate)
            
            if score >= config.SIMILARITY_THRESHOLD:
                result = self._create_result(candidate, score)
                scored_results.append(result)
        
        # 3. Сортуємо за score
        scored_results.sort(key=lambda x: x['score'], reverse=True)
        
        # 4. Визначаємо можливість автопідстановки
        auto_result = self._find_auto_result(address, scored_results)
        
        # ============ ЛОГУВАННЯ РЕЗУЛЬТАТІВ ============
        search_mode = 'auto' if auto_result else 'manual'
        
        if auto_result:
            self.logger.info("✅ РЕЖИМ: АВТОМАТИЧНА ПІДСТАНОВКА")
            self.logger.info(f"   Індекс:   [{auto_result['index']}]")
            self.logger.info(f"   Адреса:   {auto_result['city']}, {auto_result['street']}, {auto_result['building']}")
            self.logger.info(f"   Впевненість: {auto_result['confidence']}%")
        else:
            self.logger.info(f"⚠️  РЕЖИМ: РУЧНИЙ ВИБІР (знайдено {len(scored_results)} варіантів)")
            self.logger.info("-" * 80)
            self.logger.info(f"📊 ТОП-{min(len(scored_results), 10)} РЕЗУЛЬТАТІВ:")
            self.logger.info("-" * 80)
            
            for idx, result in enumerate(scored_results[:10], 1):
                confidence = result['confidence']
                index_str = f"[{result['index']}]" if result['index'] else "[-----]"
                
                self.logger.info(
                    f"{idx:2d}. {confidence:3d}% | {index_str:8s} | "
                    f"{result['city']}, {result['street']}, {result['building']}"
                )
        
        self.logger.info("=" * 80 + "\n")
        
        return {
            'auto': auto_result,
            'manual': scored_results[:max_results],
            'total_found': len(scored_results),
            'search_mode': search_mode
        }
    
    def _empty_result(self) -> Dict:
        """Порожній результат"""
        return {
            'auto': None,
            'manual': [],
            'total_found': 0,
            'search_mode': 'none'
        }
    
    def _find_auto_result(self, address: Address, results: List[Dict]) -> Optional[Dict]:

        """Визначає чи можлива автопідстановка"""
        if not results:
            return None
        
        # Фільтруємо результати ≥98%
        perfect_results = [r for r in results if r['confidence'] >= 98]
        
        # Має бути ТІЛЬКИ ОДИН результат з 98%+
        if len(perfect_results) != 1:
            return None
        
        result = perfect_results[0]
        
        # ✅ НОВА ПЕРЕВІРКА: область має збігатися!
        if address.region and address.region.strip():
            query_region = address.region.strip().lower()
            result_region = result.get('region', '').lower()
            
            # Перевіряємо схожість регіонів
            region_sim = self.similarity.jaro_winkler_similarity(query_region, result_region)
            if region_sim < 0.85:
                self.logger.debug(f"Область не збігається: {query_region} vs {result_region}")
                return None
        
        # Перевіряємо індекс якщо заданий користувачем
        if address.index and address.index.strip():
            query_index = address.index.strip().lstrip('0')
            result_index = result['index'].strip().lstrip('0') if result['index'] else ''
            
            if query_index != result_index:
                self.logger.debug(
                    f"Автопідстановка неможлива: індекс не співпадає "
                    f"(запит: {query_index}, результат: {result_index})"
                )
                return None
        
        # Перевіряємо ТОЧНЕ співпадіння будинку
        if address.building and address.building.strip():
            query_building = address.building.upper().replace("-", "").replace(" ", "").strip()
            buildings_list = [
                b.strip().upper().replace("-", "").replace(" ", "") 
                for b in result['buildings'].split(',')
            ]
            
            if query_building not in buildings_list:
                self.logger.debug(
                    f"Автопідстановка неможлива: будинок '{query_building}' "
                    f"відсутній в списку {buildings_list}"
                )
                return None
        
        self.logger.debug("✓ Автопідстановка можлива - всі критерії виконані")
        return result
    
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
        
        # Стратегія 3: Пошук по індексу якщо заданий
        if address.index and len(address.index) >= 4:
            # Тут можна додати пошук по індексу якщо є така можливість
            pass
        
        # Обмежуємо кількість кандидатів
        if len(candidates) > config.MAX_CANDIDATES:
            candidates = candidates[:config.MAX_CANDIDATES]
        
        return candidates
    
    def _calculate_score_strict(self, address: Address, record: MagistralRecord) -> float:
        """
        ЖОРСТКИЙ розрахунок score з ваговою системою
        """
        total_score = 0.0
        
        # Нормалізуємо запит
        query_city = self.normalizer.normalize_city(address.city)
        query_street = self.normalizer.normalize_street(address.street)
        query_region = self.normalizer.normalize_region(address.region)
        query_building = self.normalizer.normalize_text(address.building) if address.building else ""
        
        # ============ 1. ОБЛАСТЬ (10%) - ПЕРЕВІРКА ============
        region_match = False
        if query_region and record.normalized_region:
            region_similarity = self.similarity.jaro_winkler_similarity(
                query_region, 
                record.normalized_region
            )
            region_match = region_similarity >= 0.85
            total_score += region_similarity * 0.10
        
        # Якщо область НЕ ЗБІГАЄТЬСЯ - ВЕЛИКИЙ ШТРАФ (-30%)
        if query_region and not region_match:
            total_score -= 0.30
        
        # ============ 2. МІСТО (35%) - ЖОРСТКИЙ ФІЛЬТР ============
        city_similarity = 0.0
        if query_city and record.normalized_city:
            city_similarity = self.similarity.jaro_winkler_similarity(
                query_city, 
                record.normalized_city
            )
            
            # ЖОРСТКИЙ ФІЛЬТР: місто має бути дуже схожим
            if city_similarity < 0.85:
                return city_similarity * 0.2
            
            total_score += city_similarity * 0.35
        
        # ============ 3. ВУЛИЦЯ (35%) - СПЕЦІАЛЬНА ЛОГІКА ============
        street_similarity = 0.0
        street_found = False
        
        if query_street and record.normalized_street:
            street_similarity = self.similarity.jaro_winkler_similarity(
                query_street, 
                record.normalized_street
            )
            street_found = street_similarity >= 0.75
            
            if street_found:
                # Вулиця ЗНАЙДЕНА - звичайна вага
                total_score += street_similarity * 0.35
            else:
                # Вулиця НЕ знайдена - ШТРАФ
                total_score += street_similarity * 0.10
        
        # ============ 4. СПЕЦІАЛЬНИЙ РЕЖИМ: Вулиця не знайдена для НЕ-КИЇВА ============
        if query_city and not street_found:
            # Перевіряємо чи Київ
            is_kyiv = "київ" in query_city.lower()
            
            if not is_kyiv and city_similarity >= 0.85:
                # НЕ-КИЇВ і місто знайдено, але вулиця НІ
                # Використовуємо НОВИЙ РЕЖИМ: тільки місто + область (50/50)
                total_score = 0.0
                total_score += city_similarity * 0.50
                
                if region_match:
                    total_score += 0.50
                else:
                    total_score += 0.25  # Штраф за неправильну область
                
                # Позначаємо спеціальний режим
                record.special_mode = True
        else:
            record.special_mode = False
        
        # ============ 5. БУДИНОК (15%) - ТІЛЬКИ якщо вулиця знайдена ============
        if street_found and query_building and record.buildings:
            buildings_list = [b.strip().upper().replace("-", "").replace(" ", "") 
                             for b in record.buildings.split(',')]
            query_building_clean = query_building.upper().replace("-", "").replace(" ", "")
            
            if query_building_clean in buildings_list:
                total_score += 0.15
            else:
                for building in buildings_list:
                    if query_building_clean in building or building in query_building_clean:
                        total_score += 0.10
                        break
        
        # ============ БОНУС ============
        if city_similarity > 0.95 and street_similarity > 0.80:
            total_score += 0.05
        
        return max(0.0, min(total_score, 1.0))

    
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
