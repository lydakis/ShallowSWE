# Normalize Audit Logs

Build a deterministic audit normalization pipeline in `scripts/build_outputs.py`.

The command is run from the repository root and must read:

- `input/actors.csv`
- `input/action_aliases.csv`
- every file under `input/sources/`, in source filename order

Then write exactly these files under `output/`:

- `output/normalized.csv`
- `output/rejects.csv`
- `output/summary.json`

Keep the work local to this repository. Do not use network access.

## Input Contracts

`input/actors.csv` columns:

- `actor_id`
- `name`
- `email`
- `aliases`

`aliases` is a semicolon-separated list. An input actor token may match `actor_id`, `name`,
`email`, or any alias, case-insensitively after trimming whitespace. Output rows use canonical
`actor_id` and `name`.

`input/action_aliases.csv` columns:

- `raw`
- `canonical`

An input action token must match a `raw` value case-insensitively after trimming whitespace.
Output rows use the mapped `canonical` value exactly as written in the alias file.

Files in `input/sources/` use one of three formats:

- `*.pipe.log`: pipe-delimited rows with fields
  `timestamp|actor|action|result|event_id`.
- `*.jsonl`: one JSON object per line with keys
  `timestamp`, `actor`, `action`, `result`, and `event_id`.
- `*.csv`: CSV with header
  `timestamp,actor,action,result,event_id`.

Unsupported source extensions do not need special handling.

Timestamps are ISO-8601 strings. Accept `Z` and explicit offsets such as `+02:00` or `-04:00`.
Convert every accepted timestamp to UTC as `YYYY-MM-DDTHH:MM:SSZ`. Reject timestamps with no
timezone offset.

Normalize `result` by trimming whitespace and lowercasing it.

Deduplicate by `event_id`. The first valid row seen wins, where input order is source filename
ascending, then row order inside that source. Later valid rows with the same `event_id` are rejected.

## Rejects

Write rejects in processing order with exactly these CSV columns:

- `source`
- `line`
- `reason`

`source` is the source filename only, for example `admin.jsonl`. `line` is the raw input line text
without the trailing newline. For CSV sources, use a comma-joined raw row value in source-column
order, excluding the header.

Use exactly these reject reasons:

- `malformed_line`: a pipe row with the wrong field count, invalid JSONL, or CSV parser shape that
  does not match the required header.
- `missing_field`: any required field is missing or blank.
- `invalid_timestamp`: timestamp cannot be parsed or has no timezone.
- `unknown_actor`: actor token is not present in `actors.csv`.
- `unknown_action`: action token is not present in `action_aliases.csv`.
- `duplicate_event`: a later valid row reuses an already accepted `event_id`.

Reject rows do not appear in `normalized.csv`.

## Normalized Rows

`output/normalized.csv` columns are exactly:

- `timestamp`
- `actor_id`
- `actor_name`
- `action`
- `result`
- `event_id`
- `source`

Sort normalized rows by `timestamp`, then `actor_id`, then `event_id`.

## Summary

`output/summary.json` has exactly these top-level keys:

- `actions`: object mapping canonical action to normalized-row count.
- `actors`: object mapping actor_id to normalized-row count.
- `rejected`: total rejected row count.
- `reject_reasons`: object mapping each reject reason that occurred at least once to its count.
- `rows`: total normalized row count.
- `sources`: object mapping source filename to normalized-row count.

All objects in `summary.json` must be sorted by key when written.
