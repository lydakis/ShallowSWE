# Fable High-Effort Independent Review: Initial Response

This is the first Fable response recovered by George after the original CLI output was not captured.
It reviewed the thirteen allowed public-data and analysis sources directly.

---

I've now read all thirteen allowed sources: the frozen plan, the pre-analysis spec, both analysis modules, both test files, and all seven generated tables plus the summary. I verified the arithmetic directly (decomposition identity, tau-b implementation, cluster-bootstrap weighting, and the leaderboard reconciliation, which matches official aggregates to 3.6e-15). Here is the adversarial review. Note this was a read-only assessment; no plan file was needed since the deliverable is the review itself.

---

## 1. Bottom-line verdict

**Yes, there is a publishable 6–8 page reanalysis note — but only if you demote the current headline.** The pipeline is genuinely solid: exact reproduction of official pass rates and mean costs (`leaderboard_reconciliation.all_match: true`, max abs diff 3.55e-15), a clean decomposition identity (I checked: for Luna max, conditional successful spend 3.0752 + reliability tax 1.4318 = CPSC 4.5070 exactly), hash-pinned artifacts, and honest amendment logging. The problem is that the two "surprising" results you propose to lead with — the negative rank association and the 65%-floor Luna-vs-Sol pick — are respectively (a) statistically unresolved and mechanically confounded, and (b) a post-hoc selection on noisy point estimates at a cherry-pickable grid point. The publishable core is the **paired Luna/Sol result and the decomposition**, not the correlation.

## 2. Mathematical, data, denominator, ranking, bootstrap, missingness, selection, and interpretation errors

**No arithmetic errors found.** Specifically verified: `realized_cpsc_usd` = total/successes throughout (e.g., Luna max 1356.596331/301 = 4.50696); the Kendall tau-b denominator in `_rank_association` (`deepswe_economics.py:794-797`) is algebraically equivalent to the standard (C−D)/√((n0−n1)(n0−n2)) form; average-rank tie handling is correct; the bootstrap's task-count weighting of sufficient statistics is a correct cluster bootstrap; the bootstrap tax-share definition (failed_cost/total_cost) is consistent with the point-estimate definition. The single-denominator discipline the pre-analysis demands is actually implemented.

The errors are inferential, not computational:

- **The rank association is not distinguishable from zero and is confounded by pooling.** Spearman −0.184, Kendall −0.133 over 41 configurations. Under independence the SE of Spearman at n=41 is ~0.16, so −0.18 is ~1 SD from zero — and the 41 "observations" are not independent (same 113 tasks, and 5–6 effort levels per model). Worse, the best-per-model panel flips sign: `rank_association_best_per_model` Spearman **+0.313**. The negative all-config number is mechanically produced by within-model effort curves: dropping effort cuts attempt cost by 10–100× while cutting pass rate by only 2–3×, so cheap-and-weak effort levels get good CPSC ranks. That's a property of pooling a price range spanning $0.072 (Luna low) to $26.40 (Sonnet 5 max) per attempt, not a discovery about capability-vs-economics. **No CI is computed for either correlation** — a gap given that the doc requires distinguishing point-estimate rank from unresolved rank.

- **Reliability-floor selection ignores estimation error in both the eligibility gate and the winner.** Eligibility uses point-estimate pass rate (`_reliability_floor_curve`, `deepswe_economics.py:847-873`). Luna max's bootstrap pass-rate interval is [0.609, 0.734] — whether its true solve rate clears the 0.65 floor is roughly a coin flip. Choosing the minimum CPSC among eligible configs then adds winner's-curse bias. And the result is window-fragile: at the 0.70 floor the winner is Sol xhigh at $6.65 with only 2 eligible configurations.

- **Rank displacements are reported without uncertainty.** Fable 5 max's displacement of +35 is a point estimate; the CPSC CIs in `bootstrap-intervals.csv` overlap heavily in the middle of the table. No bootstrap rank distribution exists in the outputs.

- **Uneven attempt denominators from infrastructure exclusions.** Attempts range 429 (Opus 4.8 max, 23 excluded) to 452. Exclusion is assumed ignorable, but infra errors (timeouts, rate limits) plausibly correlate with long, expensive, failing runs — differentially by provider. No per-config exclusion audit or exclusions-as-failures bound exists.

- **Minor:** `probability_a_cheaper: 1.0` should be reported as "all 10,000 replicates," not probability 1; Luna low's CPSC interval conditions on the 9,937 replicates with ≥1 success (disclosed via `defined_cpsc_replicates`, but it biases that CI); imputation is done once before bootstrapping so imputation uncertainty isn't propagated (negligible at 21/18,396, but say so).

## 3. Strongest alternative explanations and reviewer objections

1. **"Your negative correlation is an effort-knob artifact."** See above. A reviewer will split the association into within-model (across effort) and between-model components and find the story is "effort levels trade pass rate against cost within a model," which is neither surprising nor about model choice.
2. **"Cheap configs solve only easy tasks."** Terra medium's conditional successful spend ($0.568) averages over the ~35% easiest tasks; Sol max's ($8.360) averages over 73% of tasks. Cross-config comparisons of conditional spend — and of CPSC itself — are over different success sets. Without a matched-task or per-task-difficulty analysis, "Terra medium is cheap per success" partly means "Terra medium only succeeds where success is cheap."
3. **"CPSC's retry interpretation breaks on unsolvable tasks."** Realized CPSC equals expected retry cost per success only if failures are re-drawable. Tasks a config fails 4/4 times are plausibly never-solvable by it; spend on those isn't a tax you amortize, it's money burned with no path to success. The attempt-level pass rate in the floor curve is also the wrong quantity for a buyer, who cares about task coverage (any-pass rate).
4. **"Provider-reported dollars aren't commensurable."** Fable is priced via `vertex_ai`, Opus/Sonnet via `anthropic`, Kimi via `openrouter`; cache and reasoning-token pricing semantics differ. The repricing analysis is gated off (`common_price_repricing.status: not_run`). Cross-vendor CPSC comparisons are therefore soft. (Helpfully, the strongest pair — Luna vs Sol — is same-provider OpenAI, same harness.)
5. **"The reliability tax share is mechanically high for low-pass configs."** Tax share ranges 27.6% (Sol max) to 98.6% (Luna low, 1.5% pass); at low pass rates it approaches 1 by construction. Presenting it as a comparable "inefficiency" measure across configs invites the objection that it's mostly a re-expression of (1 − pass rate).
6. **"Four replicates per task per config"** limits attempt-level precision; the cluster bootstrap covers suite composition but the paper must not imply population coverage (the doc already says this — keep it).

## 4. Confirmatory versus result-informed exploratory

Honestly: **nothing here is confirmatory in the hypothesis-testing sense**, and the paper should say so. The pre-analysis itself admits the leaderboard, mean costs, the `mean_cost / pass_rate` ratio, and "selected example rank inversions" were inspected before freezing — so even RQ1's direction was result-informed. What was genuinely pre-specified (frozen before trial-level computation): the estimand definitions, the decomposition, cohort rules, missing-cost primary+sensitivities, the task-cluster bootstrap (seed 20260714, 10,000 replicates), the failure-charge anchor and multipliers, and the reconciliation gates. Result-informed exploratory (amendment A1, correctly labeled): the Pareto frontier, the reliability-floor curve, and therefore **every claim about which configuration wins at any floor**, including the 65% Luna-vs-Sol pick. The right genre is "descriptive reanalysis with a frozen pipeline," which is publishable and credible — if labeled that way throughout.

## 5. Strongest defensible thesis and title

**Thesis:** Among DeepSWE configurations with statistically comparable frontier solve rates, realized cost per verified completion differs by a factor the paired task bootstrap resolves decisively — GPT-5.6 Sol max costs 2.3–2.9× Luna max per verified success (log ratio CI [−1.063, −0.822], Luna cheaper in all 10,000 replicates) despite a 5.5pp pass-rate edge that may not itself be resolved — and 28–66% of realized cost at frontier pass rates is spend on failed attempts. None of this is visible on a pass-rate leaderboard.

This survives every check in the artifacts: it holds under all three missing-cost sensitivities (both configs have zero imputed rows), and in the failure-charge sensitivity Luna max is rank 1 at both the 1.0× ($6.86) and 2.0× ($10.65) multipliers, i.e., it wins even when failures are charged the anchor's full budget.

**Title:** "The Reliability Tax: Failure-Aware Cost per Verified Completion on DeepSWE v1.1." (The frozen title's "A CPSC Reanalysis of DeepSWE" is fine as a subtitle; avoid anything with "rank inversion" in it.)

## 6. Claims that must be removed or weakened

- **Remove** "pass-rank vs realized-CPSC-rank association is negative" as a finding. Report both panels' correlations with bootstrap CIs and state the association is weak, unresolved, and sign-unstable across panels. If you keep a rank-divergence figure, annotate it as descriptive.
- **Remove** any unconstrained CPSC "winner" language (A1 already commits to this — the summary.json field name `unconstrained_lowest_cpsc_configuration` should not leak into prose as a recommendation).
- **Weaken** the 65%-floor claim to: exploratory, conditional on point-estimate eligibility (Luna max's pass CI straddles 0.65), and valid only on [0.65, 0.70) — at 0.70 the answer is Sol xhigh and the eligible set is 2.
- **Weaken** `probability_a_cheaper = 1.0` to "10,000 of 10,000 replicates."
- **Weaken or matched-task-qualify** all cross-configuration comparisons of `conditional_successful_spend_usd`.
- **Do not present** reliability-tax share as a cross-config efficiency ranking (mechanical dependence on pass rate), and do not imply the tax is recoverable via retries for 0/4 tasks.
- **Confine cross-vendor dollar comparisons** to descriptive tables given un-reconciled price semantics; keep the resolved headline within-provider.

## 7. Additional analyses genuinely needed before writing (ranked by importance ÷ cost)

1. **Bootstrap the reliability-floor policy itself** (highest value, cheap — the sufficient-statistic machinery in `_task_stat_matrix`/`_bootstrap_metrics` already supports it): within each replicate, recompute eligibility and the min-CPSC winner per floor; report selection frequencies, the chosen config's realized CPSC distribution, and P(chosen config truly meets the floor). This converts the weakest figure into a defensible one.
2. **Per-task success heterogeneity / pass@k**: distribution of 0/4, 1–3/4, 4/4 outcomes per configuration, plus CPSC recomputed on the task subset both Luna max and Sol max solve at least once. Directly answers objections 2 and 3. Cheap–moderate.
3. **Bootstrap CIs for Spearman/Kendall in both panels**, plus a within-model vs between-model decomposition of the association. Cheap, and mandatory if any correlation number appears in the abstract.
4. **Infrastructure-exclusion audit**: excluded-row counts per configuration and an exclusions-as-failures worst-case pass rate/CPSC bound. Cheap; closes the doc's own "account for all excluded rows" gate at configuration granularity.
5. **Paired pass-rate difference CI for Luna max vs Sol max** (the paired machinery exists for CPSC only). Determines whether the headline is "same capability, 2.5× cheaper" or "5.5pp premium costs 2.5×." Cheap.
6. **Bootstrap rank distributions for realized CPSC rank** (which of the 41 ranks are actually resolved). Moderate.
7. **Dated price-sheet provenance table** per provider (even with repricing still gated) so the pricing limitation is quantified, not just asserted. Moderate.

## 8. Does this validate CPSC as flagship and support the funding case?

**Partially, and the honest framing is stronger than the triumphant one.** What the exercise proves: the metric framework is portable to an independent public benchmark, computable to exact reconciliation with official aggregates, and adds non-redundant information (a 2.3–2.9× resolved cost gap between statistically comparable frontier configs; tax shares of 28–66% at the frontier). What it also proves — and this is the funding argument, not a liability — is that **unconstrained realized CPSC fails as a decision metric on an uncalibrated benchmark** (it picks a 35%-solve config at $1.66), and the rescue (a reliability floor) had to be bolted on post hoc against noisy point estimates. That is precisely the gap calibrated ShallowSWE reference budgets (Bₜ) and acceptable-reliability protocols claim to fill. The funding brief should say: "We stress-tested the flagship metric externally; it works as a lens and fails as a standalone decision rule in exactly the way the calibrated program predicts and fixes." Hold the pre-analysis line that DeepSWE does not validate ShallowSWE's routine-work construct, budgets, or ROI claims — the doc forbids it and reviewers will check.

## 9. Recommended outline (6–8 pages)

1. **Motivation and claim boundary** (~0.75p): pass-rate leaderboards price nothing; state explicitly what this reanalysis can and cannot show.
2. **Estimands** (~1p): realized CPSC, the exact decomposition CPSC = μˢ + (F/S)·μᶠ, reliability tax, and the retry-cost interpretation with its unsolvable-task caveat.
3. **Data and reproducibility** (~0.75p): hash-pinned artifacts, cohort rules, 126 exclusions with per-config audit, 21 missing costs, exact leaderboard reconciliation as the credibility anchor.
4. **Primary results** (~2p): best-per-model decomposition table (the strongest existing artifact — `best-model-results.csv` is genuinely informative); the paired Luna/Sol result as the headline with pass-difference CI; rank divergence shown descriptively with correlation CIs and the panel sign-flip disclosed.
5. **Exploratory constrained choice** (~1p): reliability-floor curve with the selection bootstrap from item 7.1, clearly labeled per amendment A1.
6. **Sensitivities** (~0.75p): missing cost (a null result — one sentence and a pointer to the table), failure-charge multipliers (Luna max robust at 1× and 2×), exclusions-as-failures bound.
7. **Limitations** (~0.75p): price semantics across providers, task-mix confounding of conditional spend, 4 replicates/task, no cross-benchmark value equivalence.
8. **The calibrated routine-work agenda** (~0.5p): what only ShallowSWE can identify.

**TL;DR:** Publish it, but the paper's spine is the paired, bootstrap-resolved Luna/Sol cost gap plus the decomposition — not the negative correlation (unresolved, sign-unstable, mechanically confounded) and not the 65%-floor pick as currently constructed (post-hoc selection on noisy point estimates at a fragile grid point). Five of the seven needed fixes are cheap reuses of the bootstrap machinery you already built.
