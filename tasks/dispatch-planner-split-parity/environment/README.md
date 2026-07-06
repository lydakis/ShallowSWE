# Dispatch Planner

Run a dispatch plan with:

```sh
python -m dispatch_app.cli --orders /app/orders.json --env-file /app/.env.nightly
```

Environment keys:

- `DISPATCH_REGION`: optional region filter.
- `DISPATCH_ACCOUNT`: optional account filter.
- `DISPATCH_INCLUDE_ARCHIVED=1`: include archived orders in dispatch output.

The command prints one dispatchable order ID per line. Dispatchable orders must be ready, active
or allowed archived, and not blocked or cancelled.
