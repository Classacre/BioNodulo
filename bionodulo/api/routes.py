"""All REST API endpoints for BioNodulo v2.

References app.state for registry, settings, queue, and event_hub.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from bionodulo.api.system_stats import router as system_stats_router
from bionodulo.api.previews import router as previews_router
from bionodulo.api.schemas import (
    AIChatRequest,
    DeleteFilesRequest,
    DependencyTreeRequest,
    EnvironmentCreateRequest,
    EnvironmentInstallRequest,
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
    ManagerResolveRequest,
    RunCreateRequest,
    SettingsSaveRequest,
    SettingsSetRequest,
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
from bionodulo.workflow.graph import (
    downstream_nodes,
    incoming_edges,
    topological_sort,
    upstream_nodes,
)
from bionodulo.workflow.serialization import load_workflow, save_workflow
from bionodulo.environments.manager import (
    create_conda_env,
    create_workflow_env,
    delete_conda_env,
    env_exists,
    executable_in_env,
    get_env_packages,
    install_into_env,
    list_conda_envs,
    workflow_dependency_tree,
)
from bionodulo.manager.installer import InstallJob
from bionodulo.manager.resolver import build_node_manifest, resolve_workflow
from bionodulo.workflow.validation import validate_workflow

logger = logging.getLogger(__name__)

router = APIRouter()
router.include_router(system_stats_router)
router.include_router(previews_router)


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

@router.post("/runs")
async def create_run(request: Request, body: RunCreateRequest) -> dict[str, Any]:
    """Submit a workflow for execution."""
    queue = _get_queue(request)
    event_hub = _get_event_hub(request)

    run_id = str(uuid.uuid4())
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
            name=body.name,
            mock=body.mock,
            environment=body.environment,
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

    return {"run_id": run_id, "status": "queued", "name": body.name}


@router.post("/prompt")
async def comfyui_prompt(request: Request) -> dict[str, Any]:
    """ComfyUI-compatible prompt endpoint.

    Accepts a workflow in ComfyUI prompt format and submits it for execution.
    """
    body = await request.json()
    queue = _get_queue(request)
    event_hub = _get_event_hub(request)

    run_id = str(uuid.uuid4())
    await event_hub.emit_typed(
        "execution.prompt_submitted",
        {"run_id": run_id},
        source=run_id,
    )

    if hasattr(queue, "submit"):
        await queue.submit(
            run_id=run_id,
            workflow=body,
            name="prompt-run",
            mock=None,
            environment=None,
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
    if hasattr(queue, "get_history"):
        return await queue.get_history()
    return {}


@router.get("/runs/{run_id}")
async def get_run_details(request: Request, run_id: str) -> dict[str, Any]:
    """Get details for a specific run."""
    queue = _get_queue(request)
    if hasattr(queue, "get_run"):
        run = await queue.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"Run \\\'{run_id}\\\' not found")
        return run

    runs: dict[str, Any] = getattr(request.app.state, "runs", {})
    if run_id in runs:
        return runs[run_id]
    raise HTTPException(status_code=404, detail=f"Run \\\'{run_id}\\\' not found")


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
    """Send a message to the AI assistant and get a response."""
    # Check if AI assistant is available in app state
    ai = getattr(request.app.state, "ai_assistant", None)
    if ai is not None and hasattr(ai, "chat"):
        response = await ai.chat(
            message=body.message,
            workflow=body.workflow,
            history=body.history,
        )
        return {"response": response, "model": getattr(ai, "model", "default")}

    # Fallback: return a helpful mock response
    return {
        "response": (
            f"AI assistant received: \\\'{body.message}\\\'. "
            "(AI module not configured - responses are simulated.)"
        ),
        "model": "mock",
        "note": "Install and configure the AI assistant module for real responses.",
    }


@router.post("/ai/chat/stream")
async def ai_chat_stream(request: Request, body: AIChatRequest) -> Any:
    """Stream an AI assistant response as server-sent events."""
    from fastapi.responses import StreamingResponse

    async def _stream():
        chunks = [
            "AI assistant (streaming mode): ",
            "Analyzing your request... ",
            f"Message was: \\\'{body.message}\\\'. ",
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


@router.post("/manager/diagnose")
async def manager_diagnose(
    request: Request, body: ManagerDiagnoseRequest
) -> dict[str, Any]:
    """Diagnose a workflow (find missing tools, type mismatches)."""
    registry = _get_registry(request)
    result = validate_workflow(body.workflow, registry)
    report = resolve_workflow(body.workflow, registry)

    return {
        "valid": result.valid,
        "errors": result.errors,
        "warnings": result.warnings,
        "missing_nodes": [n.node_type for n in report.missing_nodes],
        "missing_tools": [e.name for e in report.missing_executables],
        "missing_packages": [p.name for p in report.missing_packages],
        "resolution": report.to_dict(),
    }


@router.post("/manager/resolve")
async def manager_resolve(
    request: Request, body: ManagerResolveRequest
) -> dict[str, Any]:
    """Resolve dependencies for a workflow.

    Returns a report of missing nodes, executables, and packages
    with installation information where available.
    """
    registry = _get_registry(request)
    report = resolve_workflow(body.workflow, registry)
    return report.to_dict()


@router.post("/manager/install-deps")
async def manager_install_deps(
    request: Request, body: ManagerInstallDepsRequest
) -> dict[str, Any]:
    """Start an async install job for missing dependencies.

    Returns a job_id that can be polled via /manager/status/{job_id}.
    """
    settings = _get_settings(request)
    job = InstallJob.create(body.report, settings.custom_nodes_dir)

    # Start install in background
    asyncio.create_task(job.run())

    return {"job_id": job.job_id, "status": "started"}


@router.get("/manager/status/{job_id}")
async def manager_status(job_id: str) -> dict[str, Any]:
    """Get the status of an async install job."""
    job = InstallJob.get(job_id)
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
# Environment Manager
# ---------------------------------------------------------------------------

@router.get("/manager/environments")
async def list_environments() -> dict[str, Any]:
    """List all Conda/Mamba/Micromamba environments."""
    envs = list_conda_envs()
    return {"environments": envs, "count": len(envs)}


@router.post("/manager/environments")
async def create_environment(body: EnvironmentCreateRequest) -> dict[str, Any]:
    """Create a new Conda environment with specified packages."""
    success, message = create_conda_env(
        name=body.name,
        packages=body.packages,
        channels=body.channels,
        pip_packages=body.pip_packages,
    )
    if not success:
        raise HTTPException(status_code=500, detail=message)
    return {"success": True, "message": message, "name": body.name}


@router.get("/manager/environments/{name}")
async def get_environment(name: str) -> dict[str, Any]:
    """Get details for a specific environment including installed packages."""
    if not env_exists(name):
        raise HTTPException(status_code=404, detail=f"Environment '{name}' not found")
    packages = get_env_packages(name)
    return {"name": name, "packages": packages, "package_count": len(packages)}


@router.delete("/manager/environments/{name}")
async def delete_environment(name: str) -> dict[str, Any]:
    """Remove a Conda environment."""
    if not env_exists(name):
        raise HTTPException(status_code=404, detail=f"Environment '{name}' not found")
    success, message = delete_conda_env(name)
    if not success:
        raise HTTPException(status_code=500, detail=message)
    return {"success": True, "message": message}


@router.post("/manager/environments/{name}/install")
async def install_into_environment(name: str, body: EnvironmentInstallRequest) -> dict[str, Any]:
    """Install packages into an existing environment."""
    if not env_exists(name):
        raise HTTPException(status_code=404, detail=f"Environment '{name}' not found")
    success, message = install_into_env(name, body.packages, body.channels)
    if not success:
        raise HTTPException(status_code=500, detail=message)
    return {"success": True, "message": message}


@router.post("/manager/dependency-tree")
async def get_dependency_tree(
    request: Request, body: DependencyTreeRequest
) -> dict[str, Any]:
    """Get the dependency status tree for a workflow.

    Returns each dependency with its status (installed, missing, etc.)
    and where it is available.
    """
    registry = _get_registry(request)
    tree = workflow_dependency_tree(body.workflow, registry)
    return {
        "dependencies": [
            {
                "name": d.name,
                "type": d.type,
                "status": d.status,
                "source": d.source,
                "message": d.message,
                "envs": d.envs,
            }
            for d in tree
        ],
        "count": len(tree),
        "missing_count": sum(1 for d in tree if d.status == "missing"),
    }


@router.post("/manager/create-workflow-env")
async def manager_create_workflow_env(
    request: Request, body: WorkflowEnvironmentRequest
) -> dict[str, Any]:
    """Create a dedicated environment for a workflow.

    Extracts required executables from the workflow's nodes and creates
    a conda environment with those packages.
    """
    registry = _get_registry(request)
    report = resolve_workflow(body.workflow, registry)

    deps: list[str] = []
    for exe in report.missing_executables:
        pkg = exe.conda_package or exe.name
        if pkg and pkg not in deps:
            deps.append(pkg)
    for pkg in report.missing_packages:
        if pkg.name not in deps:
            deps.append(pkg.name)

    if not deps:
        return {"success": True, "message": "No dependencies to install", "env_name": ""}

    wf_id = body.workflow.get("name", "untitled").replace(" ", "-").lower()[:20]
    success, message, env_name = create_workflow_env(wf_id, deps)
    if not success:
        raise HTTPException(status_code=500, detail=message)
    return {"success": True, "message": message, "env_name": env_name}


# ---------------------------------------------------------------------------
# Workflow Templates
# ---------------------------------------------------------------------------

@router.get("/workflow_templates")
async def list_workflow_templates(request: Request) -> dict[str, Any]:
    """List available workflow templates."""
    settings = _get_settings(request)
    templates_dir = settings.project_root / "templates"
    templates: list[dict[str, Any]] = []

    if templates_dir.exists():
        for entry in sorted(templates_dir.iterdir()):
            if entry.suffix.lower() == ".json":
                try:
                    data = json.loads(entry.read_text(encoding="utf-8"))
                    templates.append({
                        "name": entry.stem,
                        "filename": entry.name,
                        "description": data.get("description", ""),
                        "node_count": len(data.get("nodes", {}))
                        if isinstance(data.get("nodes"), dict)
                        else len(data.get("nodes", [])),
                    })
                except (json.JSONDecodeError, OSError):
                    templates.append({
                        "name": entry.stem,
                        "filename": entry.name,
                        "description": "",
                        "node_count": 0,
                    })

    return {"templates": templates, "count": len(templates)}


@router.get("/workflow_templates/{filename}")
async def get_workflow_template(request: Request, filename: str) -> dict[str, Any]:
    """Return a specific workflow template JSON."""
    settings = _get_settings(request)
    templates_dir = settings.project_root / "templates"
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

    if not content and body.file_path:
        settings = _get_settings(request)
        try:
            file_path = _safe_path(body.file_path, settings.project_root)
            content = file_path.read_text(encoding="utf-8")
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not content:
        raise HTTPException(status_code=400, detail="No content or file_path provided")

    # Try to delegate to converter module
    try:
        if source == "snakemake":
            from bionodulo.converter.snakemake_converter import import_workflow as snakemake_import
            workflow = snakemake_import(content)
        elif source == "nextflow":
            from bionodulo.converter.nextflow_converter import import_workflow as nextflow_import
            workflow = nextflow_import(content)
        elif source == "cwl":
            from bionodulo.converter.cwl_converter import import_workflow as cwl_import
            workflow = cwl_import(content)
        elif source == "galaxy":
            from bionodulo.converter.galaxy_converter import import_workflow as galaxy_import
            workflow = galaxy_import(content)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported import format: \\\'{source}\\\'")

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
    """Get HPC connection and job status."""
    hpc = getattr(request.app.state, "hpc_backend", None)
    if hpc is not None and hasattr(hpc, "status"):
        return await hpc.status()

    return {
        "connected": False,
        "backend": None,
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
        backend_class = None
        if body.backend == "slurm":
            from bionodulo.hpc.slurm import SlurmBackend
            backend_class = SlurmBackend
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
