# Ukrposhta Address Matcher

Локальний Python-інструмент для обробки реєстрів Укрпошти: він читає TXT-файли, нормалізує адреси, звіряє їх з адресним класифікатором Укрпошти й формує вихідний файл з JSON-адресою. У проєкті також є вебінтерфейс для ручної перевірки спірних рядків і збірка Windows `.exe`.

## Можливості

- обробка реєстрів з `10` або `11` полями, розділеними `;`;
- перевірка та фіксація індексу перед фінальним складанням адреси;
- пошук області, району, міста, вулиці та будинку через XML API адресного класифікатора Укрпошти;
- контрольований fallback для складних кейсів;
- локальні `SQLite`-кеші для HTTP-відповідей і фінальних резолвів;
- опціональне використання Gemini лише як допоміжного нормалізатора, а не джерела істини;
- генерація перетвореного TXT-файлу, `report.csv` і окремого звіту для рядків без встановленого індексу;
- локальний human-in-the-loop UI для ручного опрацювання спірних адрес;
- запуск review UI як Windows-програми та збірка standalone `.exe`.

## Встановлення на Windows

1. Встановіть Python `3.11+` і переконайтесь, що `python` доступний у PowerShell.
2. Створіть і активуйте віртуальне середовище:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

3. Встановіть проєкт у editable-режимі:

```powershell
pip install -e .
```

4. Скопіюйте файл змінних середовища:

```powershell
Copy-Item .env.example .env
```

## Налаштування

Змінні середовища читаються з `.env`.

- `UKRPOSHTA_BEARER_TOKEN` — обов'язковий токен для API Укрпошти;
- `GEMINI_API_KEY` — ключ Gemini, якщо ввімкнено AI fallback;
- `CLASSIFIER_CACHE_PATH` — шлях до локального `SQLite`-кешу;
- `CLASSIFIER_MATCH_WORKERS` — кількість потоків для матчингу;
- `CLASSIFIER_REFRESH_HOUR` — година планового оновлення кешу;
- `CLASSIFIER_REFRESH_MINUTE` — хвилина планового оновлення кешу;
- `CLASSIFIER_REFRESH_TZ` — часовий пояс для планового оновлення;
- `GITHUB_USERNAME` — GitHub-користувач для службових сценаріїв.

Якщо `CLASSIFIER_CACHE_PATH` не задано, використовується спільний кеш за замовчуванням:

- Windows: `%LOCALAPPDATA%\ukrposhta-address-matcher\classifier-cache.sqlite`
- fallback: `~/.cache/ukrposhta-address-matcher/classifier-cache.sqlite`

## Основні команди

Обробити реєстр і сформувати вихідний TXT:

```powershell
python -m ukrposhta_address_matcher match-registry "C:\path\input.txt" "C:\path\output.txt" --report "C:\path\report.csv"
```

Явно вказати окремий кеш:

```powershell
python -m ukrposhta_address_matcher match-registry "C:\path\input.txt" "C:\path\output.txt" --report "C:\path\report.csv" --cache ".\cache.sqlite"
```

Обмежити паралелізм:

```powershell
python -m ukrposhta_address_matcher match-registry "C:\path\input.txt" "C:\path\output.txt" --report "C:\path\report.csv" --workers 4
```

Прогріти кеш без запису вихідних файлів:

```powershell
python -m ukrposhta_address_matcher warm-cache "C:\path\input.txt" --workers 4
```

Оновити кешовані відповіді класифікатора:

```powershell
python -m ukrposhta_address_matcher refresh-cache
```

## Інтерфейс ручної перевірки

Запуск локального review UI:

```powershell
python -m ukrposhta_address_matcher review-ui --port 8765
```

Після запуску браузер відкриється автоматично. Далі можна:

- завантажити TXT-реєстр;
- відокремити `Автоматично`, `Потребує перевірки` та `Hard Stop`;
- переглядати деталі рядка й кандидатів з класифікатора;
- підтверджувати пропозицію системи, вибирати кандидата, редагувати вручну або позначати рядок як нерозв'язний;
- експортувати фінальний TXT і лог ручних рішень.

Локальний каталог даних review UI за замовчуванням: `.review-ui-data/`.

## Запуск як Windows-програми

Із кореня репозиторію можна запускати інтерфейс подвійним кліком:

- `start_review_ui.cmd`
- `start_review_ui.pyw`

Обидва launcher-и підіймають локальний сервер review UI і відкривають браузер автоматично.

## Збірка standalone `.exe`

Для збірки Windows-застосунку виконайте:

```powershell
.\build_review_ui_exe.ps1
```

Після успішної збірки готовий файл буде доступний як `dist\UkrposhtaReviewUI.exe`.

## Формат вихідної адреси

Поле `4` у вихідному реєстрі перетворюється на компактний JSON:

```json
{"postcode":"","region":"","district":"","city":"","street":"","houseNumber":"","apartmentNumber":""}
```

Поля `postcode`, `region`, `city`, `street` і `houseNumber` у фінальному виході мають бути заповнені.

## Планове оновлення кешу

Для щоденного оновлення через Windows Task Scheduler використовуйте:

```powershell
python -m ukrposhta_address_matcher refresh-cache
```

Час запуску береться з `CLASSIFIER_REFRESH_HOUR` і `CLASSIFIER_REFRESH_MINUTE`.

## Важливі примітки

- Gemini не є джерелом істини для фінальної адреси.
- Канонічним джерелом фінального структурованого результату залишається адресний класифікатор Укрпошти.
- Review UI потрібен саме для спірних кейсів, де автозаміна без участі оператора ризикована.
