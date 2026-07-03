from __future__ import annotations

import argparse

from .loader import load_transactions
from .report import build_report
from .serializers import render_report


def main() -> None:
    parser = argparse.ArgumentParser(prog="account-report")
    parser.add_argument("csv_path")
    parser.add_argument("--format", choices=["text", "csv"], default="text")
    args = parser.parse_args()

    report = build_report(load_transactions(args.csv_path))
    print(render_report(report, args.format))


if __name__ == "__main__":
    main()
