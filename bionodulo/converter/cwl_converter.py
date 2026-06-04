"""
CWL (Common Workflow Language) import/export converter.

Converts BioNodulo workflows to CWL workflow + CommandLineTool documents
and vice versa.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bionodulo.converter.edge_utils import edge_source, edge_source_port, edge_target, edge_target_port, node_outputs


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
    nodes: dict[str, dict[str, Any]] = {n["id"]: n for n in workflow.get("nodes", [])}
    edges: list[dict[str, Any]] = workflow.get("edges", [])

    output_dir = Path(output_dir) if output_dir else None
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "tools").mkdir(exist_ok=True)

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
        tool_cwl = _node_to_command_line_tool(node_id, node)
        tool_filename = "tools/" + node_id + ".cwl"
        tool_content = json.dumps(tool_cwl, indent=2)
        files[tool_filename] = tool_content
        if output_dir:
            (output_dir / tool_filename).write_text(tool_content, encoding="utf-8")

    workflow_cwl = _build_cwl_workflow(
        workflow.get("id", "workflow"), nodes, incoming, outgoing, edges
    )
    wf_content = json.dumps(workflow_cwl, indent=2)
    files["workflow.cwl"] = wf_content
    if output_dir:
        (output_dir / "workflow.cwl").write_text(wf_content, encoding="utf-8")

    return files


def import_from_cwl(
    workflow_path: str | Path,
    tools_dir: str | Path | None = None,
    workflow_id: str = "imported_cwl",
) -> dict[str, Any]:
    """Parse CWL workflow + tools into a BioNodulo workflow."""
    wf_path = Path(workflow_path)
    workflow_cwl = json.loads(wf_path.read_text(encoding="utf-8"))
    tools_dir = Path(tools_dir) if tools_dir else wf_path.parent / "tools"

    steps = workflow_cwl.get("steps", {})
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    node_id_map: dict[str, str] = {}

    for step_id, step in steps.items():
        node_id = "node_" + step_id
        node_id_map[step_id] = node_id

        tool_def: dict[str, Any] = {}
        run_ref = step.get("run", "")
        if run_ref:
            tool_path = tools_dir / Path(run_ref).name if tools_dir else Path(run_ref)
            if not tool_path.is_file():
                raise FileNotFoundError(f"Referenced CWL tool file not found: {tool_path}")
            tool_def = json.loads(tool_path.read_text(encoding="utf-8"))

        node_type = _cwl_tool_to_node_type(tool_def)

        inputs = {}
        for inp_name, inp_val in step.get("in", {}).items():
            if isinstance(inp_val, str):
                inputs[inp_name] = {"type": "FILE", "value": inp_val}
            elif isinstance(inp_val, list):
                inputs[inp_name] = {"type": "FILE", "value": inp_val[0] if inp_val else ""}
            else:
                inputs[inp_name] = {"type": "ANY", "value": inp_val}

        outputs = {}
        for out_name in tool_def.get("outputs", {}).keys():
            outputs[out_name] = {"type": "FILE"}

        widgets = {}
        for req in tool_def.get("requirements", []):
            if isinstance(req, dict) and req.get("class") == "ResourceRequirement":
                if "coresMin" in req:
                    widgets["threads"] = req["coresMin"]
                if "ramMin" in req:
                    widgets["memory"] = req["ramMin"]

        base_cmd = tool_def.get("baseCommand", [])
        if base_cmd:
            widgets["command"] = " ".join(base_cmd) if isinstance(base_cmd, list) else base_cmd

        node = {
            "id": node_id,
            "type": node_type,
            "pos": [100 + len(nodes) * 250, 100 + (len(nodes) % 3) * 200],
            "inputs": inputs,
            "outputs": outputs,
            "widgets": widgets,
            "meta": {},
        }
        nodes.append(node)

    # Create edges
    for step_id, step in steps.items():
        tgt_id = node_id_map.get(step_id, "")
        for inp_name, inp_val in step.get("in", {}).items():
            if isinstance(inp_val, str):
                parts = inp_val.split("/")
                if len(parts) == 2 and parts[0] in node_id_map:
                    src_id = node_id_map[parts[0]]
                    edges.append({
                        "id": "edge_" + parts[0] + "_" + step_id + "_" + inp_name,
                        "source": src_id,
                        "target": tgt_id,
                        "source_output": parts[1],
                        "target_input": inp_name,
                    })

    return {"id": workflow_id, "name": "Imported CWL Workflow", "nodes": nodes, "edges": edges}


def _node_to_command_line_tool(node_id: str, node: dict[str, Any]) -> dict[str, Any]:
    node_type = node.get("type", "unknown")
    widgets = node.get("widgets", {})
    meta = node.get("meta", {})
    base_cmd = _cwl_base_command(node_type, widgets)

    cwl_inputs: dict[str, Any] = {}
    for inp_name in node.get("inputs", {}).keys():
        cwl_inputs[inp_name] = {
            "type": "File",
            "inputBinding": {"position": len(cwl_inputs) + 1},
        }

    cwl_outputs: dict[str, Any] = {}
    for out_name in node_outputs(node):
        cwl_outputs[out_name] = {
            "type": "File",
            "outputBinding": {"glob": out_name + "_output"},
        }

    for key, val in widgets.items():
        if key in ("command", "_node_type", "_output_ports"):
            continue
        param_name = "param_" + key
        cwl_inputs[param_name] = {
            "type": "string" if isinstance(val, str) else "int" if isinstance(val, int) else "string",
            "default": val,
            "inputBinding": {"prefix": "--" + key},
        }

    tool = {
        "class": "CommandLineTool",
        "cwlVersion": "v1.2",
        "id": node_id,
        "label": node_type + " - " + node_id,
        "baseCommand": base_cmd,
        "inputs": cwl_inputs,
        "outputs": cwl_outputs,
        "requirements": [{"class": "InlineJavascriptRequirement"}],
    }

    threads = meta.get("threads") or widgets.get("threads")
    memory = meta.get("memory") or widgets.get("memory")
    requirements = list(tool["requirements"])
    resource_req: dict[str, Any] = {"class": "ResourceRequirement"}
    if threads:
        resource_req["coresMin"] = int(threads)
    if memory:
        resource_req["ramMin"] = int(memory)
    if len(resource_req) > 1:
        requirements.append(resource_req)
    tool["requirements"] = requirements

    conda_env = meta.get("conda_env") or widgets.get("conda_env")
    container = meta.get("container") or widgets.get("container")
    if container or conda_env:
        tool["hints"] = []
        if container:
            tool["hints"].append({"class": "DockerRequirement", "dockerPull": container})
        if conda_env:
            tool["hints"].append({"class": "SoftwareRequirement", "packages": [{"package": conda_env}]})

    return tool


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
        steps[node_id] = {
            "run": "tools/" + node_id + ".cwl",
            "in": step_inputs,
            "out": list(node_outputs(node).keys()) or ["default"],
        }

    wf_inputs: dict[str, Any] = {}
    for node_id, inc in incoming.items():
        if not inc:
            node = nodes[node_id]
            for inp_name in node.get("inputs", {}).keys():
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


def _cwl_base_command(node_type: str, widgets: dict[str, Any]) -> list[str]:
    custom_cmd = widgets.get("command")
    if custom_cmd:
        return custom_cmd.split() if isinstance(custom_cmd, str) else [str(custom_cmd)]

    cmd_map: dict[str, list[str]] = {
        "fastqc": ["fastqc"], "multiqc": ["multiqc"], "fastp": ["fastp"],
        "trimmomatic": ["trimmomatic"], "bowtie2": ["bowtie2"],
        "bwa_mem": ["bwa", "mem"], "samtools_sort": ["samtools", "sort"],
        "samtools_index": ["samtools", "index"],
        "bcftools_mpileup": ["bcftools", "mpileup"],
        "spades": ["spades.py"], "prokka": ["prokka"],
        "star_align": ["STAR"], "hisat2": ["hisat2"],
        "salmon_quant": ["salmon", "quant"],
        "featurecounts": ["featureCounts"],
        "kraken2": ["kraken2"], "iqtree": ["iqtree"],
    }
    if node_type not in cmd_map:
        raise ValueError(f"Cannot export unsupported node type '{node_type}' to CWL")
    return cmd_map[node_type]


def _cwl_tool_to_node_type(tool_def: dict[str, Any]) -> str:
    base_cmd = tool_def.get("baseCommand", [])
    if isinstance(base_cmd, str):
        base_cmd = [base_cmd]
    cmd_str = " ".join(base_cmd).lower()
    label = tool_def.get("label", "").lower()

    mapping = {
        "fastqc": "fastqc", "multiqc": "multiqc", "fastp": "fastp",
        "trimmomatic": "trimmomatic", "bowtie2": "bowtie2",
        "bwa mem": "bwa_mem", "samtools sort": "samtools_sort",
        "samtools index": "samtools_index", "bcftools": "bcftools_mpileup",
        "spades": "spades", "prokka": "prokka", "star": "star_align",
        "hisat2": "hisat2", "salmon": "salmon_quant",
        "featurecounts": "featurecounts", "kraken2": "kraken2",
        "iqtree": "iqtree",
    }
    for key, val in mapping.items():
        if key in cmd_str or key in label:
            return val
    return "generic_command"
