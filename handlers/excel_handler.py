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
        
        # Для "розумного збереження"
        self.original_df = None
        self.field_to_col_name = {}  # {field: original_col_name}
    
    def load_file(self, file_path: str) -> pd.DataFrame:
        """Завантажує Excel файл з ЗБЕРЕЖЕННЯМ НУЛІВ"""
        try:
            # ✅ ЧИТАЄМО З АВТОМАТИЧНИМ ВИЗНАЧЕННЯМ ТИПІВ
            # Це важливо, щоб числа залишалися числами (0,444 -> float), а не ставали рядками з крапкою ("0.444")
            self.df = pd.read_excel(
                file_path,
                dtype=None,  # Автоматичні типи
                keep_default_na=False,
                na_values=['']  # Тільки пусті рядки як NaN
            )
            
            # ✅ Замінюємо NaN на пусті рядки (для коректного відображення в UI)
            self.df = self.df.fillna("")
            
            # ✅ ВИДАЛІТЬ ПУСТІ РЯДКИ
            self.df = self.df.dropna(how='all').reset_index(drop=True)
            
            self.file_path = file_path
            self.logger.info(f"✓ Завантажено файл: {file_path}")
            self.logger.info(f"✓ Рядків: {len(self.df)}")
            self.logger.info(f"✓ Колон: {len(self.df.columns)}")
            
            # ✅ ЛОГУВАННЯ - показуємо скільки даних
            for col in self.df.columns:
                non_empty = self.df[col].notna().sum()
                sample = self.df[col].iloc[0] if len(self.df) > 0 else "N/A"
                self.logger.debug(f"   • {col}: {non_empty} значень (приклад: {sample})")
            
            return self.df
        
        except Exception as e:
            self.logger.error(f"❌ Помилка завантаження файлу {file_path}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
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
        
        # Оновлюємо мапінг полів на назви колонок
        if self.df is not None:
            self.field_to_col_name = {}
            for field, col_indices in mapping.items():
                if col_indices:
                    # Беремо першу колонку для поля (зазвичай одна)
                    col_idx = col_indices[0]
                    if col_idx < len(self.df.columns):
                        self.field_to_col_name[field] = self.df.columns[col_idx]
    
    def apply_column_filter(self):
        """
        Залишає в self.df ТІЛЬКИ налаштовані колонки.
        Зберігає оригінал в self.original_df.
        Додає _original_row_index для зв'язку.
        """
        if self.df is None or not self.column_mapping:
            return
        
        try:
            # 1. Зберігаємо оригінал (якщо ще не збережено)
            if self.original_df is None:
                self.original_df = self.df.copy()
                # Додаємо індекс рядка в оригінал, якщо немає
                if '_original_row_index' not in self.original_df.columns:
                    self.original_df['_original_row_index'] = self.original_df.index
            
            # 2. Збираємо потрібні колонки
            columns_to_keep = []
            new_mapping = {}
            
            # Спочатку додаємо колонку для зв'язку
            if '_original_row_index' not in self.df.columns:
                self.df['_original_row_index'] = self.df.index
            columns_to_keep.append('_original_row_index')
            
            # Проходимо по mapping і збираємо індекси колонок
            current_new_idx = 1  # 0 - це _original_row_index
            
            # Сортуємо поля для порядку (опціонально)
            # Але краще зберегти порядок як в mapping або як в оригіналі
            
            used_col_indices = set()
            
            for field, col_indices in self.column_mapping.items():
                new_indices_for_field = []
                for old_col_idx in col_indices:
                    if old_col_idx in used_col_indices:
                        continue
                        
                    col_name = self.original_df.columns[old_col_idx]
                    columns_to_keep.append(col_name)
                    new_indices_for_field.append(current_new_idx)
                    current_new_idx += 1
                    used_col_indices.add(old_col_idx)
                
                if new_indices_for_field:
                    new_mapping[field] = new_indices_for_field
            
            # 3. Фільтруємо DataFrame
            self.df = self.df[columns_to_keep].copy()
            
            # 4. Оновлюємо mapping на нові індекси
            self.column_mapping = new_mapping
            
            self.logger.info(f"✅ Фільтр застосовано. Залишилось колонок: {len(self.df.columns)}")
            self.logger.info(f"   Новий mapping: {new_mapping}")
            
        except Exception as e:
            self.logger.error(f"❌ Помилка фільтрації колонок: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            # Відкат
            if self.original_df is not None:
                self.df = self.original_df.copy()
    
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
