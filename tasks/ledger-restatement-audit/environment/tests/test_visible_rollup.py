from __future__ import annotations

from pathlib import Path
import csv
import json
import tempfile

from ledger_restate.restate import restate


def test_existing_monthly_rollup_without_restatement_columns() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp)
        restate("/app/input", output)

        with (output / "restated_rollups.csv").open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        summary = json.loads((output / "summary.json").read_text())

    assert rows[0]["month"] == "2026-01"
    assert rows[0]["gross_cents"] == "15000"
    assert summary["gross_cents"] == 21000
