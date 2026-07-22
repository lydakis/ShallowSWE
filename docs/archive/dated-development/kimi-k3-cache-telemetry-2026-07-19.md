# Kimi K3 cache telemetry, 2026-07-19

This is an audit record, not part of the existing-data research result and not a paper or website
amendment. Six paid requests were made before the scope was corrected to prohibit new experiments;
no further requests are authorized. The machine-readable record is
`results/kimi-k3-cache-telemetry-2026-07-19/openrouter-moonshot-probe.json`.

A separate `ofetch` diagnostic also began before that correction. It was cancelled during
verification after 51 agent steps, returned no verifier result, and cost `$2.0142822`. It is not a
research outcome and is excluded from every K3 finding. Together with the six-request probe, the
paid activity incurred before the correction totals `$2.0771142`.

## Result

Six provider-pinned OpenRouter requests reached the sole Moonshot AI Kimi K3 endpoint. Two fresh
synthetic prefixes were cold, followed by sequential, cross-process, and concurrent warm reads.
All six requests succeeded without retries or fallback and cost $0.062832 in response-reported
usage.

The endpoint discovery record named the upstream snapshot
`Moonshot AI | moonshotai/kimi-k3-20260715`, tagged it `moonshotai/int4`, and reported INT4
quantization. Its `supports_implicit_caching` flag was `false`, contradicting the four response
records with nonzero `cached_tokens` and discounted prompt cost. Response usage and invoices are
the stronger evidence; the discovery flag is not reliable for this model as of the probe time.

| Case | Prompt | Cached | Cache share | Cost |
| --- | ---: | ---: | ---: | ---: |
| A1 cold | 7,028 | 0 | 0% | $0.022044 |
| A2 warm | 7,028 | 6,912 | 98.35% | $0.003382 |
| A3 new-process warm | 7,028 | 6,912 | 98.35% | $0.003382 |
| B1 cold prime | 8,528 | 0 | 0% | $0.026544 |
| B2 concurrent warm | 8,530 | 8,448 | 99.04% | $0.003740 |
| B3 concurrent warm | 8,530 | 8,448 | 99.04% | $0.003740 |

The warm token counts are exact multiples of 128. Both concurrent reads hit after one completed
prime, and the new-process request retained the first prefix cache. Cold requests reported zero
`cache_write_tokens`, so automatic cache creation is not exposed through that field.

This is strong evidence that a 98% cache share is realistic for an individual warm K3 request with
a long stable prefix on this route. It is not evidence that 98% was the realized cumulative cache
share of every DeepSWE attempt. The probe used OpenRouter transport to Moonshot, while the published
DeepSWE job used direct Moonshot and did not retain raw cache telemetry.

## Existing multi-turn evidence

The repository already contains 54 K3 max repair-loop attempts with real OpenRouter cache counters:
`results/shallowswe-repair-loop-preview-n3-18-v0.2-kimi-k3-2026-07-17/repair-loop-results.json`
(SHA-256 `9d5825e696135bd8ea139b742cd3917ddef6ed2a01849bb7cb265000788fb784`).

Across those attempts:

- 17,123,328 of 18,329,753 cumulative input tokens were cache reads, or 93.42% when token-weighted.
- The median per-attempt cache share was 80.26% because short runs pay a large cold-start share.
- Runs with 50 or more agent steps reached 95.96% token-weighted cache share.
- Cache share correlates strongly with run length: 0.84 with steps and 0.93 with log steps.
- Every observed cache count is a multiple of 128 and every cache-write count is zero.

The distinction is economic. DeepSWE K3 CPSC is $6.79 at 98% cache, $7.18 at 97%, $7.56 at 96%,
and $8.54 at the 93.42% aggregate observed in the shorter repair-loop workload. None of these
variants makes K3 cheaper than GPT-5.6 Sol high as a standalone DeepSWE configuration, and all keep
K3 materially below Claude Fable 5 xhigh on reported invoice.

An exploratory inverse-step fit to the 54 repair-loop attempts projects about 96.2% to 97.3% cache
at DeepSWE K3's mean 97.6 steps. That extrapolation is weak because only six local attempts reached
20 steps and the workload, harness continuation behavior, and transport differ. It narrows the
useful sensitivity range but does not replace direct telemetry.

## Boundaries and deviation

The concurrent phase reached 8,530 prompt tokens, 530 above the intended 8,000-token preflight
ceiling. OpenRouter did not expose a token-estimate preflight in this implementation. The actual
six-request spend remained far below the $0.18 dollar ceiling, but the deviation is retained in the
machine-readable record.

The probe shows that a primed cache supports two simultaneous reads. It does not test a 200-way cold
launch, cache stampedes, provider queueing, rate limiting, or direct-Moonshot billing. Those remain
plausible explanations for the synchronized DeepSWE timeout wave.
