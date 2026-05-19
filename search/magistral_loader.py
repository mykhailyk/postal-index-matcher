"""
Завантаження та індексування magistral.csv
"""
import csv
import pickle
import os
import builtins
import sys
from typing import List, Dict
from models.magistral_record import MagistralRecord
from search.normalizer import TextNormalizer
import config


def print(*args, **kwargs):
    try:
        builtins.print(*args, **kwargs)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, 'encoding', None) or 'utf-8'
        safe_args = [
            str(arg).encode(encoding, errors='replace').decode(encoding)
            for arg in args
        ]
        builtins.print(*safe_args, **kwargs)


class MagistralLoader:
    """Клас для завантаження magistral.csv"""
    
    def __init__(self):
        self.normalizer = TextNormalizer()
        self.records: List[MagistralRecord] = []
        self.index_by_city_prefix: Dict[str, List[int]] = {}
        self.index_by_region: Dict[str, List[int]] = {}
    
    def load(self, force_reload: bool = False) -> List[MagistralRecord]:
        """
        Завантажує magistral.csv
        
        Args:
            force_reload: Примусово перечитати CSV (ігнорувати кеш)
            
        Returns:
            Список MagistralRecord
        """
        # Шлях до кешу БЕЗ компресії (швидше!)
        cache_path = config.MAGISTRAL_CACHE_PATH
        
        # Перевіряємо кеш (якщо НЕ примусове завантаження)
        if not force_reload and os.path.exists(cache_path):
            try:
                print(f"📦 Завантаження з кешу: {cache_path}")
                return self._load_from_cache()
            except Exception as e:
                print(f"⚠️ Помилка завантаження кешу: {e}")
                print("📄 Перехід до завантаження з CSV...")
        
        # ⬇️ ЯКЩО кешу немає АБО force_reload - завантажуємо з CSV
        
        # Видаляємо старий кеш якщо є
        if os.path.exists(config.MAGISTRAL_CACHE_PATH):
            try:
                os.remove(config.MAGISTRAL_CACHE_PATH)
                print("✓ Старий кеш видалено")
            except:
                pass
        
        # Завантажуємо з CSV
        print("📄 Завантаження magistral.csv...")
        self._load_from_csv()
        
        # Будуємо індекси
        print("🔨 Побудова індексів...")
        self._build_indexes()
        
        # Зберігаємо в кеш
        print("💾 Збереження в кеш...")
        self._save_to_cache()
        
        print(f"✅ Завантажено {len(self.records)} записів")
        return self.records

    
    def _load_from_csv(self):
        """Завантажує дані з CSV"""
        self.records = []
        
        # Спробуємо різні кодування
        encodings = ['utf-8', 'cp1251', 'windows-1251', 'iso-8859-1', 'latin1']
        
        csv_data = None
        used_encoding = None
        
        for encoding in encodings:
            try:
                with open(config.MAGISTRAL_CSV_PATH, 'r', encoding=encoding) as f:
                    # Пробуємо прочитати перший рядок
                    f.readline()
                    f.seek(0)
                    
                    # Якщо успішно - використовуємо це кодування
                    reader = csv.DictReader(f, delimiter=';')
                    csv_data = list(reader)
                    used_encoding = encoding
                    break
            except (UnicodeDecodeError, UnicodeError):
                continue
        
        if csv_data is None:
            raise ValueError("Не вдалося визначити кодування CSV файлу")
        
        print(f"✓ Використано кодування: {used_encoding}")
        
        # Обробляємо дані
        for row in csv_data:
            row = {key.strip().lstrip('\ufeff'): value for key, value in row.items() if key}

            record = MagistralRecord(
                region=row.get('Область', '').strip(),
                old_district=row.get('Адміністративний район(старий)', '').strip(),
                new_district=row.get('Адміністративний район(новий)', '').strip(),
                otg=row.get('Найменування ОТГ(довідково)', '').strip(),
                city=row.get('Населений пункт', '').strip(),
                city_index=row.get('Індекс НП', '').strip(),
                street=row.get('Назва вулиці', '').strip(),
                buildings=row.get('№ будинку', '').strip(),
                sort_center_1=row.get('сортувальний центр 1 рівня', '').strip(),
                sort_center_2=row.get('сортувальний центр 2 рівня', '').strip(),
                delivery_district=row.get('Адміністративний район доставки(вручення)', '').strip(),
                tech_index=row.get('Технологічний індекс ОПЗ доставки(вручення)', '').strip(),
                features=row.get('Особливості функціонування ВПЗ', '').strip(),
                not_working=row.get('Тимчасово не функціонує', '').strip()
            )
            
            # Нормалізуємо для пошуку
            record.normalized_city = self.normalizer.normalize_city(record.city)
            record.normalized_street = self.normalizer.normalize_street(record.street)
            record.normalized_region = self.normalizer.normalize_region(record.region)
            
            self.records.append(record)
    
    def _build_indexes(self):
        """Будує індекси для швидкого пошуку"""
        self.index_by_city_prefix = {}
        self.index_by_region = {}
        
        for i, record in enumerate(self.records):
            # Індекс по перших 2-3 літерах міста
            if record.normalized_city and len(record.normalized_city) >= 2:
                for prefix_len in [2, 3]:
                    if len(record.normalized_city) >= prefix_len:
                        prefix = record.normalized_city[:prefix_len]
                        if prefix not in self.index_by_city_prefix:
                            self.index_by_city_prefix[prefix] = []
                        self.index_by_city_prefix[prefix].append(i)
            
            # Індекс по області
            if record.normalized_region:
                if record.normalized_region not in self.index_by_region:
                    self.index_by_region[record.normalized_region] = []
                self.index_by_region[record.normalized_region].append(i)
        
        print(f"✓ Індекс міст: {len(self.index_by_city_prefix)} префіксів")
        print(f"✓ Індекс областей: {len(self.index_by_region)} областей")
    
    def _save_to_cache(self):
        """Зберігає в pickle кеш БЕЗ компресії (швидше!)"""
        cache_path = config.MAGISTRAL_CACHE_PATH
        
        cache_data = {
            'records': self.records,
            'index_by_city_prefix': self.index_by_city_prefix,
            'index_by_region': self.index_by_region
        }
        
        # Зберігаємо БЕЗ компресії - у 4-6 разів швидше!
        with open(cache_path, 'wb') as f:
            pickle.dump(cache_data, f, protocol=pickle.HIGHEST_PROTOCOL)
    
    def _load_from_cache(self) -> List[MagistralRecord]:
        """Завантажує з pickle кешу БЕЗ компресії (швидше!)"""
        cache_path = config.MAGISTRAL_CACHE_PATH
        
        try:
            # Завантажуємо БЕЗ компресії - у 4-6 разів швидше!
            with open(cache_path, 'rb') as f:
                cache_data = pickle.load(f)
            
            self.records = cache_data['records']
            self.index_by_city_prefix = cache_data['index_by_city_prefix']
            self.index_by_region = cache_data['index_by_region']
            
            print(f"✅ Завантажено з кешу: {len(self.records)} записів")
            return self.records
        
        except Exception as e:
            print(f"⚠️ Помилка завантаження кешу: {e}")
            # Видаляємо пошкоджений кеш
            try:
                os.remove(cache_path)
            except:
                pass
            # Перезавантажуємо з CSV
            return self.load(force_reload=True)
    
    def get_candidates_by_city_prefix(self, city: str) -> List[MagistralRecord]:
        """Швидкий пошук по префіксу міста"""
        if not city or len(city) < 2:
            return []
        
        city_norm = self.normalizer.normalize_city(city)
        prefix = city_norm[:2]
        
        if prefix not in self.index_by_city_prefix:
            return []
        
        indices = self.index_by_city_prefix[prefix]
        return [self.records[i] for i in indices]
    
    def get_candidates_by_region(self, region: str) -> List[MagistralRecord]:
        """Швидкий пошук по області"""
        if not region:
            return []
        
        region_norm = self.normalizer.normalize_region(region)
        
        if region_norm not in self.index_by_region:
            return []
        
        indices = self.index_by_region[region_norm]
        return [self.records[i] for i in indices]

    def get_min_index_for_city(self, city: str, region: str = None, district: str = None) -> str:
        """
        Знаходить найменший індекс для міста (для загального результату)
        """
        if not city:
            return ""
            
        candidates = self.get_candidates_by_city_prefix(city)
        if not candidates:
            return ""
            
        # Нормалізуємо для порівняння
        norm_city = self.normalizer.normalize_city(city)
        norm_region = self.normalizer.normalize_region(region) if region else None
        
        valid_indices = []
        
        for record in candidates:
            # Перевіряємо місто
            if record.normalized_city != norm_city:
                continue
                
            # Перевіряємо область якщо задана
            if norm_region and record.normalized_region != norm_region:
                continue
                
            # Перевіряємо район якщо заданий (нестрого, бо райони мінялись)
            if district:
                # Тут можна додати логіку перевірки району, але поки пропускаємо
                # бо старі/нові райони можуть плутатись
                pass
            
            if record.city_index and len(record.city_index) == 5 and record.city_index.isdigit():
                valid_indices.append(record.city_index)
        
        if not valid_indices:
            return ""
            
        # Повертаємо найменший індекс
        return min(valid_indices)
