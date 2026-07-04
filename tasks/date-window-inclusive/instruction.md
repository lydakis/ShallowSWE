# Make Date Windows Inclusive

The event filter drops records that occur exactly on `--end-date`. Make the end date inclusive without changing start-date behavior or output order.

## Acceptance Criteria

- Start and end date records are included.
- Records after the end date remain excluded.
- CLI output matches service behavior.

Keep the work local to this repository. Do not use network access.
