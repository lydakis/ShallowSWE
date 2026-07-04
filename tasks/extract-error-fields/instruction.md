# Extract Error Fields

Read `input/errors.json` and write `output/errors.csv` with columns `timestamp,service,code,message,request_id`.

## Acceptance Criteria

- Implement the transformation in `scripts/build_outputs.py`; the verifier reruns it on fresh inputs.
- Header and row order match the input.
- Missing request IDs are blank.
- Only requested fields are included.

Keep the work local to this repository. Do not use network access.
