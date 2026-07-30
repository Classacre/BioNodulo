from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _load_template(name: str) -> dict[str, Any]:
    return json.loads((ROOT / "templates" / name).read_text(encoding="utf-8"))


def _node_types(workflow: dict[str, Any]) -> dict[str, str]:
    return {str(node["id"]): str(node["type"]) for node in workflow["nodes"]}


def _has_edge(workflow: dict[str, Any], source: str, source_output: str, target: str, target_input: str) -> bool:
    return any(
        edge.get("from") == {"node": source, "output": source_output}
        and edge.get("to") == {"node": target, "input": target_input}
        for edge in workflow["edges"]
    )


def _node(workflow: dict[str, Any], node_id: str) -> dict[str, Any]:
    return next(node for node in workflow["nodes"] if node["id"] == node_id)


def _output_validation(workflow: dict[str, Any], node_id: str, output: str) -> dict[str, Any]:
    node = _node(workflow, node_id)
    return (
        node.get("ui", {})
        .get("validation", {})
        .get("outputs", {})
        .get(output, {})
    )


def test_single_cell_template_quantifies_with_starsolo_not_cellranger() -> None:
    """Cell Ranger cannot be used unattended.

    10x distributes it under a click-through licence: the download URL answers
    403 to any automated fetch and no conda channel may redistribute it. The
    template therefore builds a STAR index and quantifies with STARsolo, which
    is open, already present in the STAR binary, and emits the same
    Matrix-Market triple Scanpy reads.
    """
    workflow = _load_template("single_cell_pipeline.json")
    node_types = _node_types(workflow)

    assert "cellranger_count" not in node_types.values()
    assert node_types["starsolo_001"] == "starsolo_count"
    assert node_types["star_index_001"] == "star_index"


def test_single_cell_template_builds_its_own_star_index() -> None:
    """The public tiny reference ships star/Genome and star/SAindex but no star/SA.

    Consuming that directory failed with "reference is missing required file(s):
    star/SA", so the index is built here from the FASTA and GTF instead.
    """
    workflow = _load_template("single_cell_pipeline.json")

    assert _has_edge(workflow, "genome_fasta_001", "reference", "star_index_001", "reference")
    assert _has_edge(workflow, "genes_gtf_001", "annotation", "star_index_001", "gtf")
    assert _has_edge(workflow, "star_index_001", "index", "starsolo_001", "genome_dir")

    index = _node(workflow, "star_index_001")
    # A 48 Mb genome needs genomeSAindexNbases <= log2(len)/2 - 1 (~11.7 here);
    # STAR's default of 14 sizes for a genome ~250x larger and is killed.
    assert index["params"]["genome_sa_index_nbases"] == 11


def test_single_cell_template_assigns_the_reads_to_the_right_starsolo_ports() -> None:
    """Swapping cDNA and barcode reads yields an empty matrix, not an error."""
    workflow = _load_template("single_cell_pipeline.json")

    assert _has_edge(workflow, "r2_001", "read1", "starsolo_001", "cdna_fastq")
    assert _has_edge(workflow, "r1_001", "read1", "starsolo_001", "barcode_fastq")

    solo = _node(workflow, "starsolo_001")
    # tinygex is 10x v3: R1 is 28 bp = 16 bp CB + 12 bp UMI (measured).
    assert solo["params"]["cb_length"] == 16
    assert solo["params"]["umi_length"] == 12


def test_single_cell_template_thresholds_match_the_tiny_reference() -> None:
    """The reference is chr21 only: 343 genes total, median 16 per cell.

    Scanpy's stock min_genes=200 leaves zero cells and exits "Too few cells or
    genes after filtering" -- measured on the real STARsolo matrix.
    """
    workflow = _load_template("single_cell_pipeline.json")

    scanpy = _node(workflow, "scanpy_umap_001")
    assert scanpy["params"]["min_genes"] == 10


def test_single_cell_template_advertises_qc_dashboard_preview() -> None:
    workflow = _load_template("single_cell_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["qc_dashboard_preview_001"] == "html_preview"
    assert _has_edge(workflow, "qc_dashboard_001", "qc_dashboard", "qc_dashboard_preview_001", "file")
    assert workflow["outputs"]["qc_dashboard_preview"] == "qc_dashboard_preview_001"


def test_single_cell_template_advertises_the_starsolo_matrix_outputs() -> None:
    workflow = _load_template("single_cell_pipeline.json")

    assert workflow["outputs"]["filtered_matrix"] == "starsolo_001"
    assert workflow["outputs"]["raw_matrix"] == "starsolo_001"
    assert workflow["outputs"]["umap"] == "scanpy_umap_001"
