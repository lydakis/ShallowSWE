from __future__ import annotations

import argparse
import json

from .api import LocalTicketApi
from .sync import reconcile_manifest


def main() -> None:
    parser = argparse.ArgumentParser(prog="ticket-sync")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--output-state", required=True)
    parser.add_argument("--audit-log", required=True)
    args = parser.parse_args()

    api = LocalTicketApi.load(args.state)
    with open(args.manifest) as handle:
        manifest = json.load(handle)
    reconcile_manifest(api, manifest, args.audit_log)
    api.dump(args.output_state)


if __name__ == "__main__":
    main()
