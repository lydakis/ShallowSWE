# Build Billing Revenue Rollup

Create revenue rollup artifacts under `output/` from the billing files in `input/`. Credits reduce recognized revenue; open disputes are listed separately.

## Acceptance Criteria

- Implement the transformation in `scripts/build_outputs.py`; the verifier reruns it on fresh inputs.
- Revenue is grouped by plan and net of credits.
- Open disputes are listed in adjustments.
- Summary total recognized revenue matches the rollup.

Keep the work local to this repository. Do not use network access.
