# Six-Task Pilot Launch Runbook

This runbook freezes and launches the protocol-validation pilot. It does not authorize the full
benchmark and does not waive the explicit funding approval in the pilot manifest.

## Runner Roles

- Kaggle Benchmarks is the canonical runner for all official pilot evidence.
- Codex subscription runs are development evidence only and never enter official aggregates.
- Pier/Harbor is the portability and parity runner, not an interchangeable official evidence source.
- Apple `container` is local, network-disabled verifier QA only.

## Freeze Sequence

1. Generate and complete the independent packet in `docs/six-task-routine-review-packet.md`, then
   import it with `pilot-review-import --write`.
2. Rerun `execute-task-quality` for any task changed during review.
3. Regenerate the deterministic schedule and launch plan.
4. Build the Kaggle bundle with the manifest, schedule, launch plan, and price sheet attached.
5. Run `pilot-freeze` without `--write`; the only acceptable result is `ready_to_freeze: true`.
6. Run the same command with `--write`, then require `ready_for_official_canary: true` from
   `pilot-readiness`.
7. Commit the frozen repository state before creating any official Kaggle task.

The canonical generation commands are:

```sh
uv run shallowswe pilot-schedule \
  configs/shallowswe-six-task-pilot-v0.3.json \
  configs/shallowswe-six-task-pilot-v0.3-schedule.json
uv run shallowswe pilot-launch-plan \
  configs/shallowswe-six-task-pilot-v0.3.json \
  configs/shallowswe-six-task-pilot-v0.3-schedule.json \
  configs/shallowswe-six-task-pilot-v0.3-launch-plan.json
```

## Kaggle Binding

Create one Kaggle task per official launch unit. Set `SHALLOWSWE_LAUNCH_UNIT_ID` to the unit's exact
ID from `configs/shallowswe-six-task-pilot-v0.3-launch-plan.json`. The runner derives all task IDs,
seeds, model identity, reasoning effort, caps, evidence class, funding pool, and trajectory IDs from
the attached launch plan. Do not set task or seed overrides for a frozen pilot unit.

Also record:

- `SHALLOWSWE_REPO_COMMIT_SHA` as the frozen commit;
- `SHALLOWSWE_ROUTINE_REVIEW_VERSION=shallowswe.routine_review.v0.1`;
- concurrency and row timeout only as operational settings that do not alter agent policy.

The requested Kaggle model must exactly match the launch unit. Mismatched models, unknown seeds,
unknown tasks, or a missing launch-unit ID fail before model execution.

## Canary Gate

Launch only the four Stage 2 Kaggle units after explicit funding approval. Stop before Stage 3 if
identity resolution, sandbox isolation, continuation, verifier accounting, trajectory binding, or
cost reconciliation fails, or if projected core spend exceeds the $200 cumulative cap.

Stage 5 remains intentionally unrunnable until Stage 4 freezes `K`, the agent step guard, and the
three preregistered task budgets. Regenerate the launch plan and repeat freeze after that policy
decision.
