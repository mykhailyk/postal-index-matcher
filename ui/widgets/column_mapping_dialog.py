"""
Оновлений діалог налаштування колонок з ВИДИМИМИ галочками
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QComboBox, QCheckBox, QScrollArea, QWidget, QFrame, QSplitter
)
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QColor
import pandas as pd
from typing import Dict, List

from handlers.column_mapping_handler import ColumnMappingHandler
from utils.logger import Logger


class MultiSelectComboBox(QComboBox):
    """
    Випадаючий список з можливістю множинного вибору через чекбокси
    З ВИДИМИМИ галочками ☑ / ☐
    """
    
    def __init__(self, items: List[str], parent=None):
        super().__init__(parent)
        
        self.items = items
        self.checked_items = set()
        
        # Додаємо пункти
        self.addItem("-- Оберіть стовпці --")
        
        # Додаємо пункти з порожніми галочками
        for item in items:
            self.addItem(f"☐ {str(item)}")
        
        # Підключаємо обробник
        self.view().pressed.connect(self.on_item_pressed)
        
        self.setEditable(False)
    
    def on_item_pressed(self, index):
        """Обробка кліку по елементу"""
        row = index.row()
        
        if row == 0:  # Заголовок
            return
        
        # Отримуємо текст без галочки
        item_text = self.itemText(row).replace("☐ ", "").replace("☑ ", "")
        
        # Перемикаємо стан
        if item_text in self.checked_items:
            self.checked_items.remove(item_text)
            # Ставимо порожню галочку
            self.setItemText(row, f"☐ {item_text}")
        else:
            self.checked_items.add(item_text)
            # Ставимо заповнену галочку
            self.setItemText(row, f"☑ {item_text}")
        
        # Оновлюємо текст в combobox
        self.update_text()
    
    def update_text(self):
        """Оновлює текст у combobox"""
        if not self.checked_items:
            self.setItemText(0, "-- Оберіть стовпці --")
        else:
            count = len(self.checked_items)
            if count == 1:
                suffix = "стовпець"
            elif 2 <= count <= 4:
                suffix = "стовпці"
            else:
                suffix = "стовпців"
            self.setItemText(0, f"✓ Обрано: {count} {suffix}")
    
    def get_checked_items(self) -> List[str]:
        """Повертає список обраних елементів (БЕЗ галочок)"""
        return list(self.checked_items)
    
    def set_checked_items(self, items: List[str]):
        """Встановлює обрані елементи"""
        # Очищаємо попередні
        self.checked_items = set()
        
        # Проходимо по всіх пунктах і оновлюємо галочки
        for row in range(1, self.count()):
            item_text = self.itemText(row).replace("☐ ", "").replace("☑ ", "")
            
            if str(item_text) in [str(item) for item in items]:
                # Ставимо заповнену галочку
                self.setItemText(row, f"☑ {item_text}")
                self.checked_items.add(item_text)
            else:
                # Ставимо порожню галочку
                self.setItemText(row, f"☐ {item_text}")
        
        self.update_text()


class ColumnMappingDialog(QDialog):
    """
    Діалог налаштування відповідності стовпців Excel до полів програми
    """
    
    def __init__(self, excel_columns: List[str], current_mapping: Dict, 
                 df_sample: pd.DataFrame, parent=None):
        super().__init__(parent)
        
        # Конвертуємо всі колонки в string
        self.excel_columns = [str(col) for col in excel_columns]
        self.current_mapping = current_mapping or {}
        self.df_sample = df_sample
        self.logger = Logger()
        
        # QSettings для збереження налаштувань
        self.settings = QSettings('PrintTo', 'AddressMatcher')
        
        # Комбобокси для кожного поля
        self.combo_boxes = {}
        
        # Splitter
        self.main_splitter = None
        
        self._init_ui()
        self._load_current_mapping()
        self._restore_geometry()
        
        # Центруємо діалог
        if parent:
            self.move(
                parent.x() + (parent.width() - self.width()) // 2,
                parent.y() + (parent.height() - self.height()) // 2
            )
    
    def _init_ui(self):
        """Ініціалізація UI"""
        self.setWindowTitle("⚙ Налаштування відповідності стовпців")
        
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Заголовок
        header = QLabel("Налаштуйте відповідність стовпців Excel до полів програми")
        header.setStyleSheet("""
            font-size: 13px;
            font-weight: bold;
            padding: 8px;
            background-color: #e3f2fd;
            border-radius: 4px;
        """)
        layout.addWidget(header)
        
        # Кнопки схем ВГОРІ
        scheme_layout = QHBoxLayout()
        
        load_btn = QPushButton("📂 Завантажити схему")
        load_btn.setStyleSheet(self._button_style("#2196F3", size="10px"))
        load_btn.clicked.connect(self.load_mapping_scheme)
        scheme_layout.addWidget(load_btn)
        
        save_btn = QPushButton("💾 Зберегти схему")
        save_btn.setStyleSheet(self._button_style("#4CAF50", size="10px"))
        save_btn.clicked.connect(self.save_mapping_scheme)
        scheme_layout.addWidget(save_btn)
        
        scheme_layout.addStretch()
        layout.addLayout(scheme_layout)
        
        # Інструкція
        instruction = QLabel(
            "💡 Клікайте на пункти у списку щоб поставити/зняти галочки. Можна обрати декілька."
        )
        instruction.setWordWrap(True)
        instruction.setStyleSheet("font-size: 10px; color: #666; padding: 3px;")
        layout.addWidget(instruction)
        
        # Головний splitter
        self.main_splitter = QSplitter(Qt.Vertical)
        
        # === ВЕРХНЯ ЧАСТИНА: Налаштування полів ===
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: 1px solid #ddd; }")
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_layout.setSpacing(5)
        scroll_layout.setContentsMargins(5, 5, 5, 5)
        scroll_widget.setLayout(scroll_layout)
        
        # Поля програми
        fields = [
            ('client_id', '🆔 ID', 'Унікальний ідентифікатор'),
            ('name', '👤 ПІБ', "Ім'я одержувача"),
            ('region', '🗺️ Область', 'Область'),
            ('district', '📍 Район', 'Район'),
            ('city', '🏙️ Місто', 'Населений пункт'),
            ('street', '🛣️ Вулиця', 'Назва вулиці'),
            ('building', '🏠 Будинок', 'Номер будинку'),
            ('index', '📮 Індекс', 'Поштовий індекс'),
        ]
        
        for field_id, field_name, field_desc in fields:
            field_widget = self._create_field_widget(field_id, field_name, field_desc)
            scroll_layout.addWidget(field_widget)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        
        self.main_splitter.addWidget(scroll)
        
        # === НИЖНЯ ЧАСТИНА: Превʼю ===
        preview_container = QWidget()
        preview_layout = QVBoxLayout()
        preview_layout.setContentsMargins(0, 5, 0, 0)
        preview_layout.setSpacing(3)
        
        preview_label = QLabel("📋 Приклад даних (перші 5 рядків):")
        preview_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        preview_layout.addWidget(preview_label)
        
        self.preview_table = QTableWidget()
        self.preview_table.setStyleSheet("""
            QTableWidget {
                font-size: 9px;
                gridline-color: #ddd;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                padding: 3px;
                border: 1px solid #ddd;
                font-weight: bold;
                font-size: 9px;
            }
        """)
        self._populate_preview()
        preview_layout.addWidget(self.preview_table)
        
        preview_container.setLayout(preview_layout)
        self.main_splitter.addWidget(preview_container)
        
        # Початкові розміри splitter
        self.main_splitter.setSizes([400, 150])
        
        layout.addWidget(self.main_splitter)
        
        # Кнопки OK/Скасувати
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Скасувати")
        cancel_btn.setStyleSheet(self._button_style("#757575"))
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        ok_btn = QPushButton("✓ OK")
        ok_btn.setStyleSheet(self._button_style("#4CAF50"))
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def _create_field_widget(self, field_id: str, field_name: str, field_desc: str) -> QFrame:
        """Створює компактний віджет для одного поля"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Box | QFrame.Plain)
        frame.setStyleSheet("""
            QFrame {
                border: 1px solid #e0e0e0;
                border-radius: 3px;
                background-color: white;
            }
        """)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)
        
        # Назва поля
        label_widget = QWidget()
        label_layout = QVBoxLayout()
        label_layout.setSpacing(1)
        label_layout.setContentsMargins(0, 0, 0, 0)
        
        name_label = QLabel(field_name)
        name_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        label_layout.addWidget(name_label)
        
        desc_label = QLabel(field_desc)
        desc_label.setStyleSheet("font-size: 9px; color: #888;")
        label_layout.addWidget(desc_label)
        
        label_widget.setLayout(label_layout)
        label_widget.setFixedWidth(130)
        layout.addWidget(label_widget)
        
        # Випадаючий список
        combo = MultiSelectComboBox(self.excel_columns)
        combo.setMinimumWidth(300)
        combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #ddd;
                border-radius: 3px;
                padding: 5px 8px;
                font-size: 10px;
                background-color: white;
            }
            QComboBox:hover {
                border-color: #2196F3;
            }
            QComboBox:focus {
                border-color: #2196F3;
                border-width: 2px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: url(none);
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #666;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #ddd;
                selection-background-color: #e3f2fd;
                font-size: 10px;
            }
        """)
        
        self.combo_boxes[field_id] = combo
        layout.addWidget(combo)
        
        layout.addStretch()
        
        frame.setLayout(layout)
        return frame
    
    def _populate_preview(self):
        """Заповнює таблицю превʼю"""
        if self.df_sample is None or self.df_sample.empty:
            return
        
        df = self.df_sample.head(5)
        
        self.preview_table.setRowCount(len(df))
        self.preview_table.setColumnCount(len(df.columns))
        self.preview_table.setHorizontalHeaderLabels([str(col) for col in df.columns])
        
        for i in range(len(df)):
            for j in range(len(df.columns)):
                value = df.iloc[i, j]
                item = QTableWidgetItem(str(value) if pd.notna(value) else "")
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.preview_table.setItem(i, j, item)
        
        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.preview_table.horizontalHeader().setStretchLastSection(True)
        
        for i in range(self.preview_table.rowCount()):
            self.preview_table.setRowHeight(i, 20)
    
    def _load_current_mapping(self):
        """Завантажує поточний mapping у combobox-и"""
        for field_id, combo in self.combo_boxes.items():
            if field_id in self.current_mapping:
                column_indices = self.current_mapping[field_id]
                column_names = [str(self.excel_columns[idx]) for idx in column_indices 
                              if idx < len(self.excel_columns)]
                combo.set_checked_items(column_names)
    
    def get_mapping(self) -> Dict[str, List[int]]:
        """Повертає mapping"""
        mapping = {}
        
        for field_id, combo in self.combo_boxes.items():
            checked_items = combo.get_checked_items()
            
            if checked_items:
                indices = []
                for col in checked_items:
                    try:
                        idx = self.excel_columns.index(str(col))
                        indices.append(idx)
                    except ValueError:
                        self.logger.warning(f"Колонка '{col}' не знайдена")
                
                if indices:
                    mapping[field_id] = indices
        
        return mapping
    
    def accept(self):
        """Перевірка перед закриттям"""
        mapping = self.get_mapping()
        
        if 'city' not in mapping:
            QMessageBox.warning(
                self,
                "Увага",
                "Поле 'Місто' обов'язкове!\nБудь ласка, оберіть стовпець для міста."
            )
            return
        
        if 'street' not in mapping:
            reply = QMessageBox.question(
                self,
                "Підтвердження",
                "Поле 'Вулиця' не налаштовано.\n\nПродовжити без вулиці?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        
        self._save_geometry()
        self.logger.info(f"Column mapping встановлено: {mapping}")
        super().accept()
    
    def reject(self):
        """Зберігаємо розміри при скасуванні"""
        self._save_geometry()
        super().reject()
    
    def _restore_geometry(self):
        """Відновлює розміри через QSettings"""
        self.settings.beginGroup('ColumnMappingDialog')
        
        x = self.settings.value('x', 100, type=int)
        y = self.settings.value('y', 100, type=int)
        width = self.settings.value('width', 700, type=int)
        height = self.settings.value('height', 600, type=int)
        
        self.setGeometry(x, y, width, height)
        
        # Розміри splitter
        splitter_sizes = self.settings.value('splitter_sizes', [400, 150])
        if splitter_sizes and self.main_splitter:
            if isinstance(splitter_sizes, list):
                splitter_sizes = [int(s) for s in splitter_sizes]
                self.main_splitter.setSizes(splitter_sizes)
        
        self.settings.endGroup()
    
    def _save_geometry(self):
        """Зберігає розміри через QSettings"""
        self.settings.beginGroup('ColumnMappingDialog')
        
        geometry = self.geometry()
        self.settings.setValue('x', geometry.x())
        self.settings.setValue('y', geometry.y())
        self.settings.setValue('width', geometry.width())
        self.settings.setValue('height', geometry.height())
        
        if self.main_splitter:
            sizes = self.main_splitter.sizes()
            self.settings.setValue('splitter_sizes', sizes)
        
        self.settings.endGroup()
    
    def save_mapping_scheme(self):
        """Зберігає схему mapping"""
        from PyQt5.QtWidgets import QInputDialog
        
        name, ok = QInputDialog.getText(
            self,
            "Зберегти схему",
            "Введіть назву схеми:"
        )
        
        if ok and name:
            mapping = self.get_mapping()
            success = ColumnMappingHandler.save_mapping(name, mapping)
            
            if success:
                QMessageBox.information(self, "Успіх", f"Схему '{name}' збережено!")
            else:
                QMessageBox.critical(self, "Помилка", "Не вдалося зберегти схему")
    
    def load_mapping_scheme(self):
        """Завантажує схему mapping"""
        from PyQt5.QtWidgets import QInputDialog
        
        schemes = ColumnMappingHandler.list_mappings()
        
        if not schemes:
            QMessageBox.information(self, "Інформація", "Немає збережених схем")
            return
        
        name, ok = QInputDialog.getItem(
            self,
            "Завантажити схему",
            "Оберіть схему:",
            schemes,
            0,
            False
        )
        
        if ok and name:
            mapping = ColumnMappingHandler.load_mapping(name)
            
            if mapping:
                for field_id, column_indices in mapping.items():
                    if field_id in self.combo_boxes:
                        column_names = [str(self.excel_columns[idx]) for idx in column_indices 
                                      if idx < len(self.excel_columns)]
                        self.combo_boxes[field_id].set_checked_items(column_names)
                
                QMessageBox.information(self, "Успіх", f"Схему '{name}' завантажено!")
            else:
                QMessageBox.critical(self, "Помилка", "Не вдалося завантажити схему")
    
    def _button_style(self, bg_color="#2196F3", size="11px"):
        """Стиль кнопки"""
        color = QColor(bg_color)
        h, s, v, a = color.getHsv()
        hover_v = max(0, int(v * 0.8))
        hover_color = QColor()
        hover_color.setHsv(h, s, hover_v, a)
        
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: white;
                border: none;
                border-radius: 3px;
                padding: 6px 12px;
                font-size: {size};
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {hover_color.name()};
            }}
            QPushButton:pressed {{
                background-color: {bg_color};
                padding-top: 7px;
                padding-bottom: 5px;
            }}
        """