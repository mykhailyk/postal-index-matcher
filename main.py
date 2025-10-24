"""
Головний модуль GUI програми підбору поштових індексів
"""
import sys
from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow
from utils.logger import Logger


def main():
    """Точка входу програми"""
    logger = Logger()
    logger.info("=" * 80)
    logger.info("Запуск програми Address Matcher v2.1")
    logger.info("=" * 80)
    
    try:
        app = QApplication(sys.argv)
        app.setStyle('Fusion')  # Сучасний стиль
        
        window = MainWindow()
        window.show()
        
        logger.info("GUI ініціалізовано")
        
        sys.exit(app.exec_())
        
    except Exception as e:
        logger.critical(f"Критична помилка: {e}")
        raise


if __name__ == '__main__':
    main()
