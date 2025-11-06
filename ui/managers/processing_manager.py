"""
ProcessingManager - управління автоматичною обробкою v2.0

Відповідає за:
- Автоматичну обробку з жорсткими критеріями (ТІЛЬКИ 1 результат ≥98%)
- Напівавтоматичну обробку (з підтвердженням)
- Застосування індексів за правилами
- Управління прогресом обробки
"""

import re
from typing import Dict, List, Optional, Callable
from PyQt5.QtWidgets import QApplication

from handlers.excel_handler import ExcelHandler
from models.address import Address
from utils.logger import Logger
from utils.undo_manager import UndoManager


class ProcessingManager:
    """Менеджер для автоматичної обробки рядків з жорсткими критеріями"""
    
    def __init__(self, excel_handler: ExcelHandler, undo_manager: UndoManager):
        """
        Ініціалізація ProcessingManager
        
        Args:
            excel_handler: Обробник Excel файлів
            undo_manager: Менеджер відміни дій
        """
        self.excel_handler = excel_handler
        self.undo_manager = undo_manager
        self.logger = Logger()
        
        # Стан обробки
        self.is_processing = False
        self.is_stopped = False
        self.semi_auto_waiting = False
        
        # Статистика
        self.stats = {
            'total': 0,
            'auto_applied': 0,
            'manual_required': 0,
            'not_found': 0,
            'skipped': 0,
            'errors': 0
        }
        
        # Параметри обробки
        self.current_row = -1
        
        # Колбеки для оновлення UI
        self.on_progress_update: Optional[Callable[[int, int], None]] = None
        self.on_row_processed: Optional[Callable[[int, str, str], None]] = None  # row, index, mode
        self.on_semi_auto_pause: Optional[Callable[[int, List[Dict]], None]] = None
    
    def start_auto_processing(
        self,
        start_row: int,
        total_rows: int,
        search_func: Callable[[Address, bool], Dict]  # Змінено! Тепер повертає Dict
    ) -> Dict[str, int]:
        """
        Запускає ЖОРСТКУ автоматичну обробку
        
        НОВІ ПРАВИЛА:
        - Застосовується ТІЛЬКИ якщо є ОДИН результат ≥98%
        - Будинок має ТОЧНО співпадати
        - Індекс співпадає (якщо заданий)
        
        Args:
            start_row: Початковий рядок
            total_rows: Загальна кількість рядків
            search_func: Функція пошуку (має бути search_manager.search_with_auto)
            
        Returns:
            Словник зі статистикою: {
                'total': N,
                'auto_applied': X,
                'manual_required': Y,
                'not_found': Z,
                'skipped': M
            }
        """
        self.is_processing = True
        self.is_stopped = False
        self.current_row = start_row
        
        # Скидаємо статистику
        self.stats = {
            'total': total_rows - start_row,
            'auto_applied': 0,
            'manual_required': 0,
            'not_found': 0,
            'skipped': 0,
            'errors': 0
        }
        
        mapping = self.excel_handler.column_mapping
        if not mapping or 'index' not in mapping:
            self.logger.error("Column mapping не налаштовано")
            return self.stats
        
        idx_col = mapping['index'][0]
        old_index_col_idx = self._get_old_index_column_idx()
        
        self.logger.info("=" * 80)
        self.logger.info("🚀 ПОЧАТОК АВТОМАТИЧНОЇ ОБРОБКИ")
        self.logger.info(f"   Рядків: {start_row} - {total_rows}")
        self.logger.info("=" * 80)
        
        for row_idx in range(start_row, total_rows):
            QApplication.processEvents()
            
            if self.is_stopped:
                self.logger.info("⏸️  Обробку зупинено користувачем")
                break
            
            # Оновлюємо прогрес
            if self.on_progress_update:
                self.on_progress_update(row_idx + 1, total_rows)
            
            # Перевіряємо чи вже проставлено
            if self._is_row_already_processed(row_idx, idx_col, old_index_col_idx):
                self.stats['skipped'] += 1
                continue
            
            try:
                # Отримуємо адресу
                address = self.excel_handler.get_address_from_row(row_idx)
                
                # НОВИЙ ПОШУК з жорсткими критеріями
                result = search_func(address, auto_apply=True)  # auto_apply=True!
                
                if result['mode'] == 'auto' and result['applied']:
                    # ✅ АВТОПІДСТАНОВКА УСПІШНА
                    auto_result = result['auto_result']
                    index = self._determine_index(auto_result)
                    
                    if index:
                        self._apply_index_to_row(row_idx, index, idx_col)
                        self.stats['auto_applied'] += 1
                        
                        if self.on_row_processed:
                            self.on_row_processed(row_idx, index, 'auto')
                        
                        self.logger.debug(
                            f"✅ Рядок {row_idx}: AUTO -> [{index}] "
                            f"{auto_result['city']}, {auto_result['street']}, {auto_result['building']}"
                        )
                
                elif result['mode'] == 'manual':
                    # ⚠️ ПОТРІБЕН РУЧНИЙ ВИБІР
                    self.stats['manual_required'] += 1
                    
                    self.logger.debug(
                        f"⚠️  Рядок {row_idx}: MANUAL (знайдено {result['total_found']} варіантів) - "
                        f"{address.city}, {address.street}, {address.building}"
                    )
                
                else:
                    # ❌ НІЧОГО НЕ ЗНАЙДЕНО
                    self.stats['not_found'] += 1
                    
                    self.logger.debug(
                        f"❌ Рядок {row_idx}: NOT_FOUND - "
                        f"{address.city}, {address.street}, {address.building}"
                    )
                        
            except Exception as e:
                self.logger.error(f"🔥 Помилка обробки рядка {row_idx}: {e}")
                self.stats['errors'] += 1
                continue
        
        self.is_processing = False
        
        # Підсумкова статистика
        self._log_final_stats()
        
        return self.stats
    
    def start_semi_auto_processing(
        self,
        start_row: int,
        total_rows: int,
        search_func: Callable[[Address, bool], Dict]
    ) -> Dict[str, int]:
        """
        Запускає напівавтоматичну обробку (з паузами на ручний вибір)
        
        ЛОГІКА:
        - Якщо є автопідстановка (1 результат ≥98%) - застосовує автоматично
        - Якщо потрібен ручний вибір - ЗУПИНЯЄТЬСЯ і чекає вибору
        
        Args:
            start_row: Початковий рядок
            total_rows: Загальна кількість рядків
            search_func: Функція пошуку
            
        Returns:
            Словник зі статистикою
        """
        self.is_processing = True
        self.is_stopped = False
        self.semi_auto_waiting = False
        self.current_row = start_row
        
        # Скидаємо статистику якщо це новий запуск
        if start_row == 0 or not hasattr(self, 'stats'):
            self.stats = {
                'total': total_rows - start_row,
                'auto_applied': 0,
                'manual_required': 0,
                'not_found': 0,
                'skipped': 0,
                'errors': 0
            }
        
        mapping = self.excel_handler.column_mapping
        if not mapping or 'index' not in mapping:
            return self.stats
        
        idx_col = mapping['index'][0]
        old_index_col_idx = self._get_old_index_column_idx()
        
        self.logger.info("🔄 Напівавтоматична обробка...")
        
        for row_idx in range(start_row, total_rows):
            QApplication.processEvents()
            
            if self.is_stopped:
                break
            
            if self.on_progress_update:
                self.on_progress_update(row_idx + 1, total_rows)
            
            if self._is_row_already_processed(row_idx, idx_col, old_index_col_idx):
                self.stats['skipped'] += 1
                continue
            
            try:
                address = self.excel_handler.get_address_from_row(row_idx)
                result = search_func(address, auto_apply=True)
                
                if result['mode'] == 'auto' and result['applied']:
                    # Автопідстановка
                    auto_result = result['auto_result']
                    index = self._determine_index(auto_result)
                    
                    if index:
                        self._apply_index_to_row(row_idx, index, idx_col)
                        self.stats['auto_applied'] += 1
                        
                        if self.on_row_processed:
                            self.on_row_processed(row_idx, index, 'auto')
                
                else:
                    # ПАУЗА для ручного вибору
                    self.semi_auto_waiting = True
                    self.current_row = row_idx
                    
                    if result['mode'] == 'manual':
                        self.stats['manual_required'] += 1
                    else:
                        self.stats['not_found'] += 1
                    
                    if self.on_semi_auto_pause:
                        # Передаємо ручні результати
                        manual_results = result.get('manual_results', [])
                        self.on_semi_auto_pause(row_idx, manual_results)
                    
                    # ЗУПИНЯЄМОСЬ і чекаємо вибору користувача
                    return self.stats
                    
            except Exception as e:
                self.logger.error(f"Помилка обробки рядка {row_idx}: {e}")
                self.stats['errors'] += 1
                continue
        
        self.is_processing = False
        self._log_final_stats()
        
        return self.stats
    
    def continue_semi_auto(
        self, 
        search_func: Callable[[Address, bool], Dict]
    ) -> Dict[str, int]:
        """
        Продовжує напівавтоматичну обробку після ручного вибору
        
        Args:
            search_func: Функція пошуку
            
        Returns:
            Словник зі статистикою
        """
        if not self.semi_auto_waiting:
            return self.stats
        
        self.semi_auto_waiting = False
        next_row = self.current_row + 1
        
        total_rows = len(self.excel_handler.df)
        return self.start_semi_auto_processing(
            next_row, total_rows, search_func
        )
    
    def stop_processing(self):
        """Зупиняє обробку"""
        self.is_stopped = True
        self.semi_auto_waiting = False
        self.is_processing = False
        self.logger.info("⏹️  Обробку зупинено")
    
    def apply_index(self, row_idx: int, index: str) -> bool:
        """
        Застосовує індекс до рядка з збереженням в Undo
        
        Args:
            row_idx: Номер рядка
            index: Індекс для застосування
            
        Returns:
            True якщо успішно
        """
        try:
            mapping = self.excel_handler.column_mapping
            if not mapping or 'index' not in mapping:
                return False
            
            idx_col = mapping['index'][0]
            
            # Зберігаємо старе значення для Undo
            address = self.excel_handler.get_address_from_row(row_idx)
            old_index = address.index
            
            self.undo_manager.push({
                'row': row_idx,
                'old_values': {'index': old_index},
                'new_values': {'index': index}
            })
            
            # Застосовуємо новий індекс
            self.excel_handler.df.iloc[row_idx, idx_col] = index
            
            if self.on_row_processed:
                self.on_row_processed(row_idx, index, 'manual')
            
            return True
            
        except Exception as e:
            self.logger.error(f"Помилка застосування індексу: {e}")
            return False
    
    def _determine_index(self, result: Dict) -> str:
        """
        Визначає індекс за правилами обробки
        
        Args:
            result: Результат пошуку
            
        Returns:
            Індекс або '*' для спеціальних випадків
        """
        not_working = result.get('not_working', '')
        
        # Тимчасово не функціонує (але не ВПЗ)
        if 'Тимчасово не функціонує' in not_working and 'ВПЗ' not in not_working:
            return '*'
        
        # ВПЗ - шукаємо індекс у тексті
        if 'ВПЗ' in not_working:
            match = re.search(r'(\d{5})', not_working)
            return match.group(1) if match else '*'
        
        # Звичайний індекс
        return result.get('index', '')
    
    def _apply_index_to_row(self, row_idx: int, index: str, idx_col: int):
        """
        Застосовує індекс безпосередньо до DataFrame
        
        Args:
            row_idx: Номер рядка
            index: Індекс
            idx_col: Номер колонки індексу
        """
        self.excel_handler.df.iloc[row_idx, idx_col] = index
    
    def _is_row_already_processed(
        self, 
        row_idx: int, 
        idx_col: int, 
        old_index_col_idx: Optional[int]
    ) -> bool:
        """
        Перевіряє чи рядок вже оброблено
        
        Args:
            row_idx: Номер рядка
            idx_col: Колонка індексу
            old_index_col_idx: Колонка старого індексу
            
        Returns:
            True якщо вже оброблено
        """
        if old_index_col_idx is None:
            return False
        
        try:
            current_index = str(self.excel_handler.df.iloc[row_idx, idx_col]).strip()
            old_index = str(self.excel_handler.df.iloc[row_idx, old_index_col_idx]).strip()
            
            # Нормалізуємо
            if current_index in ['', 'nan', 'None']:
                current_index = ''
            if old_index in ['', 'nan', 'None']:
                old_index = ''
            
            # Якщо індекси різні - вже проставлено
            return current_index != old_index and current_index != ''
            
        except Exception as e:
            self.logger.error(f"Помилка перевірки рядка {row_idx}: {e}")
            return False
    
    def _get_old_index_column_idx(self) -> Optional[int]:
        """
        Знаходить індекс колонки "Старий індекс"
        
        Returns:
            Індекс колонки або None
        """
        for i, col_name in enumerate(self.excel_handler.df.columns):
            if col_name == 'Старий індекс':
                return i
        return None
    
    def _log_final_stats(self):
        """Виводить фінальну статистику в лог"""
        self.logger.info("=" * 80)
        self.logger.info("📊 СТАТИСТИКА ОБРОБКИ")
        self.logger.info("=" * 80)
        self.logger.info(f"Всього записів:        {self.stats['total']}")
        self.logger.info(f"✅ Автопідстановка:    {self.stats['auto_applied']}")
        self.logger.info(f"⚠️  Ручний вибір:       {self.stats['manual_required']}")
        self.logger.info(f"❌ Не знайдено:        {self.stats['not_found']}")
        self.logger.info(f"⏭️  Пропущено:          {self.stats['skipped']}")
        self.logger.info(f"🔥 Помилки:            {self.stats['errors']}")
        self.logger.info("=" * 80 + "\n")
