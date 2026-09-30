"""
CWL (Common Workflow Language) import/export converter.

Converts BioNodulo workflows to CWL workflow + CommandLineTool documents
and vice versa.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from bionodulo.converter.edge_utils import (
    edge_source, edge_source_port, edge_target, edge_target_port, executable_edges, executable_nodes, node_outputs, validate_edge_ports,
)
from bionodulo.converter.node_adapter import canonicalize_foreign_workflow, node_input_ports, node_option_widgets
from bionodulo.nodes.registry import NodeRegistry
from bionodulo.converter.roundtrip import restore_workflow_bundle, stamp_workflow_bundle


_CWL_NODE_RUNNER_TYPES = {
    "extract_columns",
    "filter_rows",
    "merge_tables",
    "normalize_data",
    "replace_text",
}


def export_to_cwl(
    workflow: dict[str, Any],
    output_dir: str | Path | None = None,
) -> dict[str, str]:
    """Convert a BioNodulo workflow to CWL workflow + command line tools.

    Args:
        workflow: BioNodulo workflow dict with ``nodes`` and ``edges``.
        output_dir: Directory to write CWL files. If *None*, only returns
            file content without writing.

    Returns:
        Dictionary mapping file names to their content strings.
    """
    nodes = executable_nodes(workflow)
    edges = executable_edges(workflow, nodes)
    validate_edge_ports(nodes, edges)
    for node_id in nodes:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", node_id) or ".." in node_id:
            raise ValueError(f"CWL node id {node_id!r} cannot be used as a safe tool filename")

    output_dir = Path(output_dir) if output_dir else None

    incoming: dict[str, list[dict[str, Any]]] = {nid: [] for nid in nodes}
    outgoing: dict[str, list[dict[str, Any]]] = {nid: [] for nid in nodes}
    for edge in edges:
        src = edge_source(edge)
        tgt = edge_target(edge)
        if src in nodes and tgt in nodes:
            incoming[tgt].append(edge)
            outgoing[src].append(edge)

    files: dict[str, str] = {}

    for node_id, node in nodes.items():
        tool_cwl = _node_to_command_line_tool(
            node_id, node, {edge_target_port(edge) for edge in incoming[node_id]},
        )
        tool_filename = "tools/" + node_id + ".cwl"
        tool_content = json.dumps(tool_cwl, indent=2)
        files[tool_filename] = tool_content

    workflow_cwl = _build_cwl_workflow(
        workflow.get("id", "workflow"), nodes, incoming, outgoing, edges
    )
    wf_content = json.dumps(workflow_cwl, indent=2)
    files["workflow.cwl"] = wf_content
    files = stamp_workflow_bundle(files, workflow)
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "tools").mkdir(exist_ok=True)
        for name, content in files.items():
            (output_dir / name).write_text(content, encoding="utf-8")

    return files


def import_from_cwl(
    workflow_path: str | Path,
    tools_dir: str | Path | None = None,
    workflow_id: str = "imported_cwl",
) -> dict[str, Any]:
    """Parse CWL workflow + tools into a BioNodulo workflow."""
    wf_path = Path(workflow_path)
    workflow_cwl = json.loads(wf_path.read_text(encoding="utf-8"))
    if not isinstance(workflow_cwl, dict):
        raise ValueError("CWL import requires a Workflow object")
    tools_dir = Path(tools_dir) if tools_dir else wf_path.parent / "tools"

    manifest = wf_path.parent / "bionodulo-roundtrip.json"
    if manifest.exists():
        if not manifest.resolve().is_relative_to(wf_path.parent.resolve()):
            raise ValueError("CWL manifest path escapes the workflow directory")
        bundle = {"workflow.cwl": wf_path.read_text(encoding="utf-8"),
                  "bionodulo-roundtrip.json": manifest.read_text(encoding="utf-8")}
        if tools_dir.exists():
            for tool_path in tools_dir.glob("*.cwl"):
                if not tool_path.resolve().is_relative_to(wf_path.parent.resolve()):
                    raise ValueError("CWL tool path escapes the workflow directory")
                bundle["tools/" + tool_path.name] = tool_path.read_text(encoding="utf-8")
        original = restore_workflow_bundle(bundle)
        if original is not None:
            return original

    if workflow_cwl.get("class") != "Workflow":
        raise ValueError("CWL import requires a Workflow document")
    for section in ("inputs", "outputs"):
        if section in workflow_cwl and not isinstance(workflow_cwl[section], dict):
            raise ValueError(f"CWL workflow {section} must be a named object")
        if any(not name for name in workflow_cwl.get(section, {})):
            raise ValueError(f"CWL workflow {section} contains an unnamed port")
    steps = workflow_cwl.get("steps", {})
    if not isinstance(steps, dict) or not steps:
        raise ValueError("CWL import requires named workflow steps")
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    node_id_map: dict[str, str] = {}
    step_output_names: dict[str, set[str]] = {}

    for step_id, step in steps.items():
        if not isinstance(step_id, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", step_id):
            raise ValueError(f"CWL step name {step_id!r} is unsupported")
        if not isinstance(step, dict) or not isinstance(step.get("run"), str) or not step["run"]:
            raise ValueError(f"CWL step {step_id!r} requires a referenced tool file")
        if set(step) - {"run", "in", "out", "id", "label", "doc", "hints", "requirements"}:
            raise ValueError(f"CWL step {step_id!r} uses unsupported workflow features")
        step_inputs = step.get("in", {})
        if not isinstance(step_inputs, dict):
            raise ValueError(f"CWL step {step_id!r} inputs must be a named object")
        for inp_name in step_inputs:
            if not isinstance(inp_name, str) or not inp_name:
                raise ValueError(f"CWL step {step_id!r} has an unnamed input")
        node_id = "node_" + step_id
        node_id_map[step_id] = node_id

        tool_def: dict[str, Any] = {}
        run_ref = step.get("run", "")
        if run_ref:
            if (Path(run_ref).is_absolute() or ".." in Path(run_ref).parts or
                    "\\" in run_ref or ":" in run_ref or len(Path(run_ref).parts) != 2 or
                    not run_ref.startswith("tools/")):
                raise ValueError(f"CWL step {step_id!r} requires a safe tools/<name>.cwl reference")
            tool_path = tools_dir / Path(run_ref).name if tools_dir else Path(run_ref)
            if not tool_path.is_file():
                raise FileNotFoundError(f"Referenced CWL tool file not found: {tool_path}")
            if not tool_path.resolve().is_relative_to(wf_path.parent.resolve()):
                raise ValueError("CWL tool path escapes the workflow directory")
            tool_def = json.loads(tool_path.read_text(encoding="utf-8"))
            if not isinstance(tool_def, dict):
                raise ValueError(f"CWL step {step_id!r} tool must be an object")
            if tool_def.get("class") != "CommandLineTool":
                raise ValueError(f"CWL step {step_id!r} requires a CommandLineTool")
            for section in ("inputs", "outputs"):
                if section in tool_def and not isinstance(tool_def[section], dict):
                    raise ValueError(f"CWL step {step_id!r} tool {section} must be a named object")
                if any(not name for name in tool_def.get(section, {})):
                    raise ValueError(f"CWL step {step_id!r} tool {section} contains an unnamed port")

        tool_outputs = tool_def.get("outputs", {})
        if any(not isinstance(name, str) or not name for name in tool_outputs):
            raise ValueError(f"CWL step {step_id!r} tool has an unnamed output")
        step_out = step.get("out", list(tool_outputs))
        if not isinstance(step_out, list) or any(not isinstance(name, str) or not name for name in step_out):
            raise ValueError(f"CWL step {step_id!r} outputs must be a list of names")
        if set(step_out) - set(tool_outputs):
            raise ValueError(f"CWL step {step_id!r} references an unknown tool output")
        step_output_names[step_id] = set(step_out)

        node_type = "generic_command"

        inputs = {}
        for inp_name, inp_val in step_inputs.items():
            if isinstance(inp_val, dict):
                if set(inp_val) != {"source"}:
                    raise ValueError(f"CWL step {step_id!r} input {inp_name!r} has unsupported binding fields")
                inp_val = inp_val.get("source")
            if isinstance(inp_val, list):
                if len(inp_val) != 1:
                    raise ValueError(f"CWL step {step_id!r} input {inp_name!r} has unsupported multiple sources")
                if not isinstance(inp_val[0], str):
                    raise ValueError(f"CWL step {step_id!r} input {inp_name!r} requires one string source")
                inp_val = inp_val[0]
            if not isinstance(inp_val, str) or not inp_val:
                raise ValueError(f"CWL step {step_id!r} input {inp_name!r} has unsupported source")
            inputs[inp_name] = {"type": "FILE", "value": inp_val}

        outputs = {}
        for out_name in step_out:
            outputs[out_name] = {"type": "FILE"}

        widgets = {}
        for req in tool_def.get("requirements", []):
            if isinstance(req, dict) and req.get("class") == "ResourceRequirement":
                if "coresMin" in req:
                    widgets["threads"] = req["coresMin"]
                if "ramMin" in req:
                    widgets["memory"] = req["ramMin"]

        base_cmd = tool_def.get("baseCommand", [])
        if not isinstance(base_cmd, str) and not (
            isinstance(base_cmd, list) and all(isinstance(part, str) for part in base_cmd)
        ):
            raise ValueError(f"CWL step {step_id!r} tool baseCommand must be a string or string list")
        if base_cmd:
            widgets["command"] = " ".join(base_cmd) if isinstance(base_cmd, list) else base_cmd

        node = {
            "id": node_id,
            "type": node_type,
            "pos": [100 + len(nodes) * 250, 100 + (len(nodes) % 3) * 200],
            "inputs": inputs,
            "outputs": outputs,
            "widgets": widgets,
            "meta": {"import_status": "structural_only"},
        }
        nodes.append(node)

    # Create edges
    for step_id, step in steps.items():
        tgt_id = node_id_map.get(step_id, "")
        for inp_name, inp_val in step.get("in", {}).items():
            if isinstance(inp_val, dict):
                inp_val = inp_val.get("source")
            if isinstance(inp_val, list):
                inp_val = inp_val[0]
            parts = inp_val.split("/")
            if len(parts) == 2 and parts[0] in node_id_map and parts[1] in step_output_names[parts[0]]:
                src_id = node_id_map[parts[0]]
                edges.append({
                    "id": "edge_" + parts[0] + "_" + step_id + "_" + inp_name,
                    "source": src_id,
                    "target": tgt_id,
                    "source_output": parts[1],
                    "target_input": inp_name,
                })
            elif "/" in inp_val or inp_val not in workflow_cwl.get("inputs", {}):
                raise ValueError(f"CWL step {step_id!r} input {inp_name!r} references an unknown source")

    for output_name, output_spec in workflow_cwl.get("outputs", {}).items():
        if not isinstance(output_spec, dict) or not isinstance(output_spec.get("outputSource"), str):
            raise ValueError(f"CWL workflow output {output_name!r} requires one string outputSource")
        parts = output_spec["outputSource"].split("/")
        if len(parts) != 2 or parts[1] not in step_output_names.get(parts[0], set()):
            raise ValueError(f"CWL workflow output {output_name!r} references an unknown source")

    return canonicalize_foreign_workflow({
        "id": workflow_id, "name": "Imported CWL Workflow", "nodes": nodes, "edges": edges,
    })


def _node_to_command_line_tool(
    node_id: str, node: dict[str, Any], connected_inputs: set[str],
) -> dict[str, Any]:
    node_type = node.get("type", "unknown")
    if node_type in _CWL_NODE_RUNNER_TYPES:
        return _node_to_builtin_runner_tool(node_id, node, connected_inputs)
    raise ValueError(f"Cannot export unsupported node type '{node_type}' to CWL")


def _node_to_builtin_runner_tool(
    node_id: str, node: dict[str, Any], connected_inputs: set[str],
) -> dict[str, Any]:
    node_type = node.get("type", "unknown")
    node_class = _registered_node_class(node_type)
    widgets = node_option_widgets(node, connected_inputs=connected_inputs)
    input_types = node_class.INPUT_TYPES()
    specs = dict(_node_runner_input_specs(input_types))
    unknown_widgets = set(widgets) - set(specs)
    input_ports = node_input_ports(node)
    unknown_inputs = set(input_ports) - set(specs)
    if unknown_widgets or unknown_inputs:
        raise ValueError(
            f"CWL node {node_id!r} has unsupported widget/input ports: "
            + ", ".join(sorted(unknown_widgets | unknown_inputs))
        )
    for name in input_ports:
        spec = specs[name]
        kind = spec[0] if isinstance(spec, (list, tuple)) else spec
        if kind != "FILE":
            raise ValueError(f"CWL node {node_id!r} cannot bind scalar widget {name!r} as a file port")
    return_names = set(getattr(node_class, "RETURN_NAMES", ()))
    output_names = set(node_outputs(node))
    if not output_names or not output_names <= return_names:
        raise ValueError(f"CWL node {node_id!r} has unsupported output ports")
    for name, spec in input_types.get("required", {}).items():
        options = spec[1] if isinstance(spec, (list, tuple)) and len(spec) > 1 and isinstance(spec[1], dict) else {}
        if name not in input_ports and name not in widgets and "default" not in options:
            raise ValueError(f"CWL node {node_id!r} lacks required input {name!r}")
    cwl_inputs: dict[str, Any] = {}
    arguments = [
        "--node-type",
        node_type,
        "--output-dir",
        ".",
    ]

    for input_name, spec in _node_runner_input_specs(input_types):
        is_file_input = input_name in input_ports
        cwl_inputs[input_name] = _cwl_node_runner_input(input_name, spec, widgets, is_file_input)
        input_type = cwl_inputs[input_name]["type"]
        arguments.extend([
            "--input",
            input_name,
            f"$(inputs.{input_name}.path)" if is_file_input else (
                f"$(String(inputs.{input_name}))" if input_type == "boolean" else f"$(inputs.{input_name})"
            ),
        ])

    cwl_outputs: dict[str, Any] = {}
    for out_name in node_outputs(node):
        cwl_outputs[out_name] = {
            "type": "File",
            "outputBinding": {"glob": out_name + "_output"},
        }

    return {
        "class": "CommandLineTool",
        "cwlVersion": "v1.2",
        "id": node_id,
        "label": node_type + " - " + node_id,
        # Resolve the interpreter in the target runtime. An absolute path from
        # the exporting host (notably C:\\Python... on Windows) is not portable.
        "baseCommand": ["python", "-m", "bionodulo.converter.cwl_node_runner"],
        "arguments": arguments,
        "inputs": cwl_inputs,
        "outputs": cwl_outputs,
        "requirements": [{"class": "InlineJavascriptRequirement"}],
    }


def _registered_node_class(node_type: str) -> Any:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_type)
    if node_class is None:
        raise ValueError(f"Cannot export unsupported node type '{node_type}' to CWL")
    return node_class


def _node_runner_input_specs(input_types: dict[str, dict[str, Any]]) -> list[tuple[str, Any]]:
    specs: list[tuple[str, Any]] = []
    for section in ("required", "optional"):
        specs.extend((name, spec) for name, spec in input_types.get(section, {}).items())
    return specs


def _cwl_node_runner_input(
    input_name: str,
    spec: Any,
    widgets: dict[str, Any],
    is_file_input: bool,
) -> dict[str, Any]:
    if is_file_input:
        return {"type": "File"}
    config = spec[1] if isinstance(spec, (list, tuple)) and len(spec) > 1 and isinstance(spec[1], dict) else {}
    type_name = spec[0] if isinstance(spec, (list, tuple)) else spec
    cwl_input: dict[str, Any] = {"type": _cwl_type(type_name)}
    if input_name in widgets:
        cwl_input["default"] = widgets[input_name]
    elif "default" in config:
        cwl_input["default"] = config["default"]
    return cwl_input


def _cwl_type(type_name: Any) -> str:
    if isinstance(type_name, list):
        return "string"
    mapping = {
        "FILE": "File",
        "DIRECTORY": "Directory",
        "STRING": "string",
        "INT": "int",
        "FLOAT": "float",
        "BOOLEAN": "boolean",
    }
    return mapping.get(str(type_name), "string")


def _build_cwl_workflow(
    workflow_id: str,
    nodes: dict[str, dict[str, Any]],
    incoming: dict[str, list[dict[str, Any]]],
    outgoing: dict[str, list[dict[str, Any]]],
    edges: list[dict[str, Any]],
) -> dict[str, Any]:
    steps: dict[str, Any] = {}
    for node_id, node in nodes.items():
        step_inputs: dict[str, Any] = {}
        for edge in incoming[node_id]:
            src = edge_source(edge)
            src_port = edge_source_port(edge)
            tgt_port = edge_target_port(edge)
            step_inputs[tgt_port] = str(src) + "/" + src_port
        for inp_name in node_input_ports(node):
            if inp_name not in step_inputs:
                step_inputs[inp_name] = node_id + "_" + inp_name
        steps[node_id] = {
            "run": "tools/" + node_id + ".cwl",
            "in": step_inputs,
            "out": list(node_outputs(node).keys()) or ["default"],
        }

    wf_inputs: dict[str, Any] = {}
    for node_id, node in nodes.items():
        connected_inputs = {edge_target_port(edge) for edge in incoming[node_id]}
        for inp_name in node_input_ports(node):
            if inp_name not in connected_inputs:
                wf_inputs[node_id + "_" + inp_name] = "File"

    wf_outputs: dict[str, Any] = {}
    for node_id, out in outgoing.items():
        if not out:
            node = nodes[node_id]
            for out_name in node_outputs(node):
                wf_outputs[node_id + "_" + out_name] = {
                    "type": "File",
                    "outputSource": node_id + "/" + out_name,
                }

    return {
        "class": "Workflow",
        "cwlVersion": "v1.2",
        "id": workflow_id,
        "label": "BioNodulo workflow " + workflow_id,
        "inputs": wf_inputs,
        "outputs": wf_outputs,
        "steps": steps,
    }
