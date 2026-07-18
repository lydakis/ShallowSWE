# Task Quality Audit

ShallowSWE task QA exists to keep task noise from becoming fake economics. A task can be
reproducible and still be a bad benchmark item if the prompt, verifier, or coverage is wrong.

The audit is a gate before calibration and scoring. Calibration answers "how large is this fair
task?" Task QA answers "is this task fair enough to measure at all?"

## Failure Taxonomy

Use these public labels when rejecting, repairing, or reporting candidate tasks:

- `overly_strict_verifier`: hidden checks require formatting, ordering, file layout, helper names,
  or implementation shape not required by the prompt or existing public contract.
- `underspecified_prompt`: hidden checks enforce behavior that is not explicitly requested and not
  reasonably inferable from the local repo.
- `low_coverage_verifier`: incomplete, hardcoded, fixture-only, or no-op solutions can pass.
- `misleading_prompt`: examples or wording push a solver toward behavior the verifier rejects.

ShallowSWE may also record internal labels such as `ambiguous_repo_convention`,
`alternate_solution_not_independent`, `verifier_infra_error`, and `contamination_risk`, but the four
labels above are the main public benchmark-quality taxonomy.

## Required Evidence

Every publishable task needs task-local evidence under:

```text
tasks/<task-id>/quality/
  requirements.json
  negative-controls.json
  negative-controls/<control-id>.sh
  executions.json
  routine-review.json
  investigator-review.md   # optional but recommended for admitted tasks
```

`requirements.json` maps verifier checks back to prompt or repo-contract sources:

```json
{
  "requirements": [
    {
      "id": "R1",
      "source": "instruction.md:4",
      "behavior": "deduplicate invoices by normalized invoice_id, keeping the first row",
      "verifier_checks": [
        "tests/test.sh:hidden_duplicate_invoice_case",
        "tests/test.sh:visible_cli_total_case"
      ]
    }
  ]
}
```

`negative-controls.json` records intentionally bad solutions that must fail:

```json
{
  "negative_controls": [
    {
      "id": "NC1",
      "description": "hardcode the visible output file without implementing the parser",
      "expected_failure": "hidden fixture output mismatch"
    },
    {
      "id": "NC2",
      "description": "apply the feature but delete unrelated input records",
      "expected_failure": "negative/overreach check"
    }
  ]
}
```

Good negative controls are boring and specific: no-op patch, hardcoded visible fixture output,
partial implementation, wrong ordering, missing malformed-row handling, deleted unrelated state, or
test-only changes without runtime behavior.

`executions.json` is generated evidence, not an author claim. It binds the task packet by SHA-256,
records the clean-sandbox runtime and image digest, and records three clean reference runs, one
materially different alternate run, and one rejecting run for every declared control. Any prompt,
environment, verifier, solution, or control edit makes the evidence stale.

`routine-review.json` records the construct gate separately from verifier QA. It requires at least
one qualified reviewer who is not the task author, an accept/revise/reject rationale for every
routine-work rubric field, including explicit category fit, and hashes for the reviewed instruction
and environment. Investigator
agents may assist this review but do not satisfy an independent engineer sign-off by themselves.

## Audit Workflow

1. Write the original task, reference solution, and verifier.
2. Confirm the unmodified base fails for the intended reason.
3. Confirm the reference solution passes three clean verifier runs.
4. Confirm a materially different alternate solution passes.
5. Fill `quality/requirements.json`.
6. Add bad-patch negative controls and confirm they fail.
7. Run investigator review as QA assistance only:
   - prompt/verifier consistency,
   - alternate valid solutions,
   - incomplete solutions that might pass,
   - example and hidden-expectation contradictions.
8. Run calibration only after unresolved task-quality issues are repaired or the task is rejected.

Investigator agents can help find broken tasks. They are not benchmark judges and never score model
outputs.

## Reporting

Generate the current report with:

```sh
uv run shallowswe task-quality tasks
```

The audit command reports three distinct states:

- `quality_evidence_complete`: requirement and negative-control declarations are structurally valid;
- `executed_quality_evidence_complete`: current hash-bound reference, alternate, and control runs pass;
- `routine_review_complete`: a current independent construct review accepts the task.

Generate executed evidence with Docker:

```sh
uv run shallowswe execute-task-quality tasks --task-id <task-id>
```

Docker provides local deterministic QA. Kaggle remains the primary funded execution backend, and
Pier/Harbor remains the portability runner.

The report includes:

- authored task count,
- quality-evidence-complete count,
- missing requirement maps,
- missing negative controls,
- alternate-solution blockers,
- OpenAI-style failure-mode history found in calibration notes,
- per-task evidence paths and issue labels.

For v1, publish the task-quality report next to the leaderboard so readers can see not only which
models won, but how many candidate tasks were repaired, rejected, or accepted before scoring.
