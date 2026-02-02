# Kharkiv Metro Route Planner

CLI та MCP сервер для планування маршрутів у Харківському метрополітені.

![Default and simple CLI output for routes](assets/route_demo.gif)

## Особливості

### Харківський метрополітен
  - **3 лінії метро:** Холодногірсько-заводська, Салтівська, Олексіївська
  - **3 пересадки:** Майдан Конституції ↔ Історичний музей, Спортивна ↔ Метробудівників, Університет ↔ Держпром
  - **Розклад:** Окремий для буднів та вихідних
### Функціонал
  - **Local-first:** Локальна БД, працює офлайн
  - **Час пересадки:** 3 хвилини
  - **Мови:** Українська та англійська
  - <details>
    <summary> <b>Альтернативні назви</b>: Старі та скорочені назви станцій </summary>
  
      - Героїв праці: Салтівська
      - Проспект Гагаріна: Левада
      - Пушкінська: Ярослава Мудрого
      - 23: 23 Серпня
      - Барабашова: Академіка Барабашова
      - Бекетова: Архітектора Бекетова
      - Ботсад: Ботанічний сад
      - Гагаріна: Левада
      - Масельського: Ім. О.С. Масельського
      - Павлова: Академіка Павлова
      - Палац: Палац спорту
      - ХТЗ: Тракторний завод
    </details>

## Запуск та ініціалізація бази даних

Проєкт використовує `uv`, наступні команди виконуються через `uv run metro`.

**Ініціалізація**
```bash
metro scrape --init-db
```

Розклади парсяться з https://www.metro.kharkiv.ua/ і зберігаються окремо для буднів та вихідних.

## Пошук маршруту

```bash
# За замовчуванням - з поточного часу
metro route "Холодна гора" "Студентська"

# З конкретним часом
metro route "Холодна гора" "Студентська" --time "08:30"

# З виведенням у JSON
metro route "Холодна гора" "Студентська" --output json

# Англійською мовою
metro route "Kholodna Hora" "Heroiv Praci" --lang en

# Компактний вивід (тільки ключові станції: початок, пересадки, кінець)
metro route "Холодна гора" "Студентська" --compact

# Повний вивід (всі станції) - якщо в конфігу compact=true
metro config set preferences.route.compact true
metro route "Холодна гора" "Студентська" --compact
```

### Перегляд розкладу

```bash
# Розклад станції
metro schedule "Майдан Конституції"

# З конкретним напрямком
metro schedule "Майдан Конституції" --direction "Індустріальна"

# У вихідні
metro schedule "Майдан Конституції" --day-type weekend
```

### Список станцій

```bash
# Всі станції
metro stations

# Тільки одна лінія
metro stations --line saltivska

# Або коротше
metro stations -l s # "k", "o"
```

## Конфігурація

Конфіг зберігається в XDG директоріях:
- **Linux**: `~/.config/kharkiv-metro-rp/config.toml`
- **macOS**: `~/Library/Application Support/kharkiv-metro-rp/config.toml`
- **Windows**: `%APPDATA%\kharkiv-metro-rp\config.toml`

База даних:
- **Linux**: `~/.local/share/kharkiv-metro-rp/metro.db`
- **macOS**: `~/Library/Application Support/kharkiv-metro-rp/metro.db`
- **Windows**: `%LOCALAPPDATA%\kharkiv-metro-rp\metro.db`

### config.toml - повна специфікація

#### `[database]` - налаштування бази даних

| Опція | Тип | За замовчуванням | Опис |
|-------|-----|------------------|------|
| `auto` | boolean | `true` | `true` - використовувати XDG директорію, `false` - використовувати `path` |
| `path` | string | `null` | Абсолютний шлях до бази даних (використовується якщо `auto = false`). Підтримує `~` (домашня директорія) |

#### `[preferences]` - загальні налаштування

| Опція | Тип | За замовчуванням | Можливі значення | Опис |
|-------|-----|------------------|------------------|------|
| `language` | string | `"ua"` | `"ua"`, `"en"` | Мова станцій за замовчуванням |
| `output_format` | string | `"table"` | `"table"`, `"json"` | Формат виводу за замовчуванням для `stations` та `schedule` команд |

#### `[preferences.route]` - налаштування маршрутів

| Опція | Тип | За замовчуванням | Можливі значення | Опис |
|-------|-----|------------------|------------------|------|
| `format` | string | `"full"` | `"full"`, `"simple"`, `"json"` | Формат виводу маршруту: full=детальна таблиця, simple=компактний inline, json=JSON |
| `compact` | boolean | `false` | `true`, `false` | `true` - показувати тільки ключові станції (початок, пересадки, кінець), `false` - всі станції. Працює з форматами `full` та `simple` |

#### `[scraper]` - налаштування парсера сайту

| Опція | Тип | За замовчуванням | Опис |
|-------|-----|------------------|------|
| `timeout` | integer | `30` | Таймаут HTTP запитів в секундах |
| `user_agent` | string | `"kharkiv-metro-rp/1.0"` | User-Agent для HTTP запитів |

### Повний приклад config.toml

```toml
[database]
auto = false
path = "~/Documents/kharkiv_metro.db"

[preferences]
language = "ua"
output_format = "table"

[preferences.route]
format = "full"
compact = false

[scraper]
timeout = 30
user_agent = "kharkiv-metro-rp/1.0"
```

### Команди управління конфігом

- Команда `metro config set` працює для будь-якої опції з config.toml за шаблоном `section.key value`. Тип значення визначається автоматично (string, boolean, integer).
- Команда `metro config open` відкриває конфіг у системному редакторі:
  - **Linux**: використовує `xdg-open` або `$EDITOR` (fallback: nano)
  - **macOS**: використовує `open`
  - **Windows**: використовує `start`

```bash
# Кастомна база даних
metro --db-path /tmp/test.db route "Холодна гора" "Студентська"

# Кастомний конфіг
metro --config ./my-config.toml route "Холодна гора" "Студентська"
```

## MCP Server

Запуск MCP сервера для інтеграції з AI-агентами:

### OpenCode
Передбачає:
- Наявність `uv` у `$PATH`
- Локальний репозиторій
  - `git clone https://github.com/beauloxe/kharkiv-metro-rp.git /foo/bar/`, де `/foo/bar/` - приклад директорії.

```json
"mcp": {
    "metro-kh": {
        "enabled": true,
        "type": "local",
        "command": [
        "uv", "run",
        "--directory", "/foo/bar/kharkiv-metro-rp",
        "python", "-m", "kharkiv_metro_rp.mcp.server"
        ],
    }
}
```

### Доступні інструменти

- `get_route` - пошук маршруту між станціями
- `get_schedule` - отримання розкладу станції
- `list_stations` - список всіх станцій
- `find_station` - пошук станції за назвою

## Структура проєкту

```
metropoliten/
├── src/metropoliten/
│   ├── core/           # Ядро системи
│   │   ├── models.py   # Моделі даних
│   │   ├── graph.py    # Граф метро
│   │   └── router.py   # Алгоритми маршрутизації
│   ├── data/           # Робота з даними
│   │   ├── database.py # SQLite база
│   │   ├── scraper.py  # Парсер сайту metro.kharkiv.ua
│   │   └── initializer.py # Ініціалізація бази
│   ├── cli/            # CLI інтерфейс
│   │   └── main.py     # Команди
│   ├── mcp/            # MCP сервер
│   │   └── server.py   # Сервер
│   └── config.py       # XDG конфігурація
└── data/
    └── metro.db        # База даних (legacy, тепер в XDG)
```

## TODO
- [x] Правильна транслітерація та назви станцій
- [x] Доопрацювати парсер
- [x] Переклад усіх полів
- [ ] Уніфікація виводу, аргументів
- [ ] ~~Переписати весь цей ШІ слоп~~ Зробити повний рефактор
