"""
ProcessingManager - управління автоматичною обробкою

Відповідає за:
- Автоматичну обробку рядків
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
    """Менеджер для автоматичної обробки рядків"""
    
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
        
        # Параметри обробки
        self.min_confidence = 80
        self.current_row = -1
        
        # Колбеки для оновлення UI
        self.on_progress_update: Optional[Callable[[int, int], None]] = None
        self.on_row_processed: Optional[Callable[[int, str], None]] = None
        self.on_semi_auto_pause: Optional[Callable[[int, List[Dict]], None]] = None
    
    def start_auto_processing(
        self,
        start_row: int,
        total_rows: int,
        min_confidence: int,
        search_func: Callable[[Address], List[Dict]]
    ) -> Dict[str, int]:
        """
        Запускає автоматичну обробку
        
        Args:
            start_row: Початковий рядок
            total_rows: Загальна кількість рядків
            min_confidence: Мінімальна точність для автозастосування
            search_func: Функція пошуку адреси
            
        Returns:
            Словник зі статистикою: {'processed': N, 'skipped': M}
        """
        self.is_processing = True
        self.is_stopped = False
        self.min_confidence = min_confidence
        self.current_row = start_row
        
        processed_count = 0
        skipped_count = 0
        
        mapping = self.excel_handler.column_mapping
        if not mapping or 'index' not in mapping:
            self.logger.error("Column mapping не налаштовано")
            return {'processed': 0, 'skipped': 0}
        
        idx_col = mapping['index'][0]
        old_index_col_idx = self._get_old_index_column_idx()
        
        for row_idx in range(start_row, total_rows):
            QApplication.processEvents()
            
            if self.is_stopped:
                self.logger.info("Обробку зупинено користувачем")
                break
            
            # Оновлюємо прогрес
            if self.on_progress_update:
                self.on_progress_update(row_idx + 1, total_rows)
            
            # Перевіряємо чи вже проставлено
            if self._is_row_already_processed(row_idx, idx_col, old_index_col_idx):
                skipped_count += 1
                continue
            
            try:
                # Отримуємо адресу та шукаємо
                address = self.excel_handler.get_address_from_row(row_idx)
                results = search_func(address)
                
                if not results:
                    continue
                
                # Обробляємо найкращий результат
                best_result = results[0]
                confidence = best_result.get('confidence', 0)
                
                # Визначаємо індекс за правилами
                index = self._determine_index(best_result)
                
                # Застосовуємо якщо точність достатня
                if confidence >= min_confidence and index:
                    self._apply_index_to_row(row_idx, index, idx_col)
                    processed_count += 1
                    
                    if self.on_row_processed:
                        self.on_row_processed(row_idx, index)
                        
            except Exception as e:
                self.logger.error(f"Помилка обробки рядка {row_idx}: {e}")
                continue
        
        self.is_processing = False
        return {'processed': processed_count, 'skipped': skipped_count}
    
    def start_semi_auto_processing(
        self,
        start_row: int,
        total_rows: int,
        min_confidence: int,
        search_func: Callable[[Address], List[Dict]]
    ) -> Dict[str, int]:
        """
        Запускає напівавтоматичну обробку (з паузами на підтвердження)
        
        Args:
            start_row: Початковий рядок
            total_rows: Загальна кількість рядків
            min_confidence: Мінімальна точність для автозастосування
            search_func: Функція пошуку адреси
            
        Returns:
            Словник зі статистикою
        """
        self.is_processing = True
        self.is_stopped = False
        self.semi_auto_waiting = False
        self.min_confidence = min_confidence
        self.current_row = start_row
        
        processed_count = 0
        skipped_count = 0
        
        mapping = self.excel_handler.column_mapping
        if not mapping or 'index' not in mapping:
            return {'processed': 0, 'skipped': 0}
        
        idx_col = mapping['index'][0]
        old_index_col_idx = self._get_old_index_column_idx()
        
        for row_idx in range(start_row, total_rows):
            QApplication.processEvents()
            
            if self.is_stopped:
                break
            
            if self.on_progress_update:
                self.on_progress_update(row_idx + 1, total_rows)
            
            if self._is_row_already_processed(row_idx, idx_col, old_index_col_idx):
                skipped_count += 1
                continue
            
            try:
                address = self.excel_handler.get_address_from_row(row_idx)
                results = search_func(address)
                
                if not results:
                    continue
                
                best_result = results[0]
                confidence = best_result.get('confidence', 0)
                index = self._determine_index(best_result)
                
                if confidence >= min_confidence and index:
                    self._apply_index_to_row(row_idx, index, idx_col)
                    processed_count += 1
                    
                    if self.on_row_processed:
                        self.on_row_processed(row_idx, index)
                else:
                    # Пауза для ручного вибору
                    self.semi_auto_waiting = True
                    self.current_row = row_idx
                    
                    if self.on_semi_auto_pause:
                        self.on_semi_auto_pause(row_idx, results)
                    
                    return {'processed': processed_count, 'skipped': skipped_count}
                    
            except Exception as e:
                self.logger.error(f"Помилка обробки рядка {row_idx}: {e}")
                continue
        
        self.is_processing = False
        return {'processed': processed_count, 'skipped': skipped_count}
    
    def continue_semi_auto(self, search_func: Callable[[Address], List[Dict]]) -> Dict[str, int]:
        """
        Продовжує напівавтоматичну обробку після паузи
        
        Args:
            search_func: Функція пошуку
            
        Returns:
            Словник зі статистикою
        """
        if not self.semi_auto_waiting:
            return {'processed': 0, 'skipped': 0}
        
        self.semi_auto_waiting = False
        next_row = self.current_row + 1
        
        total_rows = len(self.excel_handler.df)
        return self.start_semi_auto_processing(
            next_row, total_rows, self.min_confidence, search_func
        )
    
    def stop_processing(self):
        """Зупиняє обробку"""
        self.is_stopped = True
        self.semi_auto_waiting = False
        self.is_processing = False
    
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
