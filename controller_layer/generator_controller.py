from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from enum import Enum

from ai_layer.exercise_generator import ExerciseGenerator
from ai_layer.promts import ExerciseType, CEFRLevel

app = FastAPI(title="English Exercise Generator API")
generator = ExerciseGenerator()


class GenerateRequest(BaseModel):
    exercise_type: str  # "fill_blanks", "multiple_choice", etc.
    level: str  # "A1", "B1", "C1", etc.
    count: int = 5
    grammar_topic: Optional[str] = None
    theme: str = "general"
    context: Optional[str] = "everyday situations"


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
            context=request.context
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@app.post("/api/v1/batch-generate")
async def batch_generate_exercises(requests: List[GenerateRequest]):
    """Пакетная генерация"""
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
                theme=req.theme
            )
            results.append({"success": True, "data": result})
        except Exception as e:
            results.append({"success": False, "error": str(e)})

    return {"results": results}


# Эндпоинт для улучшения упражнения
@app.post("/api/v1/improve")
async def improve_exercise(
        exercise: dict,
        feedback: str,
        exercise_type: str,
        level: str
):
    """Улучшение упражнения на основе фидбека"""
    try:
        result = generator.regenerate_with_feedback(
            original_exercise=exercise,
            feedback=feedback,
            exercise_type=ExerciseType(exercise_type),
            level=CEFRLevel(level)
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))