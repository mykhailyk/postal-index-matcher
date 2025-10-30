"""
UIStateManager - управління станом інтерфейсу

Відповідає за:
- Управління станом кнопок (enabled/disabled)
- Поточний вибраний рядок
- Стан фільтрів
- Відображення статусів
"""

from typing import Optional, Dict, Callable
from PyQt5.QtGui import QColor
from PyQt5.QtCore import QObject, pyqtSignal

from utils.logger import Logger


class UIStateManager(QObject):
    """Менеджер стану UI компонентів"""
    
    # Сигнали для оповіщення про зміни стану
    file_loaded = pyqtSignal(str)  # Файл завантажено
    file_saved = pyqtSignal()      # Файл збережено
    row_selected = pyqtSignal(int)  # Рядок обрано
    processing_started = pyqtSignal()  # Обробка розпочата
    processing_finished = pyqtSignal()  # Обробка завершена
    undo_redo_changed = pyqtSignal()  # Стан Undo/Redo змінився
    
    def __init__(self):
        """Ініціалізація UIStateManager"""
        super().__init__()
        self.logger = Logger()
        
        # Стан файлу
        self.is_file_loaded = False
        self.current_file_path: Optional[str] = None
        
        # Стан обробки
        self.is_processing = False
        self.current_row = -1
        
        # Стан фільтра
        self.current_filter = "Всі"
        
        # Кольори для індексів
        self.COLOR_INDEX_APPLIED = QColor("#4CAF50")  # Зелений
        self.COLOR_INDEX_DEFAULT = QColor("#000000")  # Чорний
        
    def set_file_loaded(self, file_path: str):
        """
        Встановлює стан "файл завантажено"
        
        Args:
            file_path: Шлях до завантаженого файлу
        """
        self.is_file_loaded = True
        self.current_file_path = file_path
        self.file_loaded.emit(file_path)
        self.logger.info(f"UI State: файл завантажено - {file_path}")
    
    def set_file_saved(self):
        """Встановлює стан "файл збережено" """
        self.file_saved.emit()
        self.logger.info("UI State: файл збережено")
    
    def set_current_row(self, row: int):
        """
        Встановлює поточний вибраний рядок
        
        Args:
            row: Номер рядка
        """
        self.current_row = row
        self.row_selected.emit(row)
    
    def set_processing_state(self, is_processing: bool):
        """
        Встановлює стан обробки
        
        Args:
            is_processing: True якщо обробка активна
        """
        self.is_processing = is_processing
        
        if is_processing:
            self.processing_started.emit()
        else:
            self.processing_finished.emit()
    
    def set_filter(self, filter_name: str):
        """
        Встановлює активний фільтр
        
        Args:
            filter_name: Назва фільтру
        """
        self.current_filter = filter_name
        self.logger.debug(f"Фільтр змінено: {filter_name}")
    
    def enable_buttons_for_file_loaded(self, buttons: Dict[str, any]):
        """
        Активує кнопки після завантаження файлу
        
        Args:
            buttons: Словник кнопок {name: button_widget}
        """
        buttons_to_enable = [
            'column_mapping', 'save', 'save_as', 
            'search', 'auto_process', 'semi_auto',
            'parse_addresses'  # ДОДАНО
        ]
        
        for name in buttons_to_enable:
            if name in buttons and buttons[name]:
                buttons[name].setEnabled(True)
    
    def disable_buttons_for_processing(self, buttons: Dict[str, any]):
        """
        Деактивує кнопки під час обробки
        
        Args:
            buttons: Словник кнопок
        """
        buttons_to_disable = [
            'search', 'auto_process', 'semi_auto',
            'column_mapping', 'save'
        ]
        
        for name in buttons_to_disable:
            if name in buttons and buttons[name]:
                buttons[name].setEnabled(False)
    
    def enable_buttons_after_processing(self, buttons: Dict[str, any]):
        """
        Активує кнопки після обробки
        
        Args:
            buttons: Словник кнопок
        """
        if self.is_file_loaded:
            self.enable_buttons_for_file_loaded(buttons)
    
    def update_undo_redo_buttons(
        self, 
        undo_button: any, 
        redo_button: any,
        can_undo: bool,
        can_redo: bool
    ):
        """
        Оновлює стан кнопок Undo/Redo
        
        Args:
            undo_button: Кнопка Undo
            redo_button: Кнопка Redo
            can_undo: Чи можна відмінити
            can_redo: Чи можна повторити
        """
        if undo_button:
            undo_button.setEnabled(can_undo)
        if redo_button:
            redo_button.setEnabled(can_redo)
        
        self.undo_redo_changed.emit()
    
    def get_index_color_for_state(self, is_applied: bool) -> QColor:
        """
        Повертає колір для індексу в залежності від стану
        
        Args:
            is_applied: Чи застосовано індекс
            
        Returns:
            Колір для відображення
        """
        return self.COLOR_INDEX_APPLIED if is_applied else self.COLOR_INDEX_DEFAULT
    
    def reset(self):
        """Скидає стан до початкового"""
        self.is_file_loaded = False
        self.current_file_path = None
        self.is_processing = False
        self.current_row = -1
        self.current_filter = "Всі"
        self.logger.info("UI State: скинуто до початкового стану")
    
    def get_status_message(self) -> str:
        """
        Генерує повідомлення статусу
        
        Returns:
            Текст статусу
        """
        if self.is_processing:
            return "⏳ Обробка..."
        elif not self.is_file_loaded:
            return "Готово до роботи"
        elif self.current_row >= 0:
            return f"Обрано рядок {self.current_row + 1}"
        else:
            return "✅ Готово"
