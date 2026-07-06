from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile


def test_cli_writes_outputs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "state.json"
        audit = Path(tmp) / "audit.jsonl"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "incident_comms.cli",
                "--timeline",
                "/app/fixtures/timeline.json",
                "--state",
                "/app/fixtures/state.json",
                "--output-state",
                str(output),
                "--audit-log",
                str(audit),
            ],
            check=True,
        )
        assert output.exists()
        assert audit.exists()
