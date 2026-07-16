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
matching, task-difficulty strata, counterfactual failure charging, and a reviewer-requested
repository-clustered sensitivity over 91 source repositories.

The cleanest operational result stays within one model, provider, and harness. GPT-5.6 Sol high,
xhigh, and max attain 69.4%, 70.7%, and 72.7% solve rates, but cost $5.00, $6.65, and $11.54 per
verified success. High and xhigh are cheaper and use fewer recorded steps, token counters, and
seconds than max in all 10,000 task and repository bootstrap replicates. Their paired solve-rate
differences from max remain unresolved. For this suite, maximum effort carries a resolved economic
premium without a resolved capability gain.

The most striking cross-model comparison is a price-versus-work reversal. GPT-5.6 Luna max costs
$4.51 per verified success versus $11.54 for Sol max. The paired task-bootstrap CPSC ratio is 0.390
with a 95% interval of 0.345 to 0.439, and the repository-cluster interval is 0.350 to 0.434. Luna
is cheaper in every replicate, while consuming more recorded steps and token counters per success.
The paired solve-rate difference remains unresolved, so the result is an invoice advantage rather
than evidence of equivalent capability or lower agent work.

The result survives the main task-mix objections. Luna and Sol solve 92 tasks in common, with solved-
set Jaccard overlap of 0.86, and Luna remains about 60% cheaper on that selected common footprint.
Luna also reaches more tasks in the 20-task rare stratum assigned without any GPT-5.6 outcomes, so
the cost result is not explained by Luna solving only the easy subset and failing cheaply elsewhere.
When Sol is tuned to high rather than max effort, however, the Luna-to-Sol CPSC interval crosses
parity while Sol uses much less recorded work and time. The large Luna-versus-Sol-max invoice gap
is therefore partly an effort-setting result.

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
failure pricing can be audited, that lower effort can dominate within a fixed model, and that a
same-provider invoice gap survives task- and repository-mix checks but narrows under effort tuning.

Claim requiring the funded study: routine software work contains a substantial calibrated regime
where multiple models qualify and economic ordering changes decisions.
