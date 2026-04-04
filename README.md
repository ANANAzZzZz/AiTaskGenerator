# AI Task Generator

Сервис на FastAPI для генерации упражнений по английскому языку через OpenRouter.

## Что умеет

- Генерировать упражнения через `POST /api/v1/generate`
- Пакетно генерировать через `POST /api/v1/batch-generate`
- Улучшать упражнение по фидбеку через `POST /api/v1/improve`
- Проверять доступность сервиса через `GET /health`

## Быстрый старт

1. Создайте и активируйте виртуальное окружение.
2. Установите зависимости:

```powershell
pip install -r requirements.txt
```

3. Создайте `.env` в корне проекта:

```dotenv
OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

4. Запустите API:

```powershell
uvicorn controller_layer.generator_controller:app --reload
```

Swagger UI: `http://127.0.0.1:8000/docs`

## Пример запроса

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/generate" \
  -H "Content-Type: application/json" \
  -d '{
	"exercise_type": "fill_blanks",
	"level": "B1",
	"count": 3,
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

## Тесты

```powershell
pytest -q
```
