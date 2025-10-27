"""
Менеджер Undo/Redo операцій
"""
from typing import List, Dict, Any


class UndoManager:
    """Менеджер для відміни/повтору дій"""
    
    def __init__(self, max_stack_size: int = 50):
        """
        Ініціалізація менеджера
        
        Args:
            max_stack_size: Максимальна кількість збережених дій
        """
        self.undo_stack: List[Dict[str, Any]] = []
        self.redo_stack: List[Dict[str, Any]] = []
        self.max_stack_size = max_stack_size
    
    def push(self, action: Dict[str, Any]):
        """
        Додає дію до стеку undo
        
        Args:
            action: Словник з інформацією про дію
                   Обов'язково містить:
                   - 'row': номер рядка
                   - 'old_values': словник старих значень
                   - 'new_values': словник нових значень
        """
        self.undo_stack.append(action)
        
        # Обмежуємо розмір стеку
        if len(self.undo_stack) > self.max_stack_size:
            self.undo_stack.pop(0)
        
        # Очищаємо redo при новій дії
        self.redo_stack.clear()
    
    def can_undo(self) -> bool:
        """Перевіряє чи можна відмінити"""
        return len(self.undo_stack) > 0
    
    def can_redo(self) -> bool:
        """Перевіряє чи можна повторити"""
        return len(self.redo_stack) > 0
    
    def undo(self) -> Dict[str, Any]:
        """
        Відміняє останню дію
        
        Returns:
            Дія для відміни або None якщо стек пустий
        """
        if not self.can_undo():
            return None
        
        action = self.undo_stack.pop()
        self.redo_stack.append(action)
        
        return action
    
    def redo(self) -> Dict[str, Any]:
        """
        Повторює відмінену дію
        
        Returns:
            Дія для повтору або None якщо стек пустий
        """
        if not self.can_redo():
            return None
        
        action = self.redo_stack.pop()
        self.undo_stack.append(action)
        
        return action
    
    def clear(self):
        """Очищає всі стеки"""
        self.undo_stack.clear()
        self.redo_stack.clear()
    
    def get_undo_count(self) -> int:
        """Повертає кількість доступних undo"""
        return len(self.undo_stack)
    
    def get_redo_count(self) -> int:
        """Повертає кількість доступних redo"""
        return len(self.redo_stack)
    
    def peek_undo(self) -> Dict[str, Any]:
        """
        Переглянути останню undo дію без видалення
        
        Returns:
            Остання дія або None
        """
        if self.can_undo():
            return self.undo_stack[-1]
        return None
    
    def peek_redo(self) -> Dict[str, Any]:
        """
        Переглянути останню redo дію без видалення
        
        Returns:
            Остання дія або None
        """
        if self.can_redo():
            return self.redo_stack[-1]
        return None
