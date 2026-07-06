from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import tempfile


def test_cli_writes_state_and_audit() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "output.json"
        audit = Path(tmp) / "audit.jsonl"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "release_train.cli",
                "--plan",
                "/app/fixtures/release_plan.json",
                "--state",
                "/app/fixtures/state.json",
                "--output-state",
                str(output),
                "--audit-log",
                str(audit),
            ],
            check=True,
        )

        state = json.loads(output.read_text())
        rows = [json.loads(line) for line in audit.read_text().splitlines()]

    assert "release/2.7" in state["branches"]
    assert rows
