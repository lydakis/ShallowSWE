from __future__ import annotations

import argparse
import csv
from hashlib import sha256
from html import escape
import json
import math
from pathlib import Path
from typing import Any, Iterable

from shallowswe.deepswe_economics import derive_deepswe_trial_rows


PAPER_ASSET_SCHEMA_VERSION = "shallowswe.deepswe_paper_assets.v0.1"
BLUE = "#2563A6"
GOLD = "#D49A27"
ORANGE = "#C9673B"
CHARCOAL = "#252A31"
GRAY = "#89919A"
LIGHT_GRAY = "#E5E8EB"
PALE_BLUE = "#DCE9F5"
PALE_GOLD = "#F5E8C8"


def write_deepswe_paper_assets(
    trials: dict[str, Any],
    report: dict[str, Any],
    output_dir: Path,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = output_dir / "tables"
    figures_dir = output_dir / "figures"
    tables_dir.mkdir(exist_ok=True)
    figures_dir.mkdir(exist_ok=True)

    primary = _mapping(report, "primary")
    bootstrap = _mapping(report, "bootstrap")
    task_mix = _mapping(primary, "task_mix")
    panel_solvedness = _mapping(task_mix, "panel_solvedness_strata")
    leave_one_family_out = _mapping(
        task_mix, "leave_one_family_out_panel_solvedness"
    )
    gpt_5_6_group_out = _mapping(
        task_mix, "gpt_5_6_group_out_panel_solvedness"
    )
    exclusion_audit = _mapping(primary, "infrastructure_exclusion_audit")
    task_weighting = _mapping(primary, "task_weighting_sensitivity")
    task_weighting_bootstrap = _mapping(bootstrap, "task_weighting_sensitivity")
    table_specs = {
        "derived-trials.csv": derive_deepswe_trial_rows(trials),
        "configuration-results.csv": _rows(primary, "configurations"),
        "resource-intensity.csv": _rows(primary, "resource_intensity"),
        "economic-frontier.csv": [
            row
            for row in _rows(primary, "configurations")
            if row.get("attempt_cost_pareto_frontier")
        ],
        "best-model-results.csv": _rows(primary, "display_configurations"),
        "reliability-floor.csv": _rows(primary, "reliability_floor_curve"),
        "bootstrap-intervals.csv": _rows(bootstrap, "configurations"),
        "paired-comparisons.csv": _rows(bootstrap, "paired_comparisons"),
        "resource-intensity-bootstrap.csv": _rows(
            bootstrap, "resource_intensity"
        ),
        "paired-resource-comparisons.csv": _rows(
            bootstrap, "paired_resource_comparisons"
        ),
        "task-success-heterogeneity.csv": _rows(task_mix, "success_heterogeneity"),
        "panel-solvedness-assignments.csv": _rows(panel_solvedness, "tasks"),
        "panel-solvedness-strata.csv": _rows(panel_solvedness, "configurations"),
        "leave-one-family-out-panel-solvedness-assignments.csv": _rows(
            leave_one_family_out, "assignments"
        ),
        "leave-one-family-out-panel-solvedness.csv": _rows(
            leave_one_family_out, "configurations"
        ),
        "gpt-5-6-group-out-panel-solvedness-assignments.csv": _rows(
            gpt_5_6_group_out, "assignments"
        ),
        "gpt-5-6-group-out-panel-solvedness.csv": _rows(
            gpt_5_6_group_out, "configurations"
        ),
        "matched-solved-task-comparisons.csv": _rows(
            task_mix, "matched_solved_task_comparisons"
        ),
        "infrastructure-exclusion-audit.csv": _rows(
            exclusion_audit, "configurations"
        ),
        "equal-task-full-basket.csv": _rows(
            task_weighting, "full_basket_configurations"
        ),
        "equal-task-common-basket.csv": _rows(
            task_weighting, "common_basket_configurations"
        ),
        "equal-task-reliability-floor.csv": _rows(
            task_weighting, "full_basket_reliability_floor_curve"
        ),
        "equal-task-bootstrap.csv": _rows(
            task_weighting_bootstrap, "reliability_floor_policy"
        ),
        "equal-task-selection-frequencies.csv": _rows(
            task_weighting_bootstrap, "reliability_floor_selection_frequencies"
        ),
        "rank-association-intervals.csv": _rank_association_interval_rows(
            bootstrap
        ),
        "within-model-rank-associations.csv": _within_model_association_rows(
            primary, bootstrap
        ),
        "reliability-floor-bootstrap.csv": _rows(
            bootstrap, "reliability_floor_policy"
        ),
        "reliability-floor-lcb-eligibility.csv": _rows(
            bootstrap, "reliability_floor_lcb_eligibility"
        ),
        "reliability-floor-selection-frequencies.csv": _rows(
            bootstrap, "reliability_floor_selection_frequencies"
        ),
        "provider-cost-provenance.csv": [
            row
            for row in report.get("provider_cost_provenance") or []
            if isinstance(row, dict)
        ],
        "missing-cost-sensitivities.csv": _missing_cost_sensitivity_rows(report),
        "failure-charge-sensitivity.csv": _failure_charge_rows(report),
        "anchor-success-budget-sensitivity.csv": _anchor_success_budget_rows(
            report
        ),
    }
    for name, rows in table_specs.items():
        _write_csv(tables_dir / name, rows)

    figure_specs = {
        "economic-frontier.svg": render_economic_frontier_svg(report),
        "rank-divergence.svg": render_rank_divergence_svg(report),
        "reliability-floor.svg": render_reliability_floor_svg(report),
        "failure-cost-decomposition.svg": render_failure_cost_decomposition_svg(report),
        "task-coverage.svg": render_task_coverage_svg(report),
        "invoice-work-frontiers.svg": render_invoice_work_frontiers_svg(report),
    }
    for name, svg in figure_specs.items():
        (figures_dir / name).write_text(svg)

    summary = build_paper_summary(report)
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    generated = sorted(
        [
            path
            for path in output_dir.rglob("*")
            if path.is_file() and path.name != "manifest.json"
        ]
    )
    manifest = {
        "schema_version": PAPER_ASSET_SCHEMA_VERSION,
        "analysis_schema_version": report.get("schema_version"),
        "benchmark_release": report.get("benchmark_release"),
        "files": [
            {
                "path": str(path.relative_to(output_dir)),
                "bytes": path.stat().st_size,
                "sha256": sha256(path.read_bytes()).hexdigest(),
            }
            for path in generated
        ],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    return manifest


def build_paper_summary(report: dict[str, Any]) -> dict[str, object]:
    primary = _mapping(report, "primary")
    all_rows = _rows(primary, "configurations")
    display_rows = _rows(primary, "display_configurations")
    lowest_cpsc = min(all_rows, key=lambda row: float(row["realized_cpsc_usd"]))
    highest_pass = max(all_rows, key=lambda row: float(row["pass_rate"]))
    display_lowest = min(
        display_rows, key=lambda row: float(row["realized_cpsc_usd"])
    )
    floor_changes = []
    previous = object()
    for row in _rows(primary, "reliability_floor_curve"):
        config = row.get("minimum_cpsc_config")
        if config != previous:
            floor_changes.append(dict(row))
            previous = config
    return {
        "schema_version": PAPER_ASSET_SCHEMA_VERSION,
        "benchmark_release": report.get("benchmark_release"),
        "analysis_report_sha256": sha256(
            json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "cohort": primary.get("cohort"),
        "missing_cost": primary.get("missing_cost"),
        "rank_association_all_configurations": primary.get("rank_association"),
        "rank_association_best_per_model": primary.get("display_rank_association"),
        "rank_association_within_model_effort": primary.get(
            "effort_rank_association"
        ),
        "rank_association_bootstrap_intervals": _mapping(
            report, "bootstrap"
        ).get("rank_association_intervals"),
        "highest_pass_configuration": highest_pass,
        "unconstrained_lowest_cpsc_configuration": lowest_cpsc,
        "best_per_model_lowest_cpsc_configuration": display_lowest,
        "reliability_floor_change_points": floor_changes,
        "reliability_floor_bootstrap": _mapping(report, "bootstrap").get(
            "reliability_floor_policy"
        ),
        "task_weighting_sensitivity": primary.get("task_weighting_sensitivity"),
        "task_weighting_bootstrap_sensitivity": _mapping(
            report, "bootstrap"
        ).get("task_weighting_sensitivity"),
        "infrastructure_exclusion_audit": {
            key: value
            for key, value in _mapping(
                primary, "infrastructure_exclusion_audit"
            ).items()
            if key != "configurations"
        },
        "bootstrap": {
            "method": _mapping(report, "bootstrap").get("method"),
            "cluster_count": _mapping(report, "bootstrap").get("cluster_count"),
            "replicates": _mapping(report, "bootstrap").get("replicates"),
            "seed": _mapping(report, "bootstrap").get("seed"),
        },
        "leaderboard_reconciliation": report.get("leaderboard_reconciliation"),
        "common_price_repricing": report.get("common_price_repricing"),
        "provider_cost_provenance": report.get("provider_cost_provenance"),
        "source_metadata": report.get("source_metadata"),
        "anchor_success_budget_sensitivity": report.get(
            "anchor_success_budget_sensitivity"
        ),
        "panel_solvedness_strata": _mapping(
            _mapping(primary, "task_mix"), "panel_solvedness_strata"
        ).get("summaries"),
        "leave_one_family_out_panel_solvedness": {
            key: value
            for key, value in _mapping(
                _mapping(primary, "task_mix"),
                "leave_one_family_out_panel_solvedness",
            ).items()
            if key not in {"assignments", "configurations"}
        },
        "gpt_5_6_group_out_panel_solvedness": {
            key: value
            for key, value in _mapping(
                _mapping(primary, "task_mix"),
                "gpt_5_6_group_out_panel_solvedness",
            ).items()
            if key not in {"assignments", "configurations"}
        },
    }


def render_rank_divergence_svg(report: dict[str, Any]) -> str:
    primary = _mapping(report, "primary")
    bootstrap = _mapping(report, "bootstrap")
    rows = _rows(primary, "configurations")
    association_intervals = _mapping(bootstrap, "rank_association_intervals")
    all_interval = _mapping(association_intervals, "all_configurations")
    display_interval = _mapping(association_intervals, "fixed_display_panel")
    all_point = _mapping(primary, "rank_association")
    display_point = _mapping(primary, "display_rank_association")
    width, height = 1200, 850
    left, right, top, bottom = 120, 70, 145, 105
    plot_w = width - left - right
    plot_h = height - top - bottom
    maximum_rank = max(
        max(float(row["pass_rate_rank"]), float(row["realized_cpsc_rank"]))
        for row in rows
    )

    def x(rank: float) -> float:
        return left + (rank - 1) / max(1, maximum_rank - 1) * plot_w

    def y(rank: float) -> float:
        return top + (rank - 1) / max(1, maximum_rank - 1) * plot_h

    elements = _svg_header(
        width,
        height,
        "Rank association depends on the comparison panel",
        (
            f"All 41 configurations: rho {float(all_point['spearman']):+.2f} "
            f"[{float(all_interval['spearman_ci_low']):+.2f}, "
            f"{float(all_interval['spearman_ci_high']):+.2f}]. Fixed 13-model panel: "
            f"{float(display_point['spearman']):+.2f} "
            f"[{float(display_interval['spearman_ci_low']):+.2f}, "
            f"{float(display_interval['spearman_ci_high']):+.2f}]."
        ),
    )
    ticks = [1, 10, 20, 30, 40]
    for tick in ticks:
        if tick > maximum_rank:
            continue
        elements.append(_line(x(tick), top, x(tick), top + plot_h, LIGHT_GRAY, 1))
        elements.append(_line(left, y(tick), left + plot_w, y(tick), LIGHT_GRAY, 1))
        elements.append(_text(x(tick), top + plot_h + 34, str(tick), anchor="middle"))
        elements.append(_text(left - 24, y(tick) + 6, str(tick), anchor="end"))
    elements.append(_line(left, top, left + plot_w, top + plot_h, GRAY, 2, dash="8 7"))
    elements.append(_line(left, top + plot_h, left + plot_w, top + plot_h, CHARCOAL, 2))
    elements.append(_line(left, top, left, top + plot_h, CHARCOAL, 2))
    elements.append(
        _text(left + plot_w / 2, height - 32, "Pass-rate rank", anchor="middle", size=19)
    )
    elements.append(
        _text(29, top + plot_h / 2, "Realized-CPSC rank", anchor="middle", size=19,
              transform=f"rotate(-90 29 {top + plot_h / 2:.1f})")
    )

    highlights = {
        "mini_swe_agent_gpt_5_6_sol_max": (BLUE, 10, -16),
        "mini_swe_agent_gpt_5_6_luna_max": (GOLD, 10, -14),
        "mini_swe_agent_gpt_5_6_terra_medium": (ORANGE, 10, 26),
        "mini_swe_agent_gpt_5_6_luna_high": ("#6F7E3F", 10, 26),
    }
    for row in rows:
        cx = x(float(row["pass_rate_rank"]))
        cy = y(float(row["realized_cpsc_rank"]))
        frontier = bool(row.get("attempt_cost_pareto_frontier"))
        config = str(row["config"])
        color = highlights.get(config, (CHARCOAL, 0, 0))[0] if config in highlights else CHARCOAL
        fill = color if config in highlights else ("white" if frontier else GRAY)
        stroke = color if config in highlights or frontier else "white"
        radius = 8 if config in highlights else 5
        elements.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{2 if frontier else 1}" opacity="0.92"/>'
        )
        if config in highlights:
            _, dx, dy = highlights[config]
            label = _short_configuration_label(row)
            elements.append(_text(cx + dx, cy + dy, label, color=color, size=15,
                                  weight=650, anchor="start" if dx >= 0 else "end"))
    elements.append(_text(left + 18, top + 26, "Ranks match", color=GRAY, size=14))
    elements.append(
        _text(
            left,
            height - 10,
            "Task-bootstrap intervals assess suite composition. The sign flip and pooled within-model rho of -0.68 show that effort scaling drives the all-config result.",
            color="#5D6670",
            size=13,
        )
    )
    return "".join(elements) + "</svg>\n"


def render_economic_frontier_svg(report: dict[str, Any]) -> str:
    primary = _mapping(report, "primary")
    rows = _rows(primary, "configurations")
    frontier_rows = sorted(
        [row for row in rows if row.get("attempt_cost_pareto_frontier")],
        key=lambda row: float(row["pass_rate"]),
    )
    width, height = 1320, 850
    left, right, top, bottom = 120, 70, 160, 115
    plot_w = width - left - right
    plot_h = height - top - bottom
    x_max = 0.8
    positive_costs = [
        float(row["mean_cost_per_attempt_usd"])
        for row in rows
        if float(row["mean_cost_per_attempt_usd"]) > 0
    ]
    y_min = min(0.05, min(positive_costs))
    y_max = max(30.0, max(positive_costs) * 1.08)
    log_min = math.log10(y_min)
    log_max = math.log10(y_max)

    def x(value: float) -> float:
        return left + value / x_max * plot_w

    def y(value: float) -> float:
        return top + (log_max - math.log10(value)) / (log_max - log_min) * plot_h

    frontier_models = sorted({str(row.get("model", "")) for row in frontier_rows})
    subtitle = (
        f"{len(rows)} configurations; reported-price Pareto frontier families: "
        + ", ".join(_display_model_name(model) for model in frontier_models)
        + "."
    )
    elements = _svg_header(
        width,
        height,
        "Solve rate versus mean attempt cost",
        subtitle,
    )

    for tick in (0.0, 0.2, 0.4, 0.6, 0.8):
        px = x(tick)
        elements.append(_line(px, top, px, top + plot_h, LIGHT_GRAY, 1))
        elements.append(_text(px, top + plot_h + 34, f"{tick:.0%}", anchor="middle"))
    for tick in (0.1, 0.25, 0.5, 1, 2, 5, 10, 25):
        if tick < y_min or tick > y_max:
            continue
        py = y(tick)
        elements.append(_line(left, py, left + plot_w, py, LIGHT_GRAY, 1))
        label = f"${tick:.2f}" if tick < 1 else f"${tick:g}"
        elements.append(_text(left - 18, py + 6, label, anchor="end"))
    elements.append(_line(left, top + plot_h, left + plot_w, top + plot_h, CHARCOAL, 2))
    elements.append(_line(left, top, left, top + plot_h, CHARCOAL, 2))
    elements.append(
        _text(left + plot_w / 2, height - 34, "Attempt solve rate", anchor="middle", size=19)
    )
    elements.append(
        _text(
            29,
            top + plot_h / 2,
            "Mean attempt cost (USD, log scale)",
            anchor="middle",
            size=19,
            transform=f"rotate(-90 29 {top + plot_h / 2:.1f})",
        )
    )

    if frontier_rows:
        path = " L ".join(
            f"{x(float(row['pass_rate'])):.1f} {y(float(row['mean_cost_per_attempt_usd'])):.1f}"
            for row in frontier_rows
        )
        elements.append(
            f'<path d="M {path}" fill="none" stroke="{CHARCOAL}" stroke-width="2.5" '
            'stroke-linejoin="round" opacity="0.72"/>'
        )

    for row in rows:
        if row.get("attempt_cost_pareto_frontier"):
            continue
        elements.append(
            f'<circle cx="{x(float(row["pass_rate"])):.1f}" '
            f'cy="{y(float(row["mean_cost_per_attempt_usd"])):.1f}" r="5" '
            f'fill="{GRAY}" stroke="white" stroke-width="1" opacity="0.65"/>'
        )

    family_styles = {
        "gpt-5-6-sol": (BLUE, "diamond"),
        "gpt-5-6-luna": (GOLD, "circle"),
        "gpt-5-6-terra": (ORANGE, "square"),
    }
    for row in frontier_rows:
        px = x(float(row["pass_rate"]))
        py = y(float(row["mean_cost_per_attempt_usd"]))
        color, shape = family_styles.get(str(row.get("model")), (CHARCOAL, "circle"))
        elements.append(_frontier_marker(px, py, color, shape))

    selected_configs = {
        str(row.get("minimum_cpsc_config"))
        for row in _rows(primary, "reliability_floor_curve")
        if row.get("minimum_cpsc_config")
    }
    if rows:
        selected_configs.add(max(rows, key=lambda row: float(row["pass_rate"]))["config"])
    annotation_offsets = {
        "mini_swe_agent_gpt_5_6_terra_medium": (-10, 27, "end"),
        "mini_swe_agent_gpt_5_6_luna_high": (-10, -15, "end"),
        "mini_swe_agent_gpt_5_6_terra_high": (-10, 27, "end"),
        "mini_swe_agent_gpt_5_6_luna_xhigh": (-10, -15, "end"),
        "mini_swe_agent_gpt_5_6_sol_medium": (-10, 27, "end"),
        "mini_swe_agent_gpt_5_6_luna_max": (-10, 27, "end"),
        "mini_swe_agent_gpt_5_6_sol_xhigh": (-10, 27, "end"),
        "mini_swe_agent_gpt_5_6_sol_max": (-10, -15, "end"),
    }
    for row in frontier_rows:
        config = str(row["config"])
        if config not in selected_configs:
            continue
        px = x(float(row["pass_rate"]))
        py = y(float(row["mean_cost_per_attempt_usd"]))
        color, _ = family_styles.get(str(row.get("model")), (CHARCOAL, "circle"))
        dx, dy, anchor = annotation_offsets.get(config, (10, -14, "start"))
        elements.append(
            _text(
                px + dx,
                py + dy,
                _short_config_id(config),
                color=color,
                size=13,
                weight=650,
                anchor=anchor,
            )
        )

    legend = [
        (BLUE, "diamond", "GPT-5.6 Sol"),
        (GOLD, "circle", "GPT-5.6 Luna"),
        (ORANGE, "square", "GPT-5.6 Terra"),
    ]
    legend_x = left
    for color, shape, label in legend:
        elements.append(_frontier_marker(legend_x, 118, color, shape))
        elements.append(_text(legend_x + 18, 123, label, size=13, weight=650))
        legend_x += 170
    elements.append(
        f'<circle cx="{legend_x:.1f}" cy="118" r="5" fill="{GRAY}" opacity="0.65"/>'
    )
    elements.append(_text(legend_x + 16, 123, "Other configurations", size=13))
    elements.append(
        _text(
            left,
            height - 10,
            "Frontier uses observed mean attempt cost and pass rate. Provider price semantics are not harmonized; every highlighted frontier point uses the OpenAI route.",
            color="#5D6670",
            size=13,
        )
    )
    return "".join(elements) + "</svg>\n"


def render_invoice_work_frontiers_svg(report: dict[str, Any]) -> str:
    rows = _rows(_mapping(report, "primary"), "resource_intensity")
    width, height = 1420, 820
    top, bottom = 180, 125
    panel_width = 560
    panel_height = height - top - bottom
    left_origins = (105, 790)
    x_max = 0.8
    panels = (
        {
            "origin": left_origins[0],
            "field": "reported_cpsc_usd",
            "frontier": "reported_cpsc_pareto_frontier",
            "title": "Reported invoice per verified success",
            "unit": "USD, log scale",
            "color": GOLD,
            "bounds": (1.0, 100.0),
            "ticks": (1, 2, 5, 10, 25, 50, 100),
            "labels": {
                "mini_swe_agent_gpt_5_6_terra_medium": (-8, 24, "end"),
                "mini_swe_agent_gpt_5_6_luna_max": (-8, -12, "end"),
                "mini_swe_agent_gpt_5_6_sol_high": (8, 24, "start"),
                "mini_swe_agent_gpt_5_6_sol_max": (-8, -12, "end"),
            },
        },
        {
            "origin": left_origins[1],
            "field": "agent_steps_per_success",
            "frontier": "agent_steps_per_success_pareto_frontier",
            "title": "Agent steps per verified success",
            "unit": "Steps, log scale",
            "color": BLUE,
            "bounds": (40.0, 4000.0),
            "ticks": (50, 100, 250, 500, 1000, 2500),
            "labels": {
                "mini_swe_agent_gpt_5_6_sol_medium": (-8, -12, "end"),
                "mini_swe_agent_gpt_5_6_sol_high": (8, -12, "start"),
                "mini_swe_agent_gpt_5_6_sol_xhigh": (8, 23, "start"),
                "mini_swe_agent_gpt_5_6_sol_max": (-8, -12, "end"),
            },
        },
    )
    elements = _svg_header(
        width,
        height,
        "Reported invoice and agent-work frontiers",
        (
            "Dollar surface: 41 configurations. Step surface: 40 configurations with complete "
            "step fields. Lower is better on the vertical axis."
        ),
    )
    for panel in panels:
        left = float(panel["origin"])
        field = str(panel["field"])
        frontier_field = str(panel["frontier"])
        color = str(panel["color"])
        lower, upper = (float(value) for value in panel["bounds"])
        log_lower = math.log10(lower)
        log_upper = math.log10(upper)

        def x(value: float) -> float:
            return left + value / x_max * panel_width

        def y(value: float) -> float:
            clipped = min(upper, max(lower, value))
            return top + (log_upper - math.log10(clipped)) / (
                log_upper - log_lower
            ) * panel_height

        elements.append(
            _text(left, top - 62, str(panel["title"]), size=18, weight=700)
        )
        elements.append(
            _text(left, top - 35, str(panel["unit"]), size=13, color="#5D6670")
        )
        for tick in (0.0, 0.2, 0.4, 0.6, 0.8):
            px = x(tick)
            elements.append(_line(px, top, px, top + panel_height, LIGHT_GRAY, 1))
            elements.append(
                _text(px, top + panel_height + 32, f"{tick:.0%}", anchor="middle")
            )
        for tick_value in panel["ticks"]:
            tick = float(tick_value)
            py = y(tick)
            elements.append(_line(left, py, left + panel_width, py, LIGHT_GRAY, 1))
            tick_label = (
                f"${tick:g}" if field == "reported_cpsc_usd" else f"{tick:g}"
            )
            elements.append(_text(left - 14, py + 5, tick_label, anchor="end"))
        elements.append(
            _line(left, top + panel_height, left + panel_width, top + panel_height, CHARCOAL, 2)
        )
        elements.append(_line(left, top, left, top + panel_height, CHARCOAL, 2))
        elements.append(
            _text(
                left + panel_width / 2,
                height - 58,
                "Attempt solve rate",
                anchor="middle",
                size=17,
            )
        )

        panel_rows = [row for row in rows if row.get(field) is not None]
        frontier_rows = sorted(
            [row for row in panel_rows if row.get(frontier_field)],
            key=lambda row: float(row["pass_rate"]),
        )
        if frontier_rows:
            path = " L ".join(
                f"{x(float(row['pass_rate'])):.1f} {y(float(row[field])):.1f}"
                for row in frontier_rows
            )
            elements.append(
                f'<path d="M {path}" fill="none" stroke="{color}" '
                'stroke-width="2.5" stroke-linejoin="round" opacity="0.78"/>'
            )
        for row in panel_rows:
            config = str(row["config"])
            frontier = bool(row.get(frontier_field))
            cx = x(float(row["pass_rate"]))
            cy = y(float(row[field]))
            if frontier:
                elements.append(
                    f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6.5" fill="{color}" '
                    'stroke="white" stroke-width="1.5"/>'
                )
            else:
                elements.append(
                    f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4.5" fill="{GRAY}" '
                    'stroke="white" stroke-width="1" opacity="0.58"/>'
                )
            labels = panel["labels"]
            if config in labels:
                dx, dy, anchor = labels[config]
                elements.append(
                    _text(
                        cx + float(dx),
                        cy + float(dy),
                        _short_config_id(config),
                        color=color,
                        size=12,
                        weight=650,
                        anchor=str(anchor),
                    )
                )
    elements.append(
        _text(
            105,
            height - 12,
            (
                "Provider-reported dollars answer the invoice question. Agent steps are a "
                "behavioral work proxy, not a common-price reconstruction or a FLOP measure."
            ),
            color="#5D6670",
            size=13,
        )
    )
    return "".join(elements) + "</svg>\n"


def _frontier_marker(x: float, y: float, color: str, shape: str) -> str:
    if shape == "square":
        return (
            f'<rect x="{x - 7:.1f}" y="{y - 7:.1f}" width="14" height="14" '
            f'fill="{color}" stroke="white" stroke-width="1.5"/>'
        )
    if shape == "diamond":
        return (
            f'<path d="M {x:.1f} {y - 9:.1f} L {x + 9:.1f} {y:.1f} '
            f'L {x:.1f} {y + 9:.1f} L {x - 9:.1f} {y:.1f} Z" '
            f'fill="{color}" stroke="white" stroke-width="1.5"/>'
        )
    return (
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="{color}" '
        'stroke="white" stroke-width="1.5"/>'
    )


def _display_model_name(model: str) -> str:
    replacements = {
        "gpt-5-6-sol": "GPT-5.6 Sol",
        "gpt-5-6-luna": "GPT-5.6 Luna",
        "gpt-5-6-terra": "GPT-5.6 Terra",
    }
    return replacements.get(model, model)


def render_reliability_floor_svg(report: dict[str, Any]) -> str:
    primary = _mapping(report, "primary")
    bootstrap = _mapping(report, "bootstrap")
    rows = _rows(primary, "reliability_floor_curve")
    policy_rows = _rows(bootstrap, "reliability_floor_policy")
    frequency_rows = _rows(bootstrap, "reliability_floor_selection_frequencies")
    policy_by_floor = {float(row["minimum_pass_rate"]): row for row in policy_rows}
    eligible = [row for row in rows if row.get("minimum_cpsc_usd") is not None]
    width, height = 1320, 810
    left, top, bottom = 92, 180, 130
    panel_width = 520
    plot_h = height - top - bottom
    max_floor = max(float(row["minimum_pass_rate"]) for row in rows)
    plotted_values = [float(row["minimum_cpsc_usd"]) for row in eligible] or [1.0]
    y_max = max(8.0, max(plotted_values) * 1.16)

    def x(value: float) -> float:
        return left + value / max_floor * panel_width

    def y(value: float) -> float:
        return top + plot_h - value / y_max * plot_h

    elements = _svg_header(
        width,
        height,
        "Reliability requirements change both the choice and whether a choice exists",
        (
            "Panel A uses the observed point policy. Panel B reselects the policy in each "
            "task bootstrap and includes an explicit no-eligible outcome."
        ),
    )
    elements.append(_text(left, 126, "Panel A", size=17, weight=700))
    elements.append(
        _text(left + 82, 126, "Observed minimum-CPSC policy", size=17, weight=600)
    )
    for index in range(5):
        tick = index * y_max / 4
        elements.append(_line(left, y(tick), left + panel_width, y(tick), LIGHT_GRAY, 1))
        elements.append(_text(left - 18, y(tick) + 6, f"${tick:.0f}", anchor="end"))
    for tick_index in range(0, 16, 2):
        tick = tick_index / 20
        elements.append(_text(x(tick), top + plot_h + 35, f"{tick:.0%}", anchor="middle"))
    elements.append(_line(left, top + plot_h, left + panel_width, top + plot_h, CHARCOAL, 2))
    elements.append(_line(left, top, left, top + plot_h, CHARCOAL, 2))
    elements.append(
        _text(
            left + panel_width / 2,
            height - 56,
            "Required minimum solve rate",
            anchor="middle",
            size=17,
        )
    )
    elements.append(
        _text(
            28,
            top + plot_h / 2,
            "Minimum realized CPSC (USD)",
            anchor="middle",
            size=17,
            transform=f"rotate(-90 28 {top + plot_h / 2:.1f})",
        )
    )

    points = [
        (x(float(row["minimum_pass_rate"])), y(float(row["minimum_cpsc_usd"])))
        for row in eligible
    ]
    path_parts = []
    for index, (px, py) in enumerate(points):
        if index == 0:
            path_parts.append(f"M {px:.1f} {py:.1f}")
        else:
            path_parts.append(f"H {px:.1f} V {py:.1f}")
    elements.append(
        f'<path d="{" ".join(path_parts)}" fill="none" stroke="{BLUE}" '
        'stroke-width="4" stroke-linejoin="round"/>'
    )
    for px, py in points:
        elements.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="5" fill="{BLUE}"/>')

    change_rows = []
    previous_config: object = object()
    for row in eligible:
        if row.get("minimum_cpsc_config") != previous_config:
            change_rows.append(row)
            previous_config = row.get("minimum_cpsc_config")
    annotation_offsets = {
        "mini_swe_agent_gpt_5_6_terra_medium": (8, -18, "start"),
        "mini_swe_agent_gpt_5_6_luna_high": (8, 32, "start"),
        "mini_swe_agent_gpt_5_6_terra_high": (8, -20, "start"),
        "mini_swe_agent_gpt_5_6_luna_xhigh": (8, 34, "start"),
        "mini_swe_agent_gpt_5_6_sol_medium": (8, -20, "start"),
        "mini_swe_agent_gpt_5_6_luna_max": (-8, 30, "end"),
        "mini_swe_agent_gpt_5_6_sol_xhigh": (-8, -18, "end"),
    }
    for row in change_rows:
        floor = float(row["minimum_pass_rate"])
        px = x(floor)
        py = y(float(row["minimum_cpsc_usd"]))
        config = str(row.get("minimum_cpsc_config"))
        dx, offset, anchor = annotation_offsets.get(config, (8, -18, "start"))
        label = _floor_configuration_label(config)
        elements.append(
            _text(
                px + dx,
                py + offset,
                f"{label}  ${float(row['minimum_cpsc_usd']):.2f}",
                color=BLUE,
                size=12,
                weight=650,
                anchor=anchor,
            )
        )
    missing = [row for row in rows if row.get("minimum_cpsc_usd") is None]
    for row in missing:
        px = x(float(row["minimum_pass_rate"]))
        py = y(0.35)
        elements.append(_line(px - 7, py - 7, px + 7, py + 7, ORANGE, 3))
        elements.append(_line(px - 7, py + 7, px + 7, py - 7, ORANGE, 3))
        elements.append(
            _text(
                px - 8,
                py - 18,
                "No eligible configuration",
                color=ORANGE,
                size=13,
                weight=650,
                anchor="end",
            )
        )

    panel_b_left = 735
    panel_b_width = 520
    elements.append(_text(panel_b_left, 126, "Panel B", size=17, weight=700))
    elements.append(
        _text(
            panel_b_left + 82,
            126,
            "Bootstrap selection composition",
            size=17,
            weight=600,
        )
    )
    selected_floors = (0.65, 0.70, 0.75)
    selected_configs = (
        "mini_swe_agent_gpt_5_6_luna_max",
        "mini_swe_agent_gpt_5_6_sol_high",
        "mini_swe_agent_gpt_5_6_sol_xhigh",
        "mini_swe_agent_gpt_5_6_sol_max",
    )
    categories = (
        (selected_configs[0], "Luna max", GOLD),
        (selected_configs[1], "Sol high", "#86B6DA"),
        (selected_configs[2], "Sol xhigh", BLUE),
        (selected_configs[3], "Sol max", "#173F6B"),
        ("other_eligible", "Other eligible", GRAY),
        ("no_eligible", "No eligible", ORANGE),
    )
    frequencies = {
        (float(row["minimum_pass_rate"]), str(row["config"])): float(
            row["selection_share_all_replicates"]
        )
        for row in frequency_rows
    }
    bar_top = 235
    bar_height = 68
    bar_gap = 96
    for bar_index, floor in enumerate(selected_floors):
        py = bar_top + bar_index * bar_gap
        policy = policy_by_floor.get(floor, {})
        no_eligible_count = policy.get("no_eligible_configuration_replicates")
        replicates = bootstrap.get("replicates")
        no_eligible_share = (
            float(no_eligible_count) / float(replicates)
            if no_eligible_count is not None and replicates
            else 0.0
        )
        named_shares = {
            config: frequencies.get((floor, config), 0.0) for config in selected_configs
        }
        other_share = max(
            0.0,
            1.0 - no_eligible_share - sum(named_shares.values()),
        )
        shares = {
            **named_shares,
            "other_eligible": other_share,
            "no_eligible": no_eligible_share,
        }
        elements.append(
            _text(panel_b_left - 18, py + 42, f"{floor:.0%}", anchor="end", weight=650)
        )
        cursor = panel_b_left
        for category, _, color in categories:
            share = shares[category]
            segment_width = panel_b_width * share
            if segment_width <= 0:
                continue
            elements.append(
                f'<rect x="{cursor:.1f}" y="{py:.1f}" width="{segment_width:.1f}" '
                f'height="{bar_height}" fill="{color}"/>'
            )
            if share >= 0.075:
                label_color = "white" if category in {selected_configs[2], selected_configs[3]} else CHARCOAL
                elements.append(
                    _text(
                        cursor + segment_width / 2,
                        py + 42,
                        f"{share:.0%}",
                        anchor="middle",
                        color=label_color,
                        size=13,
                        weight=700,
                    )
                )
            cursor += segment_width
        elements.append(
            f'<rect x="{panel_b_left}" y="{py}" width="{panel_b_width}" '
            f'height="{bar_height}" fill="none" stroke="{CHARCOAL}" stroke-width="1"/>'
        )

    legend_y = 555
    for index, (_, label, color) in enumerate(categories):
        column = index % 3
        row_index = index // 3
        lx = panel_b_left + column * 175
        ly = legend_y + row_index * 34
        elements.append(
            f'<rect x="{lx}" y="{ly - 13}" width="18" height="14" fill="{color}"/>'
        )
        elements.append(_text(lx + 27, ly, label, size=13))
    elements.append(
        _text(
            panel_b_left,
            652,
            "Shares use all bootstrap replicates; conditional shares exclude no-eligible draws.",
            color="#5D6670",
            size=13,
        )
    )
    elements.append(
        _text(
            left,
            height - 12,
            (
                "Eligibility and pass rate are recomputed for each resampled task mixture, so a "
                "configuration below a floor in the full sample can still be selected in a draw."
            ),
            color="#5D6670",
            size=13,
        )
    )
    return "".join(elements) + "</svg>\n"


def point_floor_exists(rows: list[dict[str, Any]], floor: float) -> bool:
    return any(
        float(row["minimum_pass_rate"]) == floor
        and row.get("minimum_cpsc_usd") is not None
        for row in rows
    )


def render_failure_cost_decomposition_svg(report: dict[str, Any]) -> str:
    rows = sorted(
        _rows(_mapping(report, "primary"), "display_configurations"),
        key=lambda row: float(row["realized_cpsc_usd"]),
    )
    width, height = 1320, 1000
    left, top, bottom = 255, 160, 80
    row_h = (height - top - bottom) / max(1, len(rows))
    cpsc_left, cpsc_width = left, 440
    share_left, share_width = 830, 390
    max_cpsc = max(float(row["realized_cpsc_usd"]) for row in rows)
    x_max = max(85.0, max_cpsc * 1.06)
    elements = _svg_header(
        width,
        height,
        "Realized CPSC and failure-cost composition",
        "One highest-pass-rate configuration per model. Dots show total CPSC; bars split successful-work spend from reliability tax.",
    )
    elements.append(_text(cpsc_left, top - 28, "Realized CPSC (USD)", size=17, weight=650))
    elements.append(_text(share_left, top - 28, "Share of realized CPSC", size=17, weight=650))
    for tick in (0, 20, 40, 60, 80):
        px = cpsc_left + tick / x_max * cpsc_width
        elements.append(_line(px, top - 8, px, height - bottom, LIGHT_GRAY, 1))
        elements.append(_text(px, height - bottom + 28, f"${tick}", anchor="middle", size=13))
    for tick in (0, 25, 50, 75, 100):
        px = share_left + tick / 100 * share_width
        elements.append(_text(px, height - bottom + 28, f"{tick}%", anchor="middle", size=13))

    for index, row in enumerate(rows):
        cy = top + index * row_h + row_h / 2
        if index % 2:
            elements.append(
                f'<rect x="18" y="{cy - row_h / 2:.1f}" width="1284" height="{row_h:.1f}" fill="#F7F8F9"/>'
            )
        label = _short_configuration_label(row)
        elements.append(_text(left - 18, cy + 5, label, anchor="end", size=14, weight=560))
        cpsc = float(row["realized_cpsc_usd"])
        dot_x = cpsc_left + cpsc / x_max * cpsc_width
        elements.append(_line(cpsc_left, cy, dot_x, cy, PALE_BLUE, 5))
        elements.append(f'<circle cx="{dot_x:.1f}" cy="{cy:.1f}" r="7" fill="{BLUE}"/>')
        elements.append(_text(dot_x + 11, cy + 5, f"${cpsc:.2f}", color=BLUE, size=13, weight=650))

        tax_share = float(row["realized_reliability_tax_share"])
        success_share = max(0.0, 1.0 - tax_share)
        bar_y = cy - 10
        elements.append(
            f'<rect x="{share_left}" y="{bar_y:.1f}" width="{share_width * success_share:.1f}" '
            f'height="20" fill="{BLUE}"/>'
        )
        elements.append(
            f'<rect x="{share_left + share_width * success_share:.1f}" y="{bar_y:.1f}" '
            f'width="{share_width * tax_share:.1f}" height="20" fill="{GOLD}"/>'
        )
        elements.append(_text(share_left + share_width + 12, cy + 5, f"{tax_share:.0%} tax",
                              color="#80601F", size=13, weight=650))
    elements.append(f'<rect x="{share_left}" y="105" width="18" height="12" fill="{BLUE}"/>')
    elements.append(_text(share_left + 26, 116, "Conditional successful spend", size=13))
    elements.append(f'<rect x="{share_left + 205}" y="105" width="18" height="12" fill="{GOLD}"/>')
    elements.append(_text(share_left + 231, 116, "Realized reliability tax", size=13))
    elements.append(
        _text(
            18,
            height - 12,
            "Best-per-model selection is descriptive. Tax share is a cost composition, not an efficiency rank, and rises mechanically as pass rate falls.",
            color="#5D6670",
            size=13,
        )
    )
    return "".join(elements) + "</svg>\n"


def render_task_coverage_svg(report: dict[str, Any]) -> str:
    task_mix = _mapping(_mapping(report, "primary"), "task_mix")
    source_rows = _rows(task_mix, "success_heterogeneity")
    matched_rows = _rows(task_mix, "matched_solved_task_comparisons")
    width, height = 1300, 650
    elements = _svg_header(
        width,
        height,
        "Task coverage reveals different solved-task footprints",
        "Four-run cells are split by observed successes. Coverage is the share of 113 tasks solved at least once.",
    )
    if not source_rows:
        elements.append(_text(40, 150, "No task-coverage rows available.", color=GRAY))
        return "".join(elements) + "</svg>\n"

    priorities = [
        "mini_swe_agent_gpt_5_6_sol_max",
        "mini_swe_agent_gpt_5_6_luna_max",
        "mini_swe_agent_gpt_5_6_terra_medium",
        "mini_swe_agent_gpt_5_6_luna_high",
    ]
    by_config = {str(row["config"]): row for row in source_rows}
    rows = [by_config[config] for config in priorities if config in by_config]
    if not rows:
        rows = source_rows[:4]

    label_x = 238
    bar_x, bar_w = 270, 620
    coverage_x, coverage_w = 970, 245
    top, row_h = 180, 85
    elements.append(_text(bar_x, 132, "Task outcome pattern", size=16, weight=650))
    elements.append(
        _text(coverage_x, 132, "Any-success task coverage", size=16, weight=650)
    )
    legend = [
        (ORANGE, "0/4"),
        (GOLD, "1-3/4"),
        (BLUE, "4/4"),
        (GRAY, "incomplete/excluded"),
    ]
    legend_x = bar_x
    for color, label in legend:
        elements.append(
            f'<rect x="{legend_x}" y="145" width="14" height="14" fill="{color}"/>'
        )
        elements.append(_text(legend_x + 21, 158, label, size=12))
        legend_x += 112 if label != "incomplete/excluded" else 175

    for index, row in enumerate(rows):
        cy = top + index * row_h + row_h / 2
        config = str(row["config"])
        elements.append(
            _text(label_x, cy + 6, _short_config_id(config), anchor="end", size=16, weight=650)
        )
        total_tasks = int(row["tasks_in_suite"])
        segments = [
            (int(row["zero_of_four_tasks"]), ORANGE),
            (int(row["one_to_three_of_four_tasks"]), GOLD),
            (int(row["four_of_four_tasks"]), BLUE),
            (
                int(row["incomplete_scored_attempt_tasks"])
                + int(row["no_scored_attempt_tasks"]),
                GRAY,
            ),
        ]
        cursor = bar_x
        for count, color in segments:
            segment_w = count / total_tasks * bar_w if total_tasks else 0
            if segment_w:
                elements.append(
                    f'<rect x="{cursor:.1f}" y="{cy - 15:.1f}" width="{segment_w:.1f}" '
                    f'height="30" fill="{color}"/>'
                )
                if segment_w >= 28:
                    elements.append(
                        _text(
                            cursor + segment_w / 2,
                            cy + 5,
                            str(count),
                            anchor="middle",
                            color="white" if color in (BLUE, ORANGE, GRAY) else CHARCOAL,
                            size=12,
                            weight=650,
                        )
                    )
            cursor += segment_w

        coverage = float(row["task_coverage_rate"])
        elements.append(_line(coverage_x, cy, coverage_x + coverage_w, cy, LIGHT_GRAY, 5))
        dot_x = coverage_x + coverage * coverage_w
        elements.append(
            f'<circle cx="{dot_x:.1f}" cy="{cy:.1f}" r="8" fill="{CHARCOAL}"/>'
        )
        elements.append(
            _text(
                coverage_x + coverage_w + 12,
                cy + 6,
                f"{coverage:.0%}",
                size=15,
                weight=650,
            )
        )

    luna_sol = _find_matched_pair(
        matched_rows,
        "mini_swe_agent_gpt_5_6_luna_max",
        "mini_swe_agent_gpt_5_6_sol_max",
    )
    terra_sol = _find_matched_pair(
        matched_rows,
        "mini_swe_agent_gpt_5_6_terra_medium",
        "mini_swe_agent_gpt_5_6_sol_max",
    )
    notes = []
    if luna_sol:
        notes.append(
            f"Luna max / Sol max overlap: {int(luna_sol['matched_tasks'])} tasks, "
            f"Jaccard {float(luna_sol['solved_task_jaccard']):.2f}"
        )
    if terra_sol:
        notes.append(
            f"Terra medium / Sol max: {int(terra_sol['matched_tasks'])} tasks, "
            f"Jaccard {float(terra_sol['solved_task_jaccard']):.2f}"
        )
    elements.append(
        _text(
            32,
            height - 28,
            ";  ".join(notes) if notes else "Matched solved-task overlap not available.",
            color="#5D6670",
            size=14,
        )
    )
    return "".join(elements) + "</svg>\n"


def _find_matched_pair(
    rows: list[dict[str, Any]],
    config_a: str,
    config_b: str,
) -> dict[str, Any] | None:
    for row in rows:
        if {str(row.get("config_a")), str(row.get("config_b"))} == {
            config_a,
            config_b,
        }:
            return row
    return None


def _missing_cost_sensitivity_rows(report: dict[str, Any]) -> list[dict[str, object]]:
    output = []
    for sensitivity in report.get("missing_cost_sensitivities") or []:
        for row in sensitivity.get("configurations") or []:
            output.append(
                {
                    "sensitivity_name": sensitivity.get("name"),
                    "method": sensitivity.get("method"),
                    **row,
                }
            )
    return output


def _failure_charge_rows(report: dict[str, Any]) -> list[dict[str, object]]:
    sensitivity = report.get("failure_charge_sensitivity") or {}
    output = []
    for scenario in sensitivity.get("scenarios") or []:
        for row in scenario.get("configurations") or []:
            output.append(
                {
                    "multiplier": scenario.get("multiplier"),
                    "anchor_config": sensitivity.get("anchor_config"),
                    "proxy_budget_construction": sensitivity.get(
                        "proxy_budget_construction"
                    ),
                    **row,
                }
            )
    return output


def _anchor_success_budget_rows(
    report: dict[str, Any],
) -> list[dict[str, object]]:
    sensitivity = report.get("anchor_success_budget_sensitivity") or {}
    output = []
    for scenario in sensitivity.get("scenarios") or []:
        for row in scenario.get("configurations") or []:
            output.append(
                {
                    "multiplier": scenario.get("multiplier"),
                    "anchor_config": sensitivity.get("anchor_config"),
                    "common_basket_tasks": sensitivity.get("common_basket_tasks"),
                    "proxy_budget_construction": sensitivity.get(
                        "proxy_budget_construction"
                    ),
                    **row,
                }
            )
    return output


def _rank_association_interval_rows(
    bootstrap: dict[str, Any],
) -> list[dict[str, object]]:
    intervals = _mapping(bootstrap, "rank_association_intervals")
    return [
        {"panel": panel, **values}
        for panel, values in intervals.items()
        if isinstance(values, dict)
    ]


def _within_model_association_rows(
    primary: dict[str, Any],
    bootstrap: dict[str, Any],
) -> list[dict[str, object]]:
    point = _mapping(primary, "effort_rank_association")
    point_rows = {
        str(row["model"]): row
        for row in _rows(point, "by_model")
    }
    interval_rows = {
        str(row["model"]): row
        for row in _rows(bootstrap, "within_model_rank_association_intervals")
    }
    return [
        {
            **point_rows[model],
            **{
                key: value
                for key, value in interval_rows.get(model, {}).items()
                if key != "model"
            },
        }
        for model in sorted(point_rows)
    ]


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = _ordered_fieldnames(rows)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(
            {
                key: json.dumps(value, sort_keys=True)
                if isinstance(value, (dict, list))
                else value
                for key, value in row.items()
            }
            for row in rows
        )


def _ordered_fieldnames(rows: Iterable[dict[str, object]]) -> list[str]:
    output = []
    seen = set()
    for row in rows:
        for field in row:
            if field not in seen:
                seen.add(field)
                output.append(field)
    return output


def _mapping(value: dict[str, Any], field: str) -> dict[str, Any]:
    result = value.get(field)
    if not isinstance(result, dict):
        raise ValueError(f"DeepSWE report missing object: {field}")
    return result


def _rows(value: dict[str, Any], field: str) -> list[dict[str, Any]]:
    result = value.get(field)
    if not isinstance(result, list) or any(not isinstance(row, dict) for row in result):
        raise ValueError(f"DeepSWE report missing row list: {field}")
    return result


def _svg_header(width: int, height: int, title: str, subtitle: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#FFFFFF"/>',
        _text(28, 48, title, size=28, weight=700),
        _text(28, 80, subtitle, color="#5D6670", size=16),
    ]


def _line(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    color: str,
    width: float,
    *,
    dash: str | None = None,
) -> str:
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="{color}" stroke-width="{width}"{dash_attr}/>'
    )


def _text(
    x: float,
    y: float,
    value: object,
    *,
    anchor: str = "start",
    color: str = CHARCOAL,
    size: int = 16,
    weight: int = 400,
    transform: str | None = None,
) -> str:
    transform_attr = f' transform="{transform}"' if transform else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" fill="{color}" '
        f'font-family="Arial, Helvetica, sans-serif" font-size="{size}" '
        f'font-weight="{weight}"{transform_attr}>{escape(str(value))}</text>'
    )


def _short_configuration_label(row: dict[str, Any]) -> str:
    model = _short_model(str(row.get("model") or row.get("config") or "unknown"))
    effort = str(row.get("reasoning_effort") or "default")
    return f"{model} [{effort}]"


def _short_config_id(config: str) -> str:
    prefix = "mini_swe_agent_"
    compact = config[len(prefix):] if config.startswith(prefix) else config
    parts = compact.split("_")
    effort = parts[-1] if parts else ""
    model = "-".join(parts[:-1]) if len(parts) > 1 else compact
    return f"{_short_model(model)} [{effort}]"


def _floor_configuration_label(config: str) -> str:
    label = _short_config_id(config)
    return label.removeprefix("GPT-5.6 ")


def _short_model(model: str) -> str:
    labels = {
        "gpt-5-6-sol": "GPT-5.6 Sol",
        "gpt-5-6-terra": "GPT-5.6 Terra",
        "gpt-5-6-luna": "GPT-5.6 Luna",
        "gpt-5-5": "GPT-5.5",
        "gpt-5-4": "GPT-5.4",
        "claude-fable-5": "Claude Fable 5",
        "claude-opus-4-8": "Claude Opus 4.8",
        "claude-sonnet-5": "Claude Sonnet 5",
        "claude-sonnet-4-6": "Claude Sonnet 4.6",
        "glm-5-2": "GLM-5.2",
        "gemini-3-5-flash": "Gemini 3.5 Flash",
        "gemini-3-1-pro-preview": "Gemini 3.1 Pro Preview",
        "kimi-k2-7-code": "Kimi K2.7 Code",
    }
    return labels.get(model, model.replace("-", " ").title())


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build deterministic tables and figures for the DeepSWE CPSC paper"
    )
    parser.add_argument("trials", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args(argv)
    manifest = write_deepswe_paper_assets(
        _load_json(args.trials),
        _load_json(args.report),
        args.output_dir,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
