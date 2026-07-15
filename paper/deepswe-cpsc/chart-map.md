# Chart Map and QA Notes

Audience: technical readers evaluating the metric, analysis, and ShallowSWE research case.

Delivery surface: the requested working-paper PDF. The paper overrides the analytical-report
skill's default app or HTML surface; the skill is used for evidence order, section structure, and
chart QA.

| Figure | Report segment | Analytical question | Chart family | Fields | Supported claim |
|---|---|---|---|---|---|
| Rank divergence | Descriptive rank diagnostic | Does capability rank determine economic rank? | Rank-rank scatter with identity line | pass-rate rank, realized-CPSC rank, frontier membership | Rank association is panel-dependent and partly driven by effort scaling. |
| Reliability floor | Decision policy | Which configuration minimizes realized CPSC, and how often does a feasible choice exist? | Two-panel point-policy step curve and 100% stacked bootstrap composition | reliability floor, selected configuration, minimum CPSC, all-replicate selection share, no-eligible share | Reliability changes the point choice, while high-floor feasibility and selection are unstable under task resampling. |
| Invoice versus work frontiers | Price/work separation | Do provider-reported dollars and recorded agent work identify the same efficient configurations? | Two-panel Pareto scatter with log vertical axes | pass rate, realized CPSC, steps per success, frontier flags, all 41 configurations | The dollar frontier spans Luna, Terra, and Sol, while the steps frontier is entirely Sol. Gold and blue encode the two surfaces; direct labels and panel separation preserve grayscale meaning. |
| Failure-cost decomposition | Failure economics | How much of verified-completion cost comes from failed attempts? | Dot plot plus 100% composition bars | realized CPSC, conditional successful spend, reliability-tax share | Failed and successful attempts cost similarly, so realized tax mostly rescales failure rate. |
| Task coverage | Task-mix diagnostic | Do lower-cost configurations solve only a narrower task footprint? | Stacked task-cell counts plus coverage markers | 0/4, 1--3/4, 4/4 cells, task coverage, solved-set overlap | Attempt consistency and any-success task coverage are different goods; outcome-defined strata remain diagnostic only. |

All figures use white backgrounds, charcoal text, restrained blue/gold/orange accents, direct labels,
non-color encodings for frontier membership, explicit units, and source/cohort context. PNG exports
were inspected at their native dimensions. The reliability-floor and task-mix diagnostics are
labeled exploratory because they were added after the first full-data dry run. The reliability
figure separates the fixed point policy from bootstrap reselection and uses an explicit orange
no-eligible segment rather than an interval bar.

## Technical report structure mapping

1. Title: paper title and working-paper status.
2. Technical summary: abstract and opening result paragraph.
3. Key findings with visual evidence: Sections 4 and 5.
4. Scope, data, and metric definitions: Sections 2 and 3.
5. Methodology: Section 3.
6. Limitations, uncertainty, and robustness: Sections 5 and 7.
7. Recommended next steps: Section 6.
8. Further questions: Sections 6.2 and 7.

The research-paper convention places related work before methods and integrates implications into
the results and research-agenda sections. This is a renamed and reordered mapping, not an omission.
