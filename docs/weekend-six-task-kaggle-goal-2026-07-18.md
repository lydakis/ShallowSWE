# Weekend Goal: Complete the ShallowSWE Pipeline on Kaggle

**Planning date:** July 18, 2026
**Owner:** George Lydakis
**Execution status:** planned, not yet authorized
**Primary outcome:** run the current six-task ShallowSWE pipeline end to end on Kaggle and produce
honestly labeled preliminary CPSC results, even if the task set, calibration, or statistical design
is deficient.

## The Goal

This weekend is an execution and product-integration exercise, not a rigor gate.

The run should force every important production path to operate on Kaggle:

1. bundle and snapshot the six tasks;
2. bind model, agent, task, seed, and policy identities;
3. run a real Kaggle canary;
4. collect permissive repair-loop calibration rows;
5. select provisional caps and task budgets;
6. run fresh confirmation on all six tasks;
7. run a fresh small model panel;
8. calculate the three CPSC variants;
9. produce artifacts, diagnostics, and a preliminary analysis; and
10. document Kaggle product issues from actual grant usage.

The pipeline should continue through known research deficiencies. It should stop only for safety,
identity, isolation, accounting, or platform failures that make the output unusable or unsafe.

## Definition of Done

The weekend goal is complete when:

- [ ] A versioned Kaggle shakedown snapshot records the exact tasks, verifiers, environment,
      runner, model routes, agent policy, price basis, and run plan.
- [ ] George completes an owner/author review, supplemented by recorded agent reviews.
- [ ] All six tasks pass basic reference, alternate, and negative-control QA.
- [ ] The 16-trajectory Kaggle canary runs and its quota draw and artifacts are reconciled.
- [ ] The 72-trajectory permissive calibration stage runs on Kaggle.
- [ ] Provisional `K`, step guard, pressure labels, and six task budgets are produced, using declared
      shakedown fallbacks when the evidence cannot identify them.
- [ ] All six tasks receive fresh anchor confirmation attempts.
- [ ] The three frozen fresh candidate models run on all six tasks, with the calibration anchor
      reported alongside them.
- [ ] Reference-budget, realized, and escalation CPSC are generated with sample counts and caveats.
- [ ] A shakedown report distinguishes scored model rows, infrastructure exclusions, pipeline
      defects, calibration failures, and unresolved quantities.
- [ ] A concise update to the Kaggle contact is ready for review.

## What This Is Not

This is not:

- an official report-grade ShallowSWE snapshot;
- proof that the six tasks represent a population of routine engineering work;
- a statistically decisive model ranking;
- an independent human construct review;
- a validated 90% reliability claim;
- evidence that Kaggle and Pier are interchangeable in every respect; or
- permission to pool these rows into a later official release.

Call the output a **six-task Kaggle pipeline shakedown with preliminary CPSC results**.

## Evidence Classes

Keep four evidence sources visibly separate:

1. **DeepSWE reanalysis:** external validation of the economic accounting questions.
2. **864-row preview:** exploratory motivation that exposed saturation, repeated model-task
   failures, and repair-cost tails. It is not a frozen comparison.
3. **Kaggle shakedown:** development evidence that the full ShallowSWE pipeline can operate on
   Kaggle and produce inspectable preliminary results.
4. **Future report-grade run:** separately frozen tasks, calibration, review, sample sizes, and
   statistical policies. Shakedown rows do not silently become this evidence.

Use a dedicated shakedown evidence and release class. Do not label these rows `official_pilot` or
`protocol_validation` merely because Kaggle produced them.

## Known Deficiencies We Accept

The run may proceed when:

- George is the only human reviewer;
- agent reviews supplement but do not make the review independent;
- the task set may saturate;
- category or pressure balance may be weak;
- calibration sample sizes are too small for strong inference;
- the provisional panel may not contain the ideal model families;
- confidence intervals are very wide;
- a 90% eligibility decision rests on small `N`;
- task budgets are selected through a fallback because the pilot data do not identify them; or
- a confirmation task fails its provisional acceptance rule.

Every deficiency must be reported. None is a reason to abandon the pipeline shakedown by itself.

## Non-Negotiable Stop Conditions

Stop the affected launch or the entire run for:

- hidden verifier, solution, credential, or Kaggle input leakage into the agent environment;
- missing or unresolved model identity, silent provider fallback, or collapsed model identities;
- broken conversation or filesystem continuation that changes the intended repair loop;
- corrupted or missing artifacts needed to reconstruct an outcome;
- spend that reaches a declared batch or daily hard stop;
- quota accounting that cannot be reconciled well enough to bound further spend;
- an invalid verifier or environment that makes task outcomes uninterpretable; or
- a systemic Kaggle failure that prevents the pipeline from advancing.

Pre-response 429/503 responses are infrastructure exclusions, not model failures. Preserve the
exact route, error, retry count, timing, and quota effect.

## Review Model

George makes the accountable accept, revise, or reject decision for every task. Agent reviews are
structured second opinions that challenge:

- realism and ordinary frequency;
- delegation plausibility;
- ambiguity and hidden assumptions;
- category and horizon fit;
- verifier alignment and implementation flexibility;
- expected engineer effort;
- specialized knowledge; and
- contamination risk.

Preserve material agent findings and George's disposition of them. The review artifact should
distinguish:

- `owner_decision`;
- `agent_findings`; and
- `owner_disposition_of_agent_findings`.

Do not claim independent human review. A later report-grade run may require it.

## Shakedown Run Plan

### Stage 0: Snapshot and basic QA

Create a reproducible shakedown snapshot without implying methodological finality.

Record:

- six task and verifier hashes;
- environment identities;
- runner and agent-policy identity;
- requested and expected resolved model routes;
- a dated price basis;
- temporary permissive limits;
- seed allocation;
- review artifacts; and
- batch and daily cost stops.

Basic QA remains required because a broken task cannot test the pipeline:

- reference solution passes repeatedly;
- alternate valid solution passes;
- negative controls fail for the intended reason;
- verifier feedback is sanitized; and
- the agent cannot access hidden tests, solutions, credentials, or network resources.

The snapshot may retain known construct and calibration deficiencies in a visible issue ledger.

### Stage 1: Kaggle canary

Run the existing four canary units:

| Role and mode | Tasks | Replicates | Trajectories |
|---|---:|---:|---:|
| Primary anchor, one-shot | 2 | 2 | 4 |
| Primary anchor, permissive repair loop | 2 | 2 | 4 |
| Low floor, permissive repair loop | 2 | 2 | 4 |
| Stronger floor, permissive repair loop | 2 | 2 | 4 |
| **Total** |  |  | **16** |

The canary tests:

- the grant-backed quota in practice;
- requested and resolved model identity;
- conversation and workspace continuation;
- hidden-verifier isolation;
- event-level usage and cost capture;
- canonical versus Kaggle-reported spend;
- artifact download and normalization; and
- exclusion and retry behavior.

**Expected draw:** about $9 high estimate.
**Canary batch hard stop:** $25.

If a research signal is poor but the infrastructure is sound, continue. If the infrastructure is
unsafe or the evidence cannot be reconstructed, stop and fix it.

### Stage 2: Permissive six-task calibration

Run the existing 72-trajectory calibration shape on Kaggle:

- primary anchor: 6 repair loops per task;
- low floor: 3 repair loops per task;
- stronger floor: 3 repair loops per task; and
- 6 tasks total.

Use the temporary permissive envelope:

- up to 16 verifier submissions;
- up to 256 agent steps;
- up to $5 per trajectory;
- an infrastructure wall-time guard; and
- undisclosed caps.

Record every agent submission and verifier result with cumulative steps, token counters, reported
spend, canonical spend when available, and stop cause.

Saturation, lack of pressure separation, and excessive tails become findings. They do not stop the
shakedown unless they reveal a task or infrastructure defect.

### Stage 3: Provisional policy selection

Run the real Stage 4 machinery over the permissive rows. Select:

- verifier-submission cap `K`;
- pooled agent-step guard;
- provisional task budgets `B_t`;
- two-band and three-band pressure diagnostics; and
- tasks requiring special caveats.

Use deterministic shakedown fallbacks when the evidence does not identify a value:

| Failure to identify | Shakedown fallback | Required label |
|---|---|---|
| No candidate `K` captures the target share | Maximum candidate `K` | `selection_target_unmet` |
| No candidate step guard captures the target share | Maximum candidate step guard | `selection_target_unmet` |
| No budget band meets proposal coverage | Maximum budget band | `budget_not_identified` |
| Development check still misses after one band bump | Keep the bumped or maximum band | `development_check_failed` |
| No useful pressure separation | Keep task in an undifferentiated band | `pressure_not_identified` |

Fallbacks exist only so every later pipeline stage can execute. They are not valid calibrated
quantities for a report-grade benchmark.

### Stage 4: Fresh confirmation on all six tasks

Run 8 fresh primary-anchor repair loops per task under the provisional selected policy:

- 6 tasks;
- 8 trajectories per task;
- 48 trajectories total; and
- fresh seed namespace with no reuse from permissive calibration.

Report whether each task achieves at least 7/8 successes within its provisional policy and budget.
Do not raise the budget after confirmation begins.

For the shakedown, a miss does not stop the pipeline. Mark the task `confirmation_failed`, preserve
its observed replacement-cost evidence, and continue into preliminary scoring with that caveat.

### Stage 5: Fresh preliminary CPSC panel

The panel is frozen from the intersection of models listed by Kaggle on July 18, 2026 and exact
model configurations that produced distinct behavior in the 864-row preview.

The previous pilot used GPT-5.5 high because the July 11 Kaggle inventory did not expose GPT-5.6
Sol. That constraint no longer holds. Use **GPT-5.6 Sol high** as the shakedown calibration anchor.
It is a current frontier reference available in the live Kaggle catalog, and the DeepSWE analysis
found Sol high materially cheaper and lighter than Sol max without a resolved solve-rate advantage
for max. Do not retain GPT-5.5 merely to avoid regenerating the pilot identities.

Report the fresh GPT-5.6 Sol high calibration anchor alongside three fresh candidate rows:

| Panel role | Kaggle slug | Preview configuration | Preview reason for selection |
|---|---|---|---|
| Calibration anchor | `gpt-5.6-sol` | Sol high; supported by DeepSWE rather than the low-effort preview row | Current practical frontier reference and replacement-cost anchor. |
| Cheap frontier | `gpt-5.6-luna` | GPT-5.6 Luna low | 53/54 eventual, 52/54 first-check, about $0.020 mean row cost, and 6.3 mean turns. |
| Clean stronger baseline | `gpt-5.6-sol` | GPT-5.6 Sol low | 54/54 eventual and first-check, about $0.151 mean row cost, and 6.8 mean turns. |
| Repair-heavy cost tail | `gemini-3.5-flash` | Gemini 3.5 Flash medium | 54/54 eventual but 49/54 first-check, about $0.309 mean row cost, 24.9 mean turns, and a $1.33 p95 row cost. |

This is deliberately not a prestige leaderboard. Luna and Sol provide a controlled same-generation
price and behavior contrast. Sol high versus Sol low adds a controlled same-model effort contrast.
Gemini exercises a materially different repair and cost profile. The Sol high anchor connects the
panel to task-budget and replacement-cost calibration.

The resulting four-configuration result surface is intentionally OpenAI-heavy: Sol high, Sol low,
and Luna low, plus Gemini 3.5 Flash medium. That is acceptable for this shakedown because the goal
is interpretable signal and complete pipeline execution, not provider representation. The strongest
comparisons are the within-GPT-5.6 effort and family contrasts. Treat the Gemini comparison as a
cross-provider descriptive invoice and repair surface because provider pricing, cache semantics,
and token accounting may not be harmonized.

Do not describe this panel as representative of the model market. A later report-grade panel should
add independently selected Anthropic and open-weight configurations if exact supported versions and
stable Kaggle routes are available.

Kimi K3 and Inkling supplied the clearest exploratory repair anecdotes, but neither appears in the
live Kaggle catalog. Claude Fable 5, Claude Sonnet 5, GLM-5.2, Grok 4.5, and Kimi K2.7 Code also
lack exact catalog matches. Do not replace them with a nearby family or version and describe it as
the preview model.

Predeclare `gpt-5.6-terra` low as the single shakedown backup. Its preview row was 53/54 eventual,
51/54 first-check, and about $0.079 mean row cost. Use it only after a primary candidate repeatedly
fails before its first response for infrastructure reasons. A substitution creates a new panel
version and is disclosed; it is not silent route fallback.

Run `N=3` fresh repair-loop seeds per task and model configuration:

- 3 fresh candidate models;
- 6 tasks;
- 3 seeds;
- 54 trajectories total.

`N=3` is intentionally a pipeline-shakedown sample. It produces inspectable preliminary metrics,
not reliable ranking precision. The 48 fresh GPT-5.6 Sol high confirmations supply the separately
labeled anchor baseline. If only two candidate routes are usable and the predeclared Terra backup
is also unavailable, run 36 candidate trajectories and report the missing configuration as an
infrastructure exclusion. Do not silently substitute a different canonical model.

Preflight the `gpt-5.6-sol` high reasoning configuration before snapshot generation. If Kaggle
rejects the effort control while the Sol route itself works, create a new shakedown snapshot using
the strongest explicitly supported Sol effort or default configuration. Do not fall back to
GPT-5.5 without revisiting and recording the anchor decision.

Do not extend to `N=20` this weekend. The extension rule and higher-`N` run belong to the later
rigorous phase.

### Stage 6: Generate preliminary results

For every task and model configuration, report:

- attempted, scored, successful, failed, and infrastructure-excluded rows;
- first-submit and eventual success;
- verifier submissions, steps, turns, tokens, context, latency, and cap hits;
- actual and canonical spend;
- provisional `B_t` and confirmation status;
- reference-budget CPSC;
- realized CPSC;
- escalation CPSC when `R_t` is estimable;
- zero-success cells as `no verified successes`; and
- all known evidence and identifiability limitations.

Aggregate across the declared six-task basket, but show task contributions so a single saturated or
failed task cannot disappear inside the headline.

The analysis should answer:

1. Did every pipeline stage work on Kaggle?
2. Which Kaggle product behaviors caused friction or exclusions?
3. Did repair accounting expose differences hidden by eventual success?
4. Which calibration quantities were identified, forced by fallback, or left unavailable?
5. What would need to change before a rigorous run?

## Budget and Scheduling

Confirmed Kaggle allocation:

- $200 per day;
- $1,000 per month; and
- visible and validated on George's profile, not yet exercised through this full pipeline.

Planning envelope:

| Stage | Trajectories | Current high estimate or planning reserve |
|---|---:|---:|
| Canary | 16 | $25 hard stop |
| Permissive calibration | 72 | $50 planning reserve |
| All-task confirmation | 48 | $50 planning reserve |
| Fresh `N=3` panel | 54 | $50 planning reserve |
| Retry and infrastructure reserve | conditional | $25 |
| **Shakedown cumulative hard stop** | **190 before retries** | **$200** |

Use the existing $160 daily soft limit and $200 daily hard limit. Split the run across at least two
launch days even if the expected draw is lower. Re-estimate after each stage from actual Kaggle
costs and quota behavior.

The $5 trajectory cap does not imply a $50 panel maximum. Batch-level stops remain authoritative.

## Weekend Sequence

### Before execution authorization

- [ ] Review this plan and settle the evidence label and fallback rules.
- [x] Freeze the exact catalog-overlap panel: GPT-5.6 Sol high anchor, GPT-5.6 Luna low, GPT-5.6
      Sol low, and Gemini 3.5 Flash medium, with GPT-5.6 Terra low as the disclosed backup.
- [ ] Run a no- or minimal-spend capacity and identity preflight for every frozen route immediately
      before execution; catalog listing alone does not prove live capacity.
- [ ] Decide whether all six current tasks remain in the shakedown regardless of saturation.
- [ ] Approve the $200 cumulative and daily hard stop.

### Execution day 1

- [ ] Produce the shakedown snapshot and issue ledger.
- [ ] Complete owner review with agent second opinions.
- [ ] Run basic QA.
- [ ] Build and inspect the Kaggle bundle.
- [ ] Run and reconcile the 16-trajectory canary.
- [ ] Stop for non-negotiable safety or accounting failures only.
- [ ] Run the 72-trajectory permissive calibration if the canary infrastructure is sound.

### Execution day 2

- [ ] Select provisional policy and budgets, applying declared fallbacks when necessary.
- [ ] Run 48 fresh all-task confirmation trajectories.
- [ ] Run the fresh 36- or 54-trajectory small panel.
- [ ] Generate CPSC outputs and the issue ledger.
- [ ] Write the preliminary analysis and Kaggle contact update.

## Kaggle Contact Update

The update should lead with execution, not rigor:

> I have now exercised the ShallowSWE grant through a complete six-task Kaggle pipeline shakedown,
> from hidden-verifier repair loops through calibration, fresh confirmation, and preliminary CPSC
> aggregation. The study is intentionally early and the task calibration is not yet report-grade,
> but it produced [row count] trajectories, [key preliminary observation], and a concrete list of
> Kaggle product findings. I am using this run to harden the methodology before a larger frozen
> study and would value your feedback on the execution and artifact model.

Attach or link:

- one page of preliminary findings;
- the DeepSWE economic paper as methodological context;
- a concise Kaggle issue list; and
- the exact next-step projection based on observed costs.

Do not call the output a benchmark release. Do not present the 864-row preview as proof. Do not ask
for more funding before the current grant has produced this concrete evidence.

## After the Shakedown

Use the completed pipeline to decide whether to:

- revise saturated or unrealistic tasks;
- recruit an independent human reviewer;
- change the floor panel;
- strengthen model-route parity checks;
- freeze the `N=10` to `N=20` extension policy;
- rerun task admission and calibration at report-grade sample sizes; or
- request access to a higher-throughput or Harbor-based execution path with a measured workload and
  product issue list.

The shakedown succeeds by completing the real pipeline and making its deficiencies visible. It does
not need to resolve those deficiencies during the same weekend.
