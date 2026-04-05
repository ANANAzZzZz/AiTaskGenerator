# AI Task Generator

FastAPI-сервис для генерации упражнений по английскому языку через OpenRouter с легким полу-агентным циклом: `planner -> generation -> self-validation -> optional refinement`.

## Что уже реализовано

- Генерация упражнений: `POST /api/v1/generate`
- Пакетная генерация: `POST /api/v1/batch-generate`
- Улучшение упражнения по фидбеку: `POST /api/v1/improve`
- Проверка состояния сервиса: `GET /health`
- Статистика кэша: `GET /api/v1/cache/stats`
- Опциональный SQLite-кэш генераций (`exercises.db`)
- Расширенное логирование на уровне API, генератора, валидаторов, клиента и кэша

## Полу-агентный подход (sweet spot)

Проект не является полноценным multi-step autonomous agent, но использует агентные элементы:

1. `LightPlanner` формирует легкий план и хинты для промпта.
2. LLM делает один основной вызов на генерацию.
3. Результат проходит self-validation (`ExerciseValidator.validate_batch_quality`).
4. Если качество ниже порога и включен флаг, запускается один refinement-вызов.
5. Выбирается лучший результат, добавляются метаданные и (опционально) запись в кэш.

Это дает более стабильный результат без усложнения оркестрации.

## Структура проекта

```text
ai_layer/
  client.py             # OpenRouter-клиент, retry, fallback моделей, rate limiting
  config.py             # Конфигурация через .env
  exercise_generator.py # Основной pipeline генерации
  exercise_store.py     # SQLite-кэш генераций
  planner.py            # Легкий planner
  promts.py             # PromptBuilder и enum-ы типов/уровней
  validators.py         # Структурная и quality-валидация
controller_layer/
  generator_controller.py # FastAPI-эндпоинты
tests/
  ...
main.py                 # Точка входа локального запуска
```

## Быстрый старт

### 1) Установка зависимостей

```powershell
pip install -r requirements.txt
```

### 2) Настройка `.env`

Минимум:

```dotenv
OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_PRIMARY_MODEL=openai/gpt-4o-mini
```

Рекомендуемые дополнительные параметры:

```dotenv
OPENROUTER_FALLBACK_MODELS=openai/gpt-4o-mini,meta-llama/llama-3.1-8b-instruct
MIN_QUALITY_SCORE_FOR_ACCEPT=0.6
ENABLE_OPTIONAL_REFINEMENT=true
ENABLE_EXERCISE_CACHE=true
EXERCISE_DB_PATH=exercises.db
MAX_RETRIES=3
RATE_LIMIT_PER_MINUTE=60
TIMEOUT=30
```

### 3) Запуск API

```powershell
python main.py
```

или

```powershell
uvicorn controller_layer.generator_controller:app --reload
```

Swagger UI: `http://127.0.0.1:8000/docs`

## Пример запроса

```powershell
curl -X POST "http://127.0.0.1:8000/api/v1/generate" `
  -H "Content-Type: application/json" `
  -d '{
    "exercise_type": "fill_blanks",
    "level": "B1",
    "count": 5,
    "grammar_topic": "Present Perfect",
    "theme": "travel",
    "context": "airport"
  }'
```

## Поддерживаемые типы упражнений

- `fill_blanks`
- `multiple_choice`
- `error_correction`
- `sentence_transformation`
- `matching`
- `dialogue_completion`

## API-эндпоинты

- `GET /health` - статус сервиса
- `GET /api/v1/cache/stats` - статистика кэша (если включен)
- `POST /api/v1/generate` - сгенерировать упражнения
- `POST /api/v1/batch-generate` - пакетная генерация
- `POST /api/v1/improve` - улучшить упражнение по фидбеку

## Частые ошибки и как исправить

- `Input should be a valid dictionary...`
  - Обычно это означает, что body отправлен как строка, а не JSON-объект.
  - В Postman выбирайте `Body -> raw -> JSON` и передавайте чистый JSON без лишнего экранирования.

- `The provided model identifier is invalid`
  - Для вашего провайдера/аккаунта недоступна указанная модель.
  - Проверьте `OPENROUTER_PRIMARY_MODEL` и при необходимости задайте `OPENROUTER_FALLBACK_MODELS`.

## Логирование

Базовая конфигурация логирования задается в `main.py`.

Формат:

```text
%(asctime)s | %(levelname)s | %(name)s | %(message)s
```

Логи показывают этапы pipeline: входящие запросы, cache hit/miss, вызовы LLM, quality score, решение по refinement.

## Тесты

```powershell
pytest -q
```

## Бенчмарки генерации и полу-агента

В проект добавлен benchmark harness: `benchmarks/run_benchmarks.py`.

Быстрый офлайн smoke (без OpenRouter, детерминированно):

```powershell
python -m benchmarks.run_benchmarks --mode direct --iterations 5 --use-fake-client
```

Реальные замеры через API endpoint-ы:

```powershell
python main.py
python -m benchmarks.run_benchmarks --mode api --iterations 3 --base-url http://127.0.0.1:8000
```

Сценарии лежат в `benchmarks/scenarios.json`, результаты сохраняются в `benchmarks/results/` в форматах JSON/CSV/MD.
Метрики включают latency, success rate, cache/refinement rate, quality score и stage timings пайплайна (planner, generation, validation, refinement).

Подробности: `docs/benchmarking.md`.

## Подробная документация

Подробное техническое описание доступно в `docs/PROJECT_DETAILED_RU.md`.
