from __future__ import annotations

from pathlib import Path
import argparse
import csv
import json

from .importer import import_invoices


FIELDNAMES = [
    "invoice_id",
    "customer",
    "amount_usd_cents",
    "status",
    "issued_at",
    "updated_at",
    "source",
]
REJECT_FIELDNAMES = ["source", "row_ref", "invoice_id", "reason"]


def write_outputs(input_dir: str | Path, output_dir: str | Path) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    invoices, rejects = import_invoices(input_dir)

    with (output / "merged_invoices.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for invoice in sorted(invoices, key=lambda item: item.invoice_id):
            writer.writerow(
                {
                    "invoice_id": invoice.invoice_id,
                    "customer": invoice.customer,
                    "amount_usd_cents": invoice.amount_usd_cents,
                    "status": invoice.status,
                    "issued_at": invoice.issued_at,
                    "updated_at": invoice.updated_at,
                    "source": invoice.source,
                }
            )

    with (output / "rejected_invoices.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REJECT_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rejects)

    summary = {
        "invoice_count": len(invoices),
        "paid_total_usd_cents": sum(item.amount_usd_cents for item in invoices if item.status == "paid"),
        "open_total_usd_cents": sum(item.amount_usd_cents for item in invoices if item.status == "open"),
        "void_total_usd_cents": sum(item.amount_usd_cents for item in invoices if item.status == "void"),
        "rejected_count": len(rejects),
    }
    (output / "summary.json").write_text(json.dumps(summary, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    write_outputs(args.input_dir, args.output_dir)


if __name__ == "__main__":
    main()
