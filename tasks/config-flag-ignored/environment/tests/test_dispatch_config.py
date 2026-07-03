from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from dispatch_app.config import load_config
from dispatch_app.orders import load_orders
from dispatch_app.planner import plan_dispatch


class DispatchConfigTests(unittest.TestCase):
    def test_region_filter_is_loaded_from_env_file(self) -> None:
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            handle.write("DISPATCH_REGION=west\n")
            env_file = Path(handle.name)

        config = load_config(env_file)

        self.assertEqual(config.region, "west")

    def test_legacy_closed_flag_includes_archived_orders(self) -> None:
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            handle.write("DISPATCH_REGION=west\n")
            handle.write("DISPATCH_INCLUDE_CLOSED=1\n")
            env_file = Path(handle.name)

        plan = plan_dispatch(load_orders("/app/orders.json"), load_config(env_file))

        self.assertEqual(plan, ["ORD-100", "ORD-101"])


if __name__ == "__main__":
    unittest.main()
