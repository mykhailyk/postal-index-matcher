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
from typing import Dict, List, Optional

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
from ui.widgets.top_panel import TopPanel
from ui.widgets.table_panel import TablePanel

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
        self.df = None  # DataFrame для сортування
        self.auto_applied_rows = set()  # Запам'ятуємо які рядки проставили

        
        # Віджети (ініціалізуються в init_ui)
        # Віджети (ініціалізуються в init_ui)
        self.top_panel = None
        self.table_panel = None
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
        self.logger.info("=== ПОЧАТОК ЗАВАНТАЖЕННЯ UKRPOSHTA CACHE ===")

        # ВИКЛИКАЄМО _ensure_loaded() щоб завантажити дані
        self.search_manager.search_engine._ensure_loaded()

        records = self.search_manager.get_magistral_records()
        self.logger.info(f"Отримано {len(records) if records else 0} записів")

        if records and self.address_panel:
            self.logger.info(f"Передаємо {len(records):,} записів в AddressSelectorPanel...")
            print(f"\n📦 Передаємо {len(records):,} записів в AddressSelectorPanel...")
            self.address_panel.set_magistral_cache(records)
            self.logger.info("AddressSelectorPanel ініціалізовано")
            print("✅ AddressSelectorPanel ініціалізовано\n")
        else:
            self.logger.warning(f"НЕ ПЕРЕДАНО: records={len(records) if records else 0}, address_panel={self.address_panel is not None}")

        self._cache_loaded = True
        self.logger.info("=== КІНЕЦЬ ЗАВАНТАЖЕННЯ ===")
        
        self.logger.info("GUI ініціалізовано")
    
    # ==================== ІНІЦІАЛІЗАЦІЯ UI ====================
    # ==================== ІНІЦІАЛІЗАЦІЯ UI ====================
       
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
        self.top_panel = TopPanel()
        self._connect_top_panel_signals()
        main_layout.addWidget(self.top_panel)
        
        main_splitter = QSplitter(Qt.Horizontal)
        
        self.table_panel = TablePanel()
        self._connect_table_panel_signals()
        main_splitter.addWidget(self.table_panel)
        
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
    
    def _connect_top_panel_signals(self):
        """Підключає сигнали верхньої панелі"""
        self.top_panel.load_file_clicked.connect(self.load_file)
        self.top_panel.save_file_clicked.connect(self.save_file)
        self.top_panel.save_as_clicked.connect(self.save_file_as)
        self.top_panel.configure_columns_clicked.connect(self.configure_columns)
        self.top_panel.parse_addresses_clicked.connect(self.parse_visible_addresses)
        self.top_panel.undo_clicked.connect(self.undo_action)
        self.top_panel.redo_clicked.connect(self.redo_action)
        self.top_panel.refresh_cache_clicked.connect(self.refresh_cache)
        self.top_panel.filter_changed.connect(self.apply_filter)

    def _connect_table_panel_signals(self):
        """Підключає сигнали панелі таблиці"""
        self.table_panel.prev_row_clicked.connect(self.go_to_previous_row)
        self.table_panel.next_row_clicked.connect(self.go_to_next_row)
        self.table_panel.search_clicked.connect(self.search_address)
        self.table_panel.auto_process_clicked.connect(self.start_auto_processing)
        self.table_panel.semi_auto_clicked.connect(self.start_semi_auto_processing)
        self.table_panel.font_size_changed.connect(self.update_table_font_size)
        self.table_panel.row_selected.connect(self.on_row_selected)
        self.table_panel.cell_edited.connect(self.on_cell_edited)
        self.table_panel.header_clicked.connect(self.on_header_clicked)
    
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
        
    def on_header_clicked(self, column_idx):
        """Обробка кліку на заголовок колонки"""
        # header = self.sender() # Вже не потрібно, отримуємо індекс напряму
        if column_idx >= 0:
            column_name = self.file_manager.excel_handler.df.columns[column_idx]
                
                # Визначаємо напрямок сортування
                ascending = self.current_sort_order != 'asc'
                
                # ✅ СОРТУЄМО НАПРЯМУ В DATAFRAME
                try:
                    self.file_manager.excel_handler.df.sort_values(
                        by=column_name, 
                        ascending=ascending, 
                        inplace=True
                    )
                    self.file_manager.excel_handler.df.reset_index(drop=True, inplace=True)
                    
                    # Перемикаємо напрямок
                    self.current_sort_order = 'asc' if ascending else 'desc'
                    
                    # Оновлюємо таблицю
                    self._display_table()
                    
                    self.logger.info(f"✅ Сортування по '{column_name}' - {self.current_sort_order}")
                except Exception as e:
                    self.logger.error(f"❌ Помилка сортування: {e}")
        
    def sort_dataframe(self, column_name, order='asc'):
        """
        Сортує DataFrame по заданій колонці
        """
        from utils.logger import Logger
        
        if self.file_manager.excel_handler.df is None or column_name not in self.file_manager.excel_handler.df.columns:
            return
        
        # Визначаємо напрямок
        ascending = (order == 'asc')
        
        try:
            # Заповнюємо NaN пустими рядками
            self.file_manager.excel_handler.df[column_name] = self.file_manager.excel_handler.df[column_name].fillna('')
            
            # Сортуємо
            self.file_manager.excel_handler.df = self.file_manager.excel_handler.df.sort_values(
                by=column_name,
                ascending=ascending,
                na_position='last'
            )
            
            # Скидаємо індекс
            self.file_manager.excel_handler.df = self.file_manager.excel_handler.df.reset_index(drop=True)
            
        except Exception as e:
            logger = Logger()
            logger.error(f"Помилка сортування: {e}")
            
    def update_header_sort_indicator(self, column_index, order):
        """
        Оновлює візуальний індикатор сортування в заголовку
        """
        self.table_panel.update_header_sort_indicator(column_index, order)
        

    
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
        self.top_panel.set_file_name(os.path.basename(file_path))
        
        # Активуємо кнопки
        buttons = {
            'column_mapping': self.top_panel.column_mapping_btn,
            'save': self.top_panel.save_btn,
            'save_as': self.top_panel.save_as_btn,
            'search': self.table_panel.search_btn,
            'auto_process': self.table_panel.auto_process_btn,
            'semi_auto': self.table_panel.semi_auto_btn,
            'parse_addresses': self.top_panel.parse_addresses_btn
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
            'search': self.table_panel.search_btn,
            'auto_process': self.table_panel.auto_process_btn,
            'semi_auto': self.table_panel.semi_auto_btn,
            'column_mapping': self.top_panel.column_mapping_btn,
            'save': self.top_panel.save_btn
        }
        self.ui_state.disable_buttons_for_processing(buttons)
        
        # Додаємо кнопку ЗУПИНИТИ
        if not self.stop_btn:
            self.stop_btn = QPushButton("⏹ ЗУПИНИТИ")
            self.stop_btn.setStyleSheet(AppStyles.button_danger())
            self.stop_btn.clicked.connect(self.stop_processing)
            self.status_bar().addPermanentWidget(self.stop_btn)
    
    def _on_processing_finished_signal(self):
        """Обробка завершення обробки"""
        self.progress_bar.setVisible(False)
        
        buttons = {
            'search': self.table_panel.search_btn,
            'auto_process': self.table_panel.auto_process_btn,
            'semi_auto': self.table_panel.semi_auto_btn,
            'column_mapping': self.top_panel.column_mapping_btn,
            'save': self.top_panel.save_btn
        }
        self.ui_state.enable_buttons_after_processing(buttons)
        
        # Видаляємо кнопку ЗУПИНИТИ
        if self.stop_btn:
            self.status_bar().removeWidget(self.stop_btn)
            self.stop_btn.deleteLater()
            self.stop_btn = None
    
    def _on_undo_redo_changed_signal(self):
        """Обробка зміни стану Undo/Redo"""
        self.top_panel.undo_btn.setEnabled(self.undo_manager.can_undo())
        self.top_panel.redo_btn.setEnabled(self.undo_manager.can_redo())
    
    def _on_progress_update(self, current: int, total: int):
        """Колбек оновлення прогресу"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        
        percent = int((current / total) * 100)
        self.status_bar.setText(f"⏳ Обробка {current}/{total} ({percent}%)...")
        
        # Прокручуємо до активного рядка
        if current - 1 < self.table_panel.table.rowCount():
            self.scroll_to_row(current - 1)
    
    def _on_row_processed(self, row_idx: int, index: str):
        """Колбек обробки рядка"""
        mapping = self.file_manager.excel_handler.column_mapping
        if mapping and 'index' in mapping:
            idx_col = mapping['index'][0]
            item = self.table_panel.table.item(row_idx, idx_col)
            if item:
                item.setText(index)
                item.setForeground(QColor(AppStyles.Colors.INDEX_APPLIED))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
    
    def _on_semi_auto_pause(self, row_idx: int, results: list):
        """Колбек паузи напівавтоматичної обробки"""
        self.current_row = row_idx
        self.table_panel.table.selectRow(row_idx)
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
            
            # ✅ ПЕРЕВІРЯЄМО ЧИ УЖЕ НАЛАШТОВАНИЙ MAPPING
            if not self.file_manager.excel_handler.column_mapping:
                # ❌ ЕСЛИ MAPPING НЕ НАЛАШТОВАНО - ВИКЛИКАЄМО ДІАЛОГ ВІДРАЗУ
                self.configure_columns()
            else:
                # ✅ ЕСЛИ MAPPING УЖЕ НАЛАШТОВАНО - ІНІЦІАЛІЗУЄМО СТАРИЙ ІНДЕКС
                self.file_manager._initialize_old_index_column()
                self._display_table()  # Оновлюємо таблицю щоб показати нову колонку
        else:
            # ❌ ЯКЩО ФАЙЛ НЕ ЗАВАНТАЖЕНО
            QMessageBox.critical(self, "Помилка", "Не вдалося завантажити файл")
    
    def save_file(self):
        """Збереження файлу через FileManager"""
        save_old_index = self.top_panel.is_save_old_index_checked()
        
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
        
        save_old_index = self.top_panel.is_save_old_index_checked()
        
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
            QMessageBox.warning(self, "Помилка", "Файл не завантажено")
            return
        
        try:
            # Отримуємо приклад даних для діалогу
            df_sample = self.file_manager.excel_handler.df.head(10)
            
            # Створюємо діалог налаштування
            dialog = ColumnMappingDialog(
                self.file_manager.excel_handler.get_column_names(),
                self.file_manager.excel_handler.column_mapping or {},
                df_sample,
                self
            )
            
            # ✅ ЯКЩО USER НАТИСНУВ OK
            if dialog.exec_():
                mapping = dialog.get_mapping()
                
                # ✅ ВСТАНОВЛЮЄМО MAPPING
                self.file_manager.excel_handler.set_column_mapping(mapping)
                
                # ✅ ІНІЦІАЛІЗУЄМО КОЛОНКУ "СТАРИЙ ІНДЕКС"
                self.file_manager._initialize_old_index_column()
                
                # ✅ ОНОВЛЮЄМО ТАБЛИЦЮ
                self._display_table()
            
                
                self.logger.info(f"✅ Mapping налаштовано: {mapping}")

            else:
                self.logger.info("❌ Налаштування скасовано користувачем")
        
        except Exception as e:
            self.logger.error(f"❌ Помилка налаштування колонок: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            QMessageBox.critical(self, "Помилка", f"Не вдалося налаштувати колонки:\n{e}")

    
    def search_address(self):
        """Виконує пошук адреси"""
        if self.current_row < 0:
            self.status_bar.setText("❌ Виберіть рядок для пошуку")
            return
        
        try:
            address = self.file_manager.excel_handler.get_address_from_row(self.current_row)
            result = self.search_manager.search_with_auto(address, auto_apply=False)
            
            if result['mode'] == 'auto':
                auto_result = result['auto_result']
                all_results = [auto_result] + result['manual_results']
                self.results_panel.display_results(all_results, highlight_first=True)
                self.status_bar.setText(f"✅ Автопідстановка: [{auto_result['index']}]")
            elif result['mode'] == 'manual':
                self.results_panel.display_results(result['manual_results'], highlight_first=False)
                self.status_bar.setText(f"⚠️ Знайдено {result['total_found']} варіантів")
            else:
                self.results_panel.clear()
                self.status_bar.setText("❌ Нічого не знайдено")
        except Exception as e:
            self.logger.error(f"Помилка пошуку: {e}")
            self.status_bar.setText(f"❌ Помилка: {e}")

    def apply_index(self, index: str):
        """Застосування індексу з правильним заповненням форми"""
        if self.current_row < 0:
            return
        
        try:
            # ✅ ЗАПИСУЄМО ПРЯМО В DATAFRAME
            mapping = self.file_manager.excel_handler.column_mapping
            if not mapping or 'index' not in mapping:
                self.logger.error("❌ Column mapping не налаштовано для 'index'")
                return
            
            idx_col = mapping['index'][0]
            
            # ЗАПИСУЄМО В DATAFRAME
            self.file_manager.excel_handler.df.iloc[self.current_row, idx_col] = index
            
            # ОНОВЛЮЄМО ТАБЛИЦЮ
            item = self.table_panel.table.item(self.current_row, idx_col)
            if item:
                item.setText(index)
                item.setForeground(QColor(76, 175, 80))  # Зелений!
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            
            # ✅ ЗАПАМ'ЯТУЄМО РЯДОК
            self.auto_applied_rows.add(self.current_row)
            
            # ЛОГУВАННЯ
            address = self.file_manager.excel_handler.get_address_from_row(self.current_row)
            self.logger.info(f"✅ Застосовано індекс [{index}] на рядку {self.current_row + 1}")
            
            # ✅ ПЕРЕХОДИМО НА НАСТУПНИЙ
            next_row = self.current_row + 1
            
            # ✅ ЗАПОВНЮЄМО ФОРМУ РУЧНОГО ВВЕДЕННЯ НАСТУПНОГО РЯДКА
            if next_row < len(self.file_manager.excel_handler.df):
                try:
                    next_address = self.file_manager.excel_handler.get_address_from_row(next_row)
                    
                    # ЗАПОВНЮЄМО ПОЛЯ (ПРАВИЛЬНІ НАЗВИ!)
                    self.address_panel.region_input.setText(next_address.region or '')
                    self.address_panel.city_input.setText(next_address.city or '')
                    self.address_panel.street_input.setText(next_address.street or '')
                    self.address_panel.index_input.setText(next_address.index or '')
                    
                    # ОЧИЩУЄМО БУДИНКИ
                    self.address_panel.buildings_combo.clear()
                    self.address_panel.buildings_combo.hide()
                    self.address_panel.buildings_label.hide()
                    
                    # ОЧИЩУЄМО РЕЗУЛЬТАТИ ПОШУКУ
                    self.results_panel.clear()
                    
                    self.logger.info(f"📋 Форма заповнена для рядка {next_row + 1}: {next_address.city}, {next_address.street}")
                    
                except Exception as e:
                    self.logger.error(f"❌ Помилка заповнення форми: {str(e)}")
                    import traceback
                    self.logger.error(traceback.format_exc())
            
            # UNDO/REDO
            self.processing_manager.apply_index(self.current_row, index)
            self.ui_state.undo_redo_changed.emit()
            
            self.status_bar.setText(f"✅ Застосовано індекс {index}")
            
            # ✅ ПЕРЕХОДИМО НА НАСТУПНИЙ РЯДОК ПРАВИЛЬНО
            if next_row < self.table_panel.table.rowCount():
                try:
                    # ВІДКЛЮЧАЄМО СИГНАЛ ДО ВИБОРУ
                    self.table_panel.table.itemSelectionChanged.disconnect()
                except:
                    pass
                
                # ВИБИРАЄМО РЯДОК
                self.table_panel.table.selectRow(next_row)
                self.scroll_to_row(next_row)
                self.current_row = next_row
                
                # ПОДАЄМО СИГНАЛ ВРУЧНУ
                self.table_panel.table.itemSelectionChanged.connect(self.on_row_selected)
                self.logger.info(f"➡️ Перехід на рядок {next_row + 1}")
                
                # ✅ ДОДАНО: АВТОМАТИЧНИЙ ПОШУК НА НОВОМУ РЯДКУ
                QTimer.singleShot(300, self.search_address)  # Затримка 300мс для оновлення форми
                
            else:
                self.status_bar.setText("✅ Обробка завершена! Всі рядки оброблені.")
                self.logger.info("🏁 Всі рядки оброблені!")
                
                # ОЧИЩУЄМО ФОРМИ
                self.address_panel.city_input.clear()
                self.address_panel.street_input.clear()
                self.address_panel.region_input.clear()
                self.address_panel.index_input.clear()
                self.results_panel.clear()
        
        except Exception as e:
            self.logger.error(f"❌ Критична помилка в apply_index: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            QMessageBox.critical(self, "Помилка", f"Помилка застосування індексу:\n{e}")


    
    def start_auto_processing(self):
        """Запустити автоматичну обробку адрес"""
        if self.file_manager.excel_handler.df is None:
            QMessageBox.warning(self, "Помилка", "Файл не завантажено")
            return
        
        
        # ДІАЛОГ
        from PyQt5.QtWidgets import QDialog
        dialog = AutoProcessingDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return
        
        start_row = dialog.get_start_row()
        min_confidence = dialog.get_min_confidence()
        
        self.logger.info("=" * 80)
        self.logger.info("🚀 ЗАПУСК АВТОМАТИЧНОЇ ОБРОБКИ")
        self.logger.info(f"   Початковий рядок: {start_row + 1}")
        self.logger.info(f"   Мінімальна точність: {min_confidence}%")
        self.logger.info("=" * 80)
        
        self.auto_process_btn.setEnabled(False)
        self.semi_auto_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        
        df = self.file_manager.excel_handler.df
        total_rows = len(df)
        
        stats = {
            'total': total_rows - start_row,
            'auto_applied': 0,
            'manual_required': 0,
            'not_found': 0,
            'skipped': 0,
            'errors': 0
        }
        
        try:
            for idx in range(start_row, total_rows):
                self.current_row = idx
                
                if stats['total'] > 0:
                    progress_pct = int((idx - start_row) / stats['total'] * 100)
                    self.progress_bar.setValue(progress_pct)
                
                progress_pct = int((idx - start_row) / stats['total'] * 100) if stats['total'] > 0 else 0
                self.status_bar.setText(f"⏳ Обробка {idx - start_row + 1}/{stats['total']} ({progress_pct}%)...")
                QApplication.processEvents()
                
                try:
                    address = self.file_manager.excel_handler.get_address_from_row(idx)
                    
                    if not address or not address.city:
                        stats['skipped'] += 1
                        continue
                    
                    # ✅ ПРАВИЛЬНИЙ ФОРМАТ
                    results = self.search_manager.search_with_auto(address, auto_apply=False)
                    
                    
                    if results['mode'] == 'auto' and results.get('auto_result'):
                        auto_result = results['auto_result']
                        auto_index = auto_result['index']
                        auto_confidence = auto_result.get('confidence', 0)
                        
                        # ✅ ПЕРЕВІРЯЄМО МІНІМАЛЬНУ ТОЧНІСТЬ
                        if auto_confidence >= min_confidence:
                            # Записуємо індекс напряму в DataFrame
                            mapping = self.file_manager.excel_handler.column_mapping
                            if mapping and 'index' in mapping:
                                idx_col = mapping['index'][0]
                                self.file_manager.excel_handler.df.iloc[idx, idx_col] = auto_index
                                
                                # Оновлюємо таблицю
                                item = self.table.item(idx, idx_col)
                                if item:
                                    item.setText(auto_index)
                                    item.setForeground(QColor(76, 175, 80))
                                    font = item.font()
                                    font.setBold(True)
                                    item.setFont(font)
                            
                            stats['auto_applied'] += 1
                            self.scroll_to_row(idx)
                            self.logger.info(f"✅ Рядок {idx + 1}: Автопідстановка [{auto_index}] - {auto_confidence}%")
                        else:
                            stats['manual_required'] += 1
                            self.logger.info(f"⚠️ Рядок {idx + 1}: Низька точність ({auto_confidence}% < {min_confidence}%)")
                    
                    elif results['mode'] == 'manual':
                        stats['manual_required'] += 1
                        self.logger.info(f"⚠️ Рядок {idx + 1}: Потребує ручного вибору ({len(results['manual_results'])} варіантів)")
                    
                    else:
                        stats['not_found'] += 1
                        self.logger.info(f"❌ Рядок {idx + 1}: Не знайдено")
                    
                except Exception as e:
                    self.logger.error(f"❌ Помилка рядка {idx + 1}: {str(e)}")
                    stats['errors'] += 1
            
            self._show_processing_statistics(stats)
            
        except Exception as e:
            self.logger.error(f"❌ Критична помилка: {str(e)}")
            QMessageBox.critical(self, "Помилка", f"Помилка обробки:\n{e}")
        
        finally:
            self.progress_bar.setVisible(False)
            self.auto_process_btn.setEnabled(True)
            self.semi_auto_btn.setEnabled(True)
            # ✅ НЕ вивантажуймо всю таблицю!
            # Лише оновлюємо розміри

    def scroll_to_row(self, row_idx: int):
        """Скролює таблицю до конкретного рядка"""
        if 0 <= row_idx < self.table.rowCount():
            # Скролює та центрує рядок на екрані
            self.table.scrollToItem(
                self.table.item(row_idx, 0),
                QAbstractItemView.PositionAtCenter
            )
            # Виділяємо рядок
            self.table.setCurrentCell(row_idx, 0)



    def _show_processing_statistics(self, stats: Dict):
        """Показує статистику обробки"""
        total_processed = stats['auto_applied'] + stats['manual_required'] + stats['not_found']
        efficiency = 0.0
        
        if total_processed > 0:
            efficiency = (stats['auto_applied'] / total_processed) * 100
        
        message = (
            f"📊 Обробка завершена!\n\n"
            f"Всього записів: {stats['total']}\n"
            f"✅ Автопідстановка: {stats['auto_applied']}\n"
            f"⚠️ Ручний вибір: {stats['manual_required']}\n"
            f"❌ Не знайдено: {stats['not_found']}\n"
            f"🔄 Пропущено: {stats['skipped']}\n"
            f"🔥 Помилки: {stats['errors']}\n\n"
            f"⏱️ Ефективність: {efficiency:.1f}%"
        )
        
        self.logger.info("=" * 80)
        self.logger.info(message.replace("\n", "\n   "))
        self.logger.info("=" * 80 + "\n")
        
        QMessageBox.information(self, "Обробка завершена", message)


    def update_progress(self, current: int, total: int):
        """Оновлює прогрес-бар"""
        progress = int(current / total * 100)
        self.progress_bar.setValue(progress)
        self.status_bar.setText(f"Обробка: {current} / {total}")
        QApplication.processEvents()

    def on_row_auto_processed(self, row_idx: int, index: str, mode: str):
        """Колбек після обробки рядка"""
        # Оновлюємо рядок в таблиці
        mapping = self.file_manager.excel_handler.column_mapping
        if mapping and 'index' in mapping:
            idx_col = mapping['index'][0]
            item = self.table.item(row_idx, idx_col)
            if item:
                item.setText(index)
                # Зелений колір для автопідстановки
                if mode == 'auto':
                    item.setForeground(QColor(76, 175, 80))
    
    def start_semi_auto_processing(self):
        """Напівавтоматична обробка"""
        if self.file_manager.excel_handler.df is None:
            QMessageBox.warning(self, "Помилка", "Файл не завантажено")
            return
        
        self.progress_bar.setVisible(True)
        self.semi_auto_btn.setEnabled(False)
        self.auto_process_btn.setEnabled(False)
        
        total_rows = len(self.file_manager.excel_handler.df)
        self.processing_manager.on_progress_update = self.update_progress
        self.processing_manager.on_row_processed = self.on_row_auto_processed
        self.processing_manager.on_semi_auto_pause = self.on_semi_auto_pause
        
        try:
            stats = self.processing_manager.start_semi_auto_processing(
                0, total_rows,
                search_func=lambda addr, auto: self.search_manager.search_with_auto(addr, auto_apply=True)
            )
            if not self.processing_manager.semi_auto_waiting:
                self.show_processing_stats(stats)
                self.progress_bar.setVisible(False)
                self.semi_auto_btn.setEnabled(True)
                self.auto_process_btn.setEnabled(True)
        except Exception as e:
            self.logger.error(f"Помилка: {e}")
            QMessageBox.critical(self, "Помилка", str(e))
            self.progress_bar.setVisible(False)
            self.semi_auto_btn.setEnabled(True)
            self.auto_process_btn.setEnabled(True)


    def on_semi_auto_pause(self, row_idx: int, results: List[Dict]):
        """
        Колбек коли напівавтоматична обробка зупинилась для ручного вибору
        """
        # Прокручуємо до рядка
        self.table.selectRow(row_idx)
        self.scroll_to_row(row_idx)
        self.current_row = row_idx
        
        # Показуємо результати для вибору
        if results:
            self.results_panel.display_results(results)
            self.status_bar.setText(
                f"⏸️  Обробка призупинена на рядку {row_idx + 1}. "
                f"Оберіть результат вручну або натисніть 'Продовжити'"
            )
        else:
            self.status_bar.setText(
                f"⏸️  Рядок {row_idx + 1}: нічого не знайдено. "
                f"Пропустіть або введіть вручну"
            )

    def continue_semi_auto(self):
        """Продовжує напівавтоматичну обробку після паузи"""
        stats = self.processing_manager.continue_semi_auto(
            search_func=lambda addr, auto: self.search_manager.search_with_auto(addr, auto_apply=True)
        )
        
        if not self.processing_manager.semi_auto_waiting:
            self.ui_state.set_processing_state(False)
            self.show_processing_stats(stats)
            self.progress_bar.setVisible(False)
            self.semi_auto_btn.setEnabled(True)
    
    def stop_processing(self):
        """Зупинка обробки"""
        self.processing_manager.stop_processing()
        self.logger.info("Обробку зупинено користувачем")
    
    def undo_action(self):
        """Відміна дії - повертає попередній індекс"""
        if not self.undo_manager.can_undo():
            return
        
        action = self.undo_manager.undo()
        if not action:
            return
        
        try:
            row_idx = action['row']
            old_values = action['old_values']
            
            # ✅ ЗАПИСУЄМО СТАРЕ ЗНАЧЕННЯ В DATAFRAME
            mapping = self.file_manager.excel_handler.column_mapping
            if 'index' in mapping:
                idx_col = mapping['index'][0]
                old_index = old_values.get('index', '')
                
                # ЗАПИСУЄМО СТАРИЙ ІНДЕКС В DATAFRAME
                self.file_manager.excel_handler.df.iloc[row_idx, idx_col] = old_index
                
                # ✅ ОНОВЛЮЄМО КЛІТИНКУ В ТАБЛИЦІ
                item = self.table.item(row_idx, idx_col)
                if item:
                    item.setText(old_index)
                    
                    # ✅ ВИДАЛЯЄМО ЗЕЛЕНИЙ КОЛІР (чорний текст)
                    item.setForeground(QColor(0, 0, 0))
                    font = item.font()
                    font.setBold(False)
                    item.setFont(font)
                
                # ✅ ВИДАЛЯЄМО ЗІ СПИСКУ АВТОПРОСТАВЛЕНИХ
                self.auto_applied_rows.discard(row_idx)
            
            self.logger.info(f"⤴️ UNDO: Рядок {row_idx + 1} - повернено індекс [{old_index}]")
            self.status_bar.setText(f"⤴️ Відмінено: було [{old_index}]")
            self.ui_state.undo_redo_changed.emit()
            
        except Exception as e:
            self.logger.error(f"❌ Помилка UNDO: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())


    def redo_action(self):
        """Повторення дії - повертає новий індекс"""
        if not self.undo_manager.can_redo():
            return
        
        action = self.undo_manager.redo()
        if not action:
            return
        
        try:
            row_idx = action['row']
            new_values = action['new_values']
            
            # ✅ ЗАПИСУЄМО НОВЕ ЗНАЧЕННЯ В DATAFRAME
            mapping = self.file_manager.excel_handler.column_mapping
            if 'index' in mapping:
                idx_col = mapping['index'][0]
                new_index = new_values.get('index', '')
                
                # ЗАПИСУЄМО НОВИЙ ІНДЕКС В DATAFRAME
                self.file_manager.excel_handler.df.iloc[row_idx, idx_col] = new_index
                
                # ✅ ОНОВЛЮЄМО КЛІТИНКУ В ТАБЛИЦІ
                item = self.table.item(row_idx, idx_col)
                if item:
                    item.setText(new_index)
                    
                    # ✅ ВСТАНОВЛЮЄМО ЗЕЛЕНИЙ КОЛІР
                    item.setForeground(QColor(76, 175, 80))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                
                # ✅ ДОДАЄМО ДО СПИСКУ АВТОПРОСТАВЛЕНИХ
                self.auto_applied_rows.add(row_idx)
            
            self.logger.info(f"⤵️ REDO: Рядок {row_idx + 1} - повернено індекс [{new_index}]")
            self.status_bar.setText(f"⤵️ Повторено: було [{new_index}]")
            self.ui_state.undo_redo_changed.emit()
            
        except Exception as e:
            self.logger.error(f"❌ Помилка REDO: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())

    
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
                records = self.search_manager.get_magistral_records()
                if records and self.address_panel:
                    self.address_panel.set_magistral_cache(records)
                
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
            
    def _continue_semi_auto(self):
        """Продовжує напівавтоматичну обробку після паузи"""
        stats = self.processing_manager.continue_semi_auto(
            search_func=lambda addr, auto: self.search_manager.search_with_auto(addr, auto_apply=True)
        )
        
        if not self.processing_manager.semi_auto_waiting:
            self._show_processing_statistics(stats)
            self.progress_bar.setVisible(False)
            self.semi_auto_btn.setEnabled(True)
            self.auto_process_btn.setEnabled(True)

    
    def set_index_star(self):
        """Встановлює індекс *"""
        if self.current_row >= 0:
            self.apply_index("*")
    
    # ==================== РОБОТА З ТАБЛИЦЕЮ ====================
    
    def _display_table(self):
        """Відображає дані в таблиці"""
        df = self.file_manager.excel_handler.df
        self.df = df  # Зберігаємо посилання
        
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
            
            # ✅ ДОДАНО: ЗАПОВНЮЄМО ФОРМУ РУЧНОГО ВВЕДЕННЯ
            self.address_panel.region_input.setText(address.region or '')
            self.address_panel.city_input.setText(address.city or '')
            self.address_panel.street_input.setText(address.street or '')
            self.address_panel.index_input.setText(address.index or '')
            
            # ОЧИЩУЄМО БУДИНКИ
            self.address_panel.buildings_combo.clear()
            self.address_panel.buildings_combo.hide()
            self.address_panel.buildings_label.hide()
            
            self.logger.info(f"📋 Форма заповнена для рядка {self.current_row + 1}")
            
        except Exception as e:
            self.logger.error(f"Помилка відображення даних: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
        
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
            
            
    def on_semi_auto_pause(self, row_idx: int, results: List[Dict]):
        """Пауза напівавто"""
        self.current_row = row_idx
        self.table.selectRow(row_idx)
        self.scroll_to_row(row_idx)
        
        if results:
            self.results_panel.display_results(results, highlight_first=False)
            self.status_bar.setText(f"⏸️ Рядок {row_idx + 1} - оберіть результат")
        else:
            self.results_panel.clear()
            self.status_bar.setText(f"⏸️ Рядок {row_idx + 1}: нічого не знайдено")

    def show_processing_stats(self, stats: Dict):
        """Показує статистику"""
        total = stats['total'] - stats['skipped']
        eff = round(stats['auto_applied'] / max(total, 1) * 100, 1)
        
        msg = (
            f"Обробка завершена!\\n\\n"
            f"Всього: {stats['total']}\\n"
            f"✅ Автопідстановка: {stats['auto_applied']}\\n"
            f"⚠️ Ручний вибір: {stats['manual_required']}\\n"
            f"❌ Не знайдено: {stats['not_found']}\\n"
            f"⏭️ Пропущено: {stats['skipped']}\\n"
            f"🔥 Помилки: {stats['errors']}\\n\\n"
            f"Ефективність: {eff}%"
        )
        QMessageBox.information(self, "Статистика", msg)

    def update_progress(self, current: int, total: int):
        """Оновити прогрес"""
        if total > 0:
            self.progress_bar.setValue(int(current / total * 100))
        self.status_bar.setText(f"⏳ {current} / {total}")
        QApplication.processEvents()

    def on_row_auto_processed(self, row_idx: int, index: str, mode: str):
        """Колбек після обробки"""
        mapping = self.file_manager.excel_handler.column_mapping
        if mapping and 'index' in mapping:
            idx_col = mapping['index'][0]
            item = self.table.item(row_idx, idx_col)
            if item:
                item.setText(index)
                if mode == 'auto':
                    item.setForeground(QColor(76, 175, 80))

    
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