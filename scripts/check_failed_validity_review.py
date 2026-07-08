from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    args = parse_args()
    audit = json.loads(args.audit_json.read_text())
    review = json.loads(args.review_json.read_text())

    failed_tasks = set(audit["summary"]["failed_by_task"])
    reviewed_tasks = set(review.get("tasks", {}))
    missing = sorted(failed_tasks - reviewed_tasks)
    stale_count = audit.get("failed_trajectory_count") != review.get("snapshot", {}).get(
        "failed_trajectory_count"
    )

    print(f"failed_tasks={len(failed_tasks)} reviewed_tasks={len(reviewed_tasks)}")
    if missing:
        print("missing qualitative review:")
        for task_id in missing:
            print(f"- {task_id}")
        return 1

    if stale_count:
        print(
            "warning: qualitative review trajectory count is stale "
            f"({review.get('snapshot', {}).get('failed_trajectory_count')} != "
            f"{audit.get('failed_trajectory_count')})"
        )
    print("all failed tasks have qualitative review coverage")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check that failed tasks are covered by the qualitative validity review."
    )
    parser.add_argument("audit_json", type=Path)
    parser.add_argument("review_json", type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
