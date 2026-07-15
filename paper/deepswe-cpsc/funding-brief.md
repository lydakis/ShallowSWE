# Funding Brief: Calibrating the Economic Regime for Routine Software Work

## The case in one sentence

We stress-tested the CPSC framework on an independent frontier benchmark and found that the metric
is portable and informative, but economic model selection remains unidentified until reliability
and failure value are explicitly calibrated. Funding ShallowSWE would identify those missing policy
quantities in the high-volume routine-work regime.

## What the external stress test established

The DeepSWE v1.1 reanalysis uses 18,396 scored trials, 41 fixed model-effort configurations, and 113
original software-engineering tasks. The analysis exactly reconciles the public leaderboard and
adds task-clustered uncertainty, failure-spend decomposition, exclusion audits, solved-footprint
matching, task-difficulty strata, and counterfactual failure charging.

The strongest comparison stays within one provider and one harness. GPT-5.6 Luna max costs $4.51
per verified benchmark success under DeepSWE's attempt policy, versus $11.54 for GPT-5.6 Sol max.
The paired task-bootstrap CPSC ratio is 0.390 with a 95% interval of 0.345 to 0.439, and Luna is
cheaper in 10,000 of 10,000 task-mix replicates. The paired solve-rate difference remains unresolved.

The result survives the main task-mix objections. Luna and Sol solve 92 tasks in common, with solved-
set Jaccard overlap of 0.86, and Luna remains about 60% cheaper on that selected common footprint.
Luna also outperforms Sol on the 17 tasks solved by at most half of the 41 configurations, so the
cost result is not explained by Luna solving only the easy subset and failing cheaply elsewhere.

A deliberately Sol-favorable post-hoc test restricts every configuration to the 97 tasks Sol solves
and prices failures from Sol's successful attempt spend. This makes economic ranks increasingly
align with capability ranks as the failure charge rises, but Luna remains cheaper than Sol at 0.5x,
1x, and 2x the Sol-derived task budgets. The proposed artifact is real as a policy sensitivity, but
it does not explain away the Luna-Sol result at the tested charges.

## What remains unidentified

Realized CPSC is exactly mean attempt cost divided by pass rate. It is an accounting estimand, not a
deployment policy. DeepSWE does not identify:

- the minimum reliability an operator requires;
- a task-only reference budget or replacement cost for failure;
- a bounded retry and repair policy;
- the value of a routine completion; or
- the width and commercial importance of the regime where models are substitutable but not
  economically identical.

The external analysis therefore motivates ShallowSWE. It does not validate the routine-work
construct in advance.

## The fundable experiment

Test one falsifiable claim:

> There exists a substantial regime of routine, functionally verifiable software work where
> multiple fixed configurations meet a predeclared reliability requirement but their failure-aware
> economic ordering differs.

The study would:

1. Source ordinary, independently authored software tasks and validate their routine-work construct
   with qualified reviewers.
2. Calibrate tasks into pressure bands using cheap probes before report-grade execution.
3. Freeze a bounded repair protocol, hidden deterministic verifier, provider route, dated price
   sheet, immutable model identity, rollout count, and stopping rule.
4. Predeclare reliability eligibility, task reference budgets, anchor replacement cost, missing-data
   handling, and task-clustered uncertainty.
5. Measure whether the middle regime is wide, whether CPSC changes routing decisions within it, and
   where the shallow-to-frontier transition occurs.

## Reviewable outputs

- A construct-validated, verifier-backed routine software benchmark.
- Frozen task and pressure metadata with transparent provenance.
- A reproducible execution and aggregation package.
- Reliability-constrained and failure-priced CPSC estimates with uncertainty.
- A public technical report stating both positive and negative results.
- A routing-oriented decision map showing where models are substitutes, complements, or ineligible.

## Decision value

If the middle regime is broad, ShallowSWE supplies evidence no capability leaderboard currently
provides: which qualifying model-policy configuration minimizes expected economic cost for routine
software work. If the regime is narrow, the suite thesis is weakened, but the project still returns
a portable economic analysis framework and a defensible negative result. Either outcome resolves a
real uncertainty before organizations build routing policy from price sheets or capability ranks
alone.

## Evidence boundary for funders

Safe claim: the DeepSWE reanalysis shows that the framework is reproducible, that task mix and
failure pricing can be audited, and that a same-provider cost gap survives several strong post-hoc
checks.

Claim requiring the funded study: routine software work contains a substantial calibrated regime
where multiple models qualify and economic ordering changes decisions.
