from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import json
from typing import Any, Iterable, Iterator

from .transcript_candidate_coding import (
    classify_category,
    classify_maintenance_type,
    classify_sensitivity,
    classify_shape,
    classify_size,
    classify_strength,
    excerpt,
    next_step,
    normalize_space,
    readiness,
    sanitization_plan,
    score_request,
    should_skip_request,
    signal_terms,
    stable_candidate_id,
    title_from_text,
    verifier_idea,
)

SCHEMA_VERSION = "shallowswe.transcript_candidate.v0.1"


@dataclass(frozen=True)
class TranscriptRequest:
    source: str
    path: Path
    line_no: int
    text: str
    timestamp: str | None = None
    session_id: str | None = None
    cwd: str | None = None
    project: str | None = None


def iter_codex_requests(root: Path) -> Iterator[TranscriptRequest]:
    for path in sorted(root.rglob("*.jsonl")):
        session_id: str | None = None
        cwd: str | None = None
        for line_no, row in iter_jsonl(path):
            row_type = row.get("type")
            payload = row.get("payload")
            if row_type == "session_meta" and isinstance(payload, dict):
                raw_payload = payload.get("payload")
                meta = raw_payload if isinstance(raw_payload, dict) else payload
                session_id = as_str(meta.get("id") or meta.get("session_id")) or session_id
                cwd = as_str(meta.get("cwd")) or cwd
                continue
            if row_type != "response_item" or not isinstance(payload, dict):
                continue
            if payload.get("type") != "message" or payload.get("role") != "user":
                continue
            text = flatten_content(payload.get("content"))
            if should_skip_request(text):
                continue
            yield TranscriptRequest(
                source="codex",
                path=path,
                line_no=line_no,
                text=text,
                timestamp=as_str(row.get("timestamp")),
                session_id=session_id,
                cwd=cwd,
            )


def iter_claude_requests(root: Path) -> Iterator[TranscriptRequest]:
    for path in sorted(root.rglob("*.jsonl")):
        project = path.parent.name
        for line_no, row in iter_jsonl(path):
            row_type = row.get("type")
            if row_type == "queue-operation" and row.get("operation") == "enqueue":
                text = as_str(row.get("content")) or ""
                if should_skip_request(text):
                    continue
                yield TranscriptRequest(
                    source="claude",
                    path=path,
                    line_no=line_no,
                    text=text,
                    timestamp=as_str(row.get("timestamp")),
                    session_id=as_str(row.get("sessionId")),
                    project=project,
                )
                continue
            if row_type != "user" or row.get("isMeta") is True:
                continue
            message = row.get("message")
            if not isinstance(message, dict) or message.get("role") != "user":
                continue
            text = flatten_content(message.get("content"))
            if should_skip_request(text):
                continue
            yield TranscriptRequest(
                source="claude",
                path=path,
                line_no=line_no,
                text=text,
                timestamp=as_str(row.get("timestamp")),
                session_id=as_str(row.get("sessionId")),
                cwd=as_str(row.get("cwd")),
                project=project,
            )


def candidate_from_request(
    request: TranscriptRequest,
    *,
    min_score: int = 5,
    repo_hints: Iterable[str] = (),
) -> dict[str, Any] | None:
    text = normalize_space(request.text)
    if len(text) < 30:
        return None

    lower = text.lower()
    signals = sorted(signal_terms(lower, repo_hints))
    score = score_request(lower, signals)
    if score < min_score:
        return None

    category = classify_category(lower)
    size = classify_size(lower, score)
    sensitivity = classify_sensitivity(lower, request.path, request.cwd, request.project)
    candidate_id = stable_candidate_id(
        request.source,
        request.path,
        request.line_no,
        request.session_id,
        text,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "id": candidate_id,
        "title": title_from_text(text),
        "source": {
            "system": request.source,
            "path": str(request.path),
            "line_no": request.line_no,
            "timestamp": request.timestamp,
            "session_id": request.session_id,
            "cwd": request.cwd,
            "project": request.project,
        },
        "coding": {
            "category": category,
            "size_hypothesis": size,
            "maintenance_type": classify_maintenance_type(lower),
            "shape": classify_shape(lower, category),
            "candidate_strength": classify_strength(score),
            "score": score,
            "signals": signals,
        },
        "privacy": {
            "sensitivity": sensitivity,
            "sanitization_plan": sanitization_plan(sensitivity, category),
            "raw_excerpt_is_private": True,
        },
        "benchmarking": {
            "verifier_idea": verifier_idea(category),
            "readiness": readiness(score, sensitivity, lower),
            "next_step": next_step(score, sensitivity, lower),
        },
        "raw_request_excerpt": excerpt(text),
    }


def mine_candidates(
    *,
    codex_root: Path | None,
    claude_root: Path | None,
    min_score: int = 5,
    repo_hints: Iterable[str] = (),
    source_hints: Iterable[str] = (),
    max_candidates: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    requests: list[TranscriptRequest] = []
    source_counts: Counter[str] = Counter()
    if codex_root and codex_root.exists():
        for request in iter_codex_requests(codex_root):
            source_counts["codex_requests"] += 1
            requests.append(request)
    if claude_root and claude_root.exists():
        for request in iter_claude_requests(claude_root):
            source_counts["claude_requests"] += 1
            requests.append(request)

    selected_source_hints = [hint for hint in source_hints if hint.strip()]
    scoped_requests = [
        request
        for request in requests
        if _request_matches_source_hints(request, selected_source_hints)
    ]

    seen: set[str] = set()
    candidates: list[dict[str, Any]] = []
    for request in scoped_requests:
        candidate = candidate_from_request(
            request,
            min_score=min_score,
            repo_hints=repo_hints,
        )
        if candidate is None:
            continue
        text_hash = stable_candidate_id("dedupe", Path(), 0, None, request.text)
        if text_hash in seen:
            continue
        seen.add(text_hash)
        candidates.append(candidate)

    candidates.sort(
        key=lambda row: (
            -int(row["coding"]["score"]),
            str(row["source"].get("timestamp") or ""),
            row["id"],
        )
    )
    if max_candidates is not None:
        candidates = candidates[:max_candidates]

    inventory = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "codex_root": str(codex_root) if codex_root else None,
        "claude_root": str(claude_root) if claude_root else None,
        "source_counts": dict(source_counts),
        "source_hints": selected_source_hints,
        "scoped_request_count": len(scoped_requests),
        "candidate_count": len(candidates),
        "deduped_request_count": len(seen),
    }
    return candidates, inventory


def _request_matches_source_hints(
    request: TranscriptRequest,
    source_hints: list[str],
) -> bool:
    if not source_hints:
        return True
    source_blob = " ".join(
        value
        for value in (
            str(request.path),
            request.cwd or "",
            request.project or "",
        )
        if value
    ).lower()
    return any(hint.lower() in source_blob for hint in source_hints)


def validate_private_output_dir(out_dir: Path, *, public_repo_root: Path) -> None:
    """Reject raw transcript output inside tracked areas of the public repository."""

    resolved_output = out_dir.expanduser().resolve()
    resolved_repo = public_repo_root.expanduser().resolve()
    try:
        relative = resolved_output.relative_to(resolved_repo)
    except ValueError:
        return
    if relative.parts and relative.parts[0] == "tmp":
        return
    raise ValueError(
        "private output must be outside the public repository or under its ignored tmp/ directory"
    )


def summarize_candidates(candidates: list[dict[str, Any]], inventory: dict[str, Any]) -> dict[str, Any]:
    def count(path: tuple[str, ...]) -> dict[str, int]:
        counter: Counter[str] = Counter()
        for candidate in candidates:
            value: Any = candidate
            for key in path:
                value = value[key]
            counter[str(value)] += 1
        return dict(sorted(counter.items()))

    return {
        "schema_version": SCHEMA_VERSION,
        "inventory": inventory,
        "counts": {
            "source": count(("source", "system")),
            "category": count(("coding", "category")),
            "size_hypothesis": count(("coding", "size_hypothesis")),
            "maintenance_type": count(("coding", "maintenance_type")),
            "sensitivity": count(("privacy", "sensitivity")),
            "readiness": count(("benchmarking", "readiness")),
        },
        "top_candidates": [
            summary_row(row)
            for row in candidates[:25]
        ],
        "pattern_card_ready_candidates": [
            summary_row(row)
            for row in candidates
            if row["benchmarking"]["readiness"] == "pattern_card_ready"
        ][:25],
        "sanitize_first_candidates": [
            summary_row(row)
            for row in candidates
            if row["benchmarking"]["readiness"] == "needs_sanitization"
        ][:25],
    }


def write_outputs(out_dir: Path, candidates: list[dict[str, Any]], inventory: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = summarize_candidates(candidates, inventory)
    write_json(out_dir / "inventory.json", inventory)
    write_json(out_dir / "summary.json", summary)
    with (out_dir / "candidates.jsonl").open("w", encoding="utf-8") as handle:
        for candidate in candidates:
            handle.write(json.dumps(candidate, sort_keys=True) + "\n")
    (out_dir / "summary.md").write_text(summary_markdown(summary), encoding="utf-8")


def iter_jsonl(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    try:
        with path.open(encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    yield line_no, row
    except (OSError, UnicodeDecodeError):
        return


def flatten_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict):
            text = item.get("text") or item.get("content")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts)


def summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Transcript Task Mining Summary",
        "",
        f"Schema: `{summary['schema_version']}`",
        f"Candidates: {summary['inventory']['candidate_count']}",
        "",
        "## Counts",
        "",
    ]
    for label, counts in summary["counts"].items():
        rendered = ", ".join(f"{key}={value}" for key, value in counts.items()) or "none"
        lines.append(f"- {label}: {rendered}")
    lines.extend(["", "## Top Candidates", ""])
    for row in summary["top_candidates"]:
        lines.append(
            "- "
            f"{row['id']}: {row['title']} "
            f"({row['source']}, {row['category']}, {row['size_hypothesis']}, "
            f"score={row['score']}, sensitivity={row['sensitivity']}, "
            f"readiness={row['readiness']})"
        )
    lines.extend(["", "## Pattern Card Ready", ""])
    for row in summary["pattern_card_ready_candidates"]:
        lines.append(
            "- "
            f"{row['id']}: {row['title']} "
            f"({row['source']}, {row['category']}, {row['size_hypothesis']}, "
            f"score={row['score']}, sensitivity={row['sensitivity']})"
        )
    lines.extend(["", "## Sanitize First", ""])
    for row in summary["sanitize_first_candidates"]:
        lines.append(
            "- "
            f"{row['id']}: {row['title']} "
            f"({row['source']}, {row['category']}, {row['size_hypothesis']}, "
            f"score={row['score']}, sensitivity={row['sensitivity']})"
        )
    lines.append("")
    return "\n".join(lines)


def summary_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "source": row["source"]["system"],
        "category": row["coding"]["category"],
        "size_hypothesis": row["coding"]["size_hypothesis"],
        "score": row["coding"]["score"],
        "sensitivity": row["privacy"]["sensitivity"],
        "readiness": row["benchmarking"]["readiness"],
    }


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def as_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None
