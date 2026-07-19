# ShallowSWE

An independent benchmark for the easy parts of software work.

ShallowSWE measures verified software-task completion under a bounded repair loop. The repository
keeps benchmark execution, methodology analysis, and experiment planning as separate layers.

## Canonical Sources

- `docs/white-paper-v0.4.2.md`: frozen normative methodology.
- `docs/protocol-governance.md`: document authority, freeze rules, and code boundaries.
- `docs/weekend-six-task-kaggle-goal-2026-07-18.md`: current six-task execution goal.
- `docs/kaggle-runner.md`: generic Kaggle packaging and operating manual.
- `docs/README.md`: complete active, reference, future, and archive inventory.
- `tasks/`: canonical authored task packets.

The white paper and files under `paper/` are frozen. Change them only after concrete evidence and
explicit owner approval.

## Architecture

```text
Experiment plan -> RunSpec + TaskBundle -> harness -> ResultBundle
ResultBundle + MethodologySpec -> analyzer -> AnalysisBundle
```

The harness enforces execution facts: task and model identity, agent policy, seed, limits,
same-context continuation, sandbox isolation, usage checkpoints, verifier isolation, and artifacts.
It does not interpret experiment phases, evidence labels, funding, readiness, or publication status.
Those labels may travel as opaque `run_metadata` and are interpreted only by an external analysis or
planning document.

## Quick Checks

```sh
uv run python -m unittest discover -s tests
uv run shallowswe tasks tasks
uv run shallowswe run-spec \
  configs/experiments/weekend-six-task-kaggle-2026-07-18/run-spec-canary.json
```

Build a private Kaggle bundle from the canonical task tree and one exact run spec:

```sh
uv run shallowswe kaggle-pack /tmp/shallowswe-kaggle-canary \
  --task-id <task-id-a> \
  --task-id <task-id-b> \
  --tasks-root tasks \
  --config-file configs/mini-swe-agent-kaggle-repair-loop.yaml \
  --run-spec configs/experiments/weekend-six-task-kaggle-2026-07-18/run-spec-canary.json \
  --price-sheet prices/openrouter-2026-07-09.json \
  --mini-swe-agent-source-dir /Users/lydakis/Developer/oss/mini-swe-agent
```

Generate one bound Kaggle source per run unit:

```sh
uv run shallowswe kaggle-bound-sources \
  configs/experiments/weekend-six-task-kaggle-2026-07-18/run-spec-canary.json \
  /tmp/shallowswe-kaggle-canary-sources
```

Analyze normalized repair-loop rows with an exogenous methodology specification:

```sh
uv run shallowswe analyze-repair-loops \
  /tmp/shallowswe-repair-loop-results.json \
  configs/experiments/weekend-six-task-kaggle-2026-07-18/methodology-spec.json \
  /tmp/shallowswe-analysis-bundle.json \
  --scoring-run-spec /tmp/shallowswe-scoring-run-spec.json
```

See `docs/kaggle-runner.md` for bundle inspection, Kaggle publication, execution, artifact download,
and reconciliation.

## Boundary

ShallowSWE is not affiliated with DeepSWE, Datacurve, Pier, Kaggle, or model providers. Kaggle is
the primary funded execution backend. Pier remains useful for local portability and deterministic
development, but runner provenance is always retained.
