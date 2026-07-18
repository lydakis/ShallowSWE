# Development-Only Pipeline Rehearsal v0.1

**Run date:** 2026-07-18  
**Manifest:** `shallowswe-six-task-pilot-v0.3`  
**Evidence class:** `development_dry_run`  
**Release class:** `development_dry_run`

## Purpose

This rehearsal tests the ShallowSWE control flow before independent routine-work review or metered
Kaggle execution. It uses deterministic synthetic model and verifier events. It does not assess the
six tasks, select empirical constants, produce model evidence, or satisfy a human review gate.

## Command

```sh
uv run shallowswe development-rehearsal \
  configs/shallowswe-six-task-pilot-v0.3.json \
  results/development-rehearsal-v0.1
```

## Result

The rehearsal completed with `valid: true` over 114 rows and exercised:

- direct success and successful same-context repair;
- verifier-submission, dollar, and agent-step exhaustion;
- infrastructure exclusion;
- ordered model-call and verifier-result usage checkpoints;
- deterministic Stage 4 selection and one adjacent budget-band bump;
- exact-policy fresh-confirmation validation, including rejection at 6/8 successes;
- category-by-pressure weighted-ratio aggregation;
- a retained zero-success task and six underfilled declared cells;
- rejection of mixed development and official evidence;
- rejection of an official launch unit whose status is still blocked.

The synthetic Stage 4 proposal selected `K=2` and a 32-step guard. Those values only prove that the
selector behaves as specified on the fixture. The artifact is labeled `development_proposal` and
sets `official_launch_eligible: false`.

## Remaining official gates

`pilot-readiness` remains structurally valid but not launch-ready. The independent routine-work
review is incomplete, the price and runner bundle have not been frozen, task/verifier/environment
hashes have not been written into the pilot manifest, and explicit funding approval has not been
given. No routine-review file was synthesized or imported during this rehearsal.
