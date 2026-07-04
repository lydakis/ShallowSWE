# Fix Token Expiry Units

Recent login tokens carry `expires_at` in milliseconds, while older tests still use seconds. Support both units.

## Acceptance Criteria

- Future millisecond tokens are accepted.
- Past millisecond tokens expire.
- Second-based tokens continue to work.

Keep the work local to this repository. Do not use network access.
