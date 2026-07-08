from pathlib import Path
import json


def test_status_fixture_has_prior_statuses():
    assert json.loads((Path("api_state") / "statuses.json").read_text())


def test_release_fixture_has_gate_and_notification_state():
    assert json.loads((Path("input") / "release_rules.json").read_text())
    assert json.loads((Path("api_state") / "deployment_gates.json").read_text())
    assert json.loads((Path("api_state") / "notifications.json").read_text())
