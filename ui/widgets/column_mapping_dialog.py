"""
Діалог налаштування відповідності стовпців
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, 
    QPushButton, QGroupBox, QGridLayout, QTableWidget, QTableWidgetItem,
    QComboBox, QMessageBox, QLineEdit, QInputDialog, QListWidgetItem
)
from PyQt5.QtCore import Qt
from handlers.column_mapping_handler import ColumnMappingHandler
import pandas as pd


class ColumnMappingDialog(QDialog):
    """Діалог для налаштування відповідності стовпців"""
    
    def __init__(self, column_names, current_mapping, df_sample, parent=None):
        super().__init__(parent)
        
        self.column_names = column_names
        self.current_mapping = current_mapping or {}
        self.df_sample = df_sample
        
        # Нормалізуємо mapping
        self.normalize_mapping()
        
        self.combos = {}
        
        self.init_ui()
    
    def normalize_mapping(self):
        """Нормалізує mapping"""
        normalized = {}
        for field, value in self.current_mapping.items():
            if isinstance(value, int):
                normalized[field] = [value]
            elif isinstance(value, list):
                normalized[field] = value
            else:
                normalized[field] = []
        self.current_mapping = normalized
    
    def init_ui(self):
        """Ініціалізує UI"""
        self.setWindowTitle("Налаштування відповідності стовпців")
        self.setMinimumSize(900, 700)
        
        layout = QVBoxLayout()
        
        # Заголовок
        title = QLabel("⚙ Налаштування відповідності стовпців Excel")
        title.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        layout.addWidget(title)
        
        # Інструкція
        instruction = QLabel(
            "Поставте галочки напроти стовпців Excel для кожного поля адреси. "
            "Можна вибрати кілька стовпців (вони об'єднаються через кому)."
        )
        instruction.setWordWrap(True)
        instruction.setStyleSheet("padding: 5px; color: #666;")
        layout.addWidget(instruction)
        
        # Групи налаштувань
        mapping_group = QGroupBox("Відповідність полів")
        mapping_layout = QGridLayout()
        
        # СПИСОК ПОЛІВ БЕЗ "Старий індекс"
        fields = [
            ('client_id', 'ID Клієнта'),
            ('name', 'ПІБ / Назва'),
            ('region', 'Область'),
            ('district', 'Район'),
            ('city', 'Населений пункт'),
            ('street', 'Вулиця'),
            ('building', 'Будинок'),
            ('index', 'Індекс')
        ]
        
        row = 0
        for field_id, field_name in fields:
            label = QLabel(f"{field_name}:")
            label.setStyleSheet("font-weight: bold; font-size: 11px;")
            label.setFixedWidth(120)
            mapping_layout.addWidget(label, row, 0)
            
            # Список з чекбоксами
            list_widget = QListWidget()
            list_widget.setMaximumHeight(80)
            list_widget.setMaximumWidth(250)
            
            for i, col_name in enumerate(self.column_names):
                item = QListWidgetItem(str(col_name))
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                
                # Чекбокс замість селекції
                if field_id in self.current_mapping and i in self.current_mapping[field_id]:
                    item.setCheckState(Qt.Checked)
                else:
                    item.setCheckState(Qt.Unchecked)
                
                list_widget.addItem(item)
            
            self.combos[field_id] = list_widget
            mapping_layout.addWidget(list_widget, row, 1)
            
            row += 1
        
        mapping_group.setLayout(mapping_layout)
        layout.addWidget(mapping_group)
        
        # Preview
        preview_group = QGroupBox("Попередній перегляд (перші 5 рядків)")
        preview_layout = QVBoxLayout()
        
        self.preview_table = QTableWidget()
        self.preview_table.setMaximumHeight(200)
        self.update_preview()
        
        preview_layout.addWidget(self.preview_table)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        
        # Збереження схем
        schemes_layout = QHBoxLayout()
        
        schemes_label = QLabel("Схеми:")
        schemes_label.setStyleSheet("font-weight: bold;")
        schemes_layout.addWidget(schemes_label)
        
        self.scheme_combo = QComboBox()
        self.load_scheme_list()
        schemes_layout.addWidget(self.scheme_combo, 1)
        
        load_scheme_btn = QPushButton("Завантажити")
        load_scheme_btn.clicked.connect(self.load_scheme)
        schemes_layout.addWidget(load_scheme_btn)
        
        save_scheme_btn = QPushButton("Зберегти")
        save_scheme_btn.clicked.connect(self.save_scheme)
        schemes_layout.addWidget(save_scheme_btn)
        
        layout.addLayout(schemes_layout)
        
        # Кнопки OK/Cancel
        buttons = QHBoxLayout()
        
        preview_btn = QPushButton("Оновити preview")
        preview_btn.clicked.connect(self.update_preview)
        buttons.addWidget(preview_btn)
        
        buttons.addStretch()
        
        cancel_btn = QPushButton("Скасувати")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)
        
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 5px 20px;")
        buttons.addWidget(ok_btn)
        
        layout.addLayout(buttons)
        
        self.setLayout(layout)
    
    def get_mapping(self):
        """Повертає обране mapping"""
        mapping = {}
        
        for field_id, list_widget in self.combos.items():
            selected_indices = []
            
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                if item.checkState() == Qt.Checked:
                    selected_indices.append(i)
            
            if selected_indices:
                mapping[field_id] = selected_indices
        
        return mapping
    
    def update_preview(self):
        """Оновлює preview таблиці"""
        mapping = self.get_mapping()
        
        if not mapping:
            return
        
        # Створюємо preview DataFrame
        preview_data = {}
        
        for field_id, col_indices in mapping.items():
            values = []
            for i in range(min(5, len(self.df_sample))):
                row_values = []
                for col_idx in col_indices:
                    if col_idx < len(self.df_sample.columns):
                        val = self.df_sample.iloc[i, col_idx]
                        if pd.notna(val):
                            row_values.append(str(val))
                
                values.append(', '.join(row_values) if row_values else '')
            
            preview_data[field_id] = values
        
        # Відображаємо в таблиці
        df_preview = pd.DataFrame(preview_data)
        
        self.preview_table.setRowCount(len(df_preview))
        self.preview_table.setColumnCount(len(df_preview.columns))
        
        # МАПА НАЗВ БЕЗ "Старий індекс"
        field_names_map = {
            'client_id': 'ID Клієнта',
            'name': 'ПІБ',
            'region': 'Область',
            'district': 'Район',
            'city': 'Місто',
            'street': 'Вулиця',
            'building': 'Будинок',
            'index': 'Індекс'
        }
        header_labels = [field_names_map.get(col, col) for col in df_preview.columns]
        self.preview_table.setHorizontalHeaderLabels(header_labels)
        
        for i in range(len(df_preview)):
            for j, col in enumerate(df_preview.columns):
                value = df_preview.iloc[i, j]
                item = QTableWidgetItem(str(value))
                self.preview_table.setItem(i, j, item)
        
        self.preview_table.resizeColumnsToContents()
    
    def load_scheme_list(self):
        """Завантажує список схем"""
        schemes = ColumnMappingHandler.list_mappings()
        self.scheme_combo.clear()
        self.scheme_combo.addItems(schemes)
    
    def load_scheme(self):
        """Завантажує схему"""
        scheme_name = self.scheme_combo.currentText()
        if not scheme_name:
            return
        
        mapping = ColumnMappingHandler.load_mapping(scheme_name)
        if not mapping:
            QMessageBox.warning(self, "Помилка", "Не вдалося завантажити схему")
            return
        
        # Застосовуємо mapping
        self.current_mapping = mapping
        self.normalize_mapping()
        
        # Оновлюємо UI
        for field_id, list_widget in self.combos.items():
            # Скидаємо всі чекбокси
            for i in range(list_widget.count()):
                list_widget.item(i).setCheckState(Qt.Unchecked)
            
            # Ставимо галочки
            if field_id in self.current_mapping:
                for col_idx in self.current_mapping[field_id]:
                    if 0 <= col_idx < list_widget.count():
                        list_widget.item(col_idx).setCheckState(Qt.Checked)
        
        self.update_preview()
        QMessageBox.information(self, "Успіх", f"Схему '{scheme_name}' завантажено!")
    
    def save_scheme(self):
        """Зберігає схему"""
        name, ok = QInputDialog.getText(
            self, 
            "Зберегти схему", 
            "Введіть назву схеми:"
        )
        
        if not ok or not name:
            return
        
        # Отримуємо поточне mapping
        mapping = self.get_mapping()
        
        # Зберігаємо
        if ColumnMappingHandler.save_mapping(name, mapping):
            self.load_scheme_list()
            idx = self.scheme_combo.findText(name)
            if idx >= 0:
                self.scheme_combo.setCurrentIndex(idx)
            QMessageBox.information(self, "Успіх", f"Схему '{name}' збережено!")
        else:
            QMessageBox.warning(self, "Помилка", "Не вдалося зберегти схему")
