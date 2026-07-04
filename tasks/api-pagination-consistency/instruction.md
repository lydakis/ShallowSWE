# Add Pagination Consistently

The catalog service accepts pagination arguments but ignores them. Implement page/per-page slicing consistently.

## Acceptance Criteria

- Requested pages return the correct slice.
- Defaults return all items.
- Invalid partial or non-positive pagination raises an error.

Keep the work local to this repository. Do not use network access.
