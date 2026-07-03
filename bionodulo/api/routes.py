"""All REST API endpoints for BioNodulo v2.

References app.state for registry, settings, queue, and event_hub.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import re
import shutil
import subprocess
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
    ManagerPackageRequest,
    PauseRequestResolveRequest,
    QueueReorderRequest,
    RunCreateRequest,
    ValidationRequest,
    WorkspaceRootRequest,
    WorkflowEnvironmentRequest,
    WorkflowExportRequest,
    WorkflowExtractRequest,
    WorkflowTriggerEvaluateRequest,
)
from bionodulo.core.config import Settings
from bionodulo.core.credentials import redact_tree
from bionodulo.core.events import EventHub
from bionodulo.core.paths import ensure_within
from bionodulo.workflow.export import export_workflow
from bionodulo.workflow.trigger_runner import WorkflowTriggerRunner
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
from bionodulo.nodes.builtin.workflow_enhancement import CheckpointNode, PauseResumeNode
from bionodulo.manager.resolver import _resolve_workflow_async
from bionodulo.manager.custom_nodes import list_installed_packages, registry_entries
from bionodulo.workflow.graph import edge_source, edge_target
from bionodulo.workflow.validation import validate_workflow

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
logger = logging.getLogger(__name__)


def _track_background_task(task: asyncio.Task[Any], label: str) -> None:
    """Log unhandled exceptions from fire-and-forget asyncio tasks."""

    def _on_done(done: asyncio.Task[Any]) -> None:
        try:
            done.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("%s failed", label)

    task.add_done_callback(_on_done)


def _schedule_event_emit(
    event_hub: EventHub,
    event_type: str,
    payload: dict[str, Any],
    *,
    source: str,
) -> None:
    task = asyncio.create_task(event_hub.emit_typed(event_type, payload, source=source))
    _track_background_task(task, f"Event emit {event_type}")


def _schedule_event_emit_threadsafe(
    loop: asyncio.AbstractEventLoop,
    event_hub: EventHub,
    event_type: str,
    payload: dict[str, Any],
    *,
    source: str,
) -> None:
    def _schedule() -> None:
        _schedule_event_emit(event_hub, event_type, payload, source=source)

    loop.call_soon_threadsafe(_schedule)


def _callable_accepts_keyword(callable_obj: Any, keyword: str) -> bool:
    """Return whether a callable can receive the named keyword argument."""

    try:
        signature = inspect.signature(callable_obj)
    except (TypeError, ValueError):
        return False

    return any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD or name == keyword
        for name, parameter in signature.parameters.items()
    )


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
    queue = request.app.state.run_queue
    if queue is None:
        # Shared-editor mode: this backend does not execute workflows. Runs are
        # submitted to the cloud Batch runner from the client instead.
        raise HTTPException(
            status_code=503,
            detail="This editor does not run workflows; runs execute in the cloud.",
        )
    return queue


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
    """Gate run/queue mutations when collaborative permissions are enabled.

    In local (single-user) mode collaboration is off and the whole app is
    unauthenticated by design, so this is a no-op. When collaboration is on,
    a valid token is *always* required — a missing ``workflow_id`` no longer
    silently bypasses the check — and an execute role is additionally required
    on the specific workflow when one is identified.
    """
    if not _setting_bool(request, "bionodulo.collab.enabled", False):
        return None
    payload = _require_auth_payload(request)
    if workflow_id:
        user_id = payload.get("sub", "")
        require_workflow_role(request, workflow_id, user_id, "execute")
    return payload


def _safe_path(path_str: str, root: Path) -> Path:
    return ensure_within(Path(path_str), root)


# Run identifiers are server- or client-supplied but must always be a single
# safe path segment — never a traversal sequence used to walk outside runs/.
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")

# Upper bounds for the (polling) log endpoint so a chatty tool can't OOM the
# server or return an unbounded JSON array.
LOG_MAX_BYTES_PER_FILE = 2 * 1024 * 1024
LOG_DEFAULT_LIMIT = 5000
LOG_MAX_LIMIT = 50000


def _safe_run_dir(settings: Settings, run_id: str) -> Path:
    """Resolve ``runs/{run_id}`` and guarantee it stays inside the runs root.

    Raises ``HTTPException(400)`` for malformed or traversal-style run ids.
    """
    if not _RUN_ID_RE.match(run_id or ""):
        raise HTTPException(status_code=400, detail="Invalid run id")
    runs_root = settings.project_root / "runs"
    try:
        return ensure_within(Path(run_id), runs_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid run id") from exc


def _checkpoint_manifest_path(settings: Settings) -> Path:
    return settings.project_root / "checkpoints" / "checkpoint_manifest.json"


def _pause_requests_dir(settings: Settings) -> Path:
    return settings.project_root / "pause_requests"


def _workflow_triggers_dir(settings: Settings) -> Path:
    return settings.project_root / "workflow_triggers"


def _read_checkpoint_manifest_for_api(manifest_path: Path) -> dict[str, Any]:
    try:
        return CheckpointNode._read_checkpoint_manifest(manifest_path)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _checkpoint_resume_contract() -> dict[str, Any]:
    return {
        "resume_manifest_supported": True,
        "resume_supported": True,
        "resume_note": "Checkpoint artifact resolution and downstream executor resume are supported for checkpoint nodes.",
    }


def _checkpoint_artifact_path(settings: Settings, checkpoint_path: Any) -> Path:
    if checkpoint_path is None or str(checkpoint_path).strip() == "":
        raise HTTPException(status_code=400, detail="resume checkpoint descriptor requires checkpoint_path")

    raw_path = Path(str(checkpoint_path)).expanduser()
    resolved = raw_path.resolve() if raw_path.is_absolute() else (settings.project_root / raw_path).resolve()
    try:
        resolved.relative_to(settings.project_root.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="resume checkpoint path must be within the workspace") from exc
    return resolved


def _resolve_resume_checkpoint(settings: Settings, descriptor: dict[str, Any] | None) -> dict[str, Any] | None:
    if descriptor is None:
        return None
    if not isinstance(descriptor, dict):
        raise HTTPException(status_code=400, detail="resume_checkpoint must be an object")

    if descriptor.get("checkpoint_path"):
        checkpoint = dict(descriptor)
    else:
        try:
            checkpoint = CheckpointNode.resolve_checkpoint(
                manifest_path=_checkpoint_manifest_path(settings),
                run_id=str(descriptor.get("run_id", "") or ""),
                node_id=str(descriptor.get("node_id", "") or ""),
                checkpoint_name=str(descriptor.get("checkpoint_name", "") or ""),
            )
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        if not checkpoint:
            raise HTTPException(status_code=404, detail="resume checkpoint was not found")

    if not str(checkpoint.get("node_id", "") or "").strip():
        raise HTTPException(status_code=400, detail="resume checkpoint descriptor requires node_id")

    checkpoint_path = _checkpoint_artifact_path(settings, checkpoint.get("checkpoint_path"))
    if not checkpoint_path.is_file():
        raise HTTPException(status_code=404, detail="resume checkpoint artifact was not found")

    checkpoint["checkpoint_path"] = str(checkpoint_path)
    return checkpoint


def _pause_runtime_contract() -> dict[str, Any]:
    return {
        "review_decision_supported": True,
        "engine_pause_supported": True,
        "pause_note": "Review request decisions and executor-level blocking pause/resume are supported.",
    }


def _workflow_trigger_runtime_contract() -> dict[str, Any]:
    return {
        "scheduler_runner_contract_supported": True,
        "durable_scheduler_supported": True,
        "file_watch_runner_contract_supported": True,
        "polling_file_watcher_supported": True,
        "durable_trigger_runner_supported": True,
        "run_submission_supported": False,
        "workflow_trigger_note": (
            "Workflow trigger registrations are pollable metadata; the durable polling runner can evaluate "
            "schedule and file-watch triggers and submit embedded workflows."
        ),
    }


def _normalize_pause_contract(pause_request: dict[str, Any]) -> dict[str, Any]:
    pause_request.setdefault("review_decision_supported", True)
    pause_request.setdefault("engine_pause_supported", True)
    pause_request.setdefault(
        "note",
        "Review request recorded with persistent approval metadata; executor-level blocking pause/resume is supported.",
    )
    return pause_request


def _read_pause_request_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"pause request file is not valid JSON: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"pause request file must contain a JSON object: {path}")
    data.setdefault("pause_file", str(path))
    return _normalize_pause_contract(data)


def _read_workflow_trigger_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"workflow trigger file is not valid JSON: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"workflow trigger file must contain a JSON object: {path}")
    data.setdefault("trigger_file", str(path))
    return data


def _resolve_pause_request_path(settings: Settings, body: PauseRequestResolveRequest) -> Path:
    pause_dir = _pause_requests_dir(settings).resolve()
    if body.pause_file:
        candidate = (settings.project_root / body.pause_file).resolve()
    elif body.run_id and body.node_id:
        candidate = (pause_dir / f"{body.run_id}__{body.node_id}.json").resolve()
    elif body.node_id:
        candidate = (pause_dir / f"{body.node_id}.json").resolve()
    else:
        raise HTTPException(status_code=400, detail="run_id and node_id, node_id, or pause_file is required")

    try:
        candidate.relative_to(pause_dir)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="pause request must be inside the workspace pause_requests directory") from exc
    if not candidate.exists() and body.run_id and body.node_id and not body.pause_file:
        legacy_candidate = (pause_dir / f"{body.node_id}.json").resolve()
        try:
            legacy_candidate.relative_to(pause_dir)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="pause request must be inside the workspace pause_requests directory") from exc
        if legacy_candidate.exists():
            candidate = legacy_candidate
    if not candidate.exists():
        raise HTTPException(status_code=404, detail=f"Pause request not found: {candidate.name}")
    return candidate


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
    """Submit a workflow for execution, or preview it when dry_run is true."""
    _require_execute_permission(request, body.workflow_id or body.workflow.get("id"))
    queue = _get_queue(request)
    settings = _get_settings(request)

    wf_name = body.workflow.get("name", body.name or "Untitled")
    run_id = _generate_run_id(str(wf_name))
    execution_options = {
        **({"target_nodes": body.target_nodes} if body.target_nodes else {}),
        **({"parameters": body.parameters} if body.parameters else {}),
    }
    resume_checkpoint = _resolve_resume_checkpoint(settings, body.resume_checkpoint)
    if resume_checkpoint:
        execution_options["resume_checkpoint"] = resume_checkpoint
    if body.dry_run:
        executor = getattr(queue, "executor", None)
        if executor is None or not hasattr(executor, "dry_run"):
            raise HTTPException(status_code=500, detail="Executor dry-run preview is unavailable")
        preview = await executor.dry_run(
            run_id=run_id,
            workflow=body.workflow,
            options=execution_options,
            force=body.no_cache,
            force_nodes=set(body.force_nodes),
        )
        preview.setdefault("workflow_name", wf_name)
        preview.setdefault("name", body.name)
        return preview

    event_hub = _get_event_hub(request)
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
                "parameters": body.parameters,
                "resume_checkpoint": resume_checkpoint,
            },
            options=execution_options,
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
            "parameters": body.parameters,
            "resume_checkpoint": resume_checkpoint,
        }
        request.app.state.runs = runs

    return {"run_id": run_id, "status": "queued", "name": body.name, "workflow_name": wf_name}


# ---------------------------------------------------------------------------
# Workflow runtime artifacts
# ---------------------------------------------------------------------------

@router.get("/checkpoints/manifest")
async def get_checkpoint_manifest(request: Request) -> dict[str, Any]:
    """Return the persisted checkpoint manifest for the current workspace."""
    settings = _get_settings(request)
    manifest_path = _checkpoint_manifest_path(settings)
    manifest = _read_checkpoint_manifest_for_api(manifest_path)
    return {
        "exists": manifest_path.exists(),
        "manifest_path": str(manifest_path),
        "manifest": manifest,
        **_checkpoint_resume_contract(),
    }


@router.get("/checkpoints/resolve")
async def resolve_checkpoint(
    request: Request,
    run_id: str = "",
    node_id: str = "",
    checkpoint_name: str = "",
) -> dict[str, Any]:
    """Resolve a checkpoint by run/node pair or checkpoint name."""
    settings = _get_settings(request)
    manifest_path = _checkpoint_manifest_path(settings)
    try:
        checkpoint = CheckpointNode.resolve_checkpoint(
            manifest_path=manifest_path,
            run_id=run_id,
            node_id=node_id,
            checkpoint_name=checkpoint_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "found": bool(checkpoint),
        "manifest_path": str(manifest_path),
        "checkpoint": checkpoint,
        **_checkpoint_resume_contract(),
    }


@router.get("/pause_requests")
async def list_pause_requests(request: Request) -> dict[str, Any]:
    """List persisted pause/resume review requests for the current workspace."""
    settings = _get_settings(request)
    pause_dir = _pause_requests_dir(settings)
    pause_requests: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    if pause_dir.exists():
        for path in sorted(pause_dir.glob("*.json")):
            try:
                pause_requests.append(_read_pause_request_file(path))
            except ValueError as exc:
                errors.append({"pause_file": str(path), "error": str(exc)})
    return {
        "pause_requests_dir": str(pause_dir),
        "pause_requests": pause_requests,
        "count": len(pause_requests),
        "errors": errors,
        **_pause_runtime_contract(),
    }


@router.post("/pause_requests/resolve")
async def resolve_pause_request(request: Request, body: PauseRequestResolveRequest) -> dict[str, Any]:
    """Persist an approve/reject decision for a workspace pause request."""
    settings = _get_settings(request)
    pause_file = _resolve_pause_request_path(settings, body)
    try:
        pause_request = PauseResumeNode.resolve_pause_request(
            pause_file,
            action=body.action,
            reviewer=body.reviewer,
            comment=body.comment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    pause_request["pause_file"] = str(pause_file)
    _normalize_pause_contract(pause_request)
    return {"pause_request": pause_request}


@router.get("/workflow_triggers")
async def list_workflow_triggers(request: Request) -> dict[str, Any]:
    """List persisted workflow trigger registrations for the current workspace."""
    settings = _get_settings(request)
    trigger_dir = _workflow_triggers_dir(settings)
    triggers: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    if trigger_dir.exists():
        for path in sorted(trigger_dir.glob("*.json")):
            try:
                triggers.append(redact_tree(_read_workflow_trigger_file(path)))
            except ValueError as exc:
                errors.append({"trigger_file": str(path), "error": str(exc)})
    return {
        "trigger_dir": str(trigger_dir),
        "triggers": triggers,
        "count": len(triggers),
        "errors": errors,
        **_workflow_trigger_runtime_contract(),
    }


@router.post("/workflow_triggers/evaluate")
async def evaluate_workflow_triggers(request: Request, body: WorkflowTriggerEvaluateRequest) -> dict[str, Any]:
    """Evaluate schedule and file-watch trigger registrations."""
    # Evaluating with submit_runs=True enqueues real executions, so gate it the
    # same way as POST /runs when collaboration is enabled.
    if body.submit_runs:
        _require_execute_permission(request, None)
    settings = _get_settings(request)
    trigger_dir = _workflow_triggers_dir(settings)
    errors: list[dict[str, str]] = []
    try:
        runner = WorkflowTriggerRunner(
            trigger_dir=trigger_dir,
            queue=_get_queue(request),
            run_id_factory=lambda workflow, trigger: _generate_run_id(
                str(workflow.get("name") or trigger.get("target_workflow") or "triggered_workflow")
            ),
        )
        evaluation = await runner.evaluate(now=body.now, submit_runs=body.submit_runs)
    except ValueError as exc:
        evaluation = {
            "trigger_dir": str(trigger_dir),
            "due_schedule_triggers": [],
            "due_schedule_count": 0,
            "due_file_watch_triggers": [],
            "due_file_watch_count": 0,
            "submitted_runs": [],
            "submitted_run_count": 0,
            "errors": [],
        }
        errors.append({"kind": "evaluation", "error": str(exc)})
    errors.extend(evaluation.get("errors", []))
    return {
        "trigger_dir": evaluation["trigger_dir"],
        "due_schedule_triggers": redact_tree(evaluation["due_schedule_triggers"]),
        "due_schedule_count": evaluation["due_schedule_count"],
        "due_file_watch_triggers": redact_tree(evaluation["due_file_watch_triggers"]),
        "due_file_watch_count": evaluation["due_file_watch_count"],
        "submitted_runs": redact_tree(evaluation["submitted_runs"]),
        "submitted_run_count": evaluation["submitted_run_count"],
        "errors": errors,
        **{
            **_workflow_trigger_runtime_contract(),
            "run_submission_supported": bool(body.submit_runs),
            "workflow_trigger_note": (
                "Workflow trigger evaluation submitted embedded workflows for due triggers."
                if body.submit_runs
                else _workflow_trigger_runtime_contract()["workflow_trigger_note"]
            ),
        },
    }


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
    _require_execute_permission(request, None)
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
    """Cancel a pending or running job.

    Returns 200 with ``status: "cancelled"`` for active cancels, and 200
    with ``status: "already_finished"`` when the run has already moved into
    history (so a slightly-late click from the UI is a no-op instead of an
    error toast). Only an unknown ``run_id`` is treated as 404.
    """
    _require_execute_permission(request, None)
    queue = _get_queue(request)
    if not hasattr(queue, "cancel"):
        raise HTTPException(status_code=501, detail="Queue cancellation is not available")
    cancelled = await queue.cancel(run_id)
    if cancelled:
        return {"run_id": run_id, "status": "cancelled"}

    # Fall back: was the run already in history (completed / failed / cancelled)?
    history = getattr(queue, "_history", None)
    if history is not None:
        for entry in history:
            if getattr(entry, "run_id", None) == run_id:
                return {"run_id": run_id, "status": "already_finished"}

    raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")


@router.post("/queue/reorder")
async def reorder_pending_run(request: Request, body: QueueReorderRequest) -> dict[str, Any]:
    """Move a pending job within the queue."""
    _require_execute_permission(request, None)
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


@router.post("/history/clear")
async def clear_history(request: Request) -> dict[str, Any]:
    """Remove all completed runs from history."""
    _require_execute_permission(request, None)
    queue = _get_queue(request)
    if hasattr(queue, "clear_history"):
        cleared = queue.clear_history()
    else:
        cleared = 0
    return {"status": "cleared", "cleared": cleared}


@router.delete("/history/{run_id}")
async def delete_history_entry(request: Request, run_id: str) -> dict[str, Any]:
    """Remove a single completed run from history."""
    _require_execute_permission(request, None)
    queue = _get_queue(request)
    if not hasattr(queue, "delete_history_entry"):
        raise HTTPException(status_code=501, detail="History deletion is not available")
    removed = queue.delete_history_entry(run_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not in history")
    return {"run_id": run_id, "status": "deleted"}


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
    _require_execute_permission(request, None)
    queue = _get_queue(request)
    if not hasattr(queue, "retry"):
        raise HTTPException(status_code=501, detail="Run retry is not available")
    try:
        new_run_id = await queue.retry(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
    return {"run_id": new_run_id, "retry_of": run_id, "status": "queued"}


def _read_log_tail(log_path: Path, max_bytes: int) -> tuple[str, bool]:
    """Read at most *max_bytes* from the end of a log file.

    Returns ``(text, truncated)``. Reading only the tail bounds memory for a
    multi-gigabyte log and keeps the most recent (most useful) output.
    """
    try:
        size = log_path.stat().st_size
        with log_path.open("rb") as handle:
            if size > max_bytes:
                handle.seek(size - max_bytes)
                raw = handle.read()
                # Drop a partial first line after seeking into the middle.
                nl = raw.find(b"\n")
                if nl != -1:
                    raw = raw[nl + 1 :]
                return raw.decode("utf-8", errors="replace"), True
            return handle.read().decode("utf-8", errors="replace"), False
    except OSError:
        return "", False


@router.get("/runs/{run_id}/logs")
async def get_run_logs(
    request: Request,
    run_id: str,
    offset: int = 0,
    limit: int = LOG_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Retrieve logs for a specific run from on-disk log files.

    Reads stdout.log and stderr.log from each node's execution directory under
    workspace/runs/{run_id}/. Per-file reads are tail-capped and the assembled
    log array is paginated via ``offset``/``limit`` so a chatty tool cannot
    exhaust server memory.
    """
    settings = _get_settings(request)
    run_dir = _safe_run_dir(settings, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run directory not found: '{run_id}'")

    offset = max(0, int(offset))
    limit = max(1, min(int(limit), LOG_MAX_LIMIT))

    logs: list[dict[str, Any]] = []
    truncated_files: list[str] = []
    meta_path = run_dir / "run_metadata.json"
    nodes_meta: dict[str, Any] = {}
    run_started_at = datetime.now(timezone.utc).isoformat()
    final_status = "unknown"

    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            nodes_meta = meta.get("nodes", {})
            run_started_at = meta.get("started_at") or run_started_at
            final_status = meta.get("status", final_status)
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
            content, was_truncated = _read_log_tail(log_path, LOG_MAX_BYTES_PER_FILE)
            if was_truncated:
                truncated_files.append(f"{node_id}/{stream_name}.log")
            try:
                mtime = datetime.fromtimestamp(log_path.stat().st_mtime, tz=timezone.utc).isoformat()
            except OSError:
                mtime = run_started_at
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

    # Synthetic complete event
    logs.append({
        "node_id": "engine",
        "level": "success" if final_status == "completed" else "error" if final_status == "failed" else "info",
        "message": f"Workflow {final_status}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stream": "event",
    })

    total = len(logs)
    page = logs[offset : offset + limit]
    return {
        "run_id": run_id,
        "logs": page,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
        "truncated_files": truncated_files,
    }


@router.get("/runs/{run_id}/report", response_class=PlainTextResponse)
async def get_run_report(request: Request, run_id: str) -> PlainTextResponse:
    """Render the provenance HTML execution report for a finished run."""
    from bionodulo.provenance import generate_execution_report

    settings = _get_settings(request)
    run_dir = _safe_run_dir(settings, run_id)
    meta_path = run_dir / "run_metadata.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail=f"Run metadata not found: '{run_id}'")
    try:
        run_metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read run metadata for %s: %s", run_id, exc)
        raise HTTPException(status_code=500, detail="Could not read run metadata") from exc

    html_text = generate_execution_report(run_metadata, include_artifacts=True)
    return PlainTextResponse(html_text, media_type="text/html; charset=utf-8")


@router.get("/runs/{run_id}/manifest")
async def get_run_manifest(request: Request, run_id: str) -> JSONResponse:
    """Return the JSON provenance manifest for a finished run."""
    from bionodulo.provenance import generate_provenance_report

    settings = _get_settings(request)
    run_dir = _safe_run_dir(settings, run_id)
    meta_path = run_dir / "run_metadata.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail=f"Run metadata not found: '{run_id}'")
    try:
        run_metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read run metadata for %s: %s", run_id, exc)
        raise HTTPException(status_code=500, detail="Could not read run metadata") from exc

    workflow: dict[str, Any] = {}
    node_results: dict[str, dict[str, Any]] = {}
    artifacts = run_metadata.get("artifacts") if isinstance(run_metadata.get("artifacts"), list) else []

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
    """Set a new workspace root directory.

    Constrained to the user's home directory tree (or BIONODULO_ROOT_BASE) so a
    caller cannot repoint the root at "/" or a system directory and then read or
    write arbitrary files through the workspace file endpoints.
    """
    new_root = Path(body.path).resolve()
    if not new_root.exists():
        raise HTTPException(
            status_code=400, detail=f"Directory does not exist: \\\'{body.path}\\\'"
        )
    if not new_root.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: \\\'{body.path}\\\'")

    allowed_base = Path(os.environ.get("BIONODULO_ROOT_BASE", str(Path.home()))).resolve()
    try:
        new_root.relative_to(allowed_base)
    except ValueError:
        raise HTTPException(
            status_code=403,
            detail=f"Workspace root must be inside {allowed_base}",
        )

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
    installed_packages = list_installed_packages(settings.custom_nodes_dir)
    return {
        "registries": settings.registries,
        "tool_paths": settings.tool_paths,
        "custom_node_registries": registry_entries(settings.custom_nodes_dir),
        "installed_packages": installed_packages,
    }


def _validate_git_clone_inputs(url: str, branch: str | None, commit: str | None) -> None:
    """Guard `git clone` against transport/argument-injection abuse.

    `git clone` uses an argument list (no shell), so classic injection is out,
    but a `url` like `ext::sh -c ...` or `file://` can execute code or read the
    filesystem, and a `branch`/`commit` starting with `-` can smuggle git flags.
    Restrict the URL to https/ssh git remotes and refs to safe characters.
    """
    from urllib.parse import urlparse

    u = (url or "").strip()
    if u.startswith("git@") and ":" in u:  # scp-like SSH form: git@host:org/repo
        pass
    else:
        scheme = urlparse(u).scheme.lower()
        if scheme not in ("https", "ssh"):
            raise HTTPException(
                status_code=400,
                detail="Repository URL must be an https:// or ssh:// (or git@host:) git remote.",
            )
    for label, ref in (("branch", branch), ("commit", commit)):
        if ref and (ref.startswith("-") or not re.fullmatch(r"[A-Za-z0-9._/-]+", ref)):
            raise HTTPException(status_code=400, detail=f"Invalid git {label}: {ref!r}")


@router.post("/manager/install-git")
async def manager_install_git(
    request: Request, body: ManagerGitRequest
) -> dict[str, str]:
    """Install a custom node from a Git repository."""
    _validate_git_clone_inputs(body.url, body.branch, body.commit)
    settings = _get_settings(request)
    target_dir = settings.custom_nodes_dir
    if body.directory:
        target_dir = target_dir / body.directory
    else:
        # Derive directory name from URL
        from urllib.parse import urlparse
        repo_name = Path(urlparse(body.url).path).stem
        target_dir = target_dir / repo_name

    if target_dir.exists():
        raise HTTPException(
            status_code=409,
            detail=f"Directory already exists: \\\'{target_dir.name}\\\'",
        )

    try:
        cmd = ["git", "clone", "--depth", "1", "--branch", body.branch, "--", body.url, str(target_dir)]
        if body.commit:
            # Full clone for specific commit
            cmd = ["git", "clone", "--", body.url, str(target_dir)]
        await asyncio.to_thread(
            subprocess.run,
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if body.commit:
            await asyncio.to_thread(
                subprocess.run,
                ["git", "-C", str(target_dir), "checkout", body.commit],
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
    except subprocess.CalledProcessError as exc:
        raise HTTPException(status_code=500, detail=f"Git clone failed: {exc.stderr}") from exc
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="Git clone timed out") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail="Git not found on system") from exc

    # Reload custom nodes
    registry = _get_registry(request)
    if hasattr(registry, "load_custom_nodes"):
        await asyncio.to_thread(registry.load_custom_nodes, settings.custom_nodes_dir)

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

    try:
        result = await asyncio.to_thread(
            subprocess.run,
            ["git", "-C", str(node_dir), "pull"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise HTTPException(
                status_code=500, detail=f"Git pull failed: {result.stderr}"
            )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="Git pull timed out") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail="Git not found") from exc

    # Reload
    registry = _get_registry(request)
    if hasattr(registry, "load_custom_nodes"):
        await asyncio.to_thread(registry.load_custom_nodes, settings.custom_nodes_dir)

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

    await asyncio.to_thread(shutil.rmtree, node_dir)

    # Reload
    registry = _get_registry(request)
    if hasattr(registry, "load_custom_nodes"):
        await asyncio.to_thread(registry.load_custom_nodes, settings.custom_nodes_dir)

    return {"status": "removed", "package": body.name}


@router.post("/manager/reload")
async def manager_reload(request: Request) -> dict[str, str]:
    """Reload all custom nodes."""
    settings = _get_settings(request)
    registry = _get_registry(request)

    def reload_nodes() -> None:
        if hasattr(registry, "load_builtin_nodes"):
            registry.load_builtin_nodes()
        if hasattr(registry, "load_custom_nodes"):
            registry.load_custom_nodes(settings.custom_nodes_dir)

    await asyncio.to_thread(reload_nodes)
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
        _schedule_event_emit_threadsafe(
            loop,
            event_hub,
            "install.log",
            payload,
            source="pixi-installer",
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


@router.get("/manager/status/{job_id}")
async def manager_job_status(request: Request, job_id: str) -> dict[str, Any]:
    """Get the status of an async install job."""
    installer = app_state(request).dependency_installer
    job = installer.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return job.progress.to_dict()

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

    def emit(event_type: str, data: dict[str, Any]) -> None:
        _schedule_event_emit(
            event_hub,
            event_type,
            {
                **data,
                "level": data.get("level", "info"),
                "timestamp": datetime.now().isoformat(),
            },
            source="dependency-installer",
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
    envs = await asyncio.to_thread(list_all_envs, settings.project_root)
    return {"environments": envs, "count": len(envs)}


@router.get("/manager/environments/{env_id}")
async def get_environment(env_id: str, request: Request) -> dict[str, Any]:
    """Get details for a specific environment including installed packages."""
    settings = _get_settings(request)
    env_dir = get_env_dir(env_id, settings.project_root)
    if not env_dir.exists():
        raise HTTPException(status_code=404, detail=f"Environment '{env_id}' not found")
    meta, packages, ready = await asyncio.to_thread(
        lambda: (get_env_meta(env_dir), get_env_packages(env_dir), is_env_ready(env_dir))
    )
    return {
        "id": env_id,
        "name": meta.get("name") or f"Env {env_id[:8]}",
        "path": str(env_dir),
        "packages": packages,
        "package_count": len(packages),
        "ready": ready,
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
    await asyncio.to_thread(set_env_meta, env_dir, name=new_name)
    return {"success": True, "id": env_id, "name": new_name}


@router.post("/manager/environments/{env_id}/duplicate")
async def duplicate_environment(env_id: str, request: Request) -> dict[str, Any]:
    """Duplicate an environment."""
    settings = _get_settings(request)
    env_dir = get_env_dir(env_id, settings.project_root)
    if not env_dir.exists():
        raise HTTPException(status_code=404, detail=f"Environment '{env_id}' not found")
    success, message, new_id = await asyncio.to_thread(duplicate_env_dir, env_dir, settings.project_root)
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
    success, message = await asyncio.to_thread(remove_package_from_env, env_dir, pkg_name)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message}


@router.delete("/manager/environments/{env_id}")
async def delete_environment(env_id: str, request: Request) -> dict[str, Any]:
    """Remove an environment directory."""
    settings = _get_settings(request)
    env_dir = get_env_dir(env_id, settings.project_root)
    success, message = await asyncio.to_thread(delete_env_dir, env_dir)
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
        content = await asyncio.to_thread(
            export_workflow,
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
                content = await asyncio.to_thread(file_path_obj.read_text, encoding="utf-8")
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not content and not file_path_obj:
        raise HTTPException(status_code=400, detail="No content or file_path provided")

    # Try to delegate to converter module
    try:
        if source == "snakemake":
            from bionodulo.converter.snakemake_converter import import_from_snakemake as snakemake_import
            workflow = await asyncio.to_thread(snakemake_import, content)
        elif source == "nextflow":
            from bionodulo.converter.nextflow_converter import import_from_nextflow as nextflow_import
            workflow = await asyncio.to_thread(nextflow_import, content)
        elif source == "cwl":
            from bionodulo.converter.cwl_converter import import_from_cwl as cwl_import
            if file_path_obj:
                workflow = await asyncio.to_thread(cwl_import, file_path_obj)
            else:
                with tempfile.NamedTemporaryFile(mode="w", suffix=".cwl", delete=False) as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name
                try:
                    workflow = await asyncio.to_thread(cwl_import, tmp_path)
                finally:
                    os.unlink(tmp_path)
        elif source == "galaxy":
            from bionodulo.converter.galaxy_converter import import_from_galaxy as galaxy_import
            workflow = await asyncio.to_thread(galaxy_import, content)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported import format: \\'{source}\\'")

        return {"workflow": workflow, "source": source, "imported": True}
    except ImportError as exc:
        logger.warning("Converter module not available: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=(
                f"Converter for {source} is unavailable. "
                "Install converter dependencies before importing this format."
            ),
        ) from exc
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
            submit_workflow = hpc.submit_workflow
            submit_kwargs = {
                "workflow": body.workflow,
                "name": body.name,
                "cpus": body.cpus,
                "memory": body.memory,
                "walltime": body.walltime,
                "dependency_jobs": body.dependency_jobs,
            }
            if body.parameters:
                if not _callable_accepts_keyword(submit_workflow, "parameters"):
                    raise HTTPException(
                        status_code=501,
                        detail="HPC backend submit_workflow does not support runtime parameters",
                    )
                submit_kwargs["parameters"] = body.parameters
            remote_job_id = await submit_workflow(**submit_kwargs)
            return {"job_id": job_id, "remote_job_id": remote_job_id, "status": "submitted"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("HPC submit failed: %s", exc)
        raise HTTPException(status_code=500, detail="HPC submit failed") from exc

    raise HTTPException(status_code=501, detail="HPC backend submit_workflow is not implemented")


@router.get("/hpc/jobs/{job_id}")
async def hpc_job_status(request: Request, job_id: str) -> dict[str, Any]:
    """Check the status of an HPC job."""
    hpc = getattr(request.app.state, "hpc_backend", None)
    if hpc is not None and hasattr(hpc, "job_status"):
        try:
            return await hpc.job_status(job_id)
        except Exception as exc:
            logger.warning("Failed to get HPC job status for %s: %s", job_id, exc)
            raise HTTPException(status_code=500, detail="Failed to get job status") from exc

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
    docs_dirs = [
        settings.project_root / "docs" / "help",
        REPO_ROOT / "docs" / "help",
    ]
    for docs_dir in docs_dirs:
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
        _schedule_event_emit_threadsafe(
            loop,
            event_hub,
            "install.progress",
            payload,
            source="example-data",
        )

    emit_progress("Starting example data download from public sources ...", "info")

    # Run download in a thread pool so the event loop stays responsive
    result = await asyncio.to_thread(
        download_example_data,
        project_root=settings.project_root,
        emit=emit_progress,
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
