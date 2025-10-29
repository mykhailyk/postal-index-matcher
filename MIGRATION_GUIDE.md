# Інструкція міграції на нову архітектуру

## Огляд змін

Старий код використовував монолітний підхід з великим MainWindow.
Нова архітектура розділяє відповідальності між менеджерами та UI компонентами.

## Покрокова міграція

### Крок 1: Ініціалізація менеджерів

**Було:**
```python
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.logger = Logger()
        self.excel_handler = ExcelHandler()
        self.undo_manager = UndoManager()
        self.search_engine = None
        self.init_ui()
        self.init_search_engine()
```

**Стало:**
```python
from ui.managers import FileManager, SearchManager, ProcessingManager, UIStateManager

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Менеджери інкапсулюють логіку
        self.file_manager = FileManager()
        self.search_manager = SearchManager()
        self.undo_manager = UndoManager()
        self.processing_manager = ProcessingManager(
            self.file_manager.excel_handler,
            self.undo_manager
        )
        self.ui_state = UIStateManager()
        
        self._init_ui()
        self._connect_signals()
        self._setup_callbacks()
```

### Крок 2: Завантаження файлів

**Було:**
```python
def load_excel_file(self):
    file_path, _ = QFileDialog.getOpenFileName(...)
    if not file_path:
        return
    
    try:
        self.logger.info(f"Завантаження файлу: {file_path}")
        SettingsManager.set_last_directory(os.path.dirname(file_path))
        self.excel_handler.load_file(file_path)
        
        # Створюємо віртуальну колонку "Старий індекс"
        if 'Старий індекс' not in self.excel_handler.df.columns:
            # ... 20+ рядків логіки
        
        self.current_file = file_path
        self.file_label.setText(os.path.basename(file_path))
        # ... ще багато коду
    except Exception as e:
        # обробка помилок
```

**Стало:**
```python
def load_file(self):
    """Завантаження файлу через FileManager"""
    file_path = self.file_manager.get_file_dialog_path(self, mode='open')
    if not file_path:
        return
    
    success = self.file_manager.load_file(file_path)
    if success:
        self.ui_state.set_file_loaded(file_path)
        self._display_table()
    else:
        QMessageBox.critical(self, "Помилка", "Не вдалося завантажити файл")
```

**Переваги:**
- Менше коду у MainWindow
- Логіка файлів інкапсульована в FileManager
- Легше тестувати
- Повторне використання можливе

### Крок 3: Пошук адрес

**Було:**
```python
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
        
        # Логування
        self.log_search_request(address)
        
        results = self.search_engine.search(address, max_results=20)
        
        # Логування результатів
        self.log_search_results(address, results)
        
        self.search_results = results
        self.results_panel.show_results(results, address.building or "")
        
        if results:
            self.address_panel.populate_from_results(results)
        
        self.status_bar.setText(f"✅ Знайдено {len(results)} варіантів")
    except Exception as e:
        # обробка помилок
```

**Стало:**
```python
def search_address(self):
    """Пошук адреси через SearchManager"""
    if self.current_row < 0:
        QMessageBox.warning(self, "Увага", "Оберіть рядок для пошуку")
        return
    
    try:
        address = self.file_manager.excel_handler.get_address_from_row(self.current_row)
        
        # SearchManager виконує пошук + логування
        results = self.search_manager.search(address, max_results=20)
        
        # Відображаємо результати
        self.results_panel.show_results(results, address.building or "")
        if results:
            self.address_panel.populate_from_results(results)
        
        self.status_bar.setText(f"✅ Знайдено {len(results)} варіантів")
    except Exception as e:
        QMessageBox.critical(self, "Помилка", f"Помилка пошуку:\n{e}")
```

**Переваги:**
- Логіка пошуку та логування в SearchManager
- Менше повторень коду
- Простіше підтримувати

### Крок 4: Автоматична обробка

**Було:**
```python
def process_all_rows(self, auto_mode=True, min_confidence=80):
    """Обробка всіх рядків з автоматичним/напівавтоматичним режимом"""
    if self.excel_handler.df is None:
        return
    
    self.processing_stopped = False
    
    # Вимикаємо кнопки
    self.search_btn.setEnabled(False)
    self.auto_process_btn.setEnabled(False)
    # ... багато коду управління UI
    
    total_rows = len(self.excel_handler.df)
    processed_count = 0
    skipped_count = 0
    
    # ... 100+ рядків логіки обробки
    
    for row_idx in range(self.current_row, total_rows):
        QApplication.processEvents()
        
        if self.processing_stopped:
            break
        
        # Оновлення прогресу
        self.progress_bar.setValue(row_idx + 1)
        
        # Пошук та застосування індексу
        # ... багато коду
    
    # Очищення
    self._cleanup_processing()
```

**Стало:**
```python
def start_auto_processing(self):
    """Запуск автоматичної обробки"""
    if self.current_row < 0:
        self.current_row = 0
    
    dialog = AutoProcessingDialog(...)
    if dialog.exec_():
        min_confidence = dialog.get_min_confidence()
        
        # Встановлюємо стан обробки (автоматично керує UI)
        self.ui_state.set_processing_state(True)
        
        # ProcessingManager виконує всю роботу
        stats = self.processing_manager.start_auto_processing(
            start_row=self.current_row,
            total_rows=len(self.file_manager.excel_handler.df),
            min_confidence=min_confidence,
            search_func=lambda addr: self.search_manager.search(addr)
        )
        
        # Завершуємо
        self.ui_state.set_processing_state(False)
        
        QMessageBox.information(
            self, "Завершено",
            f"Оброблено: {stats['processed']}\nПропущено: {stats['skipped']}"
        )
```

**Переваги:**
- Логіка обробки в ProcessingManager
- UI оновлення через колбеки
- Легше тестувати обробку окремо

### Крок 5: Використання стилів

**Було:**
```python
button.setStyleSheet(
    "background-color: #4CAF50; color: white; padding: 6px 15px; "
    "font-weight: bold; font-size: 11px;"
)

self.table.setStyleSheet("""
    QTableWidget {
        gridline-color: #d0d0d0;
        border: 1px solid #c0c0c0;
    }
    QTableWidget::item:selected {
        background-color: #E3F2FD;
    }
""")
```

**Стало:**
```python
from ui.styles import AppStyles

# Кнопка
button.setStyleSheet(AppStyles.button_success(font_size="11px"))

# Таблиця
self.table.setStyleSheet(AppStyles.table_main())

# Або через helper
AppStyles.apply_to_widget(button, AppStyles.button_primary)
```

**Переваги:**
- Єдиний стиль для всієї програми
- Легко змінювати глобально
- Константи для кольорів

### Крок 6: Сигнали та колбеки

**Було:**
```python
def on_file_loaded(self):
    self.column_mapping_btn.setEnabled(True)
    self.save_btn.setEnabled(True)
    self.search_btn.setEnabled(True)
    # ... багато коду активації кнопок
```

**Стало:**
```python
def _connect_signals(self):
    """Підключає сигнали від менеджерів"""
    self.ui_state.file_loaded.connect(self._on_file_loaded_signal)
    self.ui_state.processing_started.connect(self._on_processing_started_signal)
    self.ui_state.processing_finished.connect(self._on_processing_finished_signal)

def _on_file_loaded_signal(self, file_path: str):
    """Обробка сигналу завантаження файлу"""
    self.file_label.setText(file_path.split('/')[-1])
    
    buttons = {
        'column_mapping': self.column_mapping_btn,
        'save': self.save_btn,
        'search': self.search_btn,
        'auto_process': self.auto_process_btn
    }
    self.ui_state.enable_buttons_for_file_loaded(buttons)
```

**Переваги:**
- Реактивна архітектура
- Зменшення зв'язаності
- Легше додавати нові обробники

## Порівняння розмірів коду

### MainWindow

| Метрика | Старий код | Новий код | Зміна |
|---------|-----------|-----------|-------|
| Рядків коду | ~1000 | ~400 | -60% |
| Методів | ~30 | ~15 | -50% |
| Відповідальностей | Багато | Координація | ✅ |
| Залежностей | Прямі | Інжекція | ✅ |

### Переваги нової архітектури

| Аспект | Покращення |
|--------|------------|
| Читабельність | ⬆️⬆️⬆️ Набагато краще |
| Підтримуваність | ⬆️⬆️⬆️ Легше знаходити баги |
| Тестування | ⬆️⬆️⬆️ Менеджери окремо |
| Повторне використання | ⬆️⬆️ Логіка не прив'язана до UI |
| Масштабованість | ⬆️⬆️⬆️ Легко додавати функції |

## Чеклист міграції

### Для існуючого коду

- [ ] **Крок 1:** Імпортувати менеджери
  ```python
  from ui.managers import FileManager, SearchManager, ProcessingManager, UIStateManager
  from ui.styles import AppStyles
  ```

- [ ] **Крок 2:** Замінити ініціалізацію в `__init__`
  ```python
  self.file_manager = FileManager()
  self.search_manager = SearchManager()
  # ...
  ```

- [ ] **Крок 3:** Замінити методи завантаження файлів
  - Використати `file_manager.load_file()`
  - Використати `file_manager.save_file()`

- [ ] **Крок 4:** Замінити методи пошуку
  - Використати `search_manager.search()`

- [ ] **Крок 5:** Замінити автообробку
  - Використати `processing_manager.start_auto_processing()`
  - Налаштувати колбеки

- [ ] **Крок 6:** Застосувати централізовані стилі
  - Замінити inline стилі на `AppStyles.*`

- [ ] **Крок 7:** Підключити сигнали
  - `ui_state.file_loaded.connect(...)`
  - `ui_state.processing_started.connect(...)`

- [ ] **Крок 8:** Тестування
  - Перевірити всі функції
  - Порівняти з оригіналом

## Приклад повної міграції методу

### До міграції (45 рядків)

```python
def apply_suggested_index(self, index_str):
    if self.current_row < 0:
        return
    
    try:
        address = self.excel_handler.get_address_from_row(self.current_row)
        old_index = address.index
        
        # Зберігаємо для Undo
        self.undo_manager.push({
            'row': self.current_row,
            'old_values': {'index': old_index},
            'new_values': {'index': index_str}
        })
        
        # Оновлюємо DataFrame
        mapping = self.excel_handler.column_mapping
        if mapping and 'index' in mapping:
            idx_col = mapping['index'][0]
            self.excel_handler.df.iloc[self.current_row, idx_col] = index_str
        
        # Логування
        self.log_index_applied(self.current_row, address, index_str)
        
        # Оновлюємо комірку в таблиці
        if mapping and 'index' in mapping:
            for col_idx in mapping['index']:
                item = self.table.item(self.current_row, col_idx)
                if item:
                    item.setText(index_str)
                    item.setForeground(QColor("#4CAF50"))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
        
        self.status_bar.setText(f"✅ Застосовано індекс {index_str}")
        
        # Очищаємо форму
        self.address_panel.cascade_city_input.clear()
        # ... багато очищень
        
        self.update_undo_redo_buttons()
        
        # Переходимо на наступний рядок
        next_row = self.current_row + 1
        if next_row < self.table.rowCount():
            self.table.selectRow(next_row)
    except Exception as e:
        self.logger.error(f"Помилка застосування індексу: {e}")
```

### Після міграції (25 рядків)

```python
def apply_index(self, index: str):
    """Застосування індексу через ProcessingManager"""
    if self.current_row < 0:
        return
    
    # ProcessingManager виконує всю логіку + Undo
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
        
        # SearchManager виконує логування
        address = self.file_manager.excel_handler.get_address_from_row(self.current_row)
        self.search_manager.log_index_applied(self.current_row, address, index)
        
        self.status_bar.setText(f"✅ Застосовано індекс {index}")
        
        # Переходимо на наступний рядок
        if self.current_row + 1 < self.table.rowCount():
            self.table.selectRow(self.current_row + 1)
```

**Результат:** -44% коду, більше зрозумілості

## Тестування після міграції

```python
# Тестування менеджерів окремо
def test_file_manager():
    fm = FileManager()
    assert fm.load_file("test.xlsx") == True

def test_search_manager():
    sm = SearchManager()
    results = sm.search(test_address)
    assert len(results) > 0

def test_processing_manager():
    pm = ProcessingManager(excel_handler, undo_manager)
    stats = pm.start_auto_processing(...)
    assert stats['processed'] > 0
```

## Поширені помилки

### ❌ Помилка 1: Використання старих залежностей

```python
# Погано
self.excel_handler.load_file(path)

# Добре
self.file_manager.load_file(path)
```

### ❌ Помилка 2: Ігнорування сигналів

```python
# Погано
def load_file(self):
    self.file_manager.load_file(path)
    self.enable_buttons()  # Прямий виклик

# Добре
def load_file(self):
    success = self.file_manager.load_file(path)
    if success:
        self.ui_state.set_file_loaded(path)  # Сигнал -> enable_buttons
```

### ❌ Помилка 3: Дублювання стилів

```python
# Погано
button1.setStyleSheet("background-color: #4CAF50; ...")
button2.setStyleSheet("background-color: #4CAF50; ...")

# Добре
button1.setStyleSheet(AppStyles.button_success())
button2.setStyleSheet(AppStyles.button_success())
```

## Подальші кроки

1. ✅ Менеджери створено
2. ✅ Стилі централізовано
3. ✅ Документація написана
4. ⏳ Міграція MainWindow (в процесі)
5. ⏳ Створення окремих панелей
6. ⏳ Фінальне тестування

## Підтримка

Питання? Проблеми? Дивіться:
- `ui/README.md` - документація менеджерів
- `ui/main_window_refactored_example.py` - повний приклад
- `REFACTORING_PLAN.md` - загальний план
