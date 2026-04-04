# AI Task Generator - подробное техническое описание

## 1. Назначение проекта

`AiTaskGenerator` - это backend-сервис на FastAPI, который генерирует упражнения по английскому языку с учетом:

- типа упражнения;
- уровня CEFR;
- темы/контекста;
- (опционально) грамматического фокуса.

Вместо сложного автономного агента проект реализует практичный **semi-agent pipeline**: минимальное планирование + генерация + самопроверка качества + опциональное доулучшение.

## 2. Что значит "полу-агент" в этом проекте

### 2.1 Почему это не "полный агент"

В системе нет:

- многократного tool-use цикла с динамическим выбором инструментов;
- долгоживущей памяти задач;
- автономной декомпозиции цели на произвольное число шагов.

### 2.2 Почему это уже "агентный" подход

Есть ключевые агентные элементы:

1. **Planner stage**: `LightPlanner` формирует план выполнения и ограничения.
2. **Goal-oriented generation**: LLM генерирует контент под целевой формат.
3. **Self-evaluation**: результат оценивается по quality score.
4. **Conditional correction**: при провале качества делается один refinement-pass.
5. **Decision policy**: принимается лучший результат (до/после refinement).

Именно это и есть "sweet spot": больше контроля качества без сложности полноценного оркестратора.

## 3. Архитектура по слоям

### 3.1 `controller_layer`

Файл: `controller_layer/generator_controller.py`

- содержит FastAPI-приложение и HTTP-контракты;
- парсит входные DTO (`GenerateRequest`, `ImproveRequest`);
- конвертирует строковые поля в enum (`ExerciseType`, `CEFRLevel`);
- вызывает методы `ExerciseGenerator`;
- возвращает JSON-ответы и HTTP-ошибки.

Эндпоинты:

- `GET /health`
- `GET /api/v1/cache/stats`
- `POST /api/v1/generate`
- `POST /api/v1/batch-generate`
- `POST /api/v1/improve`

### 3.2 `ai_layer`

#### `config.py`

Конфигурация через `pydantic-settings`:

- API: `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`
- модели: `OPENROUTER_PRIMARY_MODEL`, `OPENROUTER_FALLBACK_MODELS`
- качество: `MIN_QUALITY_SCORE_FOR_ACCEPT`, `ENABLE_OPTIONAL_REFINEMENT`
- кэш: `ENABLE_EXERCISE_CACHE`, `EXERCISE_DB_PATH`
- надежность: `MAX_RETRIES`, `RATE_LIMIT_PER_MINUTE`, `TIMEOUT`

#### `client.py`

`OpenRouterClient`:

- вызывает OpenRouter через SDK `openai`;
- поддерживает retry/backoff;
- переключается на fallback-модели;
- ограничивает частоту вызовов (`RateLimiter`);
- логирует использование токенов.

#### `promts.py`

- enum-ы: `ExerciseType`, `CEFRLevel`;
- `PromptBuilder`:
  - системный промпт;
  - шаблоны для каждого типа упражнения;
  - сборка финального списка `messages`.

> Примечание: имя файла - `promts.py` (без второй "p" в "prompts"). Это текущее фактическое имя в проекте.

#### `planner.py`

`LightPlanner` строит легкий план:

- целевое количество;
- grammar focus;
- текстовые planner hints для усиления консистентности генерации.

#### `validators.py`

`ExerciseValidator`:

- проверка структуры по типам упражнений;
- эвристическая проверка соответствия CEFR;
- агрегированная quality-оценка пачки (`validate_batch_quality`).

#### `exercise_store.py`

`ExerciseStore` на SQLite:

- сохранение JSON-ответа и quality score;
- точный подбор по ключу запроса (`type`, `level`, `count`, `grammar_topic`, `theme`);
- возврат cache hit/miss;
- статистика кэша.

#### `exercise_generator.py`

Центральный orchestration-класс `ExerciseGenerator`:

1. логирует старт генерации;
2. пробует взять ответ из кэша (если включено и нет `force_refresh`);
3. строит план через `LightPlanner`;
4. собирает промпт через `PromptBuilder`;
5. делает основной LLM-вызов;
6. валидирует структуру;
7. оценивает quality score;
8. при необходимости делает один refinement-вызов;
9. выбирает лучший результат;
10. добавляет `metadata`;
11. сохраняет в кэш;
12. логирует итог.

## 4. Сквозной flow запроса `/api/v1/generate`

Ниже фактический поток данных:

1. HTTP-запрос приходит в `generate_exercises` контроллера.
2. Pydantic валидирует body.
3. Строковые `exercise_type` и `level` приводятся к enum.
4. `ExerciseGenerator.generate_exercises(...)` запускает pipeline.
5. Если есть cache hit - ответ возвращается сразу (`metadata.source = cache`).
6. Иначе выполняется LLM-генерация (`metadata.source = llm`).
7. Выполняется quality-check, опционально refinement.
8. Результат возвращается клиенту.

## 5. Формат ответа и metadata

Ожидаемый формат:

```json
{
  "exercises": [
    {"...": "..."}
  ],
  "metadata": {
    "type": "fill_blanks",
    "level": "B1",
    "grammar_topic": "Present Perfect",
    "theme": "travel",
    "count": 5,
    "generated_at": 1710000000.0,
    "plan": {
      "target_count": 5,
      "grammar_focus": "Present Perfect",
      "plan_hints": "..."
    },
    "quality": {
      "score": 0.84,
      "pass": true,
      "issues": [],
      "stats": {
        "structure_ratio": 1.0,
        "level_ratio": 0.8,
        "count_ratio": 1.0
      }
    },
    "refined": false,
    "source": "llm"
  }
}
```

Поля могут немного отличаться в зависимости от типа упражнения и реального ответа модели.

## 6. API-контракты

### 6.1 `POST /api/v1/generate`

Request (пример):

```json
{
  "exercise_type": "fill_blanks",
  "level": "B1",
  "count": 5,
  "grammar_topic": "Present Perfect",
  "theme": "travel",
  "context": "airport",
  "model": null,
  "force_refresh": false
}
```

Ключевые ограничения:

- `count`: от 1 до 50;
- `exercise_type` и `level` должны входить в enum.

### 6.2 `POST /api/v1/batch-generate`

Принимает массив объектов формата `GenerateRequest`.
Возвращает `{"results": [{"success": true, "data": ...} | {"success": false, "error": ...}]}`.

### 6.3 `POST /api/v1/improve`

Улучшение конкретного упражнения по текстовому feedback.

### 6.4 `GET /api/v1/cache/stats`

Возвращает информацию о состоянии кэша. Если кэш отключен, `{"enabled": false}`.

## 7. Кэш и БД (SQLite)

Таблица: `generated_exercises`.

Хранит:

- ключ запроса (`exercise_type`, `level`, `count`, `grammar_topic`, `theme`);
- `payload_json` (полный ответ генератора);
- `quality_score`;
- `created_at`.

Стратегия:

- exact-match по параметрам запроса;
- берется самая свежая запись (`ORDER BY id DESC LIMIT 1`).

## 8. Логирование и наблюдаемость

### 8.1 Где настраивается

- `main.py` задает `logging.basicConfig(...)`.

### 8.2 Что логируется

- входящие API-запросы;
- hit/miss кэша;
- попытки вызова LLM и ретраи;
- quality score и решение о refinement;
- ошибки парсинга/валидации/внешнего API.

### 8.3 Пример интерпретации событий

- `Generation started...`
- `Cache miss...`
- `Prompt built...`
- `LLM attempt...`
- `Self-validation score=... pass=...`
- `Refinement triggered...` (если нужно)
- `Generation finished...`

## 9. Конфигурация `.env` (рекомендованный базовый шаблон)

```dotenv
OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_PRIMARY_MODEL=openai/gpt-4o-mini
OPENROUTER_FALLBACK_MODELS=

MIN_QUALITY_SCORE_FOR_ACCEPT=0.6
ENABLE_OPTIONAL_REFINEMENT=true

ENABLE_EXERCISE_CACHE=true
EXERCISE_DB_PATH=exercises.db

MAX_RETRIES=3
RATE_LIMIT_PER_MINUTE=60
TIMEOUT=30
```

## 10. Типовые ошибки

### 10.1 Body передан строкой вместо JSON

Признак: `Input should be a valid dictionary or object to extract fields from`.

Решение:

- отправлять именно JSON-объект;
- в Postman: `Body -> raw -> JSON`;
- проверить `Content-Type: application/json`.

### 10.2 Неверный идентификатор модели

Признак: `The provided model identifier is invalid`.

Решение:

- выбрать модель, доступную вашему провайдеру/аккаунту;
- настроить `OPENROUTER_PRIMARY_MODEL`;
- задать fallback-список в `OPENROUTER_FALLBACK_MODELS`.

## 11. Тесты и покрытие сценариев

Файлы тестов:

- `tests/test_api.py`
- `tests/test_exercise_store.py`
- `tests/test_prompt_builder.py`
- `tests/test_validators.py`

Что покрыто:

- health и базовый API-flow;
- работа cache store;
- построение промптов;
- валидация структуры/уровня/quality-report.

Что стоит расширить:

- e2e тест генерации с моками для refinement-ветки;
- проверка fallback-моделей в `generate_with_retry`;
- smoke-тест на включенный SQLite-кэш в боевом pipeline.

## 12. Производственный контур: рекомендации

- держать ключи в переменных окружения/секретах;
- явно фиксировать поддерживаемые модели OpenRouter;
- включить централизованный сбор логов;
- добавить метрики latencies/error-rate/cache-hit-rate;
- при росте нагрузки вынести БД из SQLite в более устойчивое хранилище.

## 13. Краткое резюме

Проект уже готов к практическому использованию как сервис генерации учебного контента:

- имеет HTTP API;
- содержит защитные механизмы (валидация, retry, fallback);
- использует quality gate + optional refinement;
- поддерживает кэш и базовую наблюдаемость через логирование.

С точки зрения агентности это **управляемый полу-агент**: легкий, контролируемый и достаточный для большинства продуктовых сценариев без избыточной сложности.
