from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable
import hashlib
import json
import shlex
import shutil
import subprocess
import sys
import tempfile

from .mini_swe_config import effective_scaffold_prompt_hash, load_effective_mini_swe_config


KAGGLE_BUNDLE_SCHEMA_VERSION = "shallowswe.kaggle_bundle.v0.1"
SUPPORTED_BASE_IMAGE = "python:3.12-slim"


def export_kaggle_bundle(
    *,
    tasks_root: Path,
    output_dir: Path,
    task_ids: Iterable[str],
    config_file: Path,
    project_root: Path | None = None,
    mini_swe_agent_source_dir: Path | None = None,
    notebook_source: Path | None = None,
) -> dict[str, Any]:
    selected_task_ids = sorted(dict.fromkeys(str(task_id) for task_id in task_ids))
    if not selected_task_ids:
        raise ValueError("at least one task_id is required")
    if not config_file.is_file():
        raise ValueError(f"missing mini-swe-agent config: {config_file}")

    if output_dir.exists():
        shutil.rmtree(output_dir)
    (output_dir / "tasks").mkdir(parents=True)
    (output_dir / "verifiers").mkdir()
    (output_dir / "config").mkdir()

    task_entries: list[dict[str, Any]] = []
    for task_id in selected_task_ids:
        _validate_task_id(task_id)
        task_path = tasks_root / task_id
        _validate_task_path(task_path)
        validate_kaggle_task_environment(task_path)

        exported_task = output_dir / "tasks" / task_id
        exported_task.mkdir()
        shutil.copy2(task_path / "task.toml", exported_task / "task.toml")
        shutil.copy2(task_path / "instruction.md", exported_task / "instruction.md")
        shutil.copytree(task_path / "environment", exported_task / "environment")
        shutil.copytree(task_path / "tests", output_dir / "verifiers" / task_id)

        task_entries.append(
            {
                "task_id": task_id,
                "source_task_hash": tree_sha256(task_path),
                "instruction_hash": file_sha256(task_path / "instruction.md"),
                "environment_hash": tree_sha256(task_path / "environment"),
                "verifier_hash": tree_sha256(task_path / "tests"),
                "task_path": f"tasks/{task_id}",
                "verifier_path": f"verifiers/{task_id}",
            }
        )

    exported_config = output_dir / "config" / config_file.name
    shutil.copy2(config_file, exported_config)
    manifest = {
        "schema_version": KAGGLE_BUNDLE_SCHEMA_VERSION,
        "task_ids": selected_task_ids,
        "tasks": task_entries,
        "mini_swe_agent_config": f"config/{config_file.name}",
        "scaffold_prompt_hash": (
            effective_scaffold_prompt_hash(
                load_effective_mini_swe_config(
                    config_file,
                    base_config_file=(
                        mini_swe_agent_source_dir
                        / "src"
                        / "minisweagent"
                        / "config"
                        / "mini.yaml"
                    ),
                )
            )
            if mini_swe_agent_source_dir is not None
            else file_sha256(config_file)
        ),
        "source_of_truth": "tasks/",
    }
    runtime_values = (project_root, mini_swe_agent_source_dir, notebook_source)
    if any(value is not None for value in runtime_values):
        if any(value is None for value in runtime_values):
            raise ValueError(
                "project_root, mini_swe_agent_source_dir, and notebook_source "
                "must be provided together"
            )
        assert project_root is not None
        assert mini_swe_agent_source_dir is not None
        assert notebook_source is not None
        manifest["runtime"] = _export_runtime(
            output_dir=output_dir,
            project_root=project_root,
            mini_swe_agent_source_dir=mini_swe_agent_source_dir,
            notebook_source=notebook_source,
        )
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    return manifest


def _export_runtime(
    *,
    output_dir: Path,
    project_root: Path,
    mini_swe_agent_source_dir: Path,
    notebook_source: Path,
) -> dict[str, Any]:
    for path, label in (
        (project_root / "pyproject.toml", "ShallowSWE project"),
        (mini_swe_agent_source_dir / "pyproject.toml", "mini-swe-agent project"),
        (notebook_source, "Kaggle notebook source"),
    ):
        if not path.exists():
            raise ValueError(f"missing {label}: {path}")
    uv = shutil.which("uv")
    if uv is None:
        raise ValueError("uv is required to build the Kaggle runtime wheels")

    wheels_dir = output_dir / "wheels"
    wheels_dir.mkdir()
    subprocess.run(
        [uv, "build", "--wheel", "--out-dir", str(wheels_dir), str(project_root)],
        check=True,
    )
    with tempfile.TemporaryDirectory() as tmp:
        staged_mini_swe_agent = Path(tmp) / "mini-swe-agent"
        shutil.copytree(
            mini_swe_agent_source_dir,
            staged_mini_swe_agent,
            ignore=shutil.ignore_patterns(
                ".git",
                ".venv",
                ".mypy_cache",
                ".pytest_cache",
                ".ruff_cache",
                "__pycache__",
                "*.pyc",
                "*.egg-info",
                "dist",
                "build",
            ),
        )
        subprocess.run(
            [
                uv,
                "build",
                "--wheel",
                "--out-dir",
                str(wheels_dir),
                str(staged_mini_swe_agent),
            ],
            check=True,
        )
    (wheels_dir / ".gitignore").unlink(missing_ok=True)
    notebook_dir = output_dir / "notebook"
    notebook_dir.mkdir()
    exported_notebook = notebook_dir / notebook_source.name
    shutil.copy2(notebook_source, exported_notebook)
    requirements_source = notebook_source.parent / "requirements-runtime.txt"
    if not requirements_source.is_file():
        raise ValueError(f"missing Kaggle runtime requirements: {requirements_source}")
    exported_requirements = notebook_dir / requirements_source.name
    shutil.copy2(requirements_source, exported_requirements)
    return {
        "wheels": [
            f"wheels/{wheel.name}" for wheel in sorted(wheels_dir.glob("*.whl"))
        ],
        "notebook": f"notebook/{exported_notebook.name}",
        "requirements": f"notebook/{exported_requirements.name}",
        "mini_swe_agent_commit": (
            "8c3cfaee0ddb37c8325426990ff179c96690a1cf"
        ),
    }


def materialize_task_environment(task_path: Path, workspace: Path) -> None:
    _validate_task_path(task_path, require_tests=False)
    instructions = _dockerfile_instructions(task_path / "environment" / "Dockerfile")
    environment = task_path / "environment"
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)

    staged_paths: dict[str, Path] = {}
    for instruction, arguments in instructions:
        if instruction == "FROM":
            if arguments != SUPPORTED_BASE_IMAGE:
                _unsupported(instruction, arguments)
            continue
        if instruction == "WORKDIR":
            if arguments != "/app":
                _unsupported(instruction, arguments)
            continue
        if instruction == "ENV":
            if arguments != "PYTHONPATH=/app":
                _unsupported(instruction, arguments)
            continue
        if instruction == "COPY":
            source_name, destination = _copy_arguments(arguments)
            source = environment / source_name
            if not source.exists():
                raise ValueError(f"Dockerfile COPY source does not exist: {source_name}")
            if destination.startswith("/app"):
                relative_destination = destination.removeprefix("/app").lstrip("/")
                target = workspace / relative_destination
                _copy_docker_source(source, target)
            elif destination.startswith("/tmp/") and source.is_file():
                staged_paths[destination] = source
            else:
                _unsupported(instruction, arguments)
            continue
        if instruction == "RUN":
            tokens = shlex.split(arguments)
            if len(tokens) == 3 and tokens[0] in {"python", "python3"} and tokens[2] == "/app":
                generator = staged_paths.get(tokens[1])
                if generator is None:
                    _unsupported(instruction, arguments)
                subprocess.run(
                    [sys.executable, str(generator.resolve()), str(workspace)],
                    check=True,
                    cwd=environment,
                )
            else:
                _unsupported(instruction, arguments)
            continue
        _unsupported(instruction, arguments)


def validate_kaggle_task_environment(task_path: Path) -> None:
    with _temporary_workspace() as workspace:
        materialize_task_environment(task_path, workspace)


def _dockerfile_instructions(path: Path) -> list[tuple[str, str]]:
    if not path.is_file():
        raise ValueError(f"missing task Dockerfile: {path}")
    parsed: list[tuple[str, str]] = []
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        instruction, separator, arguments = line.partition(" ")
        if not separator or not arguments.strip():
            _unsupported(instruction.upper(), arguments)
        parsed.append((instruction.upper(), arguments.strip()))
    return parsed


def _copy_arguments(arguments: str) -> tuple[str, str]:
    tokens = shlex.split(arguments)
    if len(tokens) != 2 or tokens[0].startswith("--"):
        _unsupported("COPY", arguments)
    return tokens[0], tokens[1]


def _copy_docker_source(source: Path, target: Path) -> None:
    if source.is_dir():
        target.mkdir(parents=True, exist_ok=True)
        for child in source.iterdir():
            child_target = target / child.name
            if child.is_dir():
                shutil.copytree(child, child_target, dirs_exist_ok=True)
            else:
                child_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(child, child_target)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _validate_task_id(task_id: str) -> None:
    if not task_id or Path(task_id).name != task_id or task_id in {".", ".."}:
        raise ValueError(f"invalid task_id: {task_id!r}")


def _validate_task_path(task_path: Path, *, require_tests: bool = True) -> None:
    required = ["task.toml", "instruction.md", "environment"]
    if require_tests:
        required.append("tests")
    missing = [name for name in required if not (task_path / name).exists()]
    if missing:
        raise ValueError(f"task {task_path} is missing: {', '.join(missing)}")


def _unsupported(instruction: str, arguments: str) -> None:
    raise ValueError(
        "unsupported Kaggle Dockerfile instruction: "
        f"{instruction}{f' {arguments}' if arguments else ''}"
    )


class _temporary_workspace:
    def __enter__(self) -> Path:
        from tempfile import TemporaryDirectory

        self._temporary_directory = TemporaryDirectory()
        return Path(self._temporary_directory.name) / "workspace"

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self._temporary_directory.cleanup()


def file_sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def tree_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        hasher.update(item.relative_to(path).as_posix().encode())
        hasher.update(b"\0")
        hasher.update(item.read_bytes())
        hasher.update(b"\0")
    return f"sha256:{hasher.hexdigest()}"
