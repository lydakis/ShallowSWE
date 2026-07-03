# ShallowSWE Methodology Notes

## Result Status

Rollout rows are either `scored` or `excluded`.

Scored rows count toward pass rate, tokens per success, and CPSC. This includes normal verifier failures, context-window failures, task caps, and agent timeouts when token usage is available.

Excluded rows do not count toward pass rate or CPSC. This includes provider, network, credential, credit, routing, and verifier infrastructure failures. Exclusions should be retried until each model-task pair has the target number of scored rollouts. Published summaries should include exclusion counts.

## Token Convention

`input_tokens` uses the provider/gateway prompt-token convention. For OpenAI-style APIs, cached input tokens are included in prompt tokens. `cache_read_tokens` and `cache_write_tokens` are stored separately so cost derivation can price uncached input, cache reads, and cache writes without double-counting.

The cost formula is:

```text
uncached_input_tokens = input_tokens - cache_read_tokens - cache_write_tokens
derived_cost = uncached_input_tokens * input_rate
             + cache_read_tokens * cache_read_rate
             + cache_write_tokens * cache_write_rate
             + output_tokens * output_rate
```

`reasoning_tokens` are a subset of output tokens when the provider reports them.

## Gateway Policy

OpenRouter is the default gateway for panel plumbing because it exposes the current DeepSWE model set through one API. Official runs must still pin provider routing, disable fallbacks, record the upstream provider per row, and run direct-provider audit checks per provider family.

Dollar metrics are gateway-aware. Tokens remain canonical, while gateway-reported cost is stored only as reconciliation metadata.

## Panel Floor

The calibration floor is empirical on shallow tasks. Do not use DeepSWE rank on hard tasks as the ShallowSWE floor. Gate candidate tasks against the cheapest/smallest panel candidates first, then use the observed weakest row on shallow tasks as the floor for the saturation gate.
