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
        
        return self.normalize_text(city)
    
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
