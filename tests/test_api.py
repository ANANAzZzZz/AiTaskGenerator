from fastapi.testclient import TestClient

from controller_layer.generator_controller import app


class FakeGenerator:
    last_force_refresh = False

    def generate_exercises(self, **kwargs):
        FakeGenerator.last_force_refresh = bool(kwargs.get("force_refresh"))
        return {
            "exercises": [{"sentence": "I ___ English.", "correct_answer": "study"}],
            "metadata": {"count": 1},
        }

    def get_cache_stats(self):
        return {"enabled": True, "total_entries": 3}


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_generate_endpoint_returns_payload(monkeypatch):
    monkeypatch.setattr("controller_layer.generator_controller.generator", FakeGenerator())

    response = client.post(
        "/api/v1/generate",
        json={
            "exercise_type": "fill_blanks",
            "level": "B1",
            "count": 1,
            "grammar_topic": "Present Simple",
            "theme": "daily routines",
            "force_refresh": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "exercises" in payload
    assert payload["metadata"]["count"] == 1
    assert FakeGenerator.last_force_refresh is True


def test_cache_stats_endpoint(monkeypatch):
    monkeypatch.setattr("controller_layer.generator_controller.generator", FakeGenerator())

    response = client.get("/api/v1/cache/stats")

    assert response.status_code == 200
    assert response.json()["enabled"] is True

