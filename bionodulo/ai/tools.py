"""Tool registry and executor for BioNodulo AI Assistant.

Provides declarative tools that the AI can call to inspect and modify
workflows, environments, settings, and dependencies.
"""
from __future__ import annotations

import copy
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


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
    """Context passed to tool executions containing app state."""

    def __init__(
        self,
        workflow: dict[str, Any] | None = None,
        registry: Any = None,
        settings: Any = None,
    ):
        self.workflow = workflow or {}
        self.registry = registry
        self.settings = settings


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
        mut = " [MUTATING — requires user confirmation]" if t.mutates else ""
        lines.append(f"### {t.name}{mut}")
        lines.append(f"{t.description}")
        lines.append("Parameters:")
        lines.append(_param_schema(t.parameters))
        lines.append("")
    lines.append("""
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
""")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _get_current_workflow(ctx: ToolContext, **kwargs: Any) -> dict[str, Any]:
    """Return the current workflow JSON."""
    return {"workflow": ctx.workflow}


def _list_available_nodes(ctx: ToolContext, category: str | None = None, **kwargs: Any) -> dict[str, Any]:
    """List available node types."""
    nodes: list[dict[str, Any]] = []
    registry = ctx.registry
    if registry and hasattr(registry, "object_info"):
        info = registry.object_info()
        for node_id, meta in info.items():
            if category and meta.get("category") != category:
                continue
            nodes.append({
                "id": node_id,
                "display_name": meta.get("display_name", node_id),
                "category": meta.get("category", "Unknown"),
                "description": meta.get("description", ""),
                "inputs": list((meta.get("input_types") or {}).get("required", {}).keys()),
                "outputs": meta.get("return_types", []),
                "requires_tools": meta.get("requires_external_tools", []),
            })
    return {"nodes": nodes, "count": len(nodes)}


def _get_dependency_report(ctx: ToolContext, **kwargs: Any) -> dict[str, Any]:
    """Run dependency resolution on the current workflow."""
    from bionodulo.manager.resolver import resolve_workflow

    registry = ctx.registry
    if not registry:
        return {"error": "Node registry not available"}
    report = resolve_workflow(ctx.workflow, registry)
    return report.to_dict()


def _add_node(ctx: ToolContext, node_type: str, position: list[float] | None = None, params: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    """Add a new node to the workflow. Returns the modified workflow."""
    wf = copy.deepcopy(ctx.workflow)
    nodes = wf.get("nodes", [])
    if isinstance(nodes, dict):
        nodes = list(nodes.values())
        wf["nodes"] = nodes

    pos = position or [200 + len(nodes) * 30, 200 + len(nodes) * 20]
    node_id = f"{node_type}_{len(nodes)}"

    # Try to get defaults from registry
    node_params: dict[str, Any] = {}
    registry = ctx.registry
    if registry and hasattr(registry, "object_info"):
        meta = registry.object_info(node_type)
        if meta:
            for inp_name, inp_spec in (meta.get("input_types") or {}).get("required", {}).items():
                node_params[inp_name] = inp_spec.get("default", "")
            for inp_name, inp_spec in (meta.get("input_types") or {}).get("optional", {}).items():
                node_params[inp_name] = inp_spec.get("default", "")

    if params:
        node_params.update(params)

    new_node = {
        "id": node_id,
        "type": node_type,
        "position": pos,
        "params": node_params,
    }
    nodes.append(new_node)
    wf["nodes"] = nodes
    return {"workflow": wf, "added_node": new_node}


def _update_node(ctx: ToolContext, node_id: str, params: dict[str, Any] | None = None, position: list[float] | None = None, **kwargs: Any) -> dict[str, Any]:
    """Update a node's parameters or position."""
    wf = copy.deepcopy(ctx.workflow)
    nodes = wf.get("nodes", [])
    if isinstance(nodes, dict):
        nodes = list(nodes.values())

    for node in nodes:
        if node.get("id") == node_id:
            if params:
                node.setdefault("params", {}).update(params)
            if position:
                node["position"] = position
            break

    wf["nodes"] = nodes
    return {"workflow": wf}


def _remove_node(ctx: ToolContext, node_id: str, **kwargs: Any) -> dict[str, Any]:
    """Remove a node and its connected edges."""
    wf = copy.deepcopy(ctx.workflow)
    nodes = wf.get("nodes", [])
    if isinstance(nodes, dict):
        nodes = list(nodes.values())

    wf["nodes"] = [n for n in nodes if n.get("id") != node_id]
    edges = wf.get("edges", [])
    wf["edges"] = [e for e in edges if e.get("from", {}).get("node") != node_id and e.get("to", {}).get("node") != node_id]
    return {"workflow": wf}


def _add_edge(ctx: ToolContext, from_node: str, from_output: str, to_node: str, to_input: str, **kwargs: Any) -> dict[str, Any]:
    """Connect an output of one node to an input of another."""
    wf = copy.deepcopy(ctx.workflow)
    edges = wf.get("edges", [])

    edge_id = f"{from_node}_{from_output}_to_{to_node}_{to_input}"
    new_edge = {
        "id": edge_id,
        "from": {"node": from_node, "output": from_output},
        "to": {"node": to_node, "input": to_input},
    }
    edges.append(new_edge)
    wf["edges"] = edges
    return {"workflow": wf, "added_edge": new_edge}


def _remove_edge(ctx: ToolContext, edge_id: str, **kwargs: Any) -> dict[str, Any]:
    """Remove an edge by its ID."""
    wf = copy.deepcopy(ctx.workflow)
    edges = wf.get("edges", [])
    wf["edges"] = [e for e in edges if e.get("id") != edge_id]
    return {"workflow": wf}


def _load_template(ctx: ToolContext, template_name: str, **kwargs: Any) -> dict[str, Any]:
    """Load a pre-built template by filename stem."""
    from pathlib import Path

    templates_dir = Path(__file__).parent.parent.parent / "templates"
    target = templates_dir / f"{template_name}.json"
    if not target.exists():
        # Try common variations
        for alt in [f"{template_name}_pipeline.json", f"{template_name}.json"]:
            t = templates_dir / alt
            if t.exists():
                target = t
                break
    if not target.exists():
        available = [p.stem for p in templates_dir.glob("*.json")]
        return {"error": f"Template '{template_name}' not found. Available: {available}"}

    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return {"workflow": data, "template": target.stem}
    except Exception as exc:
        return {"error": str(exc)}


def _set_workflow_name(ctx: ToolContext, name: str, **kwargs: Any) -> dict[str, Any]:
    """Set the workflow name."""
    wf = copy.deepcopy(ctx.workflow)
    wf["name"] = name
    return {"workflow": wf}


def _set_workflow_description(ctx: ToolContext, description: str, **kwargs: Any) -> dict[str, Any]:
    """Set the workflow description."""
    wf = copy.deepcopy(ctx.workflow)
    wf["description"] = description
    return {"workflow": wf}


def _resolve_dependencies(ctx: ToolContext, **kwargs: Any) -> dict[str, Any]:
    """Run dependency resolution."""
    return _get_dependency_report(ctx)


def _get_settings(ctx: ToolContext, **kwargs: Any) -> dict[str, Any]:
    """Get current application settings."""
    settings = ctx.settings
    if not settings:
        return {"settings": {}}
    # Convert Settings dataclass to dict safely
    try:
        data = {k: v for k, v in vars(settings).items() if not k.startswith("_")}
    except Exception:
        data = {}
    return {"settings": data}


def _update_setting(ctx: ToolContext, key: str, value: Any, **kwargs: Any) -> dict[str, Any]:
    """Update a single setting."""
    return {"setting_key": key, "setting_value": value, "note": "User must confirm before applying"}


def _list_environments(ctx: ToolContext, **kwargs: Any) -> dict[str, Any]:
    """List pixi environments from the workspace envs directory."""
    import subprocess
    try:
        result = subprocess.run(
            ["pixi", "info", "--json"], capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            envs = []
            for name, info in data.get("environments", {}).items():
                envs.append({"name": name, "path": info.get("prefix", "")})
            return {"environments": envs}
    except Exception as exc:
        return {"error": str(exc)}
    return {"environments": []}


def _create_environment(ctx: ToolContext, name: str, packages: list[str], **kwargs: Any) -> dict[str, Any]:
    """Create a pixi environment via manifest (legacy — use workflow envs instead)."""
    return {
        "success": False,
        "message": "Direct environment creation is deprecated. Use workflow-scoped environments via /manager/ensure-workflow-env.",
    }


def _get_node_info(ctx: ToolContext, node_type: str, **kwargs: Any) -> dict[str, Any]:
    """Get detailed info about a specific node type."""
    registry = ctx.registry
    if not registry:
        return {"error": "Registry not available"}
    meta = registry.object_info(node_type)
    if not meta:
        return {"error": f"Node type '{node_type}' not found"}
    return {
        "id": meta.get("id"),
        "display_name": meta.get("display_name"),
        "category": meta.get("category"),
        "description": meta.get("description"),
        "inputs": meta.get("input_types", {}),
        "outputs": meta.get("return_types", []),
        "required_tools": meta.get("requires_external_tools", []),
    }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ALL_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="get_current_workflow",
        description="Get the full JSON of the currently active workflow.",
        parameters=[],
        mutates=False,
        execute=_get_current_workflow,
    ),
    ToolDefinition(
        name="list_available_nodes",
        description="List all available node types. Optionally filter by category. Categories include: 'input', 'qc', 'alignment', 'rna_seq', 'variant', 'assembly', 'phylogeny', 'r' (R visualization), 'biopython' (sequence analysis), 'metagenomics', 'chip_seq', 'single_cell'.",
        parameters=[
            ToolParameter("category", "string", "Filter by category (e.g., 'RNA-Seq', 'Alignment', 'r', 'biopython')", required=False, default=None),
        ],
        mutates=False,
        execute=_list_available_nodes,
    ),
    ToolDefinition(
        name="get_node_info",
        description="Get detailed metadata about a specific node type (inputs, outputs, required tools, required R packages).",
        parameters=[
            ToolParameter("node_type", "string", "Node type ID (e.g., 'fastqc', 'star_align', 'r_plot', 'deseq2_analysis', 'bp_seq_stats')"),
        ],
        mutates=False,
        execute=_get_node_info,
    ),
    ToolDefinition(
        name="get_dependency_report",
        description="Get a report of missing dependencies (nodes, executables, packages) for the current workflow.",
        parameters=[],
        mutates=False,
        execute=_get_dependency_report,
    ),
    ToolDefinition(
        name="list_environments",
        description="List existing pixi environments.",
        parameters=[],
        mutates=False,
        execute=_list_environments,
    ),
    ToolDefinition(
        name="get_settings",
        description="Get current application settings.",
        parameters=[],
        mutates=False,
        execute=_get_settings,
    ),
    ToolDefinition(
        name="add_node",
        description="Add a new node to the workflow.",
        parameters=[
            ToolParameter("node_type", "string", "Node type ID (e.g., 'fastqc')"),
            ToolParameter("position", "array", "[x, y] coordinates on canvas", required=False, default=None),
            ToolParameter("params", "object", "Parameter values to set", required=False, default=None),
        ],
        mutates=True,
        execute=_add_node,
    ),
    ToolDefinition(
        name="update_node",
        description="Update a node's parameters or position.",
        parameters=[
            ToolParameter("node_id", "string", "ID of the node to update"),
            ToolParameter("params", "object", "Parameter values to update", required=False, default=None),
            ToolParameter("position", "array", "New [x, y] coordinates", required=False, default=None),
        ],
        mutates=True,
        execute=_update_node,
    ),
    ToolDefinition(
        name="remove_node",
        description="Remove a node and its connected edges.",
        parameters=[
            ToolParameter("node_id", "string", "ID of the node to remove"),
        ],
        mutates=True,
        execute=_remove_node,
    ),
    ToolDefinition(
        name="add_edge",
        description="Connect an output of one node to an input of another.",
        parameters=[
            ToolParameter("from_node", "string", "Source node ID"),
            ToolParameter("from_output", "string", "Source output name"),
            ToolParameter("to_node", "string", "Target node ID"),
            ToolParameter("to_input", "string", "Target input name"),
        ],
        mutates=True,
        execute=_add_edge,
    ),
    ToolDefinition(
        name="remove_edge",
        description="Remove an edge by its ID.",
        parameters=[
            ToolParameter("edge_id", "string", "Edge ID to remove"),
        ],
        mutates=True,
        execute=_remove_edge,
    ),
    ToolDefinition(
        name="load_template",
        description="Load a pre-built workflow template by name.",
        parameters=[
            ToolParameter("template_name", "string", "Template name stem, e.g. 'rna_seq_pipeline', 'fastq_qc_pipeline'"),
        ],
        mutates=True,
        execute=_load_template,
    ),
    ToolDefinition(
        name="set_workflow_name",
        description="Set the name of the current workflow.",
        parameters=[
            ToolParameter("name", "string", "New workflow name"),
        ],
        mutates=True,
        execute=_set_workflow_name,
    ),
    ToolDefinition(
        name="set_workflow_description",
        description="Set the description of the current workflow.",
        parameters=[
            ToolParameter("description", "string", "New workflow description"),
        ],
        mutates=True,
        execute=_set_workflow_description,
    ),
    ToolDefinition(
        name="resolve_dependencies",
        description="Run dependency resolution to find missing tools, Python packages, and R packages for the current workflow.",
        parameters=[],
        mutates=False,
        execute=_resolve_dependencies,
    ),
    ToolDefinition(
        name="create_environment",
        description="Create a new Conda environment with specified packages. Can include bioinformatics tools, Python packages, and R packages (e.g., ['bwa', 'samtools', 'r-base', 'r-ggplot2', 'bioconductor-deseq2']).",
        parameters=[
            ToolParameter("name", "string", "Environment name"),
            ToolParameter("packages", "array", "List of package names (e.g., ['bwa', 'samtools', 'r-base', 'bioconductor-deseq2'])"),
        ],
        mutates=True,
        execute=_create_environment,
    ),
    ToolDefinition(
        name="update_setting",
        description="Update a single application setting.",
        parameters=[
            ToolParameter("key", "string", "Setting key"),
            ToolParameter("value", "any", "New value"),
        ],
        mutates=True,
        execute=_update_setting,
    ),
]


def get_tool(name: str) -> ToolDefinition | None:
    """Get a tool by name."""
    for t in ALL_TOOLS:
        if t.name == name:
            return t
    return None


def execute_tool(name: str, arguments: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    """Execute a tool by name with the given arguments."""
    tool = get_tool(name)
    if not tool:
        return {"error": f"Tool '{name}' not found"}
    try:
        result = tool.execute(ctx, **arguments)
        return {"status": "ok", "result": result}
    except Exception as exc:
        logger.exception("Tool execution failed: %s", name)
        return {"status": "error", "error": str(exc)}
