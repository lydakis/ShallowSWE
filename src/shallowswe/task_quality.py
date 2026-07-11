from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
import json
import tomllib

from .admission import ALTERNATE_SOLUTION_DIRS
from .task_metadata import discover_tasks, is_official_calibration_status


TASK_QUALITY_SCHEMA_VERSION = "shallowswe.task_quality.v0.1"

REQUIREMENT_MAP_CANDIDATES = (
    "quality/requirements.json",
    "quality/requirement-map.json",
)
NEGATIVE_CONTROL_CANDIDATES = (
    "quality/negative-controls.json",
    "quality/negative_controls.json",
)
INVESTIGATOR_REVIEW_CANDIDATES = (
    "quality/investigator-review.md",
    "quality/investigator-review.json",
)

OPENAI_FAILURE_MODES = (
    "overly_strict_verifier",
    "underspecified_prompt",
    "low_coverage_verifier",
    "misleading_prompt",
)


def build_task_quality_report(root: Path, *, official_only: bool = False) -> dict[str, Any]:
    """Audit task-quality evidence structure without executing declared controls."""

    rows: list[dict[str, Any]] = []
    issue_counts: Counter[str] = Counter()
    failure_mode_counts: Counter[str] = Counter()
    contract_review_counts: Counter[str] = Counter()

    for task in discover_tasks(root):
        if official_only and not is_official_calibration_status(task.calibration_status):
            continue
        row = _audit_task_quality(task.path)
        row.update(
            {
                "task_id": task.task_id,
                "category": task.category,
                "size": task.size,
                "calibration_status": task.calibration_status,
                "official_candidate": is_official_calibration_status(task.calibration_status),
            }
        )
        for issue in row["quality_issues"]:
            issue_counts[issue] += 1
        for mode in row["openai_failure_modes_seen"]:
            failure_mode_counts[mode] += 1
        for review in row["contract_reviews"]:
            contract_review_counts[review] += 1
        rows.append(row)

    return {
        "schema_version": TASK_QUALITY_SCHEMA_VERSION,
        "tasks_root": str(root),
        "task_count": len(rows),
        "official_task_count": sum(1 for row in rows if row["official_candidate"]),
        "quality_evidence_complete_count": sum(
            1 for row in rows if row["quality_evidence_complete"]
        ),
        "quality_evidence_complete": all(row["quality_evidence_complete"] for row in rows),
        "quality_issue_counts": dict(sorted(issue_counts.items())),
        "openai_failure_mode_counts": {
            mode: failure_mode_counts.get(mode, 0)
            for mode in OPENAI_FAILURE_MODES
        },
        "contract_review_counts": dict(sorted(contract_review_counts.items())),
        "summary": _summary(rows),
        "tasks": sorted(rows, key=lambda row: str(row["task_id"])),
    }


def _audit_task_quality(path: Path) -> dict[str, Any]:
    raw = _load_task_toml(path)
    entries = _calibration_entries(raw)
    contract_reviews = _contract_reviews(entries)
    openai_failure_modes = _openai_failure_modes(entries)
    quality_labels = _quality_labels(entries)

    requirement_map = _load_quality_json(
        path,
        REQUIREMENT_MAP_CANDIDATES,
        required_key="requirements",
        required_fields=("id", "source", "behavior"),
        required_string_list_field="verifier_checks",
    )
    negative_controls = _load_quality_json(
        path,
        NEGATIVE_CONTROL_CANDIDATES,
        required_key="negative_controls",
        required_fields=("id", "description", "expected_failure"),
    )
    invalid_verifier_references = _invalid_verifier_references(
        path,
        requirement_map["items"] if requirement_map["valid"] else [],
    )
    investigator_review_path = _first_existing(path, INVESTIGATOR_REVIEW_CANDIDATES)
    alternate_solution_blocker = _alternate_solution_blocker(entries)

    local_evidence = {
        "has_instruction": (path / "instruction.md").exists(),
        "has_verifier": (path / "tests" / "test.sh").exists(),
        "has_reference_solution": (path / "solution" / "solve.sh").exists(),
        "has_alternate_solution": _has_alternate_solution(path),
    }
    quality_evidence = {
        "requirement_map_path": requirement_map["path"],
        "requirement_count": requirement_map["item_count"],
        "invalid_verifier_references": invalid_verifier_references,
        "negative_controls_path": negative_controls["path"],
        "negative_control_count": negative_controls["item_count"],
        "investigator_review_path": (
            str(investigator_review_path.relative_to(path))
            if investigator_review_path
            else None
        ),
    }

    issues = _quality_issues(
        local_evidence=local_evidence,
        requirement_map=requirement_map,
        negative_controls=negative_controls,
        invalid_verifier_references=invalid_verifier_references,
        alternate_solution_blocker=alternate_solution_blocker,
    )

    return {
        "local_evidence": local_evidence,
        "quality_evidence": quality_evidence,
        "contract_reviews": contract_reviews,
        "openai_failure_modes_seen": sorted(openai_failure_modes),
        "quality_labels": sorted(quality_labels),
        "alternate_solution_blocker": alternate_solution_blocker,
        "quality_issues": issues,
        "quality_evidence_complete": not issues,
    }


def _load_task_toml(path: Path) -> dict[str, Any]:
    with (path / "task.toml").open("rb") as handle:
        return tomllib.load(handle)


def _calibration_entries(raw: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    calibration = raw.get("calibration")
    if not isinstance(calibration, dict):
        return []

    entries: list[tuple[str, dict[str, Any]]] = []
    root_fields = {
        key: value
        for key, value in calibration.items()
        if not isinstance(value, dict)
    }
    if root_fields:
        entries.append(("calibration", root_fields))

    for name, value in calibration.items():
        if not isinstance(value, dict):
            continue
        if _contains_quality_signal(value):
            entries.append((f"calibration.{name}", value))
    return entries


def _contains_quality_signal(entry: dict[str, Any]) -> bool:
    return any(
        key in entry
        for key in (
            "task_contract_review",
            "contract_issue",
            "trajectory_audit",
            "local_solution_note",
            "alternate_solution_independent",
            "alternate_solution_note",
            "independent_alt_solution_status",
        )
    )


def _contract_reviews(entries: list[tuple[str, dict[str, Any]]]) -> list[str]:
    reviews: list[str] = []
    for _, entry in entries:
        review = entry.get("task_contract_review")
        if isinstance(review, str) and review:
            reviews.append(review)
    return reviews


def _openai_failure_modes(entries: list[tuple[str, dict[str, Any]]]) -> set[str]:
    modes: set[str] = set()
    for _, entry in entries:
        text = _entry_text(entry)
        if any(
            token in text
            for token in (
                "underspecified",
                "prompt_ambiguity",
                "prompt ambiguity",
                "prompt_repaired",
                "prompt repaired",
                "prompt_issue",
                "prompt issue",
                "contract_fixed",
                "contract fixed",
            )
        ):
            modes.add("underspecified_prompt")
        if any(
            token in text
            for token in (
                "strictness",
                "overly strict",
                "tolerance",
                "nonsemantic",
                "list order",
                "json list order",
                "unfair",
                "invalid_",
                "metric_label_parser",
                "trailing-markdown",
                "export_projection",
            )
        ):
            modes.add("overly_strict_verifier")
        if any(
            token in text
            for token in (
                "low coverage",
                "coverage weakness",
                "verifier weakness",
                "whole files",
                "hardcoded visible",
            )
        ):
            modes.add("low_coverage_verifier")
        if "misleading prompt" in text or "misleading_prompt" in text:
            modes.add("misleading_prompt")
    return modes


def _quality_labels(entries: list[tuple[str, dict[str, Any]]]) -> set[str]:
    labels: set[str] = set()
    for _, entry in entries:
        if entry.get("contract_issue") is True:
            labels.add("contract_issue_history")
        if _alternate_solution_blocker([("", entry)]):
            labels.add("alternate_solution_not_independent")
        if "verifier weakness" in _entry_text(entry):
            labels.add("verifier_coverage_repaired")
    return labels


def _entry_text(entry: dict[str, Any]) -> str:
    values: list[str] = []
    for key, value in entry.items():
        if isinstance(value, (str, bool, int, float)):
            values.append(f"{key}={value}")
    return " ".join(values).lower()


def _load_quality_json(
    path: Path,
    candidates: tuple[str, ...],
    *,
    required_key: str,
    required_fields: tuple[str, ...],
    required_string_list_field: str | None = None,
) -> dict[str, Any]:
    quality_path = _first_existing(path, candidates)
    if quality_path is None:
        return {
            "path": None,
            "item_count": 0,
            "items": [],
            "valid": False,
            "issue": "missing",
        }

    try:
        payload = json.loads(quality_path.read_text())
    except json.JSONDecodeError:
        return {
            "path": str(quality_path.relative_to(path)),
            "item_count": 0,
            "items": [],
            "valid": False,
            "issue": "invalid_json",
        }

    items = payload.get(required_key) if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return {
            "path": str(quality_path.relative_to(path)),
            "item_count": 0,
            "items": [],
            "valid": False,
            "issue": f"missing_{required_key}",
        }

    item_count = len(items)
    if not items:
        return {
            "path": str(quality_path.relative_to(path)),
            "item_count": 0,
            "items": [],
            "valid": False,
            "issue": f"empty_{required_key}",
        }
    if any(
        not isinstance(item, dict)
        or any(not _nonempty_string(item.get(field)) for field in required_fields)
        or (
            required_string_list_field is not None
            and not _nonempty_string_list(item.get(required_string_list_field))
        )
        for item in items
    ):
        return {
            "path": str(quality_path.relative_to(path)),
            "item_count": item_count,
            "items": items,
            "valid": False,
            "issue": "invalid_entry",
        }

    return {
        "path": str(quality_path.relative_to(path)),
        "item_count": item_count,
        "items": items,
        "valid": True,
        "issue": None,
    }


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _nonempty_string_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(_nonempty_string(item) for item in value)


def _invalid_verifier_references(path: Path, requirements: list[dict[str, Any]]) -> list[str]:
    invalid: set[str] = set()
    file_cache: dict[Path, str] = {}
    for requirement in requirements:
        for raw_reference in requirement.get("verifier_checks", []):
            reference = str(raw_reference)
            relative_path, separator, symbol = reference.partition(":")
            verifier_path = path / relative_path
            if not verifier_path.is_file():
                invalid.add(reference)
                continue
            if not separator:
                continue
            content = file_cache.setdefault(
                verifier_path,
                verifier_path.read_text(encoding="utf-8", errors="replace"),
            )
            symbol_parts = [part for part in symbol.split(".") if part]
            if not symbol_parts or any(part not in content for part in symbol_parts):
                invalid.add(reference)
    return sorted(invalid)


def _first_existing(path: Path, candidates: tuple[str, ...]) -> Path | None:
    for candidate in candidates:
        candidate_path = path / candidate
        if candidate_path.exists():
            return candidate_path
    return None


def _has_alternate_solution(path: Path) -> bool:
    return any((path / name / "solve.sh").exists() for name in ALTERNATE_SOLUTION_DIRS)


def _alternate_solution_blocker(entries: list[tuple[str, dict[str, Any]]]) -> str | None:
    for _, entry in entries:
        if entry.get("alternate_solution_independent") is False:
            return "alternate_solution_marked_not_independent"
        text = _entry_text(entry)
        if "mechanical copy" in text:
            return "alternate_solution_mechanical_copy"
        if "pending_stale_solution_alt" in text or "stale_solution_alt" in text:
            return "alternate_solution_stale_after_contract_change"
    return None


def _quality_issues(
    *,
    local_evidence: dict[str, bool],
    requirement_map: dict[str, Any],
    negative_controls: dict[str, Any],
    invalid_verifier_references: list[str],
    alternate_solution_blocker: str | None,
) -> list[str]:
    issues = [
        issue
        for issue, passed in (
            ("missing_instruction", local_evidence["has_instruction"]),
            ("missing_verifier", local_evidence["has_verifier"]),
            ("missing_reference_solution", local_evidence["has_reference_solution"]),
            ("missing_alternate_solution", local_evidence["has_alternate_solution"]),
        )
        if not passed
    ]

    if not requirement_map["valid"]:
        issues.append(f"requirement_map_{requirement_map['issue']}")
    if not negative_controls["valid"]:
        issues.append(f"negative_controls_{negative_controls['issue']}")
    if invalid_verifier_references:
        issues.append("requirement_map_invalid_verifier_reference")
    if alternate_solution_blocker:
        issues.append(alternate_solution_blocker)
    return sorted(issues)


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "authored_tasks": len(rows),
        "tasks_with_requirement_map": sum(
            1 for row in rows if row["quality_evidence"]["requirement_map_path"]
        ),
        "tasks_with_negative_controls": sum(
            1 for row in rows if row["quality_evidence"]["negative_controls_path"]
        ),
        "tasks_with_investigator_review": sum(
            1 for row in rows if row["quality_evidence"]["investigator_review_path"]
        ),
        "tasks_with_alternate_solution": sum(
            1 for row in rows if row["local_evidence"]["has_alternate_solution"]
        ),
        "tasks_with_alternate_solution_blocker": sum(
            1 for row in rows if row["alternate_solution_blocker"]
        ),
        "tasks_with_contract_issue_history": sum(
            1 for row in rows if "contract_issue_history" in row["quality_labels"]
        ),
    }
