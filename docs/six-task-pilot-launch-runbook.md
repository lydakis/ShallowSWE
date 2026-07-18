# Six-Task Pilot Launch Runbook

This runbook freezes and launches the protocol-validation pilot. It does not authorize the full
benchmark and does not waive the explicit funding approval in the pilot manifest.

## Runner Roles

- Kaggle Benchmarks is the canonical runner for all official pilot evidence.
- Codex subscription runs use the `development_dry_run` evidence and release classes and never
  enter official aggregates.
- Pier/Harbor is the portability and parity runner. Matching rows are eligible for pooled model
  evidence, with runner, gateway, and provider-route provenance retained and published.
- Docker is local, network-disabled verifier QA only.

## Freeze Sequence

1. Run the deterministic local vertical slice and require `valid: true`:

   ```sh
   uv run shallowswe development-rehearsal \
     configs/shallowswe-six-task-pilot-v0.3.json \
     results/development-rehearsal-v0.1
   ```

2. Generate and complete the independent packet in `docs/six-task-routine-review-packet.md`, then
   import it with `pilot-review-import --write`.
3. Rerun `execute-task-quality` for any task changed during review.
4. Regenerate the deterministic schedule and launch plan.
5. Build the Kaggle bundle with the manifest, schedule, launch plan, and price sheet attached.
6. Run `pilot-freeze` without `--write`; the only acceptable result is `ready_to_freeze: true`.
7. Run the same command with `--write`, then require `ready_for_official_canary: true` from
   `pilot-readiness`.
8. Commit the frozen repository state before creating any official Kaggle task.

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

Create one Kaggle task per official launch unit. Generate bound sources first:

```sh
uv run shallowswe kaggle-bound-sources \
  configs/shallowswe-six-task-pilot-v0.3-launch-plan.json \
  /tmp/shallowswe-pilot-bound-sources
```

Each generated source freezes the exact launch-unit ID and `kaggle_task_name`. The runner derives
all task IDs, seeds, model identity, reasoning effort, caps, evidence class, funding pool, and
trajectory IDs from the attached launch plan. Do not push the generic runner or set task or seed
overrides. An operational `SHALLOWSWE_LAUNCH_UNIT_ID` must match the frozen source value.

Also record:

- `SHALLOWSWE_REPO_COMMIT_SHA` as the frozen commit;
- `SHALLOWSWE_ROUTINE_REVIEW_VERSION=shallowswe.routine_review.v0.2`;
- concurrency and row timeout only as operational settings that do not alter agent policy.

The requested Kaggle model must exactly match the launch unit. Mismatched models, unknown seeds,
unknown tasks, or a missing launch-unit ID fail before model execution.

A launch unit whose `launch_status` is not `official_ready` also fails before model execution.
The checked-in plan remains blocked while the routine-review, artifact-freeze, Stage 4, or funding
gate relevant to that stage is unresolved. Do not bypass this with notebook edits or environment
overrides.

## Canary Gate

Launch only the four Stage 2 Kaggle units after explicit funding approval. Stop before Stage 3 if
identity resolution, sandbox isolation, continuation, verifier accounting, trajectory binding, or
cost reconciliation fails, or if projected core spend exceeds the $200 cumulative cap.

Stage 5 remains intentionally unrunnable until Stage 4 freezes `K`, the agent step guard, and the
three preregistered task budgets. Regenerate the launch plan and repeat freeze after that policy
decision.

## Development Shadow

Before human review, the exact Kaggle runner can be exercised through a quarantined shadow:

```sh
uv run shallowswe development-shadow-plan \
  configs/shallowswe-six-task-pilot-v0.3.json \
  configs/shallowswe-six-task-pilot-v0.3-development-shadow-schedule.json \
  configs/shallowswe-six-task-pilot-v0.3-development-shadow-launch-plan.json
```

The shadow freezes the weekend shakedown identities, reserves seeds 5000 through 8002, creates new
trajectory IDs, and forces both evidence and release class to `development_dry_run`. Its 190 rows
cover the 16-row canary, 72-row calibration, 48 all-task confirmations, and 54 fresh candidate
rows. The canary is initially launchable; later stages remain gated in order. Shadow rows cannot
satisfy the official gate.
