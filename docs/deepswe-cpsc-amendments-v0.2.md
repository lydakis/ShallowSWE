# DeepSWE CPSC v0.2 Amendment Supplement

Date: 2026-07-14

This supplement extends, but does not overwrite, the historical A1--A3 specification in
`docs/deepswe-cpsc-preanalysis.md` and machine-readable plan in
`configs/deepswe-cpsc-v0.1.json`. Those files are preserved byte-for-byte as supplied to the
first GPT-5.6 Pro review. The executable amended plan is
`configs/deepswe-cpsc-v0.2.json`.

All additions below were requested after inspection of earlier results. They are exploratory and
must not be described as preregistered or confirmatory.

## A4: Workload weighting and noncircular panel-solvedness

Added: 2026-07-14 11:07 EDT

Trigger: GPT-5.6 Pro observed that pooled observed-attempt CPSC weights tasks in proportion to the
number of surviving scored attempts, while the target methodology declares workload weights. The
same review also noted that full-panel solvedness strata let a target family's own outcomes help
define the strata used to analyze it.

The pooled observed-attempt invoice ratio remains

\[
\widehat{\mathrm{CPSC}}^{\mathrm{pooled}}_m
=\frac{\sum_{t,i} C_{mti}}{\sum_{t,i}Y_{mti}}.
\]

The equal-task sensitivity is

\[
\widehat{\Theta}^{\mathrm{equal\ task}}_m
=\frac{T^{-1}\sum_t \overline C_{mt}}
       {T^{-1}\sum_t \overline Y_{mt}},
\]

where each task receives equal weight and each task-level bar averages surviving scored attempts.
This is a ratio of task-weighted expectations, not an average of task-level CPSC values. The
analysis reports the 113-task basket for configurations observed on every task and a common
111-task basket for all configurations.

The task-balanced bootstrap samples 113 task IDs with replacement. Within each sampled task it
reuses all surviving scored attempts, recomputes the task-level means, then recomputes the
equal-task ratio, reliability eligibility, and selected configuration. Configurations lacking any
task in the declared 113-task basket are excluded from that basket before resampling.

Outcome-derived rare, contested, and common groups are renamed panel-solvedness strata. The primary
GPT-5.6 mechanism diagnostic assigns strata using only the 26 non-GPT-5.6 configurations, then
evaluates every Luna, Sol, and Terra configuration on the same labels. Leave-one-family-out labels
are exported for all other family-level diagnostics.

The lower-bound eligibility policy is a fixed-sample exploratory rule. For each configuration,
compute the 2.5th percentile of its pass rate across the primary task-cluster bootstrap once. At
floor \(r\), retain configurations whose fixed lower bound is at least \(r\), then choose the
minimum point-estimate CPSC among them. The bound and winner are not recomputed inside another
bootstrap.

Retrospective failure charges are renamed proxy charges throughout. They are not calibrated
reference budgets.

## A5: Effort-tuned comparison and reliability-figure revision

Added: 2026-07-14 12:37 EDT

Trigger: Fable noted that Sol max is itself an overprovisioned comparison and requested the paired
Luna-max versus Sol-high contrast. GPT-5.6 Pro requested a formal reliability-policy definition,
all-replicate and conditional selection shares, a simpler figure, and stricter resource-field
language.

The analysis adds:

- the paired Luna-max versus Sol-high solve-rate and log-CPSC contrast under the same 10,000
  task-cluster bootstrap replicates;
- accumulated agent seconds and trial seconds divided by verified successes, with paired
  task-bootstrap ratios;
- an explicit missing-resource rule: if any scored row for a configuration lacks a resource field,
  that configuration-resource total is unidentified and is excluded from that resource's rank,
  pairwise ratio, and frontier; and
- both selection share over all 10,000 replicates and selection share conditional on a nonempty
  feasible set.

Figure 2 is split into two panels. Panel A shows only the observed point-estimate policy curve.
Panel B shows bootstrap selection composition at the 65%, 70%, and 75% floors, including an
explicit no-eligible category. The fixed lower-bound policy remains available in the generated
table and is described in the methods, but is removed from the main figure.

The paper also removes task coverage from the abstract, changes the group-out conclusion from
"rejects" to "does not support," renames generic token totals as sums of reported token counters,
and states the asymmetric Sol result directly: max effort's cost premium is resolved, while its
solve-rate gain is not.

## Deferred nonblocking checks

A repository-cluster bootstrap was suggested because 113 tasks span 91 repositories. It is not
part of v0.2 and remains a future robustness check. A public repository URL, release tag, and exact
implementation commit must be added before public circulation; the current analysis files are
uncommitted, so no truthful commit identifier exists yet.
