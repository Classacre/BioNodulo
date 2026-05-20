from __future__ import annotations

from bionodulo.ai.tools import ToolContext, execute_tool


class DummyRegistry:
    def object_info(self, node_type: str | None = None):
        data = {
            "input_fastq": {
                "display_name": "Input FASTQ",
                "category": "Input",
                "description": "FASTQ input",
                "input_types": {"required": {}, "optional": {"path": {"type": "STRING", "default": ""}}},
                "return_types": ["FASTQ"],
                "return_names": ["fastq"],
            },
            "fastqc": {
                "display_name": "FastQC",
                "category": "QC",
                "description": "Quality control",
                "input_types": {"required": {"fastq": {"type": "FASTQ"}}},
                "return_types": ["HTML"],
                "return_names": ["report"],
                "requires_external_tools": ["fastqc"],
            },
        }
        return data if node_type is None else data.get(node_type)


def test_ai_graph_tools_preserve_workflow_id_and_validate_edges():
    ctx = ToolContext(
        workflow={"id": "wf-local", "nodes": [], "edges": []},
        workflow_id="wf-local",
        registry=DummyRegistry(),
    )

    first = execute_tool("add_node", {"node_type": "input_fastq"}, ctx)
    second = execute_tool("add_node", {"node_type": "fastqc"}, ctx)
    nodes = ctx.workflow["nodes"]
    edge = execute_tool(
        "add_edge",
        {
            "from_node": nodes[0]["id"],
            "from_output": "fastq",
            "to_node": nodes[1]["id"],
            "to_input": "fastq",
        },
        ctx,
    )

    assert first["status"] == "ok"
    assert second["status"] == "ok"
    assert edge["status"] == "ok"
    assert ctx.workflow["id"] == "wf-local"
    assert len(ctx.workflow["edges"]) == 1


def test_ai_graph_tools_reject_unknown_slots():
    ctx = ToolContext(
        workflow={"id": "wf-local", "nodes": [], "edges": []},
        workflow_id="wf-local",
        registry=DummyRegistry(),
    )
    execute_tool("add_node", {"node_type": "input_fastq"}, ctx)
    execute_tool("add_node", {"node_type": "fastqc"}, ctx)
    nodes = ctx.workflow["nodes"]

    result = execute_tool(
        "add_edge",
        {
            "from_node": nodes[0]["id"],
            "from_output": "not_a_real_output",
            "to_node": nodes[1]["id"],
            "to_input": "fastq",
        },
        ctx,
    )

    assert result["status"] == "error"
    assert "not_a_real_output" in result["error"]
