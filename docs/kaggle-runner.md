# Kaggle Runner

Kaggle is the primary funded execution backend. The runner is a generic deployment entrypoint: it
consumes a generated task bundle and one roadmap-agnostic `RunSpec`, executes the bounded repair
loop, and emits normalized result artifacts. It does not decide what an experiment means.

## Contract

Each row binds one task, model configuration, agent policy, rollout seed, and set of limits. The
runner preserves:

- one resumable agent and persistent workspace;
- hidden verifier isolation and sanitized feedback;
- exact verifier-submission, agent-step, dollar, and wall-time limits;
- native provider tool-call transport;
- event-level usage, cost, and verifier checkpoints;
- requested and resolved model identity;
- final workspace, trajectory, verifier diagnostics, and normalized result; and
- opaque experiment metadata without branching on it.

There is no model fallback. Unknown units, tasks, models, seeds, prices, or identities fail closed.

## Bundle

`shallowswe kaggle-pack` generates private deployment data from `tasks/`:

```text
manifest.json
tasks/<task-id>/          # agent-visible task source
verifiers/<task-id>/      # hidden verifier
config/                   # agent configuration
run/run-spec.json         # exact execution facts
pricing/                  # dated canonical price basis
wheels/                   # pinned ShallowSWE and mini-swe-agent runtime
notebook/                 # generic Kaggle entrypoint
```

Build the current canary bundle:

```sh
uv run shallowswe kaggle-pack /tmp/shallowswe-kaggle-canary \
  --task-id env-flags-to-json \
  --task-id invoice-multi-source-merge \
  --tasks-root tasks \
  --config-file configs/mini-swe-agent-kaggle-repair-loop.yaml \
  --run-spec configs/experiments/weekend-six-task-kaggle-2026-07-18/run-spec-canary.json \
  --price-sheet prices/openrouter-2026-07-09.json \
  --mini-swe-agent-source-dir /Users/lydakis/Developer/oss/mini-swe-agent
```

Inspect `manifest.json`, `run/run-spec.json`, task hashes, verifier hashes, wheel names, and the
price sheet before publishing a dataset version.

Generate one hash-bound Kaggle source per run unit:

```sh
uv run shallowswe kaggle-bound-sources \
  configs/experiments/weekend-six-task-kaggle-2026-07-18/run-spec-canary.json \
  /tmp/shallowswe-kaggle-canary-sources
```

Each generated source freezes `FROZEN_RUN_UNIT_ID` and its Kaggle task name. An optional
`SHALLOWSWE_RUN_UNIT_ID` must agree with the frozen value.

## Isolation

The Kaggle runtime uses a kernel `chroot` and seccomp because user namespaces are unavailable:

- only the task workspace and minimal runtime enter the agent root;
- commands run as UID/GID 65534;
- socket creation is denied for the command process tree;
- `/proc`, Kaggle inputs, credentials, and verifier files are absent during agent turns;
- verifier files enter the chroot only during a verifier submission and are then removed; and
- a fail-closed preflight checks Python, network denial, and input-mount absence before model use.

A preflight failure is runner infrastructure, not a scored model failure.

## Publish and Run

Authenticate without committing credentials:

```sh
kaggle auth login
kaggle benchmarks init -y --env-file /tmp/shallowswe-kaggle.env \
  --example-file /tmp/shallowswe-kaggle-example.py
```

Create or version the private bundle dataset, then wait until Kaggle reports the new published
version. Push each bound source using its generated task name:

```sh
set -a
source /tmp/shallowswe-kaggle.env
set +a

kaggle benchmarks tasks push <task-name> \
  -f /tmp/shallowswe-kaggle-canary-sources/<task-name>.py \
  -d glydakis/shallowswe-kaggle-bundle \
  --wait

kaggle benchmarks tasks run <task-name> -m '<exact-kaggle-model-slug>' --wait
```

Never print, commit, or bundle the Kaggle token or model-proxy environment. The harness contains no
default-model registration workaround and must never invoke Gemini 3 Flash. Gemini 3.5 Flash is a
different configured model and is only eligible when named by an exact run spec.

## Download and Reconcile

Download every task run with `kaggle benchmarks tasks download`. Preserve the normalized
`repair-loop-result.json`, raw task-run record, trajectory, checkpoints, verifier diagnostics, final
workspace, retry count, and provider error.

Only rows with `status != excluded` are scored. Provider 429/503 failures before the first model
response are infrastructure exclusions. Missing gateway dollar metadata does not disable the step,
wall-time, or batch hard stops; it must remain visible in the result.

After each launch unit, reconcile:

1. requested and resolved model identity;
2. expected versus downloaded trajectory count;
3. scored versus excluded rows and retries;
4. gateway and canonical cost fields;
5. Kaggle quota draw and batch hard stop; and
6. complete artifact presence.

Analysis happens separately with `shallowswe analyze-repair-loops` and an explicit
`MethodologySpec`.
