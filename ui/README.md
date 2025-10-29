# UI Module Documentation

## Огляд

UI модуль postal-index-matcher побудований за принципом розділення відповідальностей:
- **Managers** - бізнес-логіка
- **Widgets** - UI компоненти
- **Styles** - централізовані стилі

## Архітектура

```
ui/
├── managers/              # Бізнес-логіка
│   ├── file_manager.py    # Робота з файлами
│   ├── search_manager.py  # Пошук адрес
│   ├── processing_manager.py  # Авто/напів-авто обробка
│   └── ui_state_manager.py    # Стан інтерфейсу
├── widgets/               # UI компоненти
│   ├── address_selector_panel.py
│   ├── results_panel.py
│   ├── column_mapping_dialog.py
│   └── auto_processing_dialog.py
├── styles/                # Стилі
│   └── styles.py          # AppStyles
└── main_window.py         # Головне вікно (координатор)
```

## Managers

### FileManager

Управляє всіма операціями з Excel файлами.

**Приклад використання:**

```python
from ui.managers import FileManager

file_manager = FileManager()

# Завантаження файлу
success = file_manager.load_file("/path/to/file.xlsx")

# Збереження файлу
success = file_manager.save_file(
    file_path="/path/to/file.xlsx",
    save_old_index=True
)

# Копіювання індексу у "Старий індекс"
file_manager.copy_to_old_index()
```

**Основні методи:**

- `load_file(file_path)` - завантажує Excel файл
- `save_file(file_path, save_old_index)` - зберігає файл
- `get_file_dialog_path(parent, mode)` - відкриває діалог вибору файлу
- `copy_to_old_index()` - копіює індекси

### SearchManager

Управляє пошуком адрес і логуванням.

**Приклад використання:**

```python
from ui.managers import SearchManager
from models.address import Address

search_manager = SearchManager()

# Пошук адреси
address = Address(
    city="Київ",
    street="вул. Хрещатик",
    building="1"
)
results = search_manager.search(address, max_results=20)

# Оновлення кешу
search_manager.refresh_cache(force_reload=True)

# Логування застосованого індексу
search_manager.log_index_applied(row_idx=0, address=address, index_value="01001")
```

**Основні методи:**

- `search(address, max_results)` - виконує пошук
- `get_magistral_records()` - повертає записи magistral.csv
- `refresh_cache(force_reload)` - оновлює кеш
- `log_index_applied(row_idx, address, index_value)` - логує індекс

### ProcessingManager

Управляє автоматичною та напівавтоматичною обробкою.

**Приклад використання:**

```python
from ui.managers import ProcessingManager
from handlers.excel_handler import ExcelHandler
from utils.undo_manager import UndoManager

excel_handler = ExcelHandler()
undo_manager = UndoManager()

processing_manager = ProcessingManager(excel_handler, undo_manager)

# Налаштування колбеків
processing_manager.on_progress_update = lambda current, total: print(f"{current}/{total}")
processing_manager.on_row_processed = lambda row, index: print(f"Row {row}: {index}")

# Автоматична обробка
def search_func(address):
    return search_manager.search(address)

stats = processing_manager.start_auto_processing(
    start_row=0,
    total_rows=100,
    min_confidence=80,
    search_func=search_func
)

print(f"Processed: {stats['processed']}, Skipped: {stats['skipped']}")

# Зупинка обробки
processing_manager.stop_processing()
```

**Основні методи:**

- `start_auto_processing(...)` - автоматична обробка
- `start_semi_auto_processing(...)` - напівавтоматична обробка
- `continue_semi_auto(search_func)` - продовження після паузи
- `stop_processing()` - зупинка
- `apply_index(row_idx, index)` - застосування індексу

### UIStateManager

Управляє станом UI компонентів.

**Приклад використання:**

```python
from ui.managers import UIStateManager

ui_state = UIStateManager()

# Підключення до сигналів
ui_state.file_loaded.connect(lambda path: print(f"File loaded: {path}"))
ui_state.processing_started.connect(lambda: print("Processing started"))

# Встановлення стану
ui_state.set_file_loaded("/path/to/file.xlsx")
ui_state.set_current_row(5)
ui_state.set_processing_state(True)

# Управління кнопками
buttons = {
    'save': save_button,
    'search': search_button,
    'auto_process': auto_button
}

ui_state.enable_buttons_for_file_loaded(buttons)
ui_state.disable_buttons_for_processing(buttons)

# Отримання кольору для індексу
color = ui_state.get_index_color_for_state(is_applied=True)
```

**Сигнали:**

- `file_loaded(str)` - файл завантажено
- `file_saved()` - файл збережено
- `row_selected(int)` - рядок обрано
- `processing_started()` - обробка розпочата
- `processing_finished()` - обробка завершена
- `undo_redo_changed()` - стан Undo/Redo змінився

## Styles

### AppStyles

Централізоване сховище всіх стилів.

**Приклад використання:**

```python
from ui.styles import AppStyles

# Застосування стилю до кнопки
button.setStyleSheet(AppStyles.button_primary(font_size="12px"))

# Застосування через helper
AppStyles.apply_to_widget(button, AppStyles.button_success, font_size="11px")

# Використання кольорів
item.setForeground(QColor(AppStyles.Colors.INDEX_APPLIED))

# Використання розмірів
label.setStyleSheet(f"font-size: {AppStyles.Sizes.FONT_LARGE};")
```

**Доступні стилі:**

**Кнопки:**
- `button_primary()` - синя кнопка
- `button_success()` - зелена кнопка
- `button_warning()` - помаранчева кнопка
- `button_danger()` - червона кнопка
- `button_default()` - сіра кнопка

**Таблиці:**
- `table_main()` - стиль головної таблиці

**Панелі:**
- `panel_header()` - заголовок панелі
- `status_bar()` - статус бар
- `file_label()` - мітка файлу
- `original_data_label()` - панель оригінальних даних

**Поля введення:**
- `input_field()` - звичайне поле
- `input_index()` - поле для індексу

**Списки:**
- `list_results()` - список результатів
- `list_popup()` - popup список

**Інше:**
- `combo_box()` - комбобокс
- `progress_bar()` - прогрес бар

## Інтеграція з MainWindow

Приклад інтеграції менеджерів у MainWindow:

```python
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Ініціалізація менеджерів
        self.file_manager = FileManager()
        self.search_manager = SearchManager()
        self.processing_manager = ProcessingManager(
            self.file_manager.excel_handler,
            UndoManager()
        )
        self.ui_state = UIStateManager()
        
        # Підключення сигналів
        self.ui_state.file_loaded.connect(self.on_file_loaded)
        self.ui_state.processing_started.connect(self.on_processing_started)
        
        self._init_ui()
    
    def load_file(self):
        """Завантаження файлу через FileManager"""
        file_path = self.file_manager.get_file_dialog_path(self, mode='open')
        if file_path:
            success = self.file_manager.load_file(file_path)
            if success:
                self.ui_state.set_file_loaded(file_path)
                self.display_table(self.file_manager.excel_handler.df)
    
    def search_address(self):
        """Пошук через SearchManager"""
        if self.ui_state.current_row < 0:
            return
        
        address = self.file_manager.excel_handler.get_address_from_row(
            self.ui_state.current_row
        )
        results = self.search_manager.search(address)
        self.results_panel.show_results(results)
```

## Best Practices

### 1. Розділення відповідальностей

❌ **Погано:**
```python
class MainWindow(QMainWindow):
    def load_file(self):
        # 100 рядків коду завантаження файлу
        ...
```

✅ **Добре:**
```python
class MainWindow(QMainWindow):
    def load_file(self):
        file_path = self.file_manager.get_file_dialog_path(self)
        if file_path:
            self.file_manager.load_file(file_path)
```

### 2. Використання централізованих стилів

❌ **Погано:**
```python
button.setStyleSheet("background-color: #4CAF50; color: white; padding: 6px;")
```

✅ **Добре:**
```python
button.setStyleSheet(AppStyles.button_success())
```

### 3. Використання сигналів для комунікації

❌ **Погано:**
```python
def process_row(self):
    # Прямий виклик UI оновлення
    self.status_bar.setText("Processing...")
```

✅ **Добре:**
```python
def process_row(self):
    self.ui_state.set_processing_state(True)
    # UI автоматично оновиться через сигнал
```

### 4. Колбеки для оновлення UI

```python
processing_manager.on_progress_update = lambda current, total: \
    self.progress_bar.setValue(current * 100 // total)

processing_manager.on_row_processed = lambda row, index: \
    self.update_table_cell(row, index)
```

## Тестування

Менеджери можна легко тестувати окремо:

```python
def test_search_manager():
    search_manager = SearchManager()
    address = Address(city="Київ", street="вул. Хрещатик")
    
    results = search_manager.search(address)
    
    assert len(results) > 0
    assert results[0]['confidence'] > 0

def test_processing_manager():
    excel_handler = MockExcelHandler()
    undo_manager = UndoManager()
    
    processing_manager = ProcessingManager(excel_handler, undo_manager)
    
    processed_count = []
    processing_manager.on_row_processed = lambda row, idx: processed_count.append(row)
    
    stats = processing_manager.start_auto_processing(...)
    
    assert stats['processed'] == len(processed_count)
```

## Міграція з старого коду

### Крок 1: Замінити прямі виклики на менеджери

Замість:
```python
self.excel_handler.load_file(file_path)
```

Використовувати:
```python
self.file_manager.load_file(file_path)
```

### Крок 2: Винести бізнес-логіку

Замість:
```python
def search_address(self):
    # 50 рядків логіки пошуку
    ...
```

Використовувати:
```python
def search_address(self):
    results = self.search_manager.search(address)
    self.results_panel.show_results(results)
```

### Крок 3: Застосувати централізовані стилі

Замість:
```python
button.setStyleSheet("background-color: #2196F3; ...")
```

Використовувати:
```python
button.setStyleSheet(AppStyles.button_primary())
```

## Підтримка

При виникненні питань чи проблем:
1. Перевірте цю документацію
2. Подивіться приклади коду
3. Перегляньте логи у `logs/` директорії
4. Зверніться до розробника

## Changelog

### v1.0 (2025-01-29)
- ✅ Створено FileManager
- ✅ Створено SearchManager
- ✅ Створено ProcessingManager
- ✅ Створено UIStateManager
- ✅ Створено AppStyles
- ✅ Документація

### Наступні кроки
- [ ] Рефакторинг MainWindow
- [ ] Створення окремих панелей
- [ ] Додаткові тести
