from retry_parser.parser import parse_retry_row
from retry_parser.scheduler import build_retry_plan


def test_visible_parser_keeps_legacy_fields_for_done_row():
    row = {
        "job_id": "visible",
        "attempts": "1",
        "delay_seconds": "10",
        "max_attempts": "3",
        "retryable": "true",
        "status": "done",
        "mode": "standard",
    }

    assert build_retry_plan(row)["mode"] == "standard"
    assert parse_retry_row(row)["max_attempts"] == 3
