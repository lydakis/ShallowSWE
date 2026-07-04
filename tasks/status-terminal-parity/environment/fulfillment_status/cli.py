from __future__ import annotations

from pathlib import Path
import argparse
import json

from .admin import repair_order_status
from .importer import import_orders_csv
from .report import build_report
from .statuses import status_help
from .storage import load_orders, save_orders
from .webhook import apply_carrier_webhook


def main() -> None:
    parser = argparse.ArgumentParser(prog="fulfillment-status")
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser("import-csv")
    import_parser.add_argument("--orders-csv", required=True)
    import_parser.add_argument("--output-json", required=True)

    webhook_parser = subparsers.add_parser("webhook")
    webhook_parser.add_argument("--orders", required=True)
    webhook_parser.add_argument("--event-json", required=True)
    webhook_parser.add_argument("--output-json", required=True)

    repair_parser = subparsers.add_parser("repair", epilog=status_help())
    repair_parser.add_argument("--orders", required=True)
    repair_parser.add_argument("--order-id", required=True)
    repair_parser.add_argument("--status", required=True)
    repair_parser.add_argument("--output-json", required=True)

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--orders", required=True)
    report_parser.add_argument("--output-json", required=True)

    args = parser.parse_args()
    if args.command == "import-csv":
        save_orders(args.output_json, import_orders_csv(args.orders_csv))
        return
    if args.command == "webhook":
        event = json.loads(Path(args.event_json).read_text())
        save_orders(args.output_json, apply_carrier_webhook(load_orders(args.orders), event))
        return
    if args.command == "repair":
        save_orders(
            args.output_json,
            repair_order_status(load_orders(args.orders), args.order_id, args.status),
        )
        return
    if args.command == "report":
        Path(args.output_json).write_text(
            json.dumps(build_report(load_orders(args.orders)), indent=2, sort_keys=True) + "\n"
        )
        return
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    main()
