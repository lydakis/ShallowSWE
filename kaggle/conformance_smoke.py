# %% [markdown]
# # ShallowSWE Kaggle repair-loop conformance smoke
#
# This no-provider smoke exercises the production Kaggle runner, sandbox, hidden verifier,
# sanitized repair continuation, result schema, and artifacts with a deterministic scripted chat.

# %%
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys


def _find_bundle() -> Path:
    for manifest in Path("/kaggle/input").rglob("manifest.json"):
        try:
            payload = json.loads(manifest.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("schema_version") == "shallowswe.kaggle_bundle.v0.1":
            return manifest.parent
    raise RuntimeError("Attached ShallowSWE bundle was not found")


def _prepare_bundle(source: Path) -> Path:
    if (source / "wheels").is_dir():
        return source
    target = Path("/kaggle/working/shallowswe-conformance-bundle")
    if target.exists():
        shutil.rmtree(target)
    target.mkdir()
    for item in source.iterdir():
        if item.suffix == ".zip":
            destination = target / item.stem
            destination.mkdir()
            shutil.unpack_archive(item, destination)
        elif item.is_file():
            shutil.copy2(item, target / item.name)
    return target


def _install_runtime(bundle: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--quiet",
            "-r",
            str(bundle / "notebook" / "requirements-runtime.txt"),
        ],
        check=True,
    )
    wheels = sorted((bundle / "wheels").glob("*.whl"))
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
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv is required for the Python 3.12 sandbox runtime")
    subprocess.run([uv, "python", "install", "3.12", "--no-progress"], check=True)
    os.environ["SHALLOWSWE_SANDBOX_PYTHON"] = subprocess.check_output(
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
    if shutil.which("busybox") is None:
        subprocess.run(["apt-get", "update", "-qq"], check=True)
        subprocess.run(
            ["apt-get", "install", "-y", "-qq", "busybox-static", "libseccomp2"],
            check=True,
        )


BUNDLE_ROOT = _prepare_bundle(_find_bundle())
_install_runtime(BUNDLE_ROOT)

# %%
import kaggle_benchmarks as kbench  # noqa: E402
from kaggle_benchmarks.actors.llms import LLMChat, LLMResponse  # noqa: E402
from IPython import get_ipython  # noqa: E402

from shallowswe.kaggle_repair_loop import (  # noqa: E402
    dump_kaggle_result,
    run_kaggle_repair_loop,
)


class _ScriptedRepairLLM(LLMChat):
    def __init__(self) -> None:
        super().__init__(name="conformance/scripted", support_temperature=True)
        self.commands = [
            "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT",
            (
                "printf 'def normalize_username(value: str) -> str:\\n"
                "    return value.strip().lower()\\n' > usernames.py"
            ),
            "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT",
        ]

    def invoke(self, messages, system, tools=None, **kwargs):
        del messages, system, tools, kwargs
        command = self.commands.pop(0)
        return LLMResponse(
            content="Executing the deterministic conformance action.",
            tool_calls=[
                {
                    "id": f"conformance-{len(self.commands)}",
                    "function": {
                        "name": "bash",
                        "arguments": json.dumps({"command": command}),
                    },
                }
            ],
            meta={"input_tokens": 1, "output_tokens": 1},
        )


@kbench.task(
    name="shallowswe-repair-loop-conformance",
    description="Verify the production ShallowSWE Kaggle repair-loop contract end to end.",
)
def shallowswe_repair_loop_conformance(llm) -> bool:
    del llm
    manifest = json.loads((BUNDLE_ROOT / "manifest.json").read_text())
    task = manifest["tasks"][0]
    run_root = Path("/kaggle/working/shallowswe-conformance")
    row = run_kaggle_repair_loop(
        llm=_ScriptedRepairLLM(),
        task_path=BUNDLE_ROOT / task["task_path"],
        verifier_dir=BUNDLE_ROOT / task["verifier_path"],
        workspace_dir=run_root / "workspace",
        artifacts_dir=run_root / "artifacts",
        run_id="kaggle-conformance",
        model_name="conformance/scripted",
        config_file=BUNDLE_ROOT / manifest["mini_swe_agent_config"],
        max_verifier_submissions=3,
        wall_time_cap_seconds=300,
        task_suite_version="shallowswe-kaggle-conformance-v0.1",
    )
    (run_root / "repair-loop-result.json").write_text(dump_kaggle_result(row))
    kbench.assertions.assert_true(
        row.passed and row.verifier_submissions == 2,
        expectation="The same agent should pass after one sanitized repair continuation.",
    )
    return row.passed and row.verifier_submissions == 2


# %%
SHALLOWSWE_CONFORMANCE_RUN = shallowswe_repair_loop_conformance.run(llm=kbench.llm)

# %%
get_ipython().run_line_magic("choose", "shallowswe_repair_loop_conformance")
