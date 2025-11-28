"""
Нормалізація українського тексту для пошуку адрес
"""
import re
from typing import Dict
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
        city_lower = city.lower()
        for prefix in config.CITY_PREFIXES:
            if city_lower.startswith(prefix):
                city = city[len(prefix):].strip()
                break
        
        normalized = self.normalize_text(city)
        
        # Перевірка перейменувань
        if normalized in self.city_renames:
            normalized = self.city_renames[normalized]
            
        return normalized
    
    def normalize_street(self, street: str) -> str:
        """Нормалізує назву вулиці"""
        if not street:
            return ""
        
        # Видаляємо префікси
        street_lower = street.lower()
        for prefix in config.STREET_PREFIXES:
            if street_lower.startswith(prefix):
                street = street[len(prefix):].strip()
                break
        
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
        known_cities = {'київ', 'харків', 'одеса', 'дніпро', 'львів', 'запоріжжя', 'кривий ріг', 'миколаїв'}
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
        match = re.search(r'^(.*?)\s+(\d+[а-яА-Яa-zA-Z]?(?:[/-]\d+)?)\s*(?:,.*|#.*)?$', street)
        if match:
            clean_street = match.group(1).strip()
            building = match.group(2).strip()
            
            # Перевіряємо, чи не є це частиною назви вулиці (наприклад "1-го Травня")
            # Якщо вулиця занадто коротка або закінчується на дефіс - це підозріло
            if len(clean_street) < 3 or clean_street.endswith('-'):
                return "", street
                
            return building, clean_street
            
        return "", street

