"""
Панель підбору адреси
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QGroupBox, QFormLayout, QCompleter, QComboBox
)
from PyQt5.QtCore import pyqtSignal, Qt
import config


class AddressSelectorPanel(QWidget):
    """Панель для ручного підбору адреси"""
    
    index_double_clicked = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.magistral_cache = []
        self.street_completer = None
        self.city_completer = None
        self.current_city_records = []
        
        self.init_ui()
    
    def init_ui(self):
        """Ініціалізує UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        
        # Заголовок
        header = QLabel("🔍 Підбір адреси")
        header.setStyleSheet("font-weight: bold; font-size: 13px; padding: 5px;")
        layout.addWidget(header)
        
        # Форма вводу
        form = QFormLayout()
        form.setSpacing(5)
        form.setContentsMargins(5, 5, 5, 5)
        
        # Область (тільки для читання, оновлюється автоматично)
        self.region_input = QLineEdit()
        self.region_input.setPlaceholderText("Автоматично")
        self.region_input.setStyleSheet("padding: 5px; font-size: 11px; background-color: #f0f0f0;")
        self.region_input.setReadOnly(True)
        form.addRow("Область:", self.region_input)
        
        # Місто
        self.city_input = QLineEdit()
        self.city_input.setPlaceholderText("Введіть місто")
        self.city_input.setStyleSheet("padding: 5px; font-size: 11px;")
        self.city_input.textChanged.connect(self.on_city_changed)
        self.city_input.returnPressed.connect(self.on_apply_index)
        form.addRow("Місто:", self.city_input)
        
        # Вулиця
        self.street_input = QLineEdit()
        self.street_input.setPlaceholderText("Введіть вулицю")
        self.street_input.setStyleSheet("padding: 5px; font-size: 11px;")
        self.street_input.textChanged.connect(self.on_street_changed)
        self.street_input.returnPressed.connect(self.on_apply_index)
        form.addRow("Вулиця:", self.street_input)
        
        # Випадашка для будинків (спочатку прихована)
        self.buildings_combo = QComboBox()
        self.buildings_combo.setStyleSheet("padding: 5px; font-size: 11px;")
        self.buildings_combo.currentIndexChanged.connect(self.on_building_selected)
        self.buildings_label = QLabel("Будинки:")
        form.addRow(self.buildings_label, self.buildings_combo)
        self.buildings_combo.hide()
        self.buildings_label.hide()
        
        # Індекс (великий, виділений)
        self.index_input = QLineEdit()
        self.index_input.setPlaceholderText("00000")
        self.index_input.setStyleSheet(
            "padding: 10px; font-size: 20px; font-weight: bold; "
            "border: 2px solid #2196F3; border-radius: 5px; text-align: center;"
        )
        self.index_input.setMaxLength(5)
        self.index_input.setAlignment(Qt.AlignCenter)
        self.index_input.returnPressed.connect(self.on_apply_index)
        form.addRow("→ Індекс:", self.index_input)
        
        layout.addLayout(form)
        
        # Кнопка застосування
        apply_btn = QPushButton("✓ Застосувати індекс (Enter)")
        apply_btn.clicked.connect(self.on_apply_index)
        apply_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; padding: 8px; "
            "font-weight: bold; font-size: 11px; margin: 5px;"
        )
        layout.addWidget(apply_btn)
        
        # Підказка
        hint = QLabel("💡 Введіть місто → вулицю → Enter застосує індекс")
        hint.setStyleSheet("color: #666; font-size: 9px; padding: 5px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        
        self.setLayout(layout)
    
    def set_magistral_cache(self, magistral_records):
        """Встановлює кеш magistral і створює автокомпліт"""
        self.magistral_cache = magistral_records
        
        # Створюємо словник міст з районами
        cities_with_districts = {}
        for record in magistral_records:
            if hasattr(record, 'city') and record.city:
                city_key = record.city.lower()
                if city_key not in cities_with_districts:
                    cities_with_districts[city_key] = set()
                
                district = getattr(record, 'new_district', None) or getattr(record, 'old_district', None)
                if district:
                    cities_with_districts[city_key].add(district)
        
        # Формуємо список міст з районами в дужках
        city_list = []
        for record in magistral_records:
            if hasattr(record, 'city') and record.city:
                city_key = record.city.lower()
                districts = cities_with_districts.get(city_key, set())
                district = getattr(record, 'new_district', None) or getattr(record, 'old_district', None)
                
                if len(districts) > 1 and district:
                    city_display = f"{record.city} ({district})"
                else:
                    city_display = record.city
                
                if city_display not in city_list:
                    city_list.append(city_display)
        
        # Створюємо автокомпліт для міст
        city_list = sorted(list(set(city_list)))
        self.city_completer = QCompleter(city_list, self)
        self.city_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.city_completer.setFilterMode(Qt.MatchContains)
        self.city_input.setCompleter(self.city_completer)
    
    def on_city_changed(self):
        """Викликається при зміні міста"""
        city_text = self.city_input.text().strip()
        
        if not city_text:
            self.region_input.clear()
            self.street_input.clear()
            self.index_input.setText("00000")
            self.buildings_combo.hide()
            self.buildings_label.hide()
            self.current_city_records = []
            return
        
        # Видаляємо район з дужок якщо є
        city_clean = city_text.split('(')[0].strip()
        district_clean = None
        if '(' in city_text:
            district_clean = city_text.split('(')[1].strip(')')
        
        # Шукаємо всі записи для цього міста
        self.current_city_records = []
        for record in self.magistral_cache:
            if hasattr(record, 'city') and record.city and city_clean.lower() == record.city.lower():
                if district_clean:
                    new_dist = getattr(record, 'new_district', None)
                    old_dist = getattr(record, 'old_district', None)
                    district = new_dist or old_dist
                    
                    if district and district_clean.lower() in district.lower():
                        self.current_city_records.append(record)
                else:
                    self.current_city_records.append(record)
        
        if self.current_city_records:
            # Оновлюємо область
            first_record = self.current_city_records[0]
            region = getattr(first_record, 'region', None)
            self.region_input.setText(region if region else "")
            
            # Встановлюємо мінімальний індекс міста
            self.set_minimum_city_index()
            
            # Створюємо автокомпліт для вулиць цього міста
            unique_streets = set()
            for record in self.current_city_records:
                street = getattr(record, 'street', None)
                if street:
                    # Видаляємо префікс
                    street_clean = street
                    for prefix in ['вул. ', 'провул. ', 'пров. ', 'бульв. ', 'б-р ', 'просп. ', 'пр. ', 'пл. ']:
                        if street_clean.startswith(prefix):
                            street_clean = street_clean[len(prefix):]
                            break
                    unique_streets.add(street_clean)
            
            street_list = sorted(list(unique_streets))
            self.street_completer = QCompleter(street_list, self)
            self.street_completer.setCaseSensitivity(Qt.CaseInsensitive)
            self.street_completer.setFilterMode(Qt.MatchContains)
            self.street_input.setCompleter(self.street_completer)
        else:
            self.region_input.clear()
            self.index_input.setText("00000")
    
    def on_street_changed(self):
        """Викликається при зміні вулиці"""
        street_text = self.street_input.text().strip()
        
        if not street_text or not self.current_city_records:
            if self.current_city_records and not street_text:
                self.set_minimum_city_index()
            else:
                self.index_input.setText("00000")
            self.buildings_combo.hide()
            self.buildings_label.hide()
            return
        
        # Шукаємо записи з цією вулицею
        matching_records = []
        for record in self.current_city_records:
            street = getattr(record, 'street', None)
            if street:
                record_street = street
                for prefix in ['вул. ', 'провул. ', 'пров. ', 'бульв. ', 'б-р ', 'просп. ', 'пр. ', 'пл. ']:
                    if record_street.startswith(prefix):
                        record_street = record_street[len(prefix):]
                        break
                
                if street_text.lower() == record_street.lower():
                    matching_records.append(record)
        
        if not matching_records:
            self.set_minimum_city_index()
            self.buildings_combo.hide()
            self.buildings_label.hide()
            return
        
        # ВИКОРИСТОВУЄМО city_index
        unique_indexes = {}
        for record in matching_records:
            idx = getattr(record, 'city_index', None)
            
            if idx and str(idx) not in unique_indexes:
                unique_indexes[str(idx)] = record
        
        if not unique_indexes:
            self.set_minimum_city_index()
            self.buildings_combo.hide()
            self.buildings_label.hide()
            return
        
        if len(unique_indexes) == 1:
            idx = list(unique_indexes.keys())[0]
            self.index_input.setText(idx)
            self.buildings_combo.hide()
            self.buildings_label.hide()
        else:
            self.buildings_combo.blockSignals(True)
            self.buildings_combo.clear()
            self.buildings_combo.addItem("-- Оберіть будинки --", None)
            
            for idx, record in sorted(unique_indexes.items()):
                buildings = getattr(record, 'buildings', None)
                if not buildings:
                    buildings = "всі"
                self.buildings_combo.addItem(f"{buildings} → {idx}", idx)
            
            self.buildings_combo.blockSignals(False)
            self.buildings_combo.show()
            self.buildings_label.show()
            
            min_idx = min(unique_indexes.keys())
            self.index_input.setText(min_idx)
    
    def set_minimum_city_index(self):
        """Встановлює мінімальний індекс для міста"""
        if not self.current_city_records:
            self.index_input.setText("00000")
            return
        
        all_indexes = []
        for record in self.current_city_records:
            idx = getattr(record, 'city_index', None)
            if idx:
                all_indexes.append(str(idx))
        
        if all_indexes:
            min_index = min(all_indexes)
            self.index_input.setText(min_index)
        else:
            self.index_input.setText("00000")
    
    def on_building_selected(self):
        """Викликається при виборі будинків"""
        idx = self.buildings_combo.currentData()
        if idx:
            self.index_input.setText(idx)
    
    def populate_from_results(self, results):
        """Заповнює форму з результатів пошуку"""
        if not results:
            return
        
        best_result = results[0]
        
        # ЗАВЖДИ ОНОВЛЮЄМО З НАЙКРАЩОГО РЕЗУЛЬТАТУ
        self.region_input.setText(best_result.get('region', ''))
        self.city_input.setText(best_result.get('city', ''))
        
        # Видаляємо префікс з вулиці
        street = best_result.get('street', '')
        for prefix in ['вул. ', 'провул. ', 'пров. ', 'бульв. ', 'б-р ', 'просп. ', 'пр. ', 'пл. ']:
            if street.startswith(prefix):
                street = street[len(prefix):]
                break
        self.street_input.setText(street)
        
        # Індекс
        if best_result.get('index'):
            self.index_input.setText(best_result.get('index', ''))
        
        self.buildings_combo.hide()
        self.buildings_label.hide()
        
        # Фокус на індекс
        self.index_input.setFocus()
        self.index_input.selectAll()

    
    def on_apply_index(self):
        """Застосовує введений індекс"""
        index = self.index_input.text().strip()
        if index and len(index) == 5:
            self.index_double_clicked.emit(index)
    
    def clear_fields(self):
        """Очищує всі поля"""
        self.region_input.clear()
        self.city_input.clear()
        self.street_input.clear()
        self.index_input.setText("00000")
        self.buildings_combo.hide()
        self.buildings_label.hide()
        self.current_city_records = []
