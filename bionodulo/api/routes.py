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

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from bionodulo.api.system_stats import router as system_stats_router
from bionodulo.api.previews import router as previews_router
from bionodulo.api.schemas import (
    AIChatRequest,
    AuthMeResponse,
    AuthTokenRequest,
    AuthTokenResponse,
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
    RoomStatusResponse,
    RunCreateRequest,
    SettingsSaveRequest,
    SettingsSetRequest,
    ShareWorkflowRequest,
    ShareWorkflowResponse,
    ValidationRequest,
    WorkspaceRootRequest,
    WorkflowEnvironmentRequest,
    WorkflowExportRequest,
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
from bionodulo.ai.assistant import chat_with_tools
from bionodulo.manager.diagnostics import host_diagnostics
from bionodulo.manager.example_data import download_example_data
from bionodulo.manager.installer import get_installer
from bionodulo.hpc.base import HPCBackend
from bionodulo.manager.resolver import _resolve_workflow_async
from bionodulo.workflow.validation import validate_workflow
from bionodulo.collab.auth import get_token_from_header_or_query, validate_token

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


def _get_settings_manager(request: Request) -> Any:
    return request.app.state.settings_manager


def _setting_literal(request: Request, key: str, default: Any = None) -> Any:
    """Read frontend-style literal dotted settings keys.

    SettingsManager also supports nested dotted access, but the React settings
    store persists keys such as "bionodulo.collab.enabled" literally.
    """
    sm = _get_settings_manager(request)
    try:
        settings = sm.get_all()
    except Exception:
        settings = {}
    return settings.get(key, default)


def _setting_bool(request: Request, key: str, default: bool = False) -> bool:
    value = _setting_literal(request, key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _safe_path(path_str: str, root: Path) -> Path:
    return ensure_within(Path(path_str), root)


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
            metadata={"name": body.name, "environment": body.environment},
            force=body.no_cache,
        )
    else:
        # Fallback: store in app state
        runs: dict[str, Any] = getattr(request.app.state, "runs", {})
        runs[run_id] = {
            "run_id": run_id,
            "name": body.name,
            "status": "queued",
            "workflow": body.workflow,
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
async def clear_queue(request: Request) -> dict[str, str]:
    """Clear all pending jobs from the queue."""
    queue = _get_queue(request)
    if hasattr(queue, "clear"):
        await queue.clear()
    return {"status": "cleared"}


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
# Settings (ComfyUI-style per-user settings)
# ---------------------------------------------------------------------------

@router.get("/settings")
async def get_all_settings(request: Request) -> dict[str, Any]:
    """Get all user settings."""
    sm = _get_settings_manager(request)
    return sm.get_all()


@router.post("/settings")
async def save_settings(request: Request, body: SettingsSaveRequest) -> dict[str, str]:
    """Save multiple user settings at once."""
    sm = _get_settings_manager(request)
    sm.set_many(body.settings)
    return {"status": "saved"}


@router.get("/settings/{setting_id}")
async def get_setting(request: Request, setting_id: str) -> Any:
    """Get a specific user setting by ID.

    Supports dotted key access for nested values.
    """
    sm = _get_settings_manager(request)
    value = sm.get(setting_id)
    if value is None:
        raise HTTPException(status_code=404, detail=f"Setting \\\'{setting_id}\\\' not found")
    return {setting_id: value}


@router.post("/settings/{setting_id}")
async def set_setting(
    request: Request, setting_id: str, body: SettingsSetRequest
) -> dict[str, str]:
    """Set a specific user setting by ID.

    Supports dotted key access for nested values.
    """
    sm = _get_settings_manager(request)
    sm.set(setting_id, body.value)
    return {"status": "saved", "id": setting_id}


# ---------------------------------------------------------------------------
# AI Assistant
# ---------------------------------------------------------------------------

@router.post("/ai/chat")
async def ai_chat(request: Request, body: AIChatRequest) -> dict[str, Any]:
    """Send a message to the AI assistant and get a tool-aware response."""
    settings = _get_settings(request)
    settings_manager = _get_settings_manager(request)
    registry = _get_registry(request)

    provider = body.provider or _setting_literal(request, "bionodulo.llm.provider", "openai")
    model = body.model or _setting_literal(request, "bionodulo.llm.model", None)
    api_key = _setting_literal(request, "bionodulo.llm.apiKey", "") or os.environ.get("OPENAI_API_KEY", "")
    api_base = _setting_literal(request, "bionodulo.llm.baseUrl", None) or None
    temperature = _setting_literal(request, "bionodulo.llm.temperature", 0.2)
    try:
        temperature = float(temperature)
    except (TypeError, ValueError):
        temperature = 0.2

    try:
        response = await chat_with_tools(
            user_message=body.message,
            workflow=body.workflow,
            workflow_id=body.workflow_id,
            history=body.history,
            provider=provider,
            model=model,
            api_key=api_key,
            api_base=api_base,
            temperature=temperature,
            registry=registry,
            settings=settings,
            settings_manager=settings_manager,
            files=[{"name": f.name, "mime_type": f.mime_type, "content": f.content} for f in body.files],
        )
    except Exception as exc:
        return {
            "steps": [{"type": "reply", "content": f"AI error: {exc}"}],
            "reply": f"AI error: {exc}",
            "model": model or provider,
        }

    return {
        "steps": [
            {
                "type": s.type,
                "content": s.content,
                "name": s.name,
                "arguments": s.arguments,
                "result": s.result,
                "workflow": s.workflow,
                "description": s.description,
            }
            for s in response.steps
        ],
        "reply": response.reply,
        "proposed_workflow": response.proposed_workflow,
        "proposed_description": response.proposed_description,
        "model": model or provider,
    }


@router.post("/ai/chat/stream")
async def ai_chat_stream(request: Request, body: AIChatRequest) -> Any:
    """Stream an AI assistant response as server-sent events."""
    from fastapi.responses import StreamingResponse

    async def _stream():
        chunks = [
            "AI assistant (streaming mode): ",
            "Analyzing your request... ",
            f"Message was: '{body.message}'. ",
            "Configure a real AI backend (OpenAI, Ollama, etc.) for production use.",
        ]
        for chunk in chunks:
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            await asyncio.sleep(0.1)
        yield "data: [DONE]\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


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
    return host_diagnostics()


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
async def manager_job_status(job_id: str) -> dict[str, Any]:
    """Get the status of an async install job."""
    installer = get_installer()
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

    installer = get_installer()
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

                    templates.append({
                        "id": entry.stem,
                        "name": name,
                        "filename": entry.name,
                        "description": description,
                        "node_count": sum(1 for n in nodes if n.get("type") != "note"),
                        "tools": tools,
                        "category": category,
                        "tags": tags,
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

    def emit_progress(message: str, level: str = "info") -> None:
        asyncio.create_task(
            event_hub.emit_typed(
                "install.progress",
                {
                    "job_id": "example-data-download",
                    "message": message,
                    "level": level,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                source="example-data",
            )
        )

    emit_progress("Starting example data download from public sources ...", "info")

    # Run download in a thread pool so the event loop stays responsive
    loop = asyncio.get_event_loop()
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


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

security_scheme = HTTPBearer(auto_error=False)


def _get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme)) -> dict[str, Any] | None:
    """Validate the Bearer token from the Authorization header.

    Returns the decoded JWT payload, or None if no valid token was provided.
    """
    from bionodulo.collab.auth import validate_token
    if credentials is None:
        return None
    return validate_token(credentials.credentials)


@router.post("/auth/token", response_model=AuthTokenResponse)
async def auth_create_token(body: AuthTokenRequest) -> dict[str, Any]:
    """Create a new JWT authentication token.

    Generates a fresh user ID, creates a signed JWT with the provided name,
    and returns both the token and user details.
    """
    from bionodulo.collab.auth import create_token, generate_user_id

    user_id = generate_user_id()
    token = create_token(
        user_id=user_id,
        name=body.name,
        role="editor",
        expiry_hours=24,
    )
    return {
        "token": token,
        "user_id": user_id,
        "name": body.name,
    }


@router.get("/auth/me", response_model=AuthMeResponse)
async def auth_me(user: dict[str, Any] | None = Depends(_get_current_user)) -> dict[str, Any]:
    """Return the currently authenticated user's details.

    Requires a valid Bearer token in the Authorization header.
    """
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or missing authentication token")
    return {
        "user_id": user.get("sub", ""),
        "name": user.get("name", ""),
        "role": user.get("role", "editor"),
    }


# ---------------------------------------------------------------------------
# Collaboration
# ---------------------------------------------------------------------------

def _get_room_manager(request: Request) -> Any:
    if not hasattr(request.app.state, "room_manager") or request.app.state.room_manager is None:
        from bionodulo.collab.room_manager import RoomManager
        request.app.state.room_manager = RoomManager()
    return request.app.state.room_manager


def _get_permissions(request: Request) -> Any:
    if not hasattr(request.app.state, "permission_checker") or request.app.state.permission_checker is None:
        from bionodulo.collab.permissions import PermissionChecker
        from bionodulo.collab.models import CollabStore
        from bionodulo.collab.persistence import _resolve_workspace_root
        db_path = _resolve_workspace_root() / "collab.db"
        fallback = _resolve_workspace_root() / "permissions.json"
        request.app.state.permission_checker = PermissionChecker(
            store=CollabStore(str(db_path)),
            fallback_file=fallback,
        )
    return request.app.state.permission_checker


def _require_auth_payload(request: Request) -> dict[str, Any]:
    token = get_token_from_header_or_query(request)
    payload = validate_token(token) if token else None
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or missing authentication token")
    return payload


def _require_execute_permission(request: Request, workflow_id: str | None) -> dict[str, Any] | None:
    if not workflow_id:
        return None
    if not _setting_bool(request, "bionodulo.collab.enabled", False):
        return None
    payload = _require_auth_payload(request)
    user_id = payload.get("sub", "")
    permissions = _get_permissions(request)
    permissions.ensure_owner(workflow_id, user_id)
    if not permissions.can_execute(workflow_id, user_id):
        raise HTTPException(status_code=403, detail="Execute permission required")
    return payload


@router.post("/collab/share", response_model=ShareWorkflowResponse)
async def collab_share(
    request: Request,
    body: ShareWorkflowRequest,
) -> dict[str, Any]:
    """Share a workflow with another user.

    The calling user must be the owner of the workflow.
    """
    permissions = _get_permissions(request)
    payload = _require_auth_payload(request)
    caller_id = payload["sub"]
    permissions.ensure_owner(body.workflow_id, caller_id)

    if not permissions.can_share(body.workflow_id, caller_id):
        raise HTTPException(status_code=403, detail="Only the owner can share workflows")

    share = permissions.grant(
        workflow_id=body.workflow_id,
        user_id=body.user_id,
        role=body.role,
        invited_by=caller_id,
    )
    return {
        "share_id": share.id,
        "workflow_id": share.workflow_id,
        "user_id": share.user_id,
        "role": share.role,
        "invited_by": share.invited_by,
        "invited_at": share.invited_at,
    }


@router.get("/collab/shares/{workflow_id}")
async def collab_list_shares(
    request: Request,
    workflow_id: str,
) -> dict[str, Any]:
    """List all shares for a given workflow."""
    permissions = _get_permissions(request)
    payload = _require_auth_payload(request)
    caller_id = payload["sub"]
    if not permissions.can_read(workflow_id, caller_id):
        raise HTTPException(status_code=403, detail="Access denied")

    shares = permissions.list_users(workflow_id)
    return {"workflow_id": workflow_id, "shares": shares, "count": len(shares)}


@router.delete("/collab/share/{share_id}")
async def collab_revoke_share(
    request: Request,
    share_id: str,
) -> dict[str, str]:
    """Revoke a share by its share record ID."""
    from bionodulo.collab.models import CollabStore
    from bionodulo.collab.persistence import _resolve_workspace_root

    db_path = _resolve_workspace_root() / "collab.db"
    store = CollabStore(str(db_path))
    share = store.get_share(share_id)
    if share is None:
        raise HTTPException(status_code=404, detail="Share not found")

    permissions = _get_permissions(request)
    payload = _require_auth_payload(request)
    caller_id = payload["sub"]
    if not permissions.can_share(share.workflow_id, caller_id):
        raise HTTPException(status_code=403, detail="Only the owner can revoke shares")

    success = store.delete_share(share_id)
    if success:
        # Warm cache removal
        permissions.revoke(share.workflow_id, share.user_id)
    return {"status": "revoked" if success else "not_found"}


@router.get("/collab/room/{workflow_id}", response_model=RoomStatusResponse)
async def collab_room_status(
    request: Request,
    workflow_id: str,
) -> dict[str, Any]:
    """Get the current collaboration room status for a workflow."""
    payload = _require_auth_payload(request)
    caller_id = payload["sub"]
    permissions = _get_permissions(request)
    if not permissions.can_read(workflow_id, caller_id):
        raise HTTPException(status_code=403, detail="Access denied")
    room_manager = _get_room_manager(request)
    return room_manager.room_status(workflow_id)
