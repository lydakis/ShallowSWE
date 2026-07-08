# Codex Subscription Higher-N Calibration Plan

## Position

N=3 is not enough for statistically significant task-size calibration. It is a cheap smoke probe
that catches broken task contracts and gives provisional sizing labels.

With N=3, the floor pass-rate grid is only:

- `0/3`: provisional large
- `1/3`: provisional medium
- `2/3`: provisional medium
- `3/3`: provisional small

That is too coarse to distinguish true pass probabilities near the `0.30` and `0.70` band
boundaries.

## Recommended Next Run

Run a fresh current-repo N=10 floor confirmation across all 47 tasks using
`openai/gpt-5.4-mini[low]`.

Reasoning:

- The seven contract-fix tasks changed prompts, so the original N=3 all-task floor run is not fully
  comparable for those tasks.
- A fresh N=10 all-task pass is simpler to interpret than mixing old and repaired prompt versions.
- N=10 can start confirming extremes: `0/10` is strong evidence for large, and `10/10` is strong
  evidence for small.
- Tasks with intermediate rates should remain provisional unless more samples separate them from
  the thresholds.

## Final Snapshot Target

For a stronger public or benchmark-snapshot claim, use N=16 to N=20 floor attempts per task.

Suggested rule:

- Assign final small only when uncertainty is above the `0.70` threshold.
- Assign final large only when uncertainty is below the `0.30` threshold.
- Leave boundary-crossing tasks as provisional or collect more rollouts.

## Current Status

- All 47 tasks have N=3 provisional Codex subscription calibration markers.
- The seven prompt/verifier contract issues were repaired.
- The repaired seven-task smoke recalibration passed `gpt-5.5[medium]` for all 7 tasks, but that
  is medium smoke evidence only, not the formal ceiling.
- The repaired seven-task mini floor smoke produced 4 provisional small and 3 provisional medium
  labels, with no remaining verifier/prompt contract issues.
