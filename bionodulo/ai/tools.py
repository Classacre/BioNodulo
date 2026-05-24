"""Tool registry and executor for the BioNodulo AI assistant."""
from __future__ import annotations

import copy
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


class ToolContext:
    """Request-scoped application state available to AI tools."""

    def __init__(
        self,
        workflow: dict[str, Any] | None = None,
        workflow_id: str | None = None,
        registry: Any = None,
        settings: Any = None,
        settings_manager: Any = None,
    ):
        self.workflow = _normalize_workflow(workflow or {}, workflow_id)
        self.workflow_id = self.workflow.get("id") or workflow_id
        self.registry = registry
        self.settings = settings
        self.settings_manager = settings_manager


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
To call a tool, output exactly:
<tool_call name="TOOL_NAME">
{"param1": "value1", "param2": "value2"}
</tool_call>

Show your reasoning inside <thinking> tags before each tool call.

When you want to propose changes to the workflow, output:
<propose_changes>
{"description": "human-readable summary", "workflow": {...full workflow JSON...}}
</propose_changes>

For mutating tools, the user must confirm before changes are applied.
"""
    )
    return "\n".join(lines)


def _new_id(prefix: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in prefix).strip("_")
    return f"{cleaned or 'id'}_{uuid.uuid4().hex[:8]}"


def _normalize_workflow(workflow: dict[str, Any], workflow_id: str | None = None) -> dict[str, Any]:
    wf = copy.deepcopy(workflow)
    wf.setdefault("version", "Alpha 1.5")
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


def _get_run_history(ctx: ToolContext, **kwargs: Any) -> dict[str, Any]:
    return {
        "runs": [],
        "note": "Run history is request-context dependent. Open the console/history panel for live local run records.",
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
    ToolDefinition("get_run_history", "Summarize locally available run history context.", [], _get_run_history),
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
    """Execute a tool by name with the given arguments."""
    tool = get_tool(name)
    if not tool:
        return {"status": "error", "error": f"Tool '{name}' not found"}
    try:
        result = tool.execute(ctx, **arguments)
        if isinstance(result, dict) and "error" in result:
            return {"status": "error", "error": result["error"], "result": result}
        return {"status": "ok", "result": result, "mutates": tool.mutates}
    except Exception as exc:
        logger.exception("Tool execution failed: %s", name)
        return {"status": "error", "error": str(exc)}
