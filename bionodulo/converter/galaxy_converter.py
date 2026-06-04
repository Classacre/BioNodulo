"""
Galaxy workflow converter.

Converts BioNodulo workflows to Galaxy workflow JSON (.ga format) and vice versa.
"""

from __future__ import annotations

import json
import uuid as _uuid
from collections import deque
from pathlib import Path
from typing import Any

from bionodulo.converter.edge_utils import edge_source, edge_source_port, edge_target, edge_target_port, node_outputs


def export_to_galaxy(
    workflow: dict[str, Any],
    output_path: str | Path | None = None,
) -> str:
    """Convert a BioNodulo workflow to Galaxy workflow JSON (.ga format).

    Args:
        workflow: BioNodulo workflow dict with ``nodes`` and ``edges``.
        output_path: If given, write the JSON to this path.

    Returns:
        The Galaxy workflow JSON as a string.
    """
    nodes: dict[str, dict[str, Any]] = {n["id"]: n for n in workflow.get("nodes", [])}
    edges: list[dict[str, Any]] = workflow.get("edges", [])

    incoming: dict[str, list[dict[str, Any]]] = {nid: [] for nid in nodes}
    outgoing: dict[str, list[dict[str, Any]]] = {nid: [] for nid in nodes}
    for edge in edges:
        src = edge_source(edge)
        tgt = edge_target(edge)
        if src in nodes and tgt in nodes:
            incoming[tgt].append(edge)
            outgoing[src].append(edge)

    galaxy_wf: dict[str, Any] = {
        "a_galaxy_workflow": "true",
        "format-version": "0.1",
        "name": workflow.get("name", "BioNodulo Workflow"),
        "annotation": workflow.get("description", "Exported from BioNodulo v2"),
        "uuid": str(_uuid.uuid4()),
        "steps": {},
    }

    step_index: dict[str, int] = {}
    step_counter = 1

    for node_id in _topological_sort_galaxy(nodes, incoming):
        node = nodes[node_id]
        node_type = node.get("type", "unknown")
        widgets = node.get("widgets", {})

        galaxy_step = {
            "id": step_counter,
            "uuid": str(_uuid.uuid4()),
            "label": node_id,
            "annotation": "BioNodulo node: " + node_type,
            "tool_id": _node_type_to_galaxy_tool(node_type),
            "tool_version": widgets.get("tool_version", "1.0.0"),
            "name": node_type,
            "type": "tool",
            "inputs": [],
            "outputs": [],
            "input_connections": {},
            "tool_state": _build_tool_state(widgets),
            "position": {
                "left": node.get("pos", [100 + step_counter * 200, 100])[0],
                "top": node.get("pos", [100, 100 + step_counter * 150])[1],
            },
            "post_job_actions": {},
        }

        for port in node_outputs(node):
            galaxy_step["outputs"].append({
                "name": port,
                "type": "data",
                "output_name": port,
            })

        for edge in incoming[node_id]:
            src = edge_source(edge)
            src_port = edge_source_port(edge)
            tgt_port = edge_target_port(edge)
            if src in step_index:
                galaxy_step["input_connections"][tgt_port] = {
                    "id": step_index[src],
                    "output_name": src_port,
                }

        for inp_name in node.get("inputs", {}).keys():
            if inp_name not in galaxy_step["input_connections"]:
                galaxy_step["inputs"].append({"name": inp_name, "description": "Input: " + inp_name})

        galaxy_wf["steps"][str(step_counter)] = galaxy_step
        step_index[node_id] = step_counter
        step_counter += 1

    result = json.dumps(galaxy_wf, indent=2)
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(result, encoding="utf-8")
    return result


def import_from_galaxy(
    galaxy_json: str,
    workflow_id: str = "imported_galaxy",
) -> dict[str, Any]:
    """Parse a Galaxy workflow JSON (.ga format) into a BioNodulo workflow."""
    content = galaxy_json
    if Path(galaxy_json).is_file():
        content = Path(galaxy_json).read_text(encoding="utf-8")
    galaxy_wf = json.loads(content)

    steps = galaxy_wf.get("steps", {})
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    node_id_map: dict[str, str] = {}

    for step_id_str, step in steps.items():
        step_type = step.get("type", "tool")

        if step_type in ("data_input", "data_collection_input", "parameter_input"):
            node_id = "input_" + step_id_str
            node_id_map[step_id_str] = node_id
            node = {
                "id": node_id,
                "type": "file_input",
                "pos": [
                    step.get("position", {}).get("left", 100),
                    step.get("position", {}).get("top", 100),
                ],
                "inputs": {},
                "outputs": {"output": {"type": "FILE"}},
                "widgets": {"format": step.get("tool_state", {}).get("format", "auto")},
                "meta": {"galaxy_step_type": step_type},
            }
            nodes.append(node)

        elif step_type == "tool":
            node_id = "node_" + step.get("label", step_id_str)
            node_id_map[step_id_str] = node_id
            tool_id = step.get("tool_id", "")
            node_type = _galaxy_tool_to_node_type(tool_id)

            widgets: dict[str, Any] = {}
            tool_state = step.get("tool_state", {})
            if isinstance(tool_state, str):
                try:
                    tool_state = json.loads(tool_state)
                except json.JSONDecodeError:
                    tool_state = {}
            widgets.update(tool_state)

            inputs = {}
            for inp in step.get("inputs", []):
                if isinstance(inp, dict):
                    inputs[inp.get("name", "input")] = {"type": "FILE"}
                else:
                    inputs[inp] = {"type": "FILE"}

            outputs: dict[str, Any] = {}
            for out in step.get("outputs", []):
                if isinstance(out, dict):
                    outputs[out.get("name", "output_" + str(len(outputs)))] = {"type": "FILE"}
                else:
                    outputs["output_" + str(len(outputs))] = {"type": "FILE"}

            position = step.get("position", {})
            node = {
                "id": node_id,
                "type": node_type,
                "pos": [
                    position.get("left", 100 + len(nodes) * 250),
                    position.get("top", 100 + (len(nodes) % 3) * 200),
                ],
                "inputs": inputs,
                "outputs": outputs,
                "widgets": widgets,
                "meta": {
                    "galaxy_tool_id": tool_id,
                    "galaxy_tool_version": step.get("tool_version", ""),
                },
            }
            nodes.append(node)

    for step_id_str, step in steps.items():
        tgt_id = node_id_map.get(step_id_str)
        if not tgt_id:
            continue
        input_connections = step.get("input_connections", {})
        for tgt_port, conn in input_connections.items():
            src_step = ""
            src_port = "default"
            if isinstance(conn, dict):
                src_step = str(conn.get("id", ""))
                src_port = conn.get("output_name", "default")
            elif isinstance(conn, list) and conn:
                src_step = str(conn[0].get("id", ""))
                src_port = conn[0].get("output_name", "default")
            src_id = node_id_map.get(src_step)
            if src_id and tgt_id:
                edges.append({
                    "id": "edge_" + src_step + "_" + step_id_str + "_" + tgt_port,
                    "source": src_id,
                    "target": tgt_id,
                    "source_output": src_port,
                    "target_input": tgt_port,
                })

    return {
        "id": workflow_id,
        "name": galaxy_wf.get("name", "Imported Galaxy Workflow"),
        "nodes": nodes,
        "edges": edges,
    }


def _node_type_to_galaxy_tool(node_type: str) -> str:
    mapping = {
        "fastqc": "toolshed.g2.bx.psu.edu/repos/devteam/fastqc/fastqc/0.74+galaxy0",
        "multiqc": "toolshed.g2.bx.psu.edu/repos/iuc/multiqc/multiqc/1.11+galaxy0",
        "fastp": "toolshed.g2.bx.psu.edu/repos/iuc/fastp/fastp/0.23.2+galaxy0",
        "trimmomatic": "toolshed.g2.bx.psu.edu/repos/pjbriggs/trimmomatic/trimmomatic/0.39",
        "bowtie2": "toolshed.g2.bx.psu.edu/repos/devteam/bowtie2/bowtie2/2.4.5+galaxy0",
        "bwa_mem": "toolshed.g2.bx.psu.edu/repos/devteam/bwa/bwa_mem/0.7.17.2",
        "samtools_sort": "toolshed.g2.bx.psu.edu/repos/devteam/samtools_sort/samtools_sort/2.0.5",
        "samtools_index": "toolshed.g2.bx.psu.edu/repos/devteam/samtools_index/samtools_index/2.0.5",
        "bcftools_mpileup": "toolshed.g2.bx.psu.edu/repos/iuc/bcftools_mpileup/bcftools_mpileup/1.15.1+galaxy0",
        "spades": "toolshed.g2.bx.psu.edu/repos/nml/spades/spades/3.15.5+galaxy0",
        "prokka": "toolshed.g2.bx.psu.edu/repos/crs4/prokka/prokka/1.14.6+galaxy0",
        "star_align": "toolshed.g2.bx.psu.edu/repos/iuc/rgrnastar/rna_star/2.7.10b+galaxy3",
        "hisat2": "toolshed.g2.bx.psu.edu/repos/iuc/hisat2/hisat2/2.2.1+galaxy1",
        "salmon_quant": "toolshed.g2.bx.psu.edu/repos/iuc/salmon/salmon/1.10.1+galaxy0",
        "featurecounts": "toolshed.g2.bx.psu.edu/repos/iuc/featurecounts/featurecounts/2.0.3+galaxy0",
        "kraken2": "toolshed.g2.bx.psu.edu/repos/iuc/kraken2/kraken2/2.1.2+galaxy0",
        "iqtree": "toolshed.g2.bx.psu.edu/repos/iuc/iqtree/iqtree/2.2.2.7+galaxy0",
    }
    if node_type not in mapping:
        raise ValueError(f"Cannot export unsupported node type '{node_type}' to Galaxy")
    return mapping[node_type]


def _galaxy_tool_to_node_type(tool_id: str) -> str:
    tl = tool_id.lower()
    if "fastqc" in tl:
        return "fastqc"
    if "multiqc" in tl:
        return "multiqc"
    if "fastp" in tl:
        return "fastp"
    if "trimmomatic" in tl:
        return "trimmomatic"
    if "bowtie2" in tl:
        return "bowtie2"
    if "bwa" in tl:
        return "bwa_mem"
    if "samtools_sort" in tl:
        return "samtools_sort"
    if "samtools_index" in tl:
        return "samtools_index"
    if "bcftools" in tl:
        return "bcftools_mpileup"
    if "spades" in tl:
        return "spades"
    if "prokka" in tl:
        return "prokka"
    if "star" in tl or "rgrnastar" in tl:
        return "star_align"
    if "hisat2" in tl:
        return "hisat2"
    if "salmon" in tl:
        return "salmon_quant"
    if "featurecounts" in tl:
        return "featurecounts"
    if "kraken2" in tl:
        return "kraken2"
    if "iqtree" in tl:
        return "iqtree"
    return "command"


def _build_tool_state(widgets: dict[str, Any]) -> dict[str, Any]:
    state: dict[str, Any] = {}
    for key, val in widgets.items():
        if isinstance(val, (dict, list)):
            state[key] = json.dumps(val)
        else:
            state[key] = str(val)
    return state


def _topological_sort_galaxy(
    nodes: dict[str, dict[str, Any]],
    incoming: dict[str, list[dict[str, Any]]],
) -> list[str]:
    in_degree = {nid: len(incoming[nid]) for nid in nodes}
    queue = deque(nid for nid, deg in in_degree.items() if deg == 0)
    order: list[str] = []
    while queue:
        nid = queue.popleft()
        order.append(nid)
        for other_nid in nodes:
            for edge in incoming.get(other_nid, []):
                if edge_source(edge) == nid:
                    in_degree[other_nid] -= 1
                    if in_degree[other_nid] == 0:
                        queue.append(other_nid)
    if len(order) != len(nodes):
        return list(nodes.keys())
    return order
