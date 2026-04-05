from benchmarks.metrics import BenchmarkSample, summarize_samples


def test_summarize_samples_reports_core_rates():
    samples = [
        BenchmarkSample(
            scenario="generate_a",
            operation="generate",
            latency_ms=120.0,
            success=True,
            metadata={
                "source": "llm",
                "refined": True,
                "plan": {"target_count": 5},
                "quality": {"score": 0.8, "pass": True},
                "benchmark_trace": {"timings_ms": {"llm_generation": 100.0, "total": 120.0}},
            },
        ),
        BenchmarkSample(
            scenario="generate_a",
            operation="generate",
            latency_ms=20.0,
            success=True,
            metadata={
                "source": "cache",
                "refined": False,
                "plan": {"target_count": 5},
                "quality": {"score": 0.9, "pass": True},
                "benchmark_trace": {"timings_ms": {"cache_lookup": 5.0, "total": 20.0}},
            },
        ),
    ]

    report = summarize_samples(samples)
    overall = report["overall"]

    assert overall["runs"] == 2
    assert overall["success_rate"] == 1.0
    assert overall["cache_hit_rate"] == 0.5
    assert overall["refinement_rate"] == 0.5
    assert overall["plan_coverage_rate"] == 1.0
    assert overall["quality_avg_score"] == 0.85
    assert "llm_generation_avg_ms" in overall


def test_summarize_samples_handles_failures():
    samples = [
        BenchmarkSample(
            scenario="generate_b",
            operation="generate",
            latency_ms=200.0,
            success=False,
            metadata={},
            error="boom",
        )
    ]

    report = summarize_samples(samples)
    overall = report["overall"]

    assert overall["runs"] == 1
    assert overall["success_rate"] == 0.0
    assert overall["cache_hit_rate"] == 0.0
    assert overall["quality_avg_score"] is None

