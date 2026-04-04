from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
import logging

from ai_layer.exercise_generator import ExerciseGenerator
from ai_layer.promts import ExerciseType, CEFRLevel

logger = logging.getLogger(__name__)

app = FastAPI(title="English Exercise Generator API")
generator = ExerciseGenerator()


class GenerateRequest(BaseModel):
    exercise_type: str  # "fill_blanks", "multiple_choice", etc.
    level: str  # "A1", "B1", "C1", etc.
    count: int = Field(default=5, ge=1, le=50)
    grammar_topic: Optional[str] = None
    theme: str = "general"
    context: Optional[str] = "everyday situations"
    model: Optional[str] = None
    force_refresh: bool = False


class ImproveRequest(BaseModel):
    exercise: dict
    feedback: str = Field(min_length=5)
    exercise_type: str
    level: str


@app.get("/health")
async def health() -> dict:
    logger.info("Health check requested")
    return {"status": "ok"}


@app.get("/api/v1/cache/stats")
async def cache_stats() -> dict:
    logger.info("Cache stats endpoint requested")
    return generator.get_cache_stats()


@app.post("/api/v1/generate")
async def generate_exercises(request: GenerateRequest):
    """
    Генерация упражнений

    Example request:
    {
        "exercise_type": "fill_blanks",
        "level": "B1",
        "count": 5,
        "grammar_topic": "Present Perfect",
        "theme": "travel"
    }
    """
    try:
        logger.info("API generate request received: type=%s level=%s count=%s", request.exercise_type, request.level, request.count)
        # Преобразуем строки в enum
        exercise_type = ExerciseType(request.exercise_type)
        level = CEFRLevel(request.level)

        # Генерируем
        result = generator.generate_exercises(
            exercise_type=exercise_type,
            level=level,
            count=request.count,
            grammar_topic=request.grammar_topic,
            theme=request.theme,
            context=request.context,
            model=request.model,
            force_refresh=request.force_refresh,
        )

        return result

    except ValueError as e:
        logger.warning("Bad request in generate: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Unhandled generation error")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@app.post("/api/v1/batch-generate")
async def batch_generate_exercises(requests: List[GenerateRequest]):
    """Пакетная генерация"""
    logger.info("Batch generation request received: size=%s", len(requests))
    results = []

    for req in requests:
        try:
            exercise_type = ExerciseType(req.exercise_type)
            level = CEFRLevel(req.level)

            result = generator.generate_exercises(
                exercise_type=exercise_type,
                level=level,
                count=req.count,
                grammar_topic=req.grammar_topic,
                theme=req.theme,
                context=req.context,
                model=req.model,
                force_refresh=req.force_refresh,
            )
            results.append({"success": True, "data": result})
        except Exception as e:
            logger.warning("Batch item failed: %s", e)
            results.append({"success": False, "error": str(e)})

    return {"results": results}


# Эндпоинт для улучшения упражнения
@app.post("/api/v1/improve")
async def improve_exercise(request: ImproveRequest):
    """Улучшение упражнения на основе фидбека"""
    try:
        logger.info("Improve endpoint called: type=%s level=%s", request.exercise_type, request.level)
        result = generator.regenerate_with_feedback(
            original_exercise=request.exercise,
            feedback=request.feedback,
            exercise_type=ExerciseType(request.exercise_type),
            level=CEFRLevel(request.level)
        )
        return result
    except Exception as e:
        logger.exception("Unhandled improve error")
        raise HTTPException(status_code=500, detail=str(e))