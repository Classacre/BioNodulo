from __future__ import annotations

import base64
from pathlib import Path
import asyncio
from datetime import datetime
import json
import os
import shutil

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from bionodulo.ai import chat_with_assistant
from bionodulo.api.schemas import AIChatRequest, ManagerGitRequest, ManagerPackageRequest, PromptCompatibilityRequest, RunCreateRequest, ValidationRequest, WorkflowExportRequest, WorkflowExtractRequest
from bionodulo.core.paths import ensure_within
from bionodulo.manager import diagnose_workflow, environment_status
from bionodulo.manager.custom_nodes import install_git, registry_entries, remove_package, update_package
from bionodulo.manager.diagnostics import environment_install_plan
from bionodulo.manager.runtime_installer import install_managed_micromamba, managed_micromamba_path, managed_micromamba_root
from bionodulo.workflow.schema import Workflow
from bionodulo.provenance.workflow_embed import extract_workflow
from bionodulo.workflow.export import export_workflow
from bionodulo.workflow.validation import validate_workflow

router = APIRouter()


class ManagerInstallRequest(BaseModel):
    workflow: Workflow
    targets: list[str] | None = None


class WorkspaceRootRequest(BaseModel):
    path: str


class WorkspaceFileOperationRequest(BaseModel):
    source_path: str
    target_dir: str = "."
    operation: str


class WorkspaceDeleteRequest(BaseModel):
    path: str
    trash: bool = True


@router.get("/object_info")
async def object_info(request: Request) -> dict:
    registry = request.app.state.node_registry
    return registry.object_info()


@router.get("/object_info/{node_id}")
async def object_info_one(node_id: str, request: Request) -> dict:
    registry = request.app.state.node_registry
    if not registry.has(node_id):
        raise HTTPException(status_code=404, detail=f"Unknown node type: {node_id}")
    return registry.get(node_id).metadata()


@router.post("/workflow/validate")
async def workflow_validate(payload: ValidationRequest, request: Request) -> dict:
    registry = request.app.state.node_registry
    result = validate_workflow(payload.workflow, registry, mock_tools=payload.mock_tools, project_root=request.app.state.settings.project_root)
    return result.model_dump()


@router.post("/ai/chat")
async def ai_chat(payload: AIChatRequest, request: Request) -> dict:
    try:
        return await chat_with_assistant(payload, request.app.state.node_registry, request.app.state.settings.project_root)
    except Exception as exc:  # noqa: BLE001 - provider errors should be visible in the chat panel.
        return {"reply": f"AI provider error: {exc}", "workflow": None, "node_blueprint": None, "raw_text": "", "validation": None, "provider": "error"}


@router.post("/ai/chat/stream")
async def ai_chat_stream(payload: AIChatRequest, request: Request) -> StreamingResponse:
    async def events():
        yield _json_line({"type": "status", "text": "Reading BioNodulo docs and active workflow..."})
        try:
            result = await chat_with_assistant(payload, request.app.state.node_registry, request.app.state.settings.project_root)
            reply = result.get("reply") or ""
            for token in _stream_chunks(reply):
                yield _json_line({"type": "token", "text": token})
                await asyncio.sleep(0.012)
            yield _json_line({"type": "final", "data": result})
        except Exception as exc:  # noqa: BLE001 - sent to chat UI.
            message = f"AI provider error: {exc}"
            for token in _stream_chunks(message):
                yield _json_line({"type": "token", "text": token})
                await asyncio.sleep(0.012)
            yield _json_line({"type": "final", "data": {"reply": message, "workflow": None, "node_blueprint": None, "raw_text": "", "validation": None, "provider": "error"}})

    return StreamingResponse(events(), media_type="application/x-ndjson")


@router.post("/runs")
async def create_run(payload: RunCreateRequest, request: Request) -> dict:
    run_queue = request.app.state.run_queue
    record = await run_queue.submit(payload.workflow, mock_tools=payload.mock_tools, force=payload.force, force_nodes=payload.force_nodes, options=payload.options)
    return record.as_dict()


@router.post("/prompt")
async def prompt_compat(payload: PromptCompatibilityRequest, request: Request) -> dict:
    workflow = payload.prompt if isinstance(payload.prompt, Workflow) else Workflow.model_validate(payload.prompt)
    run_queue = request.app.state.run_queue
    record = await run_queue.submit(workflow, mock_tools=payload.mock_tools, force=payload.force, options=payload.options)
    return {"prompt_id": record.run_id, "number": request.app.state.run_queue.queue_state()["queue_remaining"], "run": record.as_dict()}


@router.post("/workflow/extract")
async def workflow_extract(payload: WorkflowExtractRequest, request: Request) -> dict:
    try:
        path = Path(payload.path).expanduser().resolve() if payload.path else Path(payload.filename)
        if payload.path:
            path = ensure_within(path, request.app.state.settings.project_root)
        content_bytes = base64.b64decode(payload.content) if payload.content and payload.content_encoding == "base64" else None
        return extract_workflow(path, content=payload.content if content_bytes is None else None, content_bytes=content_bytes)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/workspace/workflow/extract")
async def workspace_workflow_extract(payload: WorkflowExtractRequest, request: Request) -> dict:
    if not payload.path:
        raise HTTPException(status_code=400, detail="path is required")
    try:
        path = ensure_within(request.app.state.settings.project_root / payload.path, request.app.state.settings.project_root)
        return extract_workflow(path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/workflow/export")
async def workflow_export(payload: WorkflowExportRequest, request: Request) -> dict:
    try:
        return export_workflow(payload.workflow, request.app.state.node_registry, payload.format)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/config/effective")
async def effective_config(request: Request) -> dict:
    return request.app.state.settings.as_effective_config()


@router.get("/runs")
async def list_runs(request: Request) -> list[dict]:
    return request.app.state.run_queue.list_runs()


@router.get("/runs/{run_id}")
async def get_run(run_id: str, request: Request) -> dict:
    record = request.app.state.run_queue.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}")
    return record.as_dict()


@router.get("/runs/{run_id}/execution-plan")
async def get_execution_plan(run_id: str, request: Request) -> dict:
    record = request.app.state.run_queue.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}")
    return {"run_id": run_id, "execution_plan": record.execution_plan}


@router.get("/runs/{run_id}/previews")
async def get_run_previews(run_id: str, request: Request) -> dict:
    record = request.app.state.run_queue.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}")
    return {"run_id": run_id, "previews": record.previews}


@router.get("/runs/{run_id}/nodes/{node_id}/previews")
async def get_node_previews(run_id: str, node_id: str, request: Request) -> dict:
    record = request.app.state.run_queue.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}")
    return {"run_id": run_id, "node_id": node_id, "previews": record.previews.get(node_id, [])}


@router.get("/runs/{run_id}/artifacts")
async def get_run_artifacts(run_id: str, request: Request) -> dict:
    record = request.app.state.run_queue.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}")
    return {"run_id": run_id, "artifacts": record.artifacts}


@router.post("/runs/{run_id}/interrupt")
async def interrupt_run(run_id: str, request: Request) -> dict:
    ok = await request.app.state.run_queue.interrupt(run_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Unknown or finished run: {run_id}")
    return {"ok": True}


@router.get("/runs/{run_id}/nodes/{node_id}/logs")
async def node_logs(run_id: str, node_id: str, request: Request) -> dict:
    settings = request.app.state.settings
    node_dir = settings.runs_dir / run_id / "nodes" / node_id
    if not node_dir.exists():
        sanitized = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in node_id)
        node_dir = settings.runs_dir / run_id / "nodes" / sanitized
    if not node_dir.exists():
        raise HTTPException(status_code=404, detail="Node logs not found")
    return {
        "stdout": _read_optional(node_dir / "stdout.log"),
        "stderr": _read_optional(node_dir / "stderr.log"),
        "metadata": _read_optional(node_dir / "metadata.json"),
        "outputs": _read_optional(node_dir / "outputs.json"),
    }


@router.get("/queue")
async def queue_state(request: Request) -> dict:
    return request.app.state.run_queue.queue_state()


@router.post("/queue/clear")
async def clear_queue(request: Request) -> dict:
    await request.app.state.run_queue.clear_pending()
    return {"ok": True}


@router.get("/history")
async def history(request: Request) -> list[dict]:
    return request.app.state.run_queue.list_history()


@router.get("/history/{run_id}")
async def history_one(run_id: str, request: Request) -> dict:
    record = request.app.state.run_queue.get_run(run_id)
    if record is None or run_id not in request.app.state.run_queue.history:
        raise HTTPException(status_code=404, detail=f"Unknown completed run: {run_id}")
    return record.as_dict()


@router.get("/workspace/files")
async def workspace_files(request: Request, path: str = "", depth: int = 3, show_hidden: bool = False) -> dict:
    settings = request.app.state.settings
    root = settings.project_root
    target = ensure_within(root / path, root)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")
    return _file_entry(target, root=root, max_depth=max(0, min(depth, 6)), show_hidden=show_hidden)


@router.get("/workspace/root")
async def workspace_root(request: Request) -> dict:
    settings = request.app.state.settings
    return {"path": str(settings.project_root)}


@router.post("/workspace/root")
async def set_workspace_root(payload: WorkspaceRootRequest, request: Request) -> dict:
    path = Path(payload.path).expanduser().resolve()
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Workspace path does not exist: {path}")
    if not path.is_dir():
        raise HTTPException(status_code=400, detail=f"Workspace path is not a directory: {path}")
    settings = request.app.state.settings
    settings.project_root = path
    settings.runs_dir = path / "runs"
    settings.cache_dir = path / ".bionodulo_cache"
    settings.custom_nodes_dir = path / "custom_nodes"
    settings.ensure_directories()
    request.app.state.run_queue.executor.runs_dir = settings.runs_dir
    request.app.state.run_queue.executor.cache = request.app.state.run_queue.executor.cache.__class__(settings.cache_dir)
    return {"path": str(settings.project_root)}


@router.get("/workspace/directories")
async def workspace_directories(request: Request, path: str = "") -> dict:
    settings = request.app.state.settings
    target = Path(path).expanduser().resolve() if path else settings.project_root
    if not target.exists() or not target.is_dir():
        target = settings.project_root
    entries = []
    try:
        for child in sorted(target.iterdir(), key=lambda value: value.name.lower()):
            if child.is_dir() and not child.name.startswith("."):
                entries.append({"name": child.name, "path": str(child.resolve())})
    except OSError:
        entries = []
    parent = target.parent if target.parent != target else None
    quick_roots = [{"name": "Home", "path": str(Path.home().resolve())}, {"name": "Current workspace", "path": str(settings.project_root)}]
    if Path.cwd().anchor:
        quick_roots.append({"name": Path.cwd().anchor, "path": Path.cwd().anchor})
    return {
        "path": str(target),
        "parent": str(parent.resolve()) if parent else None,
        "entries": entries[:300],
        "quick_roots": quick_roots,
    }


@router.get("/workspace/file")
async def workspace_file(request: Request, path: str) -> dict:
    settings = request.app.state.settings
    target = ensure_within(settings.project_root / path, settings.project_root)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail=f"Workspace file not found: {path}")
    if target.stat().st_size > 8_000_000:
        raise HTTPException(status_code=400, detail="File is too large to open in the browser.")
    return {"path": path, "content": target.read_text(encoding="utf-8", errors="replace")}


@router.post("/workspace/file-operation")
async def workspace_file_operation(payload: WorkspaceFileOperationRequest, request: Request) -> dict:
    settings = request.app.state.settings
    root = settings.project_root
    source = ensure_within(root / payload.source_path, root)
    target_dir = ensure_within(root / payload.target_dir, root)
    if not source.exists():
        raise HTTPException(status_code=404, detail=f"Workspace item not found: {payload.source_path}")
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=400, detail=f"Paste target is not a directory: {payload.target_dir}")
    destination = _available_destination(target_dir / source.name)
    if payload.operation == "copy":
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
    elif payload.operation == "move":
        shutil.move(str(source), str(destination))
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported file operation: {payload.operation}")
    return {"ok": True, "destination": str(destination.relative_to(root)).replace("\\", "/")}


@router.post("/workspace/delete")
async def workspace_delete(payload: WorkspaceDeleteRequest, request: Request) -> dict:
    settings = request.app.state.settings
    root = settings.project_root
    target = ensure_within(root / payload.path, root)
    if target == root:
        raise HTTPException(status_code=400, detail="Cannot delete the workspace root.")
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Workspace item not found: {payload.path}")
    if payload.trash:
        trash_dir = root / ".bionodulo_trash"
        trash_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        destination = _available_destination(trash_dir / f"{stamp}-{target.name}")
        shutil.move(str(target), str(destination))
        return {"ok": True, "deleted": payload.path, "trash_path": str(destination.relative_to(root)).replace("\\", "/")}
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    return {"ok": True, "deleted": payload.path}


@router.get("/manager/status")
async def manager_status(request: Request) -> dict:
    return environment_status(request.app.state.node_registry, custom_nodes_dir=request.app.state.settings.custom_nodes_dir)


@router.get("/manager/registry")
async def manager_registry(request: Request) -> dict:
    settings = request.app.state.settings
    return {"registry": registry_entries(settings.registries), "custom_nodes_dir": str(settings.custom_nodes_dir)}


@router.post("/manager/install-git")
async def manager_install_git(payload: ManagerGitRequest, request: Request) -> dict:
    result = install_git(payload.url, request.app.state.settings.custom_nodes_dir, name=payload.name)
    if result.get("ok"):
        request.app.state.node_registry.load_custom_nodes(request.app.state.settings.custom_nodes_dir)
    return result


@router.post("/manager/update")
async def manager_update(payload: ManagerPackageRequest, request: Request) -> dict:
    result = update_package(payload.package, request.app.state.settings.custom_nodes_dir)
    if result.get("ok"):
        request.app.state.node_registry.load_custom_nodes(request.app.state.settings.custom_nodes_dir)
    return result


@router.post("/manager/remove")
async def manager_remove(payload: ManagerPackageRequest, request: Request) -> dict:
    result = remove_package(payload.package, request.app.state.settings.custom_nodes_dir)
    if result.get("ok"):
        registry = request.app.state.node_registry.__class__()
        registry.load_builtin_nodes()
        registry.load_custom_nodes(request.app.state.settings.custom_nodes_dir)
        request.app.state.node_registry = registry
        request.app.state.run_queue.registry = registry
        request.app.state.run_queue.executor.registry = registry
    return result


@router.post("/manager/reload")
async def manager_reload(request: Request) -> dict:
    registry = request.app.state.node_registry.__class__()
    registry.load_builtin_nodes()
    registry.load_custom_nodes(request.app.state.settings.custom_nodes_dir)
    request.app.state.node_registry = registry
    request.app.state.run_queue.registry = registry
    request.app.state.run_queue.executor.registry = registry
    return {"ok": True, "registered_nodes": len(registry.all()), "import_warnings": registry.import_warnings}


@router.post("/manager/diagnose")
async def manager_diagnose(payload: ValidationRequest, request: Request) -> dict:
    return diagnose_workflow(payload.workflow, request.app.state.node_registry)


@router.post("/manager/install-plan")
async def manager_install_plan(payload: ValidationRequest) -> dict:
    plan = environment_install_plan(payload.workflow)
    return {"plan": plan, "install_requires_confirmation": True}


@router.post("/manager/install")
async def manager_install(payload: ManagerInstallRequest, request: Request) -> dict:
    diagnosis = diagnose_workflow(payload.workflow, request.app.state.node_registry)
    targets = set(payload.targets or [])
    plans = [
        plan
        for plan in diagnosis.get("install_plans", [])
        if plan and (not targets or plan.get("target") in targets or plan.get("action") in targets)
    ]
    results = []
    for plan in plans:
        if plan.get("action") == "install_managed_micromamba":
            results.append(install_managed_micromamba())
            continue
        command = _resolved_install_command(plan.get("command") or [])
        if not command:
            results.append({"target": plan.get("target"), "status": "skipped", "message": plan.get("command_hint", "No executable install command available yet.")})
            continue
        if not _allowed_install_command(command):
            results.append({"target": plan.get("target"), "status": "blocked", "message": "Install command is not in BioNodulo's allow-list."})
            continue
        try:
            process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=_install_environment(command))
        except FileNotFoundError:
            results.append({"target": plan.get("target"), "status": "blocked", "message": f"Installer executable not found: {command[0]}"})
            continue
        stdout, stderr = await process.communicate()
        results.append(
            {
                "target": plan.get("target"),
                "status": "completed" if process.returncode == 0 else "failed",
                "returncode": process.returncode,
                "stdout": stdout.decode("utf-8", errors="replace")[-4000:],
                "stderr": stderr.decode("utf-8", errors="replace")[-4000:],
            }
        )
    return {"ok": all(result["status"] in {"completed", "skipped"} for result in results), "results": results}


@router.get("/examples/workflows/fastq_qc_pipeline.bionodulo.json")
async def sample_workflow() -> JSONResponse:
    path = Path("examples/workflows/fastq_qc_pipeline.bionodulo.json")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Sample workflow missing")
    return JSONResponse(content=__import__("json").loads(path.read_text(encoding="utf-8")))


def _read_optional(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _allowed_install_command(command: list[str]) -> bool:
    if not command:
        return False
    executable = Path(command[0]).name.lower()
    if executable.endswith(".exe"):
        executable = executable.removesuffix(".exe")
    allowed = {"conda", "mamba", "micromamba", "docker", "apptainer", "singularity"}
    if executable in allowed:
        return True
    if executable == "winget":
        return command[:5] == ["winget", "install", "-e", "--id"] and command[5:] == ["Docker.DockerDesktop"]
    if executable == "brew":
        return command in (["brew", "install", "--cask", "docker"], ["brew", "install", "apptainer"])
    if executable == "sudo":
        return command in (["sudo", "apt-get", "install", "-y", "docker.io"], ["sudo", "apt-get", "install", "-y", "apptainer"])
    return False


def _resolved_install_command(command: list[str]) -> list[str]:
    if not command:
        return command
    executable = Path(command[0]).name.lower()
    if executable.endswith(".exe"):
        executable = executable.removesuffix(".exe")
    if executable in {"conda", "mamba", "micromamba"} and managed_micromamba_path().exists():
        return [str(managed_micromamba_path()), *command[1:]]
    return command


def _install_environment(command: list[str]) -> dict[str, str]:
    env = os.environ.copy()
    if command and Path(command[0]).resolve() == managed_micromamba_path().resolve():
        managed_micromamba_root().mkdir(parents=True, exist_ok=True)
        env.setdefault("MAMBA_ROOT_PREFIX", str(managed_micromamba_root()))
    return env


def _available_destination(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    for index in range(1, 10_000):
        candidate = parent / f"{stem} copy {index}{suffix}"
        if not candidate.exists():
            return candidate
    raise HTTPException(status_code=409, detail=f"Could not find a free destination name for {path.name}")


def _json_line(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False) + "\n"


def _stream_chunks(text: str) -> list[str]:
    words = text.split(" ")
    if len(words) <= 1:
        return [text]
    return [f"{word} " for word in words[:-1]] + [words[-1]]


def _file_entry(path: Path, *, root: Path, max_depth: int, show_hidden: bool) -> dict:
    relative = "." if path == root else str(path.relative_to(root)).replace("\\", "/")
    item = {
        "name": "." if path == root else path.name,
        "path": relative,
        "absolute_path": str(path.resolve()),
        "type": "directory" if path.is_dir() else "file",
    }
    if path.is_file():
        stat = path.stat()
        item["size"] = stat.st_size
        item["modified"] = stat.st_mtime
        return item
    if max_depth <= 0:
        item["children"] = []
        return item
    ignored = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache"}
    children = []
    for child in sorted(path.iterdir(), key=lambda value: (value.is_file(), value.name.lower())):
        if child.name in ignored:
            continue
        if not show_hidden and child.name.startswith("."):
            continue
        children.append(_file_entry(child, root=root, max_depth=max_depth - 1, show_hidden=show_hidden))
    item["children"] = children[:200]
    return item
