# Convert Access Logs To Incidents

Read `input/access.log` and create incidents, rejects, and summary outputs. Treat HTTP 500+ as high severity and 429 as medium.

## Acceptance Criteria

- Implement the transformation in `scripts/build_outputs.py`; the verifier reruns it on fresh inputs.
- Incidents are sorted by timestamp.
- Malformed lines are rejected.
- Summary counts incidents by severity.

Keep the work local to this repository. Do not use network access.
