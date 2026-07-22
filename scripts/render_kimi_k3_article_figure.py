#!/usr/bin/env python3
"""Render the validated Kimi K3 two-panel article figure as a standalone SVG."""

from __future__ import annotations

import argparse
from html import escape
import json
from pathlib import Path
from typing import Any, Sequence


WIDTH = 1280
HEIGHT = 780
INK = "#172033"
MUTED = "#667085"
GRID = "#d9dee8"
ORANGE = "#d97706"
BLUE = "#2563eb"
NEUTRAL = "#475467"
LIGHT = "#98a2b3"
PAPER = "#fbfcfe"


def scale(value: float, domain: tuple[float, float], target: tuple[float, float]) -> float:
    start, end = domain
    output_start, output_end = target
    return output_start + (value - start) / (end - start) * (output_end - output_start)


def text_element(
    x: float,
    y: float,
    value: str,
    *,
    size: int = 13,
    fill: str = INK,
    weight: int = 400,
    anchor: str = "start",
    family: str = "Inter, ui-sans-serif, system-ui, sans-serif",
) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-size="{size}" '
        f'font-weight="{weight}" text-anchor="{anchor}" font-family="{family}">'
        f"{escape(value)}</text>"
    )


def marker(x: float, y: float, symbol: str, color: str, *, size: float = 5.5) -> str:
    if symbol == "L":
        points = f"{x:.1f},{y - size:.1f} {x + size:.1f},{y:.1f} {x:.1f},{y + size:.1f} {x - size:.1f},{y:.1f}"
        return f'<polygon points="{points}" fill="{color}" stroke="{INK}" stroke-width="1"/>'
    if symbol == "S":
        return (
            f'<rect x="{x - size:.1f}" y="{y - size:.1f}" width="{2 * size:.1f}" '
            f'height="{2 * size:.1f}" fill="{color}" stroke="{INK}" stroke-width="1"/>'
        )
    if symbol == "F":
        points = (
            f"{x:.1f},{y - size:.1f} {x + size:.1f},{y + size:.1f} {x - size:.1f},{y + size:.1f}"
        )
        return f'<polygon points="{points}" fill="white" stroke="{color}" stroke-width="2"/>'
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{size:.1f}" fill="{color}" stroke="{INK}" stroke-width="1"/>'


def render_svg(analysis: dict[str, Any]) -> str:
    standalone = analysis["standalone"]
    retry = analysis["retry"]
    all_costs = [float(row["realized_cpsc_usd"]) for row in standalone["models"].values()]
    all_costs.extend(float(row["realized_cpsc_usd"]) for row in standalone["k3_cache_sensitivity"])
    x_a_domain = (3.0, max(20.0, max(all_costs) * 1.08))
    y_a_domain = (0.47, 0.78)
    plot_a = (92.0, 600.0, 176.0, 604.0)
    retry_points = [row for model in retry["models"].values() for row in model["curve"]]
    x_b_domain = (
        0.0,
        max(22.0, max(float(row["stopped_cost_per_task_usd"]) for row in retry_points) * 1.08),
    )
    y_b_domain = (0.50, 0.93)
    plot_b = (686.0, 1194.0, 176.0, 604.0)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">',
        '<title id="title">Kimi K3 capability and retry economics on DeepSWE v1.1</title>',
        '<desc id="desc">Standalone cost and pass rate comparison plus fresh-context retry cost coverage curves.</desc>',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{PAPER}"/>',
        text_element(
            64, 45, "Kimi K3 capability and retry economics on DeepSWE v1.1", size=24, weight=700
        ),
        text_element(
            64,
            72,
            "108 matched tasks · four attempts per configuration · provider-reported invoice",
            size=13,
            fill=MUTED,
        ),
        '<g aria-label="research blossom" transform="translate(1232 42)">',
        f'<circle cx="0" cy="-8" r="5" fill="{ORANGE}" opacity="0.85"/>',
        f'<circle cx="8" cy="0" r="5" fill="{BLUE}" opacity="0.75"/>',
        f'<circle cx="0" cy="8" r="5" fill="{ORANGE}" opacity="0.45"/>',
        f'<circle cx="-8" cy="0" r="5" fill="{BLUE}" opacity="0.40"/>',
        f'<circle cx="0" cy="0" r="3" fill="{INK}"/>',
        "</g>",
        text_element(64, 112, "Panel A", size=12, fill=MUTED, weight=700),
        text_element(64, 137, "Pass@1 versus realized invoice per success", size=17, weight=650),
        text_element(658, 112, "Panel B", size=12, fill=MUTED, weight=700),
        text_element(658, 137, "Fresh-context retry cost–coverage curves", size=17, weight=650),
    ]

    left, right, top, bottom = plot_a
    for tick in (0.50, 0.55, 0.60, 0.65, 0.70, 0.75):
        y = scale(tick, y_a_domain, (bottom, top))
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>'
        )
        parts.append(
            text_element(
                left - 10,
                y + 4,
                f"{tick:.0%}",
                fill=MUTED,
                anchor="end",
                family="ui-monospace, SFMono-Regular, monospace",
            )
        )
    for tick in (4, 8, 12, 16, 20):
        if tick > x_a_domain[1]:
            continue
        x = scale(tick, x_a_domain, (left, right))
        parts.append(
            f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{bottom}" stroke="{GRID}" stroke-width="1"/>'
        )
        parts.append(
            text_element(
                x,
                bottom + 25,
                f"${tick}",
                fill=MUTED,
                anchor="middle",
                family="ui-monospace, SFMono-Regular, monospace",
            )
        )
    parts.extend(
        [
            f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="{INK}" stroke-width="1.2"/>',
            f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="{INK}" stroke-width="1.2"/>',
            text_element(
                (left + right) / 2,
                bottom + 52,
                "Realized invoice per verified success",
                size=12,
                fill=MUTED,
                anchor="middle",
            ),
        ]
    )
    sensitivity = sorted(standalone["k3_cache_sensitivity"], key=lambda row: row["cache_fraction"])
    k3_rate = float(standalone["models"]["K"]["pass_rate"])
    sensitivity_y = scale(k3_rate, y_a_domain, (bottom, top))
    sensitivity_x = [
        scale(float(row["realized_cpsc_usd"]), x_a_domain, (left, right)) for row in sensitivity
    ]
    parts.append(
        f'<line x1="{min(sensitivity_x):.1f}" y1="{sensitivity_y:.1f}" x2="{max(sensitivity_x):.1f}" y2="{sensitivity_y:.1f}" stroke="{ORANGE}" stroke-width="4" opacity="0.55"/>'
    )
    for x, row in zip(sensitivity_x, sensitivity, strict=True):
        parts.append(
            f'<circle cx="{x:.1f}" cy="{sensitivity_y:.1f}" r="3.5" fill="white" stroke="{ORANGE}" stroke-width="2"/>'
        )
        fraction = float(row["cache_fraction"])
        if abs(fraction - 0.98) >= 1e-9:
            parts.append(
                text_element(
                    x,
                    sensitivity_y - 11,
                    f"{fraction:.1%}",
                    size=10,
                    fill=ORANGE,
                    anchor="middle",
                    weight=650,
                )
            )

    offsets = {
        "G": (8, 19),
        "S": (8, -28),
        "X": (8, -43),
        "M": (8, -14),
        "T": (8, 42),
        "L": (8, 21),
        "K": (5, 27),
        "F": (-8, -15),
    }
    short_labels = {
        "G": "Grok high",
        "S": "Sol high",
        "X": "Sol xhigh",
        "M": "Sol max",
        "T": "Terra max",
        "L": "Luna max",
        "K": "K3 max · 98% imputed",
        "F": "Fable xhigh",
    }
    for symbol, row in standalone["models"].items():
        x = scale(float(row["realized_cpsc_usd"]), x_a_domain, (left, right))
        y = scale(float(row["pass_rate"]), y_a_domain, (bottom, top))
        low, high = [float(value) for value in row["pass_rate_ci"]]
        low_y = scale(low, y_a_domain, (bottom, top))
        high_y = scale(high, y_a_domain, (bottom, top))
        color = ORANGE if symbol == "K" else BLUE if symbol in {"S", "L"} else NEUTRAL
        parts.append(
            f'<line x1="{x:.1f}" y1="{low_y:.1f}" x2="{x:.1f}" y2="{high_y:.1f}" stroke="{color}" stroke-width="1.5" opacity="0.75"/>'
        )
        parts.append(
            f'<line x1="{x - 4:.1f}" y1="{low_y:.1f}" x2="{x + 4:.1f}" y2="{low_y:.1f}" stroke="{color}" stroke-width="1.5"/>'
        )
        parts.append(
            f'<line x1="{x - 4:.1f}" y1="{high_y:.1f}" x2="{x + 4:.1f}" y2="{high_y:.1f}" stroke="{color}" stroke-width="1.5"/>'
        )
        parts.append(marker(x, y, symbol, color))
        dx, dy = offsets.get(symbol, (8, -8))
        parts.append(
            text_element(
                x + dx,
                y + dy,
                short_labels.get(symbol, str(row["label"])),
                size=11,
                fill=color,
                weight=650 if symbol in {"K", "S", "L"} else 500,
                anchor="end" if dx < 0 else "start",
            )
        )

    left, right, top, bottom = plot_b
    for tick in (0.50, 0.60, 0.70, 0.80, 0.90):
        y = scale(tick, y_b_domain, (bottom, top))
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>'
        )
        parts.append(
            text_element(
                left - 10,
                y + 4,
                f"{tick:.0%}",
                fill=MUTED,
                anchor="end",
                family="ui-monospace, SFMono-Regular, monospace",
            )
        )
    for tick in (0, 5, 10, 15, 20):
        x = scale(tick, x_b_domain, (left, right))
        parts.append(
            f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{bottom}" stroke="{GRID}" stroke-width="1"/>'
        )
        parts.append(
            text_element(
                x,
                bottom + 25,
                f"${tick}",
                fill=MUTED,
                anchor="middle",
                family="ui-monospace, SFMono-Regular, monospace",
            )
        )
    parts.extend(
        [
            f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="{INK}" stroke-width="1.2"/>',
            f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="{INK}" stroke-width="1.2"/>',
            text_element(
                (left + right) / 2,
                bottom + 52,
                "Expected stopped invoice per task",
                size=12,
                fill=MUTED,
                anchor="middle",
            ),
        ]
    )
    styles = {
        "K": (ORANGE, "", "circle"),
        "L": (BLUE, "", "diamond"),
        "S": (NEUTRAL, "8 5", "square"),
        "F": (LIGHT, "3 5", "triangle"),
    }
    end_offsets = {"K": (10, 1), "L": (10, -12), "S": (10, 18), "F": (10, 16)}
    retry_labels = {"K": "K3 max", "L": "Luna max", "S": "Sol high", "F": "Fable xhigh"}
    for symbol in ("F", "S", "L", "K"):
        model = retry["models"][symbol]
        color, dash, _ = styles[symbol]
        points = [
            (
                scale(float(row["stopped_cost_per_task_usd"]), x_b_domain, (left, right)),
                scale(float(row["coverage"]), y_b_domain, (bottom, top)),
                int(row["attempts"]),
            )
            for row in model["curve"]
        ]
        point_text = " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in points)
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        parts.append(
            f'<polyline points="{point_text}" fill="none" stroke="{color}" stroke-width="2.5"{dash_attr}/>'
        )
        for x, y, attempts in points:
            parts.append(marker(x, y, symbol, color, size=5))
            parts.append(
                text_element(
                    x,
                    y - 10,
                    str(attempts),
                    size=9,
                    fill=color,
                    anchor="middle",
                    weight=700,
                    family="ui-monospace, SFMono-Regular, monospace",
                )
            )
        end_x, end_y, _ = points[-1]
        dx, dy = end_offsets[symbol]
        parts.append(
            text_element(
                end_x + dx, end_y + dy, retry_labels[symbol], size=11, fill=color, weight=650
            )
        )

    parts.extend(
        [
            text_element(
                64,
                690,
                "K3 cache sensitivity holds behavior and token volume fixed; only cached-input billing changes.",
                size=12,
                fill=MUTED,
            ),
            text_element(
                64,
                716,
                "Panel B uses random ordering without replacement and stops at first success. These are fresh-context retries, not same-context repair.",
                size=12,
                fill=MUTED,
            ),
            text_element(
                64,
                742,
                "Vertical bars are repository-bootstrap 95% intervals. Four Fable costs are configuration-mean imputed.",
                size=12,
                fill=MUTED,
            ),
            text_element(
                64,
                765,
                "Source: frozen DeepSWE v1.1 rows generated July 17, 2026 and retrieved July 19, 2026.",
                size=11,
                fill=MUTED,
            ),
            "</svg>",
        ]
    )
    return "\n".join(parts) + "\n"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    analysis = json.loads(args.analysis.read_text())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_svg(analysis))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
