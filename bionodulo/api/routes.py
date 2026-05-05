from __future__ import annotations

from pathlib import Path
import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from bionodulo.ai import chat_with_assistant
from bionodulo.api.schemas import AIChatRequest, PromptCompatibilityRequest, RunCreateRequest, ValidationRequest
from bionodulo.core.paths import ensure_within
from bionodulo.manager import diagnose_workflow, environment_status
from bionodulo.manager.diagnostics import environment_install_plan
from bionodulo.workflow.schema import Workflow
from bionodulo.workflow.validation import validate_workflow

router = APIRouter()


class ManagerInstallRequest(BaseModel):
    workflow: Workflow
    targets: list[str] | None = None


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
    record = await run_queue.submit(payload.workflow, mock_tools=payload.mock_tools, force=payload.force, force_nodes=payload.force_nodes)
    return record.as_dict()


@router.post("/prompt")
async def prompt_compat(payload: PromptCompatibilityRequest, request: Request) -> dict:
    workflow = payload.prompt if isinstance(payload.prompt, Workflow) else Workflow.model_validate(payload.prompt)
    run_queue = request.app.state.run_queue
    record = await run_queue.submit(workflow, mock_tools=payload.mock_tools, force=payload.force)
    return {"prompt_id": record.run_id, "number": request.app.state.run_queue.queue_state()["queue_remaining"], "run": record.as_dict()}


@router.get("/runs")
async def list_runs(request: Request) -> list[dict]:
    return request.app.state.run_queue.list_runs()


@router.get("/runs/{run_id}")
async def get_run(run_id: str, request: Request) -> dict:
    record = request.app.state.run_queue.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}")
    return record.as_dict()


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


@router.get("/manager/status")
async def manager_status(request: Request) -> dict:
    return environment_status(request.app.state.node_registry, custom_nodes_dir=request.app.state.settings.custom_nodes_dir)


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
        command = plan.get("command") or []
        if not command:
            results.append({"target": plan.get("target"), "status": "skipped", "message": plan.get("command_hint", "No executable install command available yet.")})
            continue
        if not _allowed_install_command(command):
            results.append({"target": plan.get("target"), "status": "blocked", "message": "Install command is not in BioNodulo's allow-list."})
            continue
        process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
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
    allowed = {"conda", "mamba", "micromamba", "docker", "apptainer", "singularity"}
    return executable in allowed or executable.endswith(".exe") and executable.removesuffix(".exe") in allowed


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
