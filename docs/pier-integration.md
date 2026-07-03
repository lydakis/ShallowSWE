# Pier Integration Notes

Date checked: 2026-07-03.

ShallowSWE is independent from DeepSWE. Pier is useful because it is a standard open-source eval runner with sandboxing, agents, verifier execution, token/cost fields, and a trajectory viewer.

## What We Use From Pier

- Local task dataset execution via `pier run -p tasks`.
- Standard agents, especially `mini-swe-agent`.
- Docker or Modal environments.
- Programmatic verifier execution.
- Trial-level `result.json` files.
- Agent trajectories and token/cost totals.

## What ShallowSWE Owns

- The problem definition in `SPEC.md`.
- Original shallow tasks.
- Category and tier taxonomy: Fix, Transform, Operate, Invoke; T1, T2, T3.
- Calibration rules, including weakest-model saturation gates.
- Normalized `results.json` for the ShallowSWE site.
- CPSC and token-per-success reporting.

## Task Layout

Use Pier's local task format directly:

```text
tasks/<task-id>/
  task.toml
  instruction.md
  environment/
  solution/
  tests/
```

Put ShallowSWE-specific fields in `[metadata]`, not in custom directory structure:

```toml
[metadata]
category = "fix"
tier = "t1"
subtype = "single-function-bugfix"
```

## Current Decision

Use Pier as the runner until it fails a concrete ShallowSWE requirement. Do not maintain a parallel harness.
