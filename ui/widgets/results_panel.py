"""
Панель результатів пошуку
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QListWidget, QListWidgetItem, QSpinBox
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QColor, QBrush
import config


class ResultsPanel(QWidget):
    """Панель для відображення результатів пошуку"""
    
    index_double_clicked = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_results = []
        self.init_ui()
    
    def init_ui(self):
        """Ініціалізує UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        
        # Заголовок
        header = QLabel("📋 Результати пошуку")
        header.setStyleSheet("font-weight: bold; font-size: 13px; padding: 5px;")
        layout.addWidget(header)
        
        # Налаштування
        controls = QHBoxLayout()
        
        label = QLabel("Будинків на рядок:")
        label.setStyleSheet("font-size: 10px;")
        controls.addWidget(label)
        
        self.buildings_per_line_spinbox = QSpinBox()
        self.buildings_per_line_spinbox.setMinimum(5)
        self.buildings_per_line_spinbox.setMaximum(60)
        self.buildings_per_line_spinbox.setValue(12)
        self.buildings_per_line_spinbox.setStyleSheet("font-size: 10px; padding: 2px;")
        self.buildings_per_line_spinbox.valueChanged.connect(self.refresh_results)
        controls.addWidget(self.buildings_per_line_spinbox)
        
        # ДОДАНО: Контроль розміру шрифту
        font_label = QLabel("Шрифт:")
        font_label.setStyleSheet("font-size: 10px; margin-left: 10px;")
        controls.addWidget(font_label)
        
        self.results_font_spinbox = QSpinBox()
        self.results_font_spinbox.setMinimum(9)
        self.results_font_spinbox.setMaximum(14)
        self.results_font_spinbox.setValue(11)
        self.results_font_spinbox.setSuffix(" px")
        self.results_font_spinbox.setStyleSheet("font-size: 10px; padding: 2px;")
        self.results_font_spinbox.valueChanged.connect(self.update_font_size)
        controls.addWidget(self.results_font_spinbox)
        
        controls.addStretch()
        layout.addLayout(controls)
        
        # Список результатів
        self.results_list = QListWidget()
        self.results_list.setWordWrap(True)
        self.results_list.itemDoubleClicked.connect(self.on_result_double_clicked)
        
        # Зберігаємо базовий stylesheet
        self.base_stylesheet = """
            QListWidget {
                border: 1px solid #ddd;
                background-color: white;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                border: 2px solid #2196F3;
                background-color: rgba(33, 150, 243, 0.2);
            }
            QListWidget::item:hover {
                border: 1px solid #2196F3;
            }
        """
        self.update_font_size(11)  # Встановлюємо початковий розмір
        layout.addWidget(self.results_list)
        
        # Підказка
        hint = QLabel("💡 Подвійний клік для швидкого застосування")
        hint.setStyleSheet("color: #666; font-size: 9px; padding: 5px;")
        layout.addWidget(hint)
        
        self.setLayout(layout)

    def update_font_size(self, size):
        """Оновлює розмір шрифту результатів"""
        stylesheet = self.base_stylesheet.replace(
            "QListWidget {",
            f"QListWidget {{\n            font-size: {size}px;"
        )
        self.results_list.setStyleSheet(stylesheet)

    
    def show_results(self, results, query_building=""):
        """
        Показує результати пошуку
        
        Args:
            results: Список результатів з полями region, city, street, index тощо
            query_building: Номер будинку з запиту для підсвічування
        """
        self.current_results = results
        self._last_query_building = query_building
        self.results_list.clear()
        
        if not results:
            item = QListWidgetItem("❌ Нічого не знайдено")
            item.setForeground(QBrush(QColor(150, 150, 150)))
            self.results_list.addItem(item)
            return
        
        max_per_line = self.buildings_per_line_spinbox.value()
        
        for i, result in enumerate(results, 1):
            confidence = result.get('confidence', 0)
            
            # Форматуємо будинки з підсвічуванням
            buildings = result.get('buildings', '')
            if buildings and query_building:
                buildings_display = self.format_buildings_multiline(
                    buildings, 
                    query_building, 
                    max_per_line=max_per_line
                )
            else:
                buildings_display = self.format_buildings_multiline(
                    buildings, 
                    max_per_line=max_per_line
                )
            
            # Формуємо текст
            text = f"#{i} [{confidence}%] {result['city']}, {result['street']}"
            
            if result.get('district'):
                text += f"\n   Район: {result['district']}"
            
            text += f"\n   🏠 {buildings_display}"
            text += f"\n   📮 Індекс: {result['index']}"
            
            # Додаткова інформація
            if result.get('not_working'):
                text += f"\n   ⚠️ {result['not_working']}"
            elif result.get('features'):
                text += f"\n   ℹ️ {result['features']}"
            
            # Створюємо item
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, result)
            
            # КОЛЬОРОВЕ РОЗДІЛЕННЯ - ВИПРАВЛЕНО!
            if confidence >= 90:
                color_hex = "#C8E6C9"  # світло-зелений
            elif confidence >= 80:
                color_hex = "#FFF9C4"  # світло-жовтий
            elif confidence >= 70:
                color_hex = "#FFE0B2"  # світло-помаранчевий
            else:
                color_hex = "#FFCDD2"  # світло-червоний
            
            # Встановлюємо колір фону
            item.setBackground(QColor(color_hex))
            
            self.results_list.addItem(item)
    
    def format_buildings_multiline(self, buildings_str, highlight="", max_per_line=12):
        """
        Форматує будинки в кілька рядків з підсвічуванням
        
        Args:
            buildings_str: Рядок з будинками через кому
            highlight: Будинок для підсвічування
            max_per_line: Максимум будинків на рядок
        """
        if not buildings_str:
            return "—"
        
        buildings = [b.strip() for b in buildings_str.split(',')]
        
        # Підсвічуємо шуканий будинок
        if highlight:
            highlight_clean = highlight.upper().replace("-", "").replace(" ", "")
            formatted = []
            for b in buildings:
                b_clean = b.upper().replace("-", "").replace(" ", "")
                if b_clean == highlight_clean:
                    formatted.append(f"➤{b}⬅")  # Підсвічуємо стрілками
                else:
                    formatted.append(b)
            buildings = formatted
        
        # Розбиваємо на рядки
        lines = []
        for i in range(0, len(buildings), max_per_line):
            chunk = buildings[i:i + max_per_line]
            lines.append(", ".join(chunk))
        
        return "\n      ".join(lines)
    
    def refresh_results(self):
        """Оновлює відображення результатів при зміні налаштувань"""
        if self.current_results:
            query_building = ""
            if hasattr(self, '_last_query_building'):
                query_building = self._last_query_building
            self.show_results(self.current_results, query_building)
    
    def on_result_double_clicked(self, item):
        """Обробляє подвійний клік по результату"""
        result = item.data(Qt.UserRole)
        if result and 'index' in result:
            self.index_double_clicked.emit(result['index'])
    
    def clear_results(self):
        """Очищає результати"""
        self.results_list.clear()
        self.current_results = []
