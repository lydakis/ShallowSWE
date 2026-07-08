from pathlib import Path


def test_subscription_events_exist():
    assert (Path("input") / "subscription_events.csv").exists()
