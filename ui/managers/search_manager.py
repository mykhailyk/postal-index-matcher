"""
SearchManager - управління пошуком адрес

Відповідає за:
- Ініціалізацію пошукового движка
- Виконання пошуку адрес з рівнями впевненості
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
    """Менеджер для пошуку адрес з автоматичною та ручною підстановкою"""
    
    def __init__(self):
        """Ініціалізація SearchManager"""
        self.logger = Logger()
        self.search_engine: Optional[HybridSearch] = None
        self.last_results: List[Dict] = []
        self.last_search_response: Optional[Dict] = None  # Повна відповідь з search_with_confidence
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
        LEGACY метод - виконує пошук адреси (зворотна сумісність)
        Повертає тільки список результатів
        
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
    
    def search_with_auto(self, address: Address, max_results: int = 20, auto_apply: bool = False) -> Dict:
        """
        НОВИЙ метод - пошук з автоматичною підстановкою
        
        Args:
            address: Об'єкт адреси для пошуку
            max_results: Максимальна кількість результатів для ручного вибору
            auto_apply: Чи застосовувати автопідстановку автоматично
            
        Returns:
            {
                'mode': 'auto' | 'manual' | 'none',
                'auto_result': Dict or None,     # Результат для автопідстановки
                'manual_results': List[Dict],    # Результати для ручного вибору
                'total_found': int,
                'applied': bool                   # Чи була застосована автопідстановка
            }
        """
        if not self.search_engine:
            self.logger.error("Пошуковий движок не ініціалізовано")
            return self._empty_response()
        
        try:
            # Логуємо запит
            self._log_search_request(address)
            
            # Виконуємо пошук з рівнями впевненості
            result = self.search_engine.search_with_confidence(address, max_results)
            
            # Формуємо відповідь
            response = {
                'mode': result['search_mode'],
                'auto_result': result['auto'],
                'manual_results': result['manual'],
                'total_found': result['total_found'],
                'applied': False
            }
            
            # Логуємо результати
            self._log_search_results_detailed(address, result)
            
            # Автоматична підстановка якщо дозволено
            if auto_apply and result['search_mode'] == 'auto':
                response['applied'] = True
                self._log_auto_applied(address, result['auto'])
                self.logger.info(
                    f"✅ Автопідстановка: [{result['auto']['index']}] "
                    f"{result['auto']['city']}, {result['auto']['street']}, {result['auto']['building']}"
                )
            
            # Зберігаємо результати
            self.last_results = result['manual']
            self.last_search_response = response
            
            return response
            
        except Exception as e:
            self.logger.error(f"Помилка пошуку: {e}")
            return self._empty_response(error=str(e))
    
    def get_auto_result_only(self, address: Address) -> Optional[Dict]:
        """
        Отримати ТІЛЬКИ результат для автопідстановки
        
        Args:
            address: Об'єкт адреси для пошуку
            
        Returns:
            Dict з результатом або None якщо автопідстановка неможлива
        """
        if not self.search_engine:
            return None
        
        try:
            result = self.search_engine.search_with_confidence(address)
            return result['auto']
        except Exception as e:
            self.logger.error(f"Помилка пошуку автопідстановки: {e}")
            return None
    
    def _empty_response(self, error: str = None) -> Dict:
        """Порожня відповідь"""
        response = {
            'mode': 'none',
            'auto_result': None,
            'manual_results': [],
            'total_found': 0,
            'applied': False
        }
        if error:
            response['error'] = error
        return response
    
    def get_magistral_records(self):
        """Повертає всі magistral записи (УЖЕ завантажені!)"""
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
        Логує результати пошуку (LEGACY - для старого методу search)
        
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
    
    def _log_search_results_detailed(self, address: Address, result: Dict):
        """
        Логує детальні результати пошуку (для нового методу)
        
        Args:
            address: Оригінальна адреса запиту
            result: Результат з search_with_confidence
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': 'search_results_v2',
            'query': address.to_dict(),
            'search_mode': result['search_mode'],
            'total_found': result['total_found'],
            'auto_result': None,
            'manual_results': []
        }
        
        # Логуємо автопідстановку якщо є
        if result['auto']:
            log_entry['auto_result'] = {
                'city': result['auto'].get('city'),
                'district': result['auto'].get('district'),
                'region': result['auto'].get('region'),
                'street': result['auto'].get('street'),
                'index': result['auto'].get('index'),
                'confidence': result['auto'].get('confidence'),
                'buildings': result['auto'].get('buildings', ''),
                'not_working': result['auto'].get('not_working', '')
            }
        
        # Логуємо ручні результати (ТОП-20)
        log_entry['manual_results'] = [
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
            for r in result['manual'][:20]
        ]
        
        search_log_path = os.path.join(config.LOGS_DIR, 'search_queries.jsonl')
        try:
            with open(search_log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        except Exception as e:
            self.logger.error(f"Помилка логування результатів: {e}")
    
    def _log_auto_applied(self, address: Address, auto_result: Dict):
        """
        Логує застосовану автопідстановку
        
        Args:
            address: Оригінальна адреса
            auto_result: Результат що був застосований
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': 'auto_applied',
            'query': address.to_dict(),
            'applied_result': {
                'city': auto_result.get('city'),
                'street': auto_result.get('street'),
                'building': auto_result.get('building'),
                'index': auto_result.get('index'),
                'confidence': auto_result.get('confidence')
            }
        }
        
        search_log_path = os.path.join(config.LOGS_DIR, 'search_queries.jsonl')
        try:
            with open(search_log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        except Exception as e:
            self.logger.error(f"Помилка логування автопідстановки: {e}")
    
    def log_index_applied(self, row_idx: int, address: Address, index_value: str):
        """
        Логує застосований індекс (ручна підстановка)
        
        Args:
            row_idx: Номер рядка
            address: Адреса
            index_value: Застосований індекс
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': 'index_applied_manual',
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
