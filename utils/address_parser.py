"""
Парсинг адрес з повного тексту
"""
import re
from typing import Dict


def parse_full_address_text(text: str) -> Dict[str, str]:
    """
    Парсить повний текст адреси та витягує компоненти
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
    
    # 2. Витягуємо місто (РОЗШИРЕНО!)
    city_patterns = [
        r'м\.\s*([^,]+)',          # м. Київ
        r'місто\s+([^,]+)',        # місто Київ
        r'с\.\s*([^,]+)',          # с. Петрівка
        r'смт\.\s*([^,]+)',        # смт. Буча
        r'селище\s+([^,]+)',       # селище Буча
        r',\s*([А-ЯІЇЄҐ][а-яіїєґ\'`-]+),',  # ", Херсонська, " або ", Київ, "
    ]
    
    for pattern in city_patterns:
        city_match = re.search(pattern, text, re.IGNORECASE)
        if city_match:
            city = city_match.group(1).strip()
            # Фільтруємо області
            if not any(x in city.lower() for x in ['область', 'обл.', 'район', 'р-н']):
                result['city'] = city
                break
    
    # 3. Витягуємо вулицю (РОЗШИРЕНО!)
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
        r'кв\.\s*([^,]+)',            # кв. Волкова (квартал)
        r'квартал\s+([^,]+)',         # квартал Волкова
    ]
    
    for pattern in street_patterns:
        street_match = re.search(pattern, text, re.IGNORECASE)
        if street_match:
            street_raw = street_match.group(1).strip()
            # Видаляємо все після "буд." або цифр будинку
            street_clean = re.split(r',?\s*буд\.?|,?\s*будинок|,?\s*\d+[а-яА-Яa-zA-Z\-/]*\s*,', 
                                   street_raw, flags=re.IGNORECASE)[0]
            result['street'] = street_clean.strip()
            break
    
    # 4. Витягуємо будинок (РОЗШИРЕНО!)
    building_patterns = [
        r'буд\.\s*([^,]+)',                    # буд. 4-Б
        r'будинок\s+([^,]+)',                  # будинок 4-Б
        r'd\.\s*(\d+[а-яА-Яa-zA-Z\-/]*)',      # d.208
        r'д\.?\s*(\d+[а-яА-Яa-zA-Z\-/]*)',     # д.208 або д208
        r',\s*(\d+[а-яА-Яa-zA-Z\-/]*)\s*,',    # , 20-а,
        r',\s*(\d+[а-яА-Яa-zA-Z\-/]*)\s*$',    # закінчується на ", 48"
    ]
    
    for pattern in building_patterns:
        building_match = re.search(pattern, text, re.IGNORECASE)
        if building_match:
            building_raw = building_match.group(1).strip()
            # Видаляємо "офіс", "кв.", "корп." тощо
            building_clean = re.split(r',?\s*офіс|,?\s*кв\.|,?\s*корп\.', 
                                     building_raw, flags=re.IGNORECASE)[0]
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