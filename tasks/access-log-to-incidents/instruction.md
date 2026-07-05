# Convert Access Logs To Incidents

Read `input/access.log` and create incidents, rejects, and summary outputs. Treat HTTP 500+ as high severity and 429 as medium.

## Acceptance Criteria

- Implement the transformation in `scripts/build_outputs.py`; the verifier reruns it on fresh inputs.
- Incidents are sorted by timestamp.
- Malformed lines are rejected.
- Summary counts incidents by severity.
- Write exactly these files under `output/`:
  - `summary.json` with keys `high`, `medium`, and `total_incidents`.
  - `incidents.csv` with columns `timestamp,service,method,path,status,severity,request_id`.
  - `rejects.csv` with columns `line,reason`.
- Use severity `high` for HTTP status codes 500 and above, and `medium` for HTTP 429.
- Use reject reason `malformed_line` for lines that do not match the expected log shape.

Keep the work local to this repository. Do not use network access.
