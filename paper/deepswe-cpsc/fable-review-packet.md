# Independent Review Packet: DeepSWE CPSC Reanalysis

This packet contains only public DeepSWE v1.1 aggregate results, mathematical definitions, and
analysis decisions derived from public data. It excludes private tasks, trajectories, credentials,
unrelated workspace files, and the provisional paper draft.

## Review role

Act as a skeptical benchmark economist and statistics reviewer. This is a proposed 6 to 10 page
working paper about failure-aware economics of fixed coding-agent configurations.

Return nine numbered sections:

1. Bottom-line verdict on whether there is a publishable mini-paper.
2. Mathematical, data, denominator, ranking, bootstrap, missingness, selection, or interpretation
   errors.
3. Strongest alternative explanations and likely reviewer objections.
4. Which findings are confirmatory versus result-informed exploratory.
5. Strongest defensible thesis and title.
6. Claims that must be removed or weakened.
7. Three to seven genuinely necessary additional analyses, ranked by importance and cost.
8. Whether the exercise materially validates CPSC as the flagship contribution and supports a
   funding case for calibrated ShallowSWE tasks.
9. A concise recommended paper outline.

Quote exact numbers and field names where useful. Be direct.

## Research question and claim boundary

The analysis asks whether failure-aware economic metrics add decision-relevant information to
DeepSWE's frontier-capability results. It applies the ShallowSWE metric family to an independent
public benchmark, then identifies which questions still require a calibrated routine-work suite.

The reanalysis may demonstrate:

- portable computation of realized cost per successful completion, or realized CPSC;
- economic rank changes relative to pass-rate rank;
- decomposition into successful-work cost and realized reliability tax;
- uncertainty and sensitivity of economic comparisons; and
- empirical motivation for measuring the routine-work regime.

It may not claim that DeepSWE validates ShallowSWE's routine-work construct, calibrated reference
budgets, bounded hidden-verifier repair loop, replacement-cost protocol, or production return on
investment. It may not treat a DeepSWE completion and a future shallow-task completion as equal
units of economic value.

The primary hypothesis frozen before the trial-level pipeline was completed was: frontier
capability rank does not fully determine frontier-task economic rank. The later ShallowSWE
hypothesis is: among routine tasks solved at acceptable reliability by multiple configurations,
expected cost per verified completion differs materially and the preferred configuration changes
with task pressure.

This is a retrospective analysis plan, not a blinded preregistration. Before freeze, the public
leaderboard, its pass rates and mean costs, the basic ratio `mean_cost / pass_rate`, and selected
example inversions had been inspected. The trial-level decomposition, clustered uncertainty, full
ranking, and sensitivity results had not been computed.

## Frozen public data

DeepSWE v1.1 has 113 original long-horizon tasks. Four public artifacts were frozen by byte count
and SHA-256 on 2026-07-14. The trial artifact contained 18,522 rows. The scored cohort requires:

```text
source == "deep-swe"
eval_scope == "full"
included_in_score == true
```

The cohort contains:

- 18,396 scored rows and 126 excluded infrastructure-error rows;
- 41 model-effort configurations across all 113 tasks;
- 8,985 ordinary passes and 4 passes ending with `agent_timeout`;
- 9,297 ordinary failures, 72 `agent_timeout` failures, and 38
  `context_window_exceeded` failures; and
- model-caused timeout and context failures retained as scored outcomes.

Provider, routing, rate-limit, and verifier failures already marked
`included_in_score=false` remain excluded.

## Missing cost

Twenty-one scored rows lack `cost_usd`: 20 failed Fable rows on one task, spread evenly across five
effort levels, and one successful Sonnet row. DeepSWE's aggregate mean cost excludes missing-cost
rows while pass rate retains their outcomes, so directly dividing those aggregates mixes
denominators.

The primary trial-level analysis retains every scored outcome and imputes each missing cost with the
mean observed cost of its configuration. Imputing the configuration mean exactly preserves the
official aggregate mean while restoring one denominator. Frozen alternatives are:

1. charge zero as a lower bound;
2. impute the within-configuration, outcome-specific median; and
3. remove cost-missing rows from both the numerator and denominator.

All three alternatives preserve the all-configuration rank correlations and the unconstrained CPSC
minimum reported below.

## Estimands

For configuration `m`, task `t`, and scored attempt `i`, let `Y_mti` indicate verified success and
`C_mti` be reported or explicitly imputed model spend. Let `N_m` be attempts, `S_m` successes, and
`F_m = N_m - S_m` failures.

```text
p_hat_m = S_m / N_m

realized_CPSC_hat_m = sum(C_mti) / S_m

mu_success_hat_m = sum(C_mti where Y=1) / S_m

mu_failure_hat_m = sum(C_mti where Y=0) / F_m

realized_CPSC_hat_m
  = mu_success_hat_m + (F_m / S_m) * mu_failure_hat_m

realized_reliability_tax_hat_m
  = (F_m / S_m) * mu_failure_hat_m

realized_reliability_tax_share_hat_m
  = realized_reliability_tax_hat_m / realized_CPSC_hat_m
```

The ratio is computed from total scored spend over total verified successes, not as an unweighted
average of per-task ratios. Zero-success configurations remain visible with undefined CPSC.

Realized CPSC prices failures at observed spend. Reference-budget CPSC would instead be:

```text
CPSC_B = mu_success + ((1 - p) / p) * B_t
```

where `B_t` is a task-only reference budget. DeepSWE did not calibrate `B_t`, so reference-budget
CPSC is not identified in this reanalysis.

## Ranking and secondary display panel

The primary analysis retains all 41 configurations and independently ranks pass rate descending and
realized CPSC ascending. It reports average ranks, rank displacement, Spearman rank correlation,
Kendall tau-b, and the joint pass-rate/mean-attempt-cost Pareto frontier.

The secondary display panel selects one configuration per base model by maximum official pass rate,
breaking exact ties by lower official mean cost and then configuration ID. This gives 13 rows. The
view is descriptive because selecting the maximum observed pass rate introduces selection bias.

Rank association results:

| Panel | Configurations | Spearman | Kendall tau-b |
|---|---:|---:|---:|
| All configurations | 41 | -0.1843 | -0.1330 |
| Best pass rate per base model | 13 | 0.3132 | 0.2308 |

The correlations compare pass-rate rank with realized-CPSC rank. Lower numerical rank is better on
both axes after ranking.

## Selected primary results

| Configuration | Attempts | Successes | Pass rate | Mean attempt cost | Successful spend | Failure tax | Tax share | Realized CPSC | Pass rank | CPSC rank |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| GPT-5.6 Terra medium | 450 | 158 | 35.11% | $0.583 | $0.568 | $1.093 | 65.80% | $1.661 | 33 | 1 |
| GPT-5.6 Luna high | 452 | 200 | 44.25% | $0.778 | $0.753 | $1.006 | 57.20% | $1.758 | 27 | 2 |
| GPT-5.6 Sol medium | 452 | 276 | 61.06% | $1.862 | $1.864 | $1.186 | 38.88% | $3.049 | 12 | 8 |
| GPT-5.6 Luna max | 448 | 301 | 67.19% | $3.028 | $3.075 | $1.432 | 31.77% | $4.507 | 8 | 11 |
| GPT-5.6 Sol xhigh | 451 | 319 | 70.73% | $4.704 | $4.704 | $1.946 | 29.26% | $6.650 | 2 | 17 |
| GPT-5.6 Sol max | 450 | 327 | 72.67% | $8.386 | $8.360 | $3.181 | 27.56% | $11.541 | 1 | 30 |

Thus, the top pass-rate configuration is GPT-5.6 Sol max at 72.67%, but it ranks 30th by realized
CPSC. The unconstrained realized-CPSC minimum is GPT-5.6 Terra medium at $1.661 with a 35.11% pass
rate. The observed cost per attempt is sufficiently low that frequent failure does not eliminate
its ratio advantage.

## Task-cluster bootstrap

Uncertainty uses 10,000 task-cluster bootstrap replicates with seed `20260714`. Each replicate
samples 113 task IDs with replacement and retains every scored attempt associated with each sampled
task. Paired configuration comparisons use the same sampled task list. The trial data do not expose
a trustworthy cross-provider common-random-number identity, so no seed-level pairing is claimed.

Percentile 95% intervals:

| Configuration | Pass-rate interval | Realized-CPSC interval |
|---|---:|---:|
| Terra medium | 28.44% to 41.74% | $1.374 to $2.076 |
| Luna high | 37.83% to 50.88% | $1.484 to $2.111 |
| Sol medium | 53.98% to 67.92% | $2.638 to $3.557 |
| Luna max | 60.94% to 73.39% | $3.795 to $5.333 |
| Sol xhigh | 63.86% to 77.61% | $5.844 to $7.568 |
| Sol max | 65.71% to 79.46% | $9.982 to $13.391 |

Selected paired comparisons use the log ratio `log(CPSC_A / CPSC_B)`:

- Luna high versus Terra medium: interval `[-0.1106, 0.2140]`; Luna is cheaper in 25.4% of
  replicates. The equivalent ratio interval is approximately 0.895 to 1.239.
- Luna max versus Sol max: interval `[-1.0628, -0.8225]`; Luna is cheaper in 100% of replicates.
  The point CPSC ratio is 0.390 and the ratio interval is approximately 0.345 to 0.439.
- Sol medium versus Sol xhigh: interval `[-0.8647, -0.6905]`; Sol medium is cheaper in 100% of
  replicates.

These are suite-composition robustness intervals, not unrestricted population coverage.

## Reliability-constrained decision rule

The first full-data dry run showed that unconstrained CPSC can favor a low-cost configuration with
low solve rate. This triggered Amendment A1 after results were seen. The paper therefore must not
declare an unconstrained CPSC deployment winner.

The exploratory decision rule for a required point-estimate solve rate `r` is:

```text
m_star(r) = argmin_m realized_CPSC_hat_m
            subject to p_hat_m >= r
```

The floor is a policy input, not a fitted parameter. The observed choice changes at:

| Required floor | Selected configuration | Selected pass rate | Realized CPSC | Eligible configurations |
|---:|---|---:|---:|---:|
| 0% through 35% | Terra medium | 35.11% | $1.661 | 41 at the 0% floor |
| 40% | Luna high | 44.25% | $1.758 | 29 |
| 45% through 50% | Terra high | 53.76% | $2.110 | 26 at the 45% floor |
| 55% | Luna xhigh | 56.86% | $2.701 | 16 |
| 60% | Sol medium | 61.06% | $3.049 | 13 |
| 65% | Luna max | 67.19% | $4.507 | 10 |
| 70% | Sol xhigh | 70.73% | $6.650 | 2 |
| 75% | No eligible configuration | n/a | n/a | 0 |

Eligibility uses point estimates. For example, Luna max is selected at the 65% floor although its
task-cluster bootstrap pass-rate interval is 60.94% to 73.39%. A lower-confidence-bound or Bayesian
eligibility rule was not frozen or run.

## Failure-cost decomposition in the 13-row display panel

The realized reliability-tax share varies substantially. Examples:

- GPT-5.6 Sol max: CPSC $11.54, 27.6% reliability tax.
- GPT-5.6 Luna max: CPSC $4.51, 31.8% reliability tax.
- GLM-5.2 max: CPSC $8.95, 55.8% reliability tax.
- Kimi K2.7 Code default: CPSC $9.22, 73.5% reliability tax.
- Claude Sonnet 4.6 high: CPSC $18.45, about 70% reliability tax.
- Gemini 3.1 Pro Preview high: CPSC $80.68, about 84% reliability tax.

A lower tax share does not imply lower total CPSC because conditional successful spend also varies.

## Frozen sensitivities

### Missing cost

Charging zero, imputing the within-configuration outcome median, or using complete cases leaves the
all-configuration Spearman and Kendall results unchanged and preserves Terra medium as the
unconstrained CPSC minimum.

### Counterfactual failure charge

Because calibrated reference budgets are unavailable, a declared sensitivity uses GPT-5.6 Sol max
as an anchor. For each task, the proxy base budget is the median included, cost-complete anchor spend
on that task. Failed rows are charged at 0.5, 1, or 2 times that proxy. This is explicitly labeled a
counterfactual failure-charge sensitivity, not ShallowSWE calibration.

| Failure multiplier | Minimum proxy CPSC configuration | Pass rate | Proxy CPSC | Proxy tax share |
|---:|---|---:|---:|---:|
| 0.5x | Sol medium | 61.06% | $4.460 | 58.21% |
| 1.0x | Luna max | 67.19% | $6.863 | 55.19% |
| 2.0x | Luna max | 67.19% | $10.651 | 71.13% |

The minimizing configuration changes with the failure charge.

### Common-price reconstruction

Provider-reported `cost_usd` remains primary. A common-price reconstruction was gated on complete
coverage and consistent input, cache, output, and reasoning-token semantics. The gate was not met,
so no global common-price ranking was produced.

## Validation and reproducibility

The pipeline reproduces all 41 official pass rates and mean costs. Maximum absolute pass-rate
difference is zero. Maximum absolute mean-cost and implied-CPSC difference is approximately
`3.55e-15`. Artifact byte counts and SHA-256 hashes are checked before analysis.

The generated package includes:

- 18,396 row-level derived trial records with reported cost, analysis cost, imputation flag, outcome,
  tokens, and steps;
- full configuration and best-per-model tables;
- 10,000-replicate bootstrap intervals and all 820 paired comparisons;
- reliability-floor and sensitivity tables;
- deterministic publication figures; and
- a file manifest with SHA-256 hashes.

Focused unit tests cover cohort filtering, exact CPSC decomposition, all missing-cost conventions,
zero-success visibility, independent ranks, frontier and floor construction, display selection,
deterministic task-cluster bootstrap, paired comparisons, failure-charge sensitivity, artifact
verification, and deterministic paper assets.

## Proposed interpretation and funding question

The initial verbal prediction was that frontier-task CPSC might collapse into capability rank. The
data do not support that simple prediction: economic and capability ranks differ substantially.
However, unconstrained CPSC can favor low reliability, so the portable ratio does not by itself
identify a deployment recommendation.

The candidate thesis is: failure-aware completion economics adds information even on frontier
coding tasks, but it is decision-safe only inside an explicit reliability policy. The DeepSWE
exercise validates metric portability and reveals the need to declare reliability and failure cost.
It does not prove that a wide routine-work regime exists.

The proposed ShallowSWE experiment would test one falsifiable sentence:

> There exists a substantial regime of routine, functionally verifiable software work where
> multiple fixed configurations satisfy a predeclared reliability requirement but their CPSC
> ordering differs from their capability ordering.

The funding claim would be narrow: the external reanalysis has produced nontrivial reproducible
findings, and funding is needed to identify the missing routine-work regime and calibrate its task
budgets, replacement costs, repair policy, and reliability eligibility rule. It is not a request to
build another generic capability leaderboard or to rerun DeepSWE at larger scale.
