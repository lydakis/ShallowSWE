Dispatch planning is rolling over a visibility config key.

Please migrate the repo from the old boolean environment key to the new enum key:

- old: `DISPATCH_INCLUDE_CLOSED=1`
- new: `DISPATCH_VISIBILITY=active|archived|all`

Visibility semantics:

- `active`: include active dispatchable orders only. This is the default.
- `archived`: include archived dispatchable orders only.
- `all`: include both active and archived dispatchable orders.

The old `DISPATCH_INCLUDE_CLOSED=1` key must keep working as a compatibility alias for `all`
when `DISPATCH_VISIBILITY` is absent. If both keys are present, `DISPATCH_VISIBILITY` wins.

Update the runtime config path, CLI help, env fixtures, and README to use the new key. Keep the
existing command/module name and the one-order-id-per-line output format stable. Existing
`DISPATCH_REGION` and `DISPATCH_ACCOUNT` filters should keep working.
