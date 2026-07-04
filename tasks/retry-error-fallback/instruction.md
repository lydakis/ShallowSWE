# Return Retry Fallback For Malformed Rows

The retry parser raises on malformed numeric fields. Change it to return the documented fallback for malformed rows while preserving normal rows.

## Acceptance Criteria

- Valid rows preserve attempts, delay, and mode.
- Malformed numeric fields return attempts `0`, delay `30`, and mode `fallback`.
- The CLI emits one JSON row per input row.

Keep the work local to this repository. Do not use network access.
