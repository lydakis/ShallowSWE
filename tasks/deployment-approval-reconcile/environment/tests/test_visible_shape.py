from __future__ import annotations

from pathlib import Path
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
                "deploy_ops.cli",
                "--plan",
                "/app/fixtures/plan.json",
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
