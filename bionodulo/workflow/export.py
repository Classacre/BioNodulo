"""Workflow export to various pipeline formats.

Delegates to converter modules for SnakeMake, NextFlow, CWL, and Galaxy.
"""

from __future__ import annotations

from typing import Any


def export_workflow(
    workflow: dict[str, Any],
    fmt: str,
    name: str = "workflow",
) -> str:
    """Export a workflow to the specified format.

    Args:
        workflow: Workflow dictionary to export.
        fmt: Target format - "snakemake", "nextflow", "cwl", "galaxy", or "json".
        name: Base name for the output file.

    Returns:
        String content of the exported workflow.

    Raises:
        ValueError: If the format is not supported.
    """
    fmt = fmt.lower()

    if fmt == "json":
        import json as _json
        return _json.dumps(workflow, indent=2, ensure_ascii=False, default=str)

    if fmt == "snakemake":
        try:
            from bionodulo.converter.snakemake_converter import export_workflow as snakemake_export
            return snakemake_export(workflow, name=name)
        except ImportError:
            return _fallback_export(workflow, fmt, name)

    if fmt == "nextflow":
        try:
            from bionodulo.converter.nextflow_converter import export_workflow as nextflow_export
            return nextflow_export(workflow, name=name)
        except ImportError:
            return _fallback_export(workflow, fmt, name)

    if fmt == "cwl":
        try:
            from bionodulo.converter.cwl_converter import export_workflow as cwl_export
            return cwl_export(workflow, name=name)
        except ImportError:
            return _fallback_export(workflow, fmt, name)

    if fmt == "galaxy":
        try:
            from bionodulo.converter.galaxy_converter import export_workflow as galaxy_export
            return galaxy_export(workflow, name=name)
        except ImportError:
            return _fallback_export(workflow, fmt, name)

    raise ValueError(
        f"Unsupported export format: '{fmt}'. "
        f"Supported: snakemake, nextflow, cwl, galaxy, json"
    )


def _fallback_export(workflow: dict[str, Any], fmt: str, name: str) -> str:
    """Generate a placeholder export when the converter module is unavailable."""
    lines: list[str] = [
        f"# {fmt.upper()} export: {name}",
        f"# NOTE: {fmt} converter module not installed.",
        "# Install converter dependencies for full export support.",
        "",
        "# Workflow nodes:",
    ]

    nodes = workflow.get("nodes", {})
    if isinstance(nodes, dict):
        for node_id, node in nodes.items():
            if isinstance(node, dict):
                node_type = node.get("type", "unknown")
                node_params = node.get("params", {})
                lines.append(f"#   {node_id}: {node_type}")
                for k, v in node_params.items():
                    lines.append(f"#     param {k} = {v}")
            else:
                nt = getattr(node, "type", "unknown")
                lines.append(f"#   {node_id}: {nt}")
    elif isinstance(nodes, list):
        for node in nodes:
            if isinstance(node, dict):
                nid = node.get("id", "?")
                ntype = node.get("type", "unknown")
                lines.append(f"#   {nid}: {ntype}")

    lines.append("")
    lines.append("# Edges:")
    for edge in workflow.get("edges", []):
        if isinstance(edge, dict):
            src = edge.get("from_node") or edge.get("source_node", "?")
            dst = edge.get("to_node") or edge.get("target_node", "?")
            lines.append(f"#   {src} --> {dst}")
        else:
            src = getattr(edge, "source_node", "?")
            dst = getattr(edge, "target_node", "?")
            lines.append(f"#   {src} --> {dst}")

    lines.append("")
    lines.append(f"# End of {name} export")
    return "\n".join(lines)
