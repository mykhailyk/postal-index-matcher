"""
Панель з результатами пошуку
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QListWidget, QPushButton, QFrame, QListWidgetItem, QMessageBox
)
from PyQt5.QtCore import pyqtSignal, Qt, QSize
from PyQt5.QtGui import QColor, QFont
import config
import re


class ResultsPanel(QWidget):
    """Панель для відображення результатів пошуку"""
    
    apply_index_clicked = pyqtSignal(dict)
    fix_address_clicked = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.current_results = []
        self.query_building = ""
        self.current_selected_row = -1
        
        self.init_ui()
    
    def init_ui(self):
        """Ініціалізує UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Заголовок з кількістю результатів
        header_layout = QHBoxLayout()
        title = QLabel("📊 Результати пошуку")
        title.setStyleSheet("font-weight: bold; font-size: 13px; padding: 5px;")
        header_layout.addWidget(title)
        
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #666; font-size: 11px; padding: 5px;")
        header_layout.addWidget(self.count_label)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Список результатів
        self.results_list = QListWidget()
        
        # СТИЛЬ БЕЗ ВИДІЛЕННЯ
        self.results_list.setStyleSheet("""
            QListWidget {
                font-size: 11px;
                border: 1px solid #ccc;
                background-color: white;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #E0E0E0;
                margin-bottom: 2px;
            }
            QListWidget::item:selected {
                background: transparent;
                border: none;
            }
            QListWidget::item:focus {
                outline: none;
            }
        """)
        
        # ВІДКЛЮЧАЄМО АВТОМАТИЧНЕ ВИДІЛЕННЯ
        self.results_list.setSelectionMode(QListWidget.NoSelection)
        
        self.results_list.itemClicked.connect(self.on_item_clicked)
        self.results_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.results_list)
        
        # Кнопки
        buttons = QHBoxLayout()
        
        self.apply_btn = QPushButton("✓ Застосувати індекс")
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self.on_apply_index)
        self.apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 6px; font-size: 11px;")
        buttons.addWidget(self.apply_btn)
        
        self.fix_address_btn = QPushButton("🔧 Виправити адресу")
        self.fix_address_btn.setEnabled(False)
        self.fix_address_btn.clicked.connect(self.on_fix_address)
        self.fix_address_btn.setStyleSheet("background-color: #FF9800; color: white; padding: 6px; font-size: 11px;")
        buttons.addWidget(self.fix_address_btn)
        
        layout.addLayout(buttons)
        
        hint = QLabel("💡 Клік для вибору, подвійний клік = Застосувати")
        hint.setStyleSheet("color: #666; font-size: 10px; padding: 3px;")
        layout.addWidget(hint)
        
        self.setLayout(layout)
    
    def show_results(self, results, query_building=""):
        self.results_list.clear()
        self.current_results = results
        self.query_building = query_building
        self.current_selected_row = -1
        
        self.apply_btn.setEnabled(False)
        self.fix_address_btn.setEnabled(False)
        
        self.count_label.setText(f"Знайдено: {len(results)}")
        
        if not results:
            item = QListWidgetItem("❌ Нічого не знайдено")
            item.setData(Qt.UserRole, {'no_results': True})
            self.results_list.addItem(item)
            return
        
        first_result = results[0] if results else {}
        not_working = first_result.get('not_working', '')
        
        if not_working:
            if '⛔' in not_working or 'Тимчасово не функціонує' in not_working:
                text = f"⛔ {not_working}\n\n💡 Подвійний клік → індекс '*'"
                color = QColor(255, 224, 224, 180)
                special_index = '*'
            elif 'ВПЗ' in not_working:
                match = re.search(r'(\d{5})', not_working)
                special_index = match.group(1) if match else '**'
                text = f"📮 {not_working}\n\n💡 Подвійний клік → індекс '{special_index}'"
                color = QColor(255, 243, 224, 180)
            else:
                special_index = None
            
            if special_index:
                item = QListWidgetItem(text)
                item.setBackground(color)
                font = item.font()
                font.setBold(True)
                font.setPointSize(font.pointSize() + 1)
                item.setFont(font)
                item.setData(Qt.UserRole, {'index': special_index, 'special': True})
                self.results_list.addItem(item)
                self.apply_btn.setEnabled(True)
                return
        
        has_high_confidence = any(r.get('confidence', 0) >= 95 for r in results)
        self.fix_address_btn.setEnabled(has_high_confidence)
        
        for i, result in enumerate(results, 1):
            confidence = result.get('confidence', 0)
            city = result.get('city', '')
            street = result.get('street', '')
            region = result.get('region', '')
            district = result.get('district', '')
            index = result.get('index', '')
            not_working = result.get('not_working', '')
            buildings = result.get('buildings', '')
            
            text = f"#{i} [{confidence}%]\n"
            location_parts = []
            if region:
                location_parts.append(region)
            if district:
                location_parts.append(district)
            if city:
                location_parts.append(city)
            text += ", ".join(location_parts) + f"\n{street}"
            text += f"\n   → Індекс: {index}"
            
            if buildings:
                highlighted_buildings = self.highlight_matching_buildings(buildings, query_building)
                buildings_display = self.format_buildings_multiline(highlighted_buildings, max_per_line=12)
                text += f"\n   🏠 {buildings_display}"

            if not_working:
                text += f"\n   ⚠️ {not_working}"

            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, result)

            # КОЛЬОРОВЕ РОЗДІЛЕННЯ ПО ВІДСОТКАМ
            if confidence >= 90:
                bg_color = QColor(200, 230, 201)
            elif confidence >= 80:
                bg_color = QColor(255, 249, 196)
            elif confidence >= 70:
                bg_color = QColor(255, 224, 178)
            else:
                bg_color = QColor(255, 205, 210)

            item.setBackground(bg_color)

            # ДИНАМІЧНА ВИСОТА (залежно від кількості рядків тексту)
            line_count = text.count('\n') + 1
            item_height = max(80, line_count * 18)  # 18px на рядок
            item.setSizeHint(QSize(0, item_height))

            self.results_list.addItem(item)

        
        if results:
            self.apply_btn.setEnabled(True)
            
    def format_buildings_multiline(self, buildings_str, max_per_line=15):
        """Форматує список будинків з переносом на нові рядки"""
        buildings_list = [b.strip() for b in buildings_str.split(',')]
        
        lines = []
        current_line = []
        
        for building in buildings_list:
            current_line.append(building)
            if len(current_line) >= max_per_line:
                lines.append(", ".join(current_line))
                current_line = []
        
        if current_line:
            lines.append(", ".join(current_line))
        
        return "\n      ".join(lines)

    def clear_results(self):
        """Очищає результати пошуку"""
        self.results_list.clear()
        self.current_results = []
        self.query_building = ""
        self.current_selected_row = -1
        self.count_label.setText("")
        self.apply_btn.setEnabled(False)
        self.fix_address_btn.setEnabled(False)
            
    
    def highlight_matching_buildings(self, buildings_str, query_building):
        """Виділяє співпадаючі будинки жирним шрифтом через спеціальну розмітку"""
        if not query_building:
            return buildings_str
        
        # Нормалізуємо запит
        query_clean = query_building.strip().upper().replace(" ", "").replace("-", "").replace("А", "A").replace("Б", "B")
        
        buildings_list = [b.strip() for b in buildings_str.split(',')]
        highlighted_list = []
        
        for building in buildings_list:
            building_clean = building.upper().replace(" ", "").replace("-", "").replace("А", "A").replace("Б", "B")
            
            if query_clean == building_clean:
                # Позначаємо співпадаючі будинки символом ★
                highlighted_list.append(f"★{building}")
            else:
                highlighted_list.append(building)
        
        return ", ".join(highlighted_list)

    
    def on_item_clicked(self, item):
        """Виділяє елемент жирним шрифтом"""
        data = item.data(Qt.UserRole)
        if isinstance(data, dict) and data.get('no_results'):
            return
        
        # Скидаємо шрифт для всіх елементів
        for i in range(self.results_list.count()):
            list_item = self.results_list.item(i)
            font = list_item.font()
            font.setBold(False)
            list_item.setFont(font)
        
        # Робимо жирним вибраний
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        
        # Зберігаємо індекс
        self.current_selected_row = self.results_list.row(item)
    
    def on_item_double_clicked(self, item):
        data = item.data(Qt.UserRole)
        if isinstance(data, dict):
            if data.get('no_results'):
                return
            if data.get('special'):
                self.apply_index_clicked.emit(data)
                return
        self.on_apply_index()
    
    def on_apply_index(self):
        if self.current_selected_row < 0:
            QMessageBox.warning(self, "Увага", "Оберіть результат зі списку (клікніть на нього)")
            return
        
        if self.current_selected_row >= len(self.current_results):
            return
        
        result = self.current_results[self.current_selected_row]
        self.apply_index_clicked.emit(result)
    
    def on_fix_address(self):
        if self.current_selected_row < 0:
            QMessageBox.warning(self, "Увага", "Оберіть результат зі списку (клікніть на нього)")
            return
        
        if self.current_selected_row >= len(self.current_results):
            return
        
        result = self.current_results[self.current_selected_row]
        self.fix_address_clicked.emit(result)
