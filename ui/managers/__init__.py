"""
Менеджери бізнес-логіки для UI

Цей пакет містить менеджери, які інкапсулюють бізнес-логіку
та надають простий інтерфейс для UI компонентів.
"""

from .file_manager import FileManager
from .search_manager import SearchManager
from .processing_manager import ProcessingManager
from .ui_state_manager import UIStateManager

__all__ = [
    'FileManager',
    'SearchManager',
    'ProcessingManager',
    'UIStateManager'
]
