from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json

from .pilot_launch import audit_pilot_launch_plan
from .pilot_readiness import audit_pilot_readiness
from .pilot_schedule import audit_pilot_schedule
from .kaggle_bundle import tree_sha256
from .task_quality import build_task_quality_report


PILOT_FREEZE_REPORT_SCHEMA_VERSION = "shallowswe.pilot_freeze_report.v0.1"


def build_pilot_freeze_report(
    manifest_path: Path,
    *,
    runner_bundle: Path,
    price_sheet: Path,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = (repo_root or Path.cwd()).resolve()
    manifest = json.loads(manifest_path.read_text())
    task_ids = [str(value) for value in manifest.get("task_ids", [])]
    blockers: list[str] = []

    readiness = audit_pilot_readiness(manifest_path, repo_root=root)
    blockers.extend(f"readiness_issue:{issue}" for issue in readiness["issues"])
    blockers.extend(
        blocker
        for blocker in readiness["blockers"]
        if not blocker.startswith("freeze_artifact_missing:")
        and blocker != "pilot_routine_review_incomplete"
    )

    tasks_root = _repo_path(root, manifest.get("task_root") or "tasks")
    quality_rows = {
        row["task_id"]: row
        for row in build_task_quality_report(tasks_root)["tasks"]
        if row["task_id"] in task_ids
    }
    if sorted(quality_rows) != sorted(task_ids):
        blockers.append("pilot_task_quality_rows_missing")
    if any(not quality_rows[task_id]["executed_quality_evidence_complete"] for task_id in quality_rows):
        blockers.append("pilot_task_quality_incomplete")
    if any(not quality_rows[task_id]["routine_review_complete"] for task_id in quality_rows):
        blockers.append("pilot_routine_review_incomplete")

    bundle_manifest_path = runner_bundle / "manifest.json"
    if not bundle_manifest_path.is_file():
        blockers.append("runner_bundle_manifest_missing")
        bundle_manifest: dict[str, Any] = {}
    else:
        bundle_manifest = json.loads(bundle_manifest_path.read_text())
    bundle_rows = {
        str(row.get("task_id")): row
        for row in bundle_manifest.get("tasks", [])
        if isinstance(row, dict) and row.get("task_id")
    }
    if sorted(bundle_rows) != sorted(task_ids):
        blockers.append("runner_bundle_task_set_mismatch")
    for task_id in task_ids:
        if task_id not in bundle_rows:
            continue
        task_path = tasks_root / task_id
        expected_hashes = {
            "source_task_hash": tree_sha256(task_path),
            "verifier_hash": tree_sha256(task_path / "tests"),
            "environment_hash": tree_sha256(task_path / "environment"),
        }
        for field, expected in expected_hashes.items():
            if bundle_rows[task_id].get(field) != expected:
                blockers.append(f"runner_bundle_{field}_mismatch:{task_id}")

    freeze = manifest.get("freeze_artifacts") or {}
    schedule_path = _repo_path(root, freeze.get("pilot_schedule") or "")
    launch_path = _repo_path(root, freeze.get("pilot_launch_plan") or "")
    schedule_report = audit_pilot_schedule(manifest_path, schedule_path)
    launch_report = audit_pilot_launch_plan(manifest_path, schedule_path, launch_path)
    if not schedule_report["valid"]:
        blockers.append("pilot_schedule_invalid")
    if not launch_report["valid"]:
        blockers.append("pilot_launch_plan_invalid")
    if not price_sheet.is_file():
        blockers.append("price_sheet_missing")
    protocol_sources = {
        "pilot_manifest": manifest_path,
        "pilot_schedule": schedule_path,
        "pilot_launch_plan": launch_path,
        "price_sheet": price_sheet,
    }
    for key, source in protocol_sources.items():
        attached_value = bundle_manifest.get(key)
        attached = runner_bundle / str(attached_value) if attached_value else None
        if attached is None or not attached.is_file():
            blockers.append(f"runner_bundle_{key}_missing")
        elif source.is_file() and attached.read_bytes() != source.read_bytes():
            blockers.append(f"runner_bundle_{key}_mismatch")

    task_hashes = {
        task_id: bundle_rows[task_id].get("source_task_hash")
        for task_id in task_ids
        if task_id in bundle_rows
    }
    verifier_hashes = {
        task_id: bundle_rows[task_id].get("verifier_hash")
        for task_id in task_ids
        if task_id in bundle_rows
    }
    environment_hashes = {
        task_id: bundle_rows[task_id].get("environment_hash")
        for task_id in task_ids
        if task_id in bundle_rows
    }
    if any(not value for values in (task_hashes, verifier_hashes, environment_hashes) for value in values.values()):
        blockers.append("runner_bundle_task_hash_missing")

    runner_paths = [runner_bundle / name for name in ("config", "notebook", "wheels")]
    if any(not path.exists() for path in runner_paths):
        blockers.append("runner_bundle_artifact_missing")

    artifacts = {
        "price_sheet": {
            "path": _display_path(price_sheet, root),
            "sha256": _hash_paths([price_sheet], base=root) if price_sheet.is_file() else None,
        },
        "task_hashes": task_hashes,
        "verifier_hashes": verifier_hashes,
        "environment_hashes": environment_hashes,
        "runner_artifact_hash": (
            _hash_paths(runner_paths, base=runner_bundle)
            if all(path.exists() for path in runner_paths)
            else None
        ),
        "pilot_schedule": _display_path(schedule_path, root),
        "pilot_schedule_hash": schedule_report["schedule_sha256"],
        "pilot_launch_plan": _display_path(launch_path, root),
        "pilot_launch_plan_hash": launch_report["launch_plan_sha256"],
    }
    return {
        "schema_version": PILOT_FREEZE_REPORT_SCHEMA_VERSION,
        "manifest": manifest.get("name"),
        "ready_to_freeze": not blockers,
        "blockers": sorted(set(blockers)),
        "candidate_artifacts": artifacts,
    }


def freeze_pilot_manifest(
    manifest_path: Path,
    *,
    runner_bundle: Path,
    price_sheet: Path,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    report = build_pilot_freeze_report(
        manifest_path,
        runner_bundle=runner_bundle,
        price_sheet=price_sheet,
        repo_root=repo_root,
    )
    if not report["ready_to_freeze"]:
        raise RuntimeError("pilot freeze blocked: " + ", ".join(report["blockers"]))
    manifest = json.loads(manifest_path.read_text())
    manifest["freeze_artifacts"] = report["candidate_artifacts"]
    frozen_text = json.dumps(manifest, indent=2) + "\n"
    manifest_path.write_text(frozen_text)
    bundle_manifest = json.loads((runner_bundle / "manifest.json").read_text())
    attached_manifest = runner_bundle / bundle_manifest["pilot_manifest"]
    attached_manifest.write_text(frozen_text)
    return report


def _hash_paths(paths: list[Path], *, base: Path) -> str:
    base = base.resolve()
    digest = hashlib.sha256()
    files: list[Path] = []
    for path in paths:
        path = path.resolve()
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(
                child
                for child in path.rglob("*")
                if child.is_file() and child.name != ".DS_Store" and "__pycache__" not in child.parts
            )
    for path in sorted(files, key=lambda candidate: str(candidate.relative_to(base))):
        digest.update(str(path.relative_to(base)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _repo_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root))
    except ValueError:
        return str(path.resolve())
