#!/usr/bin/env python
"""Run a workflow through the real WorkflowExecutor and retain a run receipt.

This is a receipt-capturing harness, not a second execution framework: it calls
the same ``bionodulo.execution.executor.WorkflowExecutor`` the cloud worker and
``scripts/smoke_harness.py`` use. It exists because ``smoke_harness`` runs inside
``tempfile.TemporaryDirectory`` and, on Windows, raises ``WinError 32`` while
deleting its own still-open ``cache/metadata/cache.db``. That cleanup defect
destroys the evidence for a run that actually succeeded.

This harness keeps its workspace on disk, so the receipt survives, and records:

* retrieval/execution start and end timestamps (UTC)
* per-node start/complete/error events
* exit status of the whole run
* every produced artifact with size and SHA-256
* whether environment provisioning was required and what happened

A receipt proves a command ran in this environment. It does not prove the
output is scientifically correct; that needs a separate independent oracle.

Usage:
    python scripts/run_local_queue_receipt.py <template.json> \
        --receipt-dir reports/run-receipts/<name>
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import traceback

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bionodulo.execution.executor import WorkflowExecutor  # noqa: E402
from bionodulo.manager.installer import DependencyInstaller  # noqa: E402
from bionodulo.nodes.registry import NodeRegistry  # noqa: E402
from bionodulo.environments.manifest import workflow_to_environment_plan  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def run(template: Path, receipt_dir: Path) -> dict:
    workflow = json.loads(template.read_text(encoding="utf-8"))
    registry = NodeRegistry()

    events: list[dict] = []
    node_status: dict[str, str] = {}
    node_errors: dict[str, str] = {}
    order: list[str] = []

    def emit(event: str, data: dict) -> None:
        record = {"at": now(), "event": event,
                  "node_id": data.get("node_id"), "data": _safe(data)}
        events.append(record)
        nid = data.get("node_id") or ""
        if event in ("node_start", "node_started"):
            if nid and nid not in order:
                order.append(nid)
            node_status[nid] = "running"
        elif event in ("node_complete", "node_completed"):
            node_status[nid] = "completed"
        elif event == "node_error":
            node_status[nid] = "failed"
            node_errors[nid] = str(data.get("error", ""))[:2000]

    workspace = receipt_dir / "workspace"
    cache_dir = receipt_dir / "cache"
    if workspace.exists():
        shutil.rmtree(workspace, ignore_errors=True)
    workspace.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    started = now()
    env_plan = workflow_to_environment_plan(workflow, registry)
    packages = list(env_plan.all_packages)
    env_result = {"required": bool(packages), "packages": packages, "status": "not_required"}

    result: dict
    if packages:
        # This host has no pixi/conda, so a workflow needing packages cannot be
        # provisioned. Record that precisely instead of failing obscurely.
        env_result["status"] = "unprovisionable_on_this_host"
        env_result["reason"] = (
            "Workflow requires environment packages but no pixi/conda/mamba exists on this "
            "host, and the project targets linux-64/linux-aarch64 only."
        )
        result = {"status": "env_blocked", "error": env_result["reason"]}
    else:
        try:
            result = await WorkflowExecutor(
                workspace_dir=workspace, cache_dir=cache_dir, registry=registry,
            ).execute(
                f"receipt-{template.stem}", workflow, force=True,
                options={"stop_on_error": True}, emit=emit,
            )
        except Exception as exc:  # noqa: BLE001
            result = {"status": "error", "error": f"{type(exc).__name__}: {exc}",
                      "traceback": traceback.format_exc()[-3000:]}
    completed = now()

    artifacts = []
    for path in sorted(workspace.rglob("*")):
        if path.is_file():
            artifacts.append({
                "path": str(path.relative_to(receipt_dir)).replace("\\", "/"),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            })

    nodes = workflow.get("nodes", [])
    node_types = {n["id"]: n.get("type", "?") for n in nodes if isinstance(n, dict)}

    receipt = {
        "schema_version": 1,
        "template": template.name,
        "template_sha256": sha256_file(template),
        "executor": "bionodulo.execution.executor.WorkflowExecutor",
        "started_at_utc": started,
        "completed_at_utc": completed,
        "status": result.get("status", "unknown"),
        "error": result.get("error", ""),
        "environment": env_result,
        "node_order": order,
        "node_status": node_status,
        "node_errors": node_errors,
        "node_types": node_types,
        "artifacts": artifacts,
        "artifact_count": len(artifacts),
        "scope": (
            "Real queued execution through the ordinary executor on this host. Proves the "
            "command ran and the planned outputs exist. Does not prove scientific correctness; "
            "that requires an independent oracle recorded separately."
        ),
        "host_platform": sys.platform,
    }
    (receipt_dir / "receipt.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with (receipt_dir / "events.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for record in events:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return receipt


def _safe(data: dict) -> dict:
    out = {}
    for key, value in data.items():
        try:
            json.dumps(value)
            out[key] = value
        except (TypeError, ValueError):
            out[key] = str(value)[:500]
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("template", type=Path)
    parser.add_argument("--receipt-dir", type=Path, required=True)
    args = parser.parse_args()
    args.receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt = asyncio.run(run(args.template, args.receipt_dir))
    print(json.dumps({k: receipt[k] for k in
                      ("template", "status", "artifact_count", "environment",
                       "node_status", "error")}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
