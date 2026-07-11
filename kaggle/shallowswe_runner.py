# %% [markdown]
# # ShallowSWE Kaggle repair-loop runner
#
# This notebook is a thin deployment entrypoint. The attached bundle is generated from the
# canonical ShallowSWE `tasks/` tree and contains pinned ShallowSWE and mini-swe-agent wheels.

# %%
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys


def _find_attached_bundle_root() -> Path:
    explicit = os.environ.get("SHALLOWSWE_BUNDLE_ROOT")
    if explicit:
        return Path(explicit)
    candidates = []
    for manifest in Path("/kaggle/input").rglob("manifest.json"):
        try:
            payload = json.loads(manifest.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("schema_version") == "shallowswe.kaggle_bundle.v0.1":
            candidates.append(manifest.parent)
    if len(candidates) != 1:
        raise RuntimeError(
            "Expected exactly one attached ShallowSWE bundle, "
            f"found {len(candidates)} under /kaggle/input"
        )
    return candidates[0]


ATTACHED_BUNDLE_ROOT = _find_attached_bundle_root()


def _prepare_bundle_root() -> Path:
    if (ATTACHED_BUNDLE_ROOT / "wheels").is_dir():
        return ATTACHED_BUNDLE_ROOT
    if not ATTACHED_BUNDLE_ROOT.is_dir():
        raise RuntimeError(f"ShallowSWE bundle is not attached: {ATTACHED_BUNDLE_ROOT}")
    target = Path("/kaggle/working/shallowswe-bundle")
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    for source in ATTACHED_BUNDLE_ROOT.iterdir():
        if source.suffix == ".zip":
            destination = target / source.stem
            destination.mkdir()
            shutil.unpack_archive(source, destination)
        elif source.is_file():
            shutil.copy2(source, target / source.name)
    return target


BUNDLE_ROOT = _prepare_bundle_root()


def _install_runtime() -> None:
    requirements = BUNDLE_ROOT / "notebook" / "requirements-runtime.txt"
    wheels = sorted((BUNDLE_ROOT / "wheels").glob("*.whl"))
    if len(wheels) != 2:
        raise RuntimeError(f"Expected ShallowSWE and mini-swe-agent wheels, found: {wheels}")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", "-r", str(requirements)],
        check=True,
    )
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv is required to install the pinned Python 3.12 sandbox runtime")
    subprocess.run([uv, "python", "install", "3.12", "--no-progress"], check=True)
    sandbox_python = subprocess.check_output(
        [
            uv,
            "python",
            "find",
            "3.12",
            "--managed-python",
            "--no-project",
            "--resolve-links",
        ],
        text=True,
    ).strip()
    os.environ["SHALLOWSWE_SANDBOX_PYTHON"] = sandbox_python
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--quiet",
            "--no-deps",
            "--ignore-requires-python",
            *(str(wheel) for wheel in wheels),
        ],
        check=True,
    )
    if shutil.which("busybox") is None:
        subprocess.run(["apt-get", "update", "-qq"], check=True)
        subprocess.run(
            [
                "apt-get",
                "install",
                "-y",
                "-qq",
                "busybox-static",
                "libseccomp2",
                "util-linux",
            ],
            check=True,
        )


_install_runtime()

# %%
import kaggle_benchmarks as kbench  # noqa: E402
from IPython import get_ipython  # noqa: E402

from shallowswe.kaggle_repair_loop import (  # noqa: E402
    dump_kaggle_result,
    run_kaggle_repair_loop,
)


MANIFEST = json.loads((BUNDLE_ROOT / "manifest.json").read_text())
TASK_INDEX = {entry["task_id"]: entry for entry in MANIFEST["tasks"]}
RESULTS_ROOT = Path("/kaggle/working/shallowswe-results")
RESULTS_ROOT.mkdir(parents=True, exist_ok=True)


@kbench.task(
    name="shallowswe-repair-loop-v2",
    description="Run the canonical bounded ShallowSWE repair-loop methodology.",
)
def shallowswe_repair_loop(llm, task_id: str, rollout_seed: int) -> bool:
    if task_id not in TASK_INDEX:
        raise ValueError(f"Task is not present in the attached ShallowSWE bundle: {task_id}")
    task_entry = TASK_INDEX[task_id]
    run_id = f"{task_id}__seed-{rollout_seed:02d}"
    run_root = RESULTS_ROOT / run_id
    row = run_kaggle_repair_loop(
        llm=llm,
        task_path=BUNDLE_ROOT / task_entry["task_path"],
        verifier_dir=BUNDLE_ROOT / task_entry["verifier_path"],
        workspace_dir=run_root / "workspace",
        artifacts_dir=run_root / "artifacts",
        run_id=run_id,
        model_name=llm.name,
        config_file=BUNDLE_ROOT / MANIFEST["mini_swe_agent_config"],
        max_verifier_submissions=int(
            os.environ.get("SHALLOWSWE_MAX_VERIFIER_SUBMISSIONS", "3")
        ),
        dollar_cap_usd=(
            float(os.environ["SHALLOWSWE_DOLLAR_CAP_USD"])
            if os.environ.get("SHALLOWSWE_DOLLAR_CAP_USD")
            else None
        ),
        wall_time_cap_seconds=int(
            os.environ.get("SHALLOWSWE_WALL_TIME_CAP_SECONDS", "2400")
        ),
        reasoning_effort=os.environ.get("SHALLOWSWE_REASONING_EFFORT") or None,
        temperature=float(os.environ.get("SHALLOWSWE_TEMPERATURE", "0")),
        seed=rollout_seed,
        task_suite_version=os.environ.get(
            "SHALLOWSWE_TASK_SUITE_VERSION",
            "shallowswe-kaggle-smoke-v0.1",
        ),
        repo_commit_sha=os.environ.get("SHALLOWSWE_REPO_COMMIT_SHA") or None,
    )
    (run_root / "repair-loop-result.json").write_text(dump_kaggle_result(row))
    if not row.is_scored:
        raise RuntimeError(
            f"Excluded ShallowSWE runner failure: {row.stop_reason} ({row.exclusion_reason})"
        )
    kbench.assertions.assert_true(
        row.passed,
        expectation="The ShallowSWE hidden verifier should pass within the submission cap.",
    )
    return row.passed


# %%
if os.environ.get("KAGGLE_KERNEL_RUN_TYPE"):
    selected_tasks = os.environ.get("SHALLOWSWE_TASK_IDS")
    task_ids = (
        [task_id.strip() for task_id in selected_tasks.split(",") if task_id.strip()]
        if selected_tasks
        else list(MANIFEST["task_ids"])
    )
    seeds = range(int(os.environ.get("SHALLOWSWE_SEEDS", "1")))
    with kbench.client.enable_cache():
        SHALLOWSWE_RUNS = shallowswe_repair_loop.evaluate(
            llm=[kbench.llm],
            task_id=task_ids,
            rollout_seed=seeds,
            n_jobs=int(os.environ.get("SHALLOWSWE_N_JOBS", "1")),
            timeout=int(os.environ.get("SHALLOWSWE_ROW_TIMEOUT_SECONDS", "2700")),
            on_failure="continue",
            max_attempts=int(os.environ.get("SHALLOWSWE_MAX_ATTEMPTS", "2")),
            retry_delay=15,
        )

# %%
if os.environ.get("KAGGLE_KERNEL_RUN_TYPE"):
    get_ipython().run_line_magic("choose", "shallowswe_repair_loop")
