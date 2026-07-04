The fulfillment status package is adding a new terminal order status:

```text
return_to_sender
```

The old carrier abbreviation `rts` must remain accepted as an alias for `return_to_sender`.

Make the new status behave consistently across all existing status surfaces:

- CSV imports must accept both `return_to_sender` and `rts`, and must store the canonical value
  `return_to_sender`.
- Carrier webhooks must accept both spellings and update the order to the canonical value.
- The admin repair command must accept both spellings.
- Reports must count `return_to_sender` as terminal.
- `return_to_sender` is not a successful delivery. It should not increase the successful count.
- CLI help for the repair command should mention both `return_to_sender` and `rts`.

Keep existing behavior stable:

- Existing aliases such as `canceled` and `lost_in_transit` still work.
- `delivered`, `cancelled`, and `lost` remain terminal.
- `hold` and `pending_review` remain non-terminal.
- Unknown statuses must still be rejected. Do not make every unknown status terminal.
- Existing command names and JSON output shapes must stay unchanged.
