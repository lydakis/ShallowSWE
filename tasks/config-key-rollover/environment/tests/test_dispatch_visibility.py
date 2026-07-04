from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from dispatch_app.config import load_config
from dispatch_app.orders import load_orders
from dispatch_app.planner import plan_dispatch


class DispatchVisibilityTests(unittest.TestCase):
    def _plan_for(self, env_text: str) -> list[str]:
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            handle.write(env_text)
            env_file = Path(handle.name)

        return plan_dispatch(load_orders("/app/orders.json"), load_config(env_file))

    def test_default_visibility_is_active_only(self) -> None:
        plan = self._plan_for("DISPATCH_REGION=west\nDISPATCH_ACCOUNT=acme\n")

        self.assertEqual(plan, ["DSP-100"])

    def test_legacy_closed_flag_still_includes_archived_orders(self) -> None:
        plan = self._plan_for(
            "DISPATCH_REGION=west\n"
            "DISPATCH_ACCOUNT=acme\n"
            "DISPATCH_INCLUDE_CLOSED=1\n"
        )

        self.assertEqual(plan, ["DSP-100", "DSP-101"])

    def test_account_filter_still_applies(self) -> None:
        plan = self._plan_for("DISPATCH_REGION=west\nDISPATCH_ACCOUNT=globex\n")

        self.assertEqual(plan, ["DSP-103"])


if __name__ == "__main__":
    unittest.main()
