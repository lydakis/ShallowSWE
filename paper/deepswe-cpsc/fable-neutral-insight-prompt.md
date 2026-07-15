# Neutral DeepSWE economic-lens review

You are reviewing a descriptive analysis, not an existing paper thesis. Do not try to rescue the
paper, kill the paper, or manufacture novelty. The researcher's question is simply:

> What happens when the failure-aware economic lens developed for ShallowSWE is applied to the
> DeepSWE v1.1 trial data? What, if anything, does CPSC reveal about the data?

Read these sources:

1. `paper/deepswe-cpsc/insight-audit.ipynb`
2. `paper/deepswe-cpsc/generated/tables/configuration-results.csv`
3. `paper/deepswe-cpsc/generated/tables/best-model-results.csv`
4. `paper/deepswe-cpsc/generated/tables/paired-comparisons.csv`
5. `paper/deepswe-cpsc/generated/tables/bootstrap-intervals.csv`
6. `paper/deepswe-cpsc/generated/tables/task-difficulty-strata.csv`
7. `paper/deepswe-cpsc/generated/tables/reliability-floor.csv`
8. `paper/deepswe-cpsc/generated/tables/reliability-floor-bootstrap.csv`
9. `paper/deepswe-cpsc/generated/tables/failure-charge-sensitivity.csv`
10. `paper/deepswe-cpsc/generated/tables/infrastructure-exclusion-audit.csv`
11. `docs/deepswe-cpsc-preanalysis.md`
12. `configs/deepswe-cpsc-v0.1.json`

Do not read `paper/deepswe-cpsc/main.tex` or any previous Fable review. Those contain candidate
narratives that could anchor your answer.

Give an impartial empirical read in five parts:

1. What are the principal patterns in the full 41-configuration, 13-family data, including
   OpenAI, Anthropic, Vertex, Z.ai, and OpenRouter routes?
2. Which observations are merely arithmetic restatements of pass rate and mean attempt cost, and
   which observations require the trial-level failure, task, or uncertainty data?
3. Which patterns are broad across providers or model families, and which are narrow GPT-5.6 or
   Luna/Sol phenomena?
4. Which apparent findings weaken or disappear under task resampling, infrastructure-as-failure,
   task-difficulty, reliability-floor, or failure-price checks?
5. After observing the results, is there a coherent empirical question worth a short descriptive
   paper? If yes, state it without forcing a headline result. If no, say so directly and explain
   what additional analysis or data would be required.

Keep claims precise. Unresolved difference is not equivalence. Provider-reported dollars are not
common-price-reconciled. Realized CPSC is benchmark spend divided by verified successes under the
observed attempt policy, not a deployable retry-until-success estimate.
