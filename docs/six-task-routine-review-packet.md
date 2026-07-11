# Six-Task Independent Routine Review Packet

**Protocol:** ShallowSWE v0.4.2, six-task pilot v0.3
**Purpose:** final human construct review before artifact freeze and official Kaggle canary
**Reviewer requirement:** at least one qualified software engineer who did not author the task

Model-assisted investigator review and executed verifier QA are complete. They do not count as the
independent sign-off required by `shallowswe.routine_review.v0.1`.

Generate a reviewer-safe packet with:

```sh
uv run shallowswe pilot-review-pack \
  configs/shallowswe-six-task-pilot-v0.3.json \
  /tmp/shallowswe-six-task-routine-review-v0.3
```

The generated `blind-review/` directories exclude solutions, hidden verifiers, and trajectories.
After the reviewer completes every `review-form.json`, audit all six forms and import them only after
the complete packet passes:

```sh
uv run shallowswe pilot-review-import \
  configs/shallowswe-six-task-pilot-v0.3.json \
  /tmp/shallowswe-six-task-routine-review-v0.3
uv run shallowswe pilot-review-import \
  configs/shallowswe-six-task-pilot-v0.3.json \
  /tmp/shallowswe-six-task-routine-review-v0.3 \
  --write
```

The importer rejects incomplete, non-accepted, non-independent, or stale forms and performs no
review writes unless the complete six-task packet passes validation.

## Review Set

| Category | Pressure hypothesis | Task | Prior evidence |
|---|---|---|---|
| Artifact | lower | `env-flags-to-json` | Pilot hypothesis only |
| Artifact | elevated | `access-log-to-incidents` | Pilot hypothesis only |
| Code | lower | `invoice-cli-regression-test-fix` | Pilot hypothesis only |
| Code | elevated | `invoice-multi-source-merge` | Floor 0/2, ceiling 1/1; provisional |
| Workflow | lower | `config-flag-ignored` | Pilot hypothesis only |
| Workflow | elevated | `merge-divergent-config-branches` | Pilot hypothesis only |

Pressure labels are hypotheses to test, not admission requirements. Do not enlarge or reject a fair
task merely because a floor model may pass it.

## Reviewer Procedure

For each task, review `instruction.md`, `task.toml`, and the visible `environment/` without reading
`solution/`, `solution_alt/`, hidden `tests/`, or prior model trajectories first. Decide whether the
request is realistic routine engineering work and whether an engineer could delegate it as written.
Then inspect `quality/investigator-review.md`, `quality/requirements.json`, and the executed evidence
to determine whether the recorded repairs address the known construct risks.

Record `accept`, `revise`, or `reject` with a non-empty rationale for every rubric field:

- `realism`
- `ordinary_frequency`
- `delegation_plausibility`
- `ambiguity_risk`
- `engineer_effort`
- `specialized_knowledge`
- `horizon_classification`

An accepted review is stored at `tasks/<task-id>/quality/routine-review.json`. Use the exact schema
shown in `tests/test_task_quality_evidence.py`; copy the current `instruction` and `environment`
hashes from the task's `quality/executions.json`. Any later task edit invalidates the review.

## Stop Conditions

Stop the freeze and return a task for repair if the reviewer finds hidden requirements, implausible
delegation, specialist knowledge not stated in the prompt, misleading examples, or a materially
different routine interpretation that the verifier would reject. After any repair, rerun executed QA
and repeat independent review for that task.

The final check is:

```sh
uv run shallowswe task-quality tasks
uv run shallowswe pilot-readiness configs/shallowswe-six-task-pilot-v0.3.json
```

All six task IDs must appear in both `quality_ready_tasks` and `routine_review_ready_tasks`.
