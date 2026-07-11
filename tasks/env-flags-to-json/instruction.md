# Convert Env Flags To JSON

Read `input/flags.env` and create `output/flags.json` with typed values.

Parsing rules:

- Ignore comments, blank lines, malformed lines without `=`, and assignments with empty keys or
  empty values.
- Parse `true` and `false` case-insensitively as JSON booleans.
- Parse integers as JSON numbers.
- Parse decimal values as JSON numbers.
- Leave all other values as strings.
- Emit keys in deterministic sorted order.

## Acceptance Criteria

- Implement the transformation in `scripts/build_outputs.py`; the verifier reruns it on fresh inputs.
- JSON values are typed.
- Comments and empty assignments are omitted.
- Key order is deterministic.
- Do not modify files under `input/`; write exactly `output/flags.json` and no other output files.

Keep the work local to this repository. Do not use network access.
