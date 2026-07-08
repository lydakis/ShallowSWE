# Build Subscription Summary Report

Read `input/subscriptions.csv` and create `output/summary.json` and `output/plan_counts.csv`. Exclude trialing accounts from MRR.

## Acceptance Criteria

- Implement the transformation in `scripts/build_outputs.py`; the verifier reruns it on fresh inputs.
- MRR includes active subscriptions only.
- Cancelled subscriptions count as churned.
- Plan counts include active and cancelled non-trial rows.
- `output/summary.json` has exactly these keys:
  - `active_accounts`: count of active non-trial accounts.
  - `churned_accounts`: count of cancelled non-trial accounts.
  - `mrr`: total MRR for active accounts only.
- `output/plan_counts.csv` columns are exactly `plan,count`.
- Sort `plan_counts.csv` rows by `plan`.

Keep the work local to this repository. Do not use network access.
