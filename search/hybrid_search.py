"""
Гібридний пошук адрес v3.0 - з рівнями впевненості
Комбінує Jaro-Winkler, Levenshtein, Fuzzy matching, N-grams
"""
import re
from typing import List, Dict, Optional
from models.address import Address
from models.magistral_record import MagistralRecord
from search.normalizer import TextNormalizer
from search.similarity import SimilarityCalculator
from search.magistral_loader import MagistralLoader
from search.ukrposhta_classifier import UkrposhtaClassifierClient
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
        self.classifier = UkrposhtaClassifierClient() if config.UKRPOSHTA_CLASSIFIER_ENABLED else None
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

        if address.street and address.building:
            street_norm = self.normalizer.normalize_text(address.street)
            building_norm = self.normalizer.normalize_text(address.building)
            if street_norm and street_norm == building_norm:
                address.building = ""

        self._preprocess_region_district(address)
        self._preprocess_full_address(address)
        
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
        
        # 2. Обчислюємо ЖОРСТКИЙ score
        scored_results = []
        for candidate in candidates:
            score = self._calculate_score_strict(address, candidate)
            
            if score >= config.SIMILARITY_THRESHOLD:
                result = self._create_result(candidate, score, address)
                scored_results.append(result)

        classifier_results = self._get_classifier_results(address)
        if classifier_results:
            self.logger.info(f"💡 Класифікатор Укрпошти додав результатів: {len(classifier_results)}")
            scored_results.extend(classifier_results)

        if not scored_results:
            self.logger.info("❌ Кандидатів не знайдено")
            self.logger.info("=" * 80 + "\n")
            return self._empty_result()
        
        # 3. Сортуємо за score
        scored_results.sort(key=lambda x: x['score'], reverse=True)
        scored_results = self._deduplicate_equivalent_results(scored_results)
        
        # 4. Визначаємо можливість автопідстановки
        auto_result = self._find_auto_result(address, scored_results)
        
        # ============ 5. ЛОГІКА "ЗАГАЛЬНОГО ІНДЕКСУ" (для не-Києва) ============
        # ============ 5. ЛОГІКА "ЗАГАЛЬНОГО ІНДЕКСУ" (для не-Києва) ============
        # Якщо автопідстановка не знайдена, і це не Київ - шукаємо загальний індекс
        # Нормалізуємо місто запиту
        query_city_norm = self.normalizer.normalize_city(address.city) if address.city else ""
        
        # Великі міста, для яких ми НЕ хочемо "загальний індекс" (бо там багато відділень)
        # і для яких ми хочемо пріоритет "м. Місто" над "с. Місто"
        major_cities = ['київ', 'м.київ', 'киів', 'донецьк', 'м.донецьк', 'харків', 'одеса', 'дніпро', 'львів', 'запоріжжя']
        is_major_city_query = query_city_norm in major_cities
        
        # Якщо це запит на велике місто - ми НЕ шукаємо загальні індекси
        if not auto_result and not is_major_city_query and address.city:
            # Шукаємо загальні результати (по місту)
            general_results = self._find_general_city_results(address)
            
            if general_results:
                self.logger.info(f"💡 Знайдено {len(general_results)} загальних індексів для '{address.city}'")
                
                # Додаємо їх до результатів (якщо їх ще немає там)
                # Перевіряємо дублікати по індексу
                existing_indices = {r['index'] for r in scored_results}
                
                for gen_res in general_results:
                    if gen_res['index'] not in existing_indices:
                        scored_results.append(gen_res)
                
                # Сортуємо знову
                scored_results.sort(key=lambda x: x['score'], reverse=True)
                scored_results = self._deduplicate_equivalent_results(scored_results)
                
                # Спробуємо знайти авто-результат знову (вже з загальними)
                # Для загальних індексів дозволяємо автопідстановку якщо це єдиний варіант
                if len(general_results) == 1 and not address.region:
                     # Якщо не вказана область, але знайшли тільки одне місто з такою назвою - це успіх
                     pass
                
                # Оновлюємо auto_result якщо він з'явився (або якщо ми вирішили що загальний підходить)
                if not auto_result:
                    auto_result = self._find_auto_result(address, scored_results, allow_general=True)

        post_office_recommendation = self._find_post_office_recommendation(address, auto_result, scored_results)
        if post_office_recommendation:
            scored_results = self._append_post_office_recommendation(scored_results, post_office_recommendation)
        
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

    def _preprocess_full_address(self, address: Address) -> None:
        """Extract city, street and building when the street field contains a full address."""
        if not address.street or "," not in address.street:
            return

        parts = [p.strip() for p in address.street.split(",") if p.strip()]
        if len(parts) < 2:
            return

        first_part_with_index = re.match(r"^(\d{4,5})\s+(.+)$", parts[0])
        if first_part_with_index:
            parts[0] = first_part_with_index.group(2).strip()
        elif re.fullmatch(r"\d{4,5}", parts[0]):
            parts = parts[1:]

        while parts and self.normalizer.normalize_text(parts[0]) in {"україна", "украина", "ukraine"}:
            parts = parts[1:]

        if len(parts) < 2:
            return

        city = ""
        street_idx = 0 if address.city else 1

        for idx, part in enumerate(parts[:3]):
            part_norm = self.normalizer.normalize_text(part)
            if re.match(r"^(м|г|місто|город|с|смт|с-ще)\.?\s*", part_norm):
                city = part
                street_idx = idx + 1
                break

        if not city:
            if address.city and parts:
                first_part_city = self.normalizer.normalize_city(parts[0])
                current_city = self.normalizer.normalize_city(address.city)
                if first_part_city and current_city and first_part_city == current_city:
                    street_idx = 1
            elif not address.city:
                city = parts[0]
                street_idx = 1

        if city and (not address.city or re.match(r"^г\.?\s*", address.city.strip(), re.IGNORECASE)):
            address.city = city

        if street_idx >= len(parts):
            return

        street = parts[street_idx]
        building_parts = parts[street_idx + 1:]

        if street:
            address.street = street

        if not address.building and building_parts:
            building = self._extract_building_from_full_address_parts(building_parts)
            if building:
                address.building = building

    @staticmethod
    def _preprocess_region_district(address: Address) -> None:
        region = (address.region or "").lower()
        district = (address.district or "").lower()
        region_looks_like_district = bool(re.search(r"\b(р-н|район)\b", region))
        district_looks_like_region = bool(re.search(r"\b(обл\.?|область)\b", district))

        if region_looks_like_district and district_looks_like_region:
            address.region, address.district = address.district, address.region
            return

        region_looks_like_region = bool(re.search(r"\b(обл\.?|область)\b", region))
        bare_region_looks_like_district = bool(
            region and not region_looks_like_region and re.search(r"(ський|цький|зький)$", region)
        )
        if bare_region_looks_like_district and not address.district:
            address.district = address.region
            address.region = ""

    @staticmethod
    def _extract_building_from_full_address_parts(parts: List[str]) -> str:
        building_pattern = r"\d+(?:[-/]\d+)?(?:[-\s]?[а-яА-Яa-zA-ZіїєґІЇЄҐ])?"
        apartment_prefix = r"^\s*(?:кв\.?|квартира|пом\.?|прим\.?|офіс|оф\.?|office|apt\.?)\b"

        def find_building(value: str, require_building_prefix: bool) -> str:
            if re.search(apartment_prefix, value, flags=re.IGNORECASE):
                return ""

            if require_building_prefix:
                match = re.search(
                    rf"(?:буд\.?|будинок|д\.?)\s*({building_pattern})(?=\s|,|$|корп|корпус|кв|офіс)",
                    value,
                    flags=re.IGNORECASE,
                )
                return match.group(1).strip() if match else ""

            match = re.search(
                rf"({building_pattern})(?=\s|,|$|корп|корпус|кв|офіс)",
                value,
                flags=re.IGNORECASE,
            )
            return match.group(1).strip() if match else ""

        for part in parts:
            value = part.strip()
            if not value or value in {"*", "#", "#-"}:
                continue

            building = find_building(value, require_building_prefix=True)
            if building:
                return building

        for part in parts:
            value = part.strip()
            if not value or value in {"*", "#", "#-"}:
                continue

            building = find_building(value, require_building_prefix=False)
            if building:
                return building

        return ""
    
    def _find_general_city_results(self, address: Address) -> List[Dict]:
        """
        Шукає "загальні" результати для міста (найнижчий індекс),
        коли точна вулиця не знайдена.
        Повертає список варіантів (якщо є кілька населених пунктів з такою назвою).
        """
        if not address.city:
            return []
            
        candidates = self.loader.get_candidates_by_city_prefix(address.city)
        if not candidates:
            return []
            
        norm_city = self.normalizer.normalize_city(address.city)
        norm_region = self.normalizer.normalize_region(address.region) if address.region else None
        
        # Групуємо по унікальних населених пунктах (Область + Район + Місто)
        unique_cities = {}
        
        for record in candidates:
            if record.normalized_city != norm_city:
                continue
                
            # Якщо задана область - фільтруємо
            if norm_region and record.normalized_region != norm_region:
                continue
                
            # Ключ для групування: Область + Район
            key = (record.region, record.new_district or record.old_district)
            
            if key not in unique_cities:
                unique_cities[key] = []
            unique_cities[key].append(record)
            
        results = []
        
        for (region, district), records in unique_cities.items():
            # Знаходимо мінімальний індекс для цього міста
            indices = [r.city_index for r in records if r.city_index and len(r.city_index) == 5 and r.city_index.isdigit()]
            if not indices:
                continue
                
            min_index = min(indices)
            
            # Створюємо "загальний" результат
            # Беремо перший запис як шаблон для назв
            template = records[0]
            
            result = {
                'region': region,
                'district': district,
                'city': template.city,
                'city_ua': template.city,
                'street': "Загальний для н.п. (вулицю не знайдено)", # Спеціальна позначка
                'street_ua': "Загальний для н.п.",
                'building': '',
                'buildings': '',
                'index': min_index,
                'score': 0.89, # Трохи менше ніж поріг точного (0.90), але достатньо високо
                'confidence': 89,
                'features': 'Загальний індекс',
                'not_working': '',
                'is_working': True,
                'is_general': True # Прапор що це загальний індекс
            }
            results.append(result)
            
        return results

    def _deduplicate_equivalent_results(self, results: List[Dict]) -> List[Dict]:
        """Згортає однакові адресні результати, які відрізняються тільки індексом."""
        deduped = {}

        for result in results:
            key = (
                self.normalizer.normalize_text(result.get('region', '')),
                self.normalizer.normalize_text(result.get('district', '')),
                self.normalizer.normalize_city(result.get('city', '')),
                self.normalizer.normalize_street(result.get('street', '')),
                self._normalize_building_for_match(result.get('building') or result.get('buildings', '')),
                bool(result.get('is_general')),
            )
            existing = deduped.get(key)
            if not existing:
                deduped[key] = result
                continue

            result_confidence = result.get('confidence', 0)
            existing_confidence = existing.get('confidence', 0)
            result_index = str(result.get('index') or '')
            existing_index = str(existing.get('index') or '')

            if (
                result_confidence > existing_confidence
                or (
                    result_confidence == existing_confidence
                    and result_index
                    and (not existing_index or result_index < existing_index)
                )
            ):
                deduped[key] = result

        return sorted(
            deduped.values(),
            key=lambda r: (r.get('score', 0), r.get('confidence', 0)),
            reverse=True,
        )

    def _find_auto_result(self, address: Address, results: List[Dict], allow_general: bool = False) -> Optional[Dict]:
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
        # АБО якщо це загальний індекс і дозволено (score >= 0.85)
        perfect_results = []
        for r in results:
            if r['confidence'] >= config.AUTO_MATCH_CONFIDENCE:
                perfect_results.append(r)
            elif allow_general and r.get('is_general') and r['score'] >= 0.85:
                perfect_results.append(r)

        query_index = self._normalize_query_index(address.index)
        if query_index:
            index_matched_results = [
                r for r in perfect_results
                if (r.get('index') or '').strip().lstrip('0') == query_index
            ]
            if index_matched_results:
                perfect_results = index_matched_results
        
        # Має бути ТІЛЬКИ ОДИН результат з високою впевненістю
        if len(perfect_results) != 1:
            ordered_by_confidence = sorted(
                perfect_results,
                key=lambda r: (r.get('confidence', 0), r.get('score', 0)),
                reverse=True,
            )
            if (
                len(ordered_by_confidence) >= 2
                and ordered_by_confidence[0].get('confidence', 0) >= getattr(config, 'AUTO_INDEX_CORRECTION_CONFIDENCE', 98)
                and ordered_by_confidence[0].get('confidence', 0) > ordered_by_confidence[1].get('confidence', 0)
            ):
                perfect_results = [ordered_by_confidence[0]]

        if len(perfect_results) != 1:
            very_high_results = [
                r for r in perfect_results
                if r.get('confidence', 0) >= 98
            ]
            if len(very_high_results) == 1:
                perfect_results = very_high_results

        if len(perfect_results) != 1:
            unique_indexes = {
                (r.get('index') or '').strip().lstrip('0')
                for r in perfect_results
                if r.get('index')
            }
            if len(unique_indexes) != 1:
                self.logger.debug(f"Автопідстановка неможлива: знайдено {len(perfect_results)} результатів ≥{config.AUTO_MATCH_CONFIDENCE}%")
                return None
        
        result = perfect_results[0]
        
        # Перевіряємо індекс якщо заданий користувачем
        if query_index:
            result_index = result['index'].strip().lstrip('0') if result['index'] else ''
            
            if query_index != result_index:
                can_correct_index = (
                    getattr(config, 'ALLOW_AUTO_INDEX_CORRECTION', False)
                    and not result.get('is_general')
                    and result.get('confidence', 0) >= getattr(config, 'AUTO_INDEX_CORRECTION_CONFIDENCE', 98)
                )
                if not can_correct_index:
                    self.logger.debug(
                        f"Автопідстановка неможлива: індекс не співпадає "
                        f"(запит: {query_index}, результат: {result_index})"
                    )
                    return None
                self.logger.debug(
                    f"Автопідстановка виправляє індекс: "
                    f"{query_index} -> {result_index} ({result.get('confidence', 0)}%)"
                )
        
        # Перевіряємо ТОЧНЕ співпадіння будинку (ТІЛЬКИ для НЕ загальних результатів)
        if not result.get('is_general') and address.building and address.building.strip():
            query_building = self._normalize_building_for_match(address.building)
            raw_buildings_list = [b.strip() for b in result['buildings'].split(',')]
            buildings_list = [
                self._normalize_building_for_match(b)
                for b in raw_buildings_list
            ]
            
            query_building_base = self._building_base(address.building)
            base_buildings = [self._building_base(b) for b in raw_buildings_list]
            base_match_allowed = self._has_letter_suffix(address.building)
            if query_building not in buildings_list and (
                not base_match_allowed
                or not query_building_base
                or query_building_base not in base_buildings
            ):
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
            postcode_candidates = self.loader.get_candidates_by_postcode(address.index)
            existing_ids = {id(c) for c in candidates}
            for pc in postcode_candidates:
                if id(pc) not in existing_ids:
                    candidates.append(pc)
                    existing_ids.add(id(pc))
        
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
        query_street_options = self.normalizer.normalize_street_aliases(address.street, address.city)
        query_street = query_street_options[0] if query_street_options else ""
        query_street_type = self.normalizer.detect_street_type(address.street)
        query_building = self.normalizer.normalize_text(address.building) if address.building else ""
        query_index = self._normalize_query_index(address.index)
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
            
            # БОНУС ДЛЯ ВЕЛИКИХ МІСТ (Столиця + Обласні центри)
            # Якщо запит "Київ"/"Донецьк" і результат "м. Київ"/"м. Донецьк" - даємо бонус
            major_cities_bonus = ['київ', 'донецьк', 'харків', 'одеса', 'дніпро', 'львів', 'запоріжжя']
            
            if query_city in major_cities_bonus or query_city in ['м.' + c for c in major_cities_bonus]:
                 if record.normalized_city in major_cities_bonus:
                    # Перевіряємо що це саме місто (зазвичай область співпадає або порожня)
                    # Для Києва область Київ або порожня
                    # Для Донецька область Донецька
                    is_major = True # Спрощена перевірка, бо normalized_city вже перевірено
                    
                    if is_major:
                        total_score += config.SCORE_CAPITAL_BONUS
        
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
            street_similarity = max(
                self.similarity.token_similarity(street_option, record.normalized_street)
                for street_option in query_street_options
            )
            record_street_type = self.normalizer.detect_street_type(record.street)
            if query_street_type and record_street_type and query_street_type != record_street_type:
                street_similarity = max(0.0, street_similarity - 0.25)
            
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
            raw_buildings_list = [b.strip() for b in record.buildings.split(',')]
            buildings_list = [
                self._normalize_building_for_match(b)
                for b in raw_buildings_list
            ]
            query_building_clean = self._normalize_building_for_match(query_building)
            
            if query_building_clean in buildings_list:
                # ТОЧНЕ СПІВПАДІННЯ - повний бонус
                building_bonus = config.SCORE_BUILDING_EXACT_BONUS
                total_score += building_bonus
            else:
                query_building_base = self._building_base(query_building)
                base_buildings = [self._building_base(b) for b in raw_buildings_list]
                if (
                    self._has_letter_suffix(query_building)
                    and query_building_base
                    and query_building_base in base_buildings
                ):
                    building_bonus = 0.12
                    total_score += building_bonus
                    found_partial = True
                else:
                    found_partial = False

                    # Часткове співпадіння (наприклад, "27" в "27А")
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
                total_score += max(config.SCORE_INDEX_WEIGHT, 0.10)
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

    @staticmethod
    def _normalize_building_for_match(building: str) -> str:
        return str(building or "").upper().replace("-", "").replace(" ", "").strip()

    @staticmethod
    def _building_base(building: str) -> str:
        cleaned = str(building or "").upper().replace(" ", "").strip()
        match = re.match(r"^(\d+(?:/\d+)?)(?:-?[A-ZА-ЯІЇЄҐ])?$", cleaned, flags=re.IGNORECASE)
        return match.group(1) if match else ""

    @staticmethod
    def _has_letter_suffix(building: str) -> bool:
        cleaned = str(building or "").upper().replace(" ", "").strip()
        return bool(re.match(r"^\d+(?:/\d+)?-?[A-ZА-ЯІЇЄҐ]$", cleaned, flags=re.IGNORECASE))

    @staticmethod
    def _normalize_query_index(index: str) -> str:
        if not index:
            return ""

        cleaned = str(index).strip().replace(" ", "").replace("\x00", "")
        if cleaned in {"*", "00000", "01000"}:
            return ""
        if not cleaned.isdigit():
            return ""
        return cleaned.lstrip('0')
    
    def _confidence_for_result(self, record: MagistralRecord, score: float, address: Address = None) -> int:
        confidence = int(score * 100)
        if not address or confidence < 100:
            return confidence

        query_street_options = self.normalizer.normalize_street_aliases(address.street, address.city)
        record_street = record.normalized_street or self.normalizer.normalize_street(record.street)
        exact_street = record_street and record_street in query_street_options

        query_building = self._normalize_building_for_match(address.building)
        raw_buildings_list = [b.strip() for b in str(record.buildings or "").split(",") if b.strip()]
        exact_building = (
            not query_building
            or query_building in [self._normalize_building_for_match(b) for b in raw_buildings_list]
        )

        if not exact_street or not exact_building:
            return 99
        return confidence

    def _create_result(self, record: MagistralRecord, score: float, address: Address = None) -> Dict:
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
            'confidence': self._confidence_for_result(record, score, address),
            'features': record.features,
            'not_working': record.not_working,
            'is_working': record.is_working()
        }

    def _get_classifier_results(self, address: Address) -> List[Dict]:
        if not self.classifier:
            return []

        records = []
        seen = set()

        query_index = self._normalize_query_index(address.index)
        if query_index:
            for item in self.classifier.get_addresses_by_postcode(address.index):
                record = self._record_from_classifier_address(item)
                self._add_classifier_record(records, seen, record)

        if address.city and address.street:
            cities = self._rank_classifier_cities(address)
            for city in cities[:config.UKRPOSHTA_CLASSIFIER_MAX_CITIES]:
                for street in self.classifier.get_streets_by_name(city.city_id, address.street)[:config.UKRPOSHTA_CLASSIFIER_MAX_STREETS]:
                    houses = self.classifier.get_houses_by_street_id(street.street_id, address.building)
                    if not houses and address.building:
                        houses = self.classifier.get_houses_by_street_id(street.street_id)
                    for house_number, postcode in houses[:config.UKRPOSHTA_CLASSIFIER_MAX_RESULTS]:
                        record = MagistralRecord(
                            region=street.region or city.region,
                            new_district=street.district or city.district,
                            city=f"{street.city_type_short} {street.city}".strip(),
                            city_index=postcode,
                            street=f"{street.street_type_short} {street.street}".strip(),
                            buildings=house_number,
                        )
                        self._prepare_classifier_record(record)
                        self._add_classifier_record(records, seen, record)

        results = []
        for record in records:
            score = self._calculate_score_strict(address, record)
            if score < config.SIMILARITY_THRESHOLD:
                continue
            result = self._create_result(record, score, address)
            result['source'] = 'ukrposhta_classifier'
            result['source_label'] = 'Класифікатор Укрпошти'
            results.append(result)

        results.sort(key=lambda r: (r.get('score', 0), r.get('confidence', 0)), reverse=True)
        return results[:config.UKRPOSHTA_CLASSIFIER_MAX_RESULTS]

    def _rank_classifier_cities(self, address: Address):
        cities = self.classifier.get_cities_by_name(address.city)
        query_city = self.normalizer.normalize_city(address.city)
        query_region = self.normalizer.normalize_region(address.region) if address.region else ""
        query_district = self.normalizer.normalize_text(address.district) if address.district else ""

        def score(city):
            value = self.similarity.token_similarity(query_city, self.normalizer.normalize_city(city.city))
            if city.old_city:
                value = max(value, self.similarity.token_similarity(query_city, self.normalizer.normalize_city(city.old_city)))
            if query_region:
                value += self.similarity.token_similarity(query_region, self.normalizer.normalize_region(city.region)) * 0.25
            if query_district:
                value += self.similarity.token_similarity(query_district, self.normalizer.normalize_text(city.district)) * 0.15
            value += min(city.population, 1000000) / 10000000
            return value

        return sorted(cities, key=score, reverse=True)

    def _record_from_classifier_address(self, item) -> MagistralRecord:
        record = MagistralRecord(
            region=item.region,
            new_district=item.district,
            city=f"{item.city_type_short} {item.city}".strip(),
            city_index=item.postcode,
            street=f"{item.street_type_short} {item.street}".strip(),
            buildings=item.house_number,
        )
        self._prepare_classifier_record(record)
        return record

    def _prepare_classifier_record(self, record: MagistralRecord) -> None:
        record.normalized_city = self.normalizer.normalize_city(record.city)
        record.normalized_street = self.normalizer.normalize_street(record.street)
        record.normalized_region = self.normalizer.normalize_region(record.region)

    def _add_classifier_record(self, records: List[MagistralRecord], seen: set, record: MagistralRecord) -> None:
        key = (
            self.normalizer.normalize_region(record.region),
            self.normalizer.normalize_text(record.new_district or record.old_district),
            self.normalizer.normalize_city(record.city),
            self.normalizer.normalize_street(record.street),
            self._normalize_building_for_match(record.buildings),
            self._normalize_query_index(record.city_index),
        )
        if key in seen:
            return
        seen.add(key)
        records.append(record)

    def _find_post_office_recommendation(self, address: Address, auto_result: Dict = None, results: List[Dict] = None) -> Optional[Dict]:
        if not self.classifier:
            return None

        anchor = auto_result or (results[0] if results else None)
        anchor_index = (anchor or {}).get('index') or address.index
        anchor_not_working = (anchor or {}).get('not_working', '')
        should_show = bool(anchor_not_working and 'Тимчасово не функціонує' in anchor_not_working)
        if not should_show and (address.index in ("*", "00000", "01000", "") or not address.index):
            should_show = bool(address.city)
        if not should_show:
            return None

        city_query = (anchor or {}).get('city') or address.city
        city_candidates = self.classifier.get_cities_by_name(city_query)
        if not city_candidates and address.city and address.city != city_query:
            city_candidates = self.classifier.get_cities_by_name(address.city)

        offices = []
        for city in city_candidates[:config.UKRPOSHTA_CLASSIFIER_MAX_CITIES]:
            offices.extend(self.classifier.get_post_offices_by_city_id(city.city_id))

        working = [office for office in offices if office.is_working() and office.postcode]
        if not working:
            return None

        target_index = self._normalize_query_index(anchor_index)

        def distance(office):
            office_index = self._normalize_query_index(office.postcode)
            if target_index and office_index:
                return abs(int(office_index) - int(target_index))
            return 0

        best = sorted(working, key=lambda office: (distance(office), office.postcode, office.street))[0]
        return {
            'source': 'post_office_recommendation',
            'source_label': 'Найближче робоче відділення',
            'is_post_office_recommendation': True,
            'region': (anchor or {}).get('region', ''),
            'district': (anchor or {}).get('district', ''),
            'city': f"{best.city_type_short} {best.city}".strip(),
            'city_ua': f"{best.city_type_short} {best.city}".strip(),
            'street': best.street,
            'street_ua': best.street,
            'building': best.house_number,
            'buildings': best.house_number,
            'index': best.postcode,
            'score': 0,
            'confidence': 0,
            'features': best.type_long or best.type_acronym or 'Робоче відділення',
            'not_working': '',
            'is_working': True,
            'postoffice_id': best.postoffice_id,
            'anchor_index': anchor_index or '',
        }

    @staticmethod
    def _append_post_office_recommendation(results: List[Dict], recommendation: Dict) -> List[Dict]:
        return [r for r in results if not r.get('is_post_office_recommendation')] + [recommendation]
    
    def get_statistics(self) -> Dict:
        """Повертає статистику системи"""
        self._ensure_loaded()
        return {
            'total_records': len(self.magistral_records),
            'indexed_cities': len(self.loader.index_by_city_prefix),
            'indexed_regions': len(self.loader.index_by_region)
        }
