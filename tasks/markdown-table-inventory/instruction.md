# Reshape Markdown Inventory Table

Read `input/inventory.md` and create grouped `output/inventory.csv` plus `output/summary.json`. Ignore retired rows.

## Acceptance Criteria

- Implement the transformation in `scripts/build_outputs.py`; the verifier reruns it on fresh inputs.
- CSV rows are sorted by team then service.
- Retired services are excluded.
- Summary totals active services by team.
- `output/inventory.csv` columns are exactly `team,service,owner,status`.
- `output/summary.json` has exactly this shape:
  ```json
  {
    "active_services": 3,
    "teams": {
      "Example Team": 2
    }
  }
  ```
- `active_services` is the total number of non-retired inventory rows.
- `teams` maps each team name to its active service count.

Keep the work local to this repository. Do not use network access.
