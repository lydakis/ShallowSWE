from __future__ import annotations

from pathlib import Path, PurePosixPath
import shlex
import shutil
import tempfile
import uuid

from pier.agents.installed.mini_swe_agent import MiniSweAgent
from pier.agents.utils import get_api_key_var_names_from_model_name
from pier.environments.base import BaseEnvironment
from pier.models.agent.context import AgentContext
from pier.models.agent.install import AgentInstallSpec
from pier.models.agent.network import NetworkAllowlist
from pier.models.trial.paths import EnvironmentPaths


class ResumableMiniSweAgent(MiniSweAgent):
    """Mini-swe-agent wrapper that can resume a prior trajectory in one sandbox."""

    _REMOTE_SOURCE_DIR = "/tmp/shallowswe-mini-swe-agent-fork"

    def __init__(
        self,
        mini_swe_agent_source_dir: str | None = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._mini_swe_agent_source_dir = (
            Path(mini_swe_agent_source_dir).expanduser().resolve()
            if mini_swe_agent_source_dir
            else None
        )

    @staticmethod
    def name() -> str:
        return "shallowswe-resumable-mini-swe-agent"

    def install_spec(self) -> AgentInstallSpec | None:
        return None

    def network_allowlist(self) -> NetworkAllowlist:
        base = super().network_allowlist()
        return NetworkAllowlist(
            domains=[
                *base.domains,
                "files.pythonhosted.org",
                "pypi.org",
            ]
        )

    async def install(self, environment: BaseEnvironment) -> None:
        await self._upload_fork_source(environment)
        await self.exec_as_agent(
            environment,
            command=_agent_install_command(
                remote_source_dir=self._REMOTE_SOURCE_DIR,
                extra_python_packages=self._install_python_packages,
            ),
            env={"LITELLM_LOCAL_MODEL_COST_MAP": "true"},
            timeout_sec=900,
        )

    async def _upload_fork_source(self, environment: BaseEnvironment) -> None:
        if self._mini_swe_agent_source_dir is None:
            raise ValueError("mini_swe_agent_source_dir is required")
        if not (self._mini_swe_agent_source_dir / "pyproject.toml").exists():
            raise ValueError(f"{self._mini_swe_agent_source_dir} is not a Python project")

        with tempfile.TemporaryDirectory() as tmp:
            staged = Path(tmp) / "mini-swe-agent"
            shutil.copytree(
                self._mini_swe_agent_source_dir,
                staged,
                ignore=shutil.ignore_patterns(
                    ".git",
                    ".venv",
                    ".mypy_cache",
                    ".pytest_cache",
                    ".ruff_cache",
                    "__pycache__",
                    "*.pyc",
                    "dist",
                    "build",
                ),
            )
            await environment.upload_dir(staged, self._REMOTE_SOURCE_DIR)

    @property
    def _previous_mini_swe_agent_trajectory_path(self) -> PurePosixPath:
        return EnvironmentPaths.agent_dir / "mini-swe-agent.previous.trajectory.json"

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        instruction = self.render_instruction(instruction)
        if self.mcp_servers:
            instruction += "\n\nMCP Servers:\n"
            for server in self.mcp_servers:
                if server.transport == "stdio":
                    args = " ".join(server.args)
                    instruction += (
                        f"- {server.name}: stdio transport, command: "
                        f"{server.command} {args}\n"
                    )
                else:
                    instruction += f"- {server.name}: {server.transport} transport, url: {server.url}\n"

        await self.exec_as_agent(
            environment,
            command=_resume_aware_run_command(
                run_model_name=self._run_model_name,
                instruction=instruction,
                remote_source_dir=self._REMOTE_SOURCE_DIR,
                output_path=self._mini_swe_agent_trajectory_path,
                previous_path=self._previous_mini_swe_agent_trajectory_path,
                extra_flags=(self.build_cli_flags() + " ") if self.build_cli_flags() else "",
                config_flags=await self._write_config_and_flags(environment),
                extra_python_packages=self._install_python_packages,
            ),
            env=self._runtime_env(),
            timeout_sec=None,
        )

    async def _write_config_and_flags(self, environment: BaseEnvironment) -> str:
        custom_config_path = None
        if self._config_yaml:
            custom_config_path = "/tmp/mswea-config/custom.yaml"
            marker = f"MSWEA_CONFIG_EOF_{uuid.uuid4().hex[:8]}"
            await self.exec_as_agent(
                environment,
                command=(
                    "mkdir -p /tmp/mswea-config\n"
                    f"cat > {shlex.quote(custom_config_path)} << {shlex.quote(marker)}\n"
                    f"{self._config_yaml}\n"
                    f"{marker}\n"
                ),
                env=self._runtime_env(),
            )
        return self._build_config_flags(custom_config_path=custom_config_path)

    def _runtime_env(self) -> dict[str, str]:
        env = self.build_process_env(
            {
                "LITELLM_LOCAL_MODEL_COST_MAP": "true",
                "MSWEA_CONFIGURED": "true",
                "MSWEA_COST_TRACKING": "ignore_errors",
            }
        )
        if self._get_env("MSWEA_API_KEY"):
            env["MSWEA_API_KEY"] = self._get_env("MSWEA_API_KEY") or ""
        else:
            for api_key_var in get_api_key_var_names_from_model_name(self.model_name):
                if not self._get_env(api_key_var):
                    raise ValueError(
                        f"Unset API variable for model {self.model_name}. "
                        f"Please set {api_key_var} or MSWEA_API_KEY."
                    )
                env[api_key_var] = self._get_env(api_key_var) or ""

        for key in ("OPENAI_API_BASE", "OPENAI_BASE_URL"):
            if self._get_env(key):
                env[key] = self._get_env(key) or ""
        return env


def _agent_install_command(
    *,
    remote_source_dir: str,
    extra_python_packages: list[str],
) -> str:
    return (
        "set -euo pipefail\n"
        + _agent_install_snippet(
            remote_source_dir=remote_source_dir,
            extra_python_packages=extra_python_packages,
            force=True,
        )
        + "\nmini-swe-agent --help\n"
    )


def _agent_install_snippet(
    *,
    remote_source_dir: str,
    extra_python_packages: list[str],
    force: bool,
) -> str:
    extra_packages = " ".join(shlex.quote(pkg) for pkg in extra_python_packages)
    install_extra = (
        f'"$venv/bin/python" -m pip install {extra_packages}\n'
        if extra_packages
        else ""
    )
    condition = (
        "true"
        if force
        else '[ ! -x "$venv/bin/python" ] || ! "$venv/bin/python" -c '
        + shlex.quote("import minisweagent")
        + " >/dev/null 2>&1"
    )
    return f"""
venv="$HOME/.local/share/shallowswe-mini-swe-agent-venv"
if {condition}; then
python3 -m venv "$venv"
"$venv/bin/python" -m pip install --upgrade pip
"$venv/bin/python" -m pip install {shlex.quote(remote_source_dir)}
{install_extra}
fi
mkdir -p "$HOME/.local/bin"
ln -sf "$venv/bin/mini-swe-agent" "$HOME/.local/bin/mini-swe-agent"
cat > "$HOME/.local/bin/env" <<'EOF'
export PATH="$HOME/.local/bin:$PATH"
EOF
source "$HOME/.local/bin/env"
"""


def _resume_aware_run_command(
    *,
    run_model_name: str,
    instruction: str,
    remote_source_dir: str,
    output_path: PurePosixPath,
    previous_path: PurePosixPath,
    extra_flags: str,
    config_flags: str,
    extra_python_packages: list[str],
) -> str:
    if not run_model_name or "/" not in run_model_name:
        raise ValueError("Model name must be in the format provider/model_name")
    escaped_model = shlex.quote(run_model_name)
    escaped_instruction = shlex.quote(instruction)
    output = shlex.quote(output_path.as_posix())
    previous = shlex.quote(previous_path.as_posix())
    base = (
        f"mini-swe-agent --yolo --model={escaped_model} --output={output} "
        f"{extra_flags}{config_flags}--exit-immediately"
    )
    ensure_agent = _agent_install_snippet(
        remote_source_dir=remote_source_dir,
        extra_python_packages=extra_python_packages,
        force=False,
    )
    return (
        "set -euo pipefail\n"
        + ensure_agent
        + '\n. "$HOME/.local/bin/env"\n'
        f"if [ -f {output} ]; then "
        f"cp {output} {previous}; "
        f"{base} --resume-from={previous} --resume-feedback={escaped_instruction}; "
        "else "
        f"{base} --task={escaped_instruction}; "
        "fi 2>&1 </dev/null | tee /logs/agent/mini-swe-agent.txt"
    )
