from __future__ import annotations

import argparse
import json

from .api import LocalDeployApi
from .reconcile import reconcile


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--output-state", required=True)
    parser.add_argument("--audit-log", required=True)
    args = parser.parse_args()

    api = LocalDeployApi.load(args.state)
    plan = json.loads(open(args.plan).read())
    reconcile(api, plan, args.audit_log)
    api.dump(args.output_state)


if __name__ == "__main__":
    main()
