# ShallowSWE Pilot Plan

The pilot is for task-quality validation, sizing, and floor calibration. It is not the official 36-task suite.

Follow `docs/task-sourcing-methodology.md` before adding official candidate tasks. The existing `py-normalize-username` task remains a harness smoke task and should not be counted as benchmark evidence.

## Stage 0: Quality Gate Pack

Before filling the full category-tier matrix, author and calibrate a small set of realistic project-shaped candidates:

| Task | Family | Tier | Purpose |
| --- | --- | --- | --- |
| `invoice-cli-regression-test-fix` | regression test plus fix | T2 | verifies test-writing and bug-fix realism |
| `report-json-format` | small feature wiring | T2/T3 | verifies multi-file feature plumbing |
| `config-flag-ignored` | bug localization / repo operation | T3 | verifies orientation and config tracing |
| `payout-reconcile` | data transform | T3 | verifies realistic structured-output work |

Current status: these four candidates exist under `tasks/` and have reference solutions plus verifiers. They are official candidates, not accepted benchmark tasks, until floor calibration and review pass.

`config-key-rollover` also exists under `tasks/` as a T4 plumbing probe. It has a reference
solution, an alternate solution, and a verifier, but its N=1 expanded-panel sweep saturated. Do not
include it in the accepted task set without redesign.

`ledger-schema-upgrade` exists under `tasks/` as a high-T3 transform candidate. Its corrected-prompt
N=1 expanded-panel sweep was non-saturated, but N=15 calibration on
`shallowswe-calibration-v0.1` produced anchor pass rates of 0.800, 0.867, and 0.933. That fails
the T4 median band and fits the T3 band, so it is not accepted as T4.

`ticket-state-reconcile` exists under `tasks/` as the first accepted T4 shelf-edge task. N=15
cheap-anchor calibration produced pass rates of 0.333, 0.400, and 0.667, with median 0.400. The
top-gated GPT-5.5 medium row passed 5/5. Include it in the same benchmark basket as the other
accepted tasks.

Run the cheap panel at N=3 first. If these tasks are too easy, ambiguous, or verifier-fragile, fix the methodology before expanding the suite.

## Stage 0.5: Rubric And Verifier Gates

Before authoring more tasks, apply the two task-quality gates:

- `docs/task-selection-rubric.md`: decide whether the task type belongs in ShallowSWE.
- `docs/verifier-contract.md`: decide whether a pass actually proves correctness.

No new task should enter calibration without a candidate pattern card and a verifier contract review.

Tier calibration uses `panels/shallowswe-calibration-v0.1.json`, not the publish panel. Run enough
cheap-anchor rollouts for coarse bands and keep those calibration rollouts out of published
leaderboard stats.

Suggested first run:

```sh
uv run pier run -p tasks \
  --include-task-name invoice-cli-regression-test-fix \
  --include-task-name report-json-format \
  --include-task-name config-flag-ignored \
  --include-task-name payout-reconcile \
  --agent mini-swe-agent \
  --model openrouter/poolside/laguna-xs-2.1 \
  --model openrouter/moonshotai/kimi-k2.7-code \
  --model openrouter/z-ai/glm-5.2 \
  --model openrouter/google/gemini-3.5-flash \
  --agent-kwarg 'model_kwargs={"max_tokens":2048}' \
  --env docker \
  --env-file /Users/lydakis/Developer/blue/apps/supervisor/.env.local \
  --agent-env 'OPENROUTER_API_KEY=${OPENROUTER_API_KEY}' \
  --job-name shallowswe_quality_gate_n3 \
  --jobs-dir /tmp/shallowswe-pier -n 3 -k 1 -q --yes
```

## Publish-Preview Panel

For a first public preview, keep the panel close to DeepSWE while avoiding a full expensive sweep:

- Prefer `panels/deepswe-v1.1-lowest-preview.json` for the first run.
- Keep `panels/deepswe-v1.1-medium-preview.json` as a cleaner medium-only comparison option.
- Exclude Claude Fable rows.
- Exclude Laguna because it is not a DeepSWE row.
- Use the lowest DeepSWE-published effort for each selected model: GPT/Claude at low, Gemini at medium, Kimi at default.
- Display `reasoning_effort` in every table and chart. Null/default effort is not the same model_config as medium.

Because Pier CLI agent kwargs apply to the whole command, run the lowest-preview panel as three effort groups:

```sh
# Low-effort GPT/Claude group
uv run pier run -p tasks \
  --include-task-name invoice-cli-regression-test-fix \
  --include-task-name report-json-format \
  --include-task-name config-flag-ignored \
  --include-task-name payout-reconcile \
  --agent mini-swe-agent \
  --model openrouter/openai/gpt-5.5 \
  --model openrouter/anthropic/claude-opus-4.8 \
  --model openrouter/anthropic/claude-sonnet-5 \
  --agent-kwarg 'reasoning_effort=low' \
  --agent-kwarg 'model_kwargs={"max_tokens":2048}' \
  --env docker \
  --env-file /Users/lydakis/Developer/blue/apps/supervisor/.env.local \
  --agent-env 'OPENROUTER_API_KEY=${OPENROUTER_API_KEY}' \
  --job-name shallowswe_publish_low_group \
  --jobs-dir /tmp/shallowswe-pier -n 3 -k 1 -q --yes

# Gemini remains medium because that is its DeepSWE row.
uv run pier run -p tasks \
  --include-task-name invoice-cli-regression-test-fix \
  --include-task-name report-json-format \
  --include-task-name config-flag-ignored \
  --include-task-name payout-reconcile \
  --agent mini-swe-agent \
  --model openrouter/google/gemini-3.5-flash \
  --agent-kwarg 'reasoning_effort=medium' \
  --agent-kwarg 'model_kwargs={"max_tokens":2048}' \
  --env docker \
  --env-file /Users/lydakis/Developer/blue/apps/supervisor/.env.local \
  --agent-env 'OPENROUTER_API_KEY=${OPENROUTER_API_KEY}' \
  --job-name shallowswe_publish_gemini_medium \
  --jobs-dir /tmp/shallowswe-pier -n 3 -k 1 -q --yes

# Kimi remains default because that is its DeepSWE row.
uv run pier run -p tasks \
  --include-task-name invoice-cli-regression-test-fix \
  --include-task-name report-json-format \
  --include-task-name config-flag-ignored \
  --include-task-name payout-reconcile \
  --agent mini-swe-agent \
  --model openrouter/moonshotai/kimi-k2.7-code \
  --agent-kwarg 'model_kwargs={"max_tokens":2048}' \
  --env docker \
  --env-file /Users/lydakis/Developer/blue/apps/supervisor/.env.local \
  --agent-env 'OPENROUTER_API_KEY=${OPENROUTER_API_KEY}' \
  --job-name shallowswe_publish_kimi_default \
  --jobs-dir /tmp/shallowswe-pier -n 3 -k 1 -q --yes
```

## Stage 1: Author One Shape Per Cell

Start with 12 task instances: one category-tier cell each.

| Category | T1 | T2 | T3 |
| --- | --- | --- | --- |
| Fix | `missing-null-guard` | `implement-to-spec` | `implement-small-feature` |
| Transform | `strip-and-sort` | `config-migration` | `multi-source-join-with-rejects` |
| Operate | `rename-symbol` | `config-chain` | `trace-and-fix-config-bug` |
| Invoke | `cut-ticket` | `update-dont-duplicate` | `reconcile-states` |

The old category-tier matrix below is a coverage target, not the immediate next authoring order.

## Stage 1A: Shelf-Edge Probe

Author shelf-edge probes with calibration gates, then include accepted tasks in the same basket:

| Slot | Candidate shape | Purpose |
| --- | --- | --- |
| Fix T4 probe | `status-terminal-parity` | Authored and locally validated; N=1 cheap-anchor sweep saturated |
| Operate T4 probe | `config-key-rollover` | Validate T4 packaging and demote if saturated |
| Transform high-T3 probe | `ledger-schema-upgrade` | Calibrated below T4; use as evidence for how much harder the next transform shelf-edge task must be |
| Invoke T4 signal | `ticket-state-reconcile` | Accepted T4; use API final state plus duplicate/destructive-overreach checks |

T4 rows should remain visibly labeled as T4, but accepted T4 tasks are folded into the headline
price index.

## Stage 2: N=1 Sizing Sweep

Run one scored rollout per candidate model on the 12-task pilot. This only answers:

- Does Pier execution work across every category?
- Are token/cost/turn metrics captured consistently?
- Which cheap models appear to be floor candidates?
- Are any task shapes obviously too hard or ambiguous?

Do not use N=1 to accept saturation or publish pass-rate claims.

## Stage 3: Floor Calibration

Select the 2-3 cheapest or weakest-looking floor candidates from Stage 2. Run N=5 or more on each pilot task against those candidates.

Accept a task only if the weakest floor candidate passes at >=80%. Simplify or cut anything below that threshold.

## Stage 4: Expand To V1

After the floor is named, instantiate two more tasks per category-tier cell to reach 36 total tasks. Keep the same shape catalog, but vary domains, languages, and file layouts across instances.

## Stop Conditions

- Do not run the 26-row DeepSWE seed panel end-to-end.
- Do not run official snapshots on the Blue OpenRouter key.
- Do not author only Fix tasks; Operate and Invoke are load-bearing.
- Do not accept tasks that require cleverness, hidden inference, external knowledge, or non-programmatic judging.
- Do not treat T3 as "hard" in the DeepSWE sense. T3 should add touch points and sequencing, not insight.
