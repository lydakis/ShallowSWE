#!/usr/bin/env python3
"""Price/efficiency clustering analysis over repair-loop results.

Answers three questions about a scored repair-loop run:

1. Are the observed $/success clusters statistically real?
   Bootstrap CIs over tasks (the sampling unit) for cost per success.
2. Do models cluster by *capability*?
   Distance + agglomerative clustering on per-task success-rate vectors.
   (On a run at ceiling this is degenerate; the script says so.)
3. How much of $/success is token behavior vs sticker price?
   Reprices every model's actual token usage at a reference model's
   sticker prices. The ratio own-$/success : repriced-$/success is the
   sticker premium over the reference market rate for identical work.
   Also clusters models on price-free per-task behavior profiles
   (log tokens / log steps, z-scored per task).

Token/cost convention follows docs/methodology.md:
  uncached_input = input_tokens - cache_read_tokens - cache_write_tokens
  reasoning_tokens are a subset of output_tokens (never added separately).

First documented use: docs/price-efficiency-clustering-2026-07-07.md

Usage:
  python scripts/analyze_price_efficiency_clusters.py \
    --results results/<run>/repair-loop-results.json \
    --prices prices/openrouter-2026-07-03.json \
    [--reference-model z-ai/glm-5.2] [--bootstrap 10000] [--seed 7]
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--results", required=True, help="repair-loop-results.json path")
    ap.add_argument("--prices", required=True, help="price sheet json path")
    ap.add_argument(
        "--reference-model",
        default="z-ai/glm-5.2",
        help="price-sheet model whose sticker prices anchor the repricing counterfactual "
        "(pick a competitively priced open-weight model)",
    )
    ap.add_argument("--bootstrap", type=int, default=10000, help="bootstrap resamples")
    ap.add_argument("--seed", type=int, default=7, help="bootstrap RNG seed")
    return ap.parse_args()


def config_label(row: dict) -> str:
    model = row["model"].split("/", 1)[-1]  # drop gateway prefix
    short = model.split("/", 1)[-1]  # drop org prefix
    effort = row.get("reasoning_effort")
    return f"{short}/{effort}" if effort else short


def price_entry(prices: dict, model: str) -> dict:
    key = model.split("/", 1)[-1]  # strip gateway prefix, keep org/model
    if key in prices:
        return prices[key]
    for name, entry in prices.items():
        if key in entry.get("aliases", []) or model in entry.get("aliases", []):
            return entry
    raise KeyError(f"no price-sheet entry for {model}")


def priced_cost(row: dict, entry: dict) -> float:
    cache_read = row["cache_read_tokens"] or 0
    cache_write = row["cache_write_tokens"] or 0
    uncached = max((row["input_tokens"] or 0) - cache_read - cache_write, 0)
    output = row["output_tokens"] or 0
    in_rate = entry["input_per_1m"] / 1e6
    read_rate = (entry.get("cached_input_per_1m") or entry["input_per_1m"]) / 1e6
    write_rate = (entry.get("cache_write_per_1m") or entry["input_per_1m"]) / 1e6
    out_rate = entry["output_per_1m"] / 1e6
    return uncached * in_rate + cache_read * read_rate + cache_write * write_rate + output * out_rate


def output_tokens(row: dict) -> int:
    return row["output_tokens"] or 0


def input_tokens(row: dict) -> int:
    return row["input_tokens"] or 0


def agglomerate(items: list[str], dist) -> None:
    """Print average-linkage merges in order."""
    clusters = [[c] for c in items]
    while len(clusters) > 1:
        best = None
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                d = sum(dist(a, b) for a in clusters[i] for b in clusters[j]) / (
                    len(clusters[i]) * len(clusters[j])
                )
                if best is None or d < best[0]:
                    best = (d, i, j)
        d, i, j = best
        print(f"  d={d:.3f}  {'+'.join(clusters[i])}  <->  {'+'.join(clusters[j])}")
        clusters[i] += clusters[j]
        del clusters[j]


def main() -> None:
    args = parse_args()
    rows = json.load(open(args.results))
    prices = json.load(open(args.prices))["models"]

    scored = [r for r in rows if r["status"] == "scored" and not r.get("exclusion_reason")]
    dropped = len(rows) - len(scored)
    if dropped:
        print(f"note: dropped {dropped} non-scored/excluded rows")

    by_cfg: dict[str, list[dict]] = defaultdict(list)
    for r in scored:
        by_cfg[config_label(r)].append(r)
    configs = sorted(by_cfg)
    tasks = sorted({r["task_id"] for r in scored})

    task_runs: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for c in configs:
        for r in by_cfg[c]:
            task_runs[(c, r["task_id"])].append(r)
    task_sr = {
        (c, t): sum(r["passed"] for r in rs) / len(rs) for (c, t), rs in task_runs.items()
    }

    # ---- headline stats ----
    print("=" * 110)
    print(
        f"{'config':<24}{'succ':>8}{'sr%':>7}{'$total':>9}{'$/succ':>9}"
        f"{'outTok/succ':>13}{'inTok/succ':>12}{'steps/run':>10}"
    )
    stats: dict[str, dict] = {}
    for c in configs:
        rs = by_cfg[c]
        n = len(rs)
        succ = sum(r["passed"] for r in rs)
        cost = sum(r["gateway_reported_cost_usd"] for r in rs)
        otok = sum(output_tokens(r) for r in rs)
        itok = sum(input_tokens(r) for r in rs)
        steps = sum(r["agent_steps"] or 0 for r in rs) / n
        cps = cost / succ if succ else float("nan")
        stats[c] = {"succ": succ, "cost": cost, "cps": cps}
        ot_ps = otok / succ if succ else float("nan")
        it_ps = itok / succ if succ else float("nan")
        print(
            f"{c:<24}{succ:>5}/{n:<3}{100 * succ / n:>5.1f}{cost:>9.3f}{cps:>9.4f}"
            f"{ot_ps:>13.0f}{it_ps:>12.0f}{steps:>10.1f}"
        )

    # ---- bootstrap CIs on $/success (resample tasks, seeds stay nested) ----
    print()
    print(f"Bootstrap 95% CI on $/success (resampling {len(tasks)} tasks, B={args.bootstrap}):")
    rng = random.Random(args.seed)
    for c in sorted(configs, key=lambda c: stats[c]["cps"]):
        per_task = {t: task_runs[(c, t)] for t in tasks}
        vals = []
        for _ in range(args.bootstrap):
            cost = succ = 0
            for t in (rng.choice(tasks) for _ in tasks):
                for r in per_task[t]:
                    cost += r["gateway_reported_cost_usd"]
                    succ += r["passed"]
            vals.append(cost / succ if succ else float("inf"))
        vals.sort()
        lo = vals[int(0.025 * args.bootstrap)]
        hi = vals[int(0.975 * args.bootstrap)]
        print(f"  {c:<24} {stats[c]['cps']:>8.4f}  [{lo:.4f}, {hi:.4f}]")

    # ---- task discrimination ----
    print()
    print("Task discrimination (success-rate mean/variance across configs; var>0.05 flagged *):")
    discriminating = 0
    for t in sorted(tasks, key=lambda t: sum(task_sr[(c, t)] for c in configs)):
        m = sum(task_sr[(c, t)] for c in configs) / len(configs)
        var = sum((task_sr[(c, t)] - m) ** 2 for c in configs) / len(configs)
        flag = " *" if var > 0.05 else ""
        discriminating += bool(flag)
        print(f"  {t:<44} mean={m:.2f} var={var:.3f}{flag}")
    if not discriminating:
        print(
        "  NOTE: no task discriminates between configs — the run is at ceiling and"
        " capability clustering below is degenerate."
        )

    # ---- capability clustering (per-task success vectors) ----
    cap_vec = {c: [task_sr[(c, t)] for t in tasks] for c in configs}

    def cap_dist(a: str, b: str) -> float:
        return math.sqrt(
            sum((x - y) ** 2 for x, y in zip(cap_vec[a], cap_vec[b])) / len(tasks)
        )

    print()
    print("Capability clustering (RMS distance between per-task success-rate vectors):")
    agglomerate(configs, cap_dist)

    # ---- behavioral clustering (price-free per-task profiles) ----
    features: dict[str, list[float]] = {c: [] for c in configs}
    for t in tasks:
        for fn in (
            lambda r: math.log1p(output_tokens(r)),
            lambda r: math.log1p(r["agent_steps"] or 0),
        ):
            for c in configs:
                vals = [fn(r) for r in by_cfg[c] if r["task_id"] == t]
                features[c].append(sum(vals) / len(vals))
    nfeat = len(features[configs[0]])
    mean = [sum(features[c][i] for c in configs) / len(configs) for i in range(nfeat)]
    sd = [
        math.sqrt(sum((features[c][i] - mean[i]) ** 2 for c in configs) / len(configs)) or 1.0
        for i in range(nfeat)
    ]
    zed = {c: [(features[c][i] - mean[i]) / sd[i] for i in range(nfeat)] for c in configs}

    def beh_dist(a: str, b: str) -> float:
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(zed[a], zed[b])) / nfeat)

    print()
    print("Behavioral clustering (z-scored per-task log output-tokens + log steps):")
    agglomerate(configs, beh_dist)

    # ---- sticker-price reconstruction sanity + repricing counterfactual ----
    ref = prices[args.reference_model]
    print()
    print(
        f"Repricing decomposition (counterfactual sticker prices: {args.reference_model})\n"
        f"{'config':<24}{'recon/reported':>15}{'$/succ own':>12}{'@ref px':>10}{'premium':>9}"
    )
    print(
        "  recon/reported far from 1.0 => price-sheet entry or provider routing needs review\n"
        "  premium = own $/succ vs same token usage at reference sticker prices"
    )
    repriced = {}
    for c in configs:
        rs = by_cfg[c]
        succ = stats[c]["succ"]
        recon = sum(priced_cost(r, price_entry(prices, r["model"])) for r in rs)
        at_ref = sum(priced_cost(r, ref) for r in rs) / succ if succ else float("nan")
        repriced[c] = at_ref
        own = stats[c]["cps"]
        print(
            f"{c:<24}{recon / stats[c]['cost']:>15.2f}{own:>12.4f}{at_ref:>10.4f}"
            f"{own / at_ref:>8.1f}x"
        )

    print()
    print("Token-efficiency ranking ($/success if every config paid reference prices):")
    for c in sorted(configs, key=lambda c: repriced[c]):
        print(f"  {c:<24} {repriced[c]:.4f}")


if __name__ == "__main__":
    main()
