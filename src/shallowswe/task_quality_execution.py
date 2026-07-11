from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json
import platform
import subprocess

from .task_quality import TASK_QUALITY_EXECUTION_SCHEMA_VERSION, quality_artifact_hashes


RUN_MARKER = "SHALLOWSWE_VERIFIER_EXIT="
ARTIFACT_MARKER = "SHALLOWSWE_ARTIFACT_SHA256="


def execute_task_quality(
    task_path: Path,
    *,
    reference_runs: int = 3,
) -> dict[str, Any]:
    task_path = task_path.resolve()
    task_id = task_path.name
    controls = _load_controls(task_path)
    image = f"shallowswe-quality/{task_id}:local"

    _run_checked(
        [
            "container",
            "build",
            "--progress",
            "plain",
            "-t",
            image,
            str(task_path / "environment"),
        ],
        label=f"build {task_id}",
    )
    runtime_version = _run_checked(["container", "--version"], label="container version").strip()
    image_inspect = json.loads(
        _run_checked(["container", "image", "inspect", image], label=f"inspect {task_id}")
    )
    image_digest = image_inspect[0]["configuration"]["descriptor"]["digest"]

    runs: list[dict[str, Any]] = []
    for attempt in range(1, reference_runs + 1):
        runs.append(
            _execute_run(
                task_path,
                image,
                kind="reference_solution",
                attempt=attempt,
                solution_dir="solution",
            )
        )
    runs.append(
        _execute_run(
            task_path,
            image,
            kind="alternate_solution",
            attempt=1,
            solution_dir="solution_alt",
        )
    )
    for control in controls:
        runs.append(
            _execute_run(
                task_path,
                image,
                kind="negative_control",
                attempt=1,
                solution_dir="solution" if control["baseline"] == "reference" else None,
                control=control,
            )
        )

    failures = [
        run
        for run in runs
        if (run["kind"] == "negative_control" and run["exit_code"] == 0)
        or (run["kind"] != "negative_control" and run["exit_code"] != 0)
        or not run["verifier_reached"]
    ]
    payload = {
        "schema_version": TASK_QUALITY_EXECUTION_SCHEMA_VERSION,
        "task_id": task_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runtime": {
            "backend": "apple_container",
            "version": runtime_version,
            "platform": f"linux/{platform.machine()}",
            "image": image,
            "image_digest": image_digest,
            "network_policy": "disabled",
        },
        "artifact_hashes": quality_artifact_hashes(task_path),
        "runs": runs,
        "quality_outcome": "pass" if not failures else "fail",
    }
    output_path = task_path / "quality" / "executions.json"
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    if failures:
        raise RuntimeError(f"task-quality execution failed for {task_id}: {failures}")
    return payload


def _execute_run(
    task_path: Path,
    image: str,
    *,
    kind: str,
    attempt: int,
    solution_dir: str | None,
    control: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mounts = [
        _mount(task_path / "tests", "/tests"),
        _mount(task_path / "quality", "/quality"),
    ]
    setup_commands: list[str] = []
    logical_commands: list[str] = []
    if solution_dir:
        mounts.append(_mount(task_path / solution_dir, "/solution"))
        setup_commands.append("bash /solution/solve.sh")
        logical_commands.append(f"{solution_dir}/solve.sh")
    if control and control.get("setup"):
        setup_path = str(control["setup"])
        setup_commands.append(f"bash /{setup_path}")
        logical_commands.append(setup_path)

    script = "set -e; " + "; ".join(setup_commands + [
        "set +e",
        "bash /tests/test.sh",
        "rc=$?",
        (
            "artifact=$(find /app -type f ! -path '*/__pycache__/*' ! -name '*.pyc' "
            "-print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}')"
        ),
        f"printf '{ARTIFACT_MARKER}%s\\n' \"$artifact\"",
        f"printf '\\n{RUN_MARKER}%s\\n' \"$rc\"",
        "exit \"$rc\"",
    ])
    command = ["container", "run", "--rm", "--network", "none"]
    for mount in mounts:
        command.extend(["--mount", mount])
    command.extend([image, "bash", "-lc", script])
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    verifier_exit = _extract_verifier_exit(result.stdout)
    artifact_hash = _extract_marker(result.stdout, ARTIFACT_MARKER)
    return {
        "kind": kind,
        "control_id": control.get("id") if control else None,
        "attempt": attempt,
        "command": " && ".join([*logical_commands, "tests/test.sh"]),
        "exit_code": verifier_exit if verifier_exit is not None else result.returncode,
        "container_exit_code": result.returncode,
        "verifier_reached": verifier_exit is not None,
        "clean_sandbox": True,
        "output_sha256": f"sha256:{hashlib.sha256(result.stdout.encode()).hexdigest()}",
        "artifact_sha256": f"sha256:{artifact_hash}" if artifact_hash else "sha256:missing",
    }


def _load_controls(task_path: Path) -> list[dict[str, Any]]:
    payload = json.loads((task_path / "quality" / "negative-controls.json").read_text())
    controls = payload.get("negative_controls")
    if not isinstance(controls, list) or not controls:
        raise ValueError(f"missing negative controls for {task_path.name}")
    for control in controls:
        if not isinstance(control, dict) or control.get("baseline") not in {"base", "reference"}:
            raise ValueError(f"invalid negative control for {task_path.name}: {control}")
        setup = control.get("setup")
        if setup is not None and not (task_path / str(setup)).is_file():
            raise ValueError(f"missing negative-control setup for {task_path.name}: {setup}")
    return controls


def _mount(source: Path, target: str) -> str:
    return f"type=bind,source={source.resolve()},target={target},readonly"


def _extract_verifier_exit(output: str) -> int | None:
    value = _extract_marker(output, RUN_MARKER)
    return int(value) if value is not None else None


def _extract_marker(output: str, marker: str) -> str | None:
    for line in reversed(output.splitlines()):
        if line.startswith(marker):
            return line.removeprefix(marker)
    return None


def _run_checked(command: list[str], *, label: str) -> str:
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode != 0:
        raise RuntimeError(f"{label} failed ({result.returncode}):\n{result.stdout}")
    return result.stdout
