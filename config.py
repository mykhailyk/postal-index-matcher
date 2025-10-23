"""
Конфігурація проекту Address Matcher v2
"""
import os

# Шляхи
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
CACHE_DIR = os.path.join(PROJECT_ROOT, 'cache')
LOGS_DIR = os.path.join(PROJECT_ROOT, 'logs')
COLUMN_MAPPINGS_DIR = os.path.join(PROJECT_ROOT, 'column_mappings')

# Шлях до файлу налаштувань
SETTINGS_FILE = os.path.join(PROJECT_ROOT, 'settings.json')

# Magistral
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
HIGH_CONFIDENCE_THRESHOLD = 0.95  # Висока впевненість

# Кількість результатів
MAX_SEARCH_RESULTS = 20
MAX_CANDIDATES = 5000  # Попереднє фільтрування

# Кешування
ENABLE_SEARCH_CACHE = True
SEARCH_CACHE_PATH = os.path.join(CACHE_DIR, 'search_cache.json')
CACHE_EXPIRY_DAYS = 30

# UI
WINDOW_TITLE = "Підбір поштових індексів v2.0"
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
MAX_UNDO_STACK = 100  # Максимум кроків назад
