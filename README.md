# Kharkiv Metro Route Planner

CLI та MCP сервер для планування маршрутів у Харківському метрополітені.

## Запуск та ініціалізація бази даних

Проєкт використовує `uv`, наступні команди виконуються через `uv run metro`.

```bash
metro init
```

## Пошук маршруту

```bash
# За замовчуванням - з поточного часу
metro route "Холодна гора" "Героїв праці"

# З конкретним часом
metro route "Холодна гора" "Героїв праці" --time "08:30"

# З виведенням у JSON
metro route "Холодна гора" "Героїв праці" --output json

# Англійською мовою
metro route "Kholodna Hora" "Heroiv Praci" --lang en
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
metro stations -l s # або "k", "o"
```

## MCP Server

Запуск MCP сервера для інтеграції з AI-агентами:

```bash
metro-mcp
```

### OpenCode
```json
"mcp": {
    "metro-kh": {
        "enabled": true,
        "type": "local",
        "command": [
        "uv", "run",
        "--directory", "/foo/bar/kharkiv-subway",
        "python", "-m", "metropoliten.mcp.server"
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
│   │   ├── scraper.py  # Парсер сайту
│   │   └── initializer.py # Ініціалізація
│   ├── cli/            # CLI інтерфейс
│   │   └── main.py     # Команди
│   └── mcp/            # MCP сервер
│       └── server.py   # Сервер
└── data/
    └── metro.db        # База даних
```

## Особливості

- **3 лінії метро:** Холодногірсько-заводська, Салтівська, Олексіївська
- **3 пересадки:** Майдан Конституції ↔ Історичний музей, Спортивна ↔ Метробудівників, Університет ↔ Держпром
- **Час пересадки:** 3 хвилини
- **Розклад:** Окремий для буднів та вихідних
- **Мови:** Українська та англійська

## Ліцензія

MIT
