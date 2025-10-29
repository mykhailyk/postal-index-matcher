"""
Приклад рефакторингу MainWindow з використанням менеджерів

Це демонстрація того, як MainWindow може виглядати після рефакторингу.
Основна ідея: MainWindow стає координатором, який делегує роботу менеджерам.
"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QTableWidget, QProgressBar, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from ui.managers import FileManager, SearchManager, ProcessingManager, UIStateManager
from ui.styles import AppStyles
from ui.widgets.column_mapping_dialog import ColumnMappingDialog
from ui.widgets.address_selector_panel import AddressSelectorPanel
from ui.widgets.results_panel import ResultsPanel
from ui.widgets.auto_processing_dialog import AutoProcessingDialog
from utils.undo_manager import UndoManager
from utils.settings_manager import SettingsManager
import config


class MainWindowRefactored(QMainWindow):
    """
    Рефакторована версія головного вікна
    
    Ключові зміни:
    - Використання менеджерів замість прямої логіки
    - Централізовані стилі через AppStyles
    - Чіткі відповідальності
    - Менше коду у вікні (координація замість імплементації)
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
        
        # Поточний стан
        self.current_row = -1
        self.search_results = []
        
        # Віджети (буде ініціалізовано в init_ui)
        self.table = None
        self.progress_bar = None
        self.status_bar = None
        self.results_panel = None
        self.address_panel = None
        
        # UI
        self._init_ui()
        self._connect_signals()
        self._setup_callbacks()
        
    def _init_ui(self):
        """Ініціалізація UI"""
        self.setWindowTitle(config.WINDOW_TITLE)
        
        # Відновлюємо геометрію вікна
        geometry = SettingsManager.get_window_geometry()
        if geometry:
            self.setGeometry(geometry['x'], geometry['y'], geometry['width'], geometry['height'])
        else:
            self.setGeometry(100, 50, config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        
        # Створюємо центральний віджет
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
        main_layout.addWidget(main_splitter)
        
        # Статус бар
        self.status_bar = QLabel("Готово до роботи")
        self.status_bar.setStyleSheet(AppStyles.status_bar())
        main_layout.addWidget(self.status_bar)
        
        # Прогрес бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet(AppStyles.progress_bar())
        main_layout.addWidget(self.progress_bar)
    
    def _create_top_panel(self):
        """Створює верхню панель з кнопками"""
        panel = QWidget()
        layout = QHBoxLayout()
        layout.setSpacing(5)
        
        # Мітка файлу
        self.file_label = QLabel("Не завантажено")
        self.file_label.setStyleSheet(AppStyles.file_label())
        layout.addWidget(self.file_label)
        
        # Кнопки
        self.load_btn = QPushButton("Відкрити файл")
        self.load_btn.setStyleSheet(AppStyles.button_default())
        self.load_btn.clicked.connect(self.load_file)
        layout.addWidget(self.load_btn)
        
        self.column_mapping_btn = QPushButton("⚙ Налаштувати стовпці")
        self.column_mapping_btn.setEnabled(False)
        self.column_mapping_btn.setStyleSheet(AppStyles.button_default())
        self.column_mapping_btn.clicked.connect(self.configure_columns)
        layout.addWidget(self.column_mapping_btn)
        
        self.save_btn = QPushButton("💾 Зберегти")
        self.save_btn.setEnabled(False)
        self.save_btn.setStyleSheet(AppStyles.button_success())
        self.save_btn.clicked.connect(self.save_file)
        layout.addWidget(self.save_btn)
        
        self.search_btn = QPushButton("🔍 Знайти")
        self.search_btn.setEnabled(False)
        self.search_btn.setStyleSheet(AppStyles.button_primary())
        self.search_btn.clicked.connect(self.search_address)
        layout.addWidget(self.search_btn)
        
        self.auto_process_btn = QPushButton("⚡ Автоматична")
        self.auto_process_btn.setEnabled(False)
        self.auto_process_btn.setStyleSheet(AppStyles.button_warning())
        self.auto_process_btn.clicked.connect(self.start_auto_processing)
        layout.addWidget(self.auto_process_btn)
        
        layout.addStretch()
        
        panel.setLayout(layout)
        return panel
    
    def _create_table_panel(self):
        """Створює панель з таблицею"""
        panel = QWidget()
        layout = QVBoxLayout()
        
        # Заголовок
        header = QLabel("📋 База даних")
        header.setStyleSheet(AppStyles.panel_header())
        layout.addWidget(header)
        
        # Таблиця
        self.table = QTableWidget()
        self.table.setStyleSheet(AppStyles.table_main())
        self.table.itemSelectionChanged.connect(self.on_row_selected)
        layout.addWidget(self.table)
        
        panel.setLayout(layout)
        return panel
    
    def _create_right_panel(self):
        """Створює праву панель"""
        panel = QSplitter(Qt.Vertical)
        
        # Панель підбору адреси
        self.address_panel = AddressSelectorPanel()
        self.address_panel.index_double_clicked.connect(self.apply_index)
        
        # Панель результатів
        self.results_panel = ResultsPanel()
        self.results_panel.index_selected.connect(self.apply_index)
        self.results_panel.search_requested.connect(self.search_address)
        
        panel.addWidget(self.address_panel)
        panel.addWidget(self.results_panel)
        
        panel.setSizes([220, 480])
        
        return panel
    
    def _connect_signals(self):
        """Підключає сигнали від менеджерів"""
        # Сигнали від UIStateManager
        self.ui_state.file_loaded.connect(self._on_file_loaded_signal)
        self.ui_state.processing_started.connect(self._on_processing_started_signal)
        self.ui_state.processing_finished.connect(self._on_processing_finished_signal)
    
    def _setup_callbacks(self):
        """Налаштовує колбеки для ProcessingManager"""
        self.processing_manager.on_progress_update = self._on_progress_update
        self.processing_manager.on_row_processed = self._on_row_processed
    
    # ==================== ОБРОБНИКИ СИГНАЛІВ ====================
    
    def _on_file_loaded_signal(self, file_path: str):
        """Обробка сигналу завантаження файлу"""
        self.file_label.setText(file_path.split('/')[-1])
        
        # Активуємо кнопки
        buttons = {
            'column_mapping': self.column_mapping_btn,
            'save': self.save_btn,
            'search': self.search_btn,
            'auto_process': self.auto_process_btn
        }
        self.ui_state.enable_buttons_for_file_loaded(buttons)
        
        # Оновлюємо magistral cache
        magistral_records = self.search_manager.get_magistral_records()
        if self.address_panel:
            self.address_panel.set_magistral_cache(magistral_records)
    
    def _on_processing_started_signal(self):
        """Обробка початку обробки"""
        self.progress_bar.setVisible(True)
        
        buttons = {
            'search': self.search_btn,
            'auto_process': self.auto_process_btn,
            'column_mapping': self.column_mapping_btn,
            'save': self.save_btn
        }
        self.ui_state.disable_buttons_for_processing(buttons)
    
    def _on_processing_finished_signal(self):
        """Обробка завершення обробки"""
        self.progress_bar.setVisible(False)
        
        buttons = {
            'search': self.search_btn,
            'auto_process': self.auto_process_btn,
            'column_mapping': self.column_mapping_btn,
            'save': self.save_btn
        }
        self.ui_state.enable_buttons_after_processing(buttons)
    
    def _on_progress_update(self, current: int, total: int):
        """Колбек оновлення прогресу"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        
        percent = int((current / total) * 100)
        self.status_bar.setText(f"⏳ Обробка {current}/{total} ({percent}%)...")
    
    def _on_row_processed(self, row_idx: int, index: str):
        """Колбек обробки рядка"""
        # Оновлюємо комірку в таблиці
        mapping = self.file_manager.excel_handler.column_mapping
        if mapping and 'index' in mapping:
            idx_col = mapping['index'][0]
            item = self.table.item(row_idx, idx_col)
            if item:
                item.setText(index)
                item.setForeground(QColor(AppStyles.Colors.INDEX_APPLIED))
    
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
        success = self.file_manager.save_file(
            save_old_index=False,
            parent=self
        )
        
        if success:
            self.ui_state.set_file_saved()
            self.status_bar.setText("✅ Файл збережено")
            QMessageBox.information(self, "Успіх", "Файл успішно збережено!")
        else:
            QMessageBox.critical(self, "Помилка", "Не вдалося зберегти файл")
    
    def configure_columns(self):
        """Налаштування відповідності стовпців"""
        if not self.file_manager.excel_handler.df.empty:
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
        if self.current_row < 0:
            QMessageBox.warning(self, "Увага", "Оберіть рядок для пошуку")
            return
        
        try:
            # Отримуємо адресу з поточного рядка
            address = self.file_manager.excel_handler.get_address_from_row(self.current_row)
            
            # Виконуємо пошук через SearchManager
            results = self.search_manager.search(address, max_results=20)
            
            # Відображаємо результати
            self.results_panel.show_results(results, address.building or "")
            
            if results:
                self.address_panel.populate_from_results(results)
            
            self.status_bar.setText(f"✅ Знайдено {len(results)} варіантів")
            
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Помилка пошуку:\n{e}")
            self.status_bar.setText("❌ Помилка пошуку")
    
    def apply_index(self, index: str):
        """Застосування індексу через ProcessingManager"""
        if self.current_row < 0:
            return
        
        success = self.processing_manager.apply_index(self.current_row, index)
        
        if success:
            # Оновлюємо таблицю
            mapping = self.file_manager.excel_handler.column_mapping
            if mapping and 'index' in mapping:
                idx_col = mapping['index'][0]
                item = self.table.item(self.current_row, idx_col)
                if item:
                    item.setText(index)
                    color = self.ui_state.get_index_color_for_state(is_applied=True)
                    item.setForeground(color)
            
            # Логуємо
            address = self.file_manager.excel_handler.get_address_from_row(self.current_row)
            self.search_manager.log_index_applied(self.current_row, address, index)
            
            self.status_bar.setText(f"✅ Застосовано індекс {index}")
            
            # Переходимо на наступний рядок
            if self.current_row + 1 < self.table.rowCount():
                self.table.selectRow(self.current_row + 1)
    
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
            
            # Запускаємо обробку
            stats = self.processing_manager.start_auto_processing(
                start_row=self.current_row,
                total_rows=len(self.file_manager.excel_handler.df),
                min_confidence=min_confidence,
                search_func=lambda addr: self.search_manager.search(addr)
            )
            
            # Завершуємо обробку
            self.ui_state.set_processing_state(False)
            
            self.status_bar.setText(
                f"✅ Оброблено: {stats['processed']}, Пропущено: {stats['skipped']}"
            )
            
            QMessageBox.information(
                self,
                "Завершено",
                f"Обробка завершена!\n\nОброблено: {stats['processed']}\nПропущено: {stats['skipped']}"
            )
    
    def on_row_selected(self):
        """Обробка вибору рядка"""
        selected_rows = self.table.selectionModel().selectedRows()
        
        if not selected_rows:
            return
        
        self.current_row = selected_rows[0].row()
        self.ui_state.set_current_row(self.current_row)
        self.results_panel.clear()
        
        # Автоматичний пошук
        self.search_address()
    
    def _display_table(self):
        """Відображає дані в таблиці"""
        df = self.file_manager.excel_handler.df
        
        if df is None or df.empty:
            return
        
        self.table.setRowCount(len(df))
        self.table.setColumnCount(len(df.columns))
        self.table.setHorizontalHeaderLabels(df.columns.tolist())
        
        # Заповнюємо таблицю
        for i in range(len(df)):
            for j in range(len(df.columns)):
                from PyQt5.QtWidgets import QTableWidgetItem
                value = df.iloc[i, j]
                item = QTableWidgetItem(str(value) if not pd.isna(value) else "")
                self.table.setItem(i, j, item)
    
    def closeEvent(self, event):
        """Збереження стану при закритті"""
        geometry = self.geometry()
        SettingsManager.set_window_geometry(
            geometry.x(), geometry.y(),
            geometry.width(), geometry.height()
        )
        event.accept()
