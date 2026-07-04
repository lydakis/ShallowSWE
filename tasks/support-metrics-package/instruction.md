# Produce Support Metrics Package

Build support metrics under `output/` from the CSV files in `input/`.

## Acceptance Criteria

- Implement the transformation in `scripts/build_outputs.py`; the verifier reruns it on fresh inputs.
- Agent summary includes ticket and breach counts.
- SLA breaches list only over-target tickets.
- Summary includes totals and escalation count.

Keep the work local to this repository. Do not use network access.
