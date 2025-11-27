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

# ==================== MAGISTRAL - ФІКСОВАНИЙ ШЛЯХ ====================
# Завжди на мережевому диску X:
MAGISTRAL_CSV_PATH = r'X:\!obmin\UkrPoshta\magistral.csv'

# Кеш magistral зберігається локально (біля EXE)
MAGISTRAL_CACHE_PATH = os.path.join(CACHE_DIR, 'normalized_magistral.pkl')

# Індекси UkrPoshta (для каскадної форми)
UKRPOSHTA_INDEX_PATH = os.path.join(CACHE_DIR, 'ukrposhta_index.pkl')
CITY_INDEX_CACHE_PATH = os.path.join(CACHE_DIR, 'city_index.pkl')
REGION_INDEX_CACHE_PATH = os.path.join(CACHE_DIR, 'region_index.pkl')

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
AUTOSAVE_INTERVAL = 100  # секунд (5 хвилин)

# Логування
LOG_FILE = os.path.join(LOGS_DIR, 'app.log')
LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# Нормалізація тексту
STREET_PREFIXES = ['вул.', 'вулиця', 'пров.', 'провулок', 'бульв.', 'бульвар', 'просп.', 'проспект']
CITY_PREFIXES = ['м.', 'місто', 'с.', 'село', 'смт.', 'с-ще', 'селище']

# Багатопоточність
MAX_WORKERS = 8  # Кількість потоків для batch обробки

# Undo/Redo
MAX_UNDO_STACK = 20  # Максимум кроків

# Мінімальна точність для автоматичної підстановки
AUTO_PROCESSING_THRESHOLD = 90  # 90% за замовчуванням (може бути 50-100)

# ==================== НАЛАШТУВАННЯ ПОШУКУ (НОВІ) ====================
# Пороги для автоматичної підстановки (HybridSearch)
AUTO_MATCH_CONFIDENCE = 98        # Мінімальна впевненість для авто-підстановки (0-100)
STRICT_MATCH_CITY_THRESHOLD = 0.95 # Поріг схожості міста для авто-підстановки
STRICT_MATCH_STREET_THRESHOLD = 0.90 # Поріг схожості вулиці для авто-підстановки

# Ваги та пороги для розрахунку score (HybridSearch)
SCORE_CITY_WEIGHT = 0.35          # Вага міста
SCORE_STREET_WEIGHT = 0.35        # Вага вулиці
SCORE_BUILDING_WEIGHT = 0.25      # Вага будинку
SCORE_INDEX_WEIGHT = 0.05         # Вага індексу

SCORE_CITY_THRESHOLD = 0.85       # Мінімальна схожість міста для нарахування балів
SCORE_STREET_THRESHOLD = 0.75     # Мінімальна схожість вулиці для нарахування балів
SCORE_REGION_THRESHOLD = 0.80     # Мінімальна схожість області (якщо задана)

SCORE_BUILDING_EXACT_BONUS = 0.25 # Бонус за точне співпадіння будинку
SCORE_BUILDING_PARTIAL_BONUS = 0.10 # Бонус за часткове співпадіння будинку
SCORE_BUILDING_PENALTY = 0.15     # Штраф за відсутність будинку

SCORE_PERFECT_MATCH_BONUS = 0.10  # Бонус за ідеальне співпадіння всіх полів
