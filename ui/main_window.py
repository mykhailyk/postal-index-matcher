"""
Головне вікно програми - оптимізована версія
"""
import os
import re
import pandas as pd
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem, QFileDialog,
    QMessageBox, QToolBar, QAction, QProgressBar, QHeaderView,
    QAbstractItemView, QFrame, QComboBox, QShortcut, QApplication
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QKeySequence

from handlers.excel_handler import ExcelHandler
from handlers.column_mapping_handler import ColumnMappingHandler
from search.hybrid_search import HybridSearch
from models.address import Address
from utils.logger import Logger
from utils.undo_manager import UndoManager
from utils.settings_manager import SettingsManager
from ui.widgets.column_mapping_dialog import ColumnMappingDialog
from ui.widgets.address_selector_panel import AddressSelectorPanel
from ui.widgets.results_panel import ResultsPanel
import config


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.logger = Logger()
        self.excel_handler = ExcelHandler()
        self.undo_manager = UndoManager()
        self.search_engine = None

        self.current_file = None
        self.current_row = -1
        self.search_results = []

        self.processing_stopped = False
        self.semi_auto_waiting = False
        self.semi_auto_current_row = -1
        self.semi_auto_min_confidence = 90

        self.init_ui()
        self.init_search_engine()

    def init_ui(self):
        self.setWindowTitle(config.WINDOW_TITLE)

        geometry = SettingsManager.get_window_geometry()
        if geometry:
            self.setGeometry(geometry['x'], geometry['y'], geometry['width'], geometry['height'])
        else:
            self.setGeometry(100, 50, config.WINDOW_WIDTH, config.WINDOW_HEIGHT)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()
        main_layout.setSpacing(3)
        main_layout.setContentsMargins(5, 5, 5, 5)
        central_widget.setLayout(main_layout)

        top_panel = self.create_compact_top_panel()
        main_layout.addWidget(top_panel)

        main_splitter = QSplitter(Qt.Horizontal)

        left_panel = self.create_table_panel()
        main_splitter.addWidget(left_panel)

        right_panel = self.create_compact_right_panel()
        main_splitter.addWidget(right_panel)

        main_splitter.setSizes([1100, 600])
        main_layout.addWidget(main_splitter)

        self.create_status_bar()
        main_layout.addWidget(self.status_bar)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumHeight(15)
        main_layout.addWidget(self.progress_bar)

        self.setup_shortcuts()

    def create_compact_top_panel(self):
        """Компактна панель управління"""
        panel = QFrame()
        panel.setMaximumHeight(100)
        layout = QVBoxLayout()
        layout.setSpacing(3)
        layout.setContentsMargins(2, 2, 2, 2)

        row1 = QHBoxLayout()

        file_label = QLabel("📁")
        file_label.setStyleSheet("font-size: 14px;")
        row1.addWidget(file_label)

        self.file_label = QLabel("Не завантажено")
        self.file_label.setStyleSheet("padding: 3px; background-color: #f0f0f0; border-radius: 2px; font-size: 11px;")
        row1.addWidget(self.file_label, 1)

        load_btn = QPushButton("Відкрити файл")
        load_btn.clicked.connect(self.load_excel_file)
        load_btn.setStyleSheet("padding: 4px 10px; font-size: 11px;")
        row1.addWidget(load_btn)

        self.column_mapping_btn = QPushButton("⚙ Налаштувати стовпці")
        self.column_mapping_btn.setEnabled(False)
        self.column_mapping_btn.clicked.connect(self.configure_columns)
        self.column_mapping_btn.setStyleSheet("padding: 4px 10px; font-size: 11px;")
        row1.addWidget(self.column_mapping_btn)

        self.save_btn = QPushButton("💾 Зберегти")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save_excel_file)
        self.save_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 4px 10px; font-size: 11px;")
        row1.addWidget(self.save_btn)

        stats_btn = QPushButton("📊 Статистика")
        stats_btn.clicked.connect(self.show_statistics)
        stats_btn.setStyleSheet("padding: 4px 10px; font-size: 11px;")
        row1.addWidget(stats_btn)

        layout.addLayout(row1)

        row2 = QHBoxLayout()

        self.undo_btn = QPushButton("⬅ Назад")
        self.undo_btn.setShortcut(QKeySequence.Undo)
        self.undo_btn.clicked.connect(self.undo)
        self.undo_btn.setEnabled(False)
        self.undo_btn.setStyleSheet("padding: 4px 10px; font-size: 11px;")
        row2.addWidget(self.undo_btn)

        self.redo_btn = QPushButton("➡ Вперед")
        self.redo_btn.setShortcut(QKeySequence.Redo)
        self.redo_btn.clicked.connect(self.redo)
        self.redo_btn.setEnabled(False)
        self.redo_btn.setStyleSheet("padding: 4px 10px; font-size: 11px;")
        row2.addWidget(self.redo_btn)

        row2.addSpacing(20)

        filter_label = QLabel("Фільтр:")
        filter_label.setStyleSheet("font-size: 11px;")
        row2.addWidget(filter_label)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Всі рядки", "Тільки оброблені", "Тільки необроблені"])
        self.filter_combo.setStyleSheet("font-size: 11px;")
        self.filter_combo.currentTextChanged.connect(self.apply_filter)
        row2.addWidget(self.filter_combo)

        row2.addStretch()

        layout.addLayout(row2)

        panel.setLayout(layout)
        return panel

    def create_table_panel(self):
        """Панель з таблицею"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(3)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()

        label = QLabel("📋 База даних")
        label.setStyleSheet("font-weight: bold; font-size: 13px;")
        header.addWidget(label)

        header.addStretch()

        self.search_btn = QPushButton("🔍 Знайти (Enter)")
        self.search_btn.setEnabled(False)
        self.search_btn.clicked.connect(self.search_address)
        self.search_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 6px 15px; font-weight: bold; font-size: 11px;")
        header.addWidget(self.search_btn)

        self.auto_process_btn = QPushButton("⚡ Автоматична")
        self.auto_process_btn.setEnabled(False)
        self.auto_process_btn.clicked.connect(self.start_auto_processing)
        self.auto_process_btn.setStyleSheet("background-color: #FF9800; color: white; padding: 6px 12px; font-size: 11px;")
        header.addWidget(self.auto_process_btn)

        self.semi_auto_btn = QPushButton("🔄 Напів-авто")
        self.semi_auto_btn.setEnabled(False)
        self.semi_auto_btn.clicked.connect(self.start_semi_auto_processing)
        self.semi_auto_btn.setStyleSheet("background-color: #9C27B0; color: white; padding: 6px 12px; font-size: 11px;")
        header.addWidget(self.semi_auto_btn)

        layout.addLayout(header)

        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.itemChanged.connect(self.on_cell_edited)
        self.table.itemSelectionChanged.connect(self.on_row_selected)
        layout.addWidget(self.table)

        self.original_data_label = QLabel("Оберіть рядок для перегляду даних")
        self.original_data_label.setStyleSheet(
            "padding: 5px; background-color: #FFF3E0; border: 1px solid #FFB74D; "
            "border-radius: 3px; font-family: 'Courier New'; font-size: 10px;"
        )
        self.original_data_label.setWordWrap(True)
        self.original_data_label.setMaximumHeight(60)
        layout.addWidget(self.original_data_label)

        panel.setLayout(layout)
        return panel

    def create_compact_right_panel(self):
        """Компактна права панель"""
        panel = QSplitter(Qt.Vertical)

        self.address_panel = AddressSelectorPanel()
        self.address_panel.index_double_clicked.connect(self.apply_suggested_index)
        self.address_panel.setMaximumHeight(320)
        panel.addWidget(self.address_panel)

        self.results_panel = ResultsPanel()
        self.results_panel.apply_index_clicked.connect(self.apply_selected_index)
        self.results_panel.fix_address_clicked.connect(self.fix_address)
        panel.addWidget(self.results_panel)

        sizes = SettingsManager.get_splitter_sizes('right_panel')
        if sizes:
            panel.setSizes(sizes)
        else:
            panel.setSizes([220, 480])

        return panel

    def create_status_bar(self):
        self.status_bar = QLabel("Готово до роботи")
        self.status_bar.setStyleSheet(
            "padding: 5px; background-color: #E8F5E9; "
            "border-top: 1px solid #4CAF50; font-size: 10px;"
        )
        self.status_bar.setMaximumHeight(25)

    def setup_shortcuts(self):
        search_shortcut = QShortcut(QKeySequence(Qt.Key_Return), self)
        search_shortcut.activated.connect(self.search_address)

        star_shortcut = QShortcut(QKeySequence("*"), self)
        star_shortcut.activated.connect(self.set_index_star)

    def init_search_engine(self):
        self.logger.info("Ініціалізація пошукового движка...")
        self.status_bar.setText("⏳ Завантаження magistral.csv...")

        try:
            self.search_engine = HybridSearch()
            self.address_panel.set_magistral_cache(self.search_engine.magistral_records)
            self.status_bar.setText("✅ Пошуковий движок готовий")
            self.logger.info("Пошуковий движок ініціалізовано")
        except Exception as e:
            self.logger.error(f"Помилка ініціалізації пошуку: {e}")
            QMessageBox.critical(self, "Помилка", f"Не вдалося завантажити magistral.csv:\n{e}")
    def load_excel_file(self):
        last_path = SettingsManager.get_last_file_path()
        start_dir = os.path.dirname(last_path) if last_path and os.path.exists(last_path) else ""

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Виберіть Excel файл",
            start_dir,
            "Excel Files (*.xlsx *.xls)"
        )

        if not file_path:
            return

        try:
            self.status_bar.setText("⏳ Завантаження файлу...")
            df = self.excel_handler.load_file(file_path)

            self.current_file = file_path
            self.file_label.setText(os.path.basename(file_path))

            SettingsManager.set_last_file_path(file_path)

            # ДОДАЄМО ВІРТУАЛЬНУ КОЛОНКУ "Старий індекс"
            self.add_virtual_old_index_column()

            self.display_table(self.excel_handler.df)

            self.column_mapping_btn.setEnabled(True)
            self.save_btn.setEnabled(True)
            self.auto_process_btn.setEnabled(True)
            self.semi_auto_btn.setEnabled(True)

            self.status_bar.setText(f"✅ Завантажено {len(df)} рядків")

        except Exception as e:
            self.logger.error(f"Помилка завантаження файлу: {e}")
            QMessageBox.critical(self, "Помилка", f"Не вдалося завантажити:\n{e}")

    def add_virtual_old_index_column(self):
        """Додає віртуальну колонку 'Старий індекс' в кінець DataFrame"""
        if 'Старий індекс' not in self.excel_handler.df.columns:
            self.excel_handler.df['Старий індекс'] = ''
            self.logger.info("✅ Додано віртуальну колонку 'Старий індекс'")

    def save_excel_file(self):
        if not self.current_file:
            self.save_excel_file_as()
            return

        try:
            # Зберігаємо БЕЗ віртуальної колонки "Старий індекс"
            df_to_save = self.excel_handler.df.copy()
            
            if 'Старий індекс' in df_to_save.columns:
                df_to_save = df_to_save.drop(columns=['Старий індекс'])
                self.logger.info("Видалено віртуальну колонку 'Старий індекс' перед збереженням")
            
            df_to_save.to_excel(self.current_file, index=False)
            self.status_bar.setText("✅ Файл збережено")
            QMessageBox.information(self, "Успіх", "Файл успішно збережено!")
        except Exception as e:
            self.logger.error(f"Помилка збереження: {e}")
            QMessageBox.critical(self, "Помилка", f"Не вдалося зберегти:\n{e}")

    def save_excel_file_as(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Зберегти як",
            "",
            "Excel Files (*.xlsx)"
        )

        if file_path:
            try:
                df_to_save = self.excel_handler.df.copy()
                
                if 'Старий індекс' in df_to_save.columns:
                    df_to_save = df_to_save.drop(columns=['Старий індекс'])
                
                df_to_save.to_excel(file_path, index=False)
                self.current_file = file_path
                self.file_label.setText(os.path.basename(file_path))
                self.status_bar.setText("✅ Файл збережено")
            except Exception as e:
                QMessageBox.critical(self, "Помилка", f"Не вдалося зберегти:\n{e}")

    def display_table(self, df):
        self.table.blockSignals(True)

        self.table.setRowCount(len(df))
        self.table.setColumnCount(len(df.columns))

        header_labels = []
        for i, db_col in enumerate(df.columns):
            our_name = self.get_our_field_name_for_column(i)
            if our_name:
                header_labels.append(f"{our_name}\n({db_col})")
            else:
                header_labels.append(str(db_col))

        self.table.setHorizontalHeaderLabels(header_labels)

        for i in range(len(df)):
            for j in range(len(df.columns)):
                value = df.iloc[i, j]
                item = QTableWidgetItem(str(value) if pd.notna(value) else "")
                
                # Робимо "Старий індекс" тільки для читання
                if j == len(df.columns) - 1 and df.columns[j] == 'Старий індекс':
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    item.setBackground(QColor(240, 240, 240))
                
                self.table.setItem(i, j, item)

        saved_widths = SettingsManager.get_column_widths()
        if saved_widths and len(saved_widths) == len(df.columns):
            for i, width in enumerate(saved_widths):
                self.table.setColumnWidth(i, width)
        else:
            self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
            self.table.resizeColumnsToContents()

        self.table.blockSignals(False)

    def get_our_field_name_for_column(self, col_idx):
        """Повертає назву поля для відображення в заголовку колонки"""
        
        # Перевіряємо чи це остання колонка і чи це "Старий індекс"
        if self.excel_handler.df is not None:
            if col_idx == len(self.excel_handler.df.columns) - 1:
                if self.excel_handler.df.columns[col_idx] == 'Старий індекс':
                    return 'Ст.Інд.(поч.)'
        
        # Словник назв полів
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

        mapping = self.excel_handler.column_mapping
        if not mapping:
            return None

        # Шукаємо поле за індексом колонки
        for field_id, col_indices in mapping.items():
            if col_idx in col_indices:
                return field_names.get(field_id, field_id)

        return None

    def on_row_selected(self):
        selected_rows = self.table.selectionModel().selectedRows()

        if not selected_rows:
            self.search_btn.setEnabled(False)
            return

        self.current_row = selected_rows[0].row()
        self.search_btn.setEnabled(True)
        
        # ОЧИЩАЄМО ПОПЕРЕДНІ РЕЗУЛЬТАТИ
        self.results_panel.clear_results()

        try:
            address = self.excel_handler.get_address_from_row(self.current_row)

            parts = []
            if address.region:
                parts.append(f"Обл: {address.region}")
            if address.district:
                parts.append(f"Р-н: {address.district}")
            if address.city:
                parts.append(f"Місто: {address.city}")
            if address.street:
                parts.append(f"Вул: {address.street}")
            if address.building:
                parts.append(f"Буд: {address.building}")

            text = " | ".join(parts) if parts else "Немає даних"
            self.original_data_label.setText(f"📍 {text}")

        except Exception as e:
            self.logger.error(f"Помилка отримання даних: {e}")

    def on_cell_edited(self, item):
        if not item:
            return

        row = item.row()
        col = item.column()
        new_value = item.text()

        self.excel_handler.df.iloc[row, col] = new_value
        self.logger.debug(f"Відредаговано комірку [{row}, {col}]: {new_value}")
    def search_address(self):
        if self.current_row < 0:
            QMessageBox.warning(self, "Увага", "Оберіть рядок для пошуку")
            return

        if not self.search_engine:
            QMessageBox.critical(self, "Помилка", "Пошуковий движок не ініціалізовано")
            return

        try:
            self.status_bar.setText("🔍 Пошук...")

            address = self.excel_handler.get_address_from_row(self.current_row)

            self.log_search_request(address)
            results = self.search_engine.search(address, max_results=20)
            self.log_search_results(address, results)

            self.search_results = results

            self.results_panel.show_results(results, address.building or "")

            if results:
                self.address_panel.populate_from_results(results)

            self.status_bar.setText(f"✅ Знайдено {len(results)} варіантів")

        except Exception as e:
            self.logger.error(f"Помилка пошуку: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Помилка", f"Помилка пошуку:\n{e}")
            self.status_bar.setText("❌ Помилка пошуку")

    def log_search_request(self, address):
        import json
        from datetime import datetime

        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': 'search_request',
            'address': address.to_dict()
        }

        search_log_path = os.path.join(config.LOGS_DIR, 'search_queries.jsonl')
        with open(search_log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

    def log_search_results(self, address, results):
        import json
        from datetime import datetime

        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': 'search_results',
            'query': address.to_dict(),
            'results_count': len(results),
            'all_results': [
                {
                    'city': r.get('city'),
                    'district': r.get('district'),
                    'region': r.get('region'),
                    'street': r.get('street'),
                    'index': r.get('index'),
                    'confidence': r.get('confidence'),
                    'buildings': r.get('buildings', ''),
                    'not_working': r.get('not_working', '')
                }
                for r in results
            ]
        }

        search_log_path = os.path.join(config.LOGS_DIR, 'search_queries.jsonl')
        with open(search_log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

    def log_index_applied(self, row_idx, address, index_value):
        """Логування застосованого індексу"""
        import json
        from datetime import datetime

        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': 'index_applied',
            'row': row_idx,
            'address': address.to_dict(),
            'applied_index': index_value
        }

        search_log_path = os.path.join(config.LOGS_DIR, 'search_queries.jsonl')
        with open(search_log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

    def apply_suggested_index(self, index: str):
        if self.current_row < 0:
            return

        try:
            address = self.excel_handler.get_address_from_row(self.current_row)
            
            self.excel_handler.update_row(self.current_row, {'index': index})

            self.log_index_applied(self.current_row, address, index)

            mapping = self.excel_handler.column_mapping
            if mapping and 'index' in mapping:
                for col_idx in mapping['index']:
                    item = self.table.item(self.current_row, col_idx)
                    if item:
                        item.setText(index)

            for col in range(self.table.columnCount()):
                item = self.table.item(self.current_row, col)
                if item:
                    item.setBackground(QColor(config.COLOR_PROCESSED))

            self.status_bar.setText(f"✅ Застосовано індекс {index}")
            
            # ЯКЩО НАПІВАВТОМАТИЧНИЙ РЕЖИМ - ПРОДОВЖУЄМО
            if self.semi_auto_waiting:
                self.semi_auto_waiting = False
                QApplication.processEvents()
                self.continue_semi_auto_processing()

        except Exception as e:
            self.logger.error(f"Помилка застосування індексу: {e}")
            QMessageBox.critical(self, "Помилка", f"Не вдалося застосувати:\n{e}")

    def apply_selected_index(self, result):
        if self.current_row < 0:
            return

        index = result.get('index', '')
        self.apply_suggested_index(index)

    def fix_address(self, result):
        if self.current_row < 0:
            return

        try:
            address = self.excel_handler.get_address_from_row(self.current_row)
            updates = {}

            for field in ['region', 'district', 'city', 'street']:
                if result.get(field):
                    updates[field] = result[field]

            if result.get('index'):
                updates['index'] = result['index']

            self.excel_handler.update_row(self.current_row, updates)

            self.log_index_applied(self.current_row, address, result.get('index', ''))

            mapping = self.excel_handler.column_mapping
            if mapping:
                for field, value in updates.items():
                    if field in mapping:
                        for col_idx in mapping[field]:
                            item = self.table.item(self.current_row, col_idx)
                            if item:
                                item.setText(value)

            for col in range(self.table.columnCount()):
                item = self.table.item(self.current_row, col)
                if item:
                    item.setBackground(QColor(config.COLOR_PROCESSED))

            self.status_bar.setText(f"✅ Адресу виправлено")

        except Exception as e:
            self.logger.error(f"Помилка виправлення: {e}")
            QMessageBox.critical(self, "Помилка", f"Не вдалося виправити:\n{e}")

    def apply_filter(self, filter_text):
        if self.excel_handler.df is None:
            return

        for row in range(self.table.rowCount()):
            is_processed = self.is_row_processed(row)

            if filter_text == "Всі рядки":
                self.table.setRowHidden(row, False)
            elif filter_text == "Тільки оброблені":
                self.table.setRowHidden(row, not is_processed)
            elif filter_text == "Тільки необроблені":
                self.table.setRowHidden(row, is_processed)

    def is_row_processed(self, row):
        item = self.table.item(row, 0)
        if item:
            bg_color = item.background().color()
            return bg_color == QColor(config.COLOR_PROCESSED)
        return False
    def configure_columns(self):
        if self.excel_handler.df is None:
            return

        df_sample = self.excel_handler.df.head(10)
        current_mapping = self.excel_handler.column_mapping or {}

        dialog = ColumnMappingDialog(
            self.excel_handler.get_column_names(),
            current_mapping,
            df_sample,
            self
        )

        if dialog.exec_():
            mapping = dialog.get_mapping()
            self.excel_handler.set_column_mapping(mapping)
            
            # ДІАГНОСТИКА - виводимо в лог що саме налаштовано
            self.logger.info("=== MAPPING ПІСЛЯ НАЛАШТУВАННЯ ===")
            for field_id, col_indices in mapping.items():
                if col_indices:
                    col_names = [self.excel_handler.df.columns[idx] for idx in col_indices]
                    self.logger.info(f"  {field_id}: колонки {col_indices} → назви: {col_names}")
                else:
                    self.logger.info(f"  {field_id}: не налаштовано")
            
            # Оновлюємо відображення таблиці
            self.display_table(self.excel_handler.df)
            
            # КОПІЮЄМО ІНДЕКС → СТАРИЙ ІНДЕКС
            self.initialize_old_index()

            QMessageBox.information(self, "Успіх", "Відповідність стовпців оновлено!")

    def initialize_old_index(self):
        """Копіює індекс у віртуальну колонку 'Старий індекс'"""
        mapping = self.excel_handler.column_mapping
        
        if not mapping or 'index' not in mapping:
            self.logger.warning("Поле 'index' не налаштоване")
            return
        
        index_cols = mapping.get('index', [])
        if not index_cols:
            return
        
        idx_col = index_cols[0]
        
        # Знаходимо колонку "Старий індекс" (вона завжди остання)
        old_index_col_idx = len(self.excel_handler.df.columns) - 1
        old_index_col_name = self.excel_handler.df.columns[old_index_col_idx]
        
        if old_index_col_name == 'Старий індекс':
            # Копіюємо значення з робочого індексу
            self.excel_handler.df['Старий індекс'] = self.excel_handler.df.iloc[:, idx_col].copy()
            self.logger.info(f"✅ Скопійовано з колонки {idx_col} у 'Старий індекс'")
            
            # Оновлюємо відображення
            for row in range(min(self.table.rowCount(), len(self.excel_handler.df))):
                value = self.excel_handler.df.iloc[row, old_index_col_idx]
                item = self.table.item(row, old_index_col_idx)
                if item:
                    item.setText(str(value) if pd.notna(value) else "")
                    # Робимо колонку тільки для читання
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    item.setBackground(QColor(240, 240, 240))

    def undo(self):
        action = self.undo_manager.undo()
        if action:
            self.apply_undo_action(action, reverse=True)
            self.update_undo_redo_buttons()

    def redo(self):
        action = self.undo_manager.redo()
        if action:
            self.apply_undo_action(action, reverse=False)
            self.update_undo_redo_buttons()

    def apply_undo_action(self, action, reverse=False):
        pass

    def update_undo_redo_buttons(self):
        self.undo_btn.setEnabled(self.undo_manager.can_undo())
        self.redo_btn.setEnabled(self.undo_manager.can_redo())

    def set_index_star(self):
        if self.current_row < 0:
            return

        self.apply_suggested_index("*")

    def start_auto_processing(self):
        if self.current_row < 0:
            self.current_row = 0

        from ui.widgets.auto_processing_dialog import AutoProcessingDialog

        dialog = AutoProcessingDialog(
            self.current_row,
            len(self.excel_handler.df) if self.excel_handler.df is not None else 0,
            self
        )

        if dialog.exec_():
            min_confidence = dialog.get_min_confidence()
            self.process_all_rows(auto_mode=True, min_confidence=min_confidence)

    def start_semi_auto_processing(self):
        if self.current_row < 0:
            self.current_row = 0

        from ui.widgets.auto_processing_dialog import AutoProcessingDialog

        dialog = AutoProcessingDialog(
            self.current_row,
            len(self.excel_handler.df) if self.excel_handler.df is not None else 0,
            self
        )

        if dialog.exec_():
            min_confidence = dialog.get_min_confidence()
            self.semi_auto_min_confidence = min_confidence
            self.process_all_rows(auto_mode=False, min_confidence=min_confidence)

    def continue_semi_auto_processing(self):
        """Продовжує напівавтоматичну обробку після застосування індексу"""
        if not hasattr(self, 'semi_auto_min_confidence'):
            return
        
        # Запускаємо обробку з наступного рядка
        next_row = self.semi_auto_current_row + 1
        if next_row < len(self.excel_handler.df):
            self.current_row = next_row
            # Викликаємо обробку знову
            self.process_all_rows(auto_mode=False, min_confidence=self.semi_auto_min_confidence)

    def process_all_rows(self, auto_mode=True, min_confidence=90):
        if self.excel_handler.df is None:
            return

        self.processing_stopped = False

        self.search_btn.setEnabled(False)
        self.auto_process_btn.setEnabled(False)
        self.semi_auto_btn.setEnabled(False)
        self.column_mapping_btn.setEnabled(False)
        self.save_btn.setEnabled(False)

        # ПЕРЕВІРКА ЧИ КНОПКА ВЖЕ ІСНУЄ
        if not hasattr(self, 'stop_btn') or self.stop_btn is None:
            self.stop_btn = QPushButton("⏹ ЗУПИНИТИ")
            self.stop_btn.clicked.connect(self.stop_processing)
            self.stop_btn.setStyleSheet("background-color: #F44336; color: white; padding: 6px 15px; font-weight: bold; font-size: 11px;")
            self.statusBar().addPermanentWidget(self.stop_btn)

        total_rows = len(self.excel_handler.df)
        processed_count = 0
        skipped_count = 0

        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(total_rows - self.current_row)

        for row_idx in range(self.current_row, total_rows):
            if self.processing_stopped:
                break

            self.progress_bar.setValue(row_idx - self.current_row + 1)
            self.status_bar.setText(f"⏳ Обробка {row_idx + 1}/{total_rows}...")

            QApplication.processEvents()

            if self.is_row_processed(row_idx):
                skipped_count += 1
                continue

            try:
                address = self.excel_handler.get_address_from_row(row_idx)
                results = self.search_engine.search(address, max_results=20)

                self.log_search_request(address)
                self.log_search_results(address, results)

                if not results:
                    continue

                best_result = results[0]
                confidence = best_result.get('confidence', 0)
                not_working = best_result.get('not_working', '')

                # ВИЗНАЧАЄМО ІНДЕКС ЗАЛЕЖНО ВІД not_working
                if 'Тимчасово не функціонує' in not_working and 'ВПЗ' not in not_working:
                    index = '*'
                elif 'ВПЗ' in not_working:
                    match = re.search(r'(\d{5})', not_working)
                    index = match.group(1) if match else '**'
                else:
                    index = best_result.get('index', '')

                if confidence >= min_confidence and index:
                    # АВТОМАТИЧНО ЗАСТОСОВУЄМО
                    self.excel_handler.update_row(row_idx, {'index': index})

                    self.log_index_applied(row_idx, address, index)

                    mapping = self.excel_handler.column_mapping
                    if mapping and 'index' in mapping:
                        for col_idx in mapping['index']:
                            item = self.table.item(row_idx, col_idx)
                            if item:
                                item.setText(index)

                    for col in range(self.table.columnCount()):
                        item = self.table.item(row_idx, col)
                        if item:
                            item.setBackground(QColor(config.COLOR_PROCESSED))

                    processed_count += 1

                elif not auto_mode:
                    # НАПІВАВТОМАТИЧНИЙ РЕЖИМ - ЗУПИНЯЄМОСЯ І ЧЕКАЄМО
                    self.current_row = row_idx
                    self.semi_auto_current_row = row_idx
                    self.table.selectRow(row_idx)
                    self.table.scrollToItem(self.table.item(row_idx, 0))
                    self.results_panel.show_results(results, address.building or "")
                    self.address_panel.populate_from_results(results)
                    
                    self.status_bar.setText(f"⏸ Очікування вибору індексу для рядка {row_idx + 1} (точність {confidence}%)")
                    
                    # Зупиняємо цикл і чекаємо
                    self.semi_auto_waiting = True
                    self.progress_bar.setVisible(False)
                    
                    # Вмикаємо кнопки
                    self.search_btn.setEnabled(True)
                    self.column_mapping_btn.setEnabled(True)
                    self.save_btn.setEnabled(True)
                    
                    return  # Виходимо з циклу

            except Exception as e:
                self.logger.error(f"Помилка обробки рядка {row_idx}: {e}")
                continue

        # ЗАВЕРШЕННЯ ОБРОБКИ
        self.search_btn.setEnabled(True)
        self.auto_process_btn.setEnabled(True)
        self.semi_auto_btn.setEnabled(True)
        self.column_mapping_btn.setEnabled(True)
        self.save_btn.setEnabled(True)

        if hasattr(self, 'stop_btn') and self.stop_btn is not None:
            self.statusBar().removeWidget(self.stop_btn)
            self.stop_btn.deleteLater()
            self.stop_btn = None

        self.progress_bar.setVisible(False)
        self.status_bar.setText(f"✅ Оброблено: {processed_count}, Пропущено: {skipped_count}")

        if auto_mode or not self.semi_auto_waiting:
            QMessageBox.information(
                self,
                "Завершено",
                f"Обробка завершена!\n\nОброблено: {processed_count}\nПропущено: {skipped_count}"
            )


    def stop_processing(self):
        self.processing_stopped = True
        self.semi_auto_waiting = False

    def show_statistics(self):
        if not self.search_engine:
            QMessageBox.warning(self, "Увага", "Пошуковий движок не готовий")
            return

        stats = self.search_engine.get_statistics()

        msg = f"""
Статистика системи:

Загальна кількість записів: {stats['total_records']:,}
Проіндексовано міст: {stats['indexed_cities']:,}
Проіндексовано областей: {stats['indexed_regions']}
        """

        QMessageBox.information(self, "Статистика", msg)

    def closeEvent(self, event):
        geometry = self.geometry()
        SettingsManager.set_window_geometry(geometry.x(), geometry.y(), geometry.width(), geometry.height())
        
        if self.table.columnCount() > 0:
            widths = [self.table.columnWidth(i) for i in range(self.table.columnCount())]
            SettingsManager.set_column_widths(widths)

        right_splitter = self.findChild(QSplitter)
        if right_splitter:
            sizes = right_splitter.sizes()
            SettingsManager.set_splitter_sizes('right_panel', sizes)

        event.accept()
