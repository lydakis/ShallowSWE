The ledger restatement command needs to apply late-arriving corrections to monthly ledger files and
emit a restated audit package.

Run shape:

```sh
python -m ledger_restate.cli --input-dir <input> --output-dir <output>
```

Input layout:

- `months/`: one CSV per month named `YYYY-MM.csv`.
- Each month CSV has columns exactly `entry_id,account_id,posted_at,amount_cents,memo`.
- `corrections.csv` has columns exactly
  `correction_id,target_entry_id,restated_amount_cents,reason,applied_at`.

Rules:

- The month for an entry is the `YYYY-MM` prefix of `posted_at`.
- Read every `months/*.csv` file.
- `amount_cents` and `restated_amount_cents` are signed integers.
- Corrections are processed by `applied_at` ascending, then `correction_id` ascending.
- A correction whose `target_entry_id` does not exist is rejected with status
  `rejected_unknown_entry` and does not affect rollups.
- Accepted corrections restate the target entry's amount to `restated_amount_cents`.
- If multiple accepted corrections target the same entry, each audit row shows the current amount
  before that correction and the new amount after that correction. The final rollup uses the last
  accepted restated amount.
- Re-running the command into an output directory that already contains previous outputs must be a
  no-op in content: overwrite deterministic files, never append duplicate rows.

Output files:

- `restated_rollups.csv`
- `correction_audit.csv`
- `summary.json`

`restated_rollups.csv` columns are exactly
`month,gross_cents,correction_delta_cents,net_cents,entry_count`, sorted by `month`.

- `gross_cents` is the original sum of accepted month entries for that month.
- `correction_delta_cents` is the final restated total minus the original total for that month.
- `net_cents` is `gross_cents + correction_delta_cents`.
- `entry_count` counts original entries in that month.

`correction_audit.csv` columns are exactly
`correction_id,target_entry_id,month,original_amount_cents,restated_amount_cents,delta_cents,status,reason`,
sorted in correction processing order.

- Accepted rows use status `applied`.
- Rejected rows use blank `month`, `original_amount_cents`, and `delta_cents`.
- `reason` is copied from `corrections.csv`.

`summary.json` has exactly these keys:

- `months`
- `entries`
- `accepted_corrections`
- `rejected_corrections`
- `gross_cents`
- `correction_delta_cents`
- `net_cents`

Keep the existing CLI module and package name.
