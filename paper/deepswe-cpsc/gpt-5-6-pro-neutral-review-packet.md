# DeepSWE economic-lens review packet

Please review this analysis independently. Do not try to rescue or reject a planned paper, and do
not assume the analysis must contain a novel positive result.

## Research question

What happens when a failure-aware economic lens is applied to the DeepSWE v1.1 coding-agent
trials? What does realized cost per successful completion (CPSC), together with tokens and agent
steps per success, reveal beyond the capability leaderboard?

## Data and analysis scope

- 18,396 scored attempts from 41 model-effort configurations
- 13 base model families, 113 original software-engineering tasks
- Five provider routes: OpenAI, Anthropic, Vertex AI, Z.ai, and OpenRouter
- Nominally four attempts per configuration-task cell
- 10,000 paired task-cluster bootstrap replicates, seed 20260714
- 126 infrastructure rows excluded and audited; 21 missing costs imputed within configuration
- All official aggregate pass rates and costs reconcile

The attached executed notebook contains the calculations and outputs. The attached CSVs contain
configuration-level results, the fixed family display panel, and all paired bootstrap comparisons.

## Descriptive observations to verify or challenge

1. Realized CPSC equals mean attempt cost divided by pass rate to machine precision. Aggregate CPSC
   and its rank are therefore recoverable from DeepSWE's leaderboard aggregates.
2. Failed and successful attempts have similar mean spend. The failed-to-successful attempt-spend
   ratio ranges from 0.72 to 1.23 with median 1.02. Reliability-tax share consequently correlates
   0.995 with failure rate.
3. The reported-dollar CPSC frontier contains nine GPT-5.6 configurations from the Luna, Terra,
   and Sol variants. Within each multi-family provider route, one family supplies its full CPSC
   frontier: Opus 4.8 on Anthropic, Fable 5 on Vertex, and GPT-5.6 variants on OpenAI.
4. The price-free point frontiers differ. The frontiers for agent steps, output tokens, and input
   tokens per verified success contain only GPT-5.6 Sol configurations.
5. Luna max has 0.391 times Sol max's reported-dollar CPSC, but paired task-bootstrap ratios show
   1.80 times the agent steps [1.62, 1.99], 1.32 times the output tokens [1.20, 1.46], and 2.11
   times the input tokens [1.87, 2.38] per verified success.
6. Terra max has 0.616 times Sol max's reported-dollar CPSC but 1.29 times the steps [1.19, 1.41],
   1.25 times the output tokens [1.16, 1.35], and 1.22 times the input tokens [1.11, 1.35].
7. Sol high and Sol xhigh have solve-rate differences from Sol max whose paired 95% intervals
   contain zero. Both are cheaper in reported dollars and use fewer steps, output tokens, and input
   tokens per success. Every paired ratio interval is below one.
8. Seven configurations have paired solve-rate differences from Sol max whose intervals contain
   zero: Luna max, Terra max, Sol high, Sol xhigh, and Fable high, xhigh, and max. Their reported
   CPSC ranges from $4.51 to $31.03, with strongly resolved cost differences.
9. Exact minimum-CPSC selection becomes unstable at high reliability floors. At a 70% floor, the
   point winner is reselected in 16% of task-bootstrap replicates; at 75%, 67% of replicates have
   no eligible configuration.
10. Post-hoc difficulty strata produce different CPSC minima: Terra medium on common tasks, Luna
    high on contested tasks, and Luna max on rare tasks. These strata use full-panel outcomes and
    are unavailable before evaluation.

## Candidate case study: Luna max versus Sol max

The researcher considers this comparison independently interesting and does not want it lost when
the analysis broadens to the full panel. Evaluate its best role without treating it as the only
result:

- Sol max has a 72.7% attempt solve rate and Luna max 67.2%. The paired difference is -5.5
  percentage points with interval [-12.1, +1.1], so the difference is unresolved.
- Luna's realized CPSC is $4.51 versus Sol's $11.54. The paired ratio is 0.391 [0.345, 0.439], and
  Luna is cheaper in all 10,000 task-bootstrap replicates.
- Luna solves 102 of 113 tasks at least once versus Sol's 97. Their solved-task Jaccard overlap is
  0.860. On the 92 tasks both solve, Luna's CPSC remains $3.88 versus Sol's $9.72, while Sol has the
  higher matched-task attempt solve rate, 85.8% versus 77.2%.
- Luna retains lower realized CPSC in rare, contested, and common task strata. On the 17 rare tasks,
  Luna's point solve rate is 36.8% versus Sol's 25.0%.
- On the 97-task Sol-success basket, Sol-derived pseudo-failure charges of 0.5x, 1x, and 2x produce
  Luna/Sol CPSC values of $4.45/$9.09, $5.90/$9.83, and $8.79/$11.30. These are post-hoc proxy
  budgets, not calibrated failure values.
- The resource comparison reverses the dollar result: Luna uses more steps and tokens per success
  than Sol max. This means the Luna result is a reported-price advantage rather than a lower-work
  advantage.

## Required caveats

- Provider-reported dollars are not common-price-reconciled. Cross-provider dollar results may
  reflect pricing as well as model behavior.
- Input and output token semantics may differ across providers. Agent steps are more comparable
  because every configuration uses the same harness.
- Realized CPSC is benchmark spend per verified success under DeepSWE's fixed observed attempt
  policy. It is not a deployable retry-until-success estimate.
- A paired interval containing zero means the difference is unresolved, not that configurations
  are equivalent.
- Reliability floors, task-difficulty strata, and some failure-price analyses are result-informed
  exploratory additions.

## Questions

1. What are the most important patterns across the complete model-family and provider panel?
2. Which observations are arithmetic restatements, and which genuinely require trial-level data?
3. How should the reversal between reported-dollar CPSC and step or token intensity be interpreted?
4. Which findings are broad across providers and model families, and which are narrow GPT-5.6
   phenomena?
5. What is the strongest defensible interpretation and best editorial role for the Luna max versus
   Sol max case study within the broader panel?
6. Do the data support a coherent short descriptive paper? If yes, state the research question and
   central empirical answer without manufacturing novelty. If not, say so directly.
