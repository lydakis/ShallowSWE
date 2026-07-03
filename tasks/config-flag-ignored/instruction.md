Nightly dispatch is still skipping archived orders even when the documented flag is enabled.

Please fix the config path so `DISPATCH_INCLUDE_ARCHIVED=1` includes archived orders in the dispatch plan. The older `DISPATCH_INCLUDE_CLOSED=1` key should keep working as a compatibility alias. Do not change the CLI command name.
