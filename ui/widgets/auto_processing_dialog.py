from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSpinBox, QGroupBox
)
from PyQt5.QtCore import Qt
import config


class AutoProcessingDialog(QDialog):
    """Діалог налаштування параметрів автоматичної обробки"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.current_row = 0
        self.total_rows = 0
        
        # Отримуємо дані від parent
        if parent and hasattr(parent, 'current_row'):
            self.current_row = parent.current_row
        
        if parent and hasattr(parent, 'file_manager'):
            df = parent.file_manager.excel_handler.df
            if df is not None:
                self.total_rows = len(df)
        
        self.init_ui()
    
    def init_ui(self):
        """Ініціалізує UI"""
        self.setWindowTitle("Налаштування автоматичної обробки")
        self.setMinimumWidth(450)
        self.setModal(True)
        
        layout = QVBoxLayout()
        
        # ============ ДІАПАЗОН ОБРОБКИ ============
        range_group = QGroupBox("📋 Діапазон обробки")
        range_layout = QVBoxLayout()
        
        info = QLabel(f"Всього рядків: {self.total_rows}")
        info.setStyleSheet("font-weight: bold;")
        range_layout.addWidget(info)
        
        # Початковий рядок
        start_row_layout = QHBoxLayout()
        start_row_layout.addWidget(QLabel("Почати з рядка:"))
        
        self.start_row_spin = QSpinBox()
        self.start_row_spin.setMinimum(0)
        self.start_row_spin.setMaximum(self.total_rows - 1 if self.total_rows > 0 else 0)
        self.start_row_spin.setValue(self.current_row)  # ПОТОЧНИЙ РЯД!
        start_row_layout.addWidget(self.start_row_spin)
        
        current_row_label = QLabel(f"(зараз на рядку {self.current_row + 1})")
        current_row_label.setStyleSheet("color: gray; font-style: italic;")
        start_row_layout.addWidget(current_row_label)
        
        range_layout.addLayout(start_row_layout)
        range_group.setLayout(range_layout)
        layout.addWidget(range_group)
        
        # ============ МІНІМАЛЬНА ТОЧНІСТЬ ============
        confidence_group = QGroupBox("📊 Мінімальна точність для автопідстановки")
        confidence_layout = QHBoxLayout()
        
        label = QLabel("Автоматично застосовувати при точності ≥")
        confidence_layout.addWidget(label)
        
        self.confidence_spin = QSpinBox()
        self.confidence_spin.setMinimum(50)
        self.confidence_spin.setMaximum(100)
        self.confidence_spin.setValue(config.AUTO_PROCESSING_THRESHOLD)  # З config
        self.confidence_spin.setSuffix(" %")
        self.confidence_spin.setStyleSheet("min-width: 80px;")
        confidence_layout.addWidget(self.confidence_spin)
        
        info_label = QLabel("(50-100%, за замовчуванням 90%)")
        info_label.setStyleSheet("color: gray; font-style: italic;")
        confidence_layout.addWidget(info_label)
        
        confidence_group.setLayout(confidence_layout)
        layout.addWidget(confidence_group)
        
        # ============ ІНФОРМАЦІЯ ============
        info_group = QGroupBox("ℹ️ Інформація")
        info_layout = QVBoxLayout()
        
        info_text = QLabel(
            "🔍 Пошук буде обробляти записи, починаючи з обраного рядка.\n"
            "✅ Адреси з точністю ≥ вибраному значенню будуть автоматично підставлені.\n"
            "📋 Решта буде показана для ручного вибору."
        )
        info_text.setStyleSheet("color: #333; font-size: 11px; padding: 8px;")
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # ============ КНОПКИ ============
        buttons = QHBoxLayout()
        
        cancel_btn = QPushButton("Скасувати")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)
        
        ok_btn = QPushButton("Розпочати обробку")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; padding: 8px 20px; "
            "font-weight: bold; border-radius: 4px;"
        )
        buttons.addWidget(ok_btn)
        
        layout.addLayout(buttons)
        self.setLayout(layout)
    
    def get_start_row(self) -> int:
        """Повертає початковий рядок для обробки"""
        return self.start_row_spin.value()
    
    def get_min_confidence(self) -> int:
        """Повертає мінімальну точність для автопідстановки"""
        return self.confidence_spin.value()
