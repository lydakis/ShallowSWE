from __future__ import annotations

import argparse
import json

from .api import LocalReleaseApi
from .reconcile import reconcile_release


def main() -> None:
    parser = argparse.ArgumentParser(prog="release-train")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--output-state", required=True)
    parser.add_argument("--audit-log", required=True)
    args = parser.parse_args()

    api = LocalReleaseApi.load(args.state)
    with open(args.plan) as handle:
        plan = json.load(handle)
    reconcile_release(api, plan, args.audit_log)
    api.dump(args.output_state)


if __name__ == "__main__":
    main()
