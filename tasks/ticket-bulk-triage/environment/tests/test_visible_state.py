from pathlib import Path
import json


def test_ticket_fixture_has_existing_records():
    tickets = json.loads((Path("api_state") / "tickets.json").read_text())
    assert len(tickets) >= 10
