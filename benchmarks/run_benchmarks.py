from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx

from ai_layer.exercise_generator import ExerciseGenerator
from ai_layer.promts import CEFRLevel, ExerciseType
from benchmarks.fake_client import FakeBenchmarkClient
from benchmarks.metrics import BenchmarkSample, summarize_samples


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run benchmark scenarios for generation pipeline.")
    parser.add_argument("--mode", choices=["direct", "api"], default="direct")
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--scenario-file", default="benchmarks/scenarios.json")
    parser.add_argument("--output-dir", default="benchmarks/results")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--use-fake-client", action="store_true")
    return parser.parse_args()


def load_scenarios(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("scenarios", [])


def _to_enum_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(payload)
    result["exercise_type"] = ExerciseType(result["exercise_type"])
    result["level"] = CEFRLevel(result["level"])
    result["benchmark_trace"] = True
    return result


def _extract_metadata(operation: str, response: Any) -> Dict[str, Any]:
    if operation == "batch":
        items = response.get("results", []) if isinstance(response, dict) else []
        successful = [item.get("data", {}) for item in items if item.get("success")]
        if not successful:
            return {"batch_success": 0.0}

        quality_scores = [
            item.get("metadata", {}).get("quality", {}).get("score")
            for item in successful
            if item.get("metadata", {}).get("quality", {}).get("score") is not None
        ]
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else None
        cache_hits = sum(1 for item in successful if item.get("metadata", {}).get("source") == "cache")

        return {
            "batch_success": round(len(successful) / max(1, len(items)), 4),
            "source": "cache" if cache_hits == len(successful) else "llm",
            "quality": {"score": round(avg_quality, 4)} if avg_quality is not None else {},
        }

    if operation == "generate":
        if isinstance(response, dict):
            return response.get("metadata", {})
        return {}

    return {}


def run_direct(generator: ExerciseGenerator, scenario: Dict[str, Any]) -> Tuple[bool, Any, str]:
    operation = scenario["operation"]
    payload = scenario["payload"]

    try:
        if operation == "generate":
            result = generator.generate_exercises(**_to_enum_request(payload))
        elif operation == "batch":
            requests = [_to_enum_request(item) for item in payload]
            result = {
                "results": [
                    {"success": True, "data": data}
                    for data in generator.batch_generate(requests=requests)
                ]
            }
        elif operation == "improve":
            result = generator.regenerate_with_feedback(
                original_exercise=payload["exercise"],
                feedback=payload["feedback"],
                exercise_type=ExerciseType(payload["exercise_type"]),
                level=CEFRLevel(payload["level"]),
            )
        else:
            return False, None, f"Unsupported operation: {operation}"

        return True, result, ""
    except Exception as exc:  # noqa: BLE001
        return False, None, str(exc)


def run_api(client: httpx.Client, base_url: str, scenario: Dict[str, Any]) -> Tuple[bool, Any, str]:
    operation = scenario["operation"]
    payload = scenario["payload"]

    endpoint_map = {
        "generate": "/api/v1/generate",
        "batch": "/api/v1/batch-generate",
        "improve": "/api/v1/improve",
    }
    endpoint = endpoint_map.get(operation)
    if not endpoint:
        return False, None, f"Unsupported operation: {operation}"

    response = client.post(f"{base_url}{endpoint}", json=payload, timeout=120)
    if response.status_code >= 400:
        return False, None, f"HTTP {response.status_code}: {response.text}"

    return True, response.json(), ""


def write_outputs(output_dir: Path, samples: List[BenchmarkSample], report: Dict[str, Any]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path = output_dir / f"benchmark_{timestamp}.json"
    csv_path = output_dir / f"benchmark_{timestamp}.csv"
    md_path = output_dir / f"benchmark_{timestamp}.md"

    payload = {
        "created_at": datetime.now().isoformat(),
        "samples": [sample.__dict__ for sample in samples],
        "report": report,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["scenario", "operation", "latency_ms", "success", "error"])
        writer.writeheader()
        for sample in samples:
            writer.writerow(
                {
                    "scenario": sample.scenario,
                    "operation": sample.operation,
                    "latency_ms": round(sample.latency_ms, 2),
                    "success": sample.success,
                    "error": sample.error or "",
                }
            )

    lines = [
        "# Benchmark Report",
        "",
        f"Created at: `{payload['created_at']}`",
        "",
        "## Overall",
        "",
    ]
    for key, value in report.get("overall", {}).items():
        lines.append(f"- {key}: {value}")

    lines.append("")
    lines.append("## Scenarios")
    lines.append("")
    for name, stats in report.get("scenarios", {}).items():
        lines.append(f"### {name}")
        for key, value in stats.items():
            lines.append(f"- {key}: {value}")
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path


def main() -> None:
    args = parse_args()
    scenarios = load_scenarios(Path(args.scenario_file))

    if not scenarios:
        raise ValueError("No scenarios found")

    generator = ExerciseGenerator(client=FakeBenchmarkClient()) if args.use_fake_client else ExerciseGenerator()
    http_client = httpx.Client()

    samples: List[BenchmarkSample] = []

    for scenario in scenarios:
        for iteration in range(args.iterations):
            start = time.perf_counter()
            if args.mode == "direct":
                success, response, error = run_direct(generator, scenario)
            else:
                success, response, error = run_api(http_client, args.base_url, scenario)

            elapsed_ms = (time.perf_counter() - start) * 1000
            samples.append(
                BenchmarkSample(
                    scenario=scenario["name"],
                    operation=scenario["operation"],
                    latency_ms=elapsed_ms,
                    success=success,
                    metadata=_extract_metadata(scenario["operation"], response) if success else {},
                    error=error or None,
                )
            )

            print(
                f"[{scenario['name']}] iter={iteration + 1}/{args.iterations} "
                f"success={success} latency_ms={elapsed_ms:.2f}"
            )

    report = summarize_samples(samples)
    output_path = write_outputs(Path(args.output_dir), samples, report)
    print(f"Benchmark completed. Main report: {output_path}")


if __name__ == "__main__":
    main()

