# Price/Efficiency Clustering Analysis 2026-07-07

Analysis of the 540-row preview run
`shallowswe-repair-loop-preview-n3-18-v0.2-config-rollover-temp-2026-07-06`
(18 tasks x 3 seeds x 10 model configs, all rows scored, zero exclusions).

Reproduce with:

```bash
python scripts/analyze_price_efficiency_clusters.py \
  --results results/shallowswe-repair-loop-preview-n3-18-v0.2-config-rollover-temp-2026-07-06/repair-loop-results.json \
  --prices prices/openrouter-2026-07-03.json
```

## Hypotheses under test

1. Model configs cluster on $/success (observed by eye in the preview run: a cheap
   cluster around Sonnet, a mid cluster around Fable-low/GPT-low/Opus-medium, with
   the open-weight models outside).
2. Open-weight models are priced near real serving cost (competitive market), closed
   models carry margin. If models can be placed on a common capability scale, the gap
   between a closed model's price and the open-market price for equivalent capability
   estimates that margin ("shadow price" / "capability-equivalent open-market price").

## Findings

### 1. The run is at total ceiling — capability clustering is degenerate

539/540 runs passed. The only failure is `glm-5.2/high` dropping 1 of 3 seeds on
`invoice-multi-source-merge`. Every config has an identical per-task success vector,
so there is zero capability signal in this run: no task discriminates (max per-task
success-rate variance across configs is 0.010). Capability clustering, IRT/latent
ability scaling, and the price-vs-capability curve all require the harder task refill.
This is ShallowSWE working as designed, but it constrains what the preview data can say.

### 2. The $/success clusters are mostly real, but membership changes

Bootstrap 95% CIs (resampling the 18 tasks, seeds nested, B=10k):

| config | $/success | 95% CI |
| --- | ---: | --- |
| glm-5.2/high | 0.023 | [0.017, 0.031] |
| claude-sonnet-5/low | 0.053 | [0.031, 0.083] |
| kimi-k2.7-code | 0.054 | [0.027, 0.093] |
| claude-sonnet-5/medium | 0.059 | [0.045, 0.075] |
| claude-opus-4.8/low | 0.087 | [0.065, 0.113] |
| claude-fable-5/low | 0.129 | [0.094, 0.170] |
| gpt-5.5/low | 0.132 | [0.114, 0.152] |
| claude-opus-4.8/medium | 0.134 | [0.101, 0.172] |
| gpt-5.5/medium | 0.233 | [0.165, 0.334] |
| gemini-3.5-flash/medium | 0.309 | [0.205, 0.466] |

- The mid cluster {fable-low, gpt5.5-low, opus-medium} at ~$0.13 is real (heavily
  overlapping CIs).
- Kimi is NOT outside the closed cheap cluster: its CI sits dead-on Sonnet-low's.
  Only GLM is genuinely separated at the bottom.
- Opus-low floats between the two clusters, distinguishable from neither.
- With 18 tasks the CIs are wide (Kimi's spans 3.5x); cluster claims at this N need
  the bootstrap check, always.

### 3. Repricing decomposition: closed models are the most token-efficient; the residual is a margin ladder

Repricing every config's actual token usage at GLM-5.2 sticker prices separates token
behavior from sticker price:

| config | $/succ (own price) | $/succ @ GLM prices | sticker premium |
| --- | ---: | ---: | ---: |
| claude-fable-5/low | 0.1287 | 0.0097 | 13.3x |
| claude-opus-4.8/low | 0.0870 | 0.0135 | 6.4x |
| gpt-5.5/low | 0.1322 | 0.0198 | 6.7x |
| claude-opus-4.8/medium | 0.1335 | 0.0208 | 6.4x |
| claude-sonnet-5/medium | 0.0593 | 0.0238 | 2.5x |
| claude-sonnet-5/low | 0.0526 | 0.0241 | 2.2x |
| glm-5.2/high | 0.0232 | 0.0290 | 0.8x |
| gpt-5.5/medium | 0.2330 | 0.0363 | 6.4x |
| kimi-k2.7-code | 0.0541 | 0.0529 | 1.0x |
| gemini-3.5-flash/medium | 0.3093 | 0.1739 | 1.8x |

- The token-efficiency ranking (middle column) is nearly the inverse of the price
  ranking. Fable-low is the most token-efficient agent in the field — at equal token
  prices it would be ~3x cheaper per success than GLM and ~5.5x cheaper than Kimi.
- Kimi ties Sonnet-low on $/success only because ~4x cheaper tokens compensate for
  ~2x the input tokens (112k vs 65k per success) and 14 steps vs 8.5.
- The premium column is a clean ladder inside Anthropic's lineup: Sonnet ~2.2x,
  Opus ~6.4x, Fable ~13x over open-market token rates for identical work. GPT-5.5
  sits at Opus's multiple.
- Caveat: this is a premium over open-market token rates, not a proven profit margin —
  Fable/Opus are presumably more expensive per token to serve than GLM. It bounds the
  margin story; it does not prove it.

### 4. Behavioral clustering does not match the price clusters

Clustering configs on price-free per-task behavior profiles (z-scored log output
tokens + log steps per task), models group by lab and reasoning effort, not price:

- First merges: opus-medium+sonnet-medium, then gpt5.5-low joins; fable-low+opus-low
  pair, then sonnet-low joins (the Anthropic low-effort branch).
- Gemini-3.5-flash is a massive outlier (25 steps/run, 17.6k output tokens per
  success — flailing to eventual success). Kimi is also behaviorally distinct.
- So the observed $/success clusters are NOT groups of similar behavior: they are
  different behavioral profiles whose price x efficiency products land on the same
  number. Consistent with (but not proof of) labs pricing tiers so effective cost
  lands at competitive parity.

### 5. Data-quality flag: Sonnet-5 reported cost is ~30% below sticker reconstruction

Reconstructing cost from tokens x price sheet (per the methodology cost formula)
matches `gateway_reported_cost_usd` within ~10% for 8 of 10 configs (GPT-5.5-medium
matches to the cent). Two anomalies:

- claude-sonnet-5 (both efforts): reconstruction/reported ~1.4 — OpenRouter charged
  ~30% less than the sheet's $3/$15 implies. Possibly a discounted provider route.
- glm-5.2: ratio ~1.25.

Sonnet-low is the headline closed-model winner, so this materially affects the
leaderboard. Resolve before publishing: check OpenRouter provider routing for the run
and re-verify the price-sheet entries.

## Implications for future runs

- Record the resolved OpenRouter provider per row (the `provider` field was null for
  all 540 rows) so reported-vs-sticker discrepancies can be attributed.
- The margin/shadow-price experiment needs more open-weight points at varied sizes
  (DeepSeek, Qwen large+small, MiniMax) to fit a competitive price-vs-capability
  curve; two points (GLM, Kimi) cannot anchor it.
- The capability side needs the medium/large task refill to get off the ceiling
  before any capability clustering or IRT is meaningful.
- Keep 3+ seeds per task: the bootstrap CIs here are the difference between "two
  clusters" and "noise", and they are free.

## Stats worth exposing on the site

- Tokens per success (output and input separately) next to CPSC — the price-free
  efficiency metric that repricing can't game.
- Bootstrap CIs on CPSC, not just point estimates; wide CIs are honest at N=18.
- Sticker premium vs an open-weight reference (the repricing counterfactual) — the
  most shareable single number from this analysis.
- Steps/run as a behavioral signature (flailing detector; see Gemini-Flash).

## Analysis playbook

`scripts/analyze_price_efficiency_clusters.py` runs the whole pipeline on any
repair-loop results file: headline stats, bootstrap CIs, task discrimination,
capability clustering, behavioral clustering, and the repricing decomposition.
`--reference-model` picks the counterfactual price anchor (default `z-ai/glm-5.2`);
prefer the cheapest competitively-priced open-weight model in the run.
