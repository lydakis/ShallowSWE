# Repository Guidelines

## Project Structure & Module Organization

ShallowSWE is a Python package under `src/shallowswe/`. Core modules cover CLI entrypoints, task metadata validation, Pier export, budgeting, workload aggregation, and result summaries. Unit tests live in `tests/` and mirror package behavior with files such as `test_workload.py` and `test_task_metadata.py`.

Benchmark content lives in `tasks/<task-id>/` using Pier-compatible layout: `task.toml`, `instruction.md`, `environment/`, `tests/`, and optional `solution/`. Keep task assets local to each task. Project docs live in `docs/`, seed model panels in `panels/`, dated price sheets in `prices/`, sample output in `examples/`, and generated pilot artifacts in `results/`.

## Build, Test, and Development Commands

- `uv run python -m unittest discover -s tests`: run the repository unit test suite.
- `uv run shallowswe tasks tasks`: validate local ShallowSWE task metadata.
- `uv run shallowswe estimate-panel panels/deepswe-v1.1-expanded-pilot.json --prices prices/openrouter-2026-07-03.json --task-count 4 --rollouts 3`: estimate panel cost before execution.
- `uv run shallowswe export-pier /tmp/shallowswe-pier/<job> --tasks-root tasks`: convert Pier runs into ShallowSWE result rows.
- `uv run shallowswe aggregate /tmp/shallowswe-results.json`: summarize result rows.

Use `uv` as the project runtime. Do not add another package manager without approval.

## Coding Style & Naming Conventions

Target Python 3.12 and keep code compatible with the package settings in `pyproject.toml`. Ruff is configured with a 100-character line length. Use 4-space indentation, descriptive snake_case for functions and variables, PascalCase for classes, and lowercase kebab-case for task IDs such as `py-normalize-username`.

Keep local code focused on ShallowSWE metadata, pricing, aggregation, and export logic. Pier owns execution, sandboxing, agents, verifier runs, and trajectories.

## Testing Guidelines

Tests use Python `unittest`. Name files `tests/test_<feature>.py` and methods `test_<behavior>`. Add or adjust regression tests for behavior changes, especially task metadata validation, price matching, aggregation, and CLI output. For task fixtures, prefer small deterministic inputs over broad generated data.

## Commit & Pull Request Guidelines

Recent commits use short imperative subjects, for example `Add expanded pilot results`. Keep commits scoped and reviewable. PRs should include a concise summary, touched commands or data files, linked issues when relevant, and the verification command output. Include cost-estimate evidence before any broad Pier or model-panel run.

## Agent-Specific Instructions

Do not build a custom ShallowSWE harness unless Pier cannot satisfy a concrete requirement. Before expensive runs, use `shallowswe estimate-panel` with `--max-budget-usd` and `--fail-over-budget`.
