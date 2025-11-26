from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QComboBox, QCheckBox, QMessageBox
)
from PyQt5.QtCore import pyqtSignal
from ui.styles import AppStyles

class TopPanel(QFrame):
    """Верхня панель управління"""
    
    # Сигнали для комунікації з MainWindow
    load_file_clicked = pyqtSignal()
    save_file_clicked = pyqtSignal()
    save_as_clicked = pyqtSignal()
    configure_columns_clicked = pyqtSignal()
    parse_addresses_clicked = pyqtSignal()
    undo_clicked = pyqtSignal()
    redo_clicked = pyqtSignal()
    refresh_cache_clicked = pyqtSignal()
    filter_changed = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaximumHeight(60)
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(3)
        layout.setContentsMargins(5, 5, 5, 5)
        
        row1 = QHBoxLayout()
        
        # Файл
        file_label_icon = QLabel("📁")
        file_label_icon.setStyleSheet("font-size: 14px;")
        row1.addWidget(file_label_icon)
        
        self.file_label = QLabel("Не завантажено")
        self.file_label.setStyleSheet(AppStyles.file_label())
        row1.addWidget(self.file_label, 1)
        
        # Кнопки управління файлами
        load_btn = QPushButton("Відкрити файл")
        load_btn.setStyleSheet(AppStyles.button_default())
        load_btn.clicked.connect(self.load_file_clicked.emit)
        row1.addWidget(load_btn)
        
        self.column_mapping_btn = QPushButton("⚙ Налаштувати стовпці")
        self.column_mapping_btn.setEnabled(False)
        self.column_mapping_btn.setStyleSheet(AppStyles.button_default())
        self.column_mapping_btn.clicked.connect(self.configure_columns_clicked.emit)
        row1.addWidget(self.column_mapping_btn)
        
        self.save_btn = QPushButton("💾 Зберегти")
        self.save_btn.setEnabled(False)
        self.save_btn.setStyleSheet(AppStyles.button_success())
        self.save_btn.clicked.connect(self.save_file_clicked.emit)
        row1.addWidget(self.save_btn)
        
        self.save_as_btn = QPushButton("💾 Зберегти як...")
        self.save_as_btn.setEnabled(False)
        self.save_as_btn.setStyleSheet(AppStyles.button_default())
        self.save_as_btn.clicked.connect(self.save_as_clicked.emit)
        row1.addWidget(self.save_as_btn)
        
        # Кнопка парсингу адрес
        self.parse_addresses_btn = QPushButton("🔧 Розпарсити адреси")
        self.parse_addresses_btn.setEnabled(False)
        self.parse_addresses_btn.setStyleSheet(AppStyles.button_warning(font_size="11px"))
        self.parse_addresses_btn.clicked.connect(self.parse_addresses_clicked.emit)
        self.parse_addresses_btn.setToolTip("Парсить адреси у неправильному форматі (тільки видимі рядки)")
        row1.addWidget(self.parse_addresses_btn)
        
        # Undo/Redo
        self.undo_btn = QPushButton("⏪ Відмінити")
        self.undo_btn.setEnabled(False)
        self.undo_btn.setStyleSheet(AppStyles.button_default())
        self.undo_btn.clicked.connect(self.undo_clicked.emit)
        self.undo_btn.setToolTip("Відмінити останню дію (Ctrl+Z)")
        row1.addWidget(self.undo_btn)
        
        self.redo_btn = QPushButton("Повторити ⏩")
        self.redo_btn.setEnabled(False)
        self.redo_btn.setStyleSheet(AppStyles.button_default())
        self.redo_btn.clicked.connect(self.redo_clicked.emit)
        self.redo_btn.setToolTip("Повторити дію (Ctrl+Y)")
        row1.addWidget(self.redo_btn)
        
        # Фільтр
        filter_label = QLabel("Фільтр:")
        filter_label.setStyleSheet("font-size: 10px; margin-left: 15px;")
        row1.addWidget(filter_label)
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Всі", "Проставлено", "Непроставлено"])
        self.filter_combo.currentTextChanged.connect(self.filter_changed.emit)
        self.filter_combo.setStyleSheet(AppStyles.combo_box())
        row1.addWidget(self.filter_combo)
        
        # Оновити кеш
        refresh_cache_btn = QPushButton("🔄 Оновити кеш")
        refresh_cache_btn.setStyleSheet(AppStyles.button_warning(font_size="11px"))
        refresh_cache_btn.clicked.connect(self.refresh_cache_clicked.emit)
        refresh_cache_btn.setToolTip("Оновити кеш magistral.csv")
        row1.addWidget(refresh_cache_btn)
        
        # Чекбокс збереження старого індексу
        self.save_old_index_checkbox = QCheckBox("Зберігати старий індекс")
        self.save_old_index_checkbox.setChecked(False)
        self.save_old_index_checkbox.setStyleSheet("font-size: 10px;")
        row1.addWidget(self.save_old_index_checkbox)
        
        row1.addStretch()
        layout.addLayout(row1)
        
        self.setLayout(layout)

    def set_file_name(self, name: str):
        self.file_label.setText(name)

    def is_save_old_index_checked(self) -> bool:
        return self.save_old_index_checkbox.isChecked()
