from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import argparse
import json
import tomllib


CALIBRATION_TABLE = "calibration.codex_subscription_2026_07_06"
SCHEMA_VERSION = "shallowswe.codex_calibration_manifest.v0.1"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write Codex subscription calibration markers and task manifest."
    )
    parser.add_argument("results_dir", type=Path)
    parser.add_argument("--tasks-root", type=Path, default=Path("tasks"))
    parser.add_argument(
        "--doc",
        type=Path,
        default=Path("docs/codex-subscription-calibration-2026-07-06.md"),
    )
    parser.add_argument("--table-name", default=CALIBRATION_TABLE)
    parser.add_argument("--no-task-toml", action="store_true")
    args = parser.parse_args()

    results_dir = args.results_dir
    report_path = results_dir / "codex-subscription-sizing-report.json"
    audit_path = results_dir / "failed-trajectory-audit.json"
    review_path = results_dir / "failed-trajectory-validity-review.json"
    manifest_path = results_dir / "task-calibration-manifest.json"

    report = json.loads(report_path.read_text())
    audit = json.loads(audit_path.read_text())
    review = json.loads(review_path.read_text())

    failed_counts = Counter(
        trajectory["task_id"]
        for trajectory in audit.get("failed_trajectories", [])
    )
    review_tasks = review.get("tasks", {})

    manifest_tasks = []
    for task in sorted(report["tasks"], key=lambda item: item["task_id"]):
        task_id = task["task_id"]
        review_entry = review_tasks.get(task_id)
        contract_review = (
            review_entry["classification"]
            if isinstance(review_entry, dict)
            else "no_failed_trajectory"
        )
        contract_issue = contract_review in {
            "verifier_prompt_contract_issue",
            "borderline_prompt_issue",
            "borderline_strictness",
        }
        row = calibration_row_from_task(
            task,
            contract_review=contract_review,
            contract_issue=contract_issue,
            failed_trajectory_count=failed_counts[task_id],
            report_path=report_path,
            audit_path=audit_path,
        )
        manifest_tasks.append(row)
        if not args.no_task_toml:
            write_task_marker(args.tasks_root / task_id / "task.toml", row, args.table_name)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source_report": str(report_path),
        "source_failure_audit": str(audit_path),
        "source_validity_review": str(review_path),
        "task_count": len(manifest_tasks),
        "summary": {
            "assigned_size_counts": dict(sorted(Counter(t["assigned_size"] for t in manifest_tasks).items())),
            "contract_review_counts": dict(
                sorted(Counter(t["task_contract_review"] for t in manifest_tasks).items())
            ),
            "failed_trajectory_count": sum(t["failed_trajectory_count"] for t in manifest_tasks),
            "failed_task_count": sum(1 for t in manifest_tasks if t["failed_trajectory_count"]),
            "contract_issue_task_count": sum(1 for t in manifest_tasks if t["contract_issue"]),
        },
        "tasks": manifest_tasks,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    write_markdown(args.doc, manifest)
    print(manifest_path)
    print(args.doc)


def calibration_row_from_task(
    task: dict[str, Any],
    *,
    contract_review: str,
    contract_issue: bool,
    failed_trajectory_count: int,
    report_path: Path,
    audit_path: Path,
) -> dict[str, Any]:
    ceiling = task["codex_5_5_formal_ceiling"]
    ceiling_effort = format_effort(task["codex_5_5_formal_ceiling_effort"])
    formal_is_extra_high = ceiling_effort == "extra_high"

    row = {
        "task_id": task["task_id"],
        "category": task["category"],
        "metadata_size": task["metadata_size"],
        "assigned_size": task["provisional_floor_size"],
        "calibrated": formal_is_extra_high,
        "calibration_status": (
            "calibrated_provisional" if formal_is_extra_high else "triaged_medium_smoke_only"
        ),
        "band_confidence": "provisional_n3",
        "task_contract_review": contract_review,
        "contract_issue": contract_issue,
        "failed_trajectory_count": failed_trajectory_count,
        "ceiling_model_config": "openai/gpt-5.5[extra_high]",
        "ceiling_attempts": ceiling["attempts"] if formal_is_extra_high else 0,
        "ceiling_passes": ceiling["passes"] if formal_is_extra_high else 0,
        "ceiling_pass_rate": ceiling["pass_rate"] if formal_is_extra_high else 0.0,
        "floor_model_config": "openai/gpt-5.4-mini[low]",
        "floor_attempts": task["codex_5_4_mini_low_attempts"],
        "floor_passes": task["codex_5_4_mini_low_passes"],
        "floor_pass_rate": task["codex_5_4_mini_low_pass_rate"],
        "source_report": str(report_path),
        "source_failure_audit": str(audit_path),
    }

    smoke = task.get("codex_5_5_medium_smoke")
    if not formal_is_extra_high:
        smoke = ceiling
    if isinstance(smoke, dict) and int(smoke.get("attempts") or 0) > 0:
        row.update(
            {
                "medium_smoke_model_config": "openai/gpt-5.5[medium]",
                "medium_smoke_attempts": smoke["attempts"],
                "medium_smoke_passes": smoke["passes"],
                "medium_smoke_pass_rate": smoke["pass_rate"],
            }
        )

    return row


def write_task_marker(task_toml: Path, row: dict[str, Any], table_name: str) -> None:
    raw = tomllib.loads(task_toml.read_text())
    metadata = raw["metadata"]
    metadata_size = str(metadata.get("size"))
    if metadata_size != row["metadata_size"]:
        raise ValueError(
            f"{task_toml} metadata size changed under us: {metadata_size} != {row['metadata_size']}"
        )

    text = task_toml.read_text()
    text = remove_table(text, table_name)
    marker = format_marker(row, table_name)
    if not text.endswith("\n"):
        text += "\n"
    task_toml.write_text(text.rstrip() + "\n\n" + marker)


def remove_table(text: str, table_name: str) -> str:
    header = f"[{table_name}]"
    lines = text.splitlines()
    output: list[str] = []
    skipping = False
    for line in lines:
        if line.strip() == header:
            skipping = True
            continue
        if skipping and line.startswith("[") and line.endswith("]"):
            skipping = False
        if not skipping:
            output.append(line)
    return "\n".join(output).rstrip() + "\n"


def format_marker(row: dict[str, Any], table_name: str) -> str:
    fields: list[tuple[str, Any]] = [
        ("status", row["calibration_status"]),
        ("assigned_size", row["assigned_size"]),
        ("band_confidence", row["band_confidence"]),
        ("task_contract_review", row["task_contract_review"]),
        ("contract_issue", row["contract_issue"]),
        ("failed_trajectory_count", row["failed_trajectory_count"]),
    ]
    if "medium_smoke_model_config" in row:
        fields.extend(
            [
                ("medium_smoke_model_config", row["medium_smoke_model_config"]),
                ("medium_smoke_attempts", row["medium_smoke_attempts"]),
                ("medium_smoke_passes", row["medium_smoke_passes"]),
                ("medium_smoke_pass_rate", row["medium_smoke_pass_rate"]),
            ]
        )
    fields.extend(
        [
            ("ceiling_model_config", row["ceiling_model_config"]),
            ("ceiling_attempts", row["ceiling_attempts"]),
            ("ceiling_passes", row["ceiling_passes"]),
            ("ceiling_pass_rate", row["ceiling_pass_rate"]),
            ("floor_model_config", row["floor_model_config"]),
            ("floor_attempts", row["floor_attempts"]),
            ("floor_passes", row["floor_passes"]),
            ("floor_pass_rate", row["floor_pass_rate"]),
            ("source_report", row["source_report"]),
            ("source_failure_audit", row["source_failure_audit"]),
        ]
    )
    rendered = [f"[{table_name}]"]
    for key, value in fields:
        rendered.append(f"{key} = {toml_value(value)}")
    return "\n".join(rendered) + "\n"


def toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return repr(value)
    return json.dumps(str(value))


def format_effort(effort: str) -> str:
    return "extra_high" if effort == "xhigh" else effort


def write_markdown(path: Path, manifest: dict[str, Any]) -> None:
    summary = manifest["summary"]
    lines = [
        "# Codex Subscription Calibration 2026-07-06",
        "",
        f"Tasks calibrated: {manifest['task_count']}",
        "",
        "Band assignments in this document are provisional N=3 floor-probe labels, not "
        "statistically final task sizes.",
        "The GPT-5.5 Medium row is smoke evidence only; it is not the formal Extra High ceiling gate.",
        "",
        "## Summary",
        "",
        f"- Assigned size counts: {format_counts(summary['assigned_size_counts'])}",
        f"- Failed trajectories audited: {summary['failed_trajectory_count']}",
        f"- Failed tasks: {summary['failed_task_count']}",
        f"- Contract issue tasks: {summary['contract_issue_task_count']}",
        "",
        "## Statistical Status",
        "",
        "- Current floor bands are N=3 provisional labels.",
        "- With N=3, the only observable pass rates are `0/3`, `1/3`, `2/3`, and `3/3`.",
        "- The current provisional rule maps `0/3` to large, `1/3` or `2/3` to medium, and `3/3` to small.",
        "- N=3 is useful for smoke testing and prioritization, not statistically significant banding.",
        "- Use N=10 as the minimum useful confirmation pass.",
        "- Use N=16 to N=20 for a final calibrated snapshot, especially near the 0.30 and 0.70 band boundaries.",
        "- A statistically confirmed band should not have its uncertainty interval crossing a band boundary.",
        "",
        "## Task Contract Review Counts",
        "",
    ]
    for key, count in summary["contract_review_counts"].items():
        lines.append(f"- `{key}`: {count}")
    lines.extend(
        [
            "",
            "## Tasks",
            "",
            "| Task | Category | Previous Size | Provisional Size | Floor | Extra High Ceiling | Medium Smoke | Contract Review | Failed Trajectories |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | ---: |",
        ]
    )
    for task in manifest["tasks"]:
        floor = f"{task['floor_passes']}/{task['floor_attempts']}"
        ceiling = f"{task['ceiling_passes']}/{task['ceiling_attempts']}"
        medium_smoke = "pending"
        if "medium_smoke_attempts" in task:
            medium_smoke = f"{task['medium_smoke_passes']}/{task['medium_smoke_attempts']}"
        lines.append(
            "| "
            f"`{task['task_id']}` | "
            f"{task['category']} | "
            f"{task['metadata_size']} | "
            f"{task['assigned_size']} | "
            f"{floor} | "
            f"{ceiling} | "
            f"{medium_smoke} | "
            f"`{task['task_contract_review']}` | "
            f"{task['failed_trajectory_count']} |"
        )
    path.write_text("\n".join(lines) + "\n")


def format_counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in counts.items())


if __name__ == "__main__":
    main()
