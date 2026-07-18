# Prime verifiers v1 compatibility spike

Date: 2026-07-12

## Outcome

One local ShallowSWE task is compatible with Prime Intellect's announced `verifiers` v1
Harbor taskset and scorer. The probe used `tasks/py-normalize-username` and upstream commit
`3a651c33856f557e16d53f4a162b170e7e227d7e`.

The untouched task image scored `0.0`. After applying the task's existing `solution/solve.sh`,
the same Prime `HarborTask.solved` verifier scored `1.0`. Both runs completed without verifier
errors. Prime preserved the task prompt, `code` category, 300-second harness timeout,
120-second scoring timeout, and declared CPU, memory, and storage requirements.

## Boundary discovered

The announcement is ahead of the current PyPI distribution. `verifiers==0.1.14` does not
contain the announced v1 Harbor taskset API. The probe therefore ran against the upstream
source commit above.

Prime v1 also does not build Harbor tasks whose environment is declared only by a Dockerfile.
ShallowSWE currently uses that layout. The probe built the existing Dockerfile locally and
replaced the parsed task's image with
`shallowswe/py-normalize-username:prime-v1`. A production adapter would need immutable,
published image digests or a deliberate image-build phase.

Prime documents three remaining Harbor parity gaps that matter when selecting future tasks:
network isolation, shared or separate verifier environments, and multi-step tasks. The smoke
task did not exercise any of them.

## Reproduction

```bash
git clone --depth 1 https://github.com/PrimeIntellect-ai/verifiers.git /tmp/prime-verifiers-v1
docker build \
  -t shallowswe/py-normalize-username:prime-v1 \
  tasks/py-normalize-username/environment
uv run --project /tmp/prime-verifiers-v1 \
  --no-default-groups \
  --extra harbor \
  python scripts/probe_prime_verifiers_v1.py \
  tasks/py-normalize-username \
  --image shallowswe/py-normalize-username:prime-v1
```

## Recommendation

Do not add `verifiers` to ShallowSWE's runtime dependencies yet. Keep Kaggle primary and treat
Prime as an experimental third backend until v1 is released and pinned.

The next useful step is an adapter that:

1. resolves a ShallowSWE task directory to an immutable image digest;
2. loads the local directory without requiring publication to a Harbor registry;
3. maps Prime traces and rewards into `shallowswe.repair_loop.v0.3` rows;
4. checks repair-loop submission caps and verifier-feedback parity; and
5. runs one paid Codex-harness rollout only after estimating and approving its cost.
