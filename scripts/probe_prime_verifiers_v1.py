#!/usr/bin/env python3
"""Probe one local ShallowSWE Harbor task against Prime verifiers v1.

Run this from a verifiers v1 source checkout because the announced API is not yet
available in the published PyPI package.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import uuid4


async def score(task: Any, solution: bytes | None) -> dict[str, object]:
    from verifiers.v1.env import resolve_runtime_config
    from verifiers.v1.runtimes import DockerConfig, make_runtime
    from verifiers.v1.state import State
    from verifiers.v1.trace import Trace, TraceTask

    runtime = make_runtime(
        resolve_runtime_config(DockerConfig(), task),
        name=f"shallowswe-prime-v1-{uuid4().hex[:10]}",
    )
    trace = Trace(
        task=TraceTask(type=type(task).__name__, data=task.data),
        state=State(),
    )
    try:
        await runtime.start()
        if solution is not None:
            solution_path = "/tmp/shallowswe-solution.sh"
            await runtime.write(solution_path, solution)
            result = await runtime.run(["bash", solution_path], {})
            if result.exit_code != 0:
                raise RuntimeError(f"solution failed: {result.stderr.strip()}")
        await task.score(trace, runtime)
        return {
            "reward": trace.reward,
            "rewards": trace.rewards,
            "errors": [error.model_dump(mode="json") for error in trace.errors],
        }
    finally:
        await runtime.stop()


async def main_async(args: argparse.Namespace) -> int:
    try:
        from verifiers.v1.tasksets.harbor import HarborConfig, HarborTask
        from verifiers.v1.tasksets.harbor.taskset import parse_task
    except ModuleNotFoundError as exc:
        if exc.name == "verifiers":
            raise RuntimeError(
                "Prime verifiers v1 is required; run this script with the pinned upstream project"
            ) from exc
        raise

    task_dir = args.task_dir.resolve()
    config = HarborConfig(
        dataset="shallowswe/local",
        tasks=[task_dir.name],
        ignore_dockerfile=True,
    )
    data = parse_task(task_dir, 0, config).model_copy(
        update={"image": args.image, "workdir": "/app"}
    )
    task = HarborTask(data, config.task)
    baseline = await score(task, None)
    repaired = await score(task, (task_dir / "solution" / "solve.sh").read_bytes())
    report = {
        "task": {
            "name": data.name,
            "category": data.category,
            "prompt": data.prompt,
            "image": data.image,
            "timeouts": data.timeout.model_dump(mode="json"),
            "resources": data.resources.model_dump(mode="json"),
        },
        "baseline": baseline,
        "repaired": repaired,
        "compatible": baseline["reward"] == 0.0 and repaired["reward"] == 1.0,
    }
    print(json.dumps(report, indent=2))
    return 0 if report["compatible"] else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_dir", type=Path)
    parser.add_argument("--image", required=True)
    return asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
