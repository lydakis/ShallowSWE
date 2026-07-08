The ledger restatement command needs to apply late corrections to a multi-entity ledger and emit a
restatement evidence package.

Run shape:

```sh
python -m ledger_restate.cli --input-dir <input> --output-dir <output>
```

Input layout:

- `months/`: one CSV per month named `YYYY-MM.csv`.
- Each month CSV has columns exactly `entry_id,account_id,posted_at,amount_cents,memo`.
- `accounts.csv` has columns exactly
  `account_id,entity_id,owner_team,currency,materiality_cents`.
- `periods.csv` has columns exactly `month,status`, where status is `open`, `closed`, or `locked`.
- `corrections.csv` has columns exactly
  `correction_id,target_entry_id,restated_amount_cents,new_account_id,new_posted_at,reason,applied_at,requires_approval`.
- `correction_approvals.csv` has columns exactly
  `correction_id,approval_id,approved_by,approved_at,limit_cents`. Treat it as empty if absent.

Rules:

- The original month for an entry is the `YYYY-MM` prefix of `posted_at`.
- Read every `months/*.csv` file.
- `amount_cents`, `restated_amount_cents`, `materiality_cents`, and `limit_cents` are signed
  integers when non-empty.
- Corrections are processed by `applied_at` ascending, then `correction_id` ascending.
- Each ledger entry has mutable current state: amount, account, owner team, entity, currency, and
  posted month.
- A correction may change the amount, account, posted timestamp, or any combination of those fields:
  - blank `restated_amount_cents` means keep the current amount;
  - blank `new_account_id` means keep the current account;
  - blank `new_posted_at` means keep the current posted timestamp.
- Validate a correction before mutating the entry. A rejected correction never changes current
  state.
- Unknown `target_entry_id` rejects with status `rejected_unknown_entry`.
- Unknown `new_account_id` rejects with status `rejected_unknown_account`.
- If either the entry's current month or proposed new month has period status `locked`, reject with
  status `rejected_locked_period`.
- If either the entry's current month or proposed new month has period status `closed`, an approval
  is required.
- If `requires_approval` is `true`, an approval is required.
- If the absolute amount delta is greater than the current account's `materiality_cents`, an
  approval is required.
- An approval is valid when `correction_approvals.csv` contains the same `correction_id`, a non-empty
  `approval_id`, and `abs(delta_cents) <= limit_cents`.
- If approval is required but no valid approval exists, reject with status `rejected_missing_approval`.
- If the proposed state is identical to the current state after validation, reject with status
  `rejected_noop`.
- Accepted corrections use status `applied` and update the entry's current state.
- Re-running the command into an output directory that already contains previous outputs must be a
  no-op in content: overwrite deterministic files, never append duplicate rows.

Output files:

- `restated_rollups.csv`
- `correction_audit.csv`
- `owner_impact.csv`
- `summary.json`

`restated_rollups.csv` columns are exactly
`month,entity_id,currency,gross_cents,net_cents,correction_delta_cents,original_entry_count,final_entry_count`,
sorted by `month`, then `entity_id`, then `currency`.

- `gross_cents` is the original sum for entries whose original month/account belong to that
  month/entity/currency group.
- `net_cents` is the final sum for entries whose current month/account belong to that
  month/entity/currency group.
- Emit rows for the union of original and final groups.
- `correction_delta_cents` is `net_cents - gross_cents`.
- `original_entry_count` counts entries originally in the group.
- `final_entry_count` counts entries finally in the group.

`correction_audit.csv` columns are exactly
`correction_id,target_entry_id,status,reason,before_month,after_month,before_account_id,after_account_id,before_amount_cents,after_amount_cents,delta_cents,approval_id`,
sorted in correction processing order.

- `reason` is copied from `corrections.csv`.
- Unknown-entry rows use blank before/after fields, blank `delta_cents`, and blank `approval_id`.
- For other rejected rows, before fields describe current state and after fields describe the
  proposed state that failed validation.
- `delta_cents` is proposed amount minus current amount.
- `approval_id` is the valid approval id used for accepted rows; otherwise blank.

`owner_impact.csv` columns are exactly
`owner_team,applied_corrections,rejected_corrections,net_delta_cents,moved_in_entries,moved_out_entries,material_corrections`,
sorted by `owner_team`.

- Applied/rejected correction counts are attributed to the entry's before owner team.
- Unknown-entry rejections are attributed to owner team `unassigned`.
- `net_delta_cents` sums amount deltas for accepted corrections attributed to that owner team.
- `moved_out_entries` counts accepted corrections whose before owner differs from after owner,
  attributed to the before owner.
- `moved_in_entries` counts accepted corrections whose before owner differs from after owner,
  attributed to the after owner.
- `material_corrections` counts accepted corrections whose absolute amount delta is greater than
  the before account's `materiality_cents`.

`summary.json` has exactly these keys:

- `months`
- `entities`
- `currencies`
- `entries`
- `accepted_corrections`
- `rejected_corrections`
- `locked_rejections`
- `approval_rejections`
- `gross_cents`
- `correction_delta_cents`
- `net_cents`
- `moved_entries`
- `material_corrections`

`months`, `entities`, and `currencies` are counts over the emitted rollup rows. Keep the existing
CLI module and package name.
