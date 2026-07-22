"""Node conformance smoke harness.

Runs a template's graph through the REAL WorkflowExecutor locally (tools install
via pixi, same as the cloud worker) and reports per-node conformance:

  G1 runnable      — the node's command exits 0
  G2 output-honest — every PLAN_OUTPUTS path exists after the run
  G3 dep-complete  — the env provided every executable/library the node used

The executor already enforces G1+G2 (a nonzero exit or a missing planned output
raises), so a node that reaches `completed` is G1+G2+G3 conformant on the given
fixture. We capture per-node status via the emit() event stream and print a
compact PASS/FAIL table plus the first failing node's error — exactly the signal
needed to drive a fix, without a 5-minute cloud round-trip.

Usage:
    python smoke_harness.py <template.json> [template2.json ...]
    python smoke_harness.py --all        # every template in templates/
"""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bionodulo.execution.executor import WorkflowExecutor  # noqa: E402
from bionodulo.manager.installer import DependencyInstaller  # noqa: E402
from bionodulo.nodes.registry import NodeRegistry  # noqa: E402
from bionodulo.environments.manifest import (  # noqa: E402
    workflow_to_environment_plan,
)

TEMPLATES = ROOT / "templates"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


async def run_template(path: Path) -> dict:
    workflow = _load(path)
    registry = NodeRegistry()

    node_events: dict[str, str] = {}
    node_errors: dict[str, str] = {}
    order: list[str] = []

    def emit(event: str, data: dict) -> None:
        nid = data.get("node_id") or ""
        if event in ("node_start", "node_started"):
            if nid and nid not in order:
                order.append(nid)
            node_events[nid] = "running"
        elif event in ("node_complete", "node_completed"):
            node_events[nid] = "PASS"
        elif event in ("node_error",):
            node_events[nid] = "FAIL"
            node_errors[nid] = str(data.get("error", ""))[:400]

    with tempfile.TemporaryDirectory(prefix="smoke_") as tmp:
        tmp_path = Path(tmp)
        executor = WorkflowExecutor(
            workspace_dir=tmp_path,
            cache_dir=tmp_path / "cache",
            registry=registry,
        )
        # Provision through the production local installer, which shares the
        # workflow environment plan and committed lock with the cloud worker.
        # The executor only USES an installed env; it does not create one.
        environment_plan = workflow_to_environment_plan(workflow, registry)
        if environment_plan.all_packages:
            installer = DependencyInstaller()
            job_id = await installer.install_workflow_env(workflow, registry, tmp_path)
            job = installer.get_job(job_id)
            if job is None or job._task is None:
                raise RuntimeError("workflow environment installer did not create a task")
            await job._task
            if job.progress.status != "completed":
                return {
                    "template": path.name,
                    "status": "env_failed",
                    "error": f"pixi env install failed: {job.progress.message[:300]}",
                    "order": [], "events": {}, "errors": {}, "node_types": {},
                }
        try:
            result = await executor.execute(
                f"smoke-{path.stem}",
                workflow,
                force=True,
                options={"stop_on_error": True},
                emit=emit,
            )
        except Exception as exc:  # noqa: BLE001
            result = {"status": "error", "error": str(exc)[:400]}

    # node types for reporting
    node_types = {}
    nodes = workflow.get("nodes", [])
    if isinstance(nodes, list):
        node_types = {n["id"]: n.get("type", "?") for n in nodes if isinstance(n, dict)}

    return {
        "template": path.name,
        "status": result.get("status", "?"),
        "error": result.get("error", ""),
        "order": order,
        "events": node_events,
        "errors": node_errors,
        "node_types": node_types,
    }


def _print_report(rep: dict) -> bool:
    ok = rep["status"] in ("completed", "success")
    mark = "OK " if ok else "FAIL"
    print(f"\n[{mark}] {rep['template']}  (status={rep['status']})")
    if not ok:
        # find first failing node
        for nid, st in rep["events"].items():
            if st == "FAIL":
                nt = rep["node_types"].get(nid, "?")
                print(f"     FAILED node: {nid} ({nt})")
                err = rep["errors"].get(nid, "")
                if err:
                    print(f"     error: {err}")
                break
        else:
            if rep.get("error"):
                print(f"     error: {rep['error']}")
    return ok


async def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    if args == ["--all"]:
        paths = sorted(TEMPLATES.glob("*.json"))
    else:
        paths = [Path(a) if Path(a).is_absolute() else (TEMPLATES / a) for a in args]

    passed = 0
    for p in paths:
        if not p.exists():
            print(f"[SKIP] {p} (not found)")
            continue
        rep = await run_template(p)
        if _print_report(rep):
            passed += 1
    print(f"\n{'='*50}\n{passed}/{len(paths)} templates conformant")
    return 0 if passed == len(paths) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
