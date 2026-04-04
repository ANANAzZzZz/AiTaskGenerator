import json
from typing import List, Dict, Any, Optional
import logging
from .client import ai_client
from .promts import PromptBuilder, ExerciseType, CEFRLevel
from .validators import ExerciseValidator

logger = logging.getLogger(__name__)


class ExerciseGenerator:
    """Основной класс для генерации упражнений"""

    def __init__(self, client=None):
        self.client = client or ai_client
        self.validator = ExerciseValidator()

    def generate_exercises(
            self,
            exercise_type: ExerciseType,
            level: CEFRLevel,
            count: int = 5,
            grammar_topic: Optional[str] = None,
            theme: str = "general",
            validate: bool = True,
            **kwargs
    ) -> Dict[str, Any]:
        """
        Генерация упражнений

        Args:
            exercise_type: Тип упражнения
            level: Уровень сложности (CEFR)
            count: Количество заданий
            grammar_topic: Грамматическая тема (опционально)
            theme: Лексическая тема
            validate: Валидировать результат
            **kwargs: Дополнительные параметры для промпта

        Returns:
            Dict с упражнениями и метаданными
        """

        logger.info(
            f"Generating {count} {exercise_type.value} exercises "
            f"for level {level.value}"
        )

        # Строим промпт
        messages = PromptBuilder.build_prompt(
            exercise_type=exercise_type,
            level=level,
            count=count,
            grammar_topic=grammar_topic,
            theme=theme,
            **kwargs
        )

        # Генерируем с retry логикой
        try:
            response = self.client.generate_with_retry(
                messages=messages,
                response_format={"type": "json_object"},  # Важно для JSON
                temperature=0.7,  # Баланс между креативностью и последовательностью
                max_tokens=2000
            )

            # Парсим JSON
            result = json.loads(response)

            # Валидация если нужна
            if validate:
                result = self._validate_and_fix(result, exercise_type, level)

            # Добавляем метаданные
            result['metadata'] = {
                'type': exercise_type.value,
                'level': level.value,
                'grammar_topic': grammar_topic,
                'theme': theme,
                'count': len(result.get('exercises', [])),
                'generated_at': time.time()
            }

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response was: {response}")
            raise ValueError("AI returned invalid JSON")

        except Exception as e:
            logger.error(f"Error generating exercises: {e}")
            raise

    def _validate_and_fix(
            self,
            result: Dict,
            exercise_type: ExerciseType,
            level: CEFRLevel
    ) -> Dict:
        """Валидация и исправление сгенерированных упражнений"""

        if 'exercises' not in result:
            raise ValueError("Response missing 'exercises' key")

        validated_exercises = []

        for exercise in result['exercises']:
            # Базовая валидация структуры
            is_valid, errors = self.validator.validate_structure(
                exercise,
                exercise_type
            )

            if not is_valid:
                logger.warning(f"Invalid exercise structure: {errors}")
                continue

            # Проверка грамматики (опционально)
            if self.validator.check_grammar:
                grammar_ok = self.validator.validate_grammar(exercise)
                if not grammar_ok:
                    logger.warning("Exercise has grammar issues")
                    # Можно попробовать автоисправление

            # Проверка уровня сложности
            if self.validator.check_level:
                level_ok = self.validator.validate_level(exercise, level)
                if not level_ok:
                    logger.warning(f"Exercise difficulty doesn't match {level}")

            validated_exercises.append(exercise)

        result['exercises'] = validated_exercises
        return result

    def batch_generate(
            self,
            requests: List[Dict[str, Any]],
            parallel: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Пакетная генерация нескольких типов упражнений

        Args:
            requests: Список запросов [{type, level, count, ...}, ...]
            parallel: Генерировать параллельно (требует async)
        """
        results = []

        for request in requests:
            try:
                result = self.generate_exercises(**request)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to generate for request {request}: {e}")
                results.append({"error": str(e), "request": request})

        return results

    def regenerate_with_feedback(
            self,
            original_exercise: Dict,
            feedback: str,
            exercise_type: ExerciseType,
            level: CEFRLevel
    ) -> Dict:
        """
        Регенерация упражнения с учетом фидбека

        Example:
            feedback = "Make the sentences shorter and use simpler vocabulary"
        """

        messages = [
            {"role": "system", "content": PromptBuilder.SYSTEM_PROMPT},
            {"role": "user", "content": f"Original exercise:\n{json.dumps(original_exercise, indent=2)}"},
            {"role": "assistant", "content": "I see the original exercise."},
            {"role": "user",
             "content": f"Please improve it based on this feedback:\n{feedback}\n\nReturn the improved version in the same JSON format."}
        ]

        response = self.client.generate_with_retry(
            messages=messages,
            response_format={"type": "json_object"}
        )

        return json.loads(response)


# Глобальный экземпляр
generator = ExerciseGenerator()