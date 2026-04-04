from ai_layer.promts import ExerciseType, CEFRLevel
from ai_layer.validators import ExerciseValidator


def test_validate_multiple_choice_structure_success():
    validator = ExerciseValidator()
    exercise = {
        "question": "She ____ in London for five years.",
        "options": {"A": "lives", "B": "has lived", "C": "is living", "D": "lived"},
        "correct_answer": "B",
    }

    is_valid, errors = validator.validate_structure(exercise, ExerciseType.MULTIPLE_CHOICE)

    assert is_valid is True
    assert errors == []


def test_validate_level_rejects_too_short_for_b2():
    validator = ExerciseValidator()
    exercise = {"sentence": "Hello world"}

    assert validator.validate_level(exercise, CEFRLevel.B2) is False

