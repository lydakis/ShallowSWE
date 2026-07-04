# Dispatch Planner

Run a dispatch plan with:

```sh
python -m dispatch_app.cli --orders /app/orders.json --env-file /app/.env.nightly
```

Environment keys:

- `DISPATCH_REGION`: optional region filter.
- `DISPATCH_ACCOUNT`: optional account filter.
- `DISPATCH_INCLUDE_CLOSED=1`: include archived orders in the plan.

The command prints one order id per line.
