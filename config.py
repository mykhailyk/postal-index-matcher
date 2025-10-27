"""
Конфігурація проекту Address Matcher v2.1
"""
import os
import sys


def get_base_path():
    """Отримати базовий шлях (для EXE і Python)"""
    if getattr(sys, 'frozen', False):
        # Якщо EXE - повертаємо папку де лежить EXE
        return os.path.dirname(sys.executable)
    else:
        # Якщо Python скрипт
        return os.path.dirname(os.path.abspath(__file__))


# Базовий шлях
BASE_PATH = get_base_path()

# Шляхи (динамічні для EXE)
PROJECT_ROOT = BASE_PATH
DATA_DIR = os.path.join(BASE_PATH, 'data')
CACHE_DIR = os.path.join(BASE_PATH, 'cache')
LOGS_DIR = os.path.join(BASE_PATH, 'logs')
COLUMN_MAPPINGS_DIR = os.path.join(BASE_PATH, 'column_mappings')

# Шлях до файлу налаштувань
SETTINGS_FILE = os.path.join(BASE_PATH, 'settings.json')

# Magistral - ФІКСОВАНИЙ ШЛЯХ (мережевий диск)
MAGISTRAL_CSV_PATH = r'X:\!obmin\UkrPoshta\magistral.csv'
MAGISTRAL_CACHE_PATH = os.path.join(CACHE_DIR, 'normalized_magistral.pkl')

# Створюємо директорії якщо їх немає
for dir_path in [DATA_DIR, CACHE_DIR, LOGS_DIR, COLUMN_MAPPINGS_DIR]:
    os.makedirs(dir_path, exist_ok=True)

# Пошук - гібридний підхід
SEARCH_WEIGHTS = {
    'city': 0.40,      # Місто - найважливіше
    'street': 0.30,    # Вулиця
    'region': 0.20,    # Область
    'consonants': 0.10 # Приголосні (для стійкості)
}

# Пороги схожості
SIMILARITY_THRESHOLD = 0.60  # Мінімальна схожість для результату
HIGH_CONFIDENCE_THRESHOLD = 0.80  # Висока впевненість

# Кількість результатів
MAX_SEARCH_RESULTS = 20
MAX_CANDIDATES = 5000  # Попереднє фільтрування

# Кешування
ENABLE_SEARCH_CACHE = True
SEARCH_CACHE_PATH = os.path.join(CACHE_DIR, 'search_cache.json')
CACHE_EXPIRY_DAYS = 30

# UI
WINDOW_TITLE = "PrintTo Address Matcher v2.1"
WINDOW_WIDTH = 1600
WINDOW_HEIGHT = 900

COLOR_PROCESSED = "#E8F5E9"  # Світло-зелений для оброблених
COLOR_HIGH_CONFIDENCE = "#C8E6C9"  # Зелений
COLOR_MEDIUM_CONFIDENCE = "#FFF9C4"  # Жовтий
COLOR_LOW_CONFIDENCE = "#FFCDD2"  # Червоний

# Автозбереження
AUTOSAVE_ENABLED = True
AUTOSAVE_INTERVAL = 300  # секунд (5 хвилин)

# Логування
LOG_FILE = os.path.join(LOGS_DIR, 'app.log')
LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# Нормалізація тексту
STREET_PREFIXES = ['вул.', 'вулиця', 'пров.', 'провулок', 'бульв.', 'бульвар', 'просп.', 'проспект']
CITY_PREFIXES = ['м.', 'місто', 'с.', 'село', 'смт.', 'с-ще', 'селище']

# Багатопоточність
MAX_WORKERS = 4  # Кількість потоків для batch обробки

# Undo/Redo
MAX_UNDO_STACK = 50  # Максимум кроків назад
