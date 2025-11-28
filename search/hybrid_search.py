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
        
        # ============ 0. ПОПЕРЕДНЯ ОБРОБКА ============
        # Спроба витягнути місто з вулиці, якщо місто не вказано
        if not address.city and address.street:
            extracted_city, cleaned_street = self.normalizer.try_extract_city(address.street)
            if extracted_city:
                self.logger.info(f"💡 Витягнуто місто з вулиці: '{extracted_city}' (вулиця: '{cleaned_street}')")
                address.city = extracted_city
                address.street = cleaned_street
        
        # Спроба витягнути будинок з вулиці, якщо будинок не вказано
        if not address.building and address.street:
            extracted_building, cleaned_street_b = self.normalizer.try_extract_building(address.street)
            if extracted_building:
                self.logger.info(f"💡 Витягнуто будинок з вулиці: '{extracted_building}' (вулиця: '{cleaned_street_b}')")
                address.building = extracted_building
                address.street = cleaned_street_b
        
        # ============ СПЕЦІАЛЬНА ОБРОБКА: абонентська скринька ============
        if address.street and ('а/с' in address.street.lower() or 'п/с' in address.street.lower() or 'абонент' in address.street.lower()):
            if 'київ' in address.city.lower():
                result = {
                    'region': 'Київ',
                    'district': 'Київ',
                    'city': 'м. Київ',
                    'city_ua': 'м. Київ',
                    'street': f'{address.street} (Головпоштамт)',
                    'street_ua': f'{address.street} (Головпоштамт)',
                    'building': '',
                    'buildings': '',
                    'index': '01001',
                    'score': 0.95,
                    'confidence': 95,
                    'features': 'Абонентська скринька',
                    'not_working': '',
                    'is_working': True
                }
                self.logger.info("=" * 80)
                self.logger.info("✅ СПЕЦІАЛЬНА ОБРОБКА: Абонентська скринька")
                self.logger.info(f"   {address.street} → Індекс 01001")
                self.logger.info("=" * 80 + "\n")
                
                return {
                    'auto': result,
                    'manual': [result],
                    'total_found': 1,
                    'search_mode': 'auto'
                }
        
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
        """
        Визначає чи можлива автопідстановка
        
        ЖОРСТКІ критерії:
        1. ТІЛЬКИ ОДИН результат з ≥98%
        2. Індекс співпадає з запитом (якщо є)
        3. Будинок ТОЧНО співпадає (не часткове!)
        4. Місто ≥95%
        5. Вулиця ≥90%
        
        Returns:
            Dict з результатом або None
        """
        if not results:
            return None
        
        # Фільтруємо результати ≥ AUTO_MATCH_CONFIDENCE
        perfect_results = [r for r in results if r['confidence'] >= config.AUTO_MATCH_CONFIDENCE]
        
        # Має бути ТІЛЬКИ ОДИН результат з високою впевненістю
        if len(perfect_results) != 1:
            self.logger.debug(f"Автопідстановка неможлива: знайдено {len(perfect_results)} результатів ≥{config.AUTO_MATCH_CONFIDENCE}%")
            return None
        
        result = perfect_results[0]
        
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
        ЖОРСТКИЙ розрахунок score для високої точності
        
        Вагова система:
        - Місто: 35%
        - Вулиця: 35%
        - Будинок: 25%
        - Індекс: 5%
        
        З жорсткими фільтрами та штрафами
        """
        total_score = 0.0
        
        # Нормалізуємо запит
        query_city = self.normalizer.normalize_city(address.city)
        query_street = self.normalizer.normalize_street(address.street)
        query_building = self.normalizer.normalize_text(address.building) if address.building else ""
        query_index = address.index.strip().lstrip('0') if address.index else ""
        query_region = self.normalizer.normalize_region(address.region) if address.region else ""
        
        # ============ 1. МІСТО (35%) - ЖОРСТКИЙ ФІЛЬТР ============
        city_similarity = 0.0
        if query_city and record.normalized_city:
            # Використовуємо token_similarity для міста теж (щоб "Київ м." == "м. Київ")
            city_similarity = self.similarity.token_similarity(
                query_city, 
                record.normalized_city
            )
            
            # ЖОРСТКИЙ ФІЛЬТР: місто має бути дуже схожим
            if city_similarity < config.SCORE_CITY_THRESHOLD:
                # Якщо місто не схоже - максимум 17% score
                return city_similarity * 0.2
            
            total_score += city_similarity * config.SCORE_CITY_WEIGHT
        
        # ============ ФІЛЬТР РЕГІОНУ (НОВЕ!) ============
        # Якщо область задана, перевіряємо її строго
        if query_region:
            record_region = self.normalizer.normalize_region(record.region) if record.region else ""
            
            if record_region:
                # Використовуємо token_similarity для регіону
                region_sim = self.similarity.token_similarity(query_region, record_region)
                if region_sim < config.SCORE_REGION_THRESHOLD:
                    # Регіон НЕ збігся - не повертаємо результат з іншого регіону
                    return 0.0
        
        # ============ 2. ВУЛИЦЯ (35%) - ЖОРСТКИЙ ФІЛЬТР ============
        street_similarity = 0.0
        if query_street and record.normalized_street:
            # Використовуємо token_similarity для ігнорування порядку слів
            street_similarity = self.similarity.token_similarity(
                query_street, 
                record.normalized_street
            )
            
            # ЖОРСТКИЙ ФІЛЬТР: вулиця має бути досить схожою
            if street_similarity < config.SCORE_STREET_THRESHOLD:
                # Якщо вулиця не схожа - великий штраф
                total_score += street_similarity * 0.10  # Замість 35% тільки 10%
            else:
                total_score += street_similarity * config.SCORE_STREET_WEIGHT
        
        # ============ 3. БУДИНОК (25%) - КРИТИЧНО ВАЖЛИВО! ============
        building_bonus = 0.0
        if query_building and record.buildings:
            # Очищаємо будинок від дефісів та пробілів
            buildings_list = [
                b.strip().upper().replace("-", "").replace(" ", "") 
                for b in record.buildings.split(',')
            ]
            query_building_clean = query_building.upper().replace("-", "").replace(" ", "")
            
            if query_building_clean in buildings_list:
                # ТОЧНЕ СПІВПАДІННЯ - повний бонус
                building_bonus = config.SCORE_BUILDING_EXACT_BONUS
                total_score += building_bonus
            else:
                # Часткове співпадіння (наприклад, "27" в "27А")
                found_partial = False
                for building in buildings_list:
                    if query_building_clean in building or building in query_building_clean:
                        # Часткове співпадіння - зменшений бонус
                        building_bonus = config.SCORE_BUILDING_PARTIAL_BONUS
                        total_score += building_bonus
                        found_partial = True
                        break
                
                # Якщо будинок взагалі не знайдено - ШТРАФ
                if not found_partial:
                    total_score -= config.SCORE_BUILDING_PENALTY  # Штраф
        
        # ============ 4. ІНДЕКС (5%) ============
        # ============ 4. ІНДЕКС (5%) ============
        if query_index and record.city_index:
            # Нормалізація індексу (видалення пробілів, нулів на початку)
            q_idx = query_index.replace(" ", "").replace("\x00", "").lstrip('0')
            r_idx = record.city_index.strip().replace(" ", "").replace("\x00", "").lstrip('0')
            
            if q_idx == r_idx:
                total_score += config.SCORE_INDEX_WEIGHT
            else:
                # Індекс не співпадає - невеликий штраф
                total_score -= 0.02
        
        # ============ БОНУС ЗА ІДЕАЛЬНЕ СПІВПАДІННЯ ============
        # Якщо все майже ідеально - додатковий бонус
        # Вимоги: City >= 0.95, Street >= 0.95, Building EXACT match
        if city_similarity >= 0.95 and street_similarity >= 0.95 and building_bonus >= config.SCORE_BUILDING_EXACT_BONUS:
            total_score += config.SCORE_PERFECT_MATCH_BONUS  # Бонус
        
        # Обмежуємо score від 0 до 1
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
