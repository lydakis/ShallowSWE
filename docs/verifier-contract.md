# ShallowSWE Verifier Contract

This document defines what it means for a ShallowSWE rollout to pass.

Pier executes the task and records verifier rewards. ShallowSWE owns the verifier policy: a reward of `1` must mean the agent produced a behaviorally correct result for the task prompt, not merely a patch similar to the reference solution.

## Pass Definition

A rollout passes when all mandatory verifier checks succeed in a clean task environment.

```text
pass = prompt-specified behavior works
     + adjacent behavior remains stable
     + required artifacts/state exist
     + no disallowed destructive or unrelated changes occurred
```

A rollout fails when any required behavior is missing, any regression check fails, the verifier cannot execute because of the agent's changes, or the final state violates task constraints.

Provider, network, credential, credit, routing, and verifier-infrastructure failures are excluded and retried under the result-status policy in `docs/methodology.md`.

## Reward Contract

Task verifiers should write:

```text
/logs/verifier/reward.txt
```

with:

- `1` when all mandatory checks pass.
- `0` when any mandatory check fails.

The verifier may also write diagnostics such as:

```text
/logs/verifier/report.json
```

Diagnostics should explain failures and record optional efficiency signals, but ShallowSWE's pass/fail export remains binary for v1.

## Prompt-Verifier Bijection

Every hidden verifier assertion must trace back to one of:

- behavior explicitly requested in `instruction.md`,
- behavior already established by the base repo's public API, tests, docs, or fixtures,
- a non-destructive repo hygiene constraint that is necessary for the task to be meaningful.

Hidden tests must not invent requirements. If a correct engineer would not infer the behavior from the prompt or existing repo, the verifier is wrong or the prompt is incomplete.

## Required Check Types

Every official verifier needs these check types unless the task category makes one irrelevant:

1. **Fail-to-pass checks**
   - Assert the requested new or fixed behavior.
   - Must fail on the unmodified base repo for the intended reason.

2. **Pass-to-pass checks**
   - Assert adjacent existing behavior still works.
   - Must pass on the unmodified base repo.

3. **Artifact/state checks**
   - Assert expected files, outputs, API state, git state, or command output.
   - Should use canonicalized comparisons where order or formatting is not part of the contract.

4. **Negative/overreach checks**
   - Assert the agent did not delete unrelated data, duplicate records, break compatibility aliases, or mutate out-of-scope state.

5. **Verifier self-check**
   - The verifier must fail cleanly with reward `0` if the agent breaks imports, test discovery, CLI entrypoints, or the mock API in a way that prevents judgment.

## Validation Pipeline

Before a task can enter calibration:

1. Run verifier against the unmodified base in a clean container.
   - Fail-to-pass checks fail.
   - Pass-to-pass checks pass.
   - Failure reason matches the task design.

2. Apply the reference solution and run the verifier three times in clean containers.
   - All runs pass.
   - Outputs and diagnostics are deterministic.

3. Validate at least one alternate solution.
   - Use a reviewer-written or agent-written non-reference patch.
   - The alternate solution should use a materially different structure or helper decomposition.
   - Official tasks cannot enter calibration until both the reference and alternate solution pass.
   - If a plausible correct alternate fails, broaden the verifier or reject the task.

4. Review prompt-verifier alignment.
   - Every hidden assertion has a prompt or existing-contract source.
   - No hidden assertion requires a private implementation detail.

5. Run floor calibration.
   - Use the current versioned calibration panel, not a single control model.
   - T1: calibration-panel median should be near 100%.
   - T2: calibration-panel median should be >=90%.
   - T3: calibration-panel median should be 80-95%.
   - T4: calibration-panel median should be 30-70%.
   - T4: strongest/top-gated model should pass >=80%; floor models may fail.
   - T4 candidates must show meaningful pass-rate divergence after calibration or be demoted.
   - Calibration rollouts are not published leaderboard rollouts.

## Category-Specific Contracts

### Fix

Verifier should include:

- A focused fail-to-pass behavior test for the defect.
- Regression checks for nearby existing behavior.
- Public API compatibility checks when the task touches exported names.

Avoid:

- Asserting the exact code path used to fix the bug.
- Requiring exact error text unless the prompt makes that text part of the contract.

### Transform

Verifier should include:

- Schema validation for every output file.
- Canonicalized output comparison.
- Reject-file checks with reason codes when malformed or unmatched records exist.
- Aggregate counts and sampled row checks for larger datasets.

Avoid:

- Comparing raw file text when ordering or whitespace is not part of the prompt.
- Letting extra output columns pass silently unless extension is explicitly allowed.

### Operate

Verifier should include:

- Repo end-state checks: imports, commands, config flow, branch state, or file layout as relevant.
- Test suite or command-level checks for public behavior.
- Compatibility checks when a rename, move, split, or config migration preserves old paths.

Avoid:

- Requiring a specific git commit hash or exact diff.
- Accepting a green test suite if repo state violates the prompt.
- Checking documentation or help prose beyond literal public contract terms required by the prompt,
  such as a config key name or enum values.

### Invoke

Verifier should include:

- Final mock API state.
- Call-log checks for duplicate, missing, or destructive actions.
- Idempotency checks when the prompt says update or reconcile rather than create.
- Deterministic retry checks for documented transient errors.

Call count is diagnostic by default. It should only affect pass/fail when:

- the agent performs a destructive or duplicate action,
- the prompt explicitly constrains action count,
- the excessive call pattern changes final state or violates API contract.

Avoid:

- Scoring based on hidden optimal-call paths.
- Depending on network access or real third-party APIs.

### Test-Writing Tasks

When the prompt asks the agent to add tests, the verifier should check both behavior and test substance.

Required:

- The requested behavior passes.
- A meaningful test file was added or changed in the expected test surface.
- The new test references the behavior, not just a smoke assertion.

Preferred when practical:

- Apply the agent-added test without the agent's fix to the base repo and confirm it fails.

Avoid:

- Passing merely because any file under `tests/` changed.
- Requiring exact test names unless the prompt specifies them.

## T4 Shelf-Edge Contract

T4 tasks are allowed to be too hard for floor models, but they must remain fair.

Additional requirements:

- The prompt must still be unambiguous.
- The task must still be routine in kind.
- The strongest/top-gated model must pass >=80% during calibration.
- The candidate card must pre-register expected pass-rate bands and the predicted cheapest-correct
  row class before calibration.
- Accepted T4 tasks should show a meaningful spread between weaker and stronger scored rows. A
  candidate where every row passes at saturation should be demoted to T3 or kept as a non-T4 probe.
- The verifier must report the same behavior metrics as T1-T3.
- T4 rows must be labeled by tier but scored in the same price-index basket once accepted.

T4 complexity should come from compounding steps and state, not from hidden insight. If a task requires discovering a non-obvious algorithm, architecture, or product intent, it is not T4 ShallowSWE; it is outside scope.

## Anti-Cheat And Robustness Rules

Verifiers should be difficult to game accidentally, but not adversarial puzzles.

Required:

- Hidden tests live outside the prompt-visible repo surface.
- Verifier fixtures include at least one edge case not present in public examples, when that edge case follows from the prompt.
- Tests should call public commands/APIs where possible.
- Internal helpers may be imported only when they already exist in the base repo and are part of the expected public/semi-public surface.

Avoid:

- Tests that import files or names introduced only by the reference patch.
- Exact diff matching.
- Golden-output comparisons that encode incidental ordering.
- Wall-clock, randomness, locale, CPU-count, or filesystem-order dependencies.
- Snapshot tests over broad output when only a few fields matter.
- Hidden requirements that reward reading the verifier over reading the prompt.

## Review Checklist

Score each item `pass`, `needs-fix`, or `reject`.

- The prompt states all behavior that hidden tests assert.
- The base repo fails for the intended reason.
- The reference solution passes three clean verifier runs.
- The verifier accepts at least one alternate correct solution with a materially different structure.
- Pass-to-pass checks guard adjacent behavior.
- Output comparisons are canonicalized where possible.
- No copied public benchmark, issue, PR, test, patch, or fixture content appears in the task.
- The verifier is deterministic and offline.
- The verifier failure output is understandable enough for task authors to debug.
- The task metadata records verifier type, fail-to-pass count, pass-to-pass count, hidden-test presence, and calibration status.

Any `reject` blocks task admission. Any `needs-fix` blocks official snapshot admission until resolved.

## Minimal Verifier Structure

For Pier-compatible tasks, `tests/test.sh` should use this shape:

```sh
#!/usr/bin/env bash
set -euo pipefail

mkdir -p /logs/verifier

if python /tmp/hidden_verifier.py > /logs/verifier/stdout.txt 2> /logs/verifier/stderr.txt; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
```

The hidden verifier should run normal tests or checks and should emit structured diagnostics when practical. The shell wrapper should not mask verifier failures.
