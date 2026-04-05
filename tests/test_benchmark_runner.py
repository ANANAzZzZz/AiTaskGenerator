from ai_layer.exercise_generator import ExerciseGenerator
from benchmarks.fake_client import FakeBenchmarkClient
from benchmarks.run_benchmarks import run_direct


def test_run_direct_generate_with_fake_client():
    generator = ExerciseGenerator(client=FakeBenchmarkClient())
    scenario = {
        "name": "test_generate",
        "operation": "generate",
        "payload": {
            "exercise_type": "fill_blanks",
            "level": "B1",
            "count": 3,
            "grammar_topic": "Present Perfect",
            "theme": "travel",
            "context": "airport",
            "force_refresh": True,
        },
    }

    success, result, error = run_direct(generator, scenario)

    assert success is True
    assert error == ""
    assert "metadata" in result
    assert "benchmark_trace" in result["metadata"]

