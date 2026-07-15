# DeepSWE CPSC Working Paper: Frozen Analysis Specification

Status: retrospective analysis plan v0.1, frozen on 2026-07-14 before the trial-level
analysis pipeline and paper results were produced.

This is not a blinded preregistration. Before this freeze, the public DeepSWE leaderboard,
its pass rates and mean costs, the basic ratio `mean_cost / pass_rate`, and selected example
rank inversions were inspected. The trial-level decomposition, clustered uncertainty, full
configuration ranking, and sensitivity results had not been computed. The machine-readable
companion is `configs/deepswe-cpsc-v0.1.json`.

## Purpose and Claim Boundary

The working paper asks whether failure-aware economic metrics add decision-relevant information
to DeepSWE's frontier-capability results. It applies the ShallowSWE metric framework to an
independent public benchmark, then identifies which questions still require a calibrated
routine-work suite.

The paper may demonstrate:

- portable computation of realized cost per successful completion (CPSC);
- economic rank changes relative to pass-rate rank;
- decomposition into successful-work cost and realized reliability tax;
- uncertainty and sensitivity of economic recommendations; and
- the empirical motivation for measuring the routine-work regime.

The paper may not claim that DeepSWE validates ShallowSWE's routine-work construct, calibrated
reference budgets, bounded hidden-verifier repair loop, replacement-cost protocol, or production
return on investment. It also may not claim that a deep-task completion and a shallow-task
completion are equal units of economic value.

## Research Questions

1. How different are configuration rankings by pass rate and realized CPSC?
2. How much realized CPSC comes from spend on successful work versus failed attempts?
3. Which configurations lie on the joint pass-rate and cost frontier?
4. Are rank differences stable under task-clustered resampling and missing-cost conventions?
5. How do rankings respond to transparent counterfactual failure charges?
6. Which cross-regime comparisons become identifiable only after calibrated ShallowSWE runs?

The primary hypothesis is that frontier capability rank does not fully determine frontier-task
economic rank. A secondary research hypothesis, reserved for later ShallowSWE data, is that
among routine tasks solved at acceptable reliability by multiple configurations, expected cost
per verified completion differs materially and the preferred configuration changes with task
pressure.

## Frozen Data

The analysis uses the public DeepSWE v1.1 artifacts below. Raw files are downloaded into an
ignored working directory and accepted only when their SHA-256 hashes match the frozen manifest.
The source URLs are mutable even though they are versioned, so the content hashes are the actual
analysis identities.

| Artifact | Rows / role | Bytes | SHA-256 |
|---|---:|---:|---|
| `leaderboard-live.json` | 41 aggregate configuration rows | 51,213 | `bce76d9f89ff36b2ef17e56d04b63fad83d67049bd58e8b98684bfbc3c5fc773` |
| `trials.json` | 18,522 trial rows | 30,708,159 | `9f66c404d141fc18efc3d3c67e4f495e0b8b103109cb430eb5e436c9020e9794` |
| `tasks.json` | 113 task rows | 57,634 | `bae967f6472943564c3fc5232fba3c8e0ac465c1be5ccf9dd4895d4ee9df6242` |
| `release.json` | trajectory artifact resolver | 562 | `0b77963ed8c54ef40c5f744ade178b54bfae2662ed94f9235cee85eb542bdc85` |

The trial file contains 18,396 rows with `included_in_score=true` and 126 excluded
infrastructure-error rows. The scored cohort contains 8,985 ordinary passes, four passes ending
with `agent_timeout`, 9,297 ordinary failures, 72 `agent_timeout` failures, and 38
`context_window_exceeded` failures. Model-caused timeout and context failures remain scored.
Provider, routing, rate-limit, and verifier failures marked `included_in_score=false` remain
excluded.

## Cohort and Configuration Selection

The scored cohort requires:

```text
source == "deep-swe"
eval_scope == "full"
included_in_score == true
```

The primary analysis retains all 41 published configurations. A secondary display view selects
one effort level per base model by maximum official pass rate, breaking exact ties by lower
official mean cost and then configuration ID. This best-effort view is descriptive because
selecting the maximum observed pass rate introduces selection bias.

Every numerator and denominator must use the same scored cohort after the stated missing-data
rule. Zero-success configurations remain visible with undefined CPSC rather than being dropped.

## Missing Cost

Twenty-one scored trials lack `cost_usd`: twenty failed Fable trials on one task, spread evenly
across five effort levels, and one successful Sonnet trial. DeepSWE's aggregate mean cost excludes
missing-cost rows while its pass rate retains their outcomes. Directly dividing those two
aggregates therefore mixes denominators.

The primary trial-level analysis retains all scored outcomes and imputes each missing cost with
the mean observed cost of its configuration. This mirrors the aggregate convention as closely as
possible while restoring a single denominator. Three frozen sensitivities are required:

1. charge zero, producing a lower bound on realized CPSC;
2. impute the within-configuration, outcome-specific median; and
3. remove cost-missing rows from both numerator and denominator.

The paper reports missingness by configuration and whether any rank, frontier, or qualitative
conclusion changes. It does not silently treat missing cost as zero.

## Primary Estimands

For configuration \(m\), task \(t\), and scored replicate \(i\), let \(Y_{mti}\) indicate
verified success and \(C_{mti}\) be reported or explicitly imputed model spend.

At the full-suite level:

\[
\widehat p_m = \frac{\sum_{t,i}Y_{mti}}{N_m},
\]

\[
\widehat{\operatorname{CPSC}}^{\mathrm{real}}_m
=\frac{\sum_{t,i}C_{mti}}{\sum_{t,i}Y_{mti}},
\]

\[
\widehat\mu^S_m
=\frac{\sum_{t,i:Y=1}C_{mti}}{S_m},
\qquad
\widehat\mu^F_m
=\frac{\sum_{t,i:Y=0}C_{mti}}{F_m}.
\]

The realized reliability tax and tax share are:

\[
\widehat T^{\mathrm{real}}_m=\frac{F_m}{S_m}\widehat\mu^F_m,
\qquad
\widehat q_m=\frac{\widehat T^{\mathrm{real}}_m}
{\widehat{\operatorname{CPSC}}^{\mathrm{real}}_m}.
\]

Token and step intensity use the same ratio form: total scored tokens or steps divided by
verified successes. Successful and failed conditional distributions, medians, and upper
quantiles remain visible beside means.

## Ranking and Uncertainty

Report pass-rate rank, realized-CPSC rank, rank displacement, Spearman correlation, Kendall
correlation, and the pass-rate/cost Pareto frontier. A lower CPSC rank is better; a higher pass
rate rank is better.

Uncertainty uses 10,000 task-cluster bootstrap replicates with seed `20260714`. Each replicate
samples 113 task IDs with replacement and retains every scored attempt for each sampled task.
This is a suite-composition robustness analysis, not unrestricted population coverage. Paired
model differences use the same sampled task list. The trial data do not expose a trustworthy
cross-provider common-random-number identity, so no seed-level pairing claim is allowed.

Report percentile 95% intervals for solve rate, CPSC, decomposition terms, and paired log CPSC
ratios. For close comparisons, report the bootstrap proportion in which each configuration is
cheaper. The paper must distinguish point-estimate rank from statistically unresolved rank.

Unconstrained CPSC rank is descriptive. It is not, by itself, a recommendation to deploy the
lowest-CPSC configuration because the ratio can favor a cheap policy with an operationally
unacceptable solve rate. The frozen primary outputs therefore include both pass rate and the
joint Pareto frontier, not a single economic winner.

## Frozen Sensitivities

### Missing cost

Run all three missing-cost alternatives specified above.

### Counterfactual failure charge

Reference-budget CPSC is not identified because DeepSWE did not calibrate ShallowSWE task
budgets. A retrospective sensitivity may still illustrate the metric. The declared anchor is
`mini_swe_agent_gpt_5_6_sol_max`, selected from the published capability leaderboard before this
trial-level analysis. For each task, define a proxy base budget as the median included,
cost-complete anchor spend. Recompute CPSC with failed rows charged at 0.5x, 1x, and 2x that proxy.

These are counterfactual failure-charge curves, not calibrated \(B_t\) values. They may establish
rank sensitivity but may not be presented as a DeepSWE implementation of ShallowSWE calibration.

### Common-price reconstruction

Provider-reported `cost_usd` is primary. A common-price reconstruction is reportable only if the
dated price sheet covers every displayed configuration and input, cache, output, and reasoning
token semantics can be reconciled consistently. Otherwise report coverage and illustrative
partial results without producing a common-price global rank.

## Cross-Regime Comparison

Raw DeepSWE and ShallowSWE dollars may be shown descriptively, but not interpreted as the prices
of equal work units. The primary later comparison uses matched configurations and compares:

- within-benchmark pass and CPSC ranks;
- CPSC relative to a benchmark-specific declared anchor;
- realized or reference-budget reliability-tax share;
- Pareto-frontier membership; and
- rank change as task pressure changes.

The cross-regime question is whether a configuration economical on frontier work is also
economical on routine work, not whether a shallow completion costs fewer dollars than a deep one.

## Paper and Funding Deliverables

The working paper targets 6 to 10 pages excluding references and appendices:

1. motivation and contribution boundary;
2. CPSC framework and estimands;
3. DeepSWE data, cohort, and reproducibility;
4. primary economic results and rank changes;
5. decomposition, uncertainty, and sensitivities;
6. limitations and what remains unidentified; and
7. the calibrated ShallowSWE research agenda.

The reproducibility package must include a hash-verifying fetch command, deterministic analysis
command, machine-readable configuration summaries, row-level derived outputs, figure data, and
paper tables. The funding brief is a separate concise artifact. It may argue that an externally
tested metric framework motivates the missing routine-work experiment, but it must not present
the retrospective DeepSWE analysis as proof that the ShallowSWE hypotheses are true.

## Completion Gates

Before circulation:

- reproduce official pass rates and explain every cost discrepancy;
- account for all included and excluded rows and all missing metric fields;
- verify every table and figure from frozen machine-readable outputs;
- run all declared bootstrap and sensitivity analyses;
- check related work before making originality claims;
- label observed, reconstructed, counterfactual, and proposed quantities; and
- audit every funding claim against a paper result or explicit research gap.

## Amendment Log

**A1, 2026-07-14, result-informed exploratory addition.** The first full-data pipeline dry run
showed that unconstrained realized CPSC can favor very inexpensive configurations with low solve
rates. The paper will not declare an unconstrained CPSC winner. It will add a pass-rate versus
attempt-cost Pareto frontier and a minimum-CPSC curve over observed reliability floors from 0.00
through 0.75 in increments of 0.05. This curve is useful for interpreting CPSC as a constrained
decision metric, but it was added after the first full-data dry run and must be labeled
exploratory rather than frozen confirmatory analysis.

**A2, 2026-07-14, reviewer-requested result-informed robustness addition.** Two independent
Fable reviews agreed that the point-estimate rank association and reliability-floor winner were
not sufficient for publication. Before paper revision, the analysis adds task-level 0-of-4,
1-to-3-of-4, and 4-of-4 success heterogeneity; any-success task coverage; pairwise solved-task
overlap and matched solved-task CPSC diagnostics; configuration-level exclusion accounting and
exclusions-as-failures sensitivities; task-bootstrap intervals for rank association, rank
distributions, and paired pass-rate differences; within-model effort association; and a bootstrap
that reselects the reliability-floor policy within every replicate. These analyses directly test
the reviewers' task-mix, exclusion-imbalance, effort-pooling, and selection-uncertainty
explanations. Matched solved-task and reliability-floor outputs remain post-outcome exploratory
diagnostics. The public rows do not identify a predeclared retry order or stopping rule, so no
sequential retry policy is inferred.

**A3, 2026-07-14, discussion-requested result-informed hypothesis test.** A follow-up Fable
discussion proposed that realized CPSC rewards configurations that solve a cheap task subset and
fail inexpensively elsewhere. It predicted that the ordering would move toward capability rank
after charging failures with pseudo-budgets derived from successful Sol-max attempts, and that
task strata defined by how many configurations solve each task would reveal distinct shallow and
deep regimes. The analysis therefore adds two falsification diagnostics. First, it restricts every
configuration to tasks Sol max solves at least once, defines each task's pseudo-budget as the median
Sol-max successful-attempt spend, and applies the existing 0.5x, 1x, and 2x failure multipliers.
Second, it classifies tasks as rare, contested, or common when at most one half, between one half
and three quarters, or more than three quarters of configurations solve the task at least once, then
recomputes realized CPSC, pass rate, coverage, and ranks within each stratum. Both additions are
post-hoc diagnostics, not calibrated reference-budget results.
