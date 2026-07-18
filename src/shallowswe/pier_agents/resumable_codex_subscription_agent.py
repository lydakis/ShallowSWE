from __future__ import annotations

from pathlib import PurePosixPath
import shlex

from pier.agents.installed.base import with_prompt_template
from pier.environments.base import BaseEnvironment
from pier.models.agent.context import AgentContext
from pier.models.trial.paths import EnvironmentPaths

from .codex_subscription_agent import CodexSubscriptionAgent


class ResumableCodexSubscriptionAgent(CodexSubscriptionAgent):
    """Codex subscription agent that preserves one session across verifier feedback."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._submission_count = 0
        self._runtime_initialized = False

    @staticmethod
    def name() -> str:
        return "shallowswe-resumable-codex-subscription"

    @with_prompt_template
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        if not self.model_name:
            raise ValueError("Model name is required")

        if not self._runtime_initialized:
            await self._initialize_runtime(environment)
            self._runtime_initialized = True

        submission_number = self._submission_count + 1
        model = self._command_model_name or self.model_name.split("/")[-1]
        cli_flags = self.build_cli_flags()
        env = self.build_process_env({"CODEX_HOME": self._REMOTE_CODEX_HOME.as_posix()})

        await self.exec_as_agent(
            environment,
            command=_codex_exec_command(
                model=model,
                instruction=instruction,
                cli_flags=cli_flags,
                submission_number=submission_number,
            ),
            env=env,
        )
        self._submission_count = submission_number
        await self._copy_sessions_to_agent_logs(environment, env=env)

    async def _initialize_runtime(self, environment: BaseEnvironment) -> None:
        auth_json_path = self._resolve_auth_json_path()
        if auth_json_path is None:
            raise ValueError(
                "ResumableCodexSubscriptionAgent requires CODEX_FORCE_AUTH_JSON=true "
                "or CODEX_AUTH_JSON_PATH"
            )

        remote_codex_home = self._REMOTE_CODEX_HOME.as_posix()
        remote_secrets_dir = self._REMOTE_CODEX_SECRETS_DIR.as_posix()
        remote_auth_path = (self._REMOTE_CODEX_SECRETS_DIR / "auth.json").as_posix()
        env = self.build_process_env({"CODEX_HOME": remote_codex_home})

        await self.exec_as_agent(
            environment,
            command=(
                f'mkdir -p "$CODEX_HOME" {shlex.quote(remote_secrets_dir)} '
                f"{shlex.quote(EnvironmentPaths.agent_dir.as_posix())}"
            ),
            env=env,
        )
        await environment.upload_file(auth_json_path, remote_auth_path)
        if environment.default_user is not None:
            await self.exec_as_root(
                environment,
                command=f"chown {environment.default_user} {shlex.quote(remote_auth_path)}",
            )
        await self.exec_as_agent(
            environment,
            command=(
                f"ln -sf {shlex.quote(remote_auth_path)} "
                '"$CODEX_HOME/auth.json"'
            ),
            env=env,
        )

        if self._config_toml:
            await self.exec_as_agent(
                environment,
                command=(
                    f"printf '%s\\n' {shlex.quote(self._config_toml)} "
                    '>> "$CODEX_HOME/config.toml"'
                ),
                env=env,
            )

        skills_command = self._build_register_skills_command()
        if skills_command:
            await self.exec_as_agent(environment, command=skills_command, env=env)
        mcp_command = self._build_register_mcp_servers_command()
        if mcp_command:
            await self.exec_as_agent(environment, command=mcp_command, env=env)

    async def _copy_sessions_to_agent_logs(
        self,
        environment: BaseEnvironment,
        *,
        env: dict[str, str],
    ) -> None:
        sessions_path = (EnvironmentPaths.agent_dir / "sessions").as_posix()
        await self.exec_as_agent(
            environment,
            command=(
                f"rm -rf {shlex.quote(sessions_path)}\n"
                'if [ -d "$CODEX_HOME/sessions" ]; then\n'
                f'  cp -R "$CODEX_HOME/sessions" {shlex.quote(sessions_path)}\n'
                "fi"
            ),
            env=env,
        )

    async def cleanup_runtime(self, environment: BaseEnvironment) -> None:
        """Remove uploaded subscription credentials before Pier tears down the container."""

        if not self._runtime_initialized:
            return
        await self.exec_as_root(
            environment,
            command=(
                f"rm -rf {shlex.quote(self._REMOTE_CODEX_SECRETS_DIR.as_posix())} "
                f"{shlex.quote(self._REMOTE_CODEX_HOME.as_posix())}"
            ),
        )
        self._runtime_initialized = False


def _codex_exec_command(
    *,
    model: str,
    instruction: str,
    cli_flags: str,
    submission_number: int,
) -> str:
    if submission_number < 1:
        raise ValueError("submission_number must be positive")
    escaped_instruction = shlex.quote(instruction)
    escaped_model = shlex.quote(model)
    output_path = PurePosixPath(EnvironmentPaths.agent_dir) / (
        f"codex-submission-{submission_number}.txt"
    )
    resume = "resume --last " if submission_number > 1 else ""
    flags = f"{cli_flags} " if cli_flags else ""
    return (
        "if [ -s ~/.nvm/nvm.sh ]; then . ~/.nvm/nvm.sh; fi; "
        f"codex exec {resume}"
        "--dangerously-bypass-approvals-and-sandbox "
        "--skip-git-repo-check "
        f"--model {escaped_model} "
        "--json "
        "--enable unified_exec "
        f"{flags}"
        "-- "
        f"{escaped_instruction} "
        f"2>&1 </dev/null | tee {shlex.quote(output_path.as_posix())}"
    )
