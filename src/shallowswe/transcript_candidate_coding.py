from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable


ACTION_TERMS = {
    "add",
    "analyze",
    "audit",
    "build",
    "calibrate",
    "change",
    "check",
    "commit",
    "convert",
    "create",
    "debug",
    "deploy",
    "diagnose",
    "extract",
    "fix",
    "generate",
    "implement",
    "investigate",
    "mine",
    "migrate",
    "normalize",
    "package",
    "parse",
    "publish",
    "reconcile",
    "refactor",
    "release",
    "rename",
    "repair",
    "review",
    "run",
    "sanitize",
    "split",
    "summarize",
    "test",
    "triage",
    "update",
    "verify",
    "write",
}

CODE_TERMS = {
    "api",
    "bug",
    "cli",
    "code",
    "crash",
    "dependency",
    "error",
    "failing",
    "feature",
    "function",
    "import",
    "module",
    "regression",
    "test",
    "typecheck",
}

ARTIFACT_TERMS = {
    "brief",
    "csv",
    "doc",
    "document",
    "export",
    "json",
    "markdown",
    "report",
    "schema",
    "sheet",
    "summary",
    "transcript",
}

WORKFLOW_TERMS = {
    "branch",
    "ci",
    "commit",
    "deploy",
    "github",
    "issue",
    "logs",
    "merge",
    "pr",
    "pull request",
    "release",
    "rollback",
    "run",
    "status",
    "workflow",
}

SENSITIVE_TERMS = {
    "gmail",
    "email",
    "calendar",
    "bank",
    "receipt",
    "order",
    "password",
    "secret",
    "token",
    "key",
    "client",
    "customer",
}

SECRET_PATTERNS = (
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"\b[rs]k_(?:live|test)_[A-Za-z0-9]{20,}\b"),
)

SKIP_PREFIXES = (
    "# agents.md instructions",
    "<codex_internal_context",
    "<environment_context",
    "<local-command-caveat>",
    "<skill>",
    "<subagent_notification>",
    "<user_action>",
    "<user_instructions>",
    "## code review guidelines",
)

SKIP_SUBSTRINGS = (
    "request action you are assessing",
    "the following is the codex agent history",
    "whose request action you are assessing",
    "do not respond to these messages",
    "memory writing agent",
    "your job: consolidate",
)


def should_skip_request(text: str) -> bool:
    stripped = text.strip()
    lower = stripped.lower()
    return (
        not stripped
        or lower.startswith(SKIP_PREFIXES)
        or any(token in lower for token in SKIP_SUBSTRINGS)
        or looks_like_line_numbered_dump(stripped)
    )


def looks_like_line_numbered_dump(text: str) -> bool:
    lines = [line for line in text.splitlines()[:50] if line.strip()]
    if len(lines) >= 12:
        numbered = sum(1 for line in lines if re.match(r"\s*\d+\s+\S", line))
        if numbered / len(lines) >= 0.65:
            return True
    return len(re.findall(r"(?:^|\s)\d+\s+\S", text[:5000])) >= 25


def signal_terms(lower: str, repo_hints: Iterable[str]) -> set[str]:
    signals = set()
    for term in ACTION_TERMS | CODE_TERMS | ARTIFACT_TERMS | WORKFLOW_TERMS:
        if term in lower:
            signals.add(term)
    for hint in repo_hints:
        hint = hint.lower().strip()
        if hint and hint in lower:
            signals.add(f"repo:{hint}")
    return signals


def score_request(lower: str, signals: list[str]) -> int:
    score = 0
    score += sum(3 for term in ACTION_TERMS if term in lower)
    score += sum(2 for term in CODE_TERMS if term in lower)
    score += sum(2 for term in ARTIFACT_TERMS if term in lower)
    score += sum(2 for term in WORKFLOW_TERMS if term in lower)
    score += sum(3 for signal in signals if signal.startswith("repo:"))
    if "benchmark" in lower or "calibration" in lower or "verifier" in lower:
        score += 4
    if "test" in lower and ("fix" in lower or "regression" in lower):
        score += 3
    if "real" in lower and "task" in lower:
        score += 2
    if len(lower) > 600:
        score += 2
    if len(lower) > 1600:
        score += 2
    if lower.startswith(("what do you think", "thoughts on", "could this become", "anything here")):
        score -= 18
    return score


def classify_category(lower: str) -> str:
    scores = {
        "code": sum(1 for term in CODE_TERMS if term in lower),
        "artifact": sum(1 for term in ARTIFACT_TERMS if term in lower),
        "workflow": sum(1 for term in WORKFLOW_TERMS if term in lower),
    }
    if "task" in lower and ("benchmark" in lower or "calibration" in lower):
        scores["workflow"] += 2
    if "report" in lower or "summary" in lower or "transcript" in lower:
        scores["artifact"] += 2
    if "fix" in lower or "bug" in lower or "regression" in lower:
        scores["code"] += 2
    return max(("code", "artifact", "workflow"), key=lambda category: scores[category])


def classify_size(lower: str, score: int) -> str:
    large_terms = (
        "end-to-end",
        "repo-wide",
        "all ",
        "everything",
        "calibration",
        "benchmark",
        "deploy",
        "migration",
        "multi-step",
        "reconcile",
    )
    if score >= 28 or any(term in lower for term in large_terms) or len(lower) > 1800:
        return "large"
    if score >= 13 or len(lower) > 500:
        return "medium"
    return "small"


def classify_maintenance_type(lower: str) -> str:
    if any(term in lower for term in ("fix", "bug", "failing", "failure", "regression", "error")):
        return "corrective"
    if any(term in lower for term in ("migrate", "schema", "dependency", "api", "rename")):
        return "adaptive"
    if any(term in lower for term in ("refactor", "review", "lint", "typecheck", "test coverage")):
        return "preventive"
    return "perfective"


def classify_shape(lower: str, category: str) -> str:
    if "benchmark" in lower or "calibration" in lower or "verifier" in lower:
        return "benchmark-task-authoring"
    if "git" in lower or "commit" in lower or "branch" in lower or "pr" in lower:
        return "repo-workflow"
    if "report" in lower or "summary" in lower or "csv" in lower or "json" in lower:
        return "artifact-transformation"
    if "fix" in lower or "bug" in lower or "regression" in lower:
        return "bug-localization"
    if "refactor" in lower or "split" in lower or "rename" in lower:
        return "repo-refactor"
    if category == "workflow":
        return "stateful-workflow"
    return "feature-wiring"


def classify_sensitivity(lower: str, path: Path, cwd: str | None, project: str | None) -> str:
    source_blob = " ".join(value for value in (str(path), cwd or "", project or "") if value).lower()
    if any(term in lower for term in ("password", "secret", "token", "api key", "private key")):
        return "high"
    if any(term in lower for term in SENSITIVE_TERMS):
        return "high"
    if any(
        marker in source_blob
        for marker in ("/users/", "-users-", "/home/", ".codex/", ".claude/")
    ):
        return "medium"
    if "http://" in lower or "https://" in lower or "/users/" in lower or "/home/" in lower:
        return "medium"
    return "low"


def classify_strength(score: int) -> str:
    if score >= 28:
        return "strong"
    if score >= 13:
        return "medium"
    return "weak"


def readiness(score: int, sensitivity: str, lower: str) -> str:
    if is_subjective_or_review_prompt(lower):
        return "needs_review"
    if score >= 28 and sensitivity != "high":
        return "pattern_card_ready"
    if score >= 13:
        return "needs_sanitization"
    return "needs_review"


def next_step(score: int, sensitivity: str, lower: str) -> str:
    if is_subjective_or_review_prompt(lower):
        return "extract a deterministic task shape before drafting a pattern card"
    if sensitivity == "high":
        return "rewrite as abstract pattern before any tracked artifact"
    if score >= 28:
        return "draft private pattern card and verifier sketch"
    return "human review for realism and verifier feasibility"


def is_subjective_or_review_prompt(lower: str) -> bool:
    return lower.startswith(
        (
            "what do you think",
            "btw what do you think",
            "thoughts on",
            "could this become",
            "anything here",
            "here's some feedback",
            "here is some feedback",
            "i got this feedback",
            "here's a discussion",
            "here is a discussion",
            "sounds good, can you also review",
            "can you also review",
        )
    )


def verifier_idea(category: str) -> str:
    if category == "code":
        return "fail-to-pass symptom test plus pass-to-pass regression checks"
    if category == "artifact":
        return "deterministic fixture transformation into a fixed output schema"
    return "local final-state verifier plus destructive-overreach checks"


def sanitization_plan(sensitivity: str, category: str) -> list[str]:
    plan = [
        "rewrite the prompt from scratch",
        "replace real project, person, company, and path names",
        "shrink source state into synthetic fixtures",
        "record only the abstract source pattern in tracked files",
    ]
    if sensitivity == "high":
        plan.append("remove raw excerpts before promotion out of tmp")
    if category == "workflow":
        plan.append("replace external services with a deterministic local API or git fixture")
    return plan


def title_from_text(text: str) -> str:
    clean = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    for line in clean.splitlines():
        line = redact_sensitive_text(normalize_space(line))
        if len(line) >= 20 and not line.startswith("<"):
            return line[:96].rstrip(" ,.")
    return redact_sensitive_text(normalize_space(clean))[:96].rstrip(" ,.")


def excerpt(text: str, limit: int = 900) -> str:
    text = redact_sensitive_text(normalize_space(text))
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def redact_sensitive_text(text: str) -> str:
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[REDACTED_SECRET]", text)
    return text


def stable_candidate_id(
    source: str,
    path: Path,
    line_no: int,
    session_id: str | None,
    text: str,
) -> str:
    payload = "\n".join(
        [
            source,
            str(path),
            str(line_no),
            session_id or "",
            normalize_space(text).lower(),
        ]
    )
    return "tcand-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
