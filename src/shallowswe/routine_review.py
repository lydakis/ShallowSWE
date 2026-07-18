from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import shutil
import tomllib

from .task_quality import (
    ROUTINE_REVIEW_RUBRIC_FIELDS,
    ROUTINE_REVIEW_SCHEMA_VERSION,
    quality_artifact_hashes,
    routine_review_artifact_hashes,
    routine_review_payload_issues,
)


REVIEW_PACKET_SCHEMA_VERSION = "shallowswe.routine_review_packet.v0.2"


def build_routine_review_packet(
    manifest_path: Path,
    output_dir: Path,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = (repo_root or Path.cwd()).resolve()
    manifest = json.loads(manifest_path.read_text())
    tasks_root = _repo_path(root, manifest.get("task_root") or "tasks")
    task_ids = [str(value) for value in manifest.get("task_ids", [])]
    if not task_ids:
        raise ValueError("pilot manifest has no task_ids")
    if output_dir.exists():
        raise ValueError(f"review packet output already exists: {output_dir}")
    output_dir.mkdir(parents=True)

    entries = []
    for task_id in task_ids:
        task = tasks_root / task_id
        if not task.is_dir():
            raise ValueError(f"missing pilot task: {task_id}")
        task_output = output_dir / "tasks" / task_id
        blind = task_output / "blind-review"
        blind.mkdir(parents=True)
        shutil.copy2(task / "instruction.md", blind / "instruction.md")
        _write_blind_task_metadata(task / "task.toml", blind / "task.toml")
        shutil.copytree(task / "environment", blind / "environment")

        after = task_output / "after-blind-review"
        after.mkdir()
        for name in (
            "investigator-review.md",
            "requirements.json",
            "negative-controls.json",
            "executions.json",
        ):
            source = task / "quality" / name
            if source.is_file():
                shutil.copy2(source, after / name)

        quality_hashes = quality_artifact_hashes(task)
        review_hashes = routine_review_artifact_hashes(task)
        form = _review_form(task_id, review_hashes)
        form_path = task_output / "review-form.json"
        form_path.write_text(json.dumps(form, indent=2) + "\n")
        entries.append(
            {
                "task_id": task_id,
                "instruction_hash": quality_hashes["instruction"],
                "environment_hash": quality_hashes["environment"],
                "task_metadata_hash": review_hashes["task_metadata"],
                "review_form": str(form_path.relative_to(output_dir)),
            }
        )

    packet = {
        "schema_version": REVIEW_PACKET_SCHEMA_VERSION,
        "pilot_manifest": manifest.get("name"),
        "task_count": len(entries),
        "tasks": entries,
    }
    (output_dir / "packet-manifest.json").write_text(json.dumps(packet, indent=2) + "\n")
    (output_dir / "README.md").write_text(_packet_readme())
    return packet


def audit_routine_review_packet(
    manifest_path: Path,
    packet_dir: Path,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = (repo_root or Path.cwd()).resolve()
    manifest = json.loads(manifest_path.read_text())
    tasks_root = _repo_path(root, manifest.get("task_root") or "tasks")
    task_ids = [str(value) for value in manifest.get("task_ids", [])]
    issues_by_task: dict[str, list[str]] = {}
    for task_id in task_ids:
        task = tasks_root / task_id
        form_path = packet_dir / "tasks" / task_id / "review-form.json"
        if not form_path.is_file():
            issues_by_task[task_id] = ["routine_review_form_missing"]
            continue
        try:
            payload = json.loads(form_path.read_text())
        except json.JSONDecodeError:
            issues_by_task[task_id] = ["routine_review_invalid_json"]
            continue
        issues = routine_review_payload_issues(task, payload)
        if issues:
            issues_by_task[task_id] = issues
    return {
        "schema_version": REVIEW_PACKET_SCHEMA_VERSION,
        "pilot_manifest": manifest.get("name"),
        "task_count": len(task_ids),
        "ready_to_import": not issues_by_task,
        "issues_by_task": issues_by_task,
    }


def import_routine_reviews(
    manifest_path: Path,
    packet_dir: Path,
    *,
    write: bool = False,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = (repo_root or Path.cwd()).resolve()
    report = audit_routine_review_packet(
        manifest_path,
        packet_dir,
        repo_root=root,
    )
    if write and not report["ready_to_import"]:
        raise RuntimeError(
            "routine review import blocked: forms are incomplete, rejected, or stale"
        )
    if write:
        manifest = json.loads(manifest_path.read_text())
        tasks_root = _repo_path(root, manifest.get("task_root") or "tasks")
        for task_id in manifest["task_ids"]:
            source = packet_dir / "tasks" / task_id / "review-form.json"
            destination = tasks_root / task_id / "quality" / "routine-review.json"
            destination.write_text(json.dumps(json.loads(source.read_text()), indent=2) + "\n")
    return report


def _review_form(task_id: str, hashes: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": ROUTINE_REVIEW_SCHEMA_VERSION,
        "task_id": task_id,
        "reviewer_count": 1,
        "reviewer": {
            "reviewer_id": "",
            "qualification": "",
            "independent_from_task_author": False,
        },
        "review_instructions": {
            "decision_values": ["accept", "revise", "reject"],
            "rubric_rating_values": ["pass", "revise", "reject"],
            "rationale_required": True,
            "artifact_hashes_editable": False,
        },
        "decision": "revise",
        "rubric": {
            field: {"rating": "revise", "rationale": ""} for field in ROUTINE_REVIEW_RUBRIC_FIELDS
        },
        "artifact_hashes": {
            "instruction": hashes["instruction"],
            "environment": hashes["environment"],
            "task_metadata": hashes["task_metadata"],
        },
    }


def _write_blind_task_metadata(source: Path, destination: Path) -> None:
    raw = tomllib.loads(source.read_text())
    task = raw.get("task")
    metadata = raw.get("metadata")
    if not isinstance(task, dict) or not isinstance(metadata, dict):
        raise ValueError(f"task metadata is missing required tables: {source}")

    name = task.get("name")
    category = metadata.get("category")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"task metadata is missing task.name: {source}")
    if not isinstance(category, str) or not category.strip():
        raise ValueError(f"task metadata is missing metadata.category: {source}")

    lines = [
        'schema_version = "review-view-v1"',
        "",
        "[task]",
        f"name = {json.dumps(name)}",
    ]
    description = task.get("description")
    if isinstance(description, str) and description.strip():
        lines.append(f"description = {json.dumps(description)}")
    lines.extend(["", "[metadata]", f"category = {json.dumps(category)}"])
    language = metadata.get("language")
    if isinstance(language, str) and language.strip():
        lines.append(f"language = {json.dumps(language)}")
    lines.extend(
        [
            'calibration_status = "withheld_for_blind_review"',
            "",
            "# Authored pressure labels, expected effort, patch metrics, model identities,",
            "# trajectories, pass rates, and calibration outcomes are withheld until the",
            "# independent construct review is complete.",
        ]
    )
    destination.write_text("\n".join(lines) + "\n")


def _packet_readme() -> str:
    return """# ShallowSWE independent routine-review packet

Review each `blind-review/` directory before opening `after-blind-review/`. Do not inspect task
solutions, hidden verifiers, or model trajectories. Complete every `review-form.json` with your own
identity, qualification, independent-author declaration, decision, and rubric rationales.

The reviewer `task.toml` is a redacted view. It shows task identity, category, and language while
withholding pressure labels and prior calibration evidence. Review forms remain hash-bound to the
original complete task metadata; do not replace their hashes with hashes of the redacted view.

Classify category by the requested work product. Patching source or tests is Code even when the
affected feature emits artifacts or controls a workflow. Artifact asks for a checked deliverable
using existing implementation. Workflow asks for a state transition using existing repository,
tool, or system behavior. Reject or revise a category label that does not match the work performed.

For the overall `decision`, use exactly `accept`, `revise`, or `reject`. `accept` means the task is
realistic routine software work and is fair to calibrate as written. For each rubric `rating`, use
exactly `pass`, `revise`, or `reject`; do not use `accept` as a rubric rating. Every rubric entry
requires a non-empty rationale. Do not change the artifact hashes.
"""


def _repo_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path
