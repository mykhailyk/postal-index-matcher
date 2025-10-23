"""
Утиліти для нормалізації тексту
"""
import re
from typing import Optional


def normalize_text(text: str) -> str:
    """
    Нормалізує текст для порівняння
    
    Args:
        text: Вхідний текст
        
    Returns:
        Нормалізований текст
    """
    if not text:
        return ""
    
    # Приводимо до нижнього регістру
    text = text.lower()
    
    # Видаляємо зайві пробіли
    text = ' '.join(text.split())
    
    # Видаляємо спецсимволи
    text = re.sub(r'[^\w\s\-]', '', text)
    
    return text.strip()


def normalize_street_name(street: str) -> str:
    """
    Нормалізує назву вулиці
    
    Args:
        street: Назва вулиці
        
    Returns:
        Нормалізована назва
    """
    if not street:
        return ""
    
    # Видаляємо префікси типу "вул.", "пров.", "бульв."
    prefixes = [
        r'вул\.?\s+',
        r'вулиця\s+',
        r'пров\.?\s+',
        r'провулок\s+',
        r'бульв\.?\s+',
        r'бульвар\s+',
        r'просп\.?\s+',
        r'проспект\s+',
        r'пл\.?\s+',
        r'площа\s+',
    ]
    
    for prefix in prefixes:
        street = re.sub(prefix, '', street, flags=re.IGNORECASE)
    
    return normalize_text(street)


def normalize_city_name(city: str) -> str:
    """
    Нормалізує назву міста
    
    Args:
        city: Назва міста
        
    Returns:
        Нормалізована назва
    """
    if not city:
        return ""
    
    # Видаляємо префікси типу "м.", "с.", "смт."
    prefixes = [
        r'м\.?\s+',
        r'місто\s+',
        r'с\.?\s+',
        r'село\s+',
        r'смт\.?\s+',
        r'селище\s+міського\s+типу\s+',
        r'сел\.?\s+',
        r'селище\s+',
    ]
    
    for prefix in prefixes:
        city = re.sub(prefix, '', city, flags=re.IGNORECASE)
    
    return normalize_text(city)


def extract_building_from_street(street: str) -> tuple:
    """
    Витягує номер будинку з назви вулиці
    
    Args:
        street: Назва вулиці (можливо з номером будинку)
        
    Returns:
        Tuple (вулиця без номера, номер будинку)
    """
    if not street:
        return street, ""
    
    # Шукаємо номер будинку в кінці рядка
    # Формати: "40-А", "40А", "40/2", "40 А", "40"
    pattern = r'^(.+?)\s+(\d+[-/\s]?[А-Яа-яA-Za-z]*)$'
    match = re.match(pattern, street.strip())
    
    if match:
        clean_street = match.group(1).strip()
        building = match.group(2).strip()
        
        # Якщо це справді номер будинку (не частина назви)
        if building and re.match(r'^\d+', building):
            return clean_street, building
    
    return street, ""


def extract_building_number(building: str) -> Optional[str]:
    """
    Витягує основний номер будинку (без літер)
    
    Args:
        building: Номер будинку (наприклад "40А", "40-А", "40/2")
        
    Returns:
        Основний номер або None
    """
    if not building:
        return None
    
    match = re.match(r'^(\d+)', str(building).strip())
    if match:
        return match.group(1)
    
    return None


def clean_whitespace(text: str) -> str:
    """
    Очищає зайві пробіли
    
    Args:
        text: Вхідний текст
        
    Returns:
        Текст без зайвих пробілів
    """
    if not text:
        return ""
    
    return ' '.join(text.split())
