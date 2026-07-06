from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile


def test_cli_writes_expected_files() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "out"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "sla_report.cli",
                "--input-dir",
                "/app/input",
                "--output-dir",
                str(output),
            ],
            check=True,
        )
        assert (output / "ticket_sla.csv").exists()
        assert (output / "breach_summary.json").exists()
