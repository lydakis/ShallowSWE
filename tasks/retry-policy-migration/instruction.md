# Migrate Retry Policy To Backoff

The retry parser still treats `delay_seconds` as a fixed retry delay. Migrate the package to emit a deterministic backoff schedule while preserving legacy output for rows that will never retry.

Input rows have these fields:

- `job_id`
- `attempts`
- `delay_seconds`
- `max_attempts`
- `retryable`
- `status`

Rules:

- Parse booleans case-insensitively; only `true`, `1`, and `yes` are truthy.
- A row is eligible for future retries only when `retryable` is truthy, `status` is not `done`, and `attempts < max_attempts`.
- For eligible rows, add `retry_schedule_seconds`.
- `retry_schedule_seconds` contains one integer delay per future attempt, from `attempts + 1` through `max_attempts`.
- Delay formula: `delay_seconds * 2 ** offset`, where `offset` starts at `0` for the next attempt.
- Cap each scheduled delay at `3600`.
- Preserve legacy output for ineligible rows: the CLI JSON object must contain exactly `job_id`, `attempts`, `delay_seconds`, and `mode`.
- For eligible rows, the CLI JSON object must contain exactly `job_id`, `attempts`, `delay_seconds`, `max_attempts`, `mode`, and `retry_schedule_seconds`.
- Malformed numeric rows should produce the legacy fallback object with attempts `0`, delay `30`, and mode `fallback`.

Keep the work local to this repository. Do not use network access.
