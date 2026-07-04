# Adapt Dependency API Rename

The vendored notifier package now exposes `send_message` instead of `notify_user`. Update the app adapter without changing the vendor package.

## Acceptance Criteria

- `alerts.send_alert` uses `send_message`.
- Payloads preserve user ID, subject, and body.
- The old missing API is not called.

Keep the work local to this repository. Do not use network access.
