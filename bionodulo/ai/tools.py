"""Tool registry and executor for the BioNodulo AI assistant."""
from __future__ import annotations

import copy
import inspect
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = REPO_ROOT / "templates"


@dataclass
class ToolParameter:
    """Schema for a single tool parameter."""

    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None


@dataclass
class ToolDefinition:
    """Definition of a tool available to the AI."""

    name: str
    description: str
    parameters: list[ToolParameter]
    execute: Callable[..., Any] = field(repr=False)
    mutates: bool = False
    # An ``action`` tool has real side effects (runs a workflow, installs a
    # dependency, writes a file) but does not produce a draft graph edit for
    # confirmation. The autonomous agent loop may invoke these directly.
    action: bool = False


class ToolContext:
    """Request-scoped application state available to AI tools."""

    def __init__(
        self,
        workflow: dict[str, Any] | None = None,
        workflow_id: str | None = None,
        registry: Any = None,
        settings: Any = None,
        settings_manager: Any = None,
        run_queue: Any = None,
    ):
        self.workflow = _normalize_workflow(workflow or {}, workflow_id)
        self.workflow_id = self.workflow.get("id") or workflow_id
        self.registry = registry
        self.settings = settings
        self.settings_manager = settings_manager
        self.run_queue = run_queue

    @property
    def executor(self) -> Any:
        """The workflow executor backing this context, if any (unwrapped)."""
        queue_executor = getattr(self.run_queue, "executor", None)
        if queue_executor is None:
            return None
        # The queue may hold an ArqWorkflowExecutor wrapping the real executor.
        return getattr(queue_executor, "executor", queue_executor)

    @property
    def runs_dir(self) -> Path:
        executor = self.executor
        workspace = getattr(executor, "workspace_dir", None)
        if workspace is not None:
            return Path(workspace) / "runs"
        project_root = getattr(self.settings, "project_root", None)
        return (Path(project_root) if project_root else REPO_ROOT) / "runs"


def _param_schema(params: list[ToolParameter]) -> str:
    lines = []
    for p in params:
        req = "required" if p.required else f"optional (default: {p.default!r})"
        lines.append(f'    "{p.name}": <{p.type}>  # {p.description} ({req})')
    return "\n".join(lines) if lines else "    (no parameters)"


def format_tools_for_prompt(tools: list[ToolDefinition]) -> str:
    """Format tool definitions for inclusion in a system prompt."""
    lines = ["You have access to the following tools:", ""]
    for t in tools:
        mut = " [MUTATING - requires user confirmation]" if t.mutates else ""
        lines.append(f"### {t.name}{mut}")
        lines.append(t.description)
        lines.append("Parameters:")
        lines.append(_param_schema(t.parameters))
        lines.append("")
    lines.append(
        """
Use the model provider's native function calling interface to call tools.
For mutating tools, the user must confirm before changes are applied.
"""
    )
    return "\n".join(lines)


def _json_schema_type(type_name: str) -> dict[str, Any]:
    normalized = type_name.lower()
    if normalized in {"int", "integer"}:
        return {"type": "integer"}
    if normalized in {"float", "number"}:
        return {"type": "number"}
    if normalized in {"bool", "boolean"}:
        return {"type": "boolean"}
    if normalized in {"array", "list"}:
        return {"type": "array", "items": {}}
    if normalized in {"object", "dict", "json"}:
        return {"type": "object"}
    return {"type": "string"}


def tools_to_openai_schema(tools: list[ToolDefinition]) -> list[dict[str, Any]]:
    """Return LiteLLM/OpenAI-compatible function-calling schemas."""
    schemas: list[dict[str, Any]] = []
    for tool in tools:
        properties: dict[str, Any] = {}
        required: list[str] = []
        for param in tool.parameters:
            schema = _json_schema_type(param.type)
            schema["description"] = param.description
            if param.default is not None:
                schema["default"] = param.default
            properties[param.name] = schema
            if param.required:
                required.append(param.name)
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                        "additionalProperties": False,
                    },
                },
            }
        )
    return schemas


def _new_id(prefix: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in prefix).strip("_")
    return f"{cleaned or 'id'}_{uuid.uuid4().hex[:8]}"


def _normalize_workflow(workflow: dict[str, Any], workflow_id: str | None = None) -> dict[str, Any]:
    wf = copy.deepcopy(workflow)
    wf.setdefault("version", "2.0")
    wf.setdefault("app", "bionodulo")
    wf.setdefault("name", "Untitled")
    wf.setdefault("description", "")
    wf["id"] = wf.get("id") or workflow_id or _new_id("wf")
    if not isinstance(wf.get("nodes"), list):
        nodes = wf.get("nodes")
        wf["nodes"] = list(nodes.values()) if isinstance(nodes, dict) else []
    if not isinstance(wf.get("edges"), list):
        wf["edges"] = []
    if not isinstance(wf.get("groups"), list):
        wf["groups"] = []
    if not isinstance(wf.get("outputs"), dict):
        wf["outputs"] = {}
    return wf


def _object_info(ctx: ToolContext, node_type: str | None = None) -> Any:
    registry = ctx.registry
    if not registry or not hasattr(registry, "object_info"):
        return {} if node_type is None else None
    try:
        if node_type is None:
            return registry.object_info()
        return registry.object_info(node_type)
    except TypeError:
        info = registry.object_info()
        return info if node_type is None else info.get(node_type)


def _node_defaults(meta: dict[str, Any] | None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if not meta:
        return params
    inputs = meta.get("input_types") or {}
    for section in ("required", "optional"):
        for name, spec in (inputs.get(section) or {}).items():
            if isinstance(spec, dict) and "default" in spec:
                params[name] = spec["default"]
    return params


def _node_slot_names(meta: dict[str, Any] | None, direction: str) -> list[str]:
    if not meta:
        return []
    if direction == "input":
        inputs = meta.get("input_types") or {}
        return list((inputs.get("required") or {}).keys()) + list((inputs.get("optional") or {}).keys())
    names = meta.get("return_names") or []
    if names:
        return list(names)
    return [f"output_{idx}" for idx, _ in enumerate(meta.get("return_types") or [])]


def _find_node(workflow: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    return next((node for node in workflow.get("nodes", []) if node.get("id") == node_id), None)


def _settings_dict(ctx: ToolContext) -> dict[str, Any]:
    if ctx.settings_manager and hasattr(ctx.settings_manager, "get_all"):
        try:
            return dict(ctx.settings_manager.get_all())
        except Exception:
            pass
    if ctx.settings:
        try:
            return {k: v for k, v in vars(ctx.settings).items() if not k.startswith("_")}
        except Exception:
            pass
    return {}


def _workspace_root(ctx: ToolContext) -> Path:
    settings = ctx.settings
    project_root = getattr(settings, "project_root", None)
    return Path(project_root) if project_root else REPO_ROOT


def _template_files() -> list[Path]:
    if not TEMPLATES_DIR.exists():
        return []
    return sorted(TEMPLATES_DIR.glob("*.json"), key=lambda p: p.name.lower())


def _load_template_file(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("workflow"), dict):
        data = data["workflow"]
    if not isinstance(data, dict):
        raise ValueError(f"Template {path.name} does not contain a workflow object")
    return _normalize_workflow(data)


def _get_current_workflow(ctx: ToolContext, **kwargs: Any) -> dict[str, Any]:
    return {"workflow": ctx.workflow}


def _get_workflow_summary(ctx: ToolContext, **kwargs: Any) -> dict[str, Any]:
    """Compact summary of the active workflow.

    Returned in place of the full JSON when the assistant only needs to know
    *what* is on the canvas, not every parameter. Roughly 10-50x smaller than
    `get_current_workflow` on a realistic graph; preferable as a first call.
    """
    wf = ctx.workflow or {}
    nodes = wf.get("nodes") or []
    edges = wf.get("edges") or []
    node_types: dict[str, int] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        t = str(node.get("type") or "unknown")
        node_types[t] = node_types.get(t, 0) + 1
    node_list = [
        {
            "id": n.get("id"),
            "type": n.get("type"),
            "title": (n.get("ui") or {}).get("title") if isinstance(n.get("ui"), dict) else None,
        }
        for n in nodes
        if isinstance(n, dict)
    ]
    return {
        "name": wf.get("name", "Untitled"),
        "description": wf.get("description", ""),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "group_count": len(wf.get("groups") or []),
        "node_type_counts": node_types,
        "nodes": node_list,
    }


def _explain_last_failure(ctx: ToolContext, **kwargs: Any) -> dict[str, Any]:
    """Return diagnostic info from the most recent failed run.

    Reads `RunQueue.history()` when available and extracts the first failing
    node's error message + the tail of the run log. Saves the assistant from
    chasing the user for screenshots when something blew up.
    """
    queue = getattr(ctx.settings, "_run_queue", None)
    if queue is None:
        return {"error": "No run history available in this request context."}
    try:
        history = list(queue.history())
    except Exception as exc:
        return {"error": f"Could not read run history: {exc}"}
    failed = next((r for r in history if r.get("status") in ("error", "failed", "cancelled")), None)
    if failed is None:
        return {"status": "ok", "message": "No failed runs in history."}
    result = failed.get("result") or {}
    error_message = result.get("error") or failed.get("error") or ""
    failing_node = None
    for node_id, node_result in (result.get("node_results") or {}).items():
        if isinstance(node_result, dict) and node_result.get("status") in ("error", "failed"):
            failing_node = {
                "id": node_id,
                "error": node_result.get("error", ""),
                "command": node_result.get("command", ""),
            }
            break
    log_tail = (result.get("logs") or [])[-50:]
    return {
        "run_id": failed.get("run_id"),
        "workflow_name": failed.get("name"),
        "status": failed.get("status"),
        "error": str(error_message)[:1000],
        "failing_node": failing_node,
        "log_tail": log_tail,
    }


def _list_available_nodes(ctx: ToolContext, category: str | None = None, **kwargs: Any) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    info = _object_info(ctx)
    category_query = category.lower() if isinstance(category, str) and category else None
    for node_id, meta in (info or {}).items():
        meta = meta or {}
        node_category = str(meta.get("category", "Unknown"))
        if category_query and category_query not in node_category.lower():
            continue
        nodes.append(
            {
                "id": node_id,
                "display_name": meta.get("display_name", node_id),
                "category": node_category,
                "description": meta.get("description", ""),
                "inputs": _node_slot_names(meta, "input"),
                "outputs": _node_slot_names(meta, "output"),
                "return_types": meta.get("return_types", []),
                "requires_tools": meta.get("requires_external_tools", []),
                "hidden": bool(meta.get("hidden", False)),
                "visual_only": bool(meta.get("visual_only", False)),
            }
        )
    return {"nodes": nodes, "count": len(nodes)}


def _get_node_info(ctx: ToolContext, node_type: str, **kwargs: Any) -> dict[str, Any]:
    meta = _object_info(ctx, node_type)
    if not meta:
        return {"error": f"Node type '{node_type}' not found"}
    return {
        "id": node_type,
        "display_name": meta.get("display_name", node_type),
        "category": meta.get("category", "Unknown"),
        "description": meta.get("description", ""),
        "inputs": meta.get("input_types", {}),
        "input_names": _node_slot_names(meta, "input"),
        "outputs": _node_slot_names(meta, "output"),
        "return_types": meta.get("return_types", []),
        "return_names": meta.get("return_names", []),
        "required_tools": meta.get("requires_external_tools", []),
        "required_python_packages": meta.get("requires_python_packages", []),
        "required_r_packages": meta.get("requires_r_packages", []),
        "environment": meta.get("environment"),
        "output_node": bool(meta.get("output_node", False)),
        "hidden": bool(meta.get("hidden", False)),
        "visual_only": bool(meta.get("visual_only", False)),
    }


def _get_dependency_report(ctx: ToolContext, **kwargs: Any) -> dict[str, Any]:
    from bionodulo.manager.resolver import resolve_workflow

    if not ctx.registry:
        return {"error": "Node registry not available"}
    report = resolve_workflow(ctx.workflow, ctx.registry)
    return report.to_dict()


def _validate_workflow(ctx: ToolContext, **kwargs: Any) -> dict[str, Any]:
    from bionodulo.workflow.validation import validate_workflow

    result = validate_workflow(ctx.workflow, ctx.registry)
    return {
        "valid": result.valid,
        "errors": result.errors,
        "warnings": result.warnings,
        "sorted_node_order": result.sorted_node_order,
    }


def _add_node(
    ctx: ToolContext,
    node_type: str,
    position: list[float] | None = None,
    params: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    wf = _normalize_workflow(ctx.workflow, ctx.workflow_id)
    meta = _object_info(ctx, node_type)
    if not meta:
        return {"error": f"Node type '{node_type}' not found"}
    nodes = wf["nodes"]
    pos = position or [200 + len(nodes) * 30, 200 + len(nodes) * 20]
    node_params = _node_defaults(meta)
    if params:
        node_params.update(params)
    new_node = {
        "id": _new_id(node_type),
        "type": node_type,
        "position": pos,
        "params": node_params,
        "node_info": meta,
        "ui": {
            "title": meta.get("display_name", node_type),
        },
    }
    nodes.append(new_node)
    ctx.workflow = wf
    return {"workflow": wf, "added_node": new_node}


def _update_node(
    ctx: ToolContext,
    node_id: str,
    params: dict[str, Any] | None = None,
    position: list[float] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    wf = _normalize_workflow(ctx.workflow, ctx.workflow_id)
    node = _find_node(wf, node_id)
    if not node:
        return {"error": f"Node '{node_id}' not found"}
    if params:
        node.setdefault("params", {}).update(params)
    if position:
        node["position"] = position
    ctx.workflow = wf
    return {"workflow": wf, "updated_node": node}


def _remove_node(ctx: ToolContext, node_id: str, **kwargs: Any) -> dict[str, Any]:
    wf = _normalize_workflow(ctx.workflow, ctx.workflow_id)
    if not _find_node(wf, node_id):
        return {"error": f"Node '{node_id}' not found"}
    wf["nodes"] = [node for node in wf["nodes"] if node.get("id") != node_id]
    wf["edges"] = [
        edge for edge in wf["edges"]
        if edge.get("from", {}).get("node") != node_id and edge.get("to", {}).get("node") != node_id
    ]
    ctx.workflow = wf
    return {"workflow": wf, "removed_node": node_id}


def _add_edge(ctx: ToolContext, from_node: str, from_output: str, to_node: str, to_input: str, **kwargs: Any) -> dict[str, Any]:
    wf = _normalize_workflow(ctx.workflow, ctx.workflow_id)
    source = _find_node(wf, from_node)
    target = _find_node(wf, to_node)
    if not source:
        return {"error": f"Source node '{from_node}' not found"}
    if not target:
        return {"error": f"Target node '{to_node}' not found"}

    source_meta = _object_info(ctx, source.get("type"))
    target_meta = _object_info(ctx, target.get("type"))
    source_outputs = _node_slot_names(source_meta, "output")
    target_inputs = _node_slot_names(target_meta, "input")
    if source_outputs and from_output not in source_outputs:
        return {"error": f"Output '{from_output}' is not valid for node '{from_node}'. Valid outputs: {source_outputs}"}
    if target_inputs and to_input not in target_inputs:
        return {"error": f"Input '{to_input}' is not valid for node '{to_node}'. Valid inputs: {target_inputs}"}

    for edge in wf["edges"]:
        if edge.get("to", {}).get("node") == to_node and edge.get("to", {}).get("input") == to_input:
            return {"error": f"Input '{to_input}' on node '{to_node}' is already connected"}
        if (
            edge.get("from", {}).get("node") == from_node
            and edge.get("from", {}).get("output") == from_output
            and edge.get("to", {}).get("node") == to_node
            and edge.get("to", {}).get("input") == to_input
        ):
            return {"error": "That edge already exists"}

    new_edge = {
        "id": _new_id("edge"),
        "from": {"node": from_node, "output": from_output},
        "to": {"node": to_node, "input": to_input},
    }
    wf["edges"].append(new_edge)
    ctx.workflow = wf
    return {"workflow": wf, "added_edge": new_edge}


def _remove_edge(ctx: ToolContext, edge_id: str, **kwargs: Any) -> dict[str, Any]:
    wf = _normalize_workflow(ctx.workflow, ctx.workflow_id)
    before = len(wf["edges"])
    wf["edges"] = [edge for edge in wf["edges"] if edge.get("id") != edge_id]
    if len(wf["edges"]) == before:
        return {"error": f"Edge '{edge_id}' not found"}
    ctx.workflow = wf
    return {"workflow": wf, "removed_edge": edge_id}


def _list_workflow_templates(ctx: ToolContext, **kwargs: Any) -> dict[str, Any]:
    templates: list[dict[str, Any]] = []
    for path in _template_files():
        try:
            workflow = _load_template_file(path)
            templates.append(
                {
                    "name": path.stem,
                    "filename": path.name,
                    "display_name": workflow.get("name") or path.stem.replace("_", " ").title(),
                    "description": workflow.get("description", ""),
                    "nodes": len(workflow.get("nodes", [])),
                    "edges": len(workflow.get("edges", [])),
                }
            )
        except Exception as exc:
            templates.append({"name": path.stem, "filename": path.name, "error": str(exc)})
    return {"templates": templates, "count": len(templates)}


def _load_template(ctx: ToolContext, template_name: str, **kwargs: Any) -> dict[str, Any]:
    candidates = [template_name]
    if not template_name.endswith(".json"):
        candidates.extend([f"{template_name}.json", f"{template_name}_pipeline.json"])
    for path in _template_files():
        if path.name in candidates or path.stem in candidates:
            workflow = _load_template_file(path)
            workflow["id"] = ctx.workflow_id or workflow.get("id") or _new_id("wf")
            ctx.workflow = workflow
            return {"workflow": workflow, "template": path.stem}
    available = [path.stem for path in _template_files()]
    return {"error": f"Template '{template_name}' not found", "available": available}


def _set_workflow_name(ctx: ToolContext, name: str, **kwargs: Any) -> dict[str, Any]:
    wf = _normalize_workflow(ctx.workflow, ctx.workflow_id)
    wf["name"] = name
    ctx.workflow = wf
    return {"workflow": wf}


def _set_workflow_description(ctx: ToolContext, description: str, **kwargs: Any) -> dict[str, Any]:
    wf = _normalize_workflow(ctx.workflow, ctx.workflow_id)
    wf["description"] = description
    ctx.workflow = wf
    return {"workflow": wf}


def _resolve_dependencies(ctx: ToolContext, **kwargs: Any) -> dict[str, Any]:
    return _get_dependency_report(ctx)


def _get_settings(ctx: ToolContext, **kwargs: Any) -> dict[str, Any]:
    return {"settings": _settings_dict(ctx)}


def _update_setting(ctx: ToolContext, key: str, value: Any, **kwargs: Any) -> dict[str, Any]:
    return {
        "setting_key": key,
        "setting_value": value,
        "note": "Settings changes require user confirmation and should be made through the Settings panel.",
    }


def _list_environments(ctx: ToolContext, **kwargs: Any) -> dict[str, Any]:
    from bionodulo.environments.manifest import list_all_envs

    return {"environments": list_all_envs(_workspace_root(ctx))}


def _ensure_workflow_environment(ctx: ToolContext, **kwargs: Any) -> dict[str, Any]:
    return {
        "success": False,
        "message": (
            "Environment creation is handled by the app's dependency resolver and "
            "/api/manager/ensure-workflow-env so the user can review the install plan first."
        ),
    }


def _get_system_stats(ctx: ToolContext, **kwargs: Any) -> dict[str, Any]:
    try:
        import psutil
    except Exception as exc:
        return {"error": f"psutil is unavailable: {exc}"}

    vm = psutil.virtual_memory()
    disk = psutil.disk_usage(str(_workspace_root(ctx)))
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "cpu_count": os.cpu_count(),
        "memory": {
            "total": vm.total,
            "available": vm.available,
            "percent": vm.percent,
        },
        "disk": {
            "total": disk.total,
            "free": disk.free,
            "percent": disk.percent,
        },
    }


def _get_run_history(ctx: ToolContext, limit: int | None = 10, **kwargs: Any) -> dict[str, Any]:
    """Recent run records (most recent first) from the live run queue."""
    queue = ctx.run_queue
    if queue is None or not hasattr(queue, "list_history"):
        return {"runs": [], "note": "No run queue is available in this context."}
    try:
        history = list(queue.list_history())
    except Exception as exc:  # pragma: no cover - defensive
        return {"error": f"Could not read run history: {exc}"}
    try:
        count = int(limit) if limit is not None else 10
    except (TypeError, ValueError):
        count = 10
    runs = [
        {
            "run_id": r.get("run_id"),
            "name": r.get("name"),
            "status": r.get("status"),
        }
        for r in history[: max(1, count)]
    ]
    return {"runs": runs, "count": len(runs)}


async def _run_workflow(
    ctx: ToolContext,
    force: bool | None = False,
    target_nodes: list[str] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Execute the current workflow and return a status summary.

    Runs synchronously through the workflow executor and waits for completion,
    so the assistant can inspect per-node results and drive a debug loop.
    """
    executor = ctx.executor
    if executor is None or not hasattr(executor, "execute"):
        return {"error": "No execution backend is available in this context."}
    from bionodulo.workflow.validation import validate_workflow

    validation = validate_workflow(ctx.workflow, ctx.registry)
    if not validation.valid:
        return {
            "error": "Workflow is invalid; fix these before running.",
            "validation_errors": validation.errors,
        }
    run_id = _new_id("airun")
    options: dict[str, Any] = {}
    if target_nodes:
        options["target_nodes"] = list(target_nodes)
    try:
        result = await executor.execute(
            run_id=run_id,
            workflow=ctx.workflow,
            options=options,
            force=bool(force),
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("AI run_workflow failed")
        return {"run_id": run_id, "status": "failed", "error": str(exc)}
    node_results = result.get("node_results", {}) if isinstance(result, dict) else {}
    node_statuses = {nid: nr.get("status") for nid, nr in node_results.items() if isinstance(nr, dict)}
    failed_nodes = {
        nid: str(nr.get("error", ""))[:500]
        for nid, nr in node_results.items()
        if isinstance(nr, dict) and nr.get("status") in ("failed", "error")
    }
    return {
        "run_id": run_id,
        "status": result.get("status") if isinstance(result, dict) else "unknown",
        "node_statuses": node_statuses,
        "failed_nodes": failed_nodes,
        "error": result.get("error") if isinstance(result, dict) else None,
    }


def _get_run_status(ctx: ToolContext, run_id: str, **kwargs: Any) -> dict[str, Any]:
    """Status and per-node results for a run id."""
    queue = ctx.run_queue
    if queue is None or not hasattr(queue, "get_run"):
        return {"error": "No run queue is available in this context."}
    record = queue.get_run(run_id)
    if not record:
        return {"error": f"Run '{run_id}' not found."}
    return record


def _read_run_logs(
    ctx: ToolContext,
    run_id: str,
    node_id: str | None = None,
    tail: int | None = 100,
    **kwargs: Any,
) -> dict[str, Any]:
    """Read stdout/stderr logs for a run (optionally a single node).

    Returns the last ``tail`` non-empty lines so the assistant can diagnose a
    failure without flooding its context.
    """
    run_dir = ctx.runs_dir / run_id
    if not run_dir.is_dir():
        return {"error": f"Run directory not found for '{run_id}'."}
    try:
        line_cap = int(tail) if tail is not None else 100
    except (TypeError, ValueError):
        line_cap = 100
    line_cap = max(1, min(line_cap, 2000))

    lines: list[str] = []
    node_dirs = [run_dir / node_id] if node_id else sorted(p for p in run_dir.iterdir() if p.is_dir())
    for node_dir in node_dirs:
        if not node_dir.is_dir():
            continue
        for stream in ("stdout", "stderr"):
            log_path = node_dir / f"{stream}.log"
            if not log_path.is_file():
                continue
            try:
                content = log_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line in content.splitlines():
                if line.strip():
                    lines.append(f"[{node_dir.name}/{stream}] {line}")
    return {"run_id": run_id, "node_id": node_id, "log_tail": lines[-line_cap:]}


async def _retry_run(ctx: ToolContext, run_id: str, **kwargs: Any) -> dict[str, Any]:
    """Re-submit a previous run to the queue."""
    queue = ctx.run_queue
    if queue is None or not hasattr(queue, "retry"):
        return {"error": "No run queue is available in this context."}
    try:
        new_run_id = await queue.retry(run_id)
    except Exception as exc:
        return {"error": f"Retry failed: {exc}"}
    return {"retried_from": run_id, "run_id": new_run_id}


async def _search_literature(
    ctx: ToolContext,
    query: str,
    max_results: int | None = 5,
    **kwargs: Any,
) -> dict[str, Any]:
    """Search PubMed (NCBI E-utilities) for papers matching a query.

    Keyless. Used by the optimize/reproduce flows to ground method choices in
    the literature. Returns title, authors, journal, year, PMID, and DOI.
    """
    import httpx

    try:
        count = max(1, min(int(max_results) if max_results is not None else 5, 20))
    except (TypeError, ValueError):
        count = 5
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    params_search = {"db": "pubmed", "term": query, "retmax": count, "retmode": "json"}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            search = await client.get(f"{base}/esearch.fcgi", params=params_search)
            search.raise_for_status()
            ids = (search.json().get("esearchresult", {}) or {}).get("idlist", []) or []
            if not ids:
                return {"query": query, "results": [], "count": 0}
            summary = await client.get(
                f"{base}/esummary.fcgi",
                params={"db": "pubmed", "id": ",".join(ids), "retmode": "json"},
            )
            summary.raise_for_status()
            payload = summary.json().get("result", {}) or {}
    except Exception as exc:
        return {"error": f"Literature search failed: {exc}", "query": query}

    results = []
    for pmid in ids:
        entry = payload.get(pmid) or {}
        doi = ""
        for article_id in entry.get("articleids", []) or []:
            if article_id.get("idtype") == "doi":
                doi = article_id.get("value", "")
                break
        results.append(
            {
                "pmid": pmid,
                "title": entry.get("title", ""),
                "authors": [a.get("name", "") for a in (entry.get("authors") or [])][:6],
                "journal": entry.get("fulljournalname") or entry.get("source", ""),
                "year": (entry.get("pubdate", "") or "")[:4],
                "doi": doi,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            }
        )
    return {"query": query, "results": results, "count": len(results)}


def _write_custom_node(
    ctx: ToolContext,
    name: str,
    code: str,
    requirements: list[str] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Write a Python custom-node module into the custom_nodes directory.

    The module is imported on the next registry reload. ``requirements`` lists
    conda/pip packages the node needs; they are recorded next to the module so
    the dependency resolver can install them. Returns the written path.
    """
    if not name or not code:
        return {"error": "Both 'name' and 'code' are required."}
    settings = ctx.settings
    custom_dir = getattr(settings, "custom_nodes_dir", None)
    project_root = getattr(settings, "project_root", None)
    if custom_dir is not None:
        base = Path(custom_dir)
        if not base.is_absolute() and project_root is not None:
            base = Path(project_root) / base
    else:
        base = (Path(project_root) if project_root else REPO_ROOT) / "custom_nodes"
    base.mkdir(parents=True, exist_ok=True)

    safe_stem = "".join(ch if ch.isalnum() or ch in ("_",) else "_" for ch in Path(name).stem) or "custom_node"
    module_path = base / f"{safe_stem}.py"
    try:
        module_path.write_text(code, encoding="utf-8")
        written = [str(module_path)]
        if requirements:
            req_path = base / f"{safe_stem}.requirements.txt"
            req_path.write_text("\n".join(str(r) for r in requirements) + "\n", encoding="utf-8")
            written.append(str(req_path))
    except OSError as exc:
        return {"error": f"Could not write custom node: {exc}"}
    return {
        "success": True,
        "written": written,
        "note": "Reload the node manager (or restart) to register the new node.",
    }


def _read_workspace_file(ctx: ToolContext, path: str, max_bytes: int | None = 16000, **kwargs: Any) -> dict[str, Any]:
    """Read a UTF-8 text file from inside the workspace (bounded, traversal-safe)."""
    root = _workspace_root(ctx).resolve()
    try:
        target = (root / path).resolve()
        target.relative_to(root)
    except (ValueError, OSError):
        return {"error": "Path escapes the workspace root."}
    if not target.is_file():
        return {"error": f"File not found: {path}"}
    try:
        cap = max(256, min(int(max_bytes) if max_bytes is not None else 16000, 200_000))
    except (TypeError, ValueError):
        cap = 16000
    try:
        data = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"error": f"Could not read file: {exc}"}
    truncated = len(data) > cap
    return {"path": path, "content": data[:cap], "truncated": truncated}


async def _download_dataset(
    ctx: ToolContext,
    source: str,
    dest_name: str | None = None,
    max_mb: int | None = 2048,
    **kwargs: Any,
) -> dict[str, Any]:
    """Download a dataset into the workspace ``data`` directory.

    ``source`` is either a direct http(s) URL or an ENA/SRA-style run accession
    (e.g. SRR/ERR/DRR...), which is resolved to its FASTQ FTP links via the ENA
    portal. Returns the local path(s). Used by the paper-reproduction dataset
    sub-agent. Network egress is restricted to public hosts.
    """
    import httpx

    data_dir = _workspace_root(ctx).resolve() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    try:
        cap_bytes = max(1, int(max_mb) if max_mb is not None else 2048) * 1024 * 1024
    except (TypeError, ValueError):
        cap_bytes = 2048 * 1024 * 1024

    async def _download_url(url: str) -> dict[str, Any]:
        if not url.startswith(("http://", "https://", "ftp://")):
            return {"error": f"Unsupported URL scheme: {url}"}
        fetch_url = url.replace("ftp://", "https://", 1) if url.startswith("ftp://") else url
        from bionodulo.core.netguard import assert_safe_url

        try:
            assert_safe_url(fetch_url)  # SSRF guard
        except ValueError as exc:
            return {"error": str(exc)}
        name = dest_name or fetch_url.rstrip("/").split("/")[-1] or "download.dat"
        safe_name = "".join(ch if ch.isalnum() or ch in ("_", "-", ".") else "_" for ch in name)
        target = data_dir / safe_name
        written = 0
        try:
            async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                async with client.stream("GET", fetch_url) as resp:
                    resp.raise_for_status()
                    with open(target, "wb") as handle:
                        async for chunk in resp.aiter_bytes(1024 * 256):
                            written += len(chunk)
                            if written > cap_bytes:
                                handle.close()
                                target.unlink(missing_ok=True)
                                return {"error": f"Download exceeded {max_mb} MB cap."}
                            handle.write(chunk)
        except Exception as exc:
            return {"error": f"Download failed for {url}: {exc}"}
        return {"path": str(target), "bytes": written}

    accession = source.strip()
    if accession.startswith(("http://", "https://", "ftp://")):
        result = await _download_url(accession)
        if "error" in result:
            return {"source": source, **result}
        return {"source": source, "downloaded": [result]}

    # Treat as an ENA/SRA run accession: resolve fastq FTP links via ENA portal.
    if accession[:3].upper() in {"SRR", "ERR", "DRR", "SRX", "ERX", "DRX"}:
        portal = (
            "https://www.ebi.ac.uk/ena/portal/api/filereport"
            f"?accession={accession}&result=read_run&fields=fastq_ftp&format=tsv"
        )
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(portal)
                resp.raise_for_status()
                rows = [r for r in resp.text.splitlines() if r.strip()]
        except Exception as exc:
            return {"error": f"ENA lookup failed for {accession}: {exc}", "source": source}
        ftp_links: list[str] = []
        for row in rows[1:]:  # skip header
            cols = row.split("\t")
            if cols and cols[-1]:
                ftp_links.extend(part for part in cols[-1].split(";") if part)
        if not ftp_links:
            return {"error": f"No FASTQ files found for accession {accession}", "source": source}
        downloaded = []
        for link in ftp_links:
            url = link if link.startswith(("http", "ftp")) else f"https://{link}"
            res = await _download_url(url)
            downloaded.append(res)
        return {"source": source, "accession": accession, "downloaded": downloaded}

    return {
        "error": (
            f"Could not interpret '{source}' as a URL or ENA/SRA run accession. "
            "Provide a direct download URL or an SRR/ERR/DRR accession."
        ),
        "source": source,
    }


def _get_collaboration_status(ctx: ToolContext, **kwargs: Any) -> dict[str, Any]:
    settings = _settings_dict(ctx)
    enabled = bool(settings.get("bionodulo.collab.enabled", False))
    return {
        "enabled": enabled,
        "mode": "collaboration" if enabled else "local",
        "workflow_id": ctx.workflow_id,
    }


ALL_TOOLS: list[ToolDefinition] = [
    ToolDefinition("get_current_workflow", "Get the full JSON of the active workflow.", [], _get_current_workflow),
    ToolDefinition(
        "get_workflow_summary",
        "Get a compact summary of the workflow (node + edge counts, node types, ids/titles). Prefer this over get_current_workflow when you only need to know what's on the canvas, not full parameter values.",
        [],
        _get_workflow_summary,
    ),
    ToolDefinition(
        "explain_last_failure",
        "Summarize the most recent failed run: status, error message, first failing node, and a tail of the run log. Use when the user asks what went wrong or why a run failed.",
        [],
        _explain_last_failure,
    ),
    ToolDefinition(
        "list_available_nodes",
        "List available node types from the live node registry. Category matching is case-insensitive.",
        [ToolParameter("category", "string", "Optional category filter, e.g. RNA-Seq or Alignment", required=False, default=None)],
        _list_available_nodes,
    ),
    ToolDefinition(
        "get_node_info",
        "Get detailed node metadata including inputs, outputs, packages, hidden flags, and visual-only status.",
        [ToolParameter("node_type", "string", "Node type ID, e.g. fastqc or deseq2_analysis")],
        _get_node_info,
    ),
    ToolDefinition("validate_workflow", "Validate the current workflow graph.", [], _validate_workflow),
    ToolDefinition("get_dependency_report", "Resolve missing tools and packages for the current workflow.", [], _get_dependency_report),
    ToolDefinition("resolve_dependencies", "Alias for get_dependency_report.", [], _resolve_dependencies),
    ToolDefinition("list_environments", "List existing local workflow environments from the workspace envs directory.", [], _list_environments),
    ToolDefinition("list_workflow_templates", "List built-in local workflow templates available without collaboration.", [], _list_workflow_templates),
    ToolDefinition("get_settings", "Get current application settings.", [], _get_settings),
    ToolDefinition("get_system_stats", "Get CPU, memory, and disk stats for the local backend host.", [], _get_system_stats),
    ToolDefinition(
        "get_run_history",
        "List recent workflow runs (most recent first) with their status, from the live run queue.",
        [ToolParameter("limit", "integer", "Maximum number of runs to return", required=False, default=10)],
        _get_run_history,
    ),
    ToolDefinition(
        "run_workflow",
        "Execute the current workflow and wait for it to finish, returning the overall status and per-node statuses/errors. Use this to test a workflow or to drive an autonomous debug loop. Validates the graph first.",
        [
            ToolParameter("force", "boolean", "Ignore the cache and re-run every node", required=False, default=False),
            ToolParameter("target_nodes", "array", "Only run up to these node IDs (and their upstreams)", required=False, default=None),
        ],
        _run_workflow,
        action=True,
    ),
    ToolDefinition(
        "get_run_status",
        "Get the recorded status and per-node results for a specific run id.",
        [ToolParameter("run_id", "string", "Run identifier")],
        _get_run_status,
    ),
    ToolDefinition(
        "read_run_logs",
        "Read the stdout/stderr log tail for a run, optionally for a single node. Use after a failed run to diagnose the error.",
        [
            ToolParameter("run_id", "string", "Run identifier"),
            ToolParameter("node_id", "string", "Limit logs to this node", required=False, default=None),
            ToolParameter("tail", "integer", "Number of trailing log lines", required=False, default=100),
        ],
        _read_run_logs,
    ),
    ToolDefinition(
        "retry_run",
        "Re-submit a previous run to the execution queue.",
        [ToolParameter("run_id", "string", "Run identifier to retry")],
        _retry_run,
        action=True,
    ),
    ToolDefinition(
        "search_literature",
        "Search PubMed for papers matching a query (title, authors, journal, year, PMID, DOI). Use to research the best method for a task or to find a paper's referenced datasets/tools.",
        [
            ToolParameter("query", "string", "PubMed search query"),
            ToolParameter("max_results", "integer", "Maximum papers to return (<=20)", required=False, default=5),
        ],
        _search_literature,
    ),
    ToolDefinition(
        "write_custom_node",
        "Write a Python custom-node module into the custom_nodes directory so a tool not covered by the built-in nodes can be used. Provide the full module source and any conda/pip requirements.",
        [
            ToolParameter("name", "string", "Module/file name (without extension)"),
            ToolParameter("code", "string", "Full Python source for the custom node module"),
            ToolParameter("requirements", "array", "conda/pip packages the node needs", required=False, default=None),
        ],
        _write_custom_node,
        action=True,
    ),
    ToolDefinition(
        "read_workspace_file",
        "Read a UTF-8 text file from inside the workspace (bounded, path-traversal safe). Use to inspect input data or a run's output files.",
        [
            ToolParameter("path", "string", "Path relative to the workspace root"),
            ToolParameter("max_bytes", "integer", "Maximum bytes to return", required=False, default=16000),
        ],
        _read_workspace_file,
    ),
    ToolDefinition(
        "download_dataset",
        "Download a dataset into the workspace data directory from a direct URL or an ENA/SRA run accession (SRR/ERR/DRR...). Use to fetch a paper's referenced sequencing data.",
        [
            ToolParameter("source", "string", "A download URL or an ENA/SRA run accession"),
            ToolParameter("dest_name", "string", "Optional local filename", required=False, default=None),
            ToolParameter("max_mb", "integer", "Maximum download size in MB", required=False, default=2048),
        ],
        _download_dataset,
        action=True,
    ),
    ToolDefinition("get_collaboration_status", "Report whether the app is in local mode or collaboration mode.", [], _get_collaboration_status),
    ToolDefinition(
        "add_node",
        "Add a registry-backed node to the workflow with safe unique IDs and default parameters.",
        [
            ToolParameter("node_type", "string", "Node type ID"),
            ToolParameter("position", "array", "[x, y] canvas coordinates", required=False, default=None),
            ToolParameter("params", "object", "Parameter values to override", required=False, default=None),
        ],
        _add_node,
        mutates=True,
    ),
    ToolDefinition(
        "update_node",
        "Update an existing node's parameters or position.",
        [
            ToolParameter("node_id", "string", "ID of the node to update"),
            ToolParameter("params", "object", "Parameter values to update", required=False, default=None),
            ToolParameter("position", "array", "New [x, y] coordinates", required=False, default=None),
        ],
        _update_node,
        mutates=True,
    ),
    ToolDefinition("remove_node", "Remove a node and any connected edges.", [ToolParameter("node_id", "string", "Node ID")], _remove_node, mutates=True),
    ToolDefinition(
        "add_edge",
        "Connect one node output to one node input after validating node IDs and slot names.",
        [
            ToolParameter("from_node", "string", "Source node ID"),
            ToolParameter("from_output", "string", "Source output name"),
            ToolParameter("to_node", "string", "Target node ID"),
            ToolParameter("to_input", "string", "Target input name"),
        ],
        _add_edge,
        mutates=True,
    ),
    ToolDefinition("remove_edge", "Remove an edge by ID.", [ToolParameter("edge_id", "string", "Edge ID")], _remove_edge, mutates=True),
    ToolDefinition("load_template", "Load a built-in local workflow template by filename or stem.", [ToolParameter("template_name", "string", "Template filename or stem")], _load_template, mutates=True),
    ToolDefinition("set_workflow_name", "Set the workflow name.", [ToolParameter("name", "string", "New workflow name")], _set_workflow_name, mutates=True),
    ToolDefinition("set_workflow_description", "Set the workflow description.", [ToolParameter("description", "string", "New workflow description")], _set_workflow_description, mutates=True),
    ToolDefinition(
        "ensure_workflow_environment",
        "Explain how the app creates workflow-scoped environments through the resolver review flow.",
        [],
        _ensure_workflow_environment,
        mutates=False,
    ),
    ToolDefinition(
        "update_setting",
        "Draft a settings change for user confirmation rather than applying it silently.",
        [ToolParameter("key", "string", "Setting key"), ToolParameter("value", "any", "New value")],
        _update_setting,
        mutates=True,
    ),
]


def get_tool(name: str) -> ToolDefinition | None:
    """Get a tool by name."""
    for tool in ALL_TOOLS:
        if tool.name == name:
            return tool
    return None


def execute_tool(name: str, arguments: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    """Execute a synchronous tool by name with the given arguments.

    For async tools, prefer :func:`aexecute_tool`; calling this on an async tool
    returns an error rather than an un-awaited coroutine.
    """
    tool = get_tool(name)
    if not tool:
        return {"status": "error", "error": f"Tool '{name}' not found"}
    try:
        result = tool.execute(ctx, **arguments)
        if inspect.isawaitable(result):
            try:
                result.close()  # type: ignore[attr-defined]
            except Exception:
                pass
            return {"status": "error", "error": f"Tool '{name}' is async; use aexecute_tool"}
        if isinstance(result, dict) and result.get("error"):
            return {"status": "error", "error": result["error"], "result": result}
        return {"status": "ok", "result": result, "mutates": tool.mutates}
    except Exception as exc:
        logger.exception("Tool execution failed: %s", name)
        return {"status": "error", "error": str(exc)}


async def aexecute_tool(name: str, arguments: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    """Execute a tool by name, awaiting it when the tool is asynchronous."""
    tool = get_tool(name)
    if not tool:
        return {"status": "error", "error": f"Tool '{name}' not found"}
    try:
        result = tool.execute(ctx, **arguments)
        if inspect.isawaitable(result):
            result = await result
        if isinstance(result, dict) and result.get("error"):
            return {"status": "error", "error": result["error"], "result": result}
        return {"status": "ok", "result": result, "mutates": tool.mutates}
    except Exception as exc:
        logger.exception("Tool execution failed: %s", name)
        return {"status": "error", "error": str(exc)}
