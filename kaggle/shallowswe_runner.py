# %% [markdown]
# # ShallowSWE Kaggle repair-loop runner
#
# This notebook is a thin deployment entrypoint. The attached bundle is generated from the
# canonical ShallowSWE `tasks/` tree and contains pinned ShallowSWE and mini-swe-agent wheels.

# %%
from pathlib import Path
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request


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


GO_VERSION = "1.24.5"
GO_ARCHIVE_SHA256 = "10ad9e86233e74c0f6590fe5426895de6bf388964210eac34a6d83f38918ecdc"


def _install_go_runtime() -> Path:
    install_root = Path("/opt/shallowswe-toolchains") / f"go{GO_VERSION}"
    go_root = install_root / "go"
    if (go_root / "bin" / "go").is_file():
        return go_root
    install_root.mkdir(parents=True, exist_ok=True)
    archive = Path("/tmp") / f"go{GO_VERSION}.linux-amd64.tar.gz"
    urllib.request.urlretrieve(
        f"https://go.dev/dl/go{GO_VERSION}.linux-amd64.tar.gz",
        archive,
    )
    actual_sha256 = hashlib.sha256(archive.read_bytes()).hexdigest()
    if actual_sha256 != GO_ARCHIVE_SHA256:
        raise RuntimeError(
            "Go toolchain archive hash mismatch: "
            f"{actual_sha256} != {GO_ARCHIVE_SHA256}"
        )
    with tarfile.open(archive, "r:gz") as payload:
        payload.extractall(install_root, filter="data")
    archive.unlink()
    if not (go_root / "bin" / "go").is_file():
        raise RuntimeError(f"Go {GO_VERSION} toolchain extraction failed")
    return go_root


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
    os.environ["SHALLOWSWE_GO_ROOT"] = str(_install_go_runtime())
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
from shallowswe.kaggle_runtime import (  # noqa: E402
    is_kaggle_task_creation_placeholder,
    model_proxy_api,
)
from shallowswe.run_spec import (  # noqa: E402
    resolve_agent_policy,
    resolve_execution_options,
    resolve_execution_sampling,
    resolve_model_config,
    resolve_run_unit,
    trajectory_id,
    unit_matrix,
    validate_result_execution_identity,
)
from shallowswe.results import EXCLUDED_STATUS, load_prices  # noqa: E402


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
        expected_model_entry = next(
            entry
            for entry in RUN_SPEC["model_configs"]
            if entry["model_config_id"] == RUN_UNIT["model_config_id"]
        )
        expected_model = expected_model_entry["canonical"]["requested_model"]
        if is_kaggle_task_creation_placeholder(
            llm.name,
            expected_model=expected_model,
        ):
            kbench.assertions.assert_true(
                True,
                expectation=(
                    "Kaggle task creation completed without invoking its default "
                    "model placeholder."
                ),
            )
            return True
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
    upstream_provider = (
        model_entry["canonical"].get("upstream_provider")
        if model_entry is not None
        else None
    )
    proxy_api = model_proxy_api(
        llm.name,
        upstream_provider=upstream_provider,
    )
    canonical_model_name = (
        model_entry["canonical"]["requested_model"] if model_entry is not None else llm.name
    )
    transport_model_name = (
        model_entry["canonical"].get("model_proxy_slug", llm.name)
        if model_entry is not None
        else llm.name
    )
    price_model = (
        model_entry["canonical"].get("price_model") if model_entry is not None else llm.name
    )
    canonical_price = PRICE_CATALOG.get(price_model)
    if RUN_UNIT is not None and canonical_price is None:
        raise RuntimeError(f"Run price sheet does not contain model: {price_model}")
    temperature, task_suite_version = resolve_execution_sampling(
        RUN_SPEC if RUN_UNIT is not None else None,
        model_entry,
        fallback_temperature=float(os.environ.get("SHALLOWSWE_TEMPERATURE", "0")),
        fallback_task_suite_version=os.environ.get(
            "SHALLOWSWE_TASK_SUITE_VERSION",
            "shallowswe-kaggle-smoke-v0.1",
        ),
    )
    row = run_kaggle_repair_loop(
        llm=llm,
        task_path=BUNDLE_ROOT / task_entry["task_path"],
        verifier_dir=BUNDLE_ROOT / task_entry["verifier_path"],
        workspace_dir=run_root / "workspace",
        artifacts_dir=run_root / "artifacts",
        run_id=run_id,
        model_name=canonical_model_name,
        transport_model_name=transport_model_name,
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
        temperature=temperature,
        seed=rollout_seed,
        task_suite_version=task_suite_version,
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
        result_accounting=dict(RUN_UNIT.get("accounting") or {}) if RUN_UNIT else None,
        canonical_price=canonical_price,
        proxy_api=proxy_api,
    )
    if RUN_UNIT is not None:
        try:
            validate_result_execution_identity(row, RUN_SPEC, RUN_UNIT)
        except ValueError as error:
            row = replace(
                row,
                passed=False,
                stop_reason="execution_identity_mismatch",
                status=EXCLUDED_STATUS,
                exclusion_reason="runner_execution_identity_mismatch",
            )
            (run_root / "repair-loop-result.json").write_text(
                dump_kaggle_result(row)
            )
            raise RuntimeError(str(error)) from error
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
    if RUN_UNIT is not None:
        task_ids, seeds = unit_matrix(RUN_UNIT)
        execution = resolve_execution_options(RUN_SPEC, RUN_UNIT)
    else:
        selected_tasks = os.environ.get("SHALLOWSWE_TASK_IDS")
        task_ids = (
            [task_id.strip() for task_id in selected_tasks.split(",") if task_id.strip()]
            if selected_tasks
            else list(MANIFEST["task_ids"])
        )
        seeds = list(range(int(os.environ.get("SHALLOWSWE_SEEDS", "1"))))
        execution = {
            "n_jobs": int(os.environ.get("SHALLOWSWE_N_JOBS", "1")),
            "row_timeout_seconds": int(
                os.environ.get("SHALLOWSWE_ROW_TIMEOUT_SECONDS", "2700")
            ),
            "max_attempts": int(os.environ.get("SHALLOWSWE_MAX_ATTEMPTS", "2")),
            "retry_delay_seconds": int(os.environ.get("SHALLOWSWE_RETRY_DELAY_SECONDS", "15")),
        }
    evaluation_log_path = Path(
        os.environ.get(
            "SHALLOWSWE_EVALUATION_LOG_PATH",
            "/kaggle/working/shallowswe-evaluation.log",
        )
    )
    evaluation_log_path.parent.mkdir(parents=True, exist_ok=True)
    with evaluation_log_path.open("a", buffering=1) as evaluation_log:
        with redirect_stdout(evaluation_log), redirect_stderr(evaluation_log):
            with kbench.client.enable_cache():
                SHALLOWSWE_RUNS = shallowswe_repair_loop.evaluate(
                    llm=[kbench.llm],
                    task_id=task_ids,
                    rollout_seed=seeds,
                    n_jobs=execution["n_jobs"],
                    timeout=execution["row_timeout_seconds"],
                    on_failure="continue",
                    max_attempts=execution["max_attempts"],
                    retry_delay=execution["retry_delay_seconds"],
                )
    print(
        json.dumps(
            {
                "event": "shallowswe_evaluation_complete",
                "evaluation_log": str(evaluation_log_path),
                "result_count": len(SHALLOWSWE_RUNS),
            },
            sort_keys=True,
        ),
        flush=True,
    )

# %%
if os.environ.get("KAGGLE_KERNEL_RUN_TYPE"):
    get_ipython().run_line_magic("choose", "shallowswe_repair_loop")
