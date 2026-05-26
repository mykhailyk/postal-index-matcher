"""
Нормалізація українського тексту для пошуку адрес
"""
import csv
import os
import re
import config


class TextNormalizer:
    """Клас для нормалізації тексту"""
    
    def __init__(self):
        # Транслітерація російська → українська
        self.transliteration_map = {
            'ы': 'и',
            'э': 'е',
            'ё': 'е',
            'ъ': '',
            'щ': 'щ',
            # Додаткові варіанти
            'й': 'й',
            'і': 'і',
            'ї': 'і',
            'є': 'є',
        }
        
        # Словник перейменувань (стара назва -> нова назва)
        self.city_renames = {
            'киев': 'київ',
            'харьков': 'харків',
            'днепр': 'дніпро',
            'днепропетровск': 'дніпро',
            'львов': 'львів',
            'николаев': 'миколаїв',
            'пятихатки': "п'ятихатки",
            'сєвєродонецьк': 'сіверськодонецьк',
            'северодонецк': 'сіверськодонецьк',
            'димитров': 'мирноград',
            'красноармійськ': 'покровськ',
            'артемівськ': 'бахмут',
            'дніпропетровськ': 'дніпро',
            'кіровоград': 'кропивницький',
            'дніпродзержинськ': 'кам\'янське',
            'новоград-волинський': 'звягель',
            'володимир-волинський': 'володимир',
            'переяслав-хмельницький': 'переяслав',
            'іллічівськ': 'чорноморськ',
            'комсомольськ': 'горішні плавні',
            'кузнецовськ': 'вараш',
            'южне': 'південне',
            'червоноград': 'шептицький',
        }
        self.street_renames_by_city = {
            self.normalize_text('Бахмут'): {
                self.normalize_text('Горького'): 'Олекси Тихого',
            },
        }
        self.global_street_renames = {
            self.normalize_text('без назви'): 'відсутня',
        }
        self._load_street_aliases()
    
    def normalize_text(self, text: str) -> str:
        """
        Повна нормалізація тексту
        
        Args:
            text: Вхідний текст
            
        Returns:
            Нормалізований текст
        """
        if not text:
            return ""
        
        # 1. Видаляємо зайві пробіли
        text = ' '.join(text.split())
        
        # 2. Lower case
        text = text.lower()
        
        # 3. Транслітерація
        text = self._transliterate(text)
        
        # 4. Видаляємо спецсимволи (крім дефіса)
        text = re.sub(r'[^\w\s\-]', ' ', text, flags=re.UNICODE)
        
        # 5. Знову видаляємо зайві пробіли
        text = ' '.join(text.split())
        
        return text.strip()
    
    def normalize_city(self, city: str) -> str:
        """Нормалізує назву міста"""
        if not city:
            return ""
        
        # Видаляємо префікси
        city = self._strip_city_prefix(city)
        
        normalized = self.normalize_text(city)
        
        # Перевірка перейменувань
        if normalized in self.city_renames:
            normalized = self.normalize_text(self.city_renames[normalized])
            
        return normalized
    
    def normalize_street(self, street: str) -> str:
        """Нормалізує назву вулиці"""
        if not street:
            return ""
        
        street = self._strip_street_prefix(street)
        street = re.sub(
            r'\s+(?:шосе|просп(?:ект)?|просп\.?|пр-т|прт\.?|бульв(?:ар)?|бульв\.?|пров(?:улок)?|пров\.?)\.?\s*$',
            '',
            street,
            flags=re.IGNORECASE,
        )
        
        # Розширюємо скорочення
        # "л." -> "лесі", "т." -> "тараса", "б." -> "богдана"
        street = re.sub(r'\bл\.\s*', 'лесі ', street, flags=re.IGNORECASE)
        street = re.sub(r'\bт\.\s*', 'тараса ', street, flags=re.IGNORECASE)
        street = re.sub(r'\bб\.\s*', 'богдана ', street, flags=re.IGNORECASE)
        street = re.sub(r'\bі\.\s*', 'івана ', street, flags=re.IGNORECASE)
        street = re.sub(r'\bм\.\s*', 'миколи ', street, flags=re.IGNORECASE)
        street = re.sub(r'\bв\.\s*', 'василя ', street, flags=re.IGNORECASE)
        street = re.sub(r'\bг\.\s*', 'григорія ', street, flags=re.IGNORECASE) # Додано
        street = re.sub(r'\bп\.\s*', 'петра ', street, flags=re.IGNORECASE) # Додано
        street = re.sub(r'\bо\.\s*', 'олександра ', street, flags=re.IGNORECASE) # Додано
        
        return self.normalize_text(street)

    def normalize_street_aliases(self, street: str, city: str = "") -> list[str]:
        """Returns normalized street plus verified city-specific rename aliases."""
        normalized_street = self.normalize_street(street)
        if not normalized_street:
            return []

        aliases = [normalized_street]
        global_renamed_street = self.global_street_renames.get(normalized_street)
        if global_renamed_street:
            normalized_global_renamed = self.normalize_street(global_renamed_street)
            if normalized_global_renamed and normalized_global_renamed not in aliases:
                aliases.append(normalized_global_renamed)

        normalized_city = self.normalize_city(city) if city else ""
        city_renames = self.street_renames_by_city.get(normalized_city, {})
        renamed_street = city_renames.get(normalized_street)
        if renamed_street:
            normalized_renamed = self.normalize_street(renamed_street)
            if normalized_renamed and normalized_renamed not in aliases:
                aliases.append(normalized_renamed)

        return aliases

    def _load_street_aliases(self) -> None:
        aliases_path = getattr(config, "STREET_ALIASES_PATH", "")
        if not aliases_path or not os.path.exists(aliases_path):
            return

        try:
            with open(aliases_path, newline="", encoding="utf-8-sig") as aliases_file:
                for row in csv.DictReader(aliases_file):
                    city = (row.get("city") or "").strip()
                    old_street = (row.get("old_street") or "").strip()
                    new_street = (row.get("new_street") or "").strip()
                    if not city or not old_street or not new_street:
                        continue

                    normalized_city = self.normalize_city(city)
                    normalized_old_street = self.normalize_street(old_street)
                    if not normalized_city or not normalized_old_street:
                        continue

                    self.street_renames_by_city.setdefault(normalized_city, {})[
                        normalized_old_street
                    ] = new_street
        except OSError:
            return

    @staticmethod
    def detect_street_type(street: str) -> str:
        if not street:
            return ""

        street = street.strip().lower()
        suffix_type_patterns = [
            ("highway", r"\bшосе$"),
            ("avenue", r"\b(?:просп(?:ект)?|просп\.?|пр-т|прт\.?)$"),
            ("boulevard", r"\b(?:бульв(?:ар)?|бульв\.?)$"),
            ("lane", r"\b(?:пров(?:улок)?|пров\.?)$"),
        ]
        for street_type, pattern in suffix_type_patterns:
            if re.search(pattern, street, flags=re.IGNORECASE):
                return street_type

        type_patterns = [
            ("lane", r"^(?:пров(?:улок)?|пров\.)\b"),
            ("avenue", r"^(?:просп(?:ект)?|пр-т|прт\.?|пр\.?)\b"),
            ("boulevard", r"^(?:бульв(?:ар)?|бул)\b"),
            ("square", r"^(?:пл(?:оща)?)\b"),
            ("highway", r"^(?:шосе)\b"),
            ("street", r"^(?:вул(?:иця)?)\b"),
        ]
        for street_type, pattern in type_patterns:
            if re.search(pattern, street, flags=re.IGNORECASE):
                return street_type

        return ""
    
    def normalize_region(self, region: str) -> str:
        """Нормалізує назву області"""
        if not region:
            return ""
        
        region = region.lower().strip()
        
        # Видаляємо "область", "обл."
        region = re.sub(r'\s*(область|обл\.?)\s*$', '', region, flags=re.IGNORECASE)
        
        return self.normalize_text(region)
    
    def _transliterate(self, text: str) -> str:
        """Транслітерація російська → українська"""
        for ru_char, uk_char in self.transliteration_map.items():
            text = text.replace(ru_char, uk_char)
        return text

    @staticmethod
    def _strip_city_prefix(city: str) -> str:
        return re.sub(
            r'^\s*(?:місто|город|нас\.?\s*пункт|н\.?\s*п\.?|смт|сел(?:ище)?|с-ще|м|г|с)\.?\s+',
            '',
            city,
            flags=re.IGNORECASE,
        ).strip()

    @staticmethod
    def _strip_street_prefix(street: str) -> str:
        return re.sub(
            r'^\s*(?:вул(?:иця)?|пров(?:улок)?|бульв(?:ар)?|бул|просп(?:ект)?|пр-т|прт\.?|пр\.?|пл(?:оща)?|шосе)\.?\s*',
            '',
            street,
            flags=re.IGNORECASE,
        ).strip()
    
    def extract_consonants(self, text: str) -> str:
        """
        Витягує приголосні літери
        Використовується для стійкості до помилок у голосних
        """
        if not text:
            return ""
        
        text = self.normalize_text(text)
        
        # Українські голосні
        vowels = "аеиіоуюяёэы"
        
        # Залишаємо тільки приголосні
        consonants = ''.join([c for c in text if c.isalpha() and c not in vowels])
        
        return consonants
    
    def try_extract_city(self, street: str) -> tuple[str, str]:
        """
        Спроба витягнути місто з поля вулиці
        Повертає (знайдене_місто, очищена_вулиця)
        """
        if not street or ',' not in street:
            return "", street
            
        parts = [p.strip() for p in street.split(',')]
        
        # Якщо перша частина схожа на місто
        first_part = parts[0].lower()
        
        # Ознаки міста
        is_city = False
        
        # 1. Явні префікси
        for prefix in config.CITY_PREFIXES:
            if first_part.startswith(prefix):
                is_city = True
                break
                
        # 2. Відомі великі міста (без префіксів)
        known_cities = {'київ', 'харків', 'одеса', 'дніпро', 'львів', 'запоріжжя', 'кривий ріг', 'миколаїв', 'донецьк'}
        if self.normalize_text(first_part) in known_cities:
            is_city = True
            
        if is_city:
            city = parts[0]
            clean_street = ", ".join(parts[1:])
            return city, clean_street
            
        return "", street

    def try_extract_building(self, street: str) -> tuple[str, str]:
        """
        Спроба витягнути номер будинку з поля вулиці
        Наприклад: "Мічуріна 28" -> ("28", "Мічуріна")
        Повертає (знайдений_будинок, очищена_вулиця)
        """
        if not street:
            return "", street
            
        # Патерн: Вулиця + номер будинку (можливо з літерою) + можливо квартира
        # Приклад: "Мічуріна 28, #35" -> building="28", street="Мічуріна"
        
        # 1. Спочатку спробуємо знайти номер будинку перед комою або #
        building_core = r'\d+(?:[/-]\d+)?(?:[-\s]?[а-яА-Яa-zA-ZіїєґІЇЄҐ])?'
        corp_tail = r'(?:\s*[-/]?\s*(?:корп|корпус|к)\.?\s*\d+)?'
        match = re.search(
            rf'^(.*?)\s+({building_core}){corp_tail}\s*(?:,.*|#.*)?$',
            street,
            flags=re.IGNORECASE
        )
        if match:
            clean_street = match.group(1).strip()
            building = match.group(2).strip()
            
            # Перевіряємо, чи не є це частиною назви вулиці (наприклад "1-го Травня")
            # Якщо вулиця занадто коротка або закінчується на дефіс - це підозріло
            if len(clean_street) < 3 or clean_street.endswith('-'):
                return "", street
                
            return building, clean_street
            
        return "", street

