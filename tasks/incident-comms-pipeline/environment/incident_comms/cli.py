from __future__ import annotations

import argparse
import json

from .api import LocalStatuspageApi
from .pipeline import reconcile


def main() -> None:
    parser = argparse.ArgumentParser(prog="incident-comms")
    parser.add_argument("--timeline", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--output-state", required=True)
    parser.add_argument("--audit-log", required=True)
    args = parser.parse_args()
    api = LocalStatuspageApi.load(args.state)
    with open(args.timeline) as handle:
        timeline = json.load(handle)
    reconcile(api, timeline, args.audit_log)
    api.dump(args.output_state)


if __name__ == "__main__":
    main()
