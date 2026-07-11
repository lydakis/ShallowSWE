from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
import json

from .task_metadata import VALID_CATEGORIES, VALID_SIZES, load_task


TASK_FUNNEL_SCHEMA_VERSION = "shallowswe.task_funnel.v0.1"
TASK_FUNNEL_AUDIT_SCHEMA_VERSION = "shallowswe.task_funnel_audit.v0.1"

VALID_AUTHORING_STATUSES = {"planned", "authored", "needs_fix", "archived"}
VALID_FUNNEL_BUCKETS = {
    "not_triaged",
    "keep_small",
    "keep_medium",
    "keep_large",
    "too_easy_duplicate",
    "bad_task",
}
VALID_TRIAGE_STATUSES = {"not_run", "running", "complete", "blocked"}
VALID_BRIDGE_STATUSES = {"not_started", "running", "complete", "blocked"}
VALID_FORMAL_CEILING_STATUSES = {"not_run", "running", "complete", "blocked"}


def audit_task_funnel(
    manifest_path: Path,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Audit a task-funnel ledger without launching model runs."""

    root = repo_root or Path.cwd()
    manifest = json.loads(manifest_path.read_text())
    task_root = _repo_path(root, str(manifest.get("task_root") or "tasks"))

    issues: list[str] = []
    if manifest.get("schema_version") != TASK_FUNNEL_SCHEMA_VERSION:
        issues.append("unsupported_schema_version")

    candidate_target = manifest.get("candidate_target")
    if not isinstance(candidate_target, dict):
        issues.append("missing_candidate_target")
        candidate_target = {}

    min_candidates = int(candidate_target.get("min") or 0)
    max_candidates = int(candidate_target.get("max") or 0)
    if min_candidates < 1 or max_candidates < min_candidates:
        issues.append("invalid_candidate_target")

    policy = manifest.get("low_spend_policy")
    if not isinstance(policy, dict):
        issues.append("missing_low_spend_policy")
        policy = {}
    if policy.get("broad_scoring_allowed") is not False:
        issues.append("broad_scoring_not_disabled")
    if policy.get("codex_subscription_triage") is not True:
        issues.append("codex_triage_not_declared")
    if policy.get("bridge_required_before_official_label") is not True:
        issues.append("bridge_not_required_before_official_label")

    candidates_raw = manifest.get("candidates")
    if not isinstance(candidates_raw, list):
        issues.append("missing_candidates")
        candidates_raw = []

    if min_candidates and len(candidates_raw) < min_candidates:
        issues.append("candidate_count_below_target")
    if max_candidates and len(candidates_raw) > max_candidates:
        issues.append("candidate_count_above_target")

    seen: set[str] = set()
    candidate_reports: list[dict[str, Any]] = []
    for candidate in candidates_raw:
        if not isinstance(candidate, dict):
            issues.append("invalid_candidate")
            continue
        report = _audit_candidate(candidate, task_root=task_root, seen=seen)
        candidate_reports.append(report)

    candidate_issues = Counter(
        issue
        for report in candidate_reports
        for issue in report["issues"]
    )
    authoring_counts = Counter(report["authoring_status"] for report in candidate_reports)
    bucket_counts = Counter(report["funnel_bucket"] for report in candidate_reports)
    category_size_counts = Counter(
        f"{report['category']}/{report['size_hypothesis']}"
        for report in candidate_reports
        if report["category"] and report["size_hypothesis"]
    )

    tasks_to_author = [
        report["task_id"]
        for report in candidate_reports
        if report["task_id"] and not report["task_exists"]
    ]
    bridge_pending = [
        report["task_id"]
        for report in candidate_reports
        if report["task_id"]
        and report["funnel_bucket"] in {"keep_small", "keep_medium", "keep_large"}
        and report["bridge_validation_status"] != "complete"
    ]
    formal_ceiling_pending = [
        report["task_id"]
        for report in candidate_reports
        if report["task_id"]
        and report["funnel_bucket"] in {"keep_small", "keep_medium", "keep_large"}
        and not report["formal_ceiling_complete"]
    ]

    valid = not issues and not candidate_issues

    return {
        "schema_version": TASK_FUNNEL_AUDIT_SCHEMA_VERSION,
        "manifest": manifest.get("name"),
        "phase": manifest.get("phase"),
        "manifest_path": str(manifest_path),
        "task_root": str(task_root),
        "valid": valid,
        "issues": issues,
        "candidate_issue_counts": dict(sorted(candidate_issues.items())),
        "candidate_count": len(candidate_reports),
        "candidate_target": {
            "min": min_candidates,
            "max": max_candidates,
        },
        "authoring_status_counts": dict(sorted(authoring_counts.items())),
        "funnel_bucket_counts": dict(sorted(bucket_counts.items())),
        "category_size_counts": dict(sorted(category_size_counts.items())),
        "tasks_to_author": tasks_to_author,
        "formal_ceiling_pending": formal_ceiling_pending,
        "bridge_validation_pending": bridge_pending,
        "broad_scoring_allowed": policy.get("broad_scoring_allowed"),
        "codex_subscription_triage": policy.get("codex_subscription_triage"),
        "candidates": candidate_reports,
    }


def _audit_candidate(
    candidate: dict[str, Any],
    *,
    task_root: Path,
    seen: set[str],
) -> dict[str, Any]:
    issues: list[str] = []
    task_id = str(candidate.get("task_id") or "")
    if not task_id:
        issues.append("missing_task_id")
    elif task_id in seen:
        issues.append("duplicate_task_id")
    else:
        seen.add(task_id)

    category = str(candidate.get("category") or "")
    size_hypothesis = str(candidate.get("size_hypothesis") or "")
    authoring_status = str(candidate.get("authoring_status") or "")
    funnel_bucket = str(candidate.get("funnel_bucket") or "")

    if category not in VALID_CATEGORIES:
        issues.append("invalid_category")
    if size_hypothesis not in VALID_SIZES:
        issues.append("invalid_size_hypothesis")
    if authoring_status not in VALID_AUTHORING_STATUSES:
        issues.append("invalid_authoring_status")
    if funnel_bucket not in VALID_FUNNEL_BUCKETS:
        issues.append("invalid_funnel_bucket")

    codex_triage = candidate.get("codex_triage")
    if not isinstance(codex_triage, dict):
        issues.append("missing_codex_triage")
        codex_triage = {}
    codex_triage_status = str(codex_triage.get("status") or "")
    if codex_triage_status not in VALID_TRIAGE_STATUSES:
        issues.append("invalid_codex_triage_status")

    formal_ceiling = candidate.get("formal_ceiling")
    if not isinstance(formal_ceiling, dict):
        issues.append("missing_formal_ceiling")
        formal_ceiling = {}
    formal_ceiling_status = str(formal_ceiling.get("status") or "")
    if formal_ceiling_status not in VALID_FORMAL_CEILING_STATUSES:
        issues.append("invalid_formal_ceiling_status")
    formal_ceiling_target_n = int(formal_ceiling.get("target_n") or 0)
    formal_ceiling_current_n = int(formal_ceiling.get("current_n") or 0)
    formal_ceiling_passes = int(formal_ceiling.get("passes") or 0)
    formal_ceiling_pass_threshold = float(formal_ceiling.get("pass_threshold") or 0)
    formal_ceiling_complete = formal_ceiling_status == "complete"
    if formal_ceiling_complete and (
        formal_ceiling_target_n <= 0 or formal_ceiling_current_n < formal_ceiling_target_n
    ):
        issues.append("formal_ceiling_incomplete_sample")
        formal_ceiling_complete = False
    elif formal_ceiling_complete and not 0 < formal_ceiling_pass_threshold <= 1:
        issues.append("formal_ceiling_invalid_pass_threshold")
        formal_ceiling_complete = False
    elif formal_ceiling_complete and not 0 <= formal_ceiling_passes <= formal_ceiling_current_n:
        issues.append("formal_ceiling_invalid_pass_count")
        formal_ceiling_complete = False
    elif formal_ceiling_complete and (
        formal_ceiling_current_n <= 0
        or formal_ceiling_passes / formal_ceiling_current_n < formal_ceiling_pass_threshold
    ):
        issues.append("formal_ceiling_below_threshold")
        formal_ceiling_complete = False

    bridge_validation = candidate.get("bridge_validation")
    if not isinstance(bridge_validation, dict):
        issues.append("missing_bridge_validation")
        bridge_validation = {}
    bridge_validation_status = str(bridge_validation.get("status") or "")
    if bridge_validation_status not in VALID_BRIDGE_STATUSES:
        issues.append("invalid_bridge_validation_status")

    task_exists = False
    metadata_category = None
    metadata_size = None
    calibration_status = None
    if task_id:
        task_path = task_root / task_id
        task_exists = (task_path / "task.toml").exists()
        if task_exists:
            task = load_task(task_path)
            metadata_category = task.category
            metadata_size = task.size
            calibration_status = task.calibration_status
            if metadata_category != category:
                issues.append("metadata_category_mismatch")
            if metadata_size != size_hypothesis:
                issues.append("metadata_size_mismatch")

    if task_exists and authoring_status == "planned":
        issues.append("task_exists_but_marked_planned")
    if not task_exists and authoring_status in {"authored", "needs_fix"}:
        issues.append("missing_task_marked_authored")
    if funnel_bucket.startswith("keep_") and bridge_validation_status != "complete":
        issues.append("kept_without_bridge_validation")
    if funnel_bucket.startswith("keep_") and formal_ceiling_status != "complete":
        issues.append("kept_without_formal_ceiling")

    return {
        "slot": candidate.get("slot"),
        "task_id": task_id,
        "category": category,
        "size_hypothesis": size_hypothesis,
        "authoring_status": authoring_status,
        "funnel_bucket": funnel_bucket,
        "task_exists": task_exists,
        "metadata_category": metadata_category,
        "metadata_size": metadata_size,
        "calibration_status": calibration_status,
        "codex_triage_status": codex_triage_status,
        "formal_ceiling_status": formal_ceiling_status,
        "formal_ceiling_target_n": formal_ceiling_target_n,
        "formal_ceiling_current_n": formal_ceiling_current_n,
        "formal_ceiling_passes": formal_ceiling_passes,
        "formal_ceiling_complete": formal_ceiling_complete,
        "bridge_validation_status": bridge_validation_status,
        "next_action": candidate.get("next_action"),
        "issues": issues,
    }


def _repo_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path
