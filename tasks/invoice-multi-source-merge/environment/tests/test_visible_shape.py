from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class VisibleShapeTests(unittest.TestCase):
    def test_cli_writes_expected_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "invoice_merge.cli",
                    "--input-dir",
                    "/app/input",
                    "--output-dir",
                    str(output),
                ],
                check=True,
            )
            self.assertTrue((output / "merged_invoices.csv").exists())
            self.assertTrue((output / "rejected_invoices.csv").exists())
            self.assertTrue((output / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
