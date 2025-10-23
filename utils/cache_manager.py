"""
Менеджер кешування результатів пошуку
"""
import json
import os
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional
import config


class CacheManager:
    """Менеджер для кешування результатів пошуку"""
    
    def __init__(self):
        self.cache_file = config.SEARCH_CACHE_PATH
        self.cache: Dict[str, Dict] = {}
        self.enabled = config.ENABLE_SEARCH_CACHE
        
        if self.enabled:
            self._load_cache()
    
    def generate_key(self, address_data: Dict) -> str:
        """
        Генерує унікальний ключ для адреси
        
        Args:
            address_data: Словник з даними адреси
            
        Returns:
            MD5 хеш ключ
        """
        # Створюємо нормалізований рядок
        key_parts = []
        for field in ['city', 'street', 'region', 'district']:
            value = str(address_data.get(field, '')).lower().strip()
            if value:
                key_parts.append(value)
        
        key_string = '|'.join(key_parts)
        
        # MD5 хеш
        return hashlib.md5(key_string.encode('utf-8')).hexdigest()
    
    def get(self, key: str) -> Optional[Dict]:
        """
        Отримує результат з кешу
        
        Args:
            key: Ключ кешу
            
        Returns:
            Результат або None
        """
        if not self.enabled:
            return None
        
        if key not in self.cache:
            return None
        
        cached_item = self.cache[key]
        
        # Перевіряємо чи не застарів
        if config.CACHE_EXPIRY_DAYS > 0:
            cached_date = datetime.fromisoformat(cached_item.get('cached_at', '2000-01-01'))
            age_days = (datetime.now() - cached_date).days
            
            if age_days > config.CACHE_EXPIRY_DAYS:
                # Видаляємо застарілий
                del self.cache[key]
                self._save_cache()
                return None
        
        return cached_item.get('result')
    
    def set(self, key: str, result: Dict):
        """
        Зберігає результат в кеш
        
        Args:
            key: Ключ
            result: Результат для збереження
        """
        if not self.enabled:
            return
        
        self.cache[key] = {
            'result': result,
            'cached_at': datetime.now().isoformat()
        }
        
        self._save_cache()
    
    def clear(self):
        """Очищає весь кеш"""
        self.cache.clear()
        self._save_cache()
    
    def _load_cache(self):
        """Завантажує кеш з файлу"""
        if not os.path.exists(self.cache_file):
            return
        
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                self.cache = json.load(f)
        except Exception as e:
            print(f"⚠️ Помилка завантаження кешу: {e}")
            self.cache = {}
    
    def _save_cache(self):
        """Зберігає кеш в файл"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Помилка збереження кешу: {e}")
    
    def get_statistics(self) -> Dict:
        """Повертає статистику кешу"""
        return {
            'total_entries': len(self.cache),
            'enabled': self.enabled
        }
