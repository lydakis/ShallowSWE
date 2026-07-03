# ShallowSWE

An independent benchmark for the easy parts of software work.

ShallowSWE is inspired by DeepSWE's rigor, but is not affiliated with DeepSWE, Datacurve, or Pier. The benchmark target is different: ShallowSWE holds task difficulty near saturation and measures cost per successful completion by task category, tier, and model.

## Current Shape

- `SPEC.md` is the v0.1 product spec and source of truth.
- `tasks/` is a Pier-compatible local dataset.
- `src/shallowswe/` contains ShallowSWE metadata validation, Pier result export, and aggregation.
- Pier owns execution, sandboxing, agents, verifier runs, and trajectories.

## Quick Checks

```sh
uv run python -m unittest discover -s tests
uv run shallowswe tasks tasks
uv run pier run -p tasks/py-normalize-username --agent oracle --env docker --job-name shallowswe_oracle_probe --jobs-dir /tmp/shallowswe-pier -n 1 -k 1 -q
uv run shallowswe export-pier /tmp/shallowswe-pier/shallowswe_oracle_probe --tasks-root tasks > /tmp/shallowswe-results.json
uv run shallowswe aggregate /tmp/shallowswe-results.json
```

## Boundary

Do not build a ShallowSWE harness unless Pier cannot satisfy a concrete requirement. Local code should stay focused on the ShallowSWE problem definition: shallow-task metadata, calibration state, cost normalization, CPSC aggregation, and site-ready exports.
