# ShallowSWE Calibration Log

Calibration runs decide tier assignment. They are not published leaderboard rollouts.

## 2026-07-03/04: `ledger-schema-upgrade`

Purpose: test whether the first transform shelf-edge candidate qualifies as T4 under
`panels/shallowswe-calibration-v0.1.json`.

Run shape:

```text
task: ledger-schema-upgrade
agent: mini-swe-agent
environment: docker
attempts per anchor row: 15
max_tokens: 4096
calibration artifacts: results/shallowswe-t4-ledger-calibration-2026-07-03/
```

| Anchor row | Effort | Passes | Attempts | Pass rate | CPSC | Runtime |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `z-ai/glm-5.2` | high | 12 | 15 | 0.800 | 0.0775 | 27m 47s |
| `google/gemini-3.5-flash` | medium | 13 | 15 | 0.867 | 0.6445 | 51m 55s |
| `moonshotai/kimi-k2.7-code` | default | 14 | 15 | 0.933 | 0.1514 | 1h 27m 19s |

Panel summary:

- Median anchor pass rate: 0.867.
- Weakest anchor pass rate: 0.800.
- Excluded attempts: 0.
- T4 gate: failed. The T4 median band is 0.300-0.700.
- T3 gate: passed. The T3 median band is 0.800-0.950.

Decision:

`ledger-schema-upgrade` is not accepted as T4. It is marked `calibrated_t3` in task metadata and
should be treated as a high-T3 deterministic transform task unless it is redesigned into a harder
candidate and recalibrated.

Interpretation:

The N=1 expanded-panel failure by Gemini 3.5 Flash medium was a sizing signal, not a stable tier
assignment. At N=15, all three cheap anchor rows clear at least 80%, so this task is below the
shelf-edge failure band even though it remains useful for measuring flailing, token cost, and
retry tax.

## 2026-07-03: `config-key-rollover`

Purpose: validate T4 packaging and Pier/OpenRouter plumbing on a cross-cutting operate task.

Result:

- N=1 expanded-panel sweep passed 10/10 model configs.
- No high-N shelf-edge calibration was run after saturation.
- The task remains a plumbing probe with `probe_saturated_n1` metadata.

Decision:

`config-key-rollover` is not accepted as T4 without redesign. It may be demoted or kept as an
internal probe.

## 2026-07-03/04: `status-terminal-parity`

Purpose: test whether a multi-entry status-parity fix creates enough shelf-edge pressure for T4.

Run shape:

```text
task: status-terminal-parity
agent: mini-swe-agent
environment: docker
attempts per anchor row: 1
max_tokens: 4096
calibration artifacts: results/shallowswe-t4-status-calibration-2026-07-03/
```

| Anchor row | Effort | Passes | Attempts | Pass rate | CPSC | Turns |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `z-ai/glm-5.2` | high | 1 | 1 | 1.000 | 0.0233 | 10 |
| `google/gemini-3.5-flash` | medium | 1 | 1 | 1.000 | 0.3019 | 31 |
| `moonshotai/kimi-k2.7-code` | default | 1 | 1 | 1.000 | 0.0568 | 17 |

Decision:

`status-terminal-parity` is not accepted as T4 without redesign. It is marked
`probe_saturated_n1`. Gemini's 31-turn pass is useful flailing evidence, but the candidate is too
solvable on first attempt to justify immediate N=15 T4 calibration.

## 2026-07-04: `ticket-state-reconcile`

Purpose: test whether deterministic local API reconciliation creates a real shelf-edge T4 task.

Run shape:

```text
task: ticket-state-reconcile
agent: mini-swe-agent
environment: docker
anchor attempts per row: 15
top-gate attempts: 5
max_tokens: 4096
calibration artifacts: results/shallowswe-t4-ticket-calibration-2026-07-03/
```

Cheap-anchor calibration:

| Anchor row | Effort | Passes | Attempts | Pass rate | CPSC | Turns |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `google/gemini-3.5-flash` | medium | 5 | 15 | 0.333 | 1.5428 | 22.1 |
| `z-ai/glm-5.2` | high | 6 | 15 | 0.400 | 0.1548 | 9.5 |
| `moonshotai/kimi-k2.7-code` | default | 10 | 15 | 0.667 | 0.2193 | 18.4 |

Top-gated calibration:

| Top row | Effort | Passes | Attempts | Pass rate | CPSC | Turns |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `openai/gpt-5.5` | medium | 5 | 5 | 1.000 | 0.4489 | 13.6 |

Publish-panel top-up:

The expanded publish panel was topped up on this task on 2026-07-04 so the Claude/OpenAI rows
have N=5 scored attempts. These rows are publish data, not a new calibration gate. Three
provider/network retry exclusions are retained separately in the public rollouts.

| Publish row | Effort | Passes | Scored attempts | Excluded | Pass rate | CPSC | Turns |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `anthropic/claude-fable-5` | low | 4 | 5 | 0 | 0.800 | 0.4603 | 7.0 |
| `anthropic/claude-opus-4.8` | low | 3 | 5 | 1 | 0.600 | 0.3503 | 9.0 |
| `anthropic/claude-opus-4.8` | medium | 5 | 5 | 0 | 1.000 | 0.3524 | 10.4 |
| `anthropic/claude-sonnet-5` | low | 2 | 5 | 0 | 0.400 | 0.2312 | 7.4 |
| `anthropic/claude-sonnet-5` | medium | 4 | 5 | 0 | 0.800 | 0.1811 | 9.2 |
| `openai/gpt-5.5` | low | 5 | 5 | 2 | 1.000 | 0.2956 | 10.0 |

Panel summary:

- Median anchor pass rate: 0.400.
- Weakest anchor pass rate: 0.333.
- Top-gated pass rate: 1.000.
- T4 gate: passed. The calibration-panel median is inside the 0.300-0.700 T4 band, and the
  top-gated row clears the >=0.800 gate.

Decision:

`ticket-state-reconcile` is accepted as the first T4 shelf-edge task and is marked `accepted_t4`
in task metadata. It enters the same benchmark basket as T1-T3, with tier labels preserved.

Interpretation:

This task demonstrates the second cost mechanism. T1-T2 saturation can still measure flailing
and context rent among successful rollouts, while this T4 task exposes the retry-tax denominator:
some rows are cheap per attempt but no longer cheap per success.
