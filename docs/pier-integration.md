# Pier Integration

Pier/Harbor is the local portability and reproduction backend. Kaggle remains the primary funded
execution backend. Both consume the canonical `tasks/` tree and must preserve the same bounded
repair-loop semantics before their rows can be compared or pooled.

## Ownership Boundary

Pier owns sandbox execution, imported agents, verifier invocation, trajectories, and raw trial
artifacts. ShallowSWE owns:

- task metadata and hidden-verifier contracts;
- exact model and agent identities;
- repair-loop continuation and sanitized verifier feedback;
- normalized `RepairLoopResult` rows;
- dated price sheets and post-run analysis; and
- the workload and CPSC methodology.

No Pier command or agent wrapper decides whether a row is a shakedown, calibration, confirmation,
or report-grade observation. Those labels are external experiment metadata.

## Task Layout

Pier uses the canonical task packets directly:

```text
tasks/<task-id>/
  task.toml
  instruction.md
  environment/
  solution/
  tests/
```

ShallowSWE metadata belongs in `task.toml`, not in runner-specific directory structures.

## Stateful Repair Loop

Use `shallowswe.pier_agents.resumable_mini_swe_agent:ResumableMiniSweAgent` when the run requires
same-conversation repair. It resumes the prior trajectory and supplies sanitized verifier feedback
while retaining the same workspace. A wrapper that preserves only the filesystem but starts a new
conversation does not implement the canonical repair loop.

Run one generic row through Pier:

```sh
uv run shallowswe run-repair-loop <task-id> \
  --model <exact-model-id> \
  --config-file configs/mini-swe-agent-calibration.yaml \
  --max-verifier-submissions 5 \
  --wall-time-cap-seconds 2400 \
  --output /tmp/repair-loop-row.json
```

The command accepts opaque experiment, run-spec, run-unit, and metadata identifiers. They are
copied into the result and never alter execution.

## Equivalence and Accounting

Treat two backend rows as comparable only when the task contract, model identity, agent policy,
continuation behavior, limits, sampling controls, and price basis match. Always retain runner,
gateway, provider route, resolved model, retry, and exclusion provenance.

Canonical dollars are derived from the dated price sheet. Gateway-reported cost is reconciliation
metadata. Provider, credential, network, model-resolution, verifier-infrastructure, and pre-response
transport failures are exclusions; model behavior inside a valid repair loop is scored.

For cheap local probes, estimate cost first and keep the resulting rows under their actual
transport identity. A local probe is useful pipeline evidence but does not become Kaggle evidence
because its output schema matches.
