from __future__ import annotations

import argparse

from .importer import import_invoices
from .summary import summarize


def main() -> None:
    parser = argparse.ArgumentParser(prog="invoice-summary")
    parser.add_argument("csv_path")
    args = parser.parse_args()

    result = summarize(import_invoices(args.csv_path))
    print(f"invoices: {result['invoice_count']}")
    print(f"total: ${result['total_amount']:.2f}")
    print(f"open: ${result['open_amount']:.2f}")


if __name__ == "__main__":
    main()
