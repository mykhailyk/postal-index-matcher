"""
Обробник Excel файлів
"""
import os
import pandas as pd
from models.address import Address
from utils.logger import Logger


class ExcelHandler:
    """Клас для роботи з Excel файлами"""
    
    def __init__(self):
        self.df = None
        self.file_path = None
        self.column_mapping = None
        self.logger = Logger()
    
    def load_file(self, file_path: str) -> pd.DataFrame:
        """Завантажує Excel файл"""
        try:
            self.df = pd.read_excel(file_path)
            self.file_path = file_path
            self.logger.info(f"Завантажено файл: {file_path}, рядків: {len(self.df)}")
            return self.df
        except Exception as e:
            self.logger.error(f"Помилка завантаження файлу {file_path}: {e}")
            raise
    
    def save_file(self, file_path: str = None):
        """Зберігає DataFrame у Excel файл (підтримує XLS і XLSX)"""
        if self.df is None:
            raise ValueError("Немає даних для збереження")
        
        save_path = file_path or self.file_path
        if not save_path:
            raise ValueError("Не вказано шлях для збереження")
        
        try:
            # ⬇️ ДОДАНО: Визначаємо розширення файлу
            _, ext = os.path.splitext(save_path)
            
            if ext.lower() == '.xls':
                # Зберігаємо в XLS (старий формат)
                self.df.to_excel(save_path, index=False, engine='xlwt')
                self.logger.info(f"Файл збережено як XLS: {save_path}")
            else:
                # Зберігаємо в XLSX (новий формат)
                self.df.to_excel(save_path, index=False, engine='openpyxl')
                self.logger.info(f"Файл збережено як XLSX: {save_path}")
                
        except Exception as e:
            self.logger.error(f"Помилка збереження файлу {save_path}: {e}")
            raise
    
    def get_column_names(self):
        """Повертає список назв стовпців"""
        if self.df is None:
            return []
        return list(self.df.columns)
    
    def set_column_mapping(self, mapping: dict):
        """Встановлює відповідність між полями та стовпцями"""
        self.column_mapping = mapping
        self.logger.info(f"Column mapping встановлено: {mapping}")
    
    def get_address_from_row(self, row_index: int) -> Address:
        """Отримує Address об'єкт з рядка"""
        if self.df is None or self.column_mapping is None:
            raise ValueError("Файл не завантажено або mapping не налаштовано")
        
        def get_value(field_id):
            """Витягує значення з УСІХ колонок цього поля"""
            if field_id not in self.column_mapping:
                return ""
            
            col_indices = self.column_mapping[field_id]
            if not col_indices:
                return ""
            
            # ⬇️ ВИПРАВЛЕНО: Об'єднуємо значення з УСІХ колонок
            values = []
            for col_idx in col_indices:
                value = self.df.iloc[row_index, col_idx]
                if pd.notna(value) and str(value).strip():
                    values.append(str(value).strip())
            
            return " ".join(values)  # Об'єднуємо через пробіл
        
        return Address(
            city=get_value('city'),
            street=get_value('street'),
            building=get_value('building'),
            region=get_value('region'),
            district=get_value('district'),
            index=get_value('index'),
            old_index=get_value('old_index'),
            client_id=get_value('client_id'),
            name=get_value('name')
        )

    
    def update_row(self, row_index: int, updates: dict):
        """Оновлює значення в рядку
        
        Args:
            row_index: Індекс рядка
            updates: Словник {field_id: value}
        """
        if self.df is None or self.column_mapping is None:
            raise ValueError("Файл не завантажено або mapping не налаштовано")
        
        for field_id, value in updates.items():
            if field_id not in self.column_mapping:
                continue
            
            col_indices = self.column_mapping[field_id]
            for col_idx in col_indices:
                self.df.iloc[row_index, col_idx] = value
        
        self.logger.debug(f"Оновлено рядок {row_index}: {updates}")
    
    def get_row_data(self, row_index: int) -> dict:
        """Повертає всі дані рядка як словник"""
        if self.df is None:
            return {}
        
        return self.df.iloc[row_index].to_dict()
