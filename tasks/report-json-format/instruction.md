The account report CLI supports text and CSV output, but the operations team needs machine-readable JSON for a nightly job.

Add `--format json` to the existing `account-report` CLI. The JSON output should be a single object with `account`, `transaction_count`, `total_debits`, `total_credits`, and `net_change`. Keep the existing text and CSV formats working.
