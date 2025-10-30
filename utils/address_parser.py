"""
Парсинг адрес з повного тексту
"""
import re
from typing import Dict


def parse_full_address_text(text: str) -> Dict[str, str]:
    """
    Парсить повний текст адреси та витягує компоненти
    
    Args:
        text: Повний текст адреси
        
    Returns:
        Словник з компонентами: index, city, street, building
        
    Приклад:
        "02002, м. Київ, вул. Раїси Окіпної, буд. 4-Б, офіс 12"
        →
        {
            'index': '02002',
            'city': 'Київ',
            'street': 'Раїси Окіпної',
            'building': '4-Б'
        }
    """
    result = {
        'index': '',
        'city': '',
        'street': '',
        'building': ''
    }
    
    if not text or not isinstance(text, str):
        return result
    
    text = text.strip()
    
    # 1. Витягуємо індекс (5 цифр на початку)
    index_match = re.match(r'^(\d{5})', text)
    if index_match:
        result['index'] = index_match.group(1)
    
    # 2. Витягуємо місто
    city_patterns = [
        r'м\.\s*([^,]+)',      # м. Київ
        r'місто\s+([^,]+)',    # місто Київ
        r'с\.\s*([^,]+)',      # с. Петрівка
        r'смт\.\s*([^,]+)',    # смт. Буча
        r'селище\s+([^,]+)',   # селище Буча
    ]
    
    for pattern in city_patterns:
        city_match = re.search(pattern, text, re.IGNORECASE)
        if city_match:
            result['city'] = city_match.group(1).strip()
            break
    
    # 3. Витягуємо вулицю
    street_patterns = [
        r'вул\.\s*([^,]+)',           # вул. Раїси Окіпної
        r'вулиця\s+([^,]+)',          # вулиця Раїси Окіпної
        r'пров\.\s*([^,]+)',          # пров. Шевченка
        r'провулок\s+([^,]+)',        # провулок Шевченка
        r'бульв\.\s*([^,]+)',         # бульв. Лесі Українки
        r'бульвар\s+([^,]+)',         # бульвар Лесі Українки
        r'просп\.\s*([^,]+)',         # просп. Перемоги
        r'проспект\s+([^,]+)',        # проспект Перемоги
        r'пл\.\s*([^,]+)',            # пл. Незалежності
        r'площа\s+([^,]+)',           # площа Незалежності
    ]
    
    for pattern in street_patterns:
        street_match = re.search(pattern, text, re.IGNORECASE)
        if street_match:
            street_raw = street_match.group(1).strip()
            # Видаляємо все після "буд." або "будинок"
            street_clean = re.split(r',?\s*буд\.?|,?\s*будинок', street_raw, flags=re.IGNORECASE)[0]
            result['street'] = street_clean.strip()
            break
    
    # 4. Витягуємо будинок
    building_patterns = [
        r'буд\.\s*([^,]+)',           # буд. 4-Б
        r'будинок\s+([^,]+)',         # будинок 4-Б
        r'№\s*(\d+[А-Яа-яA-Za-z\-/]*)', # № 4-Б
    ]
    
    for pattern in building_patterns:
        building_match = re.search(pattern, text, re.IGNORECASE)
        if building_match:
            building_raw = building_match.group(1).strip()
            # Видаляємо "офіс", "кв.", тощо
            building_clean = re.split(r',?\s*офіс|,?\s*кв\.', building_raw, flags=re.IGNORECASE)[0]
            result['building'] = building_clean.strip()
            break
    
    return result


def is_full_address_in_text(text: str) -> bool:
    """
    Перевіряє чи текст містить повну адресу (індекс + місто/вулиця)
    
    Args:
        text: Текст для перевірки
        
    Returns:
        True якщо це схоже на повну адресу
    """
    if not text or not isinstance(text, str):
        return False
    
    # Має бути індекс на початку ТА місто/вулиця
    return bool(re.match(r'^\d{5}.*?(м\.|вул\.|с\.|смт\.)', text, re.IGNORECASE))