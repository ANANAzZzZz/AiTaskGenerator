from ai_layer.exercise_store import ExerciseStore


def test_exercise_store_save_and_get_cached(tmp_path):
    db_path = tmp_path / "exercises_test.db"
    store = ExerciseStore(str(db_path))

    payload = {"exercises": [{"sentence": "I ___ home.", "correct_answer": "go"}]}
    store.save(
        exercise_type="fill_blanks",
        level="B1",
        count=1,
        grammar_topic="Present Simple",
        theme="daily life",
        payload=payload,
        quality_score=0.9,
        created_at=1.0,
    )

    cached = store.get_cached(
        exercise_type="fill_blanks",
        level="B1",
        count=1,
        grammar_topic="Present Simple",
        theme="daily life",
    )

    assert cached == payload


def test_exercise_store_stats(tmp_path):
    db_path = tmp_path / "exercises_test.db"
    store = ExerciseStore(str(db_path))

    store.save(
        exercise_type="fill_blanks",
        level="B1",
        count=2,
        grammar_topic=None,
        theme="travel",
        payload={"exercises": []},
        quality_score=0.5,
        created_at=10.0,
    )

    stats = store.get_stats()
    assert stats["total_entries"] == 1
    assert stats["unique_request_keys"] == 1


