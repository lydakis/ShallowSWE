# Kaggle Benchmarks Probe - 2026-07-08

## Summary

Kaggle Benchmarks can run ShallowSWE-style calibration probes, including seeded
`.evaluate(...)` sweeps, local verifier execution, bounded repair loops, and downloadable
per-seed artifacts. It should be treated as a useful calibration and public-mirror path,
not as unlimited free benchmark compute.

The observed account quota was `$10/day` and `$100/month` for Kaggle AI, and the quota
screen said that AI quota applies to Kaggle Benchmarks. For ShallowSWE, that makes quota
or resource-grant support the central scaling question.

## What Worked

- A small Kaggle benchmark exists at `https://www.kaggle.com/benchmarks/glydakis/shallowswe`.
- Kaggle task files can embed ShallowSWE fixtures, prompt the model, parse candidate file
  maps, run deterministic local verification, and record pass/fail assertions.
- `.evaluate(...)` preserves one downloaded `.run.json` per seed/subrun.
- Downloaded artifacts include assertion status, conversations, token counts, model cost
  fields, and latency.
- Source notebooks can be downloaded with `kaggle b t download <task> -s`.
- A 50-subrun batch, 5 tasks x 10 seeds, completed and downloaded successfully.

## Probe Results

Model: `gemini-3-flash-preview`

| Probe | Result | Downloaded raw model cost |
|---|---:|---:|
| `py-normalize-username`, 10 seeds | 10/10 | `$0.0181` |
| `dependency-api-rename`, 10 seeds | 10/10 | `$0.0392` |
| `subscription-summary-report`, 10 seeds | 10/10 | `$0.2314` |
| `env-flags-to-json`, 10 seeds inside 50-run batch | 10/10 | `$0.3449` |
| `retry-error-fallback`, uncapped inside 50-run batch | 0/10 | `$1.1159` |
| `retry-error-fallback`, capped retry probe | 4/10 | `$0.0261` |

The full 50-subrun batch passed 40/50. The failures were concentrated in
`retry-error-fallback`, which generated long failing outputs when uncapped. Those 10
failed subruns produced roughly 370k output tokens and dominated the batch cost.

## Implementation Notes

- Use `reasoning="none"` for cheap calibration unless a reasoning setting is being tested
  deliberately.
- Use `extra_api_params={"max_tokens": 4096}` to cap output on the current
  OpenAI-compatible Kaggle model route.
- Do not use `max_output_tokens` with the current route; it failed with
  `Completions.create() got an unexpected keyword argument 'max_output_tokens'`.
- Keep failed attempts in the same task function if repair-loop cost should count.
- Treat downloaded model-cost fields as per-run diagnostics. The Kaggle quota page is the
  authoritative budget boundary.

## Recommended Use

Use Kaggle now for:

- small representative task ports,
- N=10 seed calibration on selected tasks,
- public benchmark/mirror experiments,
- cross-provider panel checks if quota is granted,
- evidence for a Kaggle Benchmarks Resource Grant ask.

Do not use Kaggle yet as the only ShallowSWE execution path. Pier remains the canonical
runner for full ShallowSWE packets, repair-loop snapshots, and local result aggregation.

## Open Questions For Kaggle

- What is the recommended hidden-verifier pattern for public Kaggle Benchmarks tasks?
- Can public benchmark pages display or rank by derived metrics such as cost per
  successful completion?
- What quota or grant path supports N=10 x task x model repair-loop calibration?
- What are the practical task runtime, dependency, file-size, and dataset limits for a
  36-task v1 mirror?
- Should ShallowSWE represent repair loops inside one Kaggle task, or as multiple
  task/run records with custom aggregation?
