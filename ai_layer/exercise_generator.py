import json
from typing import List, Dict, Any, Optional
import logging
import time

from .client import get_ai_client
from .config import config
from .exercise_store import ExerciseStore
from .planner import LightPlanner
from .promts import PromptBuilder, ExerciseType, CEFRLevel
from .validators import ExerciseValidator

logger = logging.getLogger(__name__)


class ExerciseGenerator:
    """Основной класс для генерации упражнений"""

    def __init__(self, client=None):
        self.client = client
        self.validator = ExerciseValidator()
        self.planner = LightPlanner()
        self.store = ExerciseStore(config.EXERCISE_DB_PATH) if config.ENABLE_EXERCISE_CACHE else None

    def _get_client(self):
        return self.client or get_ai_client()

    def generate_exercises(
            self,
            exercise_type: ExerciseType,
            level: CEFRLevel,
            count: int = 5,
            grammar_topic: Optional[str] = None,
            theme: str = "general",
            validate: bool = True,
            force_refresh: bool = False,
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

        benchmark_trace_enabled = bool(kwargs.pop("benchmark_trace", False))
        trace: Dict[str, Any] = {"timings_ms": {}, "events": {"llm_calls": 0, "refinement_called": False}}
        started_total = time.perf_counter()

        logger.info(
            "Generation started: type=%s level=%s count=%s theme=%s force_refresh=%s",
            exercise_type.value,
            level.value,
            count,
            theme,
            force_refresh,
        )

        started_cache = time.perf_counter()
        cached = self._try_get_cached(exercise_type, level, count, grammar_topic, theme, force_refresh)
        trace["timings_ms"]["cache_lookup"] = round((time.perf_counter() - started_cache) * 1000, 2)
        if cached is not None:
            cached.setdefault("metadata", {})
            cached["metadata"]["source"] = "cache"
            trace["timings_ms"]["total"] = round((time.perf_counter() - started_total) * 1000, 2)
            if benchmark_trace_enabled:
                cached["metadata"]["benchmark_trace"] = trace
            logger.info("Generation finished from cache")
            return cached

        started_planner = time.perf_counter()
        plan = self.planner.build_plan(
            exercise_type=exercise_type,
            level=level,
            count=count,
            grammar_topic=grammar_topic,
            theme=theme,
        )
        trace["timings_ms"]["planner"] = round((time.perf_counter() - started_planner) * 1000, 2)

        # Строим промпт
        messages = PromptBuilder.build_prompt(
            exercise_type=exercise_type,
            level=level,
            count=count,
            grammar_topic=grammar_topic,
            theme=theme,
            plan_hints=plan["plan_hints"],
            **kwargs
        )

        # Генерируем с retry логикой
        response = None
        try:
            started_llm = time.perf_counter()
            trace["events"]["llm_calls"] += 1
            response = self._get_client().generate_with_retry(
                messages=messages,
                response_format={"type": "json_object"},  # Важно для JSON
                temperature=0.7,  # Баланс между креативностью и последовательностью
                max_tokens=2000
            )
            trace["timings_ms"]["llm_generation"] = round((time.perf_counter() - started_llm) * 1000, 2)

            # Парсим JSON
            result = json.loads(response)

            # Валидация если нужна
            if validate:
                started_validation = time.perf_counter()
                result = self._validate_and_fix(result, exercise_type, level)
                trace["timings_ms"]["validation"] = round((time.perf_counter() - started_validation) * 1000, 2)

            started_quality = time.perf_counter()
            quality_report = self.validator.validate_batch_quality(
                exercises=result.get("exercises", []),
                exercise_type=exercise_type,
                target_level=level,
                expected_count=plan["target_count"],
                min_score=config.MIN_QUALITY_SCORE_FOR_ACCEPT,
            )
            trace["timings_ms"]["quality_check"] = round((time.perf_counter() - started_quality) * 1000, 2)
            logger.info("Self-validation score=%s pass=%s", quality_report["score"], quality_report["pass"])

            refined = False
            if (
                validate
                and config.ENABLE_OPTIONAL_REFINEMENT
                and not quality_report["pass"]
                and result.get("exercises")
            ):
                logger.info("Refinement triggered due to low quality score")
                trace["events"]["refinement_called"] = True
                started_refinement = time.perf_counter()
                trace["events"]["llm_calls"] += 1
                refined_result = self._refine_result_once(
                    bad_result=result,
                    quality_report=quality_report,
                    exercise_type=exercise_type,
                    level=level,
                )
                refined_result = self._validate_and_fix(refined_result, exercise_type, level)

                refined_quality_report = self.validator.validate_batch_quality(
                    exercises=refined_result.get("exercises", []),
                    exercise_type=exercise_type,
                    target_level=level,
                    expected_count=plan["target_count"],
                    min_score=config.MIN_QUALITY_SCORE_FOR_ACCEPT,
                )

                if refined_quality_report["score"] >= quality_report["score"]:
                    result = refined_result
                    quality_report = refined_quality_report
                    refined = True
                    logger.info("Refinement accepted: improved score to %s", refined_quality_report["score"])
                else:
                    logger.info("Refinement discarded: score did not improve")
                trace["timings_ms"]["refinement"] = round((time.perf_counter() - started_refinement) * 1000, 2)

            # Добавляем метаданные
            result['metadata'] = {
                'type': exercise_type.value,
                'level': level.value,
                'grammar_topic': grammar_topic,
                'theme': theme,
                'count': len(result.get('exercises', [])),
                'generated_at': time.time(),
                'plan': plan,
                'quality': quality_report,
                'refined': refined,
                'source': 'llm'
            }

            trace["timings_ms"]["total"] = round((time.perf_counter() - started_total) * 1000, 2)
            if benchmark_trace_enabled:
                result['metadata']['benchmark_trace'] = trace

            self._save_to_cache(result, exercise_type, level, count, grammar_topic, theme)

            logger.info(
                "Generation finished: type=%s level=%s count=%s source=%s refined=%s score=%s",
                exercise_type.value,
                level.value,
                len(result.get("exercises", [])),
                result.get("metadata", {}).get("source"),
                refined,
                quality_report.get("score"),
            )

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response was: {response}")
            raise ValueError("AI returned invalid JSON")

        except Exception as e:
            logger.error(f"Error generating exercises: {e}")
            raise

    def _try_get_cached(
            self,
            exercise_type: ExerciseType,
            level: CEFRLevel,
            count: int,
            grammar_topic: Optional[str],
            theme: str,
            force_refresh: bool,
    ) -> Optional[Dict[str, Any]]:
        if not self.store:
            logger.info("Cache disabled")
            return None

        if force_refresh:
            logger.info("Cache bypassed by force_refresh for type=%s level=%s", exercise_type.value, level.value)
            return None

        return self.store.get_cached(
            exercise_type=exercise_type.value,
            level=level.value,
            count=count,
            grammar_topic=grammar_topic,
            theme=theme,
        )

    def _save_to_cache(
            self,
            result: Dict[str, Any],
            exercise_type: ExerciseType,
            level: CEFRLevel,
            count: int,
            grammar_topic: Optional[str],
            theme: str,
    ) -> None:
        if not self.store:
            return

        self.store.save(
            exercise_type=exercise_type.value,
            level=level.value,
            count=count,
            grammar_topic=grammar_topic,
            theme=theme,
            payload=result,
            quality_score=result.get("metadata", {}).get("quality", {}).get("score"),
            created_at=result.get("metadata", {}).get("generated_at", time.time()),
        )

    def get_cache_stats(self) -> Dict[str, Any]:
        if not self.store:
            return {"enabled": False}

        return {"enabled": True, **self.store.get_stats()}

    def _refine_result_once(
            self,
            bad_result: Dict[str, Any],
            quality_report: Dict[str, Any],
            exercise_type: ExerciseType,
            level: CEFRLevel,
    ) -> Dict[str, Any]:
        issues = "\n".join(f"- {issue}" for issue in quality_report.get("issues", [])) or "- Improve overall quality"
        messages = [
            {"role": "system", "content": PromptBuilder.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Improve this generated JSON so it better matches the requested exercise type and CEFR level.\n"
                    f"Exercise type: {exercise_type.value}\n"
                    f"CEFR level: {level.value}\n"
                    "Quality issues detected:\n"
                    f"{issues}\n\n"
                    "Current JSON:\n"
                    f"{json.dumps(bad_result, ensure_ascii=False)}\n\n"
                    "Return only valid JSON with key 'exercises'."
                ),
            },
        ]
        response = self._get_client().generate_with_retry(
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=2000,
        )
        logger.info("Refinement call completed")
        return json.loads(response)

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

        response = self._get_client().generate_with_retry(
            messages=messages,
            response_format={"type": "json_object"}
        )

        return json.loads(response)


# Глобальный экземпляр
generator = ExerciseGenerator()