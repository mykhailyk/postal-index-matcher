"""
Система логування
"""
import logging
import os
from datetime import datetime
import config


class Logger:
    """Клас для логування подій"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._setup_logger()
    
    def _setup_logger(self):
        """Налаштовує logger"""
        # Створюємо директорію для логів
        os.makedirs(config.LOGS_DIR, exist_ok=True)
        
        # Налаштовуємо форматування
        formatter = logging.Formatter(
            config.LOG_FORMAT,
            datefmt=config.LOG_DATE_FORMAT
        )
        
        # File handler
        file_handler = logging.FileHandler(
            config.LOG_FILE,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        # Logger
        self.logger = logging.getLogger('AddressMatcher')
        self.logger.setLevel(getattr(logging, config.LOG_LEVEL))
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def debug(self, message: str):
        """Debug рівень"""
        self.logger.debug(message)
    
    def info(self, message: str):
        """Info рівень"""
        self.logger.info(message)
    
    def warning(self, message: str):
        """Warning рівень"""
        self.logger.warning(message)
    
    def error(self, message: str):
        """Error рівень"""
        self.logger.error(message)
    
    def critical(self, message: str):
        """Critical рівень"""
        self.logger.critical(message)
