"""AI node tools consume the frontend registry contract shipped in editor mode."""
from __future__ import annotations

import json

from bionodulo.ai.tools import ToolContext, catalog_matches_for_paper, execute_tool
from bionodulo.nodes.registry import NodeRegistry


def _ctx() -> ToolContext:
    return ToolContext(workflow={"nodes": [], "edges": []}, registry=NodeRegistry.create_isolated())


def test_real_deseq2_contract_and_paper_lookup() -> None:
    ctx = _ctx()
    detail = execute_tool("get_node_info", {"node_type": "deseq2"}, ctx)
    assert detail["status"] == "ok"
    node = detail["result"]
    assert node["inputs"]["required"]["count_matrix"][0] == "FILE"
    assert node["inputs"]["required"]["sample_info"][0] == "FILE"
    assert {"contrast", "count_matrix", "design_formula", "sample_info"} <= set(node["input_names"])
    assert node["return_types"] == ["CSV", "IMAGE", "CSV", "CSV"]
    assert node["outputs"] == ["results_csv", "ma_plot", "normalized_counts_csv", "pca_scores_csv"]
    assert node["requires_external_tools"] is True
    assert node["required_executables"] == ["Rscript"]
    assert "bioconductor-deseq2" in node["required_conda_packages"]
    assert node["required_r_packages"] == ["DESeq2", "ggplot2", "ashr"]
    matches = catalog_matches_for_paper(ctx, "10.1186/s13059-014-0550-8", "RNA-Seq with DESeq2")
    assert any(match["id"] == "deseq2" and match["match_reason"] == "paper DOI cited by node" for match in matches)


def test_normalized_categories_query_and_unknown_category_hint() -> None:
    ctx = _ctx()
    rnaseq = execute_tool("list_available_nodes", {"category": "RNA-Seq", "max_results": 10}, ctx)["result"]
    assert rnaseq["total"] > 0
    assert all(node["category"] == "rna_seq" for node in rnaseq["nodes"])
    assert len(rnaseq["nodes"]) <= 10
    assert rnaseq["has_more"] == (rnaseq["total"] > 10)
    assert len(json.dumps(rnaseq)) < 8000
    broad = execute_tool("list_available_nodes", {}, ctx)["result"]
    assert len(json.dumps(broad)) < 8000
    assert broad["has_more"]
    by_doi = execute_tool("list_available_nodes", {"query": "10.1186/s13059-014-0550-8"}, ctx)["result"]
    assert any(node["id"] == "deseq2" for node in by_doi["nodes"])
    unknown = execute_tool("list_available_nodes", {"category": "bioconductor"}, ctx)["result"]
    assert unknown["nodes"] == []
    assert "query" in unknown["category_hint"]
    assert "rna_seq" in unknown["categories"]


def test_real_metadata_defaults_and_named_file_edges() -> None:
    ctx = _ctx()
    for node_type in ("input_file", "input_file", "deseq2"):
        assert execute_tool("add_node", {"node_type": node_type}, ctx)["status"] == "ok"
    counts, samples, deseq = ctx.workflow["nodes"]
    assert deseq["params"]["design_formula"] == "~ condition"
    assert deseq["params"]["padj_threshold"] == 0.05
    for source, target_slot in ((counts, "count_matrix"), (samples, "sample_info")):
        edge = execute_tool("add_edge", {
            "from_node": source["id"], "from_output": "file",
            "to_node": deseq["id"], "to_input": target_slot,
        }, ctx)
        assert edge["status"] == "ok"
    assert len(ctx.workflow["edges"]) == 2
    wrong = execute_tool("add_edge", {
        "from_node": counts["id"], "from_output": "missing",
        "to_node": deseq["id"], "to_input": "count_matrix",
    }, ctx)
    assert wrong["status"] == "error"
    assert "Valid outputs" in wrong["error"]
