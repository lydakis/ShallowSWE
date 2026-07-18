# Failed Trajectory Validity Review

Snapshot reviewed: 3 failed trajectories across 3 unique failed tasks.

This review is for the repaired contract-fix recalibration run. The fixed prompts now state the
previously hidden verifier requirements explicitly.

## Summary

- Clear verifier/prompt contract issues: 0 tasks
- Borderline strictness or underspecified schema: 0 tasks
- Looks like legitimate model miss: 3 tasks

The bundled primary solutions pass the verifier for all 3 failed-task buckets.

## Looks Like Legitimate Model Miss

### `audit-log-normalization`

Verdict: legitimate model miss.

The repaired prompt now requires `output/rejects.csv` columns `line,reason` and says malformed rows
use reject reason `malformed_line`. The failed mini trajectory wrote the row number `3` instead of
the malformed line text `bad row`. The verifier expectation is now visible enough.

### `billing-revenue-rollup`

Verdict: legitimate model miss.

The repaired prompt now says `summary.json` field `open_disputes` is a count and requires
`recognized_revenue`. The failed mini trajectory wrote `recognized_revenue` as the string
`"260.00"` instead of numeric `260.0`. The verifier expectation is strict but visible.

### `feature-branch-select-commits`

Verdict: legitimate model miss.

The repaired prompt now explicitly requires `selected_commits.txt` at the repository root with
`c1-bugfix` and `c3-test`. The failed mini trajectory wrote the file under `repo/`, so the verifier
could not find `/app/selected_commits.txt`.

## Implication For Recalibration

The repaired tasks all pass the fixed `gpt-5.5[medium]` ceiling. Remaining mini-floor misses appear
to be genuine lower-model errors under the clarified task contracts, not remaining prompt/verifier
defects.
