# ShallowSWE Six-Task Protocol-Validation Pilot

**Version:** v0.3 freeze candidate
**Date:** 11 July 2026
**Methodology basis:** ShallowSWE white-paper freeze candidate v0.4.2
**Claim tier:** Protocol validation only; no global leaderboard claim

## Executive decision

Run a six-task calibration pilot, two tasks per category, in a cash-preserving sequence. Use Codex Pro for development, task debugging, and non-report-grade triage; use Kaggle funding for the official metered evidence; keep OpenRouter outside the critical path and cap out-of-pocket use at **$25** unless a separate approval is made.

The core pilot is designed to fit inside **$200 of Kaggle grant draw**, with a further **$100 Kaggle contingency** held for targeted extensions. The expected base-case official metered cost is about **$43**, with a conservative high case around **$63**. The core and reserve together commit no more than 30% of the current $1,000 monthly Kaggle allocation, and every execution day remains subject to the separate $160 soft and $200 hard launch limits.

The pilot is successful when it produces auditable answers to six questions:

1. Can six routine tasks pass the construct and executed verifier-quality gates?
2. Do first-submit outcomes exhibit useful floor-panel spread across these six tasks?
3. What undisclosed verifier-submission cap `K` captures nearly all legitimate under-budget repair success?
4. What pooled agent-step guard is safely nonbinding for ordinary trajectories?
5. Can the budget-selection and fresh-confirmation machinery be exercised on one preregistered task per category?
6. What does the complete four-phase calibration actually cost in canonical value, Kaggle grant draw, Codex subscription use, and out-of-pocket cash?

## 1. Objectives and non-objectives

### 1.1 Objectives

The pilot validates the machinery needed for a future report-grade snapshot:

- naturalistic, same-context bounded repair loops;
- construct and verifier-quality gates before calibration;
- immutable model and agent-policy identity;
- permissive collection followed by retrospective cap analysis;
- coverage-based task-budget selection;
- targeted fresh anchor confirmation and estimation of `R_t` on a preregistered subset;
- separation of reference-budget, realized, and escalation CPSC;
- reproducible resource accounting across cash, grant, and subscription pools.

### 1.2 Non-objectives

The pilot does **not**:

- publish a global model leaderboard;
- claim that six tasks represent routine software work broadly;
- certify a 90% production reliability level;
- execute the full secondary-anchor or common-price sensitivity suite;
- use OpenRouter spend merely to increase model count;
- silently convert Codex subscription trajectories into report-grade evidence when provider identity, usage accounting, or scaffold equivalence is incomplete.
- satisfy report-grade task admission, budget selection, or task-wide confirmation requirements for v1.

## 2. Funding strategy

### 2.1 Funding hierarchy

Use resources in this order:

1. **Local execution and Codex Pro:** task authoring, verifier debugging, no-op/reference checks, transcript inspection, candidate triage, and development-only OpenAI runs.
2. **Kaggle grant:** official metered calibration evidence, fresh confirmation, and narrowly targeted extensions. This is the default pool for any row intended to support the pilot report.
3. **OpenRouter out of pocket:** only for an optional external-model comparator or a provider-routing accounting check after the core pilot succeeds.

This ordering minimizes cash while preserving a clean evidentiary boundary. Canonical list-price-equivalent cost is still reconstructed for every usable trajectory, even when cash outlay is zero or grant-funded.

### 2.2 Pilot funding envelope

| Pool | Available | Pilot allocation | Hard operating rule |
|---|---:|---:|---|
| Codex Pro | Subscription quota | Development use; no incremental-cash budget | Treat as in-kind. Do not call it official evidence unless the exact frozen harness, identity, and usage contract are satisfied. |
| Kaggle | $200/day, $1,000/month | $200 core + $100 targeted-extension reserve | Stop new launches at $160 projected daily draw; retain 20% daily headroom for indivisible-call and retry variance. |
| OpenRouter | Personal cash | $25 optional extension | $0 in the critical path. Every batch needs a preflight and explicit approval. |

At least **$700 of the Kaggle monthly allocation remains uncommitted** after the core and contingency reservations. That holdback is more valuable than broadening the pilot prematurely: it can fund a fresh rerun, a small report-grade precursor, or serve as evidence of disciplined grant stewardship in a request for additional funding.

### 2.3 Runner and evidence contract

| Surface | Pilot role | Evidence class |
|---|---|---|
| Local deterministic execution | Reference, alternate, negative-control, isolation, and schema checks | Task QA and harness conformance only |
| Codex Pro | Prompt, verifier, continuation, and accounting triage | Development only; never laundered into official pilot evidence |
| Kaggle | Frozen canary, permissive collection, and targeted fresh confirmation | Canonical official metered pilot evidence |
| Pier/Harbor | Portability, local reproduction, and backend parity | Separate runner evidence; never pooled with Kaggle unless the immutable policy and transport identity are exactly equal |
| OpenRouter | Optional preregistered external comparator | Separate optional evidence with a $25 personal-cash cap |

Every row records its runner and evidence class. Backend adapters share the repair-loop contract, but backend equality is not assumed.

## 3. Pilot task set

The six tasks are provisional until construct review and executed quality evidence are complete. Their existing labels are task-selection hints, not final pressure assignments.

These public small original repositories are protocol-validation fixtures. They do not replace the private held-out corpus of real transcript-mined repository work and are not automatically promoted into the later report-grade suite.

| Category | Lower-pressure hypothesis | Elevated-pressure hypothesis | Canary |
|---|---|---|---|
| Artifact | `env-flags-to-json` | `access-log-to-incidents` | `env-flags-to-json` |
| Code | `invoice-cli-regression-test-fix` | `invoice-multi-source-merge` | `invoice-multi-source-merge` |
| Workflow | `config-flag-ignored` | `merge-divergent-config-branches` | - |

`invoice-multi-source-merge` replaces both the earlier cache-invalidation proposal and the
subsequent status-parity candidate. Adversarial review showed that deleting caching entirely could
pass the first task, while the status task saturated at 9/9 in prior floor evidence. The selected
replacement has a legitimate audited miss, 0/2 historical floor passes, and 1/1 historical ceiling
pass. Its elevated-pressure label remains a hypothesis for the Stage 3 diagnostics rather than a guaranteed band.

Each task must satisfy, before official model runs:

- one qualified construct reviewer who is not the task author;
- reference solution passes and untouched base fails;
- materially different valid solution passes where required;
- requirement-to-verifier map is executed, not merely declared;
- negative controls fail;
- hidden feedback remains coarse and non-oracle;
- task and verifier hashes are frozen.

A model-informed semantic change creates a new task version and restarts review. A task is not enlarged merely to force floor failure.

## 4. Provisional model roles

Requested model configurations, provider routes, sampling settings, and agent-policy identities freeze in the pilot manifest before the two-task canary. The canary validates resolved identities and accounting. Any mismatch invalidates the affected rows and requires a versioned manifest before rerun.

### 4.1 Primary anchor

Use the strongest stable OpenAI configuration available through the intended official route. The
2026-07-11 Kaggle model inventory does not expose the provisional GPT-5.6 Sol route, so the frozen
pilot anchor is **`gpt-5.5-2026-04-23` at high reasoning effort**. The canary must confirm that the
resolved model matches this requested slug. The choice is recorded as an immutable
`model_config_id` and `agent_policy_id`; a marketing model label is insufficient.

### 4.2 Floor panel

Use two OpenAI configurations available without out-of-pocket API spend:

- a low-cost floor, **`gpt-5.4-mini-2026-03-17` at low effort**;
- a stronger rung, **`gpt-5.4-2026-03-05` at low effort**.

GPT-5.6 Luna remains a future candidate but is not silently aliased into this pilot because Kaggle
does not currently list it. Any later substitution requires a protocol-version and immutable-ID
change before launch.

The floor panel exists to measure empirical pressure, not to maximize provider diversity. A third non-OpenAI floor row is optional and should be purchased only when the two OpenAI floor rows produce an ambiguous pressure assignment or when a small provider-diversity result materially improves the funding case.

### 4.3 Optional external comparator

After the core pilot passes its gates, run one externally routed configuration on at most six tasks and three replicates per task. Select the row before seeing the core ranking. The entire extension is capped at $25 personal cash and is excluded from the critical-path success criteria.

## 5. Execution sequence

### Stage 0 - freeze and local QA

**Funding:** local compute, $0 metered model cash.
**Outputs:** six reviewed task packets, executed quality evidence, immutable task/verifier/environment hashes, frozen canary manifest.

Do not start official model spend until all six tasks are locally runnable and at least the two canary tasks have complete executed quality evidence.

### Stage 1 - Codex development triage

**Funding:** Codex Pro subscription.
**Evidence class:** development only unless exact official equivalence is proven.

Recommended development allowance:

- anchor one-shot: 2 replicates per task;
- two floor rows one-shot: 3 replicates per task and row;
- one repair-loop smoke per task and model role.

This is 66 model trajectories. Stop earlier when a prompt, verifier, resume, identity, or accounting defect appears. Use Codex to make mistakes cheaply; do not spend Kaggle funds discovering basic packaging problems.

### Stage 2 - two-task Kaggle canary

**Funding:** Kaggle.
**Tasks:** `env-flags-to-json` and `invoice-multi-source-merge`.
**Projected reserve:** $20; target draw below $10.

Run:

- primary anchor one-shot, 2 replicates per task;
- primary anchor permissive repair loop, 2 replicates per task;
- both floor rows permissive repair loop, 2 replicates per task and row.

The canary verifies official routing, provider identity, recursive usage accounting, cache fields, transcript continuation, verifier isolation, canonical-vs-reported cost reconciliation, and actual cost per trajectory.

**Stop immediately** if any of the following occurs:

- provider or resolved-model identity is missing;
- model configurations collapse to the same aggregate identity;
- canonical and metered costs differ beyond the provisional reconciliation tolerance;
- continuation does not preserve conversation and filesystem state;
- verifier output leaks hidden assertions;
- projected six-task high-case cost exceeds $200 before contingency.

### Stage 3 - Phase 1 permissive collection

**Funding:** Kaggle.
**Sample:** 6 primary-anchor repair loops per task and 3 repair loops per task for each floor row.
**Trajectories:** 72.

Use generous temporary limits, provisionally:

- verifier submissions: 16;
- agent steps: 256;
- safety dollars: $5;
- generous wall time as infrastructure guard.

No limit is disclosed to the agent. Record cumulative spend, submissions, steps, first successful verification, and stop cause after every model call and verification event.

Candidate retrospective policies:

- `K`: 2, 4, 6, 8, 12;
- agent steps: 32, 64, 128;
- budget bands: $0.02, $0.05, $0.10, $0.20, $0.50, $1.00, $2.00.

The pilot reports whether the data support a global `K`, whether step guards can remain pooled and nonbinding, and whether the budget-band schedule has useful resolution.

For each task, the six anchor trajectories are preregistered as four proposal trajectories and two development-check trajectories. This split is intentionally coarse and cannot establish a report-grade coverage constant. The pilot reports full six-run development coverage under every candidate band, uses the 4+2 split only to exercise the one-band-bump rule, and treats fresh 7/8 confirmation as the load-bearing acceptance check.

The pre-feedback prefix of every permissive trajectory supplies its first-submit outcome. This is valid only because mode and caps are undisclosed before the first submission and the model configuration, scaffold, prompt, tool policy, seed allocation, and filesystem start state match the repair-loop run. The pilot uses these prefix outcomes for descriptive pressure diagnostics; they do not replace the independent `N=16` anchor admission and frozen floor panel required when v1 is selected.

After Stage 3, stop and author or select better tasks if first-submit success, eventual success, repair cost, and feedback use show no meaningful separation. Additional seeds cannot repair a task-diversity or task-signal failure.

### Stage 4 - freeze candidate policy and budgets

**Funding:** analysis only.

Using only identified retrospective truncations:

1. propose the smallest `K` after which extra hidden feedback yields little additional legitimate success;
2. propose a pooled step guard that truncates no ordinary successful trajectory in the pilot;
3. evaluate two-band and three-band pressure taxonomies;
4. select a candidate `B_t` for each task as the smallest budget band meeting candidate anchor coverage under the proposed `K` and step guard;
5. permit at most one adjacent development-stage budget-band increase;
6. pre-register fresh-confirmation rules before Stage 5.

Because the pilot is selecting provisional constants, it reports results under several candidate coverage targets rather than pretending that one small-sample target is natural. The 4+2 split remains a diagnostic. A practical machinery check is at least 7/8 fresh anchor successes within the selected policy and budget on each preregistered confirmation task. Full budget selection and task-wide confirmation are v1 freeze procedures demonstrated by this pilot, not satisfied by it.

### Stage 5 - targeted fresh anchor confirmation and `R_t`

**Funding:** Kaggle.
**Tasks:** `access-log-to-incidents`, `invoice-multi-source-merge`, and `merge-divergent-config-branches`.
**Sample:** 8 fresh anchor repair-loop replicates per selected task.
**Trajectories:** 24.

Run under the exact proposed `K`, step guard, `B_t`, model route, scaffold, price sheet, and cache policy. No budget increase is permitted after confirmation begins.

For accepted pilot tasks, estimate

```text
R_t = total canonical anchor spend / anchor successes
```

and publish its sample size and uncertainty. A selected task that misses the machinery check is reported as unconfirmed; its budget is not raised until it passes. The other three tasks remain pilot-development-calibrated rather than task-level confirmed.

### Stage 6 - conditional extensions

**Funding:** Kaggle contingency, then optional OpenRouter.

Use at most 30 Kaggle-funded trajectories for cells that are genuinely decision-relevant:

- anchor confirmation with one miss;
- pressure assignment near a proposed boundary;
- unstable `K` saturation;
- heavy-tailed task-budget behavior;
- reconciliation reruns after an infrastructure correction.

Only after the core pilot is complete may the optional 18-trajectory external comparator run on OpenRouter.

## 6. Planned trajectory and cost envelope

| Work | Pool | Trajectories | Base canonical estimate | High estimate |
|---|---|---:|---:|---:|
| Codex development triage | Codex Pro | 66 | about $16 in-kind | about $24 in-kind |
| Two-task official canary | Kaggle | 16 | about $6 | about $9 |
| Permissive six-task collection | Kaggle | 72 | about $22 | about $32 |
| Targeted fresh anchor confirmation | Kaggle | 24 | about $15 | about $22 |
| Targeted Kaggle extension reserve | Kaggle | up to 30 | about $8 | about $15 |
| Optional external comparator | OpenRouter | up to 18 | about $2 canonical | $25 cash cap |
| **Core official pilot** | **Kaggle** | **112 before conditional extensions** | **about $43** | **about $63** |

The budget workbook carries the exact formulas and editable assumptions. The core Kaggle allocation remains $200 because model-routing changes, longer high-pressure trajectories, indivisible-call overruns, and excluded-row retries can make the historical averages optimistic.

## 7. Daily grant schedule

Do not launch the entire pilot in one day merely because the daily grant permits it.

| Execution day | Work | Planned Kaggle ceiling | Required evidence before next day |
|---|---|---:|---|
| Day 1 | Two-task canary | $25 | Identity, continuation, isolation, and cost reconciliation pass. |
| Day 2 | First half of permissive collection | $50 | Actual cost remains within 1.5x forecast; no systemic cap or runner issue. |
| Day 3 | Remaining permissive collection | $50 | Useful first-submit or repair-loop separation, or an explicit decision to stop and improve the task set. |
| Day 4 | Targeted fresh confirmation | $40 | All three category representatives exercise the frozen confirmation path. |
| Day 5 | Targeted extensions only | $80 | Each additional batch changes a named decision. |

The spreadsheet enforces a recommended **$160 soft launch limit per day**, leaving $40 of the $200 cap as a safety margin.

The daily ceilings are independent safety bounds, not additive budgets. The cumulative **$200 core allocation and $100 targeted-extension reserve dominate** even when daily ceilings sum to a larger number.

## 8. Required data and accounting

Every official row must include:

- the pre-registered `trajectory_id`, `launch_unit_id`, pilot stage, and mode;
- `model_config_id` and canonical configuration JSON;
- `agent_policy_id` and canonical policy JSON;
- requested and resolved model;
- inference gateway and upstream provider;
- reasoning and complete sampling configuration;
- task, verifier, environment, scaffold, and repository hashes;
- response-level input, output, reasoning, cache-read, and cache-write usage;
- gateway-reported or sponsor-metered charge;
- canonical list-price-equivalent charge and price-sheet version;
- cumulative spend, steps, and submissions throughout the loop;
- actual stop reason and exclusion reason;
- funding pool: local, Codex, Kaggle, or OpenRouter.

Accounting reports four distinct quantities:

1. canonical benchmark value;
2. Kaggle grant draw;
3. out-of-pocket OpenRouter cash;
4. Codex subscription trajectories and estimated list-price-equivalent value.

Do not present subscription or grant-funded runs as “free.” They have zero marginal personal cash cost but consume scarce capacity.

## 9. Pilot outputs

The pilot report should contain:

- the six-task candidate and review funnel;
- pass/fail quality evidence for each task;
- official run manifest and immutable identities;
- success-by-submission curves under candidate `K` values;
- step distributions and proposed pooled guard;
- first-submit prefix rates and two-band versus three-band viability;
- `B_t` candidates, development coverage, targeted fresh confirmation, and any band bump;
- `R_t` estimates for the three preregistered confirmation tasks, with sample size;
- reference-budget, realized, and escalation CPSC for the small diagnostic panel, clearly labeled non-leaderboard;
- canonical, Kaggle, Codex, and OpenRouter resource accounting;
- observed cost per stage and a revised report-grade budget projection;
- a concise list of protocol changes, if any, forced by data.

## 10. Go/no-go rules

### Continue to a larger snapshot when

- all six tasks pass construct and executed quality review, or rejected tasks are transparently replaced before official calibration;
- official identities and accounting reconcile;
- all three preregistered category representatives exercise the confirmation path, with misses reported rather than repaired by post hoc budget increases;
- first-submit and repair-loop data show useful model or task separation;
- `K` and the step guard are not dominated by pathological trajectories;
- no task budget requires repeated upward adjustment;
- core Kaggle draw remains below $200 and high-case projected report-grade cost is fundable or sponsorable.

### Stop and revise when

- the high-pressure routine-work region cannot be populated without task hardening;
- permissive trajectories do not support any stable hidden-feedback cap;
- ordinary successes frequently hit the step guard;
- anchor confirmation is unstable at feasible sample sizes;
- provider identity or price reconciliation is incomplete;
- the pilot spends more than $200 of Kaggle funding before targeted confirmation;
- a proposed follow-on run would require personal OpenRouter spend to produce the core claim.

## 11. Funding request strategy

The pilot is also a funding artifact. It should demonstrate that ShallowSWE can convert a small grant into a reproducible measurement rather than a broad exploratory sweep.

After the pilot, prepare a one-page sponsor brief with:

- grant used versus reserved;
- trajectories completed and exclusion rate;
- six-task calibration results;
- one clear economic finding, even if it is a null result such as pressure-band saturation;
- measured cost per stage;
- projected cost and calendar for a report-grade snapshot;
- exact incremental funding requested.

A reasonable initial follow-on ask is the greater of:

```text
$2,000
or
1.5 x the measured report-grade metered-cost projection
```

Using the current planning midpoint of $2,250, that implies an ask near **$3,375**, rounded to a sponsor-friendly **$3,500 one-time project allocation** or approximately **$3,000 per month for two months**. The final request must use pilot actuals rather than these placeholders.

Request a daily-cap increase only when the execution plan benefits from finishing a frozen snapshot quickly. The current $200 daily limit is sufficient for the six-task pilot; the $1,000 monthly limit is the binding constraint for report-grade work.

## 12. Freeze checklist

Before the two-task canary:

- [ ] six task versions selected;
- [ ] independent construct reviewer recorded;
- [ ] executed quality evidence complete for canary tasks;
- [ ] primary anchor and two floor rows frozen;
- [ ] requested model configurations and provider routes frozen before canary execution;
- [ ] full canonical model and agent-policy identities generated;
- [ ] provider fallback disabled;
- [ ] price sheet frozen;
- [ ] temporary permissive limits frozen;
- [ ] Kaggle batch hard stop configured;
- [ ] $25 OpenRouter approval gate configured;
- [ ] output and transcript redaction paths tested;
- [ ] budget workbook assumptions reviewed.

Before targeted fresh confirmation:

- [ ] all six tasks have executed quality evidence;
- [ ] proposed `K` and step guard preregistered;
- [ ] budget-band schedule and task `B_t` values frozen;
- [ ] confirmation go/no-go rule frozen;
- [ ] the three preregistered confirmation task IDs match the v0.3 manifest;
- [ ] no further task or verifier edits permitted;
- [ ] fresh replicate identifiers reserved;
- [ ] projected confirmation draw fits the remaining Kaggle allocation.

## Sources and planning basis

- `docs/white-paper-v0.4.2.md`, especially Sections 6 and 10.4-10.5.
- `SPEC(1).md`, for the original single-model invariant, repair-loop protocol, calibration panels, and rollout defaults.
- July 2026 ShallowSWE planning evidence: approximately $311 for 576 frontier admission attempts, approximately $119 for 1,080 floor attempts, and approximately $83.68 canonical cost across 756 preview repair loops.
- Funding constraints supplied by the project owner: Codex Pro subscription access; Kaggle support of $200/day and $1,000/month; personal OpenRouter overflow to be minimized.
