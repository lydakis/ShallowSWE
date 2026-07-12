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
from kaggle_benchmarks.kaggle.models import load_model  # noqa: E402
from IPython import get_ipython  # noqa: E402

from shallowswe.kaggle_repair_loop import (  # noqa: E402
    dump_kaggle_result,
    run_kaggle_repair_loop,
)
from shallowswe.kaggle_runtime import model_proxy_api  # noqa: E402
from shallowswe.pilot_binding import (  # noqa: E402
    launch_matrix,
    resolve_launch_unit,
    resolve_trajectory,
)


MANIFEST = json.loads((BUNDLE_ROOT / "manifest.json").read_text())
TASK_INDEX = {entry["task_id"]: entry for entry in MANIFEST["tasks"]}
PILOT_MANIFEST = (
    json.loads((BUNDLE_ROOT / MANIFEST["pilot_manifest"]).read_text())
    if MANIFEST.get("pilot_manifest")
    else None
)
PILOT_SCHEDULE = (
    json.loads((BUNDLE_ROOT / MANIFEST["pilot_schedule"]).read_text())
    if MANIFEST.get("pilot_schedule")
    else None
)
PILOT_LAUNCH_PLAN = (
    json.loads((BUNDLE_ROOT / MANIFEST["pilot_launch_plan"]).read_text())
    if MANIFEST.get("pilot_launch_plan")
    else None
)
LAUNCH_UNIT = None
if PILOT_LAUNCH_PLAN is not None:
    launch_unit_id = os.environ.get("SHALLOWSWE_LAUNCH_UNIT_ID")
    if os.environ.get("KAGGLE_KERNEL_RUN_TYPE") and not launch_unit_id:
        raise RuntimeError("SHALLOWSWE_LAUNCH_UNIT_ID is required for a frozen pilot bundle")
    if launch_unit_id:
        LAUNCH_UNIT = resolve_launch_unit(PILOT_LAUNCH_PLAN, launch_unit_id)
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
    model_entry = None
    agent_policy_id = None
    if PILOT_MANIFEST is not None:
        model_entry = next(
            (
                row
                for row in PILOT_MANIFEST["model_configs"]
                if row["canonical"]["requested_model"] == llm.name
            ),
            None,
        )
        if model_entry is None:
            raise RuntimeError(f"Model is not frozen in the pilot manifest: {llm.name}")
        agent_policy_id = PILOT_MANIFEST["agent_policy"]["agent_policy_ids_by_model_role"][
            model_entry["role"]
        ]
    trajectory = None
    if LAUNCH_UNIT is not None:
        if PILOT_SCHEDULE is None or model_entry is None:
            raise RuntimeError("Frozen launch binding requires pilot schedule and model identity")
        trajectory = resolve_trajectory(
            LAUNCH_UNIT,
            PILOT_SCHEDULE,
            task_id=task_id,
            rollout_seed=rollout_seed,
            model_config_id=model_entry["model_config_id"],
            requested_model=llm.name,
        )
    run_id = (
        trajectory["trajectory_id"]
        if trajectory is not None
        else f"{task_id}__seed-{rollout_seed:02d}"
    )
    run_root = RESULTS_ROOT / run_id
    launch_policy = LAUNCH_UNIT["policy"] if LAUNCH_UNIT else None
    verifier_submission_cap = (
        launch_policy.get("verifier_submission_cap") if launch_policy else None
    )
    if LAUNCH_UNIT is not None and verifier_submission_cap is None:
        raise RuntimeError("Launch unit verifier policy is not frozen")
    native_llm = load_model(llm.name, api=model_proxy_api(llm.name))
    row = run_kaggle_repair_loop(
        llm=native_llm,
        task_path=BUNDLE_ROOT / task_entry["task_path"],
        verifier_dir=BUNDLE_ROOT / task_entry["verifier_path"],
        workspace_dir=run_root / "workspace",
        artifacts_dir=run_root / "artifacts",
        run_id=run_id,
        model_name=llm.name,
        config_file=BUNDLE_ROOT / MANIFEST["mini_swe_agent_config"],
        max_verifier_submissions=(
            int(verifier_submission_cap)
            if verifier_submission_cap is not None
            else int(os.environ.get("SHALLOWSWE_MAX_VERIFIER_SUBMISSIONS", "3"))
        ),
        dollar_cap_usd=(
            float(launch_policy["safety_dollar_cap_usd"])
            if launch_policy and launch_policy.get("safety_dollar_cap_usd") is not None
            else float(os.environ["SHALLOWSWE_DOLLAR_CAP_USD"])
            if os.environ.get("SHALLOWSWE_DOLLAR_CAP_USD") and LAUNCH_UNIT is None
            else None
        ),
        wall_time_cap_seconds=int(
            os.environ.get("SHALLOWSWE_WALL_TIME_CAP_SECONDS", "2400")
        ),
        reasoning_effort=(
            LAUNCH_UNIT["reasoning_effort"]
            if LAUNCH_UNIT
            else os.environ.get("SHALLOWSWE_REASONING_EFFORT") or None
        ),
        temperature=float(os.environ.get("SHALLOWSWE_TEMPERATURE", "0")),
        seed=rollout_seed,
        task_suite_version=os.environ.get(
            "SHALLOWSWE_TASK_SUITE_VERSION",
            "shallowswe-kaggle-smoke-v0.1",
        ),
        repo_commit_sha=os.environ.get("SHALLOWSWE_REPO_COMMIT_SHA") or None,
        model_config_id=model_entry.get("model_config_id") if model_entry else None,
        model_config_canonical_json=model_entry.get("canonical") if model_entry else None,
        agent_policy_id=agent_policy_id,
        agent_policy_canonical_json=(
            PILOT_MANIFEST["agent_policy"]["canonical"] if PILOT_MANIFEST else None
        ),
        provider_route=(
            model_entry["canonical"]["provider_route"] if model_entry else "kaggle_model_proxy"
        ),
        context_limit=(
            model_entry["canonical"].get("model_context_limit_tokens") if model_entry else None
        ),
        cache_policy=model_entry["canonical"].get("cache_policy") if model_entry else None,
        evidence_class=(
            LAUNCH_UNIT["evidence_class"]
            if LAUNCH_UNIT
            else os.environ.get("SHALLOWSWE_EVIDENCE_CLASS") or None
        ),
        funding_pool=(
            LAUNCH_UNIT["funding_pool"]
            if LAUNCH_UNIT
            else os.environ.get("SHALLOWSWE_FUNDING_POOL") or None
        ),
        price_sheet_version=(Path(MANIFEST["price_sheet"]).name if MANIFEST.get("price_sheet") else None),
        routine_review_version=os.environ.get("SHALLOWSWE_ROUTINE_REVIEW_VERSION") or None,
        trajectory_id=trajectory.get("trajectory_id") if trajectory else None,
        launch_unit_id=LAUNCH_UNIT.get("launch_unit_id") if LAUNCH_UNIT else None,
        pilot_stage=LAUNCH_UNIT.get("stage") if LAUNCH_UNIT else None,
        pilot_mode=LAUNCH_UNIT.get("mode") if LAUNCH_UNIT else None,
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
    if LAUNCH_UNIT is not None:
        task_ids, seeds = launch_matrix(LAUNCH_UNIT)
    else:
        selected_tasks = os.environ.get("SHALLOWSWE_TASK_IDS")
        task_ids = (
            [task_id.strip() for task_id in selected_tasks.split(",") if task_id.strip()]
            if selected_tasks
            else list(MANIFEST["task_ids"])
        )
        seeds = list(range(int(os.environ.get("SHALLOWSWE_SEEDS", "1"))))
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
