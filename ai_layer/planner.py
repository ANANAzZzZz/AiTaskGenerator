from typing import Dict, Any, Optional
import logging

from .promts import CEFRLevel, ExerciseType


logger = logging.getLogger(__name__)


class LightPlanner:
    """Легкий planner без отдельного LLM-вызова."""

    @staticmethod
    def build_plan(
        exercise_type: ExerciseType,
        level: CEFRLevel,
        count: int,
        grammar_topic: Optional[str],
        theme: str,
    ) -> Dict[str, Any]:
        target_count = max(1, count)
        grammar_focus = grammar_topic or "mixed grammar"

        plan_hints = (
            f"Plan: create exactly {target_count} items; "
            f"exercise_type={exercise_type.value}; level={level.value}; "
            f"grammar_focus={grammar_focus}; theme={theme}; "
            "keep JSON valid and consistent with template fields."
        )

        logger.info(
            "Planner built plan: type=%s level=%s target_count=%s theme=%s",
            exercise_type.value,
            level.value,
            target_count,
            theme,
        )

        return {
            "target_count": target_count,
            "grammar_focus": grammar_focus,
            "plan_hints": plan_hints,
        }

