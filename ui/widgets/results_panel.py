"""
Панель результатів пошуку - ОСТАТОЧНА ВЕРСІЯ
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QListWidget, QListWidgetItem, QSpinBox
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QFont


class ResultsPanel(QWidget):
    """Панель відображення результатів пошуку"""
    
    index_selected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_results = []
        self.font_size = 9  # Початковий розмір шрифту
        self.buildings_per_line = 20  # Скільки будинків на рядок
        self.init_ui()
    
    def init_ui(self):
        """Ініціалізація інтерфейсу"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Заголовок
        header = QLabel("Результати пошуку")
        header.setStyleSheet("font-weight: bold; font-size: 12px; padding: 5px;")
        layout.addWidget(header)
        
        # Контроль кількості результатів та налаштування
        control_layout = QHBoxLayout()
        
        control_layout.addWidget(QLabel("Показувати:"))
        self.result_count_spin = QSpinBox()
        self.result_count_spin.setRange(1, 50)
        self.result_count_spin.setValue(20)
        self.result_count_spin.setMaximumWidth(60)
        self.result_count_spin.valueChanged.connect(self.on_result_count_changed)
        control_layout.addWidget(self.result_count_spin)
        
        control_layout.addWidget(QLabel(" | Шрифт:"))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 16)
        self.font_size_spin.setValue(9)
        self.font_size_spin.setMaximumWidth(50)
        self.font_size_spin.valueChanged.connect(self.on_font_size_changed)
        control_layout.addWidget(self.font_size_spin)
        
        control_layout.addWidget(QLabel(" | Будинків:"))
        self.buildings_spin = QSpinBox()
        self.buildings_spin.setRange(5, 30)
        self.buildings_spin.setValue(20)
        self.buildings_spin.setMaximumWidth(50)
        self.buildings_spin.valueChanged.connect(self.on_buildings_count_changed)
        control_layout.addWidget(self.buildings_spin)
        
        control_layout.addStretch()
        layout.addLayout(control_layout)
        
        # Список результатів
        self.results_list = QListWidget()
        self.results_list.setAlternatingRowColors(True)
        self.results_list.setWordWrap(True)
        
        # ⬇️ СТИЛЬ БЕЗ РАМКИ - ТІЛЬКИ ЖИРНИЙ ШРИФТ
        self.results_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #c0c0c0;
                background-color: white;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #e0e0e0;
            }
            QListWidget::item:alternate {
                background-color: #f9f9f9;
            }
            QListWidget::item:hover {
                background-color: #f0f0f0;
            }
            QListWidget::item:selected {
                background-color: transparent;
                color: #000000;
            }
            QListWidget::item:selected:hover {
                background-color: #f5f5f5;
            }
        """)
        
        self.results_list.itemDoubleClicked.connect(self.on_result_double_clicked)
        self.results_list.itemSelectionChanged.connect(self.on_selection_changed)
        layout.addWidget(self.results_list)
    
    def on_selection_changed(self):
        """Обробка зміни вибору - робимо жирним"""
        selected_items = self.results_list.selectedItems()
        
        # Прибираємо жирний з усіх
        for i in range(self.results_list.count()):
            item = self.results_list.item(i)
            font = QFont()
            font.setPointSize(self.font_size)
            font.setBold(False)
            item.setFont(font)
        
        # Робимо жирним вибраний
        if selected_items:
            font = QFont()
            font.setPointSize(self.font_size)
            font.setBold(True)
            selected_items[0].setFont(font)
    
    def on_result_count_changed(self, value):
        """Обробка зміни кількості результатів"""
        if self.current_results:
            self.show_results(self.current_results, "")
    
    def on_font_size_changed(self, value):
        """Зміна розміру шрифту"""
        self.font_size = value
        if self.current_results:
            self.show_results(self.current_results, "")
    
    def on_buildings_count_changed(self, value):
        """Зміна кількості будинків на рядок"""
        self.buildings_per_line = value
        if self.current_results:
            self.show_results(self.current_results, "")
    
    def show_results(self, results, building_number=""):
        """Відображає результати пошуку"""
        self.current_results = results
        self.results_list.clear()
        
        if not results:
            item = QListWidgetItem("❌ Нічого не знайдено")
            item.setFlags(Qt.NoItemFlags)
            self.results_list.addItem(item)
            return
        
        max_results = self.result_count_spin.value()
        
        for i, result in enumerate(results[:max_results]):
            confidence = result.get('confidence', 0)
            index = result.get('index', '')
            city = result.get('city_ua', '')
            street = result.get('street_ua', '')
            buildings = result.get('buildings', '')
            not_working = result.get('not_working', '')
            
            # Індикатор точності
            if confidence >= 90:
                icon = "🟢"
            elif confidence >= 70:
                icon = "🟡"
            else:
                icon = "🔴"
            
            # Розбиваємо будинки на рядки
            buildings_list = [b.strip() for b in buildings.split(',') if b.strip()]
            buildings_lines = []
            
            for j in range(0, len(buildings_list), self.buildings_per_line):
                line_buildings = buildings_list[j:j + self.buildings_per_line]
                buildings_lines.append(','.join(line_buildings))
            
            # ⬇️ ФОРМАТ: НП, вулиця, будинки (рядок 1)
            text = f"{icon} {city}, {street}, {buildings_lines[0] if buildings_lines else ''}"
            
            # Додаємо інші рядки будинків
            if len(buildings_lines) > 1:
                for line in buildings_lines[1:]:
                    text += f"\n{line}"
            
            # ⬇️ ІНДЕКС НА НОВОМУ РЯДКУ (звичайний текст)
            text += f"\n{index} ({confidence}%)"
            
            # Додаткова інформація
            if not_working:
                if 'Тимчасово не функціонує' in not_working:
                    text += " ⚠️"
                if 'ВПЗ' in not_working:
                    text += " 📦"
            
            item = QListWidgetItem(text)
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            item.setData(Qt.UserRole, result)
            
            # Встановлюємо розмір шрифту
            font = QFont()
            font.setPointSize(self.font_size)
            item.setFont(font)
            
            self.results_list.addItem(item)

    
    def on_result_double_clicked(self, item):
        """Обробка подвійного кліку на результат"""
        result = item.data(Qt.UserRole)
        if result:
            index = result.get('index', '')
            not_working = result.get('not_working', '')
            
            if 'Тимчасово не функціонує' in not_working and 'ВПЗ' not in not_working:
                index = '*'
            elif 'ВПЗ' in not_working:
                import re
                match = re.search(r'(\d{5})', not_working)
                if match:
                    index = match.group(1)
                else:
                    index = '*'
            
            if index:
                self.index_selected.emit(index)
    
    def get_selected_result(self):
        """Повертає вибраний результат"""
        current_item = self.results_list.currentItem()
        if current_item:
            return current_item.data(Qt.UserRole)
        return None
    
    def clear(self):
        """Очищає результати"""
        self.results_list.clear()
        self.current_results = []
