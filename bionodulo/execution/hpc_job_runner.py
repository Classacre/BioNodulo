"""Execute one serialized BioNodulo workflow inside an HPC batch job."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.nodes.registry import NodeRegistry


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--run-id", required=True)
    return parser


async def _execute(args: argparse.Namespace) -> dict[str, Any]:
    workflow = json.loads(Path(args.workflow).read_text(encoding="utf-8"))
    if not isinstance(workflow, dict):
        raise ValueError("HPC workflow payload must be a JSON object")
    workspace = Path(args.workspace)
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    executor = WorkflowExecutor(
        workspace_dir=workspace,
        cache_dir=workspace / "cache",
        registry=registry,
    )
    return await executor.execute(run_id=str(args.run_id), workflow=workflow)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = asyncio.run(_execute(args))
    result_path = Path(args.result)
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return 0 if result.get("status") == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
