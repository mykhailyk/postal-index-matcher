"""
FileManager - управління операціями з Excel файлами

Відповідає за:
- Завантаження та збереження Excel файлів
- Управління ExcelHandler
- Роботу з column mapping
- Ініціалізацію службових колонок
"""

import os
import pandas as pd
from typing import Optional, Dict, List
from PyQt5.QtWidgets import QFileDialog, QMessageBox

from handlers.excel_handler import ExcelHandler
from utils.settings_manager import SettingsManager
from utils.logger import Logger


class FileManager:
    """Менеджер для роботи з Excel файлами"""
    
    def __init__(self):
        """Ініціалізація FileManager"""
        self.excel_handler = ExcelHandler()
        self.logger = Logger()
        self.current_file: Optional[str] = None
    
    def get_file_dialog_path(self, parent=None, mode='open') -> Optional[str]:
        """
        Відкриває діалог вибору файлу
        
        Args:
            parent: Батьківський віджет
            mode: 'open' або 'save'
            
        Returns:
            Шлях до файлу або None
        """
        last_dir = SettingsManager.get_last_directory() or ""
        
        if mode == 'open':
            file_path, _ = QFileDialog.getOpenFileName(
                parent,
                "Відкрити Excel файл",
                last_dir,
                "Excel Files (*.xlsx *.xls)"
            )
        else:  # save
            file_path, _ = QFileDialog.getSaveFileName(
                parent,
                "Зберегти як",
                last_dir,
                "Excel Files (*.xlsx)"
            )
        
        return file_path if file_path else None
    
    def load_file(self, file_path: str) -> bool:
        """
        Завантажує Excel файл
        
        Args:
            file_path: Шлях до файлу
            
        Returns:
            True якщо успішно, False якщо помилка
        """
        try:
            self.logger.info(f"Завантаження файлу: {file_path}")
            
            # Зберігаємо останню директорію
            SettingsManager.set_last_directory(os.path.dirname(file_path))
            
            # Завантажуємо файл
            self.excel_handler.load_file(file_path)
            
            # Створюємо віртуальну колонку "Старий індекс"
            self._initialize_old_index_column()
            
            self.current_file = file_path
            self.logger.info(f"Файл завантажено: {len(self.excel_handler.df)} рядків")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Помилка завантаження файлу: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
    def _initialize_old_index_column(self):
        """Створює та заповнює колонку 'Старий індекс'"""
        if 'Старий індекс' in self.excel_handler.df.columns:
            return
        
        # Знаходимо колонку індексу
        index_col = None
        if self.excel_handler.column_mapping:
            index_col = self.excel_handler.column_mapping.get('index')
            if isinstance(index_col, list):
                index_col = index_col[0] if index_col else None
        
        # Додаємо колонку після індексу
        if index_col and index_col in self.excel_handler.df.columns:
            self.excel_handler.df[index_col] = self.excel_handler.df[index_col].astype(str)
            index_position = self.excel_handler.df.columns.get_loc(index_col)
            self.excel_handler.df.insert(index_position + 1, 'Старий індекс', '')
        else:
            self.excel_handler.df['Старий індекс'] = ''
        
        self.logger.info("Створено віртуальну колонку 'Старий індекс'")
    
    def copy_to_old_index(self):
        """Копіює поточні значення індексу у 'Старий індекс'"""
        mapping = self.excel_handler.column_mapping
        
        if not mapping or 'index' not in mapping:
            self.logger.warning("Поле 'index' не налаштоване")
            return
        
        index_cols = mapping.get('index', [])
        if not index_cols:
            return
        
        idx_col = index_cols[0]
        
        # Знаходимо колонку "Старий індекс"
        old_index_col_idx = None
        for i, col_name in enumerate(self.excel_handler.df.columns):
            if col_name == 'Старий індекс':
                old_index_col_idx = i
                break
        
        if old_index_col_idx is not None:
            self.excel_handler.df['Старий індекс'] = self.excel_handler.df.iloc[:, idx_col].copy()
            self.logger.info(f"Скопійовано індекс у 'Старий індекс'")
    
    def save_file(self, file_path: Optional[str] = None, 
                  save_old_index: bool = False, 
                  parent=None) -> bool:
        """
        Зберігає Excel файл
        
        Args:
            file_path: Шлях для збереження (None = поточний файл)
            save_old_index: Чи зберігати колонку "Старий індекс"
            parent: Батьківський віджет для діалогів
            
        Returns:
            True якщо успішно, False якщо помилка
        """
        if file_path is None:
            file_path = self.current_file
        
        if not file_path:
            return False
        
        try:
            df_to_save = self.excel_handler.df.copy()
            
            # Видаляємо службові колонки
            if '_processed_by_us' in df_to_save.columns:
                df_to_save = df_to_save.drop(columns=['_processed_by_us'])
            
            # Видаляємо 'Старий індекс' якщо не потрібно
            if not save_old_index and 'Старий індекс' in df_to_save.columns:
                df_to_save = df_to_save.drop(columns=['Старий індекс'])
                self.logger.info("Колонка 'Старий індекс' не збережена")
            else:
                self.logger.info("Колонка 'Старий індекс' збережена у файл")
            
            # Визначаємо розширення файлу
            _, ext = os.path.splitext(file_path)
            
            # Збереження
            if ext.lower() == '.xls':
                # XLS підтримка
                if len(df_to_save) > 65536:
                    self.logger.error("XLS формат підтримує максимум 65536 рядків")
                    return False
                
                try:
                    import xlwt
                    df_to_save.to_excel(file_path, index=False, engine='xlwt')
                except ImportError:
                    self.logger.error("Модуль 'xlwt' не встановлено")
                    return False
            else:
                # XLSX формат
                df_to_save.to_excel(file_path, index=False, engine='openpyxl')
            
            self.logger.info(f"Файл збережено: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Помилка збереження: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
