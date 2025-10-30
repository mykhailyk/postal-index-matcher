"""
SearchManager - управління пошуком адрес

Відповідає за:
- Ініціалізацію пошукового движка
- Виконання пошуку адрес
- Логування запитів та результатів
- Кешування результатів
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Optional

from search.hybrid_search import HybridSearch
from models.address import Address
from utils.logger import Logger
import config


class SearchManager:
    """Менеджер для пошуку адрес"""
    
    def __init__(self):
        """Ініціалізація SearchManager"""
        self.logger = Logger()
        self.search_engine: Optional[HybridSearch] = None
        self.last_results: List[Dict] = []
        self._initialize_search_engine()
    
    def _initialize_search_engine(self):
        """Ініціалізує пошуковий движок"""
        try:
            self.logger.info("Ініціалізація пошукового движка...")
            self.search_engine = HybridSearch()
            self.logger.info("Пошуковий движок готовий")
        except Exception as e:
            self.logger.error(f"Помилка ініціалізації пошуку: {e}")
            raise
    
    def search(self, address: Address, max_results: int = 20) -> List[Dict]:
        """
        Виконує пошук адреси
        
        Args:
            address: Об'єкт адреси для пошуку
            max_results: Максимальна кількість результатів
            
        Returns:
            Список знайдених адрес з оцінками точності
        """
        if not self.search_engine:
            self.logger.error("Пошуковий движок не ініціалізовано")
            return []
        
        try:
            # Логуємо запит
            self._log_search_request(address)
            
            # Виконуємо пошук
            results = self.search_engine.search(address, max_results=max_results)
            
            # Логуємо результати
            self._log_search_results(address, results)
            
            # Зберігаємо результати
            self.last_results = results
            
            return results
            
        except Exception as e:
            self.logger.error(f"Помилка пошуку: {e}")
            return []
    
    def get_magistral_records(self):
        """Повертає всі magistral записи (УЖЕ завантажені!)"""
        # Використовуємо вже завантажені дані, НЕ перезавантажуємо!
        return self.search_engine.magistral_records
    
    def refresh_cache(self, force_reload: bool = True):
        """
        Оновлює кеш magistral.csv
        
        Args:
            force_reload: Примусове перезавантаження
        """
        try:
            if self.search_engine and hasattr(self.search_engine, 'loader'):
                self.search_engine.loader.load(force_reload=force_reload)
                self.logger.info("Кеш magistral.csv оновлено")
        except Exception as e:
            self.logger.error(f"Помилка оновлення кешу: {e}")
            raise
    
    def _log_search_request(self, address: Address):
        """
        Логує запит пошуку
        
        Args:
            address: Адреса для логування
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': 'search_request',
            'address': address.to_dict()
        }
        
        search_log_path = os.path.join(config.LOGS_DIR, 'search_queries.jsonl')
        try:
            with open(search_log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        except Exception as e:
            self.logger.error(f"Помилка логування запиту: {e}")
    
    def _log_search_results(self, address: Address, results: List[Dict]):
        """
        Логує результати пошуку
        
        Args:
            address: Оригінальна адреса запиту
            results: Знайдені результати
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': 'search_results',
            'query': address.to_dict(),
            'results_count': len(results),
            'all_results': [
                {
                    'city': r.get('city'),
                    'district': r.get('district'),
                    'region': r.get('region'),
                    'street': r.get('street'),
                    'index': r.get('index'),
                    'confidence': r.get('confidence'),
                    'buildings': r.get('buildings', ''),
                    'not_working': r.get('not_working', '')
                }
                for r in results
            ]
        }
        
        search_log_path = os.path.join(config.LOGS_DIR, 'search_queries.jsonl')
        try:
            with open(search_log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        except Exception as e:
            self.logger.error(f"Помилка логування результатів: {e}")
    
    def log_index_applied(self, row_idx: int, address: Address, index_value: str):
        """
        Логує застосований індекс
        
        Args:
            row_idx: Номер рядка
            address: Адреса
            index_value: Застосований індекс
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': 'index_applied',
            'row': row_idx,
            'address': address.to_dict(),
            'applied_index': index_value
        }
        
        search_log_path = os.path.join(config.LOGS_DIR, 'search_queries.jsonl')
        try:
            with open(search_log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        except Exception as e:
            self.logger.error(f"Помилка логування індексу: {e}")
