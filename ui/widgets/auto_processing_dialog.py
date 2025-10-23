"""
Діалог налаштування автоматичної обробки
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSpinBox, QGroupBox
)
from PyQt5.QtCore import Qt


class AutoProcessingDialog(QDialog):
    """Діалог налаштування параметрів автоматичної обробки"""
    
    def __init__(self, current_row=0, total_rows=0, parent=None):
        super().__init__(parent)
        
        self.current_row = current_row
        self.total_rows = total_rows
        self.min_confidence = 90
        
        self.init_ui()
    
    def init_ui(self):
        """Ініціалізує UI"""
        self.setWindowTitle("Налаштування обробки")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        # Діапазон
        range_group = QGroupBox("Діапазон обробки")
        range_layout = QVBoxLayout()
        
        info = QLabel(f"Обробка розпочнеться з рядка {self.current_row + 1} з {self.total_rows}")
        info.setStyleSheet("font-weight: bold;")
        range_layout.addWidget(info)
        
        range_group.setLayout(range_layout)
        layout.addWidget(range_group)
        
        # Точність
        confidence_group = QGroupBox("Мінімальна точність")
        confidence_layout = QHBoxLayout()
        
        label = QLabel("Автоматично застосовувати при точності ≥")
        confidence_layout.addWidget(label)
        
        self.confidence_spin = QSpinBox()
        self.confidence_spin.setMinimum(50)
        self.confidence_spin.setMaximum(100)
        self.confidence_spin.setValue(90)
        self.confidence_spin.setSuffix(" %")
        confidence_layout.addWidget(self.confidence_spin)
        
        confidence_group.setLayout(confidence_layout)
        layout.addWidget(confidence_group)
        
        # Кнопки
        buttons = QHBoxLayout()
        
        cancel_btn = QPushButton("Скасувати")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)
        
        ok_btn = QPushButton("Розпочати")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px 20px;")
        buttons.addWidget(ok_btn)
        
        layout.addLayout(buttons)
        
        self.setLayout(layout)
    
    def get_min_confidence(self):
        """Повертає мінімальну точність"""
        return self.confidence_spin.value()
