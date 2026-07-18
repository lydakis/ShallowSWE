from __future__ import annotations

from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any
import asyncio
import json

from .pilot_binding import resolve_launch_unit
from .repair_loop_protocol import (
    AgentSubmission,
    RepairLoopPolicy,
    VerifierOutcome,
    execute_repair_loop,
)
from .results import (
    CAP_HIT_STOP_REASONS,
    EXCLUDED_STATUS,
    RepairLoopResult,
    audit_repair_loop_evidence,
    dump_repair_loops,
)
from .stage4_policy import build_stage4_policy
from .task_metadata import load_task
from .workload import build_repair_loop_workload_index


DEVELOPMENT_EVIDENCE_CLASS = "development_dry_run"
DEVELOPMENT_RELEASE_CLASS = "development_dry_run"


class _ScriptedBackend:
    def __init__(self, specifications: list[dict[str, Any]]) -> None:
        self.specifications = specifications
        self.index = 0
        self.current: dict[str, Any] | None = None
        self.agent_submissions = 0
        self.verifier_submissions = 0
        self.event_checkpoints: list[dict[str, Any]] = []

    async def submit(self, instruction: str) -> AgentSubmission:
        del instruction
        if self.index >= len(self.specifications):
            raise RuntimeError("script exhausted before repair-loop termination")
        specification = self.specifications[self.index]
        self.index += 1
        if specification.get("raise_runner_exception"):
            raise RuntimeError("scripted runner infrastructure failure")
        self.current = specification
        self.agent_submissions += 1
        self._record("agent_submission")
        return AgentSubmission(
            exit_status=str(specification.get("exit_status") or "Submitted"),
            dollar_cap_hit=bool(specification.get("dollar_cap_hit")),
        )

    async def verify(self) -> VerifierOutcome:
        if self.current is None:
            raise RuntimeError("verify called without a scripted submission")
        self.verifier_submissions += 1
        result_class = str(self.current.get("result_class") or "generic_failure")
        outcome = VerifierOutcome(result_class)  # type: ignore[arg-type]
        self._record("verifier_result", result_class=result_class)
        return outcome

    def _record(self, event_type: str, *, result_class: str | None = None) -> None:
        specification = self.current or {}
        checkpoint = {
            "event_index": len(self.event_checkpoints) + 1,
            "event_type": event_type,
            "agent_submission": self.agent_submissions,
            "verifier_submission": self.verifier_submissions,
            "result_class": result_class,
            "cumulative_input_tokens": self.agent_submissions * 100,
            "cumulative_output_tokens": self.agent_submissions * 10,
            "cumulative_cache_read_tokens": 0,
            "cumulative_cache_write_tokens": 0,
            "cumulative_reasoning_tokens": 0,
            "cumulative_agent_steps": int(specification.get("steps") or 0),
            "cumulative_gateway_reported_cost_usd": float(
                specification.get("spend") or 0.0
            ),
            "cumulative_canonical_spend_usd": float(specification.get("spend") or 0.0),
        }
        self.event_checkpoints.append(checkpoint)


def run_development_rehearsal(manifest_path: Path, output_dir: Path) -> dict[str, Any]:
    """Exercise the analysis pipeline with deterministic, non-model development evidence."""

    manifest = json.loads(manifest_path.read_text())
    repo_root = manifest_path.resolve().parents[1]
    tasks = {
        task_id: load_task(repo_root / str(manifest.get("task_root") or "tasks") / task_id)
        for task_id in manifest["task_ids"]
    }
    confirmation_tasks = set(manifest["confirmation_task_ids"])

    scenario_rows = _scenario_rows()
    stage3_rows: list[RepairLoopResult] = []
    for task_index, task_id in enumerate(manifest["task_ids"]):
        task = tasks[task_id]
        proposal_spend = (0.04, 0.05, 0.08, 0.09)
        check_spend = (0.11, 0.12)
        for loop, spend in enumerate(proposal_spend):
            stage3_rows.append(
                _scripted_row(
                    task_id=task_id,
                    category=task.category,
                    pressure_band="elevated" if task_id in confirmation_tasks else "lower",
                    loop=loop,
                    model="development-anchor",
                    model_config_id="mc_development_anchor",
                    agent_policy_id="ap_development_anchor",
                    pilot_stage="permissive_collection",
                    pilot_mode="permissive_repair_loop",
                    pilot_cohort="budget_proposal",
                    success_submission=2 if loop == 0 else 1,
                    final_spend=spend,
                    final_steps=20 + task_index,
                    policy_submission_cap=16,
                )
            )
        for loop, spend in enumerate(check_spend, start=4):
            stage3_rows.append(
                _scripted_row(
                    task_id=task_id,
                    category=task.category,
                    pressure_band="elevated" if task_id in confirmation_tasks else "lower",
                    loop=loop,
                    model="development-anchor",
                    model_config_id="mc_development_anchor",
                    agent_policy_id="ap_development_anchor",
                    pilot_stage="permissive_collection",
                    pilot_mode="permissive_repair_loop",
                    pilot_cohort="development_check",
                    success_submission=1,
                    final_spend=spend,
                    final_steps=20 + task_index,
                    policy_submission_cap=16,
                )
            )
        elevated = task_id in confirmation_tasks
        for role, first_submit_successes in (
            ("floor_low", 1 if elevated else 3),
            ("floor_strong", 2 if elevated else 3),
        ):
            for loop in range(3):
                first_submit = loop < first_submit_successes
                stage3_rows.append(
                    _scripted_row(
                        task_id=task_id,
                        category=task.category,
                        pressure_band="elevated" if elevated else "lower",
                        loop=loop,
                        model=f"development-{role}",
                        model_config_id=f"mc_development_{role}",
                        agent_policy_id=f"ap_development_{role}",
                        pilot_stage="permissive_collection",
                        pilot_mode="permissive_repair_loop",
                        pilot_cohort="floor_panel",
                        success_submission=1 if first_submit else 2,
                        final_spend=0.04,
                        final_steps=16,
                        policy_submission_cap=16,
                    )
                )

    confirmation_rows: list[RepairLoopResult] = []
    for task_id in manifest["confirmation_task_ids"]:
        task = tasks[task_id]
        for loop in range(8):
            confirmation_rows.append(
                _scripted_row(
                    task_id=task_id,
                    category=task.category,
                    pressure_band="elevated",
                    loop=loop,
                    model="development-anchor",
                    model_config_id="mc_development_anchor",
                    agent_policy_id="ap_development_anchor",
                    pilot_stage="fresh_anchor_confirmation",
                    pilot_mode="frozen_repair_loop",
                    pilot_cohort="fresh_confirmation",
                    success_submission=1 if loop < 6 else None,
                    final_spend=0.10 if loop < 6 else 0.20,
                    final_steps=20,
                    policy_submission_cap=2,
                    policy_agent_step_cap=32,
                    reference_task_budget_usd=0.20,
                )
            )

    development_manifest = _development_manifest(manifest)
    stage4_rows = stage3_rows + confirmation_rows
    stage4 = build_stage4_policy(
        stage4_rows,
        development_manifest,
        evidence_class=DEVELOPMENT_EVIDENCE_CLASS,
        release_class=DEVELOPMENT_RELEASE_CLASS,
    )
    budgets = {
        str(row["task_id"]): float(row["selected_budget_usd"])
        for row in stage4["task_budgets"]
        if row["selected_budget_usd"] is not None
    }

    scoring_rows: list[RepairLoopResult] = []
    zero_success_task = str(manifest["task_ids"][-1])
    for task_id in manifest["task_ids"]:
        task = tasks[task_id]
        pressure_band = "elevated" if task_id in confirmation_tasks else "lower"
        for loop in range(2):
            scoring_rows.append(
                _scripted_row(
                    task_id=task_id,
                    category=task.category,
                    pressure_band=pressure_band,
                    loop=loop,
                    model="development-candidate",
                    model_config_id="mc_development_candidate",
                    agent_policy_id="ap_development_candidate",
                    pilot_stage="development_scoring",
                    pilot_mode="frozen_repair_loop",
                    pilot_cohort="workload",
                    success_submission=None if task_id == zero_success_task else 1,
                    final_spend=0.05,
                    final_steps=12,
                    policy_submission_cap=2,
                    policy_agent_step_cap=32,
                    reference_task_budget_usd=budgets[task_id],
                    reference_anchor_replacement_cost_usd=0.15,
                )
            )
    workload = build_repair_loop_workload_index(
        scoring_rows,
        target_tasks_per_cell=2,
        pressure_bands=("lower", "elevated"),
        evidence_class=DEVELOPMENT_EVIDENCE_CLASS,
        release_class=DEVELOPMENT_RELEASE_CLASS,
    )

    all_rows = scenario_rows + stage4_rows + scoring_rows
    mixed = replace(all_rows[0], evidence_class="official_pilot")
    mixed_report = audit_repair_loop_evidence([all_rows[0], mixed])
    mixed_guard = "rejected_as_expected" if not mixed_report["valid"] else "FAILED"
    launch_guard = _official_launch_guard(repo_root, manifest)
    confirmations = stage4["confirmation_diagnostics"]
    confirmation_check = (
        "rejected_6_of_8_as_expected"
        if confirmations
        and all(
            row["attempts"] == 8 and row["successes"] == 6 and not row["confirmed"]
            for row in confirmations
        )
        else "FAILED"
    )
    zero_success_cells = sum(
        1 for cell in workload["cells"] if int(cell["successes"]) == 0
    )
    stop_reasons = dict(sorted(Counter(row.stop_reason for row in scenario_rows).items()))
    expected_stops = {
        "agent_step_cap": 1,
        "dollar_cap": 1,
        "passed": 2,
        "runner_exception": 1,
        "verifier_submission_cap": 1,
    }
    valid = all(
        (
            stop_reasons == expected_stops,
            any(not row.is_scored for row in scenario_rows),
            stage4["policy_status"] == "development_proposal",
            confirmation_check == "rejected_6_of_8_as_expected",
            zero_success_cells == 1,
            len(workload["underfilled_cells"]) == 6,
            launch_guard == "blocked_as_expected",
            mixed_guard == "rejected_as_expected",
            stage4["official_launch_eligible"] is False,
        )
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "repair-loop-results.json").write_text(dump_repair_loops(all_rows))
    (output_dir / "stage4-policy.json").write_text(json.dumps(stage4, indent=2) + "\n")
    (output_dir / "workload-index.json").write_text(json.dumps(workload, indent=2) + "\n")
    report = {
        "schema_version": "shallowswe.development_rehearsal.v0.1",
        "valid": valid,
        "manifest": manifest.get("name"),
        "evidence_class": DEVELOPMENT_EVIDENCE_CLASS,
        "release_class": DEVELOPMENT_RELEASE_CLASS,
        "rows": len(all_rows),
        "scripted_stop_reasons": stop_reasons,
        "stage4_policy_status": stage4["policy_status"],
        "selected_policy": stage4["selected_policy"],
        "confirmation_check": confirmation_check,
        "zero_success_cells": zero_success_cells,
        "underfilled_workload_cells": len(workload["underfilled_cells"]),
        "official_launch_guard": launch_guard,
        "mixed_evidence_guard": mixed_guard,
        "human_routine_review_used": False,
        "metered_model_calls": 0,
        "official_evidence_produced": False,
    }
    (output_dir / "rehearsal-report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def _scenario_rows() -> list[RepairLoopResult]:
    common = {
        "task_id": "harness-scenario",
        "category": "code",
        "pressure_band": "lower",
        "model": "development-harness",
        "model_config_id": "mc_development_harness",
        "agent_policy_id": "ap_development_harness",
        "pilot_stage": "development_harness",
        "pilot_mode": "scripted",
        "pilot_cohort": "edge_cases",
        "policy_submission_cap": 3,
    }
    return [
        _scripted_row(
            **common,
            loop=0,
            success_submission=1,
            final_spend=0.01,
            final_steps=4,
        ),
        _scripted_row(
            **common,
            loop=1,
            success_submission=2,
            final_spend=0.03,
            final_steps=8,
        ),
        _scripted_row(
            **common,
            loop=2,
            success_submission=None,
            final_spend=0.04,
            final_steps=12,
        ),
        _scripted_row(
            **common,
            loop=3,
            success_submission=None,
            final_spend=0.05,
            final_steps=6,
            forced_stop="dollar_cap",
        ),
        _scripted_row(
            **common,
            loop=4,
            success_submission=None,
            final_spend=0.01,
            final_steps=64,
            forced_stop="agent_step_cap",
        ),
        _scripted_row(
            **common,
            loop=5,
            success_submission=None,
            final_spend=0.0,
            final_steps=0,
            forced_stop="runner_exception",
        ),
    ]


def _scripted_row(
    *,
    task_id: str,
    category: str,
    pressure_band: str,
    loop: int,
    model: str,
    model_config_id: str,
    agent_policy_id: str,
    pilot_stage: str,
    pilot_mode: str,
    pilot_cohort: str,
    success_submission: int | None,
    final_spend: float,
    final_steps: int,
    policy_submission_cap: int,
    policy_agent_step_cap: int = 256,
    forced_stop: str | None = None,
    reference_task_budget_usd: float | None = None,
    reference_anchor_replacement_cost_usd: float | None = None,
) -> RepairLoopResult:
    specifications: list[dict[str, Any]] = []
    if forced_stop == "runner_exception":
        specifications.append({"raise_runner_exception": True})
    elif forced_stop == "agent_step_cap":
        specifications.append(
            {
                "exit_status": "LimitsExceeded",
                "steps": final_steps,
                "spend": final_spend,
            }
        )
    else:
        submissions = success_submission or policy_submission_cap
        for submission in range(1, submissions + 1):
            specifications.append(
                {
                    "exit_status": "Submitted",
                    "result_class": (
                        "passed" if submission == success_submission else "output_mismatch"
                    ),
                    "dollar_cap_hit": forced_stop == "dollar_cap",
                    "steps": max(1, final_steps * submission // submissions),
                    "spend": final_spend * submission / submissions,
                }
            )
    backend = _ScriptedBackend(specifications)
    try:
        execution = asyncio.run(
            execute_repair_loop(
                backend,
                initial_instruction="Complete the scripted task.",
                policy=RepairLoopPolicy(max_verifier_submissions=policy_submission_cap),
            )
        )
        passed = execution.passed
        stop_reason = execution.stop_reason
        status = execution.status
        exclusion_reason = execution.exclusion_reason
    except RuntimeError:
        passed = False
        stop_reason = "runner_exception"
        status = EXCLUDED_STATUS
        exclusion_reason = "runner_infrastructure_error"
    actual_spend = (
        float(backend.event_checkpoints[-1]["cumulative_canonical_spend_usd"])
        if backend.event_checkpoints
        else 0.0
    )
    return RepairLoopResult(
        model=model,
        task_id=task_id,
        category=category,
        size="small",
        loop=loop,
        passed=passed,
        stop_reason=stop_reason,
        verifier_submissions=backend.verifier_submissions,
        input_tokens=backend.agent_submissions * 100,
        output_tokens=backend.agent_submissions * 10,
        cache_read_tokens=0,
        cache_write_tokens=0,
        turns=final_steps,
        agent_steps=final_steps,
        model_config_id=model_config_id,
        agent_policy_id=agent_policy_id,
        evidence_class=DEVELOPMENT_EVIDENCE_CLASS,
        release_class=DEVELOPMENT_RELEASE_CLASS,
        task_version=f"{task_id}@development-v1",
        task_suite_version="shallowswe-six-task-development-rehearsal-v1",
        verifier_hash=f"sha256:development-verifier-{task_id}",
        environment_image_digest=f"sha256:development-environment-{task_id}",
        price_sheet_version="development-synthetic-prices-v1",
        pilot_stage=pilot_stage,
        pilot_mode=pilot_mode,
        pilot_cohort=pilot_cohort,
        pressure_band=pressure_band,
        verifier_submission_cap=policy_submission_cap,
        agent_step_cap=policy_agent_step_cap,
        cap_disclosure="undisclosed",
        actual_model_spend_usd=actual_spend,
        canonical_list_price_equivalent_spend_usd=actual_spend,
        reference_task_budget_usd=reference_task_budget_usd,
        reference_anchor_replacement_cost_usd=reference_anchor_replacement_cost_usd,
        censoring_status=(
            "right_censored" if stop_reason in CAP_HIT_STOP_REASONS else "observed"
        ),
        event_checkpoints=backend.event_checkpoints,
        status=status,
        exclusion_reason=exclusion_reason,
    )


def _development_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    copied = json.loads(json.dumps(manifest))
    identifiers = {
        "primary_anchor": "mc_development_anchor",
        "floor_low": "mc_development_floor_low",
        "floor_strong": "mc_development_floor_strong",
    }
    for config in copied["model_configs"]:
        config["model_config_id"] = identifiers[config["role"]]
    return copied


def _official_launch_guard(repo_root: Path, manifest: dict[str, Any]) -> str:
    raw_path = manifest.get("freeze_artifacts", {}).get("pilot_launch_plan")
    if not raw_path:
        return "FAILED"
    launch_plan = json.loads((repo_root / str(raw_path)).read_text())
    official = next(
        unit for unit in launch_plan["units"] if unit.get("runner") == "kaggle"
    )
    try:
        resolve_launch_unit(launch_plan, str(official["launch_unit_id"]))
    except RuntimeError as exc:
        return "blocked_as_expected" if "not launchable" in str(exc) else "FAILED"
    return "FAILED"
