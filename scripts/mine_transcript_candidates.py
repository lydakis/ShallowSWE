from __future__ import annotations

import argparse
from pathlib import Path

from shallowswe.transcript_mining import (
    mine_candidates,
    validate_private_output_dir,
    write_outputs,
)


PUBLIC_REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    args = parse_args()
    validate_private_output_dir(args.out_dir, public_repo_root=PUBLIC_REPO_ROOT)
    candidates, inventory = mine_candidates(
        codex_root=args.codex_root,
        claude_root=args.claude_root,
        min_score=args.min_score,
        repo_hints=args.repo_hint,
        source_hints=args.source_project,
        max_candidates=args.max_candidates,
    )
    write_outputs(args.out_dir, candidates, inventory)
    print(f"wrote {len(candidates)} candidates to {args.out_dir}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mine local Codex and Claude transcripts for ShallowSWE task candidates."
    )
    parser.add_argument(
        "--codex-root",
        type=Path,
        default=Path.home() / ".codex" / "sessions",
        help="root containing Codex session JSONL files",
    )
    parser.add_argument(
        "--claude-root",
        type=Path,
        default=Path.home() / ".claude" / "projects",
        help="root containing Claude project JSONL files",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="private output directory; public-repo destinations must be under ignored tmp/",
    )
    parser.add_argument("--min-score", type=int, default=5)
    parser.add_argument("--max-candidates", type=int)
    parser.add_argument(
        "--repo-hint",
        action="append",
        default=["ShallowSWE"],
        help="repo/project term that should boost candidate score; may be repeated",
    )
    parser.add_argument(
        "--source-project",
        action="append",
        default=["ShallowSWE"],
        help="path/project term required for a transcript request to be mined; may be repeated",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
