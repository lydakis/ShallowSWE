# Investigator Review

Model-assisted QA only; this is not independent routine-engineer sign-off.

The review found an underspecified six-field grammar, status-range edges, and reject ordering. The
prompt now defines all three; hidden fixtures cover 499, 501, 599, 600, malformed statuses, and input
order, with controls for status hardcoding and sorted rejects.
