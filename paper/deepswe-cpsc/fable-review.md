# Fable High-Effort Independent Review

Model: `claude-fable-5`

Effort: `high`

Date: 2026-07-14

Session: `7bfecf3d-1cb2-4e39-bcb0-8ec038b0130f`

This is the verbatim review returned from the sanitized public-data packet in
`fable-review-packet.md`.

---

I checked the packet's internal arithmetic before reviewing: the decomposition identity holds in every table row (e.g., Sol max: 450 × $8.386 ≈ $3,774 total spend; $3,774 / 327 = $11.54 = $8.360 + (123/327) × $8.457), pass rates match successes/attempts exactly, and the bootstrap and floor tables are mutually consistent. The review below takes the numbers as given.

## 1. Bottom-line verdict

Yes, there is a publishable 6–10 page working paper — but only after a reframing. The headline as currently implied ("economic rank diverges from capability rank on DeepSWE") is weak, because realized CPSC is algebraically `mean_attempt_cost / pass_rate`. With configuration-mean imputation preserving the official aggregates, every CPSC value and both rank correlations are recoverable from the public leaderboard alone, and the packet admits the ratio and "selected example inversions" were inspected before freeze. The genuine, trial-level contributions are: (a) the exact success/failure-tax decomposition, (b) task-clustered uncertainty on economic comparisons, and (c) the demonstration that the "winner" flips under both a reliability floor and a counterfactual failure price — i.e., that the ratio is not decision-identifying without a declared policy. Lead with (c). As a workshop paper or arXiv working paper motivating the ShallowSWE program, this clears the bar. As a standalone contribution to a selective venue, it does not.

## 2. Errors and problems (mathematical, data, denominator, ranking, bootstrap, missingness, selection, interpretation)

**No arithmetic errors found.** The estimand identities are exact and the tables reproduce. The mixed-denominator fix is real but immaterial: 21 of 18,396 rows (~0.11%), and your own sensitivity confirms nothing moves. Do not oversell it as a methodological finding.

Substantive problems, roughly in order of severity:

1. **Unstated algebraic redundancy.** `realized_CPSC = sum(C)/S = (mean_cost × N)/(p × N) = mean_cost / p`. The paper must state this identity explicitly in the estimands section. A referee who discovers it themselves will conclude the primary result is a re-plot of public aggregates and read everything else uncharitably.

2. **The all-configuration Spearman of −0.1843 is neither significant nor interpretable as stated.** With n = 41, the naive SE of Spearman under independence is ≈ 1/√40 ≈ 0.158, so −0.18 is barely one SE from zero — and the 41 configurations are not independent: they are ~13 base models × effort levels sharing 113 tasks. Worse, within-model effort scaling *mechanically* generates the negative association (higher effort → higher pass rate and higher cost, visible in the Sol column: medium → xhigh → max moves pass rank 12 → 2 → 1 while CPSC rank moves 8 → 17 → 30). The near-zero correlation may be almost entirely a within-model effort artifact rather than a between-model economic inversion. You have the machinery to fix this: bootstrap the rank correlation over task clusters, and decompose rank disagreement into within-base-model and between-base-model components. The 13-row panel's Spearman 0.3132 is closer to the deployment question but is itself selection-biased (max pass rate per model), as you note.

3. **The unconstrained CPSC minimum is a winner's-curse selection over 41 configurations, and it is not statistically separated from its rival.** Terra medium's interval ($1.374–$2.076) overlaps Luna high's ($1.484–$2.111), and your own paired comparison shows Luna cheaper in 25.4% of replicates with log-ratio interval [−0.1106, 0.2140] straddling zero. "Terra medium is the CPSC minimum" must be stated as a point estimate with an explicit tie against Luna high.

4. **Realized CPSC is not "cost per successful completion" in any deployable sense.** `mean_cost / p` equals expected cost per success under an infinite-retry policy with *independent* attempts. Attempts on the same task are strongly dependent — with 4 attempts per task you can measure this directly. A configuration failing a task will usually fail it again; retries do not convert Terra medium's 35.11% into successes on the other 65%. Name the estimand precisely: realized benchmark spend per verified success under DeepSWE's attempt policy.

5. **Bootstrap gaps.** (a) What happens to a replicate in which a weak configuration draws zero successes? "Zero-success configurations remain visible with undefined CPSC" covers the point estimate but not the resampling rule — state it. (b) Percentile intervals for ratio estimands with 113 clusters and heavy-tailed cost can undercover; a BCa or studentized check is cheap. (c) The floor table uses point-estimate eligibility while Luna max's pass interval (60.94%–73.39%) dips below its 65% floor — you flag this honestly, but then the floor table cannot be presented as a decision procedure, only an illustration.

6. **Attempt-count asymmetry.** 113 tasks × 4 attempts = 452, but attempts range 448–452 (Luna max 448, Terra medium and Sol max 450). The 126 excluded infrastructure rows are presumably not missing at random across configurations and tasks. At ~0.7% this is likely immaterial, but show a one-line audit that exclusions are not concentrated in config × task cells that would move CPSC.

7. **The 4 `agent_timeout` passes** counted as successes need one sentence of justification (presumably solution submitted before timeout).

8. **Anchor budget proxy.** Using per-task median Sol max spend as the proxy budget is reasonable, but Sol max was chosen as anchor *knowing* it is the top pass-rate configuration, and its spend on tasks it fails is spend-until-abandonment, a strange budget. Label the anchor choice result-informed.

## 3. Strongest alternative explanations and likely reviewer objections

1. **Task-mix composition (the big one).** Terra medium's $1.661 per success is the average cost of successes on the ~35% of attempts it can solve — plausibly the easy tasks. Sol max's $11.54 includes buying successes on hard tasks no cheap configuration solves. Comparing CPSC across configurations with very different solved-task footprints compares different goods. Your own claim boundary says a DeepSWE completion and a shallow-task completion are not equal units — the same objection applies *within* DeepSWE across configurations. Without a matched-task or difficulty-stratified comparison, the inversion may be pure composition.

2. **Effort-scaling artifact** (as in §2, point 2): the negative all-config correlation is what any monotone cost–capability tradeoff within a model family produces mechanically. Reviewers will say you rediscovered the price of test-time compute.

3. **List-price economics.** `cost_usd` conflates model efficiency with provider pricing strategy, caching semantics, and preview subsidies. Gemini 3.1 Pro Preview's $80.68 CPSC with ~84% tax share may be a pricing artifact, not an inefficiency finding. The common-price gate failed, so every cross-provider comparison inherits contemporaneous list prices — the ranking is non-stationary by construction.

4. **Failure mispricing cuts both ways.** Real failure cost is human triage, delay, and rework — not model spend. Your own 2× failure-charge sensitivity flips the minimum from Terra medium territory to Luna max ($10.651, 71.13% tax share). The winner depends on the one parameter you cannot observe. That is the paper's best result, but a hostile reviewer will phrase it as "the metric gives no answer."

5. **"Practitioners already do this."** Cost/pass-rate ratios circulate informally with every leaderboard release. The reply must be: the decomposition, clustered uncertainty, and policy-flip results require trial-level data and are new.

## 4. Confirmatory versus result-informed exploratory

Genuinely frozen and confirmatory-grade: the estimand definitions, imputation convention, missing-cost sensitivities, bootstrap design (10,000 replicates, seed 20260714), and the *magnitudes* of the decomposition and intervals.

Quasi-confirmatory at best: the primary hypothesis itself ("capability rank does not fully determine economic rank"), because the leaderboard ratio and selected inversions were inspected pre-freeze. State this in the paper exactly as bluntly as the packet does.

Explicitly exploratory / result-informed: the reliability-floor decision rule (Amendment A1, adopted after the dry run exposed the 35% winner), the floor table, the 13-row display panel, the Sol max anchor choice, and any lower-confidence-bound eligibility variant. The packet's honesty here is a strength — preserve it verbatim.

## 5. Strongest defensible thesis and title

Thesis: *Cost-per-success is computable from any benchmark's public aggregates, but it is not decision-identifying: on DeepSWE v1.1, the economically preferred configuration changes with the required reliability floor (Terra medium → Luna high → … → Sol xhigh across floors 0%–70%) and with the price assigned to failure (flipping to Luna max at a 1× counterfactual charge). Failure-aware economics therefore requires declared policy inputs — a reliability requirement and a calibrated failure budget — that frontier benchmarks do not provide.*

Title options, in order of preference:

1. "The Reliability Tax: Why Cost-per-Success Needs a Policy Before It Names a Winner"
2. "Cheap Failures, Expensive Successes: Failure-Aware Economics of Fixed Coding-Agent Configurations on DeepSWE"

Avoid any title implying rank inversion is the discovery.

## 6. Claims that must be removed or weakened

- **Remove:** any statement that Terra medium *is* the most economical configuration. It is a point-estimate minimum selected over 41 configurations, statistically tied with Luna high (cheaper in only 74.6% of paired replicates).
- **Weaken:** "economic and capability ranks differ substantially" based on Spearman −0.1843. Report it, but with a cluster-bootstrap interval and the within/between-model decomposition, and concede the effort-scaling mechanism.
- **Weaken:** the framing of the mixed-denominator correction as a finding; it moves nothing at 21/18,396 rows.
- **Remove:** any language suggesting the inversion result confirms a pre-registered prediction; the ratio was inspected pre-freeze.
- **Rename:** "realized cost per successful completion" wherever it could be read as a deployable per-unit cost; attempts are not independent retries, so `mean_cost / p` does not price a retry-until-success workflow.
- **Reframe:** the floor table as an illustration, not a decision procedure, given point-estimate eligibility with ±6–7pp pass-rate intervals.
- **Keep** the honest hedges already present (suite-composition intervals, no seed-level pairing, failed common-price gate) — they are load-bearing.

## 7. Necessary additional analyses, ranked by importance (all feasible from existing trial data)

1. **Task-mix control (essential).** Compute CPSC on matched solved-task strata — e.g., tasks solved at least once by both configurations in a pair, or tasks stratified by number of configurations solving them. Report the solved-task overlap (Jaccard) between Terra medium and Sol max. If the inversion survives on the common subset, the paper is much stronger; if not, that is itself the finding. Cost: low.
2. **Within/between-model decomposition of rank disagreement,** plus per-base-model cost–capability effort curves. Directly answers the effort-scaling objection. Cost: low.
3. **Retry-policy realism.** Use the ~4 attempts per task to estimate task-level success heterogeneity (empirical pass@k or beta-binomial) and compute expected cost per success under "retry up to k" with within-task dependence. This converts realized CPSC into something a deployer can use and quantifies how much `mean_cost / p` understates true cost-per-success. Cost: moderate; value: high.
4. **Cluster-bootstrap the Spearman and Kendall statistics** so the headline correlation carries an interval. Cost: trivial given existing infrastructure.
5. **Lower-confidence-bound eligibility variant of the floor table,** labeled exploratory, to show which floor selections are fragile (Luna max at 65% will likely drop). Cost: low.
6. **BCa or studentized bootstrap check** on the CPSC ratio intervals; document undefined-CPSC replicate handling. Cost: low.
7. **Infra-exclusion audit:** distribution of the 126 excluded rows across config × task cells. Cost: trivial.

## 8. Does this validate CPSC as the flagship contribution and support the funding case?

Partially, and the packet's own framing is about right. What the exercise validates: the metric family is *portable* (exact reproduction of all 41 official aggregates to 3.55e-15), the decomposition and clustered-uncertainty machinery works, and the policy-dependence result is real and reproducible. What it does not validate: the CPSC construct itself. Reference-budget CPSC (`CPSC_B`) is unidentified here, the routine-work regime is untested, and — per the identity in §2 — realized CPSC alone adds no information beyond published aggregates. The honest funding sentence the data support is: *even on frontier tasks, the economic ordering is undetermined without a reliability floor and a failure price, and neither can be calibrated on existing benchmarks — that calibration is exactly what the proposed task suite provides.* That is a coherent, narrow feasibility argument. It is motivation for ShallowSWE, not validation of it, and the paper should say so in those words.

## 9. Recommended outline (6–10 pages)

1. **Introduction and claim boundary** (~1 page). The one falsifiable question; explicit statement that realized CPSC = mean cost / pass rate and what therefore is and is not new here.
2. **Data and cohort** (~0.5 page). Frozen artifacts, 18,396 scored rows, exclusion and missing-cost handling, exact reproduction of official aggregates.
3. **Estimands** (~1 page). Decomposition identity, what "realized" means, why reference-budget CPSC is unidentified, retry-dependence caveat.
4. **Results** (~2 pages). Decomposition table; rank association with cluster-bootstrap intervals and within/between-model split; matched-task composition check; bootstrap intervals and the Terra medium–Luna high tie.
5. **Policy dependence** (~1.5 pages). Reliability-floor illustration (labeled exploratory, Amendment A1 disclosed); failure-charge sensitivity with the winner flip at 1× and 2×.
6. **Threats to validity** (~1 page). Composition, list-price non-stationarity, retry non-independence, benchmark attempt policy.
7. **What only a calibrated suite can answer** (~0.5 page). The ShallowSWE hypothesis, stated as untested.
8. **Reproducibility appendix.** Hashes, seeds, tests, sensitivity tables.

The single most important revision across all of this: move the identity `realized CPSC = mean cost / pass rate` from an implicit fact to the paper's opening move, and let the decomposition, uncertainty, and policy-flip results — which genuinely require trial-level data — carry the contribution.
