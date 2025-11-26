from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QSpinBox, QTableWidget, QAbstractItemView, QHeaderView
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QColor
from ui.styles import AppStyles

class TablePanel(QWidget):
    """Панель з таблицею"""
    
    # Сигнали
    prev_row_clicked = pyqtSignal()
    next_row_clicked = pyqtSignal()
    search_clicked = pyqtSignal()
    auto_process_clicked = pyqtSignal()
    semi_auto_clicked = pyqtSignal()
    font_size_changed = pyqtSignal(int)
    row_selected = pyqtSignal()
    cell_edited = pyqtSignal(object) # QTableWidgetItem
    header_clicked = pyqtSignal(int) # column index
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(3)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Заголовок
        header = QHBoxLayout()
        
        label = QLabel("📋 База даних")
        label.setStyleSheet(AppStyles.panel_header())
        header.addWidget(label)
        
        # Навігація
        nav_btn_prev = QPushButton("◀ Попередній")
        nav_btn_prev.clicked.connect(self.prev_row_clicked.emit)
        nav_btn_prev.setStyleSheet(AppStyles.button_default(font_size="10px"))
        header.addWidget(nav_btn_prev)
        
        nav_btn_next = QPushButton("Наступний ▶")
        nav_btn_next.clicked.connect(self.next_row_clicked.emit)
        nav_btn_next.setStyleSheet(AppStyles.button_default(font_size="10px"))
        header.addWidget(nav_btn_next)
        
        # Розмір шрифту
        font_label = QLabel("Шрифт:")
        font_label.setStyleSheet("font-size: 10px; margin-left: 10px;")
        header.addWidget(font_label)
        
        self.table_font_spinbox = QSpinBox()
        self.table_font_spinbox.setMinimum(8)
        self.table_font_spinbox.setMaximum(16)
        self.table_font_spinbox.setValue(10)
        self.table_font_spinbox.setSuffix(" px")
        self.table_font_spinbox.setStyleSheet("font-size: 10px; padding: 2px;")
        self.table_font_spinbox.valueChanged.connect(self.font_size_changed.emit)
        header.addWidget(self.table_font_spinbox)
        
        header.addStretch()
        
        # Кнопки обробки
        self.search_btn = QPushButton("🔍 Знайти (Enter)")
        self.search_btn.setEnabled(False)
        self.search_btn.setStyleSheet(AppStyles.button_primary())
        self.search_btn.clicked.connect(self.search_clicked.emit)
        header.addWidget(self.search_btn)
        
        self.auto_process_btn = QPushButton("⚡ Автоматична")
        self.auto_process_btn.setEnabled(False)
        self.auto_process_btn.setStyleSheet(AppStyles.button_warning())
        self.auto_process_btn.clicked.connect(self.auto_process_clicked.emit)
        header.addWidget(self.auto_process_btn)
        
        self.semi_auto_btn = QPushButton("🔄 Напів-авто")
        self.semi_auto_btn.setEnabled(False)
        self.semi_auto_btn.setStyleSheet("background-color: #9C27B0; color: white; padding: 6px 12px; font-size: 11px;")
        self.semi_auto_btn.clicked.connect(self.semi_auto_clicked.emit)
        header.addWidget(self.semi_auto_btn)
        
        layout.addLayout(header)
        
        # Таблиця
        self.table = QTableWidget()
        self.table.setStyleSheet(AppStyles.table_main())
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.itemChanged.connect(self.cell_edited.emit)
        self.table.itemSelectionChanged.connect(self.row_selected.emit)
        
        # Налаштування сортування
        self.setup_table_sorting()
        
        layout.addWidget(self.table)
        
        # Панель оригінальних даних
        self.original_data_label = QLabel("Оберіть рядок для перегляду даних")
        self.original_data_label.setStyleSheet(AppStyles.original_data_label())
        self.original_data_label.setWordWrap(True)
        self.original_data_label.setMaximumHeight(60)
        layout.addWidget(self.original_data_label)
        
        self.setLayout(layout)
        
    def setup_table_sorting(self):
        """Налаштовує сортування при кліку на заголовки колонок"""
        # Отримуємо header таблиці
        header = self.table.horizontalHeader()
        
        # Дозволяємо клік по header
        header.setSectionsClickable(True)
        
        # Підключаємо обробник кліку
        header.sectionClicked.connect(self.header_clicked.emit)
        
        # Встановлюємо курсор руки при наведенні
        header.setCursor(Qt.PointingHandCursor)
        
        # Додаємо візуальну підказку
        header.setStyleSheet("""
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 8px;
                border: 1px solid #d0d0d0;
                font-weight: bold;
            }
            QHeaderView::section:hover {
                background-color: #e0e0e0;
            }
        """)

    def update_header_sort_indicator(self, column_index, order):
        """
        Оновлює візуальний індикатор сортування в заголовку
        """
        header = self.table.horizontalHeader()
        
        # Очищаємо всі індикатори
        for i in range(self.table.columnCount()):
            header_text = self.table.horizontalHeaderItem(i).text()
            # Видаляємо стрілки якщо є
            header_text = header_text.replace(' ▲', '').replace(' ▼', '')
            self.table.horizontalHeaderItem(i).setText(header_text)
        
        # Додаємо індикатор до поточної колонки
        header_text = self.table.horizontalHeaderItem(column_index).text()
        arrow = ' ▲' if order == 'asc' else ' ▼'
        self.table.horizontalHeaderItem(column_index).setText(header_text + arrow)
