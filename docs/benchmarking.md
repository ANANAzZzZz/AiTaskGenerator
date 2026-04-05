# Benchmarking

Этот документ описывает, как замерять производительность и качество генерации, включая полу-агентный цикл (`planner -> generation -> self-validation -> optional refinement`).

## Что измеряется

- `latency_avg_ms`, `latency_p50_ms`, `latency_p95_ms`
- `success_rate`
- `cache_hit_rate`
- `refinement_rate`
- `plan_coverage_rate`
- `quality_avg_score`, `quality_pass_rate`
- Средние тайминги этапов из `metadata.benchmark_trace.timings_ms`:
  - `cache_lookup_avg_ms`
  - `planner_avg_ms`
  - `llm_generation_avg_ms`
  - `validation_avg_ms`
  - `quality_check_avg_ms`
  - `refinement_avg_ms`
  - `total_avg_ms`

## Сценарии

По умолчанию используется `benchmarks/scenarios.json`:

- `generate_fill_blanks_cold` - генерация с `force_refresh=true`
- `generate_fill_blanks_warm` - повторная генерация с тем же ключом
- `generate_multiple_choice` - базовый сценарий другого типа
- `batch_mixed` - пакетная генерация нескольких запросов
- `improve_single_exercise` - вызов улучшения по фидбеку

## Запуск (direct)

Режим `direct` запускает benchmark без HTTP, напрямую через `ExerciseGenerator`.

```powershell
python -m benchmarks.run_benchmarks --mode direct --iterations 5 --use-fake-client
```

Без fake клиента (реальные вызовы LLM):

```powershell
python -m benchmarks.run_benchmarks --mode direct --iterations 3
```

## Запуск (api)

Режим `api` тестирует FastAPI endpoint-ы как black-box:

```powershell
python main.py
python -m benchmarks.run_benchmarks --mode api --iterations 3 --base-url http://127.0.0.1:8000
```

## Результаты

Скрипт сохраняет артефакты в `benchmarks/results/`:

- `benchmark_YYYYMMDD_HHMMSS.json` - полный отчет и сырые сэмплы
- `benchmark_YYYYMMDD_HHMMSS.csv` - плоская таблица прогонов
- `benchmark_YYYYMMDD_HHMMSS.md` - короткий читаемый отчет

## Практика сравнения

1. Запускайте одинаковый набор сценариев и одинаковое число итераций.
2. Сравнивайте `quality_avg_score`, `refinement_rate`, `latency_p95_ms` между коммитами.
3. Для cache-анализа делайте пары cold/warm сценариев.
4. Для CI используйте `--use-fake-client`, чтобы убрать флак и внешние лимиты.

