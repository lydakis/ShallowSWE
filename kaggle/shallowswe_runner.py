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


FROZEN_RUN_UNIT_ID: str | None = None


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
        if payload.get("schema_version") in {
            "shallowswe.kaggle_bundle.v0.1",
            "shallowswe.kaggle_bundle.v0.2",
        }:
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
from shallowswe.run_spec import (  # noqa: E402
    resolve_agent_policy,
    resolve_model_config,
    resolve_run_unit,
    trajectory_id,
    unit_matrix,
)
from shallowswe.results import load_prices  # noqa: E402


MANIFEST = json.loads((BUNDLE_ROOT / "manifest.json").read_text())
TASK_INDEX = {entry["task_id"]: entry for entry in MANIFEST["tasks"]}
PRICE_CATALOG = (
    load_prices(BUNDLE_ROOT / MANIFEST["price_sheet"])
    if MANIFEST.get("price_sheet")
    else {}
)
PRICE_PAYLOAD = (
    json.loads((BUNDLE_ROOT / MANIFEST["price_sheet"]).read_text())
    if MANIFEST.get("price_sheet")
    else {}
)
RUN_SPEC = (
    json.loads((BUNDLE_ROOT / MANIFEST["run_spec"]).read_text())
    if MANIFEST.get("run_spec")
    else None
)
RUN_UNIT = None
if RUN_SPEC is not None:
    environment_run_unit_id = os.environ.get("SHALLOWSWE_RUN_UNIT_ID")
    if (
        environment_run_unit_id
        and FROZEN_RUN_UNIT_ID
        and environment_run_unit_id != FROZEN_RUN_UNIT_ID
    ):
        raise RuntimeError("Environment run-unit ID disagrees with frozen task source")
    run_unit_id = environment_run_unit_id or FROZEN_RUN_UNIT_ID
    if os.environ.get("KAGGLE_KERNEL_RUN_TYPE") and not run_unit_id:
        raise RuntimeError("SHALLOWSWE_RUN_UNIT_ID is required for a run-spec bundle")
    if run_unit_id:
        RUN_UNIT = resolve_run_unit(RUN_SPEC, run_unit_id)
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
    agent_policy = None
    if RUN_SPEC is not None and RUN_UNIT is not None:
        model_entry = resolve_model_config(
            RUN_SPEC,
            RUN_UNIT,
            observed_model=llm.name,
        )
        agent_policy = resolve_agent_policy(RUN_SPEC, RUN_UNIT)
    registered_trajectory_id = None
    if RUN_UNIT is not None:
        registered_trajectory_id = trajectory_id(
            RUN_SPEC,
            RUN_UNIT,
            task_id=task_id,
            rollout_seed=rollout_seed,
        )
    run_id = (
        registered_trajectory_id
        if registered_trajectory_id is not None
        else f"{task_id}__seed-{rollout_seed:02d}"
    )
    run_root = RESULTS_ROOT / run_id
    limits = RUN_UNIT["limits"] if RUN_UNIT else None
    native_llm = load_model(llm.name, api=model_proxy_api(llm.name))
    price_model = (
        model_entry["canonical"].get("price_model") if model_entry is not None else llm.name
    )
    canonical_price = PRICE_CATALOG.get(price_model)
    if RUN_UNIT is not None and canonical_price is None:
        raise RuntimeError(f"Run price sheet does not contain model: {price_model}")
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
            int(limits["verifier_submissions"])
            if limits is not None
            else int(os.environ.get("SHALLOWSWE_MAX_VERIFIER_SUBMISSIONS", "3"))
        ),
        agent_step_cap=(int(limits["agent_steps"]) if limits is not None else None),
        dollar_cap_usd=(
            float(limits["dollar_usd"])
            if limits and limits.get("dollar_usd") is not None
            else float(os.environ["SHALLOWSWE_DOLLAR_CAP_USD"])
            if os.environ.get("SHALLOWSWE_DOLLAR_CAP_USD") and RUN_UNIT is None
            else None
        ),
        wall_time_cap_seconds=(
            int(limits["wall_time_seconds"])
            if limits is not None
            else int(os.environ.get("SHALLOWSWE_WALL_TIME_CAP_SECONDS", "2400"))
        ),
        reasoning_effort=(
            model_entry["canonical"].get("reasoning_effort")
            if model_entry
            else os.environ.get("SHALLOWSWE_REASONING_EFFORT") or None
        ),
        temperature=float(os.environ.get("SHALLOWSWE_TEMPERATURE", "0")),
        seed=rollout_seed,
        task_suite_version=os.environ.get(
            "SHALLOWSWE_TASK_SUITE_VERSION",
            RUN_SPEC["task_suite_version"] if RUN_SPEC else "shallowswe-kaggle-smoke-v0.1",
        ),
        repo_commit_sha=os.environ.get("SHALLOWSWE_REPO_COMMIT_SHA") or None,
        model_config_id=model_entry.get("model_config_id") if model_entry else None,
        model_config_canonical_json=model_entry.get("canonical") if model_entry else None,
        agent_policy_id=agent_policy.get("agent_policy_id") if agent_policy else None,
        agent_policy_canonical_json=agent_policy.get("canonical") if agent_policy else None,
        provider_route=(
            model_entry["canonical"]["provider_route"] if model_entry else "kaggle_model_proxy"
        ),
        context_limit=(
            model_entry["canonical"].get("model_context_limit_tokens") if model_entry else None
        ),
        cache_policy=model_entry["canonical"].get("cache_policy") if model_entry else None,
        price_sheet_version=(Path(MANIFEST["price_sheet"]).stem if MANIFEST.get("price_sheet") else None),
        price_sheet_date=str(PRICE_PAYLOAD.get("effective_date") or "") or None,
        routine_review_version=os.environ.get("SHALLOWSWE_ROUTINE_REVIEW_VERSION") or None,
        trajectory_id=registered_trajectory_id,
        experiment_id=RUN_SPEC.get("experiment_id") if RUN_SPEC else None,
        run_spec_id=RUN_SPEC.get("run_spec_id") if RUN_SPEC else None,
        run_unit_id=RUN_UNIT.get("run_unit_id") if RUN_UNIT else None,
        run_metadata=dict(RUN_UNIT.get("metadata") or {}) if RUN_UNIT else None,
        canonical_price=canonical_price,
    )
    (run_root / "repair-loop-result.json").write_text(dump_kaggle_result(row))
    if RUN_UNIT is not None:
        expected_resolved = model_entry["canonical"].get("expected_resolved_model")
        if row.resolved_model is None:
            raise RuntimeError("Official ShallowSWE row is missing resolved-model identity")
        if row.resolved_model != expected_resolved:
            raise RuntimeError(
                "Official ShallowSWE resolved-model mismatch: "
                f"expected {expected_resolved!r}, got {row.resolved_model!r}"
            )
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
    if RUN_UNIT is not None:
        task_ids, seeds = unit_matrix(RUN_UNIT)
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
