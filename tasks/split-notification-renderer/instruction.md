# Split Notification Renderers

Split text and HTML rendering into separate modules while keeping `notifications.renderer` compatibility imports working.

## Acceptance Criteria

- `notifications.text` and `notifications.html` exist.
- Old renderer imports still work.
- Rendered output stays stable.

Keep the work local to this repository. Do not use network access.
