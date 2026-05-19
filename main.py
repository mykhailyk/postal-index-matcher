"""
PrintTo Address Matcher v2.2
Головний файл програми
"""

import sys
import os
from datetime import datetime
import faulthandler
import threading
import traceback


DEBUG_FLAGS = {'--debug', '-d'}
DEBUG_MODE = (
    any(arg in DEBUG_FLAGS for arg in sys.argv[1:])
    or os.environ.get('ADDRESS_MATCHER_DEBUG', '').lower() in {'1', 'true', 'yes', 'on'}
)
RUN_TIMESTAMP = datetime.now().strftime('%Y%m%d_%H%M%S')


def _runtime_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _logs_dir():
    logs_dir = os.path.join(_runtime_base_dir(), 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    return logs_dir


DEBUG_LOG_FILE = os.path.join(_logs_dir(), f'debug_{RUN_TIMESTAMP}.log')
FATAL_LOG_FILE = os.path.join(_logs_dir(), f'fatal_{RUN_TIMESTAMP}.log')


def _write_debug(message):
    try:
        with open(DEBUG_LOG_FILE, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f'[{timestamp}] {message.rstrip()}\n')
    except Exception:
        pass


def _write_fatal(message):
    try:
        with open(FATAL_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(message)
            if not message.endswith('\n'):
                f.write('\n')
    except Exception:
        pass


def _install_debug_hooks():
    if not DEBUG_MODE:
        return

    _write_debug('Debug mode enabled')
    _write_debug(f'Python: {sys.version}')
    _write_debug(f'Executable: {sys.executable}')
    _write_debug(f'CWD: {os.getcwd()}')
    _write_debug(f'ARGV: {sys.argv}')

    try:
        fault_file = open(os.path.join(_logs_dir(), f'faulthandler_{RUN_TIMESTAMP}.log'), 'a', encoding='utf-8')
        faulthandler.enable(file=fault_file, all_threads=True)
    except Exception as exc:
        _write_debug(f'Cannot enable faulthandler: {exc}')

    def excepthook(exc_type, exc_value, exc_traceback):
        details = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        _write_debug('Unhandled exception:\n' + details)
        _write_fatal(details)
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = excepthook

    def threading_excepthook(args):
        details = ''.join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        _write_debug(f'Unhandled thread exception in {args.thread.name}:\n{details}')
        _write_fatal(details)

    threading.excepthook = threading_excepthook


_install_debug_hooks()

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

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt, qInstallMessageHandler
import config

# Імпортуємо logger
from utils.logger import Logger

# Імпортуємо головне вікно
from ui.main_window import MainWindow


def _install_qt_debug_handler():
    if not DEBUG_MODE:
        return

    def qt_message_handler(mode, context, message):
        location = ''
        if context.file:
            location = f' ({context.file}:{context.line})'
        _write_debug(f'Qt[{mode}]{location}: {message}')

    qInstallMessageHandler(qt_message_handler)


def main():
    """Головна функція"""
    _install_qt_debug_handler()
    
    # ========================================================================
    # ВАЖЛИВО: High DPI ПЕРЕД створенням QApplication
    # ========================================================================
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    # Ініціалізуємо logger
    logger = Logger()
    logger.info("="*80)
    logger.info("Запуск PrintTo Address Matcher v2.1")
    logger.info("="*80)
    if DEBUG_MODE:
        logger.info(f"DEBUG MODE: {DEBUG_LOG_FILE}")
        logger.info(f"FATAL LOG: {FATAL_LOG_FILE}")
    
    # Створюємо додаток (ПІСЛЯ налаштування High DPI)
    qt_args = [sys.argv[0]] + [arg for arg in sys.argv[1:] if arg not in DEBUG_FLAGS]
    app = QApplication(qt_args)
    app.setApplicationName(config.WINDOW_TITLE)
    
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
    except Exception:
        # Якщо критична помилка - пишемо в лог
        error_msg = f"КРИТИЧНА ПОМИЛКА:\n{traceback.format_exc()}"
        _write_debug(error_msg)
        _write_fatal(error_msg)
        
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
