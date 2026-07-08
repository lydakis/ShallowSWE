# Sessionize Access Logs

Read every `*.log` file under `input/` and write session outputs under `output/`.

Implement the operation in `scripts/sessionize.py`; the verifier reruns that script on fresh local
inputs.

Each valid log line has this whitespace-separated shape:

```text
<timestamp> <client_id> <method> <path> <status> <request_id>
```

Rules:

- Ignore blank lines.
- Reject malformed nonblank lines to `output/rejects.csv` with reason `malformed_line`.
- In `rejects.csv`, the `file` column is the input file basename, such as `api.log`, not a path.
- In `rejects.csv`, the `line` column is the 1-based input line number as a string.
- Sort valid events by `timestamp`, then `client_id`, then `request_id` before assigning sessions.
- Sessionize independently per `client_id`.
- A new session starts when the gap from the previous event for that client is greater than 15 minutes.
- A gap of exactly 15 minutes remains in the same session.
- Session ids are `S-<client_id>-<ordinal>`, with ordinals starting at `001` per client in chronological order.
- Sort final session rows by `client_id`, then session ordinal.
- `duration_seconds` is the difference between the first and last event timestamps in the session.
- `event_count` counts all valid events in the session.
- `status_max` is the maximum HTTP status in the session.
- Write `output/sessions.csv` with columns:
  `session_id,client_id,started_at,ended_at,event_count,duration_seconds,status_max,first_request_id,last_request_id`
- Write `output/rejects.csv` with columns `file,line,reason`.
- Write `output/summary.json` with keys `client_count`, `session_count`, `event_count`, and `rejected_count`.

Keep the work local to this repository. Do not use network access.
