"""
Обробка збереження/завантаження схем відповідності стовпців
"""
import json
import os
from typing import Dict, List, Optional
import config


class ColumnMappingHandler:
    """Клас для роботи зі схемами відповідності стовпців"""
    
    @staticmethod
    def save_mapping(name: str, mapping: Dict[str, List[int]]) -> bool:
        """
        Зберігає схему відповідності
        
        Args:
            name: Назва схеми
            mapping: Словник відповідності
            
        Returns:
            True якщо успішно
        """
        # Очищаємо ім'я від небезпечних символів
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '_', '-'))
        
        if not safe_name:
            return False
        
        file_path = os.path.join(config.COLUMN_MAPPINGS_DIR, f"{safe_name}.json")
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(mapping, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Помилка збереження схеми: {e}")
            return False
    
    @staticmethod
    def load_mapping(name: str) -> Optional[Dict[str, List[int]]]:
        """
        Завантажує схему відповідності
        
        Args:
            name: Назва схеми
            
        Returns:
            Словник відповідності або None
        """
        file_path = os.path.join(config.COLUMN_MAPPINGS_DIR, f"{name}.json")
        
        if not os.path.exists(file_path):
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Помилка завантаження схеми: {e}")
            return None
    
    @staticmethod
    def list_mappings() -> List[str]:
        """
        Повертає список доступних схем
        
        Returns:
            Список назв схем
        """
        if not os.path.exists(config.COLUMN_MAPPINGS_DIR):
            return []
        
        mappings = []
        for filename in os.listdir(config.COLUMN_MAPPINGS_DIR):
            if filename.endswith('.json'):
                mappings.append(filename[:-5])  # Без .json
        
        return sorted(mappings)
    
    @staticmethod
    def delete_mapping(name: str) -> bool:
        """
        Видаляє схему
        
        Args:
            name: Назва схеми
            
        Returns:
            True якщо успішно
        """
        file_path = os.path.join(config.COLUMN_MAPPINGS_DIR, f"{name}.json")
        
        if not os.path.exists(file_path):
            return False
        
        try:
            os.remove(file_path)
            return True
        except Exception as e:
            print(f"Помилка видалення схеми: {e}")
            return False
