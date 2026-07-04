# Fix Missing Settings Defaults

The settings loader crashes when `notifications` is omitted. Update it so missing notification settings default to disabled while explicit values still win.

## Acceptance Criteria

- Missing `notifications`, `email`, or `sms` values default to `False`.
- Existing explicit values keep working.
- The CLI still emits sorted JSON.

Keep the work local to this repository. Do not use network access.
