"""
Головне вікно програми - ПОВНІСТЮ МІГРОВАНА ВЕРСІЯ
Використовує менеджери для всієї бізнес-логіки
"""
import os
import pandas as pd
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem, QMessageBox, 
    QProgressBar, QHeaderView, QAbstractItemView, QFrame, 
    QComboBox, QShortcut, QApplication, QCheckBox, QSpinBox
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QKeySequence
# Менеджери
from ui.managers import FileManager, SearchManager, ProcessingManager, UIStateManager
from ui.styles import AppStyles

# UI компоненти
from ui.widgets.column_mapping_dialog import ColumnMappingDialog
from ui.widgets.address_selector_panel import AddressSelectorPanel
from ui.widgets.results_panel import ResultsPanel
from ui.widgets.auto_processing_dialog import AutoProcessingDialog

# Утиліти
from utils.undo_manager import UndoManager
from utils.settings_manager import SettingsManager
from utils.logger import Logger
from utils.address_parser import parse_full_address_text, is_full_address_in_text

import config

class CacheLoaderThread(QThread):
    """Фоновий потік для завантаження magistral cache"""
    finished = pyqtSignal(list)
    progress = pyqtSignal(str)
    
    def __init__(self, search_manager):
        super().__init__()
        self.search_manager = search_manager
    
    def run(self):
        """Виконується у фоновому потоці"""
        try:
            self.progress.emit("⏳ Завантаження довідника у фоні...")
            records = self.search_manager.get_magistral_records()
            self.finished.emit(records)
        except Exception as e:
            self.progress.emit(f"❌ Помилка: {e}")
            self.finished.emit([])

class MainWindow(QMainWindow):
    """
    Головне вікно програми - координатор компонентів
    
    Відповідальності:
    - Створення та розміщення UI компонентів
    - Координація між менеджерами та UI
    - Обробка подій користувача
    - Збереження/відновлення стану вікна
    """
    
    def __init__(self):
        super().__init__()
        
        # Ініціалізація менеджерів
        self.file_manager = FileManager()
        self.search_manager = SearchManager()
        self.undo_manager = UndoManager()
        self.processing_manager = ProcessingManager(
            self.file_manager.excel_handler,
            self.undo_manager
        )
        self.ui_state = UIStateManager()
        self.logger = Logger()
        self.sort_state = {}
        self.current_sort_column = None
        self.current_sort_order = None
        
        
        # Поточний стан
        self.current_row = -1
        self.search_results = []
        
        # Віджети (ініціалізуються в init_ui)
        self.table = None
        self.progress_bar = None
        self.status_bar = None
        self.results_panel = None
        self.address_panel = None
        self.stop_btn = None
        
        # Ініціалізація UI
        self._init_ui()
        self._connect_signals()
        self._setup_callbacks()
        self._setup_shortcuts()
        
        # Кеш вже завантажений в main.py
        self._cache_loaded = True
        
        self.logger.info("GUI ініціалізовано")
    
    # ==================== ІНІЦІАЛІЗАЦІЯ UI ====================
    
    def setup_table_sorting(self):
        """Налаштовує сортування при кліку на заголовки колонок"""
        from PyQt5.QtCore import Qt
        
        # Отримуємо header таблиці
        header = self.table.horizontalHeader()
        
        # Дозволяємо клік по header
        header.setSectionsClickable(True)
        
        # Підключаємо обробник кліку
        header.sectionClicked.connect(self.on_header_clicked)
        
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
       
    def _init_ui(self):
        """Ініціалізація інтерфейсу"""
        self.setWindowTitle(config.WINDOW_TITLE)
        
        # Відновлюємо геометрію
        geometry = SettingsManager.get_window_geometry()
        if geometry:
            self.setGeometry(geometry['x'], geometry['y'], geometry['width'], geometry['height'])
        else:
            self.setGeometry(100, 50, config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        
        # Центральний віджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        main_layout.setSpacing(3)
        main_layout.setContentsMargins(5, 5, 5, 5)
        central_widget.setLayout(main_layout)
        
        # Панелі
        top_panel = self._create_top_panel()
        main_layout.addWidget(top_panel)
        
        main_splitter = QSplitter(Qt.Horizontal)
        
        left_panel = self._create_table_panel()
        main_splitter.addWidget(left_panel)
        
        right_panel = self._create_right_panel()
        main_splitter.addWidget(right_panel)
        
        main_splitter.setSizes([1100, 600])
        
        # Вертикальний splitter для можливості зміни висоти статус бару
        vertical_splitter = QSplitter(Qt.Vertical)
        vertical_splitter.addWidget(main_splitter)
        
        # Контейнер для статус бару та прогрес бару
        status_container = QWidget()
        status_layout = QVBoxLayout()
        status_layout.setSpacing(2)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_container.setLayout(status_layout)
        
        # Статус бар з мінімальною висотою
        self.status_bar = QLabel("Готово до роботи")
        self.status_bar.setStyleSheet(AppStyles.status_bar())
        self.status_bar.setMinimumHeight(25)
        self.status_bar.setMaximumHeight(60)
        status_layout.addWidget(self.status_bar)
        
        # Прогрес бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet(AppStyles.progress_bar())
        self.progress_bar.setMaximumHeight(20)
        status_layout.addWidget(self.progress_bar)
        
        vertical_splitter.addWidget(status_container)
        
        # Встановлюємо початкові розміри: основна область велика, статус - маленький
        vertical_splitter.setSizes([700, 30])
        vertical_splitter.setStretchFactor(0, 1) 
        vertical_splitter.setStretchFactor(1, 0)  
        
        main_layout.addWidget(vertical_splitter)
    
    def _create_top_panel(self):
        """Верхня панель управління"""
        panel = QFrame()
        panel.setMaximumHeight(60)
        layout = QVBoxLayout()
        layout.setSpacing(3)
        layout.setContentsMargins(5, 5, 5, 5)
        
        row1 = QHBoxLayout()
        
        # Файл
        file_label = QLabel("📁")
        file_label.setStyleSheet("font-size: 14px;")
        row1.addWidget(file_label)
        
        self.file_label = QLabel("Не завантажено")
        self.file_label.setStyleSheet(AppStyles.file_label())
        row1.addWidget(self.file_label, 1)
        
        # Кнопки управління файлами
        load_btn = QPushButton("Відкрити файл")
        load_btn.setStyleSheet(AppStyles.button_default())
        load_btn.clicked.connect(self.load_file)
        row1.addWidget(load_btn)
        
        self.column_mapping_btn = QPushButton("⚙ Налаштувати стовпці")
        self.column_mapping_btn.setEnabled(False)
        self.column_mapping_btn.setStyleSheet(AppStyles.button_default())
        self.column_mapping_btn.clicked.connect(self.configure_columns)
        row1.addWidget(self.column_mapping_btn)
        
        self.save_btn = QPushButton("💾 Зберегти")
        self.save_btn.setEnabled(False)
        self.save_btn.setStyleSheet(AppStyles.button_success())
        self.save_btn.clicked.connect(self.save_file)
        row1.addWidget(self.save_btn)
        
        self.save_as_btn = QPushButton("💾 Зберегти як...")
        self.save_as_btn.setEnabled(False)
        self.save_as_btn.setStyleSheet(AppStyles.button_default())
        self.save_as_btn.clicked.connect(self.save_file_as)
        row1.addWidget(self.save_as_btn)
        
        # Кнопка парсингу адрес
        self.parse_addresses_btn = QPushButton("🔧 Розпарсити адреси")
        self.parse_addresses_btn.setEnabled(False)
        self.parse_addresses_btn.setStyleSheet(AppStyles.button_warning(font_size="11px"))
        self.parse_addresses_btn.clicked.connect(self.parse_visible_addresses)
        self.parse_addresses_btn.setToolTip("Парсить адреси у неправильному форматі (тільки видимі рядки)")
        row1.addWidget(self.parse_addresses_btn)
        
        # Undo/Redo
        self.undo_btn = QPushButton("⏪ Відмінити")
        self.undo_btn.setEnabled(False)
        self.undo_btn.setStyleSheet(AppStyles.button_default())
        self.undo_btn.clicked.connect(self.undo_action)
        self.undo_btn.setToolTip("Відмінити останню дію (Ctrl+Z)")
        row1.addWidget(self.undo_btn)
        
        self.redo_btn = QPushButton("Повторити ⏩")
        self.redo_btn.setEnabled(False)
        self.redo_btn.setStyleSheet(AppStyles.button_default())
        self.redo_btn.clicked.connect(self.redo_action)
        self.redo_btn.setToolTip("Повторити дію (Ctrl+Y)")
        row1.addWidget(self.redo_btn)
        
        # Фільтр
        filter_label = QLabel("Фільтр:")
        filter_label.setStyleSheet("font-size: 10px; margin-left: 15px;")
        row1.addWidget(filter_label)
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Всі", "Проставлено", "Непроставлено"])
        self.filter_combo.currentTextChanged.connect(self.apply_filter)
        self.filter_combo.setStyleSheet(AppStyles.combo_box())
        row1.addWidget(self.filter_combo)
        
        # Оновити кеш
        refresh_cache_btn = QPushButton("🔄 Оновити кеш")
        refresh_cache_btn.setStyleSheet(AppStyles.button_warning(font_size="11px"))
        refresh_cache_btn.clicked.connect(self.refresh_cache)
        refresh_cache_btn.setToolTip("Оновити кеш magistral.csv")
        row1.addWidget(refresh_cache_btn)
        
        # Чекбокс збереження старого індексу
        self.save_old_index_checkbox = QCheckBox("Зберігати старий індекс")
        self.save_old_index_checkbox.setChecked(False)
        self.save_old_index_checkbox.setStyleSheet("font-size: 10px;")
        row1.addWidget(self.save_old_index_checkbox)
        
        row1.addStretch()
        layout.addLayout(row1)
        
        panel.setLayout(layout)
        return panel
    
    def _create_table_panel(self):
        """Панель з таблицею"""
        panel = QWidget()
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
        nav_btn_prev.clicked.connect(self.go_to_previous_row)
        nav_btn_prev.setStyleSheet(AppStyles.button_default(font_size="10px"))
        header.addWidget(nav_btn_prev)
        
        nav_btn_next = QPushButton("Наступний ▶")
        nav_btn_next.clicked.connect(self.go_to_next_row)
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
        self.table_font_spinbox.valueChanged.connect(self.update_table_font_size)
        header.addWidget(self.table_font_spinbox)
        
        header.addStretch()
        
        # Кнопки обробки
        self.search_btn = QPushButton("🔍 Знайти (Enter)")
        self.search_btn.setEnabled(False)
        self.search_btn.setStyleSheet(AppStyles.button_primary())
        self.search_btn.clicked.connect(self.search_address)
        header.addWidget(self.search_btn)
        
        self.auto_process_btn = QPushButton("⚡ Автоматична")
        self.auto_process_btn.setEnabled(False)
        self.auto_process_btn.setStyleSheet(AppStyles.button_warning())
        self.auto_process_btn.clicked.connect(self.start_auto_processing)
        header.addWidget(self.auto_process_btn)
        
        self.semi_auto_btn = QPushButton("🔄 Напів-авто")
        self.semi_auto_btn.setEnabled(False)
        self.semi_auto_btn.setStyleSheet("background-color: #9C27B0; color: white; padding: 6px 12px; font-size: 11px;")
        self.semi_auto_btn.clicked.connect(self.start_semi_auto_processing)
        header.addWidget(self.semi_auto_btn)
        
        layout.addLayout(header)
        
        # Таблиця
        self.table = QTableWidget()
        self.table.setStyleSheet(AppStyles.table_main())
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.itemChanged.connect(self.on_cell_edited)
        self.table.itemSelectionChanged.connect(self.on_row_selected)
        self.setup_table_sorting()
        layout.addWidget(self.table)
        
        # Панель оригінальних даних
        self.original_data_label = QLabel("Оберіть рядок для перегляду даних")
        self.original_data_label.setStyleSheet(AppStyles.original_data_label())
        self.original_data_label.setWordWrap(True)
        self.original_data_label.setMaximumHeight(60)
        layout.addWidget(self.original_data_label)
        
        panel.setLayout(layout)
        return panel
    
    def _create_right_panel(self):
        """Права панель"""
        panel = QSplitter(Qt.Vertical)
        
        # Панель підбору адреси
        self.address_panel = AddressSelectorPanel()
        self.address_panel.index_double_clicked.connect(self.apply_index)
        self.address_panel.setMaximumHeight(320)
        
        # Панель результатів
        self.results_panel = ResultsPanel()
        self.results_panel.index_selected.connect(self.apply_index)
        self.results_panel.search_requested.connect(self.search_address)
        
        panel.addWidget(self.address_panel)
        panel.addWidget(self.results_panel)
        
        # Відновлюємо розміри
        sizes = SettingsManager.get_splitter_sizes('right_panel')
        if sizes:
            panel.setSizes(sizes)
        else:
            panel.setSizes([220, 480])
        
        return panel
        
    def on_header_clicked(self, logical_index):
        """
        Обробник кліку по заголовку колонки
        """
        from utils.logger import Logger
        
        # Перевіряємо чи є дані
        if self.df is None or self.df.empty:
            return
        
        # Визначаємо порядок сортування
        if self.current_sort_column == logical_index:
            # Перемикаємо: asc -> desc -> asc
            if self.current_sort_order == 'asc':
                self.current_sort_order = 'desc'
            else:
                self.current_sort_order = 'asc'
        else:
            # Нова колонка - починаємо з asc
            self.current_sort_column = logical_index
            self.current_sort_order = 'asc'
        
        # Отримуємо назву колонки
        column_name = self.df.columns[logical_index]
        
        # Виконуємо сортування
        self.sort_dataframe(column_name, self.current_sort_order)
        
        # Оновлюємо відображення таблиці
        self.load_data_to_table()
        
        # Оновлюємо візуальну підказку
        self.update_header_sort_indicator(logical_index, self.current_sort_order)
        
        # Логуємо
        logger = Logger()
        logger.info(f"Сортування: '{column_name}' ({self.current_sort_order})")
        
    def sort_dataframe(self, column_name, order='asc'):
        """
        Сортує DataFrame по заданій колонці
        """
        from utils.logger import Logger
        
        if self.df is None or column_name not in self.df.columns:
            return
        
        # Визначаємо напрямок
        ascending = (order == 'asc')
        
        try:
            # Заповнюємо NaN пустими рядками
            self.df[column_name] = self.df[column_name].fillna('')
            
            # Сортуємо
            self.df = self.df.sort_values(
                by=column_name,
                ascending=ascending,
                na_position='last'
            )
            
            # Скидаємо індекс
            self.df = self.df.reset_index(drop=True)
            
        except Exception as e:
            logger = Logger()
            logger.error(f"Помилка сортування: {e}")
            
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
    
    # ==================== СИГНАЛИ ТА КОЛБЕКИ ====================
    
    def _connect_signals(self):
        """Підключає сигнали від менеджерів"""
        # Сигнали від UIStateManager
        self.ui_state.file_loaded.connect(self._on_file_loaded_signal)
        self.ui_state.file_saved.connect(self._on_file_saved_signal)
        self.ui_state.processing_started.connect(self._on_processing_started_signal)
        self.ui_state.processing_finished.connect(self._on_processing_finished_signal)
        self.ui_state.undo_redo_changed.connect(self._on_undo_redo_changed_signal)
    
    def _setup_callbacks(self):
        """Налаштовує колбеки для ProcessingManager"""
        self.processing_manager.on_progress_update = self._on_progress_update
        self.processing_manager.on_row_processed = self._on_row_processed
        self.processing_manager.on_semi_auto_pause = self._on_semi_auto_pause
    
    def _setup_shortcuts(self):
        """Налаштовує гарячі клавіші"""
        # Enter - пошук
        search_shortcut = QShortcut(QKeySequence(Qt.Key_Return), self)
        search_shortcut.activated.connect(self.search_address)
        
        # * - встановити індекс *
        star_shortcut = QShortcut(QKeySequence("*"), self)
        star_shortcut.activated.connect(self.set_index_star)
        
        # Ctrl+Z - Undo
        undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        undo_shortcut.activated.connect(self.undo_action)
        
        # Ctrl+Y - Redo
        redo_shortcut = QShortcut(QKeySequence("Ctrl+Y"), self)
        redo_shortcut.activated.connect(self.redo_action)
        
        # Стрілки - навігація
        up_shortcut = QShortcut(QKeySequence(Qt.Key_Up), self)
        up_shortcut.activated.connect(self.go_to_previous_row)
        
        down_shortcut = QShortcut(QKeySequence(Qt.Key_Down), self)
        down_shortcut.activated.connect(self.go_to_next_row)
    
    def _start_background_cache_loading(self):
        """Запускає фонове завантаження кешу"""
        self.cache_thread = CacheLoaderThread(self.search_manager)
        self.cache_thread.progress.connect(self._on_cache_progress)
        self.cache_thread.finished.connect(self._on_cache_loaded)
        self.cache_thread.start()
        
        self.status_bar.setText("⏳ Довідник завантажується у фоні...")
        self.logger.info("Запущено фонове завантаження magistral cache")
    
    def _on_cache_progress(self, message: str):
        """Оновлення прогресу завантаження"""
        self.status_bar.setText(message)
    
    def _on_cache_loaded(self, records: list):
        """Колбек після завантаження кешу"""
        if records and self.address_panel:
            self.address_panel.set_magistral_cache(records)
            self.logger.info(f"Magistral cache завантажено: {len(records)} записів")
            self._cache_loaded = True
            self.status_bar.setText(f"✅ Довідник завантажено ({len(records):,} записів). Готово!")
        else:
            self.logger.error("Не вдалося завантажити magistral cache")
            self.status_bar.setText("⚠️ Помилка завантаження довідника")
            self._cache_loaded = False
    
    # ==================== ОБРОБНИКИ СИГНАЛІВ ====================
    
    def _on_file_loaded_signal(self, file_path: str):
        """Обробка сигналу завантаження файлу"""
        self.file_label.setText(os.path.basename(file_path))
        
        # Активуємо кнопки
        buttons = {
            'column_mapping': self.column_mapping_btn,
            'save': self.save_btn,
            'save_as': self.save_as_btn,
            'search': self.search_btn,
            'auto_process': self.auto_process_btn,
            'semi_auto': self.semi_auto_btn,
            'parse_addresses': self.parse_addresses_btn  # ДОДАНО
        }
        self.ui_state.enable_buttons_for_file_loaded(buttons)
        
        self.status_bar.setText(f"✅ Завантажено: {os.path.basename(file_path)}")
    
    def _on_file_saved_signal(self):
        """Обробка сигналу збереження файлу"""
        self.status_bar.setText("✅ Файл збережено")
    
    def _on_processing_started_signal(self):
        """Обробка початку обробки"""
        self.progress_bar.setVisible(True)
        
        buttons = {
            'search': self.search_btn,
            'auto_process': self.auto_process_btn,
            'semi_auto': self.semi_auto_btn,
            'column_mapping': self.column_mapping_btn,
            'save': self.save_btn
        }
        self.ui_state.disable_buttons_for_processing(buttons)
        
        # Додаємо кнопку ЗУПИНИТИ
        if not self.stop_btn:
            self.stop_btn = QPushButton("⏹ ЗУПИНИТИ")
            self.stop_btn.setStyleSheet(AppStyles.button_danger())
            self.stop_btn.clicked.connect(self.stop_processing)
            self.statusBar().addPermanentWidget(self.stop_btn)
    
    def _on_processing_finished_signal(self):
        """Обробка завершення обробки"""
        self.progress_bar.setVisible(False)
        
        buttons = {
            'search': self.search_btn,
            'auto_process': self.auto_process_btn,
            'semi_auto': self.semi_auto_btn,
            'column_mapping': self.column_mapping_btn,
            'save': self.save_btn
        }
        self.ui_state.enable_buttons_after_processing(buttons)
        
        # Видаляємо кнопку ЗУПИНИТИ
        if self.stop_btn:
            self.statusBar().removeWidget(self.stop_btn)
            self.stop_btn.deleteLater()
            self.stop_btn = None
    
    def _on_undo_redo_changed_signal(self):
        """Обробка зміни стану Undo/Redo"""
        self.undo_btn.setEnabled(self.undo_manager.can_undo())
        self.redo_btn.setEnabled(self.undo_manager.can_redo())
    
    def _on_progress_update(self, current: int, total: int):
        """Колбек оновлення прогресу"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        
        percent = int((current / total) * 100)
        self.status_bar.setText(f"⏳ Обробка {current}/{total} ({percent}%)...")
        
        # Прокручуємо до активного рядка
        if current - 1 < self.table.rowCount():
            self.scroll_to_row(current - 1)
    
    def _on_row_processed(self, row_idx: int, index: str):
        """Колбек обробки рядка"""
        mapping = self.file_manager.excel_handler.column_mapping
        if mapping and 'index' in mapping:
            idx_col = mapping['index'][0]
            item = self.table.item(row_idx, idx_col)
            if item:
                item.setText(index)
                item.setForeground(QColor(AppStyles.Colors.INDEX_APPLIED))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
    
    def _on_semi_auto_pause(self, row_idx: int, results: list):
        """Колбек паузи напівавтоматичної обробки"""
        self.current_row = row_idx
        self.table.selectRow(row_idx)
        self.scroll_to_row(row_idx)
        
        # Показуємо результати
        address = self.file_manager.excel_handler.get_address_from_row(row_idx)
        self.results_panel.show_results(results, address.building or "")
        self.address_panel.populate_from_results(results)
        
        confidence = results[0].get('confidence', 0) if results else 0
        self.status_bar.setText(
            f"⏸ Очікування вибору індексу для рядка {row_idx + 1} (точність {confidence}%)"
        )
    
    # ==================== ОСНОВНІ МЕТОДИ ====================
    
    def load_file(self):
        """Завантаження файлу через FileManager"""
        file_path = self.file_manager.get_file_dialog_path(self, mode='open')
        if not file_path:
            return
        
        success = self.file_manager.load_file(file_path)
        if success:
            self.ui_state.set_file_loaded(file_path)
            self._display_table()
            
            # Пропонуємо налаштувати колонки
            if not self.file_manager.excel_handler.column_mapping:
                reply = QMessageBox.question(
                    self,
                    "Налаштування стовпців",
                    "Бажаєте налаштувати відповідність стовпців зараз?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self.configure_columns()
        else:
            QMessageBox.critical(self, "Помилка", "Не вдалося завантажити файл")
    
    def save_file(self):
        """Збереження файлу через FileManager"""
        save_old_index = self.save_old_index_checkbox.isChecked()
        
        success = self.file_manager.save_file(
            save_old_index=save_old_index,
            parent=self
        )
        
        if success:
            self.ui_state.set_file_saved()
            QMessageBox.information(self, "Успіх", "Файл успішно збережено!")
        else:
            QMessageBox.critical(self, "Помилка", "Не вдалося зберегти файл")
    
    def save_file_as(self):
        """Збереження файлу під новим ім'ям"""
        file_path = self.file_manager.get_file_dialog_path(self, mode='save')
        if not file_path:
            return
        
        save_old_index = self.save_old_index_checkbox.isChecked()
        
        success = self.file_manager.save_file(
            file_path=file_path,
            save_old_index=save_old_index,
            parent=self
        )
        
        if success:
            self.file_manager.current_file = file_path
            self.ui_state.set_file_loaded(file_path)
            self.ui_state.set_file_saved()
            QMessageBox.information(self, "Успіх", "Файл успішно збережено!")
        else:
            QMessageBox.critical(self, "Помилка", "Не вдалося зберегти файл")
    
    def configure_columns(self):
        """Налаштування відповідності стовпців"""
        if self.file_manager.excel_handler.df is None or self.file_manager.excel_handler.df.empty:
            return
        
        df_sample = self.file_manager.excel_handler.df.head(10)
        
        dialog = ColumnMappingDialog(
            self.file_manager.excel_handler.get_column_names(),
            self.file_manager.excel_handler.column_mapping or {},
            df_sample,
            self
        )
        
        if dialog.exec_():
            mapping = dialog.get_mapping()
            self.file_manager.excel_handler.set_column_mapping(mapping)
            self._display_table()
            self.file_manager.copy_to_old_index()
            
            QMessageBox.information(self, "Успіх", "Відповідність стовпців оновлено!")
    
    def search_address(self):
        """Пошук адреси через SearchManager"""
        # Перевіряємо чи завантажено довідник
        if not self._cache_loaded:
            QMessageBox.information(
                self, 
                "Завантаження", 
                "Довідник міст ще завантажується у фоні.\n\nБудь ласка, зачекайте."
            )
            return
        
        if self.current_row < 0:
            QMessageBox.warning(self, "Увага", "Оберіть рядок для пошуку")
            return
        try:
            self.status_bar.setText("🔍 Пошук...")
            
            # Отримуємо адресу
            address = self.file_manager.excel_handler.get_address_from_row(self.current_row)
            
            # Виконуємо пошук через SearchManager (з логуванням)
            results = self.search_manager.search(address, max_results=20)
            
            # Відображаємо результати
            self.search_results = results
            self.results_panel.show_results(results, address.building or "")
            
            if results:
                self.address_panel.populate_from_results(results)
            
            self.status_bar.setText(f"✅ Знайдено {len(results)} варіантів")
            
        except Exception as e:
            self.logger.error(f"Помилка пошуку: {e}")
            QMessageBox.critical(self, "Помилка", f"Помилка пошуку:\n{e}")
            self.status_bar.setText("❌ Помилка пошуку")
    
    def apply_index(self, index: str):
        """Застосування індексу через ProcessingManager"""
        if self.current_row < 0:
            return
        
        # Застосовуємо через ProcessingManager (з Undo)
        success = self.processing_manager.apply_index(self.current_row, index)
        
        if success:
            # Оновлюємо таблицю
            mapping = self.file_manager.excel_handler.column_mapping
            if mapping and 'index' in mapping:
                idx_col = mapping['index'][0]
                item = self.table.item(self.current_row, idx_col)
                if item:
                    item.setText(index)
                    item.setForeground(QColor(AppStyles.Colors.INDEX_APPLIED))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
            
            # Логуємо через SearchManager
            address = self.file_manager.excel_handler.get_address_from_row(self.current_row)
            self.search_manager.log_index_applied(self.current_row, address, index)
            
            # Оновлюємо стан Undo/Redo
            self.ui_state.undo_redo_changed.emit()
            
            self.status_bar.setText(f"✅ Застосовано індекс {index}")
            
            # Очищаємо форми
            self._clear_address_forms()
            
            # Переходимо на наступний рядок
            if self.current_row + 1 < self.table.rowCount():
                self.table.selectRow(self.current_row + 1)
                self.scroll_to_row(self.current_row + 1)
            
            # Продовжуємо напівавто якщо потрібно
            if self.processing_manager.semi_auto_waiting:
                self.processing_manager.semi_auto_waiting = False
                QApplication.processEvents()
                self._continue_semi_auto()
    
    def start_auto_processing(self):
        """Запуск автоматичної обробки"""
        if self.current_row < 0:
            self.current_row = 0
        
        dialog = AutoProcessingDialog(
            self.current_row,
            len(self.file_manager.excel_handler.df),
            self
        )
        
        if dialog.exec_():
            min_confidence = dialog.get_min_confidence()
            
            # Встановлюємо стан обробки
            self.ui_state.set_processing_state(True)
            
            # Запускаємо через ProcessingManager
            stats = self.processing_manager.start_auto_processing(
                start_row=self.current_row,
                total_rows=len(self.file_manager.excel_handler.df),
                min_confidence=min_confidence,
                search_func=lambda addr: self.search_manager.search(addr)
            )
            
            # Завершуємо
            self.ui_state.set_processing_state(False)
            
            self.status_bar.setText(
                f"✅ Оброблено: {stats['processed']}, Пропущено: {stats['skipped']}"
            )
            
            QMessageBox.information(
                self,
                "Завершено",
                f"Обробка завершена!\n\nОброблено: {stats['processed']}\nПропущено: {stats['skipped']}"
            )
    
    def start_semi_auto_processing(self):
        """Запуск напівавтоматичної обробки"""
        if self.current_row < 0:
            self.current_row = 0
        
        dialog = AutoProcessingDialog(
            self.current_row,
            len(self.file_manager.excel_handler.df),
            self
        )
        
        if dialog.exec_():
            min_confidence = dialog.get_min_confidence()
            
            # Встановлюємо стан обробки
            self.ui_state.set_processing_state(True)
            
            # Запускаємо через ProcessingManager
            stats = self.processing_manager.start_semi_auto_processing(
                start_row=self.current_row,
                total_rows=len(self.file_manager.excel_handler.df),
                min_confidence=min_confidence,
                search_func=lambda addr: self.search_manager.search(addr)
            )
            
            # Якщо не чекаємо - завершуємо
            if not self.processing_manager.semi_auto_waiting:
                self.ui_state.set_processing_state(False)
                
                self.status_bar.setText(
                    f"✅ Оброблено: {stats['processed']}, Пропущено: {stats['skipped']}"
                )
                
                QMessageBox.information(
                    self,
                    "Завершено",
                    f"Обробка завершена!\n\nОброблено: {stats['processed']}\nПропущено: {stats['skipped']}"
                )
    
    def _continue_semi_auto(self):
        """Продовження напівавтоматичної обробки"""
        stats = self.processing_manager.continue_semi_auto(
            search_func=lambda addr: self.search_manager.search(addr)
        )
        
        if not self.processing_manager.semi_auto_waiting:
            self.ui_state.set_processing_state(False)
            
            self.status_bar.setText(
                f"✅ Оброблено: {stats['processed']}, Пропущено: {stats['skipped']}"
            )
    
    def stop_processing(self):
        """Зупинка обробки"""
        self.processing_manager.stop_processing()
        self.logger.info("Обробку зупинено користувачем")
    
    def undo_action(self):
        """Відміна дії через UndoManager"""
        if not self.undo_manager.can_undo():
            return
        
        action = self.undo_manager.undo()
        if not action:
            return
        
        row_idx = action['row']
        old_values = action['old_values']
        
        # Відновлюємо старі значення
        for field_id, value in old_values.items():
            self.file_manager.excel_handler.update_row(row_idx, {field_id: value})
        
        # Оновлюємо таблицю
        mapping = self.file_manager.excel_handler.column_mapping
        if mapping and 'index' in mapping:
            for col_idx in mapping['index']:
                item = self.table.item(row_idx, col_idx)
                if item:
                    item.setText(str(old_values.get('index', '')))
                    item.setForeground(QColor(AppStyles.Colors.INDEX_DEFAULT))
                    font = item.font()
                    font.setBold(False)
                    item.setFont(font)
        
        self.ui_state.undo_redo_changed.emit()
        self.status_bar.setText("↩️ Дію відмінено")
        self.logger.info(f"Undo: рядок {row_idx}")
    
    def redo_action(self):
        """Повторення дії через UndoManager"""
        if not self.undo_manager.can_redo():
            return
        
        action = self.undo_manager.redo()
        if not action:
            return
        
        row_idx = action['row']
        new_values = action['new_values']
        
        # Застосовуємо нові значення
        for field_id, value in new_values.items():
            self.file_manager.excel_handler.update_row(row_idx, {field_id: value})
        
        # Оновлюємо таблицю
        mapping = self.file_manager.excel_handler.column_mapping
        if mapping and 'index' in mapping:
            for col_idx in mapping['index']:
                item = self.table.item(row_idx, col_idx)
                if item:
                    item.setText(str(new_values.get('index', '')))
                    item.setForeground(QColor(AppStyles.Colors.INDEX_APPLIED))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
        
        self.ui_state.undo_redo_changed.emit()
        self.status_bar.setText("↪️ Дію повторено")
        self.logger.info(f"Redo: рядок {row_idx}")
    
    def refresh_cache(self):
        """Оновлення кешу magistral.csv"""
        reply = QMessageBox.question(
            self,
            "Оновлення кешу",
            "Оновити кеш magistral.csv?\n\nЦе займе ~3-5 хвилин.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.status_bar.setText("⏳ Оновлення кешу...")
            QApplication.processEvents()
            
            try:
                # Оновлюємо через SearchManager
                self.search_manager.refresh_cache(force_reload=True)
                
                # Оновлюємо кеш у address_panel
                self._load_magistral_cache()
                
                self.status_bar.setText("✅ Кеш оновлено")
                QMessageBox.information(self, "Готово", "Кеш успішно оновлено!")
                
            except Exception as e:
                self.logger.error(f"Помилка оновлення кешу: {e}")
                self.status_bar.setText(f"❌ Помилка: {e}")
                QMessageBox.critical(self, "Помилка", f"Не вдалося оновити кеш:\n{e}")
                

    def parse_visible_addresses(self):
        """Парсить адреси у видимих (відфільтрованих) рядках"""
        if self.file_manager.excel_handler.df is None or self.file_manager.excel_handler.df.empty:
            QMessageBox.warning(self, "Увага", "Немає завантаженого файлу")
            return
        
        mapping = self.file_manager.excel_handler.column_mapping
        if not mapping:
            QMessageBox.warning(self, "Увага", "Спочатку налаштуйте відповідність стовпців")
            return
        
        # Підтвердження
        reply = QMessageBox.question(
            self,
            "Парсинг адрес",
            "Розпарсити адреси у видимих рядках?\n\n"
            "Це знайде рядки де вся адреса записана в одному полі\n"
            "та розділить її на окремі компоненти.\n\n"
            "Продовжити?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Імпортуємо функцію парсингу
        from utils.address_parser import parse_full_address_text, is_full_address_in_text
        import pandas as pd
        
        df = self.file_manager.excel_handler.df
        parsed_count = 0
        detected_count = 0  # Скільки знайшли
        
        # Знаходимо індекси колонок
        street_cols = mapping.get('street', [])
        city_cols = mapping.get('city', [])
        building_cols = mapping.get('building', [])
        
        if not street_cols:
            QMessageBox.warning(self, "Помилка", "Колонка 'Вулиця' не налаштована")
            return
        
        street_col = street_cols[0]
        city_col = city_cols[0] if city_cols else None
        building_col = building_cols[0] if building_cols else None
        
        # Перебираємо ТІЛЬКИ ВИДИМІ рядки
        self.status_bar.setText("⏳ Парсинг адрес...")
        QApplication.processEvents()
        
        print("\n" + "="*80)
        print("🔧 ПОЧАТОК ПАРСИНГУ АДРЕС")
        print("="*80)
        print(f"Колонка 'Вулиця': {street_col}")
        print(f"Колонка 'Місто': {city_col}")
        print(f"Колонка 'Будинок': {building_col}")
        print("="*80 + "\n")
        
        for visual_row in range(self.table.rowCount()):
            # Пропускаємо приховані рядки (відфільтровані)
            if self.table.isRowHidden(visual_row):
                continue
            
            # Отримуємо значення з таблиці
            street_item = self.table.item(visual_row, street_col)
            if not street_item:
                continue
            
            street_value = street_item.text()
            
            # Перевіряємо чи це повна адреса
            if is_full_address_in_text(street_value):
                detected_count += 1
                
                print(f"\n📍 РЯДОК {visual_row + 1}:")
                print(f"   Вихідний текст: {street_value[:100]}...")
                
                # Парсимо
                parsed = parse_full_address_text(street_value)
                
                print(f"   ✓ Індекс: '{parsed['index']}'")
                print(f"   ✓ Місто: '{parsed['city']}'")
                print(f"   ✓ Вулиця: '{parsed['street']}'")
                print(f"   ✓ Будинок: '{parsed['building']}'")
                
                # Перевіряємо що витягли
                if not parsed['city'] and not parsed['street']:
                    print(f"   ⚠️ ПРОПУЩЕНО: не вдалося витягти місто та вулицю")
                    continue
                
                # Записуємо в DataFrame
                updated = False
                
                if city_col is not None and parsed['city']:
                    old_city = df.iloc[visual_row, city_col] if pd.notna(df.iloc[visual_row, city_col]) else ""
                    df.iloc[visual_row, city_col] = parsed['city']
                    city_item = self.table.item(visual_row, city_col)
                    if city_item:
                        city_item.setText(parsed['city'])
                    print(f"   📝 Місто: '{old_city}' → '{parsed['city']}'")
                    updated = True
                
                if parsed['street']:
                    df.iloc[visual_row, street_col] = parsed['street']
                    street_item.setText(parsed['street'])
                    print(f"   📝 Вулиця: → '{parsed['street']}'")
                    updated = True
                
                if building_col is not None and parsed['building']:
                    old_building = df.iloc[visual_row, building_col] if pd.notna(df.iloc[visual_row, building_col]) else ""
                    df.iloc[visual_row, building_col] = parsed['building']
                    building_item = self.table.item(visual_row, building_col)
                    if building_item:
                        building_item.setText(parsed['building'])
                    print(f"   📝 Будинок: '{old_building}' → '{parsed['building']}'")
                    updated = True
                
                if updated:
                    parsed_count += 1
                    print(f"   ✅ ОНОВЛЕНО")
                else:
                    print(f"   ⚠️ НЕ ОНОВЛЕНО (порожні дані)")
        
        print("\n" + "="*80)
        print(f"🏁 ЗАВЕРШЕНО ПАРСИНГ")
        print(f"   Знайдено адрес у неправильному форматі: {detected_count}")
        print(f"   Успішно розпарсовано: {parsed_count}")
        print("="*80 + "\n")
        
        self.status_bar.setText(f"✅ Розпарсовано {parsed_count} з {detected_count} адрес")
        
        if parsed_count > 0:
            QMessageBox.information(
                self,
                "Готово",
                f"Знайдено адрес у неправильному форматі: {detected_count}\n"
                f"Успішно розпарсовано: {parsed_count}\n\n"
                f"Дивіться деталі в консолі.\n\n"
                "Тепер можете запустити автоматичну обробку знову."
            )
        else:
            QMessageBox.information(
                self,
                "Результат",
                f"Знайдено адрес у неправильному форматі: {detected_count}\n"
                f"Успішно розпарсовано: {parsed_count}\n\n"
                "Дивіться деталі в консолі."
            )
    
    def set_index_star(self):
        """Встановлює індекс *"""
        if self.current_row >= 0:
            self.apply_index("*")
    
    # ==================== РОБОТА З ТАБЛИЦЕЮ ====================
    
    def _display_table(self):
        """Відображає дані в таблиці"""
        df = self.file_manager.excel_handler.df
        
        if df is None or df.empty:
            return
        
        self.table.blockSignals(True)
        
        self.table.setRowCount(len(df))
        self.table.setColumnCount(len(df.columns))
        
        # Заголовки
        header_labels = []
        for i, db_col in enumerate(df.columns):
            our_name = self._get_our_field_name_for_column(i)
            if our_name:
                header_labels.append(f"{our_name}\n({db_col})")
            else:
                header_labels.append(str(db_col))
        
        self.table.setHorizontalHeaderLabels(header_labels)
        
        # Заповнюємо дані
        for i in range(len(df)):
            for j in range(len(df.columns)):
                value = df.iloc[i, j]
                item = QTableWidgetItem(str(value) if pd.notna(value) else "")
                
                # Старий індекс - readonly
                if j == len(df.columns) - 1 and df.columns[j] == 'Старий індекс':
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    item.setBackground(QColor(240, 240, 240))
                
                self.table.setItem(i, j, item)
        
        # Відновлюємо ширини стовпців
        saved_widths = SettingsManager.get_column_widths()
        if saved_widths and len(saved_widths) == len(df.columns):
            for i, width in enumerate(saved_widths):
                self.table.setColumnWidth(i, width)
        else:
            self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
            self.table.resizeColumnsToContents()
        
        self.table.blockSignals(False)
    
    def _get_our_field_name_for_column(self, col_idx):
        """Повертає назву поля для відображення в заголовку"""
        if self.file_manager.excel_handler.df is not None:
            if col_idx == len(self.file_manager.excel_handler.df.columns) - 1:
                if self.file_manager.excel_handler.df.columns[col_idx] == 'Старий індекс':
                    return 'Ст.Інд.(поч.)'
        
        field_names = {
            'client_id': 'ID',
            'name': 'ПІБ',
            'region': 'Область',
            'district': 'Район',
            'city': 'Місто',
            'street': 'Вулиця',
            'building': 'Буд.',
            'index': 'Індекс'
        }
        
        mapping = self.file_manager.excel_handler.column_mapping
        if not mapping:
            return None
        
        for field_id, col_indices in mapping.items():
            if col_idx in col_indices:
                return field_names.get(field_id, field_id)
        
        return None
    
    def on_row_selected(self):
        """Обробка вибору рядка"""
        selected_rows = self.table.selectionModel().selectedRows()
        
        if not selected_rows:
            self.search_btn.setEnabled(False)
            return
        
        self.current_row = selected_rows[0].row()
        self.ui_state.set_current_row(self.current_row)
        self.search_btn.setEnabled(True)
        self.results_panel.clear()
        
        # Відображаємо оригінальні дані
        try:
            address = self.file_manager.excel_handler.get_address_from_row(self.current_row)
            parts = []
            
            if address.region:
                parts.append(f"Область: {address.region}")
            if address.district:
                parts.append(f"Район: {address.district}")
            if address.city:
                parts.append(f"Місто: {address.city}")
            if address.street:
                parts.append(f"Вулиця: {address.street}")
            if address.building:
                parts.append(f"Будинок: {address.building}")
            
            text = " | ".join(parts) if parts else "Немає даних"
            self.original_data_label.setText(f"📋 Оригінальні дані: {text}")
            
        except Exception as e:
            self.logger.error(f"Помилка відображення даних: {e}")
        
        # Автоматичний пошук
        self.search_address()
    
    def on_cell_edited(self, item):
        """Обробка редагування комірки"""
        if not item:
            return
        
        row = item.row()
        col = item.column()
        new_value = item.text()
        
        # Оновлюємо DataFrame
        self.file_manager.excel_handler.df.iloc[row, col] = str(new_value)
        
        self.logger.debug(f"Комірка змінена: row={row}, col={col}, value={new_value}")
        
        # Зелений колір для індексу при ручній зміні
        mapping = self.file_manager.excel_handler.column_mapping
        if mapping and 'index' in mapping:
            index_col = mapping['index'][0]
            if col == index_col and new_value.strip():
                item.setForeground(QColor(AppStyles.Colors.INDEX_APPLIED))
    
    def apply_filter(self, filter_type):
        """Фільтр: зелений текст = проставлено"""
        if self.file_manager.excel_handler.df is None:
            return
        
        mapping = self.file_manager.excel_handler.column_mapping
        if not mapping or 'index' not in mapping:
            self.logger.warning("Mapping не налаштовано")
            return
        
        index_cols = mapping.get('index', [])
        if not index_cols:
            return
        
        idx_col = index_cols[0]
        
        for row in range(self.table.rowCount()):
            try:
                index_item = self.table.item(row, idx_col)
                
                if index_item:
                    text_color = index_item.foreground().color()
                    is_green = (
                        text_color.red() == 76 and
                        text_color.green() == 175 and
                        text_color.blue() == 80
                    )
                else:
                    is_green = False
                
                if filter_type == "Проставлено":
                    show = is_green
                elif filter_type == "Непроставлено":
                    show = not is_green
                else:  # "Всі"
                    show = True
                
                self.table.setRowHidden(row, not show)
                
            except Exception as e:
                self.logger.error(f"Помилка фільтра рядка {row}: {e}")
                self.table.setRowHidden(row, False)
                continue
        
        visible_count = sum(1 for row in range(self.table.rowCount()) if not self.table.isRowHidden(row))
        self.status_bar.setText(f"Фільтр '{filter_type}': показано {visible_count} з {self.table.rowCount()} рядків")
    
    def update_table_font_size(self, size):
        """Оновлює розмір шрифту таблиці"""
        self.table.setStyleSheet(f"font-size: {size}px;")
    
    def scroll_to_row(self, row):
        """Прокручує таблицю до рядка"""
        if row >= 0 and row < self.table.rowCount():
            self.table.scrollToItem(
                self.table.item(row, 0),
                QAbstractItemView.PositionAtCenter
            )
    
    # ==================== НАВІГАЦІЯ ====================
    
    def go_to_previous_row(self):
        """Перехід на попередній рядок"""
        if self.current_row > 0:
            prev_row = self.current_row - 1
            self.table.selectRow(prev_row)
            self.scroll_to_row(prev_row)
            self.current_row = prev_row
        else:
            self.status_bar.setText("⚠️ Це перший рядок")
    
    def go_to_next_row(self):
        """Перехід на наступний рядок"""
        if self.current_row < self.table.rowCount() - 1:
            next_row = self.current_row + 1
            self.table.selectRow(next_row)
            self.scroll_to_row(next_row)
            self.current_row = next_row
        else:
            self.status_bar.setText("⚠️ Це останній рядок")
    
    # ==================== ДОПОМІЖНІ МЕТОДИ ====================
    
    def _clear_address_forms(self):
        """Очищає форми введення адреси"""
        # Очищаємо каскадну форму
        self.address_panel.cascade_city_input.clear()
        self.address_panel.cascade_street_input.clear()
        self.address_panel.cascade_street_input.setEnabled(False)
        self.address_panel.cascade_building_combo.clear()
        self.address_panel.cascade_building_combo.hide()
        self.address_panel.cascade_index_input.clear()
        
        # Ховаємо popup списки
        if hasattr(self.address_panel, 'cascade_city_list'):
            self.address_panel.cascade_city_list.hide()
        if hasattr(self.address_panel, 'cascade_street_list'):
            self.address_panel.cascade_street_list.hide()
    
    # ==================== ЗАКРИТТЯ ВІКНА ====================
    
    def closeEvent(self, event):
        """Збереження стану при закритті"""
        # Зберігаємо геометрію вікна
        geometry = self.geometry()
        SettingsManager.set_window_geometry(
            geometry.x(), geometry.y(),
            geometry.width(), geometry.height()
        )
        
        # Зберігаємо ширини стовпців
        if self.table.columnCount() > 0:
            widths = [self.table.columnWidth(i) for i in range(self.table.columnCount())]
            SettingsManager.set_column_widths(widths)
        
        # Зберігаємо розміри splitter
        right_splitter = self.findChild(QSplitter)
        if right_splitter:
            sizes = right_splitter.sizes()
            SettingsManager.set_splitter_sizes('right_panel', sizes)
        
        event.accept()