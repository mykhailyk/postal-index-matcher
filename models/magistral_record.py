"""
Модель запису з magistral.csv
"""
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class MagistralRecord:
    """Запис з magistral.csv"""
    
    region: str = ""                    # Область
    old_district: str = ""              # Старий адм. район
    new_district: str = ""              # Новий адм. район
    otg: str = ""                       # ОТГ
    city: str = ""                      # Населений пункт
    city_index: str = ""                # Індекс НП
    street: str = ""                    # Вулиця
    buildings: str = ""                 # Будинки (через кому)
    sort_center_1: str = ""             # Сорт. центр 1
    sort_center_2: str = ""             # Сорт. центр 2
    delivery_district: str = ""         # Адм. район доставки
    tech_index: str = ""                # Тех. індекс
    features: str = ""                  # Особливості
    not_working: str = ""               # Тимчасово не функціонує
    
    # Додаткові обчислювані поля
    normalized_city: str = ""
    normalized_street: str = ""
    normalized_region: str = ""
    
    def __str__(self):
        return f"{self.region} → {self.city} → {self.street} ({self.city_index})"
    
    def to_dict(self):
        """Конвертує в словник"""
        return {
            'region': self.region,
            'district': self.new_district or self.old_district,
            'city': self.city,
            'street': self.street,
            'buildings': self.buildings,
            'index': self.city_index,
            'features': self.features,
            'not_working': self.not_working
        }
    
    def get_buildings_list(self) -> List[str]:
        """Повертає список будинків"""
        if not self.buildings:
            return []
        return [b.strip() for b in self.buildings.split(',')]
    
    def has_building(self, building: str) -> bool:
        """Перевіряє чи є будинок в списку"""
        if not building or not self.buildings:
            return False
        
        building = building.strip()
        buildings_list = self.get_buildings_list()
        
        return building in buildings_list
    
    def is_working(self) -> bool:
        """Перевіряє чи працює ВПЗ"""
        return not self.not_working or self.not_working.lower() == ''
