"""
Модель адреси
"""


class Address:
    """Модель адреси клієнта"""
    
    def __init__(self, city="", street="", building="", region="", 
                 district="", index="", old_index="", client_id="", name=""):
        self.city = city
        self.street = street
        self.building = building
        self.region = region
        self.district = district
        self.index = index
        self.old_index = old_index
        self.client_id = client_id
        self.name = name
    
    def to_dict(self):
        """Конвертує адресу в словник"""
        return {
            'city': self.city,
            'street': self.street,
            'building': self.building,
            'region': self.region,
            'district': self.district,
            'index': self.index,
            'old_index': self.old_index,
            'client_id': self.client_id,
            'name': self.name
        }
    
    def __repr__(self):
        return f"Address(city={self.city}, street={self.street}, building={self.building}, index={self.index})"
    
    def is_empty(self):
        """Перевіряє чи адреса порожня"""
        return not any([self.city, self.street, self.building, self.region])
    
    def get_full_address(self):
        """Повертає повну адресу як рядок"""
        parts = []
        if self.region:
            parts.append(self.region)
        if self.district:
            parts.append(self.district)
        if self.city:
            parts.append(self.city)
        if self.street:
            parts.append(self.street)
        if self.building:
            parts.append(f"буд. {self.building}")
        
        return ", ".join(parts)
