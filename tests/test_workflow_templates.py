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


def test_variant_calling_template_marks_duplicates_before_gatk_and_adds_annotation_report() -> None:
    workflow = _load_template("variant_calling_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["markdup_001"] == "samtools_markdup"
    assert node_types["snpeff_001"] == "snpeff"
    assert node_types["vcf_stats_001"] == "vcf_stats_chart"
    assert node_types["variant_report_001"] == "html_report"
    assert _has_edge(workflow, "view_001", "bam", "collate_001", "bam")
    assert _has_edge(workflow, "collate_001", "name_collated_bam", "fixmate_001", "bam")
    assert _has_edge(workflow, "fixmate_001", "fixmate_bam", "sort_001", "bam")
    assert _has_edge(workflow, "sort_001", "sorted_bam", "markdup_001", "bam")
    assert _has_edge(workflow, "markdup_001", "marked_bam", "index_001", "bam")
    assert _has_edge(workflow, "markdup_001", "marked_bam", "gatk_001", "bam")
    assert _has_edge(workflow, "filter_001", "filtered_vcf", "snpeff_001", "vcf")
    assert _has_edge(workflow, "filter_001", "filtered_vcf", "vcf_stats_001", "vcf")
    assert _has_edge(workflow, "vcf_stats_001", "stats_image", "variant_report_001", "images")
    assert _has_edge(workflow, "snpeff_001", "annotated_vcf", "variant_report_001", "tables")
    assert next(node for node in workflow["nodes"] if node["id"] == "vcf_stats_001")["params"]["format"] == "png"
    assert workflow["outputs"]["vcf"] == "snpeff_001"
    assert workflow["outputs"]["variant_stats"] == "vcf_stats_001"


def test_wgs_variant_template_marks_duplicates_before_freebayes_and_adds_annotation_report() -> None:
    workflow = _load_template("wgs_variant_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["markdup_001"] == "samtools_markdup"
    assert node_types["snpeff_001"] == "snpeff"
    assert node_types["vcf_stats_001"] == "vcf_stats_chart"
    assert node_types["variant_report_001"] == "html_report"
    assert _has_edge(workflow, "view_001", "bam", "collate_001", "bam")
    assert _has_edge(workflow, "collate_001", "name_collated_bam", "fixmate_001", "bam")
    assert _has_edge(workflow, "fixmate_001", "fixmate_bam", "sort_001", "bam")
    assert _has_edge(workflow, "sort_001", "sorted_bam", "markdup_001", "bam")
    assert _has_edge(workflow, "markdup_001", "marked_bam", "idx_001", "bam")
    assert _has_edge(workflow, "markdup_001", "marked_bam", "fb_001", "bam")
    assert _has_edge(workflow, "filter_001", "filtered_vcf", "snpeff_001", "vcf")
    assert _has_edge(workflow, "filter_001", "filtered_vcf", "vcf_stats_001", "vcf")
    assert _has_edge(workflow, "vcf_stats_001", "stats_image", "variant_report_001", "images")
    assert _has_edge(workflow, "snpeff_001", "annotated_vcf", "variant_report_001", "tables")
    assert next(node for node in workflow["nodes"] if node["id"] == "vcf_stats_001")["params"]["format"] == "png"
    assert workflow["outputs"]["vcf"] == "snpeff_001"
    assert workflow["outputs"]["variant_stats"] == "vcf_stats_001"


def test_fastq_qc_template_validates_and_gates_multiqc_report_before_preview() -> None:
    workflow = _load_template("fastq_qc_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["validate_multiqc_001"] == "data_validator"
    assert node_types["gate_multiqc_001"] == "gate"
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_multiqc_001")
    gate = next(node for node in workflow["nodes"] if node["id"] == "gate_multiqc_001")
    assert validator["params"]["expected_format"] == "text"
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert gate["params"]["condition_mode"] == "boolean_is_true"
    assert gate["params"]["on_fail"] == "halt"
    assert _has_edge(workflow, "multiqc_001", "report", "validate_multiqc_001", "input")
    assert _has_edge(workflow, "validate_multiqc_001", "passed", "gate_multiqc_001", "value")
    assert _has_edge(workflow, "validate_multiqc_001", "passthrough", "html_preview_001", "file")
    assert workflow["outputs"]["validated_report"] == "validate_multiqc_001"


def test_phylogenetics_template_renders_tree_and_adds_report() -> None:
    workflow = _load_template("phylogenetics_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["tree_viewer_001"] == "phylo_tree_viewer"
    assert node_types["phylo_report_001"] == "html_report"
    tree_viewer = next(node for node in workflow["nodes"] if node["id"] == "tree_viewer_001")
    assert tree_viewer["params"]["format"] == "png"
    assert tree_viewer["params"]["layout"] == "rectangular"
    assert _has_edge(workflow, "iqtree_001", "tree", "tree_viewer_001", "tree_file")
    assert _has_edge(workflow, "tree_viewer_001", "tree_image", "phylo_report_001", "images")
    assert _has_edge(workflow, "mafft_001", "alignment", "phylo_report_001", "tables")
    assert workflow["outputs"]["tree_image"] == "tree_viewer_001"
    assert workflow["outputs"]["report"] == "phylo_report_001"


def test_rna_seq_template_adds_alignment_qc_dashboard() -> None:
    workflow = _load_template("rna_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["qualimap_001"] == "qualimap"
    assert node_types["flagstat_001"] == "samtools_flagstat"
    assert node_types["qc_dashboard_001"] == "qc_dashboard"
    dashboard = next(node for node in workflow["nodes"] if node["id"] == "qc_dashboard_001")
    assert dashboard["params"]["run_name"] == "RNA-Seq QC"
    assert _has_edge(workflow, "sort_001", "sorted_bam", "qualimap_001", "bam")
    assert _has_edge(workflow, "annot_001", "annotation", "qualimap_001", "feature_file")
    assert _has_edge(workflow, "sort_001", "sorted_bam", "flagstat_001", "bam")
    assert _has_edge(workflow, "qc_001", "report_dir", "qc_dashboard_001", "fastqc_dir")
    assert _has_edge(workflow, "flagstat_001", "stats", "qc_dashboard_001", "alignment_stats")
    assert workflow["outputs"]["alignment_qc"] == "qualimap_001"
    assert workflow["outputs"]["qc_dashboard"] == "qc_dashboard_001"
    assert workflow["outputs"]["report"] == "qc_dashboard_001"


def test_deseq2_template_adds_volcano_ma_and_report_outputs() -> None:
    workflow = _load_template("deseq2_differential_expression.json")
    node_types = _node_types(workflow)

    assert node_types["volcano_001"] == "volcano_plot"
    assert node_types["ma_plot_001"] == "ma_plot"
    assert node_types["de_report_001"] == "html_report"
    volcano = next(node for node in workflow["nodes"] if node["id"] == "volcano_001")
    ma_plot = next(node for node in workflow["nodes"] if node["id"] == "ma_plot_001")
    assert volcano["params"]["format"] == "png"
    assert ma_plot["params"]["format"] == "png"
    assert _has_edge(workflow, "deseq2_001", "results_csv", "volcano_001", "results_table")
    assert _has_edge(workflow, "deseq2_001", "results_csv", "ma_plot_001", "results_table")
    assert _has_edge(workflow, "volcano_001", "volcano_image", "de_report_001", "images")
    assert _has_edge(workflow, "deseq2_001", "results_csv", "de_report_001", "tables")
    assert workflow["outputs"]["volcano_plot"] == "volcano_001"
    assert workflow["outputs"]["ma_plot"] == "ma_plot_001"
    assert workflow["outputs"]["report"] == "de_report_001"


def test_assembly_template_validates_spades_assembly_before_quast_and_prokka() -> None:
    workflow = _load_template("assembly_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["validate_assembly_001"] == "data_validator"
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_assembly_001")
    assert validator["params"]["expected_format"] == "fasta"
    assert validator["params"]["min_records"] >= 1
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "spades_001", "assembly", "validate_assembly_001", "input")
    assert _has_edge(workflow, "validate_assembly_001", "passthrough", "quast_001", "assembly")
    assert _has_edge(workflow, "validate_assembly_001", "passthrough", "prokka_001", "assembly")
    assert workflow["outputs"]["validated_assembly"] == "validate_assembly_001"
