# Build Developer Portal API Index

Create deterministic developer-portal artifacts under `output/` by reconciling the repository files
under `catalog/`, `owners/`, `apis/`, `docs/`, and `releases/`.

Implement the transformation in `scripts/build_portal_index.py`; the verifier reruns it on fresh
visible and hidden repositories. Keep the work local to this repository. Do not use network access.

## Inputs

- `catalog/services.json`: array of service objects with `service_id`, `name`, `owner_team`,
  `tier`, and `doc_slug`.
- `owners/teams.csv`: `team,manager,slack,email`.
- `apis/*.json`: OpenAPI-like fragments. Each file has `info.service_id`, `info.version`, and
  `paths`. Each path maps lowercase HTTP method names to an object with:
  - `operationId`
  - `visibility`: `public`, `partner`, or `internal`
  - optional `deprecated`: boolean, default `false`
  - optional `sunset`: string, default empty string
  - optional `flags`: array of strings, default empty array
- `docs/pages/*.md`: Markdown pages with simple frontmatter between the first two `---` lines.
  Frontmatter keys are `slug`, `title`, `service`, `status`, and optional `redirect_from`.
  `redirect_from` is a semicolon-separated list of source paths. Page URL is `/docs/<slug>`.
- `docs/redirects.csv`: `source,target,reason`.
- `releases/*.md`: Markdown release-note files. Under `## Added`, `## Changed`, or
  `## Deprecated`, supported bullet lines have this exact shape:
  `- <service_id> <METHOD> <path>: <note>`.

## Output Files

Write exactly these files under `output/`:

- `api_inventory.json`
- `owner_matrix.csv`
- `docs_actions.md`
- `summary.json`

## Shared Rules

- Sort services by `service_id`.
- Sort endpoints by `service_id`, then `path`, then lowercase `method`.
- Sort redirects by `source`.
- Sort broken links by `source_slug`, then `target`.
- Sort release-note rows by `service_id`, then `method`, then `path`, then `change_type`.
- Sort owner matrix rows by `team`.
- An active documentation page has `status=active`.
- A service is missing documentation when no active page has both `slug == service.doc_slug` and
  `service == service.service_id`.
- For Markdown links, only inspect targets starting with `/docs/`. External links and other
  internal paths are ignored.
- A `/docs/<slug>` link is broken with reason `missing_page` when no page has that slug.
- A `/docs/<slug>` link is broken with reason `deprecated_page` when the page exists but is not
  active.
- Redirect rows come from both `docs/redirects.csv` and every page `redirect_from` alias. A page
  alias row has `reason=page_alias` and `target=/docs/<slug>`.
- A redirect has status `ok` when its target is an active docs page, `broken_missing` when the
  target docs page is absent, and `broken_deprecated` when the target page exists but is not active.
- A redirect row's `service_id` is the target docs page frontmatter `service` when the target
  `/docs/<slug>` page exists, even if that page is deprecated. Use an empty string only when the
  target docs page is absent.
- A release-note bullet has `known_endpoint=true` when the exact `service_id`, lowercase method,
  and path exist in the API fragments.

## `api_inventory.json`

Top-level keys are exactly:

- `services`
- `endpoints`
- `redirects`
- `broken_links`
- `release_notes`

Each `services` row has exactly:

- `service_id`
- `name`
- `owner_team`
- `tier`
- `doc_slug`
- `owner_slack`
- `endpoint_count`
- `public_endpoint_count`
- `deprecated_endpoint_count`
- `missing_doc`
- `release_mentions`

Each `endpoints` row has exactly:

- `service_id`
- `method`
- `path`
- `operation_id`
- `visibility`
- `deprecated`
- `sunset`
- `flags`
- `doc_slug`
- `owner_team`

Each `redirects` row has exactly:

- `source`
- `target`
- `service_id`
- `status`
- `reason`

Each `broken_links` row has exactly:

- `source_slug`
- `target`
- `reason`

Each `release_notes` row has exactly:

- `service_id`
- `method`
- `path`
- `change_type`
- `note`
- `known_endpoint`

Write JSON deterministically with sorted object keys.

## `owner_matrix.csv`

Columns are exactly:

`team,manager,slack,email,services,public_endpoints,deprecated_endpoints,missing_docs`

`services` is a semicolon-separated list of service IDs owned by the team, sorted alphabetically.
`missing_docs` is the count of owned services with `missing_doc=true`.

## `docs_actions.md`

Write exactly this structure:

```md
# Developer Portal Actions

## Missing Documentation
<items>

## Broken Links
<items>

## Deprecated Endpoints
<items>
```

For missing documentation, item lines are:

`- <service_id> <name> -> /docs/<doc_slug>`

For broken links, item lines are:

`- <source_slug> -> <target> (<reason>)`

For deprecated endpoints, item lines are:

`- <service_id> <METHOD> <path> sunset=<sunset> owner=<owner_slack>`

If a section has no items, write exactly `- none`.

## `summary.json`

Top-level keys are exactly:

- `services`
- `endpoints`
- `public_endpoints`
- `deprecated_endpoints`
- `missing_docs`
- `redirects`
- `broken_links`
- `release_mentions`
- `owner_teams`

All values are integers. Write JSON deterministically with sorted object keys.
