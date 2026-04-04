from ai_layer.promts import PromptBuilder, ExerciseType, CEFRLevel


def test_build_prompt_for_matching_contains_user_and_system_messages():
    messages = PromptBuilder.build_prompt(
        exercise_type=ExerciseType.MATCHING,
        level=CEFRLevel.B1,
        count=2,
        theme="travel",
        context="airport",
    )

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "Create 2 matching exercises" in messages[1]["content"]

