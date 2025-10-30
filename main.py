"""
PrintTo Address Matcher v2.1
Головний файл програми
"""

import sys
import os
from datetime import datetime

# ============================================================================
# ПЕРЕНАПРАВЛЕННЯ STDOUT/STDERR В ЛОГИ (для EXE без консолі)
# ============================================================================

class StdoutLogger:
    """Перенаправляє stdout в лог файл"""
    
    def __init__(self, log_file):
        self.log_file = log_file
        
    def write(self, message):
        if message.strip():  # Не писати пусті рядки
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    f.write(f"[{timestamp}] {message}\n")
                    f.flush()
            except:
                pass  # Ігноруємо помилки запису
    
    def flush(self):
        pass


class StderrLogger:
    """Перенаправляє stderr в лог файл"""
    
    def __init__(self, log_file):
        self.log_file = log_file
        
    def write(self, message):
        if message.strip():  # Не писати пусті рядки
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    f.write(f"[{timestamp}] ERROR: {message}\n")
                    f.flush()
            except:
                pass  # Ігноруємо помилки запису
    
    def flush(self):
        pass


# Налаштовуємо перенаправлення (ТІЛЬКИ для EXE)
if getattr(sys, 'frozen', False):
    # Програма запущена як EXE
    base_dir = os.path.dirname(sys.executable)
    logs_dir = os.path.join(base_dir, 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    # Файл для всього console output
    log_file = os.path.join(logs_dir, 'console_output.log')
    
    # Перенаправляємо stdout і stderr
    sys.stdout = StdoutLogger(log_file)
    sys.stderr = StderrLogger(log_file)
    
    # Записуємо початок сесії
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write("\n" + "="*80 + "\n")
        f.write(f"Програма запущена: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*80 + "\n\n")

# ============================================================================
# ЗВИЧАЙНІ ІМПОРТИ (після перенаправлення)
# ============================================================================

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
import config

# Імпортуємо logger
from utils.logger import Logger

# Імпортуємо головне вікно
from ui.main_window import MainWindow


def main():
    """Головна функція"""
    
    # Ініціалізуємо logger
    logger = Logger()
    logger.info("="*80)
    logger.info("Запуск PrintTo Address Matcher v2.1")
    logger.info("="*80)
    
    # Створюємо додаток
    app = QApplication(sys.argv)
    app.setApplicationName(config.WINDOW_TITLE)
    
    # Високе DPI розширення для Windows
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    logger.info("Створення головного вікна...")
    
    # Створюємо і показуємо головне вікно
    window = MainWindow()
    window.show()
    
    logger.info("Програма готова до роботи")
    
    # Запускаємо event loop
    sys.exit(app.exec_())


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        # Якщо критична помилка - пишемо в лог
        import traceback
        error_msg = f"КРИТИЧНА ПОМИЛКА:\n{traceback.format_exc()}"
        
        # Виводимо (піде в console_output.log якщо EXE)
        print(error_msg)
        
        # Також пишемо в основний лог якщо можливо
        try:
            logger = Logger()
            logger.critical(error_msg)
        except:
            pass
        
        # Спробуємо показати діалог
        try:
            from PyQt5.QtWidgets import QMessageBox, QApplication
            app = QApplication.instance()
            if app is None:
                app = QApplication(sys.argv)
            
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("Помилка запуску")
            msg.setText("Не вдалося запустити програму")
            msg.setDetailedText(error_msg)
            msg.exec_()
        except:
            pass
        
        sys.exit(1)