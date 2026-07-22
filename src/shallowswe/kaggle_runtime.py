from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import threading
import time

from pydantic import BaseModel, ConfigDict
from kaggle_benchmarks.tools.base import ToolInvocationResult

from .repair_loop_protocol import VerifierClass, VerifierOutcome
from .results import ModelPrice, usage_cost_usd


_CHROOT_TEMPLATE_LOCK = threading.Lock()


DEFAULT_OBSERVATION_TEMPLATE = (
    "{% if output.output | length < 10000 %}"
    '{"returncode": {{ output.returncode }}, "output": {{ output.output | tojson }}'
    "{% if output.exception_info %}, \"exception_info\": "
    "{{ output.exception_info | tojson }}{% endif %}}"
    "{% else %}"
    '{"returncode": {{ output.returncode }}, '
    '"output_head": {{ output.output[:5000] | tojson }}, '
    '"output_tail": {{ output.output[-5000:] | tojson }}, '
    '"elided_chars": {{ output.output | length - 10000 }}}'
    "{% endif %}"
)

DEFAULT_FORMAT_ERROR_TEMPLATE = (
    "Tool call error:\n\n<error>{{error}}</error>\n\n"
    "Every response must call the bash tool with a command argument."
)
KAGGLE_TASK_CREATION_PLACEHOLDER_MODEL = "google/gemini-3-flash-preview"


def is_kaggle_task_creation_placeholder(
    observed_model: str,
    *,
    expected_model: str,
) -> bool:
    """Recognize Kaggle's creation-only default without invoking it."""
    return (
        observed_model == KAGGLE_TASK_CREATION_PLACEHOLDER_MODEL
        and observed_model != expected_model
    )


def model_proxy_api(
    model_name: str,
    *,
    upstream_provider: str | None = None,
) -> str:
    """Select the provider-native Kaggle Model Proxy API for tool continuation."""
    if upstream_provider is not None:
        return "genai" if upstream_provider.lower() == "google" else "openai"
    return "genai" if model_name.startswith("google/") else "openai"


def model_kwargs_for_proxy(
    model_name: str,
    model_kwargs: dict[str, Any],
    *,
    proxy_api: str | None = None,
) -> dict[str, Any]:
    """Keep kwargs in the common form accepted by Kaggle's benchmark actor.

    Kaggle routes both OpenAI and Google benchmark chats through its ``LLMChat``
    compatibility layer. That layer accepts ``max_tokens`` and performs any
    provider-specific translation itself. Passing the Google SDK spelling
    ``max_output_tokens`` leaks through to its OpenAI-compatible chat client and
    fails before inference.
    """
    normalized = dict(model_kwargs)
    del model_name, proxy_api
    return normalized


class KaggleBenchmarksModelConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    model_name: str
    seed: int = 0
    temperature: float = 0.0
    reasoning: str | None = None
    observation_template: str = DEFAULT_OBSERVATION_TEMPLATE
    format_error_template: str = DEFAULT_FORMAT_ERROR_TEMPLATE
    model_kwargs: dict[str, Any] = {}
    multimodal_regex: str = ""


class KaggleBenchmarksModel:
    """mini-swe-agent model adapter over the active Kaggle Benchmarks chat."""

    def __init__(
        self,
        *,
        llm: Any,
        canonical_price: ModelPrice | None = None,
        proxy_api: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.llm = llm
        self.canonical_price = canonical_price
        self.config = KaggleBenchmarksModelConfig(**kwargs)
        self.config.model_kwargs = model_kwargs_for_proxy(
            self.config.model_name,
            self.config.model_kwargs,
            proxy_api=proxy_api,
        )
        self._synced_message_count = 0
        runner_model_name = getattr(llm, "name", None)
        self._runner_model_name: str | None = (
            runner_model_name
            if isinstance(runner_model_name, str) and runner_model_name
            else None
        )
        self._resolved_model_names: set[str] = set()

    def query(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        del kwargs
        self._sync_new_messages(messages)
        request_kwargs = {
            "tools": [bash],
            "seed": self.config.seed,
            "reasoning": self.config.reasoning,
            **self.config.model_kwargs,
        }
        if getattr(self.llm, "support_temperature", True):
            request_kwargs["temperature"] = self.config.temperature
        response = self.llm.respond(**request_kwargs)
        if not response.text and not response.tool_calls:
            # Kaggle records a provider's empty response in the active chat before
            # mini-swe-agent can turn it into a format-error retry. The GenAI
            # serializer represents that blank assistant turn as an empty Part,
            # which Gemini rejects on the next request. Keep the turn in the
            # transcript for diagnostics, but omit it from subsequent model input.
            response.is_visible_to_llm = False
        self._capture_resolved_model(getattr(response, "_meta", {}))
        actions, raw_tool_calls = self._parse_actions(response.tool_calls)
        usage = response.usage
        cost_nanodollars = usage.total_cost_nanodollars
        gateway_cost_usd = (
            cost_nanodollars / 1_000_000_000 if cost_nanodollars is not None else 0.0
        )
        canonical_cost_usd = (
            usage_cost_usd(
                input_tokens=int(usage.input_tokens or 0),
                output_tokens=int(usage.output_tokens or 0),
                cache_read_tokens=0,
                cache_write_tokens=0,
                peak_context_tokens=int(usage.input_tokens or 0),
                price=self.canonical_price,
            )
            if self.canonical_price is not None
            else gateway_cost_usd
        )
        return {
            "role": "assistant",
            "content": response.text,
            "tool_calls": raw_tool_calls,
            "extra": {
                "actions": actions,
                # mini-swe-agent uses this field for its runtime cost guard. Keep
                # it on the same canonical basis used to select task budget B_t.
                "cost": canonical_cost_usd,
                "timestamp": time.time(),
                "usage": {
                    "input_tokens": usage.input_tokens or 0,
                    "output_tokens": usage.output_tokens or 0,
                    # Preserve Kaggle's reported invoice separately for result
                    # accounting and price-basis comparisons.
                    "cost": gateway_cost_usd,
                },
                **(
                    {"reasoning_traces": response.reasoning_traces}
                    if response.reasoning_traces
                    else {}
                ),
            },
        }

    @property
    def resolved_model(self) -> str | None:
        if not self._resolved_model_names:
            return self._runner_model_name
        if len(self._resolved_model_names) != 1:
            return None
        return next(iter(self._resolved_model_names))

    def _capture_resolved_model(self, source: Any) -> None:
        keys = ("resolved_model", "response_model", "model_version", "model_name", "model")
        for key in keys:
            value = source.get(key) if isinstance(source, dict) else getattr(source, key, None)
            if isinstance(value, str) and value:
                self._resolved_model_names.add(value)

    def format_message(self, **kwargs: Any) -> dict[str, Any]:
        from minisweagent.models.utils.openai_multimodal import expand_multimodal_content

        return expand_multimodal_content(kwargs, pattern=self.config.multimodal_regex)

    def format_observation_messages(
        self,
        message: dict[str, Any],
        outputs: list[dict[str, Any]],
        template_vars: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        from kaggle_benchmarks import actors
        from minisweagent.models.utils.actions_toolcall import (
            format_toolcall_observation_messages,
        )

        actions = message.get("extra", {}).get("actions", [])
        rendered = format_toolcall_observation_messages(
            actions=actions,
            outputs=outputs,
            observation_template=self.config.observation_template,
            template_vars=template_vars,
            multimodal_regex=self.config.multimodal_regex,
        )
        for index, action in enumerate(actions):
            # Kaggle's chat actor serializes ToolInvocationResult.output directly
            # into the next provider request. Send the already-rendered observation,
            # not the raw environment result: the latter can contain tens of
            # megabytes even though mini-swe-agent correctly elides it for the
            # trajectory. Keeping these two views aligned also prevents a provider
            # request from exceeding Kaggle's per-input-part limit.
            output = rendered[index].get("content", "")
            actors.Tool(name="bash").send(
                ToolInvocationResult(
                    name="bash",
                    arguments={"command": action["command"]},
                    call_id=action.get("tool_call_id"),
                    output=output,
                )
            )
        return rendered

    def get_template_vars(self, **kwargs: Any) -> dict[str, Any]:
        return self.config.model_dump() | kwargs

    def serialize(self) -> dict[str, Any]:
        return {
            "info": {
                "config": {
                    "model": self.config.model_dump(mode="json"),
                    "model_type": (
                        "shallowswe.kaggle_runtime.KaggleBenchmarksModel"
                    ),
                }
            }
        }

    def _sync_new_messages(self, messages: list[dict[str, Any]]) -> None:
        from kaggle_benchmarks import actors

        for message in messages[self._synced_message_count :]:
            role = message.get("role")
            content = message.get("content", "")
            if role == "system":
                actors.system.send(content)
            elif role == "user":
                actors.user.send(content)
            # Assistant responses and tool results were already emitted by respond() and
            # format_observation_messages(). Exit messages are trajectory-only.
        self._synced_message_count = len(messages)

    def _parse_actions(self, tool_calls: list[Any] | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        from jinja2 import StrictUndefined, Template
        from minisweagent.exceptions import FormatError

        if not tool_calls:
            raise FormatError(
                {
                    "role": "user",
                    "content": Template(
                        self.config.format_error_template,
                        undefined=StrictUndefined,
                    ).render(
                        error=(
                            "No tool calls found in the response. Every response must include "
                            "at least one bash tool call."
                        ),
                        actions=[],
                    ),
                    "extra": {"interrupt_type": "FormatError"},
                }
            )

        actions: list[dict[str, Any]] = []
        raw_tool_calls: list[dict[str, Any]] = []
        for call in tool_calls:
            if isinstance(call, dict):
                function = call.get("function") or {}
                name = function.get("name")
                arguments = function.get("arguments") or {}
                call_id = call.get("id")
            else:
                name = call.name
                arguments = call.arguments
                call_id = call.call_id
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    pass
            error = ""
            if name != "bash":
                error = f"Unknown tool {name!r}."
            elif not isinstance(arguments, dict) or not isinstance(
                arguments.get("command"), str
            ):
                error = "Missing string command argument in bash tool call."
            if error:
                raise FormatError(
                    {
                        "role": "user",
                        "content": Template(
                            self.config.format_error_template,
                            undefined=StrictUndefined,
                        ).render(error=error, actions=[]),
                        "extra": {"interrupt_type": "FormatError"},
                    }
                )
            command = arguments["command"]
            actions.append({"command": command, "tool_call_id": call_id})
            raw_tool_calls.append(
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": "bash", "arguments": json.dumps(arguments)},
                }
            )
        return actions, raw_tool_calls


def bash(command: str) -> str:
    """Execute a bash command in the isolated ShallowSWE task workspace."""

    raise RuntimeError(
        "The ShallowSWE harness executes bash calls; Kaggle must not invoke this function directly."
    )


class KaggleSandboxEnvironmentConfig(BaseModel):
    workspace: str
    timeout: int = 30
    executable: str = "chroot"
    rootfs: str | None = None
    sandbox_uid: int = 65534
    sandbox_gid: int = 65534
    env: dict[str, str] = {}


class KaggleSandboxEnvironment:
    def __init__(self, **kwargs: Any) -> None:
        self.config = KaggleSandboxEnvironmentConfig(**kwargs)
        workspace = Path(self.config.workspace)
        rootfs = Path(self.config.rootfs) if self.config.rootfs else workspace.parent / ".agent-rootfs"
        self.rootfs = rootfs
        self.host_workspace = workspace
        self.task_workspace = rootfs / "app"
        prepare_chroot_environment(
            rootfs=rootfs,
            workspace=workspace,
            uid=self.config.sandbox_uid,
            gid=self.config.sandbox_gid,
        )

    def execute(
        self,
        action: dict[str, Any],
        cwd: str = "",
        *,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        del cwd
        command = str(action.get("command", ""))
        try:
            result = subprocess.run(
                build_chroot_command(
                    rootfs=self.rootfs,
                    command=command,
                    executable=self.config.executable,
                    env=self.config.env,
                    sandbox_uid=self.config.sandbox_uid,
                    sandbox_gid=self.config.sandbox_gid,
                ),
                text=True,
                timeout=timeout or self.config.timeout,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            output = {
                "output": result.stdout,
                "returncode": result.returncode,
                "exception_info": "",
            }
        except Exception as exc:
            raw_output = getattr(exc, "output", None)
            output = {
                "output": raw_output if isinstance(raw_output, str) else "",
                "returncode": -1,
                "exception_info": f"An error occurred while executing the command: {exc}",
                "extra": {"exception_type": type(exc).__name__, "exception": str(exc)},
            }
        self._check_finished(output)
        return output

    def export_workspace(self) -> None:
        if self.host_workspace.exists():
            shutil.rmtree(self.host_workspace)
        shutil.copytree(self.task_workspace, self.host_workspace)
        shutil.rmtree(self.rootfs)

    def _check_finished(self, output: dict[str, Any]) -> None:
        from minisweagent.exceptions import Submitted

        lines = str(output.get("output", "")).lstrip().splitlines(keepends=True)
        if (
            lines
            and lines[0].strip() == "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"
            and output["returncode"] == 0
        ):
            submission = "".join(lines[1:])
            raise Submitted(
                {
                    "role": "exit",
                    "content": submission,
                    "extra": {"exit_status": "Submitted", "submission": submission},
                }
            )

    def get_template_vars(self, **kwargs: Any) -> dict[str, Any]:
        return self.config.model_dump() | platform.uname()._asdict() | kwargs

    def serialize(self) -> dict[str, Any]:
        return {
            "info": {
                "config": {
                    "environment": self.config.model_dump(mode="json"),
                    "environment_type": (
                        "shallowswe.kaggle_runtime.KaggleSandboxEnvironment"
                    ),
                }
            }
        }


def build_chroot_command(
    *,
    rootfs: Path,
    command: str,
    executable: str = "chroot",
    env: dict[str, str] | None = None,
    sandbox_uid: int = 65534,
    sandbox_gid: int = 65534,
) -> list[str]:
    if not (rootfs / "app").is_dir():
        raise ValueError(f"missing Kaggle chroot task workspace: {rootfs / 'app'}")
    selected_env = {
        "HOME": "/home/sandbox",
        "LANG": "C.UTF-8",
        "PATH": "/opt/go/bin:/opt/python/bin:/usr/bin:/bin",
        "PYTHONHOME": "/opt/python",
        "PYTHONPATH": "/app",
        "GOCACHE": "/tmp/go-build",
        "GOMODCACHE": "/tmp/go-mod",
        "GOROOT": "/opt/go",
        "GOTOOLCHAIN": "local",
        "CGO_ENABLED": "0",
        **(env or {}),
    }
    env_args = [f"{key}={value}" for key, value in selected_env.items()]
    return [
        str(Path(sys.executable).absolute()),
        "-m",
        "shallowswe.sandbox_exec",
        "--",
        executable,
        f"--userspec={sandbox_uid}:{sandbox_gid}",
        str(rootfs.resolve()),
        "/bin/busybox",
        "env",
        "-i",
        *env_args,
        "/bin/bash",
        "-lc",
        f"cd /app && {command}",
    ]


def prepare_chroot_environment(
    *,
    rootfs: Path,
    workspace: Path,
    uid: int,
    gid: int,
) -> None:
    if os.geteuid() != 0:
        raise RuntimeError("The Kaggle chroot sandbox requires the root notebook runtime")
    if rootfs.exists():
        shutil.rmtree(rootfs)
    template = _ensure_chroot_template()
    shutil.copytree(template, rootfs, symlinks=True, copy_function=_link_or_copy)
    _create_chroot_devices(rootfs)
    shutil.copytree(workspace, rootfs / "app")
    (rootfs / "home" / "sandbox").mkdir(parents=True)
    (rootfs / "tmp").mkdir()
    (rootfs / "tmp").chmod(0o1777)
    for path in (rootfs / "app", rootfs / "home" / "sandbox"):
        for entry in (path, *path.rglob("*")):
            os.chown(entry, uid, gid, follow_symlinks=False)


def _ensure_chroot_template() -> Path:
    python_executable = _sandbox_python_executable()
    runtime_key = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(python_executable))
    template = Path("/tmp") / f"shallowswe-chroot-{runtime_key}"
    with _CHROOT_TEMPLATE_LOCK:
        if (template / ".ready").is_file():
            return template
        return _build_chroot_template(template, python_executable)


def _build_chroot_template(template: Path, python_executable: Path) -> Path:
    if template.exists():
        shutil.rmtree(template)
    template.mkdir(parents=True)

    busybox = shutil.which("busybox")
    if busybox is None:
        raise RuntimeError("busybox-static is required for the Kaggle chroot sandbox")
    bin_dir = template / "bin"
    bin_dir.mkdir()
    shutil.copy2(busybox, bin_dir / "busybox")
    applets = subprocess.check_output([busybox, "--list"], text=True).splitlines()
    for applet in applets:
        if "/" in applet or applet in {"chroot", "proot"}:
            continue
        applet_path = bin_dir / applet
        if applet_path.exists() or applet_path.is_symlink():
            continue
        applet_path.symlink_to("busybox")
    bash_path = bin_dir / "bash"
    if bash_path.exists() or bash_path.is_symlink():
        bash_path.unlink()
    shutil.copy2("/bin/bash", bash_path)
    usr_bin = template / "usr" / "bin"
    usr_bin.mkdir(parents=True)
    (usr_bin / "env").symlink_to("../../bin/busybox")

    runtime_prefix = python_executable.parent.parent
    destination_prefix = template / "opt" / "python"
    shutil.copytree(
        runtime_prefix,
        destination_prefix,
        symlinks=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "site-packages"),
    )
    directory = destination_prefix
    while directory != template:
        directory.chmod(directory.stat().st_mode | 0o555)
        directory = directory.parent
    for directory in (destination_prefix, *destination_prefix.rglob("*")):
        if directory.is_dir():
            directory.chmod(directory.stat().st_mode | 0o555)
    for alias in ("python", "python3"):
        alias_path = bin_dir / alias
        if alias_path.exists() or alias_path.is_symlink():
            alias_path.unlink()
        shutil.copy2(python_executable.resolve(), alias_path)
    go_root_value = os.environ.get("SHALLOWSWE_GO_ROOT")
    if go_root_value:
        go_root = Path(go_root_value)
        if not (go_root / "bin" / "go").is_file():
            raise RuntimeError(f"Missing ShallowSWE Go runtime: {go_root}")
        shutil.copytree(go_root, template / "opt" / "go", symlinks=True)
    shared_objects = [
        path
        for path in destination_prefix.rglob("*")
        if path.is_file() and (path.suffix == ".so" or ".so." in path.name)
    ]
    _copy_ldd_dependencies(
        template,
        [python_executable, Path("/bin/bash"), *shared_objects],
        source_prefix=destination_prefix,
        runtime_prefix=runtime_prefix,
    )
    (template / ".ready").write_text("ready\n")
    return template


def _create_chroot_devices(rootfs: Path) -> None:
    dev_dir = rootfs / "dev"
    dev_dir.mkdir(exist_ok=True)
    for name, major, minor in (
        ("null", 1, 3),
        ("zero", 1, 5),
        ("random", 1, 8),
        ("urandom", 1, 9),
    ):
        device = dev_dir / name
        if device.exists():
            continue
        try:
            os.mknod(device, stat.S_IFCHR | 0o666, os.makedev(major, minor))
        except OSError:
            device.touch()
        device.chmod(0o666)


def _sandbox_python_executable() -> Path:
    configured = os.environ.get("SHALLOWSWE_SANDBOX_PYTHON")
    executable = Path(configured) if configured else Path(getattr(sys, "_base_executable", sys.executable))
    if not executable.is_file():
        raise RuntimeError(f"Missing ShallowSWE sandbox Python runtime: {executable}")
    return executable.resolve()


def _copy_ldd_dependencies(
    rootfs: Path,
    paths: list[Path],
    *,
    source_prefix: Path,
    runtime_prefix: Path,
) -> None:
    seen: set[Path] = set()
    for path in paths:
        source = path
        if path.is_relative_to(source_prefix):
            source = runtime_prefix / path.relative_to(source_prefix)
        try:
            output = subprocess.check_output(["ldd", str(source)], text=True, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.CalledProcessError):
            continue
        for match in re.finditer(r"(?:=>\s+)?(/[^\s(]+)", output):
            dependency = Path(match.group(1))
            if dependency in seen or not dependency.exists():
                continue
            seen.add(dependency)
            destination = rootfs / dependency.relative_to("/")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dependency.resolve(), destination)


def _link_or_copy(source: str, destination: str) -> str:
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)
    return destination


@dataclass(frozen=True)
class HiddenVerifierResult:
    outcome: VerifierOutcome
    diagnostics: str


def run_hidden_verifier(
    *,
    workspace: Path,
    verifier_dir: Path,
    logs_dir: Path,
    timeout_seconds: int,
    rootfs: Path | None = None,
    executable: str = "chroot",
) -> HiddenVerifierResult:
    if rootfs is None:
        raise ValueError("rootfs is required for the Kaggle hidden verifier")
    if workspace.resolve() != (rootfs / "app").resolve():
        raise ValueError("hidden verifier workspace must be the chroot /app directory")
    if logs_dir.exists():
        shutil.rmtree(logs_dir)
    logs_dir.mkdir(parents=True)
    hidden_tests = rootfs / "tests"
    internal_logs = rootfs / "logs" / "verifier"
    for path in (hidden_tests, internal_logs):
        if path.exists():
            shutil.rmtree(path)
    shutil.copytree(verifier_dir, hidden_tests)
    internal_logs.mkdir(parents=True)
    for path in (internal_logs, *internal_logs.rglob("*")):
        os.chown(path, 65534, 65534, follow_symlinks=False)
    try:
        result = subprocess.run(
            build_chroot_command(
                rootfs=rootfs,
                command="bash /tests/test.sh",
                executable=executable,
            ),
            text=True,
            timeout=timeout_seconds,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        shutil.rmtree(hidden_tests, ignore_errors=True)
        shutil.rmtree(internal_logs, ignore_errors=True)
        return HiddenVerifierResult(
            outcome=VerifierOutcome("verifier_infra_error"),
            diagnostics=str(exc),
        )

    diagnostics = result.stdout
    declared_class = _declared_verifier_class(diagnostics)
    if internal_logs.exists():
        shutil.copytree(internal_logs, logs_dir, dirs_exist_ok=True)
    reward_path = logs_dir / "reward.txt"
    reward = reward_path.read_text().strip() if reward_path.is_file() else None
    if declared_class is not None:
        outcome = VerifierOutcome(declared_class)
    elif result.returncode == 0 and reward == "1":
        outcome = VerifierOutcome("passed")
    elif result.returncode != 0 and reward == "0":
        outcome = VerifierOutcome("generic_failure")
    else:
        outcome = VerifierOutcome("verifier_infra_error")
    shutil.rmtree(hidden_tests, ignore_errors=True)
    shutil.rmtree(internal_logs, ignore_errors=True)
    return HiddenVerifierResult(outcome=outcome, diagnostics=diagnostics)


def _declared_verifier_class(output: str) -> VerifierClass | None:
    allowed: set[str] = {
        "passed",
        "generic_failure",
        "runtime_error",
        "missing_required_artifact",
        "output_mismatch",
        "verifier_infra_error",
    }
    for line in output.splitlines():
        if not line.startswith("VERIFY_RESULT="):
            continue
        value = line.partition("=")[2].strip()
        if value in allowed:
            return value  # type: ignore[return-value]
    return None
