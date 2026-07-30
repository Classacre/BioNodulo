from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _load_template(name: str) -> dict[str, Any]:
    return json.loads((ROOT / "templates" / name).read_text(encoding="utf-8"))


def _node_types(workflow: dict[str, Any]) -> dict[str, str]:
    return {str(node["id"]): str(node["type"]) for node in workflow["nodes"]}


def _node_by_id(workflow: dict[str, Any], node_id: str) -> dict[str, Any]:
    return next(node for node in workflow["nodes"] if node["id"] == node_id)


def _has_edge(workflow: dict[str, Any], source: str, source_output: str, target: str, target_input: str) -> bool:
    return any(
        edge.get("from") == {"node": source, "output": source_output}
        and edge.get("to") == {"node": target, "input": target_input}
        for edge in workflow["edges"]
    )


def test_chip_seq_template_plots_bigwig_signal_in_final_report() -> None:
    workflow = _load_template("chip_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["coverage_001"] == "deeptools_bamcoverage"
    assert node_types["index_001"] == "samtools_index"
    assert node_types["chip_signal_plot_001"] == "coverage_plot"
    assert "render_chip_signal_plot_ima_2" not in node_types

    plot = _node_by_id(workflow, "chip_signal_plot_001")
    # The reference is the nf-core yeast genome (contigs I..XVI); there is no
    # contig named smoke_chr1, so pyBigWig failed the whole pipeline at the
    # last node. MACS2 calls peaks in this window, so it provably has signal.
    assert plot["params"]["region"] == "XVI:920000-940000"
    # 200 bp bins over a 20 kb window keeps the plot at 100 points.
    assert plot["params"]["window_size"] == 200
    assert plot["params"]["title"] == "ChIP-Seq Signal Coverage"
    assert plot["params"]["format"] == "html"

    assert _has_edge(workflow, "sort_001", "sorted_bam", "index_001", "bam")
    assert _has_edge(workflow, "index_001", "indexed_bam", "coverage_001", "bam")
    assert _has_edge(workflow, "index_001", "bai", "coverage_001", "bam_index")
    assert not _has_edge(workflow, "sort_001", "sorted_bam", "coverage_001", "bam")
    assert _has_edge(workflow, "coverage_001", "coverage_bw", "chip_signal_plot_001", "alignment")
    assert not any(
        edge.get("from", {}).get("node") == "index_001"
        and edge.get("to", {}).get("node") == "chip_signal_plot_001"
        for edge in workflow["edges"]
    )
    assert workflow["outputs"]["chip_signal_plot"] == "chip_signal_plot_001"
