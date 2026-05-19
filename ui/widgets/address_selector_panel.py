"""
Панель підбору адреси - ВИПРАВЛЕНА ВЕРСІЯ
ВИПРАВЛЕНО: кеш ukrposhta_v2.pkl.xz тепер створюється правильно
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFormLayout, QCompleter, QComboBox, 
    QFrame, QSpinBox, QListWidget
)
from PyQt5.QtCore import pyqtSignal, Qt
from utils.ukrposhta_index import UkrposhtaIndex


class AddressSelectorPanel(QWidget):
    """Панель для ручного підбору адреси"""
    
    index_double_clicked = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.magistral_cache = []
        self.street_completer = None
        self.city_completer = None
        self.current_city_records = []
        
        self.manual_font_size = 12
        self.cascade_font_size = 12
        
        self.ukr_index = UkrposhtaIndex()
        self.all_streets_cache = []
        
        self.init_ui()
    
    def init_ui(self):
        """Ініціалізує UI"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)
        
        # Контроль шрифтів
        font_controls = QHBoxLayout()
        
        manual_label = QLabel("Шрифт (ручне):")
        manual_label.setStyleSheet("font-size: 10px; font-weight: bold;")
        font_controls.addWidget(manual_label)
        
        self.manual_font_spinbox = QSpinBox()
        self.manual_font_spinbox.setMinimum(10)
        self.manual_font_spinbox.setMaximum(16)
        self.manual_font_spinbox.setValue(12)
        self.manual_font_spinbox.setSuffix(" px")
        self.manual_font_spinbox.valueChanged.connect(self.update_manual_font_size)
        font_controls.addWidget(self.manual_font_spinbox)
        
        font_controls.addSpacing(20)
        
        cascade_label = QLabel("Шрифт (пошук):")
        cascade_label.setStyleSheet("font-size: 10px; font-weight: bold;")
        font_controls.addWidget(cascade_label)
        
        self.cascade_font_spinbox = QSpinBox()
        self.cascade_font_spinbox.setMinimum(10)
        self.cascade_font_spinbox.setMaximum(16)
        self.cascade_font_spinbox.setValue(12)
        self.cascade_font_spinbox.setSuffix(" px")
        self.cascade_font_spinbox.valueChanged.connect(self.update_cascade_font_size)
        font_controls.addWidget(self.cascade_font_spinbox)
        
        font_controls.addStretch()
        main_layout.addLayout(font_controls)
        
        # Дві панелі
        panels_layout = QHBoxLayout()
        
        left_panel = self.create_manual_input_panel()
        panels_layout.addWidget(left_panel, 1)
        
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setStyleSheet("background-color: #ccc;")
        panels_layout.addWidget(line)
        
        right_panel = self.create_cascade_panel()
        panels_layout.addWidget(right_panel, 1)
        
        main_layout.addLayout(panels_layout)
        self.setLayout(main_layout)
    
    def create_manual_input_panel(self):
        """Ліва панель - ручне введення"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        header = QLabel("🔍 Ручне введення")
        header.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(header)
        
        form = QFormLayout()
        
        self.region_input = QLineEdit()
        self.region_input.setPlaceholderText("Автоматично")
        self.region_input.setReadOnly(True)
        self.region_input.setStyleSheet("background-color: #f0f0f0;")
        form.addRow("Область:", self.region_input)
        
        self.city_input = QLineEdit()
        self.city_input.setPlaceholderText("Введіть місто")
        self.city_input.textChanged.connect(self.on_city_changed)
        self.city_input.returnPressed.connect(self.on_apply_index)
        form.addRow("Місто:", self.city_input)
        
        self.street_input = QLineEdit()
        self.street_input.setPlaceholderText("Введіть вулицю")
        self.street_input.textChanged.connect(self.on_street_changed)
        self.street_input.returnPressed.connect(self.on_apply_index)
        form.addRow("Вулиця:", self.street_input)
        
        self.buildings_combo = QComboBox()
        self.buildings_combo.currentIndexChanged.connect(self.on_building_selected)
        self.buildings_combo.setMaxVisibleItems(10)
        self.buildings_combo.view().setWordWrap(True)
        self.buildings_combo.view().setTextElideMode(Qt.ElideNone)
        self.buildings_combo.view().setMinimumWidth(250)
        self.buildings_label = QLabel("Будинки:")
        form.addRow(self.buildings_label, self.buildings_combo)
        self.buildings_combo.hide()
        self.buildings_label.hide()
        
        self.index_input = QLineEdit()
        self.index_input.setPlaceholderText("00000")
        self.index_input.setMaxLength(5)
        self.index_input.setAlignment(Qt.AlignCenter)
        self.index_input.returnPressed.connect(self.on_apply_index)
        self.index_input.setStyleSheet(
            "padding: 6px; font-size: 16px; font-weight: bold; "
            "border: 2px solid #2196F3; border-radius: 5px;"
        )
        form.addRow("→ Індекс:", self.index_input)
        
        layout.addLayout(form)
        
        apply_btn = QPushButton("✓ Застосувати (Enter)")
        apply_btn.clicked.connect(self.on_apply_index)
        apply_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; padding: 8px; font-weight: bold;"
        )
        layout.addWidget(apply_btn)
        
        layout.addStretch()
        panel.setLayout(layout)
        return panel
    
    def create_cascade_panel(self):
        """Права панель - пошук Укрпошти з POPUP"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        header = QLabel("📮 Пошук індексу")
        header.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(header)
        
        form = QVBoxLayout()
        
        # === МІСТО ===
        city_label = QLabel("Населений пункт:")
        form.addWidget(city_label)
        
        self.cascade_city_input = QLineEdit()
        self.cascade_city_input.setPlaceholderText("Введіть населений пункт (мін. 3 символи)")
        self.cascade_city_input.textChanged.connect(self.on_cascade_city_typed)
        form.addWidget(self.cascade_city_input)
        
        # POPUP LIST
        self.cascade_city_list = QListWidget(self)
        self.cascade_city_list.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.cascade_city_list.setAttribute(Qt.WA_ShowWithoutActivating)
        self.cascade_city_list.setMinimumHeight(200)
        self.cascade_city_list.setMaximumHeight(300)
        self.cascade_city_list.setWordWrap(True)
        self.cascade_city_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.cascade_city_list.setStyleSheet("""
            QListWidget {
                border: 2px solid #2196F3;
                border-radius: 3px;
                background-color: white;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:hover {
                background-color: #e3f2fd;
            }
            QListWidget::item:selected {
                background-color: #2196F3;
                color: white;
            }
        """)
        self.cascade_city_list.hide()
        self.cascade_city_list.itemClicked.connect(self.on_cascade_city_clicked)
        
        # === ВУЛИЦЯ ===
        street_label = QLabel("Вулиця:")
        form.addWidget(street_label)
        
        self.cascade_street_input = QLineEdit()
        self.cascade_street_input.setPlaceholderText("Введіть вулицю")
        self.cascade_street_input.textChanged.connect(self.on_cascade_street_typed)
        self.cascade_street_input.setEnabled(False)
        form.addWidget(self.cascade_street_input)
        
        # POPUP LIST
        self.cascade_street_list = QListWidget(self)
        self.cascade_street_list.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.cascade_street_list.setAttribute(Qt.WA_ShowWithoutActivating)
        self.cascade_street_list.setMinimumHeight(200)
        self.cascade_street_list.setMaximumHeight(300)
        self.cascade_street_list.setWordWrap(True)
        self.cascade_street_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.cascade_street_list.setStyleSheet("""
            QListWidget {
                border: 2px solid #FF9800;
                border-radius: 3px;
                background-color: white;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:hover {
                background-color: #fff3e0;
            }
            QListWidget::item:selected {
                background-color: #FF9800;
                color: white;
            }
        """)
        self.cascade_street_list.hide()
        self.cascade_street_list.itemClicked.connect(self.on_cascade_street_clicked)
        
        # === БУДИНОК ===
        building_label = QLabel("Будинок:")
        form.addWidget(building_label)
        
        self.cascade_building_combo = QComboBox()
        self.cascade_building_combo.currentTextChanged.connect(self.on_cascade_building_changed)
        self.cascade_building_combo.setMaxVisibleItems(10)
        self.cascade_building_combo.view().setWordWrap(True)
        self.cascade_building_combo.view().setTextElideMode(Qt.ElideNone)
        self.cascade_building_combo.view().setMinimumWidth(250)
        self.cascade_building_combo.hide()
        form.addWidget(self.cascade_building_combo)
        
        # === ІНДЕКС ===
        index_label = QLabel("→ Індекс:")
        form.addWidget(index_label)
        
        self.cascade_index_input = QLineEdit()
        self.cascade_index_input.setPlaceholderText("00000")
        self.cascade_index_input.setMaxLength(5)
        self.cascade_index_input.setAlignment(Qt.AlignCenter)
        self.cascade_index_input.setReadOnly(True)
        self.cascade_index_input.setStyleSheet(
            "padding: 10px; font-size: 20px; font-weight: bold; "
            "border: 2px solid #FF9800; border-radius: 5px; background-color: #FFF3E0;"
        )
        form.addWidget(self.cascade_index_input)
        
        layout.addLayout(form)
        
        apply_btn = QPushButton("✓ Застосувати індекс")
        apply_btn.clicked.connect(self.on_cascade_apply_index)
        apply_btn.setStyleSheet(
            "background-color: #FF9800; color: white; padding: 10px; font-weight: bold;"
        )
        layout.addWidget(apply_btn)
        
        layout.addStretch()
        panel.setLayout(layout)
        return panel
    
    def set_magistral_cache(self, magistral_records):
        """Встановлює кеш magistral - ОПТИМІЗОВАНО"""
        self.magistral_cache = magistral_records
        
        print("🔄 Ініціалізація індексу Укрпошти...")
        
        # ВАЖЛИВО: Встановлюємо ПЕРЕД завантаженням щоб не копіювати
        self.ukr_index.magistral_cache = magistral_records
        
        cache_loaded = self.ukr_index.load()
        
        if cache_loaded:
            print("✅ UkrposhtaIndex завантажено з кешу")
        else:
            # Якщо кешу немає - будуємо (це довго ~2 хв)
            print("⏳ Побудова індексу Укрпошти (це займе ~2 хв)...")
            self.ukr_index.build(magistral_records)
            print("✅ Індекс побудовано і збережено")
        
        # Для лівої панелі - ЦЕЙ КОД МАЄ ВИКОНУВАТИСЯ ЗАВЖДИ!
        cities_with_districts = {}
        for record in magistral_records:
            if hasattr(record, 'city') and record.city:
                city_key = record.city.lower()
                if city_key not in cities_with_districts:
                    cities_with_districts[city_key] = set()
                
                district = getattr(record, 'new_district', None) or getattr(record, 'old_district', None)
                if district:
                    cities_with_districts[city_key].add(district)
        
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
        
        city_list = sorted(list(set(city_list)))
        self.city_completer = QCompleter(city_list, self)
        self.city_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.city_completer.setFilterMode(Qt.MatchContains)
        self.city_input.setCompleter(self.city_completer)

    def attach_magistral_cache(self, magistral_records):
        """Attach loaded magistral data without rebuilding heavy UI completers."""
        self.magistral_cache = magistral_records
        self.ukr_index.magistral_cache = magistral_records

        # The compact Ukrposhta index is enough for the cascade city/street search.
        # Avoid rebuilding completer lists on startup; that work freezes the UI.
        self.ukr_index.load()
    
    # ==================== КАСКАДНА ФОРМА (УКРПОШТА) ====================
    
    def on_cascade_city_typed(self, text):
        """Введення міста з POPUP"""
        self.cascade_street_input.clear()
        self.cascade_street_input.setEnabled(False)
        self.cascade_street_list.hide()
        self.cascade_building_combo.clear()
        self.cascade_building_combo.hide()
        self.cascade_index_input.clear()
        
        if len(text) < 3:
            self.cascade_city_list.clear()
            self.cascade_city_list.hide()
            return
        
        matching = self.ukr_index.search_cities(text)
        
        self.cascade_city_list.clear()
        if matching:
            for city in matching:
                self.cascade_city_list.addItem(city)
            
            pos = self.cascade_city_input.mapToGlobal(self.cascade_city_input.rect().bottomLeft())
            self.cascade_city_list.move(pos)
            self.cascade_city_list.setFixedWidth(self.cascade_city_input.width())
            self.cascade_city_list.show()
            self.cascade_city_list.raise_()
        else:
            self.cascade_city_list.hide()
    
    def on_cascade_city_clicked(self, item):
        """Клік по місту"""
        city_full = item.text()
        
        self.cascade_city_input.setText(city_full)
        self.cascade_city_list.hide()
        
        streets = self.ukr_index.get_streets(city_full)
        self.all_streets_cache = streets
        
        self.cascade_street_input.setEnabled(True)
        self.cascade_street_input.clear()
        
        self.cascade_building_combo.clear()
        self.cascade_building_combo.hide()
        self.cascade_index_input.clear()
        
        self.cascade_street_input.setFocus()
        
        self.cascade_street_list.clear()
        for street in streets[:10]:
            self.cascade_street_list.addItem(street)
        
        if streets:
            pos = self.cascade_street_input.mapToGlobal(self.cascade_street_input.rect().bottomLeft())
            self.cascade_street_list.move(pos)
            self.cascade_street_list.setFixedWidth(self.cascade_street_input.width())
            self.cascade_street_list.show()
            self.cascade_street_list.raise_()
    
    def on_cascade_street_typed(self, text):
        """Введення вулиці з POPUP"""
        if not hasattr(self, 'all_streets_cache') or not self.all_streets_cache:
            return
        
        if not text:
            filtered = self.all_streets_cache[:10]
        else:
            text_lower = text.lower()
            filtered = [s for s in self.all_streets_cache if text_lower in s.lower()][:10]
        
        self.cascade_street_list.clear()
        if filtered:
            for street in filtered:
                self.cascade_street_list.addItem(street)
            
            pos = self.cascade_street_input.mapToGlobal(self.cascade_street_input.rect().bottomLeft())
            self.cascade_street_list.move(pos)
            self.cascade_street_list.setFixedWidth(self.cascade_street_input.width())
            self.cascade_street_list.show()
            self.cascade_street_list.raise_()
        else:
            self.cascade_street_list.hide()
    
    def on_cascade_street_clicked(self, item):
        """Клік по вулиці"""
        street_text = item.text()
        
        self.cascade_street_input.setText(street_text)
        self.cascade_street_list.hide()
        
        city_full = self.cascade_city_input.text()
        
        buildings_map = self.ukr_index.get_buildings(city_full, street_text)
                
        if len(buildings_map) == 0:
            self.cascade_index_input.clear()
            self.cascade_building_combo.hide()
        elif len(buildings_map) == 1:
            idx = list(buildings_map.keys())[0]
            self.cascade_index_input.setText(idx)
            self.cascade_building_combo.hide()
            print(f"✅ Встановлено індекс: {idx}")
        else:
            self.cascade_building_combo.clear()
            self.cascade_building_combo.addItem("-- Оберіть будинок --")
            
            for idx, buildings in sorted(buildings_map.items()):
                if buildings:
                    self.cascade_building_combo.addItem(f"{buildings} → {idx}")
                else:
                    self.cascade_building_combo.addItem(f"Всі → {idx}")
            
            self.cascade_building_combo.show()
            self.cascade_building_combo.setFocus()
            
            first_idx = min(buildings_map.keys())
            self.cascade_index_input.setText(first_idx)
            print(f"📋 Показано випадашку з {len(buildings_map)} варіантами")

    def on_cascade_building_changed(self, text):
        """Будинок обраний"""
        if not text or text == "-- Оберіть будинок --":
            self.cascade_index_input.clear()
            return
        
        if '→' in text:
            idx = text.split('→')[-1].strip()
            self.cascade_index_input.setText(idx)
    
    def on_cascade_apply_index(self):
        """Застосовує індекс"""
        index = self.cascade_index_input.text().strip()
        if index and len(index) == 5:
            self.index_double_clicked.emit(index)
            
            self.cascade_city_input.clear()
            self.cascade_street_input.clear()
            self.cascade_street_input.setEnabled(False)
            self.cascade_building_combo.clear()
            self.cascade_building_combo.hide()
            self.cascade_index_input.clear()
            
            if hasattr(self, 'cascade_city_list'):
                self.cascade_city_list.hide()
            if hasattr(self, 'cascade_street_list'):
                self.cascade_street_list.hide()

    # ==================== РУЧНА ФОРМА ====================
    
    def on_city_changed(self):
        """Зміна міста"""
        city_text = self.city_input.text().strip()
        
        if not city_text:
            self.region_input.clear()
            self.street_input.clear()
            self.index_input.setText("00000")
            self.buildings_combo.hide()
            self.buildings_label.hide()
            self.current_city_records = []
            return
        
        # ✅ ЯКЩО КЕШ ЩЕ НЕ ЗАВАНТАЖЕНИЙ - НЕ ОЧИЩУЄМО ПОЛЯ
        if not self.magistral_cache:
            return
        
        city_clean = city_text.split('(')[0].strip()
        district_clean = None
        if '(' in city_text:
            district_clean = city_text.split('(')[1].strip(')')
        
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
            first_record = self.current_city_records[0]
            region = getattr(first_record, 'region', None)
            self.region_input.setText(region if region else "")
            
            self.set_minimum_city_index()
            
            unique_streets = set()
            for record in self.current_city_records:
                street = getattr(record, 'street', None)
                if street:
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
        """Зміна вулиці"""
        street_text = self.street_input.text().strip()
        
        # ✅ ЯКЩО КЕШ ЩЕ НЕ ЗАВАНТАЖЕНИЙ - НЕ ОЧИЩУЄМО ПОЛЯ
        if not self.magistral_cache:
            return
        
        if not street_text or not self.current_city_records:
            if self.current_city_records and not street_text:
                self.set_minimum_city_index()
            else:
                self.index_input.setText("00000")
            self.buildings_combo.hide()
            self.buildings_label.hide()
            return
        
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
        """Мінімальний індекс міста"""
        if not self.current_city_records:
            self.index_input.setText("00000")
            return
        
        all_indexes = []
        for record in self.current_city_records:
            idx = getattr(record, 'city_index', None)
            if idx:
                all_indexes.append(str(idx))
        
        if all_indexes:
            self.index_input.setText(min(all_indexes))
        else:
            self.index_input.setText("00000")
    
    def on_building_selected(self):
        """Будинок обраний"""
        idx = self.buildings_combo.currentData()
        if idx:
            self.index_input.setText(idx)
    
    def populate_from_results(self, results):
        """Заповнює форму з результатів пошуку"""
        if not results:
            return
        
        best_result = results[0]
        
        self.region_input.setText(best_result.get('region', ''))
        self.city_input.setText(best_result.get('city', ''))
        
        street = best_result.get('street', '')
        for prefix in ['вул. ', 'провул. ', 'пров. ', 'бульв. ', 'б-р ', 'просп. ', 'пр. ', 'пл. ']:
            if street.startswith(prefix):
                street = street[len(prefix):]
                break
        
        self.street_input.setText(street)
        
        if best_result.get('index'):
            self.index_input.setText(best_result.get('index', ''))
        
        self.buildings_combo.hide()
        self.buildings_label.hide()
        
        self.index_input.setFocus()
        self.index_input.selectAll()
    
    def on_apply_index(self):
        """Застосовує індекс"""
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
    
    # ==================== ШРИФТИ ====================
    
    def update_manual_font_size(self, size):
        """Оновлює шрифт ручної форми"""
        self.manual_font_size = size
        self.city_input.setStyleSheet(f"padding: 5px; font-size: {size}px;")
        self.street_input.setStyleSheet(f"padding: 5px; font-size: {size}px;")
        self.buildings_combo.setStyleSheet(f"padding: 5px; font-size: {size}px;")
        self.index_input.setStyleSheet(
            f"padding: 6px; font-size: {size + 4}px; font-weight: bold; "
            "border: 2px solid #2196F3; border-radius: 5px;"
        )
    
    def update_cascade_font_size(self, size):
        """Оновлює шрифт каскадної форми"""
        self.cascade_font_size = size
        self.cascade_city_input.setStyleSheet(f"padding: 6px; font-size: {size}px;")
        self.cascade_street_input.setStyleSheet(f"padding: 6px; font-size: {size}px;")
        self.cascade_building_combo.setStyleSheet(f"padding: 6px; font-size: {size}px;")
        self.cascade_index_input.setStyleSheet(
            f"padding: 10px; font-size: {size + 8}px; font-weight: bold; "
            "border: 2px solid #FF9800; border-radius: 5px; background-color: #FFF3E0;"
        )
