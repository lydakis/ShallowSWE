# Kaggle Runner

Kaggle is the primary backend for official ShallowSWE pilot evidence. Pier/Harbor remains the
parallel local-reproduction and portability backend. Codex/Pier may handle development triage, but
Codex subscription trajectories are not official calibration evidence. Both repair-loop backends
consume the canonical `tasks/` tree and the shared controller in `repair_loop_protocol.py`; runner
role and evidence class follow `docs/protocol-governance.md`.

## Parity Contract

The methodology is backend-independent:

- One canonical task packet under `tasks/<task-id>/`.
- The same effective mini-swe-agent prompt/config hash.
- The same pinned mini-swe-agent fork commit.
- One resumable agent instance and one persistent task workspace per row.
- Hidden verifier submissions through the same result classes.
- Only sanitized feedback is returned to the agent.
- The same verifier-submission, step, cost, and wall-time guards.
- The same active repair-loop result schema and token/accounting contract.

Kaggle and Pier do not have byte-identical provider transports. The Kaggle runner preserves native
structured function calls and results for every provider. Google models use Kaggle's provider-native
GenAI route so Gemini thought signatures survive sequential tool calls; other providers use
Kaggle's OpenAI-compatible route. Output-token caps are translated from `max_tokens` to
`max_output_tokens` on the GenAI route. The controller, command, workspace, verifier, feedback
class, and stop rules remain shared. Results should claim methodology parity, not byte-for-byte
transcript parity. Backend provenance remains mandatory, but runner or gateway differences alone
do not prevent pooling when the canonical model, task, agent policy, controls, and continuation
contract match. Known behavioral or identity mismatches remain separate.

## Bundle Boundary

`shallowswe kaggle-pack` exports a private Kaggle dataset bundle from the canonical repository:

```text
manifest.json
tasks/<task-id>/          # instruction, metadata, agent-visible environment source
verifiers/<task-id>/      # hidden verifier, not visible inside the agent chroot
config/                   # mini-swe-agent override
wheels/                   # pinned ShallowSWE and mini-swe-agent runtime
notebook/                 # production entrypoint and runtime requirements
```

The exporter fails closed on Dockerfile instructions it cannot reproduce. The current task set uses
the supported `python:3.12-slim`, `WORKDIR`, `ENV`, `COPY`, and deterministic fixture-generator
subset. `tasks/` remains the only authored source; the Kaggle dataset is generated deployment data.

Build a smoke bundle:

```sh
uv run shallowswe kaggle-pack tmp/kaggle-smoke-bundle \
  --task-id py-normalize-username \
  --tasks-root tasks \
  --config-file configs/mini-swe-agent-repair-loop-preview.yaml \
  --mini-swe-agent-source-dir /Users/lydakis/Developer/oss/mini-swe-agent
```

Repeat `--task-id` for a panel or the accepted task set. Review `manifest.json`, especially task,
environment, verifier, prompt, and runtime hashes, before publishing a dataset version.

For the protocol-validation pilot, also attach `--pilot-manifest`, `--pilot-schedule`,
`--pilot-launch-plan`, and `--price-sheet`. Official pilot bundles require
`SHALLOWSWE_LAUNCH_UNIT_ID`. The runner resolves that ID against the attached launch plan and
derives the task matrix, rollout seeds, model and agent identities, caps, funding pool, evidence
class, and pre-registered trajectory IDs. A model, task, or seed that does not resolve to exactly
one scheduled row fails before execution.

## Kaggle Isolation

The live Kaggle runtime blocks user namespaces, so Bubblewrap and PRoot plus inherited seccomp are
not usable. The production runner instead uses primitives verified in a private Kaggle probe:

- a real kernel `chroot` with only the task workspace and a minimal runtime;
- a root-owned, uv-managed Python 3.12 tree and real Bash;
- commands executed as UID/GID 65534;
- a seccomp filter installed before `chroot` that denies socket creation for the entire command
  process tree;
- no `/proc`, Kaggle input mount, credentials, notebook environment, or verifier in the agent root;
- `/tests` and `/logs/verifier` copied into the chroot only for a verifier submission, then removed
  before the agent can continue.

The runner performs a fail-closed preflight before the first model call. It verifies Python 3.12,
network denial, and absence of `/kaggle/input`. A failed preflight is excluded as runner
infrastructure and consumes no model turns.

## Private Kaggle Artifacts

The infrastructure was validated on Kaggle with private artifacts:

- Dataset: `glydakis/shallowswe-kaggle-bundle`.
- Environment probe: `glydakis/shallowswe-kaggle-environment-probe` version 8.
- Production runner: `glydakis/shallowswe-repair-loop-v2` version 1.
- Deterministic conformance task: `glydakis/shallowswe-repair-loop-conformance` version 2.

The conformance run passed in three agent turns with two hidden-verifier submissions. Submission one
failed, the same agent received only `Verification failed. Continue working.`, submission two
passed, and the raw diagnostic was absent from the trajectory. The normalized row was scored with
`stop_reason = "passed"` and `task_visibility = "kaggle-chroot-seccomp-hidden-verifier"`.

The production task also exercised live Kaggle model transport and sandbox commands. The default
Gemini smoke reached a scored agent-step cap without submitting, while Claude Haiku, GPT-OSS,
DeepSeek, and Qwen attempts were excluded because Kaggle returned provider 429/503 errors before
their first response. Those rows are provider-capacity evidence, not benchmark results.

Kaggle's model proxy may omit `total_cost_nanodollars` for a response. When it does, the runner
cannot enforce the row's dollar cap from gateway cost metadata. The step cap and wall-time cap still
bound the run, and the normalized result retains the proxy-reported usage that was available. Treat
the dollar cap as an additional guard on Kaggle, not the only funded-run budget boundary.

## Operating Flow

Authenticate and initialize the model proxy environment without committing credentials:

```sh
kaggle auth login
kaggle benchmarks init -y --env-file /tmp/shallowswe-kaggle.env \
  --example-file /tmp/shallowswe-kaggle-example.py
```

Create or version a private bundle dataset with `kaggle datasets create` or
`kaggle datasets version`, then wait until `kaggle datasets list --mine` reports the new
`lastUpdated` value before pushing a task. Kaggle task creation attaches the latest fully published
dataset version, not an upload still being processed.

Push or run the production task:

```sh
set -a
source /tmp/shallowswe-kaggle.env
set +a

kaggle benchmarks tasks push shallowswe-repair-loop-v2 \
  -f kaggle/shallowswe_runner.py \
  -d glydakis/shallowswe-kaggle-bundle \
  --wait

kaggle benchmarks tasks run shallowswe-repair-loop-v2 \
  -m '<kaggle-model-slug>' \
  --wait
```

If Benchmarks task commands do not inherit cached OAuth, export a short-lived token for that shell
with `KAGGLE_API_TOKEN="$(kaggle auth print-access-token)"`. Never print, commit, or place the model
proxy environment or Kaggle token in the bundle.

Download model-run records with `kaggle benchmarks tasks download`. Kernel creation output also
contains `shallowswe-results/<run-id>/repair-loop-result.json`, the mini-swe trajectory, runner-only
verifier diagnostics, and the final workspace. Only scored rows belong in published aggregates;
retry excluded infrastructure rows under the protocol rules.
