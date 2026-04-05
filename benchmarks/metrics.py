from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any, Dict, List, Optional


@dataclass
class BenchmarkSample:
    scenario: str
    operation: str
    latency_ms: float
    success: bool
    metadata: Dict[str, Any]
    error: Optional[str] = None


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 2)

    rank = (len(ordered) - 1) * p
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    interpolated = ordered[lower] * (1 - fraction) + ordered[upper] * fraction
    return round(interpolated, 2)


def _extract_stage_timings(samples: List[BenchmarkSample]) -> Dict[str, float]:
    buckets: Dict[str, List[float]] = {}

    for sample in samples:
        trace = sample.metadata.get("benchmark_trace") or {}
        timings = trace.get("timings_ms") or {}
        for stage, value in timings.items():
            buckets.setdefault(stage, []).append(float(value))

    return {f"{stage}_avg_ms": round(mean(values), 2) for stage, values in buckets.items() if values}


def summarize_samples(samples: List[BenchmarkSample]) -> Dict[str, Any]:
    if not samples:
        return {"overall": {}, "scenarios": {}}

    by_scenario: Dict[str, List[BenchmarkSample]] = {}
    for sample in samples:
        by_scenario.setdefault(sample.scenario, []).append(sample)

    scenario_stats = {name: _summarize_group(group) for name, group in by_scenario.items()}
    overall = _summarize_group(samples)

    return {
        "overall": overall,
        "scenarios": scenario_stats,
    }


def _summarize_group(samples: List[BenchmarkSample]) -> Dict[str, Any]:
    latencies = [sample.latency_ms for sample in samples]
    successes = [sample for sample in samples if sample.success]
    metadata_list = [sample.metadata for sample in successes]

    cache_hits = sum(1 for m in metadata_list if m.get("source") == "cache")
    refined_runs = sum(1 for m in metadata_list if bool(m.get("refined")))
    plan_present = sum(1 for m in metadata_list if "plan" in m)

    quality_scores = [m.get("quality", {}).get("score") for m in metadata_list]
    quality_scores = [float(score) for score in quality_scores if score is not None]
    quality_passes = [m.get("quality", {}).get("pass") for m in metadata_list]
    quality_passes = [bool(flag) for flag in quality_passes if flag is not None]

    stage_timings = _extract_stage_timings(samples)

    return {
        "runs": len(samples),
        "success_rate": round(len(successes) / len(samples), 4),
        "latency_avg_ms": round(mean(latencies), 2),
        "latency_p50_ms": _percentile(latencies, 0.5),
        "latency_p95_ms": _percentile(latencies, 0.95),
        "cache_hit_rate": round(cache_hits / len(successes), 4) if successes else 0.0,
        "refinement_rate": round(refined_runs / len(successes), 4) if successes else 0.0,
        "plan_coverage_rate": round(plan_present / len(successes), 4) if successes else 0.0,
        "quality_avg_score": round(mean(quality_scores), 4) if quality_scores else None,
        "quality_pass_rate": round(sum(quality_passes) / len(quality_passes), 4) if quality_passes else None,
        **stage_timings,
    }

