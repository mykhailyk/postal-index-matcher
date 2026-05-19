"""
Індекс Укрпошти - швидкий пошук міст/вулиць/індексів
"""
import os
import pickle
from collections import defaultdict


class UkrposhtaIndex:
    """Індекс для швидкого пошуку по базі Укрпошти"""
    
    def __init__(self):
        self.city_by_prefix = {}
        self.city_data = {}
        self.magistral_cache = []
        self.cache_file = os.path.join('cache', 'ukrposhta_v2.pkl')
    
    def build(self, magistral_records):
        """Будує індекс з magistral.csv"""
        print("🔨 Побудова індексу Укрпошти v2...")
        
        # Зберігаємо кеш для get_buildings
        self.magistral_cache = magistral_records
        
        cities_data = defaultdict(lambda: {'streets': set(), 'display': None})
        
        for record in magistral_records:
            city_raw = getattr(record, 'city', None)
            
            if not city_raw:
                continue
            
            # Формуємо повну назву міста
            district = getattr(record, 'new_district', None) or getattr(record, 'old_district', None)
            region = getattr(record, 'region', None)
            
            # Варіанти відображення
            if district and region:
                city_display = f"{city_raw}, {district}, {region}"
            elif region:
                city_display = f"{city_raw}, {region}"
            else:
                city_display = city_raw
            
            # Зберігаємо
            if cities_data[city_display]['display'] is None:
                cities_data[city_display]['display'] = city_display
            
            # Додаємо вулицю
            street = getattr(record, 'street', None)
            if street:
                cities_data[city_display]['streets'].add(street)
        
        # Будуємо індекс по префіксам
        print(f"📊 Всього міст: {len(cities_data)}")
        
        for city_full, data in cities_data.items():
            # Беремо перше слово (без префіксів м., с., смт.)
            city_name = city_full.split(',')[0].strip()
            
            # Видаляємо префікси для генерації ключів
            city_name_clean = city_name
            for prefix in ['м. ', 'смт. ', 'с. ', 'с-ще ']:
                if city_name_clean.startswith(prefix):
                    city_name_clean = city_name_clean[len(prefix):]
                    break
            
            # Генеруємо префікси для ОБОХ варіантів
            for name_variant in [city_name_clean, city_name]:
                if len(name_variant) >= 3:
                    for i in range(3, min(len(name_variant) + 1, 8)):
                        prefix = name_variant[:i].lower()
                        
                        if prefix not in self.city_by_prefix:
                            self.city_by_prefix[prefix] = []
                        
                        if city_full not in self.city_by_prefix[prefix]:
                            self.city_by_prefix[prefix].append(city_full)
            
            # Зберігаємо дані міста
            self.city_data[city_full] = {
                'streets': list(data['streets']),
                'display': data['display']
            }
        
        print(f"✅ Індекс побудовано. Префіксів: {len(self.city_by_prefix)}")
        
        # Зберігаємо в кеш
        self.save()
    
    def save(self):
            """Зберігає індекс у файл БЕЗ компресії (швидше!)"""
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            
            data = {
                'city_by_prefix': self.city_by_prefix,
                'city_data': self.city_data
            }
            
            # Зберігаємо БЕЗ компресії - швидше в 30+ разів
            with open(self.cache_file, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            print(f"💾 Індекс Укрпошти збережено в {self.cache_file}")
    
    def load(self):
            """Завантажує індекс з файлу БЕЗ компресії (швидше!)"""
            
            # Видаляємо старий .xz файл якщо є
            cache_xz = self.cache_file + '.xz'
            if os.path.exists(cache_xz):
                try:
                    os.remove(cache_xz)
                    print("✓ Видалено старий .xz кеш")
                except:
                    pass
            
            # Перевіряємо новий файл
            if not os.path.exists(self.cache_file):
                print("⚠️ Кеш індексу Укрпошти не знайдено")
                return False
            
            try:
                with open(self.cache_file, 'rb') as f:
                    data = pickle.load(f)
                
                self.city_by_prefix = data['city_by_prefix']
                self.city_data = data['city_data']
                
                # magistral_cache буде встановлено ззовні через set_magistral_cache()
                print(f"✅ Індекс Укрпошти завантажено з кешу ({len(self.city_data)} міст)")
                
                return True
                
            except Exception as e:
                print(f"❌ Помилка завантаження кешу: {e}")
                # Видаляємо пошкоджений кеш
                try:
                    os.remove(self.cache_file)
                except:
                    pass
                return False
    
    def search_cities(self, query):
        """Шукає міста - МІСТА ПЕРШИМИ"""
        if len(query) < 3:
            return []
        
        query_lower = query.lower()
        prefix = query_lower[:3]
        
        candidates = self.city_by_prefix.get(prefix, [])
        
        # Фільтруємо
        results = [c for c in candidates if query_lower in c.lower()]
        
        # СОРТУВАННЯ: м. > смт. > с. > с-ще
        def city_sort_key(city):
            city_part = city.split(',')[0].strip()
            if city_part.startswith('м. '):
                return (0, city)
            elif city_part.startswith('смт. '):
                return (1, city)
            elif city_part.startswith('с. '):
                return (2, city)
            elif city_part.startswith('с-ще '):
                return (3, city)
            else:
                return (4, city)
        
        results = sorted(results, key=city_sort_key)
        
        return results[:10]
    
    def get_streets(self, city_full):
        """Повертає список вулиць для міста"""
        data = self.city_data.get(city_full, {})
        return data.get('streets', [])
    
    def get_buildings(self, city_full, street):
        """Повертає мапу будинків -> індекси для вулиці"""
        # Беремо назву міста без району/області
        city_name = city_full.split(',')[0].strip()
        
        # Шукаємо всі записи для цього міста і вулиці
        buildings_map = {}
        
        for record in self.magistral_cache:
            record_city = getattr(record, 'city', None)
            record_street = getattr(record, 'street', None)
            
            if not record_city or not record_street:
                continue
            
            # Порівнюємо місто (враховуємо префікси)
            if city_name.lower() in record_city.lower() or record_city.lower() in city_name.lower():
                # Порівнюємо вулицю
                if street.lower() in record_street.lower():
                    idx = getattr(record, 'city_index', None)
                    buildings = getattr(record, 'buildings', None)
                    
                    if idx:
                        idx_str = str(idx)
                        if idx_str not in buildings_map:
                            buildings_map[idx_str] = buildings if buildings else ""
        
        return buildings_map
