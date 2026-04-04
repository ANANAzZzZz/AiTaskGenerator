from typing import Dict, Tuple, List
import logging
from .promts import ExerciseType, CEFRLevel


logger = logging.getLogger(__name__)


class ExerciseValidator:
    """Валидация сгенерированных упражнений"""

    def __init__(self, check_grammar: bool = False, check_level: bool = True):
        self.check_grammar = check_grammar
        self.check_level = check_level

    def validate_structure(
            self,
            exercise: Dict,
            exercise_type: ExerciseType
    ) -> Tuple[bool, List[str]]:
        """
        Проверка структуры упражнения

        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        # Общие поля
        if not isinstance(exercise, dict):
            return False, ["Exercise must be a dictionary"]

        # Специфичные проверки для каждого типа
        if exercise_type == ExerciseType.FILL_BLANKS:
            required = ['sentence', 'correct_answer']
            for field in required:
                if field not in exercise:
                    errors.append(f"Missing required field: {field}")

            if 'sentence' in exercise and '___' not in exercise['sentence']:
                errors.append("Fill-in-blank sentence must contain ___")

        elif exercise_type == ExerciseType.MULTIPLE_CHOICE:
            required = ['question', 'options', 'correct_answer']
            for field in required:
                if field not in exercise:
                    errors.append(f"Missing required field: {field}")

            if 'options' in exercise:
                options = exercise['options']
                if not isinstance(options, dict) or len(options) < 3:
                    errors.append("Must have at least 3 options")

                if 'correct_answer' in exercise:
                    if exercise['correct_answer'] not in options:
                        errors.append("Correct answer must be one of the options")

        elif exercise_type == ExerciseType.ERROR_CORRECTION:
            required = ['incorrect_sentence', 'correct_sentence']
            for field in required:
                if field not in exercise:
                    errors.append(f"Missing required field: {field}")

        elif exercise_type == ExerciseType.SENTENCE_TRANSFORMATION:
            required = ['original_sentence', 'instruction', 'transformed_sentence']
            for field in required:
                if field not in exercise:
                    errors.append(f"Missing required field: {field}")

        elif exercise_type == ExerciseType.MATCHING:
            required = ['prompts', 'matches', 'answer_key']
            for field in required:
                if field not in exercise:
                    errors.append(f"Missing required field: {field}")

        elif exercise_type == ExerciseType.DIALOGUE:
            required = ['dialogue', 'correct_answer']
            for field in required:
                if field not in exercise:
                    errors.append(f"Missing required field: {field}")

        is_valid = len(errors) == 0
        if not is_valid:
            logger.debug("Structure validation failed: type=%s errors=%s", exercise_type.value, errors)
        return is_valid, errors

    def validate_grammar(self, exercise: Dict) -> bool:
        """
        Проверка грамматики (требует language-tool-python)

        pip install language-tool-python
        """
        try:
            import language_tool_python
            tool = language_tool_python.LanguageTool('en-US')

            # Проверяем текстовые поля
            texts_to_check = []

            if 'sentence' in exercise:
                # Убираем blank для проверки
                text = exercise['sentence'].replace('___', exercise.get('correct_answer', 'something'))
                texts_to_check.append(text)

            if 'question' in exercise:
                texts_to_check.append(exercise['question'])

            for text in texts_to_check:
                matches = tool.check(text)
                # Игнорируем незначительные ошибки
                serious_errors = [m for m in matches if m.category != 'TYPOGRAPHY']
                if len(serious_errors) > 0:
                    return False

            return True

        except ImportError:
            # Библиотека не установлена - пропускаем проверку
            return True

    def validate_level(self, exercise: Dict, target_level: CEFRLevel) -> bool:
        """
        Приблизительная проверка соответствия уровню

        Основано на:
        - Длина предложений
        - Сложность словаря (можно улучшить с помощью CEFR word lists)
        """

        # Примерные лимиты длины предложения по уровням
        sentence_length_limits = {
            CEFRLevel.A1: (5, 12),
            CEFRLevel.A2: (8, 15),
            CEFRLevel.B1: (10, 20),
            CEFRLevel.B2: (12, 25),
            CEFRLevel.C1: (15, 30),
            CEFRLevel.C2: (15, 35)
        }

        text = exercise.get('sentence') or exercise.get('question', '')
        if not text:
            return True

        word_count = len(text.split())
        min_len, max_len = sentence_length_limits[target_level]

        if word_count < min_len or word_count > max_len:
            return False

        return True

    def validate_batch_quality(
            self,
            exercises: List[Dict],
            exercise_type: ExerciseType,
            target_level: CEFRLevel,
            expected_count: int,
            min_score: float
    ) -> Dict:
        """Оценивает качество пачки и возвращает отчет для decision о refinement."""
        issues: List[str] = []

        if expected_count > 0 and len(exercises) < expected_count:
            issues.append(f"Expected {expected_count} exercises, got {len(exercises)}")

        valid_structure = 0
        valid_level = 0

        for exercise in exercises:
            is_valid, _ = self.validate_structure(exercise, exercise_type)
            if is_valid:
                valid_structure += 1

            if self.validate_level(exercise, target_level):
                valid_level += 1

        total = max(1, len(exercises))
        structure_ratio = valid_structure / total
        level_ratio = valid_level / total
        count_ratio = min(1.0, len(exercises) / max(1, expected_count))

        score = round((0.5 * structure_ratio) + (0.3 * level_ratio) + (0.2 * count_ratio), 4)

        if structure_ratio < 1.0:
            issues.append("Some exercises do not match required structure")
        if level_ratio < 0.8:
            issues.append("Many exercises are not aligned with target CEFR level")

        report = {
            "score": score,
            "pass": score >= min_score,
            "issues": issues,
            "stats": {
                "structure_ratio": structure_ratio,
                "level_ratio": level_ratio,
                "count_ratio": count_ratio,
            }
        }
        logger.info("Batch quality report: score=%s pass=%s issues=%s", report["score"], report["pass"], len(issues))
        return report
