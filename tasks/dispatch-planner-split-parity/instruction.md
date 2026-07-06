Dispatch planning has outgrown a single monolithic planner function.

Refactor the dispatch app so the public `dispatch_app.planner.plan_dispatch` API and CLI output
stay stable, but the planning logic is split into this pipeline layout:

- `dispatch_app/pipeline/__init__.py`
- `dispatch_app/pipeline/filters.py`
- `dispatch_app/pipeline/ordering.py`
- `dispatch_app/pipeline/planner.py`

Keep `dispatch_app.planner.plan_dispatch(orders, config)` as the public compatibility entrypoint.
It should delegate to the pipeline implementation rather than keeping the monolithic loop inline.

Preserve existing dispatch behavior byte-for-byte except for one documented bug:

- Existing filters still apply: optional region filter, optional account filter, ready orders only,
  active orders always included, archived orders included only when
  `DISPATCH_INCLUDE_ARCHIVED=1`, and blocked or cancelled orders excluded.
- The CLI must still print one order ID per line.
- Orders are ordered by `promised_at` ascending.
- Bug fix: when two dispatchable orders have the same `promised_at`, higher numeric `priority`
  must come before lower priority. If priority also ties, order by `id` ascending.

Do not rename the CLI module or the `Order` and `DispatchConfig` public dataclasses. Keep the
existing environment keys and JSON order schema working.
