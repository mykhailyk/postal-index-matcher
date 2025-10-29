"""
Централізовані стилі для всіх UI компонентів

Містить:
- Кольори
- Стилі кнопок
- Стилі таблиць
- Стилі панелей
- Стилі діалогів
"""


class AppStyles:
    """Централізоване сховище всіх стилів програми"""
    
    # ==================== КОЛЬОРИ ====================
    
    class Colors:
        """Палітра кольорів програми"""
        
        # Основні кольори
        PRIMARY = "#2196F3"      # Синій
        SUCCESS = "#4CAF50"      # Зелений
        WARNING = "#FF9800"      # Помаранчевий
        DANGER = "#F44336"       # Червоний
        INFO = "#9C27B0"         # Фіолетовий
        
        # Фонові кольори
        BG_LIGHT = "#f0f0f0"
        BG_LIGHTER = "#f9f9f9"
        BG_DARK = "#e0e0e0"
        BG_WARNING = "#FFF3E0"
        BG_SUCCESS = "#E8F5E9"
        BG_PRIMARY = "#E3F2FD"
        
        # Кольори тексту
        TEXT_DEFAULT = "#000000"
        TEXT_LIGHT = "#666666"
        TEXT_WHITE = "#ffffff"
        TEXT_SUCCESS = "#4CAF50"
        
        # Кольори рамок
        BORDER_DEFAULT = "#c0c0c0"
        BORDER_LIGHT = "#d0d0d0"
        BORDER_DARK = "#a0a0a0"
        BORDER_PRIMARY = "#2196F3"
        BORDER_WARNING = "#FFB74D"
        BORDER_SUCCESS = "#4CAF50"
        
        # Кольори для статусів
        INDEX_APPLIED = "#4CAF50"     # Зелений - проставлено
        INDEX_DEFAULT = "#000000"     # Чорний - не проставлено
        ROW_SELECTED = "#E3F2FD"      # Блакитний - вибрано
        ROW_ALTERNATE = "#f9f9f9"     # Світло-сірий - чередування
    
    # ==================== РОЗМІРИ ====================
    
    class Sizes:
        """Розміри елементів"""
        
        # Відступи
        PADDING_SMALL = "3px"
        PADDING_MEDIUM = "5px"
        PADDING_LARGE = "10px"
        
        # Радіуси
        RADIUS_SMALL = "2px"
        RADIUS_MEDIUM = "3px"
        RADIUS_LARGE = "5px"
        
        # Шрифти
        FONT_SMALL = "10px"
        FONT_NORMAL = "11px"
        FONT_MEDIUM = "12px"
        FONT_LARGE = "13px"
        FONT_XLARGE = "16px"
    
    # ==================== СТИЛІ КНОПОК ====================
    
    @staticmethod
    def button_primary(font_size="11px"):
        """Основна кнопка (синя)"""
        return f"""
            QPushButton {{
                background-color: {AppStyles.Colors.PRIMARY};
                color: {AppStyles.Colors.TEXT_WHITE};
                padding: 6px 15px;
                font-weight: bold;
                font-size: {font_size};
                border: none;
                border-radius: {AppStyles.Sizes.RADIUS_MEDIUM};
            }}
            QPushButton:hover {{
                background-color: #1976D2;
            }}
            QPushButton:pressed {{
                background-color: #0D47A1;
            }}
            QPushButton:disabled {{
                background-color: #BDBDBD;
                color: #757575;
            }}
        """
    
    @staticmethod
    def button_success(font_size="11px"):
        """Кнопка успіху (зелена)"""
        return f"""
            QPushButton {{
                background-color: {AppStyles.Colors.SUCCESS};
                color: {AppStyles.Colors.TEXT_WHITE};
                padding: 6px 15px;
                font-weight: bold;
                font-size: {font_size};
                border: none;
                border-radius: {AppStyles.Sizes.RADIUS_MEDIUM};
            }}
            QPushButton:hover {{
                background-color: #388E3C;
            }}
            QPushButton:pressed {{
                background-color: #2E7D32;
            }}
            QPushButton:disabled {{
                background-color: #BDBDBD;
                color: #757575;
            }}
        """
    
    @staticmethod
    def button_warning(font_size="11px"):
        """Кнопка попередження (помаранчева)"""
        return f"""
            QPushButton {{
                background-color: {AppStyles.Colors.WARNING};
                color: {AppStyles.Colors.TEXT_WHITE};
                padding: 6px 12px;
                font-size: {font_size};
                border: none;
                border-radius: {AppStyles.Sizes.RADIUS_MEDIUM};
            }}
            QPushButton:hover {{
                background-color: #F57C00;
            }}
            QPushButton:pressed {{
                background-color: #E65100;
            }}
        """
    
    @staticmethod
    def button_danger(font_size="11px"):
        """Кнопка небезпеки (червона)"""
        return f"""
            QPushButton {{
                background-color: {AppStyles.Colors.DANGER};
                color: {AppStyles.Colors.TEXT_WHITE};
                padding: 6px 15px;
                font-weight: bold;
                font-size: {font_size};
                border: none;
                border-radius: {AppStyles.Sizes.RADIUS_MEDIUM};
            }}
            QPushButton:hover {{
                background-color: #D32F2F;
            }}
            QPushButton:pressed {{
                background-color: #C62828;
            }}
        """
    
    @staticmethod
    def button_default(font_size="11px"):
        """Звичайна кнопка (сіра)"""
        return f"""
            QPushButton {{
                padding: 4px 10px;
                font-size: {font_size};
                border: 1px solid {AppStyles.Colors.BORDER_DEFAULT};
                border-radius: {AppStyles.Sizes.RADIUS_SMALL};
                background-color: white;
            }}
            QPushButton:hover {{
                background-color: {AppStyles.Colors.BG_LIGHT};
            }}
            QPushButton:pressed {{
                background-color: {AppStyles.Colors.BG_DARK};
            }}
        """
    
    # ==================== СТИЛІ ТАБЛИЦЬ ====================
    
    @staticmethod
    def table_main():
        """Стиль головної таблиці"""
        return f"""
            QTableWidget {{
                gridline-color: {AppStyles.Colors.BORDER_LIGHT};
                border: 1px solid {AppStyles.Colors.BORDER_DEFAULT};
                background-color: white;
            }}
            QTableWidget::item {{
                padding: 4px;
            }}
            QTableWidget::item:selected {{
                background-color: {AppStyles.Colors.ROW_SELECTED};
                border: 2px solid {AppStyles.Colors.TEXT_DEFAULT};
            }}
            QTableWidget::item:focus {{
                background-color: {AppStyles.Colors.ROW_SELECTED};
                border: 2px solid {AppStyles.Colors.TEXT_DEFAULT};
            }}
            QHeaderView::section {{
                background-color: {AppStyles.Colors.BG_LIGHT};
                padding: 5px;
                border: 1px solid {AppStyles.Colors.BORDER_LIGHT};
                font-weight: bold;
            }}
        """
    
    # ==================== СТИЛІ ПАНЕЛЕЙ ====================
    
    @staticmethod
    def panel_header(font_size="13px"):
        """Заголовок панелі"""
        return f"""
            QLabel {{
                font-weight: bold;
                font-size: {font_size};
                padding: 5px;
            }}
        """
    
    @staticmethod
    def status_bar():
        """Статус бар"""
        return f"""
            QLabel {{
                padding: 5px;
                background-color: {AppStyles.Colors.BG_SUCCESS};
                border-top: 1px solid {AppStyles.Colors.BORDER_SUCCESS};
                font-size: {AppStyles.Sizes.FONT_SMALL};
            }}
        """
    
    @staticmethod
    def file_label():
        """Мітка назви файлу"""
        return f"""
            QLabel {{
                padding: 3px;
                background-color: {AppStyles.Colors.BG_LIGHT};
                border-radius: {AppStyles.Sizes.RADIUS_SMALL};
                font-size: {AppStyles.Sizes.FONT_NORMAL};
            }}
        """
    
    @staticmethod
    def original_data_label():
        """Панель оригінальних даних"""
        return f"""
            QLabel {{
                padding: 5px;
                background-color: {AppStyles.Colors.BG_WARNING};
                border: 1px solid {AppStyles.Colors.BORDER_WARNING};
                border-radius: {AppStyles.Sizes.RADIUS_MEDIUM};
                font-family: 'Courier New';
                font-size: {AppStyles.Sizes.FONT_SMALL};
            }}
        """
    
    # ==================== СТИЛІ ПОЛІВ ВВЕДЕННЯ ====================
    
    @staticmethod
    def input_field(font_size="11px", border_color=None):
        """Поле введення"""
        border = border_color or AppStyles.Colors.BORDER_DEFAULT
        return f"""
            QLineEdit {{
                padding: 5px;
                font-size: {font_size};
                border: 1px solid {border};
                border-radius: {AppStyles.Sizes.RADIUS_SMALL};
            }}
            QLineEdit:focus {{
                border: 2px solid {AppStyles.Colors.PRIMARY};
            }}
            QLineEdit:disabled {{
                background-color: {AppStyles.Colors.BG_LIGHT};
                color: {AppStyles.Colors.TEXT_LIGHT};
            }}
        """
    
    @staticmethod
    def input_index(font_size="16px", border_color=None):
        """Поле введення індексу (великі цифри)"""
        border = border_color or AppStyles.Colors.PRIMARY
        return f"""
            QLineEdit {{
                padding: 6px;
                font-size: {font_size};
                font-weight: bold;
                border: 2px solid {border};
                border-radius: {AppStyles.Sizes.RADIUS_LARGE};
                text-align: center;
            }}
            QLineEdit:focus {{
                border-color: {AppStyles.Colors.SUCCESS};
            }}
        """
    
    # ==================== СТИЛІ СПИСКІВ ====================
    
    @staticmethod
    def list_results():
        """Список результатів пошуку"""
        return f"""
            QListWidget {{
                border: 1px solid {AppStyles.Colors.BORDER_DEFAULT};
                background-color: white;
            }}
            QListWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {AppStyles.Colors.BG_DARK};
            }}
            QListWidget::item:alternate {{
                background-color: {AppStyles.Colors.ROW_ALTERNATE};
            }}
            QListWidget::item:hover {{
                background-color: {AppStyles.Colors.BG_LIGHT};
            }}
            QListWidget::item:selected {{
                background-color: transparent;
                color: {AppStyles.Colors.TEXT_DEFAULT};
            }}
            QListWidget::item:selected:hover {{
                background-color: {AppStyles.Colors.BG_LIGHTER};
            }}
        """
    
    @staticmethod
    def list_popup(border_color=None):
        """Popup список (автокомпліт)"""
        border = border_color or AppStyles.Colors.PRIMARY
        return f"""
            QListWidget {{
                border: 2px solid {border};
                border-radius: {AppStyles.Sizes.RADIUS_MEDIUM};
                background-color: white;
                font-size: {AppStyles.Sizes.FONT_NORMAL};
            }}
            QListWidget::item {{
                padding: 5px;
                border-bottom: 1px solid {AppStyles.Colors.BG_LIGHT};
            }}
            QListWidget::item:hover {{
                background-color: {AppStyles.Colors.BG_PRIMARY};
            }}
            QListWidget::item:selected {{
                background-color: {border};
                color: white;
            }}
        """
    
    # ==================== СТИЛІ КОМБОБОКСІВ ====================
    
    @staticmethod
    def combo_box(font_size="10px"):
        """Комбобокс"""
        return f"""
            QComboBox {{
                font-size: {font_size};
                padding: 2px;
                border: 1px solid {AppStyles.Colors.BORDER_DEFAULT};
                border-radius: {AppStyles.Sizes.RADIUS_SMALL};
            }}
            QComboBox:hover {{
                border-color: {AppStyles.Colors.PRIMARY};
            }}
        """
    
    # ==================== СТИЛІ ПРОГРЕС БАРУ ====================
    
    @staticmethod
    def progress_bar():
        """Прогрес бар"""
        return f"""
            QProgressBar {{
                border: 1px solid {AppStyles.Colors.BORDER_DEFAULT};
                border-radius: {AppStyles.Sizes.RADIUS_SMALL};
                text-align: center;
                background-color: {AppStyles.Colors.BG_LIGHT};
            }}
            QProgressBar::chunk {{
                background-color: {AppStyles.Colors.SUCCESS};
                border-radius: {AppStyles.Sizes.RADIUS_SMALL};
            }}
        """
    
    # ==================== HELPER МЕТОДИ ====================
    
    @staticmethod
    def apply_to_widget(widget, style_func, *args, **kwargs):
        """
        Застосовує стиль до віджета
        
        Args:
            widget: PyQt віджет
            style_func: Функція стилю з AppStyles
            *args, **kwargs: Параметри для функції стилю
        """
        style = style_func(*args, **kwargs)
        widget.setStyleSheet(style)
