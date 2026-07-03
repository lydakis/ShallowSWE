# Dispatch App

The nightly dispatch job reads orders from `orders.json` and emits the IDs that should be dispatched.

Configuration can be supplied through an env file:

- `DISPATCH_REGION`: optional region filter.
- `DISPATCH_INCLUDE_ARCHIVED=1`: include archived orders in dispatch output.
- `DISPATCH_INCLUDE_CLOSED=1`: legacy alias for including archived orders.
