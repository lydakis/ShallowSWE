# Move Module And Fix Imports

Move slug helpers into `text_tools/slug.py`, update imports, and leave a compatibility wrapper at the old module path.

## Acceptance Criteria

- `text_tools.slug.slugify` exists.
- `tools.slugify.slugify` still works.
- `app.build_slug` uses the new path.

Keep the work local to this repository. Do not use network access.
