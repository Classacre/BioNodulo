"""All REST API endpoints for BioNodulo v2.

References app.state for registry, settings, queue, and event_hub.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from bionodulo.api.app_state import app_state, setting_literal
from bionodulo.api.auth_dependencies import require_auth_payload as _require_auth_payload
from bionodulo.api.collab_dependencies import (
    ensure_open_room_access,
    require_workflow_role,
)
from bionodulo.api.collab_runtime_routes import workflow_payload_to_flat_snapshot
from bionodulo.api.system_stats import router as system_stats_router
from bionodulo.api.previews import router as previews_router
from bionodulo.api.rate_limits import limiter
from bionodulo.api.schemas import (
    DeleteFilesRequest,
    DependencyTreeRequest,
    ExampleDataDownloadRequest,
    FileOperationRequest,
    HPCConfigureRequest,
    HPCSubmitRequest,
    ImportWorkflowRequest,
    ManagerDiagnoseRequest,
    ManagerGitRequest,
    ManagerInstallDepsRequest,
    ManagerInstallPlanRequest,
    ManagerInstallRequest,
    ManagerPackageRequest,
    QueueReorderRequest,
    RunCreateRequest,
    ValidationRequest,
    WorkspaceRootRequest,
    WorkflowEnvironmentRequest,
    WorkflowExportRequest,
    WorkflowExtractRequest,
)
from bionodulo.core.config import Settings
from bionodulo.core.events import EventHub
from bionodulo.core.paths import ensure_within
from bionodulo.workflow.export import export_workflow
from bionodulo.environments.manifest import (
    delete_env_dir,
    duplicate_env_dir,
    get_env_dir,
    get_env_meta,
    get_env_packages,
    is_env_ready,
    list_all_envs,
    remove_package_from_env,
    set_env_meta,
)
from bionodulo.manager.diagnostics import host_diagnostics
from bionodulo.manager.example_data import download_example_data
from bionodulo.hpc.base import HPCBackend
from bionodulo.manager.resolver import _resolve_workflow_async
from bionodulo.workflow.graph import edge_source, edge_target
from bionodulo.workflow.validation import validate_workflow

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
logger = logging.getLogger(__name__)


def _derive_category(name: str, description: str, tools: list[str]) -> str:
    text = (name + " " + description).lower()
    tool_text = " ".join(tools).lower()
    combined = text + " " + tool_text
    if any(k in combined for k in ("single cell", "cell ranger", "cellranger", "10x")):
        return "Single Cell"
    if any(k in combined for k in ("rna-seq", "rnaseq", "expression", "deseq2", "salmon", "kallisto", "featurecounts", "stringtie")):
        return "RNA-Seq"
    if any(k in combined for k in ("variant", "vcf", "gatk", "freebayes", "bcftools", "haplotypecaller")):
        return "Variant"
    if any(k in combined for k in ("metagenom", "microbial", "kraken", "metaphlan", "bracken", "humann")):
        return "Metagenomics"
    if any(k in combined for k in ("assembly", "spades", "megahit", "quast")):
        return "Assembly"
    if any(k in combined for k in ("phylo", "tree", "iq-tree", "mafft")):
        return "Phylogenetics"
    if any(k in combined for k in ("chip", "atac", "macs2")):
        return "ChIP-Seq"
    if any(k in combined for k in ("fastq", "qc", "fastqc", "multiqc", "fastp", "trimmomatic")):
        return "QC"
    if any(k in combined for k in ("visualization", "ggplot", "plot", "heatmap", "image_preview", "r_plot", "r_pheatmap")):
        return "Visualization"
    if any(k in combined for k in ("biopython", "blast", "sequence", "seqio", "translate", "biostrings")):
        return "Sequence"
    if any(k in combined for k in ("wgs", "whole genome")):
        return "WGS"
    if any(k in combined for k in ("align", "bwa", "bowtie", "minimap", "star", "hisat")):
        return "Alignment"
    return "Other"


def _derive_tags(name: str, description: str, tools: list[str]) -> list[str]:
    text = (name + " " + description).lower()
    tags: set[str] = set()
    keywords = [
        (["qc", "fastq", "quality", "fastqc", "multiqc"], "qc"),
        (["rna", "expression", "deseq2", "salmon", "kallisto"], "rna"),
        (["variant", "vcf", "snp", "gatk", "freebayes"], "variant"),
        (["assembly", "genome", "spades", "megahit"], "assembly"),
        (["phylo", "tree", "alignment", "mafft", "iqtree"], "phylo"),
        (["chip", "epigenetics", "peak", "macs2"], "chip"),
        (["meta", "taxonomy", "microbiome", "kraken", "metaphlan"], "meta"),
        (["sc", "10x", "single cell", "cell ranger", "cellranger"], "sc"),
        (["visualization", "plot", "ggplot", "heatmap", "image"], "viz"),
        (["sequence", "blast", "biopython", "seqio", "translate"], "sequence"),
        (["r", "ggplot2", "pheatmap", "deseq2"], "r"),
        (["wgs", "whole genome"], "wgs"),
        (["align", "bwa", "bowtie", "minimap", "star"], "align"),
    ]
    for group, tag in keywords:
        for kw in group:
            if kw in text:
                tags.add(tag)
                break
    for tool in tools:
        tags.add(tool.lower())
    return sorted(tags)


router = APIRouter()
router.include_router(system_stats_router)
router.include_router(previews_router)


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Liveness probe for container orchestration."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_registry(request: Request) -> Any:
    return request.app.state.node_registry


def _get_settings(request: Request) -> Settings:
    return request.app.state.settings


def _get_queue(request: Request) -> Any:
    return request.app.state.run_queue


def _get_event_hub(request: Request) -> EventHub:
    return request.app.state.event_hub


def _setting_bool(request: Request, key: str, default: bool = False) -> bool:
    value = setting_literal(request, key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _ensure_open_room_access(request: Request, workflow_id: str, user_id: str, role: str = "editor") -> None:
    """Compatibility wrapper for tests and older route helpers."""
    ensure_open_room_access(request, workflow_id, user_id, role=role)


def _workflow_payload_to_flat_snapshot(workflow_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Compatibility wrapper for tests and older route helpers."""
    return workflow_payload_to_flat_snapshot(workflow_id, body)


def _require_execute_permission(request: Request, workflow_id: str | None) -> dict[str, Any] | None:
    """Require execute permission when collaborative permissions are enabled."""
    if not workflow_id:
        return None
    if not _setting_bool(request, "bionodulo.collab.enabled", False):
        return None
    payload = _require_auth_payload(request)
    user_id = payload.get("sub", "")
    require_workflow_role(request, workflow_id, user_id, "execute")
    return payload


def _safe_path(path_str: str, root: Path) -> Path:
    return ensure_within(Path(path_str), root)


def _workflow_node_id(node: Any, fallback: str | None = None) -> str:
    if isinstance(node, dict):
        node_id = node.get("id", fallback)
    else:
        node_id = getattr(node, "id", fallback)
    return str(node_id) if node_id is not None else ""


def _workflow_node_as_dict(node: Any, node_id: str) -> dict[str, Any]:
    if isinstance(node, dict):
        data = dict(node)
    elif hasattr(node, "model_dump"):
        data = node.model_dump()
    else:
        data = dict(getattr(node, "__dict__", {}))
    data.setdefault("id", node_id)
    return data


def _object_as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return dict(getattr(value, "__dict__", {}))


def _extract_workflow_subgraph(
    workflow: dict[str, Any],
    node_ids: list[str],
    name: str,
) -> dict[str, Any]:
    selected = {
        str(nid).strip()
        for nid in node_ids
        if nid is not None and str(nid).strip()
    }
    if not selected:
        raise ValueError("At least one node_id is required")

    raw_nodes = workflow.get("nodes", [])
    node_map: dict[str, dict[str, Any]] = {}
    if isinstance(raw_nodes, dict):
        for node_id, node in raw_nodes.items():
            nid = _workflow_node_id(node, str(node_id))
            if nid:
                node_map[nid] = _workflow_node_as_dict(node, nid)
    else:
        for node in raw_nodes or []:
            nid = _workflow_node_id(node)
            if nid:
                node_map[nid] = _workflow_node_as_dict(node, nid)

    missing = sorted(selected - set(node_map))
    if missing:
        raise KeyError(", ".join(missing))

    extracted_nodes = [node_map[nid] for nid in node_map if nid in selected]
    extracted_edges = [
        edge
        for edge in workflow.get("edges", [])
        if edge_source(edge) in selected and edge_target(edge) in selected
    ]
    extracted_groups: list[dict[str, Any]] = []
    for group in workflow.get("groups", []) or []:
        group_data = _object_as_dict(group)
        group_node_ids = [
            str(node_id)
            for node_id in group_data.get("node_ids", [])
            if str(node_id) in selected
        ]
        if group_node_ids:
            group_data["node_ids"] = group_node_ids
            extracted_groups.append(group_data)

    extracted_outputs: list[dict[str, Any]] = []
    for output in workflow.get("outputs", []) or []:
        output_data = _object_as_dict(output)
        if str(output_data.get("node_id", "")) in selected:
            extracted_outputs.append(output_data)

    extracted: dict[str, Any] = {
        key: value
        for key, value in workflow.items()
        if key not in {"id", "name", "nodes", "edges", "groups", "outputs"}
    }
    extracted.update(
        {
            "id": f"subgraph_{uuid.uuid4().hex[:12]}",
            "name": name,
            "nodes": extracted_nodes,
            "edges": extracted_edges,
            "groups": extracted_groups,
            "outputs": extracted_outputs,
        }
    )
    return extracted


# ---------------------------------------------------------------------------
# Registry / Object Info
# ---------------------------------------------------------------------------

@router.get("/object_info")
async def list_object_info(request: Request) -> dict[str, Any]:
    """List all registered node metadata."""
    registry = _get_registry(request)
    return registry.object_info()


@router.get("/object_info/{node_id}")
async def get_object_info(request: Request, node_id: str) -> dict[str, Any]:
    """Get metadata for a single registered node."""
    registry = _get_registry(request)
    meta = registry.object_info(node_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")
    return meta


# ---------------------------------------------------------------------------
# Workflow Validation
# ---------------------------------------------------------------------------

@router.post("/workflow/validate")
async def workflow_validate(request: Request, body: ValidationRequest) -> dict[str, Any]:
    """Validate a workflow for structural correctness."""
    registry = _get_registry(request)
    result = validate_workflow(body.workflow, registry)
    return {
        "valid": result.valid,
        "errors": result.errors,
        "warnings": result.warnings,
        "sorted_node_order": result.sorted_node_order,
    }


# ---------------------------------------------------------------------------
# Runs / Execution
# ---------------------------------------------------------------------------

def _generate_run_id(workflow_name: str) -> str:
    """Generate a human-readable run ID.

    Format: {sanitized_workflow_name}_{YYYYMMDD}_{HHMMSS}_{short_uuid}
    """
    safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in workflow_name)[:30]
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    short_uuid = uuid.uuid4().hex[:6]
    return f"{safe_name}_{ts}_{short_uuid}"


@router.post("/runs")
async def create_run(request: Request, body: RunCreateRequest) -> dict[str, Any]:
    """Submit a workflow for execution."""
    _require_execute_permission(request, body.workflow_id or body.workflow.get("id"))
    queue = _get_queue(request)
    event_hub = _get_event_hub(request)

    wf_name = body.workflow.get("name", body.name or "Untitled")
    run_id = _generate_run_id(str(wf_name))
    await event_hub.emit_typed(
        "execution.run_submitted",
        {"run_id": run_id, "name": body.name},
        source=run_id,
    )

    # Submit to queue if available
    if hasattr(queue, "submit"):
        await queue.submit(
            run_id=run_id,
            workflow=body.workflow,
            metadata={
                "name": body.name,
                "environment": body.environment,
                "target_nodes": body.target_nodes,
                "force_nodes": body.force_nodes,
            },
            options={"target_nodes": body.target_nodes} if body.target_nodes else {},
            force=body.no_cache,
            force_nodes=set(body.force_nodes),
        )
    else:
        # Fallback: store in app state
        runs: dict[str, Any] = getattr(request.app.state, "runs", {})
        runs[run_id] = {
            "run_id": run_id,
            "name": body.name,
            "status": "queued",
            "workflow": body.workflow,
            "target_nodes": body.target_nodes,
            "force_nodes": body.force_nodes,
        }
        request.app.state.runs = runs

    return {"run_id": run_id, "status": "queued", "name": body.name, "workflow_name": wf_name}


@router.post("/prompt")
async def comfyui_prompt(request: Request) -> dict[str, Any]:
    """ComfyUI-compatible prompt endpoint.

    Accepts a workflow in ComfyUI prompt format and submits it for execution.
    """
    body = await request.json()
    queue = _get_queue(request)
    event_hub = _get_event_hub(request)

    wf_name = body.get("name", "prompt-run")
    run_id = _generate_run_id(str(wf_name))
    await event_hub.emit_typed(
        "execution.prompt_submitted",
        {"run_id": run_id},
        source=run_id,
    )

    if hasattr(queue, "submit"):
        await queue.submit(
            run_id=run_id,
            workflow=body,
            metadata={"name": "prompt-run"},
        )

    return {"prompt_id": run_id, "number": 0, "node_errors": {}}


# ---------------------------------------------------------------------------
# Queue
# ---------------------------------------------------------------------------

@router.get("/queue")
async def get_queue_state(request: Request) -> dict[str, Any]:
    """Get the current queue state (pending and running jobs)."""
    queue = _get_queue(request)
    if hasattr(queue, "get_state"):
        return await queue.get_state()
    return {"pending": [], "running": []}


@router.post("/queue/clear")
async def clear_queue(request: Request) -> dict[str, Any]:
    """Clear all pending jobs from the queue."""
    queue = _get_queue(request)
    if hasattr(queue, "clear"):
        cleared = await queue.clear()
    elif hasattr(queue, "clear_pending"):
        cleared = await queue.clear_pending()
    else:
        cleared = 0
    return {"status": "cleared", "cleared": cleared}


@router.post("/queue/{run_id}/cancel")
async def cancel_queued_run(request: Request, run_id: str) -> dict[str, Any]:
    """Cancel a pending or running job."""
    queue = _get_queue(request)
    if not hasattr(queue, "cancel"):
        raise HTTPException(status_code=501, detail="Queue cancellation is not available")
    cancelled = await queue.cancel(run_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return {"run_id": run_id, "status": "cancelled"}


@router.post("/queue/reorder")
async def reorder_pending_run(request: Request, body: QueueReorderRequest) -> dict[str, Any]:
    """Move a pending job within the queue."""
    queue = _get_queue(request)
    if not hasattr(queue, "reorder_pending"):
        raise HTTPException(status_code=501, detail="Queue reordering is not available")
    try:
        pending = await queue.reorder_pending(
            run_id=body.run_id,
            index=body.index,
            before_run_id=body.before_run_id,
            after_run_id=body.after_run_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "reordered", "pending": pending}


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

@router.get("/history")
async def get_history(request: Request) -> dict[str, Any]:
    """Get execution history of completed runs."""
    queue = _get_queue(request)
    if hasattr(queue, "list_history"):
        history = queue.list_history()
        return {"history": history, "count": len(history)}
    return {"history": [], "count": 0}


@router.get("/runs/{run_id}")
async def get_run_details(request: Request, run_id: str) -> dict[str, Any]:
    """Get details for a specific run."""
    queue = _get_queue(request)
    if hasattr(queue, "get_run"):
        run = queue.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"Run \\\'{run_id}\\\' not found")
        return run

    runs: dict[str, Any] = getattr(request.app.state, "runs", {})
    if run_id in runs:
        return runs[run_id]
    raise HTTPException(status_code=404, detail=f"Run \\\'{run_id}\\\' not found")


@router.post("/runs/{run_id}/retry")
async def retry_run(request: Request, run_id: str) -> dict[str, Any]:
    """Retry a stored pending, running, or historic run."""
    queue = _get_queue(request)
    if not hasattr(queue, "retry"):
        raise HTTPException(status_code=501, detail="Run retry is not available")
    try:
        new_run_id = await queue.retry(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
    return {"run_id": new_run_id, "retry_of": run_id, "status": "queued"}


@router.get("/runs/{run_id}/logs")
async def get_run_logs(request: Request, run_id: str) -> dict[str, Any]:
    """Retrieve logs for a specific run from on-disk log files.

    Reads stdout.log and stderr.log from each node's execution directory
    under workspace/runs/{run_id}/.
    """
    settings = _get_settings(request)
    run_dir = settings.project_root / "runs" / run_id
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run directory not found: '{run_id}'")

    logs: list[dict[str, Any]] = []
    meta_path = run_dir / "run_metadata.json"
    nodes_meta: dict[str, Any] = {}
    run_started_at = datetime.now(timezone.utc).isoformat()

    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            nodes_meta = meta.get("nodes", {})
            run_started_at = meta.get("started_at") or run_started_at
        except (json.JSONDecodeError, OSError):
            pass

    # Synthetic start event
    exec_node_count = sum(1 for n in nodes_meta.values() if n.get("type") != "note")
    logs.append({
        "node_id": "engine",
        "level": "info",
        "message": f"Workflow started ({exec_node_count} nodes)",
        "timestamp": run_started_at,
        "stream": "event",
    })

    for node_id, node_info in nodes_meta.items():
        node_dir = run_dir / node_id
        if not node_dir.is_dir():
            continue

        node_status = node_info.get("status", "unknown")
        logs.append({
            "node_id": node_id,
            "level": "info",
            "message": f"Node {node_status}",
            "timestamp": run_started_at,
            "stream": "event",
        })

        for stream_name, level in (("stdout", "stdout"), ("stderr", "stderr")):
            log_path = node_dir / f"{stream_name}.log"
            if not log_path.exists():
                continue
            try:
                content = log_path.read_text(encoding="utf-8", errors="replace")
                mtime = datetime.fromtimestamp(log_path.stat().st_mtime, tz=timezone.utc).isoformat()
                for line in content.splitlines():
                    if not line.strip():
                        continue
                    logs.append({
                        "node_id": node_id,
                        "level": level,
                        "message": line,
                        "timestamp": mtime,
                        "stream": stream_name,
                    })
            except OSError:
                continue

    # Synthetic complete event
    final_status = "unknown"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            final_status = meta.get("status", final_status)
        except (json.JSONDecodeError, OSError):
            pass

    logs.append({
        "node_id": "engine",
        "level": "success" if final_status == "completed" else "error" if final_status == "failed" else "info",
        "message": f"Workflow {final_status}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stream": "event",
    })

    return {"run_id": run_id, "logs": logs}


@router.get("/runs/{run_id}/report", response_class=PlainTextResponse)
async def get_run_report(request: Request, run_id: str) -> PlainTextResponse:
    """Render the provenance HTML execution report for a finished run."""
    from bionodulo.provenance import generate_execution_report

    settings = _get_settings(request)
    run_dir = settings.project_root / "runs" / run_id
    meta_path = run_dir / "run_metadata.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail=f"Run metadata not found: '{run_id}'")
    try:
        run_metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Could not read run metadata: {exc}") from exc

    html_text = generate_execution_report(run_metadata, include_artifacts=True)
    return PlainTextResponse(html_text, media_type="text/html; charset=utf-8")


@router.get("/runs/{run_id}/manifest")
async def get_run_manifest(request: Request, run_id: str) -> JSONResponse:
    """Return the JSON provenance manifest for a finished run."""
    from bionodulo.provenance import generate_provenance_report

    settings = _get_settings(request)
    run_dir = settings.project_root / "runs" / run_id
    meta_path = run_dir / "run_metadata.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail=f"Run metadata not found: '{run_id}'")
    try:
        run_metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Could not read run metadata: {exc}") from exc

    workflow: dict[str, Any] = {}
    node_results: dict[str, dict[str, Any]] = {}
    artifacts: list[dict[str, Any]] = []

    queue = _get_queue(request)
    if hasattr(queue, "get_run"):
        try:
            queue_record = queue.get_run(run_id)
            if isinstance(queue_record, dict):
                workflow = queue_record.get("workflow") or workflow
                result = queue_record.get("result") or {}
                if isinstance(result, dict):
                    artifacts = result.get("artifacts") or artifacts
                    node_results = result.get("nodes") or node_results
        except Exception:  # noqa: BLE001 - missing queue data must not break manifest export
            pass

    manifest_json = generate_provenance_report(
        workflow=workflow,
        run_metadata=run_metadata,
        node_results=node_results,
        artifacts=artifacts,
    )
    return JSONResponse(
        content=json.loads(manifest_json),
        headers={
            "Content-Disposition": f'attachment; filename="bionodulo-manifest-{run_id}.json"',
        },
    )


@router.post("/cache/clear")
async def clear_cache(request: Request) -> dict[str, Any]:
    """Clear all cached workflow node execution results."""
    executor = getattr(request.app.state.run_queue, "executor", None)
    if executor is None or not hasattr(executor, "cache"):
        raise HTTPException(status_code=500, detail="Executor or cache not available")
    count = executor.cache.clear()
    return {"status": "cleared", "entries_deleted": count}


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@router.get("/config/effective")
async def get_effective_config(request: Request) -> dict[str, Any]:
    """Get the effective configuration (settings merged with defaults)."""
    settings = _get_settings(request)
    return settings.as_effective_config()


# ---------------------------------------------------------------------------
# Workspace
# ---------------------------------------------------------------------------

@router.get("/workspace/files")
async def list_workspace_files(request: Request, path: str = "") -> dict[str, Any]:
    """List files and directories in the workspace."""
    settings = _get_settings(request)
    try:
        target = _safe_path(path, settings.project_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: \\\'{path}\\\'")

    entries: list[dict[str, Any]] = []
    try:
        for entry in sorted(target.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            stat = entry.stat()
            entries.append({
                "name": entry.name,
                "path": str(entry.relative_to(settings.project_root)),
                "type": "directory" if entry.is_dir() else "file",
                "size": stat.st_size if entry.is_file() else None,
            })
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=f"Permission denied: \\\'{path}\\\'") from exc

    return {
        "path": str(target.relative_to(settings.project_root)),
        "absolute": str(target),
        "entries": entries,
    }


@router.get("/workspace/root")
async def get_workspace_root(request: Request) -> dict[str, str]:
    """Get the current workspace root directory."""
    settings = _get_settings(request)
    return {
        "root": str(settings.project_root),
        "runs_dir": str(settings.runs_dir),
        "cache_dir": str(settings.cache_dir),
    }


@router.post("/workspace/root")
async def set_workspace_root(
    request: Request, body: WorkspaceRootRequest
) -> dict[str, str]:
    """Set a new workspace root directory."""
    new_root = Path(body.path).resolve()
    if not new_root.exists():
        raise HTTPException(
            status_code=400, detail=f"Directory does not exist: \\\'{body.path}\\\'"
        )
    if not new_root.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: \\\'{body.path}\\\'")

    settings = _get_settings(request)
    settings.project_root = new_root
    settings.ensure_directories()
    return {"root": str(new_root), "status": "changed"}


@router.get("/workspace/directories")
async def browse_directories(request: Request, path: str = "") -> dict[str, Any]:
    """Browse directories only (for directory picker UI)."""
    settings = _get_settings(request)
    try:
        target = _safe_path(path, settings.project_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=404, detail=f"Directory not found: \\\'{path}\\\'")

    directories: list[dict[str, str]] = []
    try:
        for entry in sorted(target.iterdir()):
            if entry.is_dir():
                directories.append({
                    "name": entry.name,
                    "path": str(entry.relative_to(settings.project_root)),
                })
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=f"Permission denied: \\\'{path}\\\'") from exc

    return {
        "path": str(target.relative_to(settings.project_root)),
        "absolute": str(target),
        "directories": directories,
    }


@router.get("/workspace/file")
async def read_file(request: Request, path: str) -> Any:
    """Read a file from the workspace.

    Returns JSON content for .json files, plain text for others.
    """
    settings = _get_settings(request)
    try:
        target = _safe_path(path, settings.project_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not target.exists():
        raise HTTPException(status_code=404, detail=f"File not found: \\\'{path}\\\'")
    if not target.is_file():
        raise HTTPException(status_code=400, detail=f"Not a file: \\\'{path}\\\'")

    # Size limit: 10MB
    if target.stat().st_size > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (>10MB)")

    suffix = target.suffix.lower()
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return PlainTextResponse("Binary file - cannot display as text.", status_code=415)

    if suffix == ".json":
        try:
            return JSONResponse(json.loads(content))
        except json.JSONDecodeError:
            return PlainTextResponse(content)
    return PlainTextResponse(content)


@router.post("/workspace/upload")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    subdir: str = Form("uploads"),
) -> dict[str, Any]:
    """Accept a multipart file upload and store it under workspace/{subdir}/.

    Used by features like media paste on the canvas: the browser hands over a
    pasted image / audio blob and we drop it inside the user's workspace so
    a workflow node can reference it by path.
    """
    settings = _get_settings(request)
    safe_subdir = subdir.strip().strip('/').replace('..', '_') or 'uploads'
    target_dir = settings.project_root / safe_subdir
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not create upload dir: {exc}") from exc

    raw_name = file.filename or 'pasted'
    # Strip any directory components and reserve a stable, unique filename.
    base = Path(raw_name).name or 'pasted'
    stem = Path(base).stem or 'pasted'
    suffix = Path(base).suffix
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    short = uuid.uuid4().hex[:6]
    safe_name = ''.join(c if c.isalnum() or c in '._-' else '_' for c in stem)[:60]
    final_name = f"{stamp}_{short}_{safe_name}{suffix}"
    out_path = target_dir / final_name

    try:
        with open(out_path, 'wb') as fh:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                fh.write(chunk)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not write upload: {exc}") from exc

    rel = out_path.relative_to(settings.project_root)
    return {
        'status': 'ok',
        'path': str(rel).replace('\\', '/'),
        'absolute_path': str(out_path),
        'size': out_path.stat().st_size,
        'content_type': file.content_type or 'application/octet-stream',
        'original_name': raw_name,
    }


@router.post("/workspace/file-operation")
async def file_operation(
    request: Request, body: FileOperationRequest
) -> dict[str, str]:
    """Copy or move files within the workspace."""
    settings = _get_settings(request)
    try:
        source = _safe_path(body.source, settings.project_root)
        target = _safe_path(body.target, settings.project_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not source.exists():
        raise HTTPException(status_code=404, detail=f"Source not found: \\\'{body.source}\\\'")

    if body.operation == "copy":
        if source.is_file():
            shutil.copy2(source, target)
        else:
            shutil.copytree(source, target, dirs_exist_ok=True)
    elif body.operation == "move":
        shutil.move(str(source), str(target))
    else:
        raise HTTPException(status_code=400, detail=f"Unknown operation: \\\'{body.operation}\\\'")

    return {"status": "ok", "operation": body.operation}


@router.post("/workspace/delete")
async def delete_files(request: Request, body: DeleteFilesRequest) -> dict[str, Any]:
    """Delete files or directories from the workspace."""
    settings = _get_settings(request)
    deleted: list[str] = []
    failed: list[dict[str, str]] = []

    for path_str in body.paths:
        try:
            target = _safe_path(path_str, settings.project_root)
            if not target.exists():
                failed.append({"path": path_str, "reason": "not found"})
                continue
            if target.is_file():
                target.unlink()
            else:
                shutil.rmtree(target)
            deleted.append(path_str)
        except (ValueError, PermissionError, OSError) as exc:
            failed.append({"path": path_str, "reason": str(exc)})

    return {"deleted": deleted, "failed": failed}


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

@router.get("/manager/status")
async def manager_status(request: Request) -> dict[str, Any]:
    """Get manager status (installed nodes, available updates)."""
    registry = _get_registry(request)
    installed: list[dict[str, Any]] = []
    for node_id, meta in registry.object_info().items():
        installed.append({
            "name": node_id,
            "version": meta.get("version", "unknown"),
            "category": meta.get("category", "unknown"),
            "builtin": meta.get("builtin", False),
        })
    return {
        "installed_nodes": installed,
        "custom_nodes_dir": str(_get_settings(request).custom_nodes_dir),
        "total": len(installed),
    }


@router.get("/manager/registry")
async def manager_registry(request: Request) -> dict[str, Any]:
    """Get known registry entries for node discovery."""
    settings = _get_settings(request)
    return {
        "registries": settings.registries,
        "tool_paths": settings.tool_paths,
    }


@router.post("/manager/install-git")
async def manager_install_git(
    request: Request, body: ManagerGitRequest
) -> dict[str, str]:
    """Install a custom node from a Git repository."""
    settings = _get_settings(request)
    target_dir = settings.custom_nodes_dir
    if body.directory:
        target_dir = target_dir / body.directory
    else:
        # Derive directory name from URL
        from urllib.parse import urlparse
        repo_name = Path(urlparse(body.url).path).stem
        target_dir = target_dir / repo_name

    import subprocess

    if target_dir.exists():
        raise HTTPException(
            status_code=409,
            detail=f"Directory already exists: \\\'{target_dir.name}\\\'",
        )

    try:
        cmd = ["git", "clone", "--depth", "1", "--branch", body.branch, body.url, str(target_dir)]
        if body.commit:
            # Full clone for specific commit
            cmd = ["git", "clone", body.url, str(target_dir)]
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
        if body.commit:
            subprocess.run(
                ["git", "-C", str(target_dir), "checkout", body.commit],
                check=True,
                capture_output=True,
                text=True,
            )
    except subprocess.CalledProcessError as exc:
        raise HTTPException(status_code=500, detail=f"Git clone failed: {exc.stderr}") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail="Git not found on system") from exc

    # Reload custom nodes
    registry = _get_registry(request)
    if hasattr(registry, "load_custom_nodes"):
        registry.load_custom_nodes(settings.custom_nodes_dir)

    return {"status": "installed", "directory": str(target_dir.name)}


@router.post("/manager/update")
async def manager_update(
    request: Request, body: ManagerPackageRequest
) -> dict[str, str]:
    """Update an installed package."""
    settings = _get_settings(request)
    node_dir = settings.custom_nodes_dir / body.name
    if not node_dir.exists():
        raise HTTPException(
            status_code=404, detail=f"Package \\\'{body.name}\\\' not found"
        )

    import subprocess

    try:
        result = subprocess.run(
            ["git", "-C", str(node_dir), "pull"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise HTTPException(
                status_code=500, detail=f"Git pull failed: {result.stderr}"
            )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail="Git not found") from exc

    # Reload
    registry = _get_registry(request)
    if hasattr(registry, "load_custom_nodes"):
        registry.load_custom_nodes(settings.custom_nodes_dir)

    return {"status": "updated", "package": body.name}


@router.post("/manager/remove")
async def manager_remove(
    request: Request, body: ManagerPackageRequest
) -> dict[str, str]:
    """Remove an installed package."""
    settings = _get_settings(request)
    node_dir = settings.custom_nodes_dir / body.name
    if not node_dir.exists():
        raise HTTPException(
            status_code=404, detail=f"Package \\\'{body.name}\\\' not found"
        )

    shutil.rmtree(node_dir)

    # Reload
    registry = _get_registry(request)
    if hasattr(registry, "load_custom_nodes"):
        registry.load_custom_nodes(settings.custom_nodes_dir)

    return {"status": "removed", "package": body.name}


@router.post("/manager/reload")
async def manager_reload(request: Request) -> dict[str, str]:
    """Reload all custom nodes."""
    settings = _get_settings(request)
    registry = _get_registry(request)
    if hasattr(registry, "load_builtin_nodes"):
        registry.load_builtin_nodes()
    if hasattr(registry, "load_custom_nodes"):
        registry.load_custom_nodes(settings.custom_nodes_dir)
    return {"status": "reloaded"}


@router.get("/host_status")
async def api_host_status() -> dict[str, Any]:
    """Return host-level prerequisite diagnostics.

    Checks for python3, pixi, node/npm, and Rscript.
    Pixi can be auto-installed; everything else must be
    present on the host PATH.
    """
    return await asyncio.to_thread(host_diagnostics)


@router.post("/host_status/install-pixi")
async def api_install_pixi(request: Request) -> dict[str, Any]:
    """Trigger automatic installation of pixi.

    Downloads and installs pixi to the managed location
    (~/.pixi by default).
    Emits progress events via the WebSocket event hub so the
    frontend can stream logs in real-time.
    """
    from bionodulo.manager.runtime_installer import (
        install_managed_pixi,
        is_pixi_installed,
    )

    if is_pixi_installed():
        return {"success": True, "message": "pixi is already installed", "already_installed": True}

    event_hub = request.app.state.event_hub

    loop = asyncio.get_running_loop()

    def emit(level: str, data: dict[str, Any]) -> None:
        payload = {**data, "level": level, "timestamp": datetime.now().isoformat()}
        loop.call_soon_threadsafe(
            lambda: asyncio.create_task(
                event_hub.emit_typed("install.log", payload, source="pixi-installer")
            )
        )

    success = await asyncio.to_thread(install_managed_pixi, emit=emit)
    if success:
        return {"success": True, "message": "pixi installed successfully", "already_installed": False}
    return {"success": False, "message": "pixi installation failed. Check server logs for details.", "already_installed": False}


@router.post("/manager/diagnose")
async def manager_diagnose(
    request: Request, body: ManagerDiagnoseRequest
) -> dict[str, Any]:
    """Diagnose a workflow (find missing tools, type mismatches)."""
    registry = _get_registry(request)
    settings = _get_settings(request)
    result = validate_workflow(body.workflow, registry)
    report = await _resolve_workflow_async(body.workflow, registry, settings.project_root)

    return {
        "valid": result.valid,
        "errors": result.errors,
        "warnings": result.warnings,
        "missing_nodes": [n.node_type for n in report.missing_nodes],
        "missing_tools": [e.name for e in report.missing_executables],
        "missing_packages": [p.name for p in report.missing_packages],
        "compatibility_issues": [],
        "resolution": report.to_dict(),
    }


@router.post("/manager/install-deps")
async def manager_install_deps(
    request: Request, body: ManagerInstallDepsRequest
) -> dict[str, Any]:
    """Legacy endpoint — redirects to ensure-workflow-env.

    Use POST /manager/ensure-workflow-env instead.
    """
    return {"message": "Use /manager/ensure-workflow-env instead", "status": "deprecated"}


@router.get("/manager/status/{job_id}")
async def manager_job_status(request: Request, job_id: str) -> dict[str, Any]:
    """Get the status of an async install job."""
    installer = app_state(request).dependency_installer
    job = installer.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return job.progress.to_dict()


@router.post("/manager/install-plan")
async def manager_install_plan(
    request: Request, body: ManagerInstallPlanRequest
) -> dict[str, Any]:
    """Get an install plan for requested nodes (legacy endpoint)."""
    registry = _get_registry(request)
    plan: list[dict[str, Any]] = []
    for node_name in body.nodes:
        meta = registry.object_info(node_name)
        if not meta:
            plan.append({
                "node": node_name,
                "action": "install",
                "source": "git",
                "estimated_size": "unknown",
            })
        else:
            plan.append({
                "node": node_name,
                "action": "already_installed",
                "version": meta.get("version", "unknown"),
            })
    return {"plan": plan, "total_to_install": sum(1 for p in plan if p["action"] == "install")}


@router.post("/manager/install")
async def manager_install(
    request: Request, body: ManagerInstallRequest
) -> dict[str, Any]:
    """Execute an install plan (legacy endpoint)."""
    if not body.confirm:
        return {"status": "pending", "message": "Set confirm=true to execute"}

    results: list[dict[str, str]] = []
    plan_items = body.plan.get("plan", [])
    for item in plan_items:
        if item.get("action") == "install":
            results.append({
                "node": item["node"],
                "status": "installed",
                "method": item.get("source", "unknown"),
            })
        else:
            results.append({
                "node": item["node"],
                "status": "skipped",
                "reason": item.get("action", "unknown"),
            })

    # Reload nodes after install
    settings = _get_settings(request)
    registry = _get_registry(request)
    if hasattr(registry, "load_custom_nodes"):
        registry.load_custom_nodes(settings.custom_nodes_dir)

    return {"status": "completed", "results": results}


# ---------------------------------------------------------------------------
# Environment Manager (manifest-based per-workflow environments)
# ---------------------------------------------------------------------------

@router.post("/manager/resolve")
@limiter.limit("120/minute")
async def manager_resolve(
    request: Request, body: DependencyTreeRequest
) -> dict[str, Any]:
    """Resolve dependencies for a workflow.

    Returns required packages, environment status, and any missing nodes.
    """
    from bionodulo.manager.resolver import _resolve_workflow_async

    registry = _get_registry(request)
    settings = _get_settings(request)
    report = await _resolve_workflow_async(body.workflow, registry, settings.project_root)
    return report.to_dict()


@router.post("/manager/ensure-workflow-env")
async def manager_ensure_workflow_env(
    request: Request, body: DependencyTreeRequest
) -> dict[str, Any]:
    """Generate manifest, lock, and install a workflow's environment.

    Starts a background job and returns immediately with a job_id.
    Poll GET /manager/status/{job_id} for progress.
    """
    registry = _get_registry(request)
    settings = _get_settings(request)
    event_hub = request.app.state.event_hub

    def emit(level: str, data: dict[str, Any]) -> None:
        asyncio.create_task(
            event_hub.emit_typed(
                "install.progress",
                {**data, "level": level, "timestamp": datetime.now().isoformat()},
                source="dependency-installer",
            )
        )

    installer = app_state(request).dependency_installer
    job_id = await installer.install_workflow_env(
        body.workflow,
        registry,
        settings.project_root,
        emit=emit,
    )
    return {"job_id": job_id, "status": "started"}


@router.post("/manager/create-workflow-env")
async def manager_create_workflow_env(
    request: Request, body: WorkflowEnvironmentRequest
) -> dict[str, Any]:
    """Legacy alias for /manager/ensure-workflow-env."""
    return await manager_ensure_workflow_env(request, DependencyTreeRequest(workflow=body.workflow))


@router.get("/manager/environments")
async def list_environments(request: Request) -> dict[str, Any]:
    """List all workflow environments."""
    settings = _get_settings(request)
    envs = list_all_envs(settings.project_root)
    return {"environments": envs, "count": len(envs)}


@router.get("/manager/environments/{env_id}")
async def get_environment(env_id: str, request: Request) -> dict[str, Any]:
    """Get details for a specific environment including installed packages."""
    settings = _get_settings(request)
    env_dir = get_env_dir(env_id, settings.project_root)
    if not env_dir.exists():
        raise HTTPException(status_code=404, detail=f"Environment '{env_id}' not found")
    meta = get_env_meta(env_dir)
    packages = get_env_packages(env_dir)
    return {
        "id": env_id,
        "name": meta.get("name") or f"Env {env_id[:8]}",
        "path": str(env_dir),
        "packages": packages,
        "package_count": len(packages),
        "ready": is_env_ready(env_dir),
    }


@router.post("/manager/environments/{env_id}/rename")
async def rename_environment(env_id: str, request: Request, body: dict[str, Any]) -> dict[str, Any]:
    """Rename an environment (display name only — ID cannot change)."""
    settings = _get_settings(request)
    env_dir = get_env_dir(env_id, settings.project_root)
    if not env_dir.exists():
        raise HTTPException(status_code=404, detail=f"Environment '{env_id}' not found")
    new_name = body.get("name", "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="Name is required")
    set_env_meta(env_dir, name=new_name)
    return {"success": True, "id": env_id, "name": new_name}


@router.post("/manager/environments/{env_id}/duplicate")
async def duplicate_environment(env_id: str, request: Request) -> dict[str, Any]:
    """Duplicate an environment."""
    settings = _get_settings(request)
    env_dir = get_env_dir(env_id, settings.project_root)
    if not env_dir.exists():
        raise HTTPException(status_code=404, detail=f"Environment '{env_id}' not found")
    success, message, new_id = duplicate_env_dir(env_dir, settings.project_root)
    if not success:
        raise HTTPException(status_code=500, detail=message)
    return {"success": True, "message": message, "new_id": new_id}


@router.post("/manager/environments/{env_id}/packages/{pkg_name}/remove")
async def remove_environment_package(env_id: str, pkg_name: str, request: Request) -> dict[str, Any]:
    """Remove a single package from an environment's manifest."""
    settings = _get_settings(request)
    env_dir = get_env_dir(env_id, settings.project_root)
    if not env_dir.exists():
        raise HTTPException(status_code=404, detail=f"Environment '{env_id}' not found")
    success, message = remove_package_from_env(env_dir, pkg_name)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message}


@router.delete("/manager/environments/{env_id}")
async def delete_environment(env_id: str, request: Request) -> dict[str, Any]:
    """Remove an environment directory."""
    settings = _get_settings(request)
    env_dir = get_env_dir(env_id, settings.project_root)
    success, message = delete_env_dir(env_dir)
    if not success:
        raise HTTPException(status_code=500, detail=message)
    return {"success": True, "message": message}


# ---------------------------------------------------------------------------
# Workflow Templates
# ---------------------------------------------------------------------------

@router.get("/workflow_templates")
async def list_workflow_templates(request: Request) -> dict[str, Any]:
    """List available workflow templates."""
    templates_dir = REPO_ROOT / "templates"
    templates: list[dict[str, Any]] = []

    if templates_dir.exists():
        for entry in sorted(templates_dir.iterdir()):
            if entry.suffix.lower() == ".json":
                try:
                    data = json.loads(entry.read_text(encoding="utf-8"))
                    nodes = data.get("nodes", []) or []
                    if isinstance(nodes, dict):
                        nodes = list(nodes.values())

                    name = data.get("name", entry.stem.replace("_", " ").title())
                    description = data.get("description", "")

                    # Use explicit metadata if provided, otherwise auto-derive
                    tools = data.get("tools")
                    if tools is None:
                        tools = sorted({n.get("type", "") for n in nodes if n.get("type") and n.get("type") != "note"})

                    category = data.get("category")
                    if category is None:
                        category = _derive_category(name, description, tools)

                    tags = data.get("tags")
                    if tags is None:
                        tags = _derive_tags(name, description, tools)

                    preview_steps = [
                        (node.get("ui") or {}).get("title") or str(node.get("type", "")).replace("_", " ")
                        for node in nodes
                        if node.get("type") and node.get("type") != "note"
                    ][:5]

                    thumbnail_path = entry.with_suffix(".png")
                    thumbnail_url = f"/api/workflow_templates/{entry.name}/thumbnail.png" if thumbnail_path.exists() else None

                    templates.append({
                        "id": entry.stem,
                        "name": name,
                        "filename": entry.name,
                        "description": description,
                        "node_count": sum(1 for n in nodes if n.get("type") != "note"),
                        "tools": tools,
                        "category": category,
                        "tags": tags,
                        "preview_steps": preview_steps,
                        "thumbnail_url": thumbnail_url,
                    })
                except (json.JSONDecodeError, OSError):
                    templates.append({
                        "id": entry.stem,
                        "name": entry.stem.replace("_", " ").title(),
                        "filename": entry.name,
                        "description": "",
                        "node_count": 0,
                        "tools": [],
                        "category": "Other",
                        "tags": [],
                    })

    return {"templates": templates, "count": len(templates)}


@router.get("/workflow_templates/{filename}")
async def get_workflow_template(request: Request, filename: str) -> dict[str, Any]:
    """Return a specific workflow template JSON."""
    templates_dir = REPO_ROOT / "templates"
    target = templates_dir / filename

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Template not found")

    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Invalid template JSON: {exc}")

    return data


@router.get("/workflow_templates/{filename}/thumbnail.png")
async def get_workflow_template_thumbnail(request: Request, filename: str) -> FileResponse:
    """Return the PNG thumbnail for a template (workflow JSON is embedded in tEXt)."""
    templates_dir = REPO_ROOT / "templates"
    json_path = templates_dir / filename
    if not json_path.exists() or not json_path.is_file():
        raise HTTPException(status_code=404, detail="Template not found")
    thumbnail = json_path.with_suffix(".png")
    if not thumbnail.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not generated; run scripts/relayout_templates.py")
    return FileResponse(
        path=thumbnail,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=300"},
    )


# ---------------------------------------------------------------------------
# i18n / Translations
# ---------------------------------------------------------------------------

@router.get("/i18n")
async def get_translations(locale: str = "en") -> dict[str, Any]:
    """Get translation strings for the given locale."""
    # Fallback: return English defaults
    translations: dict[str, str] = {
        "app.title": "BioNodulo",
        "app.subtitle": "Visual Bioinformatics Workbench",
        "menu.file": "File",
        "menu.edit": "Edit",
        "menu.view": "View",
        "menu.run": "Run",
        "menu.help": "Help",
        "node.search": "Search nodes...",
        "run.start": "Start",
        "run.queue": "Queue",
        "run.clear": "Clear Queue",
        "settings.title": "Settings",
        "workspace.title": "Workspace",
        "panel.nodes": "Node Library",
        "panel.queue": "Queue",
        "panel.console": "Console",
        "panel.properties": "Properties",
        "dialog.confirm": "Confirm",
        "dialog.cancel": "Cancel",
        "dialog.delete": "Delete",
        "status.ready": "Ready",
        "status.running": "Running...",
        "status.completed": "Completed",
        "status.error": "Error",
    }
    return {"locale": locale, "strings": translations}


# ---------------------------------------------------------------------------
# Workflow Export
# ---------------------------------------------------------------------------

@router.post("/workflow/extract")
async def workflow_extract(request: Request, body: WorkflowExtractRequest) -> dict[str, Any]:
    """Extract a workflow containing selected nodes and internal edges."""
    del request
    try:
        workflow = _extract_workflow_subgraph(body.workflow, body.node_ids, body.name)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Unknown node_id(s): {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"workflow": workflow, "node_ids": body.node_ids, "extracted": True}


@router.post("/workflow/export")
async def workflow_export(request: Request, body: WorkflowExportRequest) -> Any:
    """Export a workflow to various formats (snakemake, nextflow, cwl, galaxy)."""
    try:
        content = export_workflow(
            workflow=body.workflow,
            fmt=body.format,
            name=body.name,
        )
        return {"format": body.format, "content": content, "filename": f"{body.name}.{body.format}"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Export failed")
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Workflow Import
# ---------------------------------------------------------------------------

@router.post("/workflow/import")
async def workflow_import(request: Request, body: ImportWorkflowRequest) -> dict[str, Any]:
    """Import a workflow from external formats (snakemake, nextflow, cwl, galaxy)."""
    source = body.source.lower()
    content = body.content

    file_path_obj = None
    if not content and body.file_path:
        settings = _get_settings(request)
        try:
            file_path_obj = _safe_path(body.file_path, settings.project_root)
            if source == "cwl":
                content = None
            else:
                content = file_path_obj.read_text(encoding="utf-8")
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not content and not file_path_obj:
        raise HTTPException(status_code=400, detail="No content or file_path provided")

    # Try to delegate to converter module
    try:
        if source == "snakemake":
            from bionodulo.converter.snakemake_converter import import_from_snakemake as snakemake_import
            workflow = snakemake_import(content)
        elif source == "nextflow":
            from bionodulo.converter.nextflow_converter import import_from_nextflow as nextflow_import
            workflow = nextflow_import(content)
        elif source == "cwl":
            from bionodulo.converter.cwl_converter import import_from_cwl as cwl_import
            if file_path_obj:
                workflow = cwl_import(file_path_obj)
            else:
                with tempfile.NamedTemporaryFile(mode="w", suffix=".cwl", delete=False) as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name
                try:
                    workflow = cwl_import(tmp_path)
                finally:
                    os.unlink(tmp_path)
        elif source == "galaxy":
            from bionodulo.converter.galaxy_converter import import_from_galaxy as galaxy_import
            workflow = galaxy_import(content)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported import format: \\'{source}\\'")

        return {"workflow": workflow, "source": source, "imported": True}
    except ImportError as exc:
        logger.warning("Converter module not available: %s", exc)
        return {
            "workflow": {"version": "1.0", "app": "bionodulo", "nodes": {}, "edges": [], "groups": []},
            "source": source,
            "imported": False,
            "note": f"Converter for {source} not available. Install converter dependencies.",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Import failed: {exc}") from exc


# ---------------------------------------------------------------------------
# HPC
# ---------------------------------------------------------------------------

@router.get("/hpc/status")
async def hpc_status(request: Request) -> dict[str, Any]:
    """Get HPC connection and job status.

    Returns a 'status' field for frontend badge: 'off', 'error', or 'on'.
    """
    hpc = getattr(request.app.state, "hpc_backend", None)
    config = getattr(request.app.state, "hpc_config", None)

    if hpc is not None and hasattr(hpc, "status"):
        try:
            result = await hpc.status()
            # Normalize status badge
            if result.get("connected"):
                result["status"] = "on"
            else:
                result["status"] = "error"
            return result
        except Exception as exc:
            return {
                "status": "error",
                "connected": False,
                "backend": config.get("backend") if config else None,
                "pending_jobs": 0,
                "running_jobs": 0,
                "message": f"HPC status check failed: {exc}",
            }

    return {
        "status": "off",
        "connected": False,
        "backend": config.get("backend") if config else None,
        "pending_jobs": 0,
        "running_jobs": 0,
        "message": "HPC backend not configured",
    }


@router.post("/hpc/configure")
async def hpc_configure(
    request: Request, body: HPCConfigureRequest
) -> dict[str, Any]:
    """Configure the HPC backend connection."""
    config_data = {
        "backend": body.backend,
        "host": body.host,
        "user": body.user,
        "key_path": body.key_path,
        "partition": body.partition,
        "account": body.account,
        "default_cpus": body.default_cpus,
        "default_memory": body.default_memory,
        "default_walltime": body.default_walltime,
    }

    # Store on app state
    request.app.state.hpc_config = config_data

    # Try to initialize backend
    try:
        backend_class: type[HPCBackend] | None = None
        if body.backend == "slurm":
            from bionodulo.hpc.slurm import SLURMBackend
            backend_class = SLURMBackend
        elif body.backend == "pbs":
            from bionodulo.hpc.pbs import PBSBackend
            backend_class = PBSBackend
        elif body.backend == "sge":
            from bionodulo.hpc.sge import SGEBackend
            backend_class = SGEBackend
        elif body.backend == "local":
            from bionodulo.hpc.local import LocalBackend
            backend_class = LocalBackend

        if backend_class:
            backend = backend_class(**{k: v for k, v in config_data.items() if v is not None})
            if hasattr(backend, "connect"):
                await backend.connect()
            request.app.state.hpc_backend = backend
            return {"configured": True, "backend": body.backend, "connected": True}

    except ImportError as exc:
        logger.warning("HPC backend module not available: %s", exc)
    except Exception as exc:
        logger.warning("HPC backend initialization failed: %s", exc)

    return {
        "configured": True,
        "backend": body.backend,
        "connected": False,
        "message": "Configuration saved but backend not connected",
    }


@router.post("/hpc/submit")
async def hpc_submit(request: Request, body: HPCSubmitRequest) -> dict[str, Any]:
    """Submit a workflow as an HPC job."""
    _require_execute_permission(request, body.workflow_id or body.workflow.get("id"))
    hpc = getattr(request.app.state, "hpc_backend", None)
    if hpc is None:
        raise HTTPException(status_code=503, detail="HPC backend not configured")

    job_id = str(uuid.uuid4())
    try:
        if hasattr(hpc, "submit_workflow"):
            remote_job_id = await hpc.submit_workflow(
                workflow=body.workflow,
                name=body.name,
                cpus=body.cpus,
                memory=body.memory,
                walltime=body.walltime,
                dependency_jobs=body.dependency_jobs,
            )
            return {"job_id": job_id, "remote_job_id": remote_job_id, "status": "submitted"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"HPC submit failed: {exc}") from exc

    return {
        "job_id": job_id,
        "status": "submitted",
        "note": "HPC backend submit_workflow not implemented",
    }


@router.get("/hpc/jobs/{job_id}")
async def hpc_job_status(request: Request, job_id: str) -> dict[str, Any]:
    """Check the status of an HPC job."""
    hpc = getattr(request.app.state, "hpc_backend", None)
    if hpc is not None and hasattr(hpc, "job_status"):
        try:
            return await hpc.job_status(job_id)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to get job status: {exc}") from exc

    return {
        "job_id": job_id,
        "status": "unknown",
        "connected": hpc is not None,
    }


# ---------------------------------------------------------------------------
# Documentation
# ---------------------------------------------------------------------------

@router.get("/docs/{page}")
async def get_docs(request: Request, page: str) -> Any:
    """Serve help documentation pages."""
    # Security: only allow alphanumeric page names with hyphens
    import re
    if not re.match(r"^[a-zA-Z0-9\\-]+$", page):
        raise HTTPException(status_code=400, detail="Invalid page name")

    settings = _get_settings(request)
    docs_dir = settings.project_root / "docs" / "help"
    html_file = docs_dir / f"{page}.html"
    md_file = docs_dir / f"{page}.md"

    if html_file.exists():
        return FileResponse(html_file)
    if md_file.exists():
        content = md_file.read_text(encoding="utf-8")
        return PlainTextResponse(content)

    raise HTTPException(status_code=404, detail=f"Documentation page \\\'{page}\\\' not found")


@router.get("/examples/workflows/{filename}")
async def get_example_workflow(request: Request, filename: str) -> Any:
    """Serve example workflow files."""
    import re
    if not re.match(r"^[a-zA-Z0-9_\\-\\.]+$", filename):
        raise HTTPException(status_code=400, detail="Invalid filename")

    settings = _get_settings(request)
    examples_dir = settings.project_root / "examples" / "workflows"
    file_path = examples_dir / filename

    try:
        safe_path = ensure_within(file_path, settings.project_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not safe_path.exists():
        raise HTTPException(status_code=404, detail=f"Example \\\'{filename}\\\' not found")

    return FileResponse(safe_path)


# ---------------------------------------------------------------------------
# Getting Started
# ---------------------------------------------------------------------------

@router.get("/getting-started/status")
async def getting_started_status(request: Request) -> dict[str, Any]:
    """Check whether example data is present locally."""
    settings = _get_settings(request)
    data_dir = settings.project_root / "examples" / "data"

    has_data = False
    total_size = 0
    categories: list[str] = []
    files_per_category: dict[str, int] = {}

    if data_dir.exists() and data_dir.is_dir():
        for subdir in data_dir.iterdir():
            if subdir.is_dir():
                categories.append(subdir.name)
                file_count = 0
                for f in subdir.rglob("*"):
                    if f.is_file():
                        total_size += f.stat().st_size
                        file_count += 1
                files_per_category[subdir.name] = file_count
        has_data = len(categories) > 0 and total_size > 0

    return {
        "has_example_data": has_data,
        "categories": sorted(categories),
        "files_per_category": files_per_category,
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 1),
    }


@router.post("/getting-started/download")
async def getting_started_download(
    request: Request, body: ExampleDataDownloadRequest
) -> dict[str, Any]:
    """Download example data files individually from public sources.

    Streams per-file progress via WebSocket (install.progress events) so the
    frontend console can show what is happening.  Files that already exist are
    skipped.  Synthetic / generated files are created on-the-fly.
    """
    settings = _get_settings(request)
    event_hub = _get_event_hub(request)

    # Worker-thread download progress must return to the request loop before
    # emitting into the async EventHub.
    loop = asyncio.get_running_loop()

    def emit_progress(message: str, level: str = "info") -> None:
        payload = {
            "job_id": "example-data-download",
            "message": message,
            "level": level,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        loop.call_soon_threadsafe(
            lambda: asyncio.create_task(
                event_hub.emit_typed(
                    "install.progress",
                    payload,
                    source="example-data",
                )
            )
        )

    emit_progress("Starting example data download from public sources ...", "info")

    # Run download in a thread pool so the event loop stays responsive
    result = await loop.run_in_executor(
        None,
        lambda: download_example_data(
            project_root=settings.project_root,
            emit=emit_progress,
        ),
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=500,
            detail=f"Example data download incomplete: {len(result.get('failed', []))} file(s) failed",
        )

    # Return refreshed status
    status = await getting_started_status(request)
    status["download_result"] = result
    return status
