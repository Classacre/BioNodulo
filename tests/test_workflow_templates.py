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
    assert _has_edge(workflow, "gate_prioritized_vcf_001", "output", "variant_report_001", "tables")
    assert next(node for node in workflow["nodes"] if node["id"] == "vcf_stats_001")["params"]["format"] == "png"
    assert workflow["outputs"]["vcf"] == "prioritize_vcf_001"
    assert workflow["outputs"]["variant_stats"] == "vcf_stats_001"


def test_variant_calling_template_validates_reference_before_alignment_and_calling() -> None:
    workflow = _load_template("variant_calling_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["validate_reference_001"] == "data_validator"
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_reference_001")
    assert validator["params"]["expected_format"] == "fasta"
    assert validator["params"]["min_records"] >= 1
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "ref_001", "reference", "validate_reference_001", "input")
    assert _has_edge(workflow, "validate_reference_001", "passthrough", "bwa_idx_001", "reference")
    assert _has_edge(workflow, "validate_reference_001", "passthrough", "gatk_001", "reference")
    assert not _has_edge(workflow, "ref_001", "reference", "bwa_idx_001", "reference")
    assert not _has_edge(workflow, "ref_001", "reference", "gatk_001", "reference")
    assert workflow["outputs"]["validated_reference"] == "validate_reference_001"


def test_variant_calling_template_validates_reads_before_alignment_and_qc() -> None:
    workflow = _load_template("variant_calling_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["validate_reads_001"] == "data_validator"
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_reads_001")
    assert validator["params"]["expected_format"] == "fastq"
    assert validator["params"]["min_records"] >= 1
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "reads_001", "reads", "validate_reads_001", "input")
    assert _has_edge(workflow, "validate_reads_001", "passthrough", "bwa_001", "reads")
    assert _has_edge(workflow, "validate_reads_001", "passthrough", "qc_001", "reads")
    assert not _has_edge(workflow, "reads_001", "reads", "bwa_001", "reads")
    assert not _has_edge(workflow, "reads_001", "reads", "qc_001", "reads")
    assert workflow["outputs"]["validated_reads"] == "validate_reads_001"


def test_variant_calling_template_validates_multiqc_report_before_preview() -> None:
    workflow = _load_template("variant_calling_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["validate_multiqc_001"] == "data_validator"
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_multiqc_001")
    assert validator["params"]["expected_format"] == "text"
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "mqc_001", "report", "validate_multiqc_001", "input")
    assert _has_edge(workflow, "validate_multiqc_001", "passthrough", "html_preview_001", "file")
    assert not _has_edge(workflow, "mqc_001", "report", "html_preview_001", "file")
    assert workflow["outputs"]["validated_multiqc_report"] == "validate_multiqc_001"


def test_variant_calling_template_adds_coverage_plot_from_marked_bam() -> None:
    workflow = _load_template("variant_calling_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["coverage_plot_001"] == "coverage_plot"
    coverage = next(node for node in workflow["nodes"] if node["id"] == "coverage_plot_001")
    assert coverage["params"]["region"] == "Wildtype:1-50000"
    assert coverage["params"]["window_size"] == 100
    assert coverage["params"]["format"] == "png"
    assert _has_edge(workflow, "markdup_001", "marked_bam", "coverage_plot_001", "alignment")
    assert _has_edge(workflow, "coverage_plot_001", "coverage_image", "variant_report_001", "images")
    assert workflow["outputs"]["coverage_plot"] == "coverage_plot_001"


def test_variant_calling_template_prioritizes_annotated_variants() -> None:
    workflow = _load_template("variant_calling_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["prioritize_vcf_001"] == "filter_vcf"
    assert node_types["gate_prioritized_vcf_001"] == "gate"
    prioritizer = next(node for node in workflow["nodes"] if node["id"] == "prioritize_vcf_001")
    gate = next(node for node in workflow["nodes"] if node["id"] == "gate_prioritized_vcf_001")
    assert prioritizer["params"]["custom_filter"] == "INFO/ANN ~ 'HIGH|MODERATE'"
    assert prioritizer["params"]["pass_only"] is True
    assert prioritizer["params"]["output_type"] == "VCF_GZ"
    assert gate["params"]["condition_mode"] == "file_exists"
    assert gate["params"]["on_fail"] == "halt"
    assert "prioritized VCF" in gate["params"]["error_message"]
    assert _has_edge(workflow, "snpeff_001", "annotated_vcf", "prioritize_vcf_001", "vcf")
    assert _has_edge(workflow, "prioritize_vcf_001", "filtered_vcf", "gate_prioritized_vcf_001", "value")
    assert _has_edge(workflow, "gate_prioritized_vcf_001", "output", "variant_report_001", "tables")
    assert not _has_edge(workflow, "snpeff_001", "annotated_vcf", "variant_report_001", "tables")
    assert not _has_edge(workflow, "prioritize_vcf_001", "filtered_vcf", "variant_report_001", "tables")
    assert workflow["outputs"]["vcf"] == "prioritize_vcf_001"
    assert workflow["outputs"]["prioritized_vcf"] == "prioritize_vcf_001"
    assert workflow["outputs"]["prioritized_vcf_quality_gate"] == "gate_prioritized_vcf_001"


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
    assert _has_edge(workflow, "gate_prioritized_vcf_001", "output", "variant_report_001", "tables")
    assert next(node for node in workflow["nodes"] if node["id"] == "vcf_stats_001")["params"]["format"] == "png"
    assert workflow["outputs"]["vcf"] == "prioritize_vcf_001"
    assert workflow["outputs"]["variant_stats"] == "vcf_stats_001"


def test_wgs_variant_template_validates_reference_before_alignment_and_calling() -> None:
    workflow = _load_template("wgs_variant_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["validate_reference_001"] == "data_validator"
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_reference_001")
    assert validator["params"]["expected_format"] == "fasta"
    assert validator["params"]["min_records"] >= 1
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "ref_001", "reference", "validate_reference_001", "input")
    assert _has_edge(workflow, "validate_reference_001", "passthrough", "bwa_idx_001", "reference")
    assert _has_edge(workflow, "validate_reference_001", "passthrough", "fb_001", "reference")
    assert not _has_edge(workflow, "ref_001", "reference", "bwa_idx_001", "reference")
    assert not _has_edge(workflow, "ref_001", "reference", "fb_001", "reference")
    assert workflow["outputs"]["validated_reference"] == "validate_reference_001"


def test_wgs_variant_template_validates_reads_before_trimming_and_qc() -> None:
    workflow = _load_template("wgs_variant_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["validate_reads_001"] == "data_validator"
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_reads_001")
    assert validator["params"]["expected_format"] == "fastq"
    assert validator["params"]["min_records"] >= 1
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "reads_001", "reads", "validate_reads_001", "input")
    assert _has_edge(workflow, "validate_reads_001", "passthrough", "fastp_001", "reads")
    assert _has_edge(workflow, "validate_reads_001", "passthrough", "qc_001", "reads")
    assert not _has_edge(workflow, "reads_001", "reads", "fastp_001", "reads")
    assert not _has_edge(workflow, "reads_001", "reads", "qc_001", "reads")
    assert workflow["outputs"]["validated_reads"] == "validate_reads_001"


def test_wgs_variant_template_validates_multiqc_report_before_preview() -> None:
    workflow = _load_template("wgs_variant_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["validate_multiqc_001"] == "data_validator"
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_multiqc_001")
    assert validator["params"]["expected_format"] == "text"
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "mqc_001", "report", "validate_multiqc_001", "input")
    assert _has_edge(workflow, "validate_multiqc_001", "passthrough", "html_preview_001", "file")
    assert not _has_edge(workflow, "mqc_001", "report", "html_preview_001", "file")
    assert workflow["outputs"]["validated_multiqc_report"] == "validate_multiqc_001"


def test_wgs_variant_template_adds_coverage_plot_from_marked_bam() -> None:
    workflow = _load_template("wgs_variant_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["coverage_plot_001"] == "coverage_plot"
    coverage = next(node for node in workflow["nodes"] if node["id"] == "coverage_plot_001")
    assert coverage["params"]["region"] == "NC_000913.3:1-50000"
    assert coverage["params"]["window_size"] == 100
    assert coverage["params"]["format"] == "png"
    assert _has_edge(workflow, "markdup_001", "marked_bam", "coverage_plot_001", "alignment")
    assert _has_edge(workflow, "coverage_plot_001", "coverage_image", "variant_report_001", "images")
    assert workflow["outputs"]["coverage_plot"] == "coverage_plot_001"


def test_wgs_variant_template_prioritizes_annotated_variants() -> None:
    workflow = _load_template("wgs_variant_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["prioritize_vcf_001"] == "filter_vcf"
    assert node_types["gate_prioritized_vcf_001"] == "gate"
    prioritizer = next(node for node in workflow["nodes"] if node["id"] == "prioritize_vcf_001")
    gate = next(node for node in workflow["nodes"] if node["id"] == "gate_prioritized_vcf_001")
    assert prioritizer["params"]["custom_filter"] == "INFO/ANN ~ 'HIGH|MODERATE'"
    assert prioritizer["params"]["pass_only"] is True
    assert prioritizer["params"]["output_type"] == "VCF_GZ"
    assert gate["params"]["condition_mode"] == "file_exists"
    assert gate["params"]["on_fail"] == "halt"
    assert "prioritized VCF" in gate["params"]["error_message"]
    assert _has_edge(workflow, "snpeff_001", "annotated_vcf", "prioritize_vcf_001", "vcf")
    assert _has_edge(workflow, "prioritize_vcf_001", "filtered_vcf", "gate_prioritized_vcf_001", "value")
    assert _has_edge(workflow, "gate_prioritized_vcf_001", "output", "variant_report_001", "tables")
    assert not _has_edge(workflow, "snpeff_001", "annotated_vcf", "variant_report_001", "tables")
    assert not _has_edge(workflow, "prioritize_vcf_001", "filtered_vcf", "variant_report_001", "tables")
    assert workflow["outputs"]["vcf"] == "prioritize_vcf_001"
    assert workflow["outputs"]["prioritized_vcf"] == "prioritize_vcf_001"
    assert workflow["outputs"]["prioritized_vcf_quality_gate"] == "gate_prioritized_vcf_001"


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


def test_fastq_qc_template_adds_qc_dashboard() -> None:
    workflow = _load_template("fastq_qc_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["qc_dashboard_001"] == "qc_dashboard"
    assert node_types["qc_dashboard_preview_001"] == "html_preview"
    dashboard = next(node for node in workflow["nodes"] if node["id"] == "qc_dashboard_001")
    assert dashboard["params"]["run_name"] == "FastQ QC"
    assert dashboard["params"]["title"] == "FastQ QC Dashboard"
    assert dashboard["params"]["theme"] == "light"
    assert _has_edge(workflow, "fastqc_001", "report_dir", "qc_dashboard_001", "fastqc_dir")
    assert _has_edge(workflow, "qc_dashboard_001", "qc_dashboard", "qc_dashboard_preview_001", "file")
    assert workflow["outputs"]["qc_dashboard"] == "qc_dashboard_001"


def test_fastq_qc_template_trims_reads_before_fastqc() -> None:
    workflow = _load_template("fastq_qc_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["fastp_001"] == "fastp"
    fastp = next(node for node in workflow["nodes"] if node["id"] == "fastp_001")
    assert fastp["params"]["threads"] == 4
    assert _has_edge(workflow, "validate_reads_001", "passthrough", "fastp_001", "reads")
    assert _has_edge(workflow, "fastp_001", "trimmed_reads", "fastqc_001", "reads")
    assert not _has_edge(workflow, "input_fastq_001", "reads", "fastp_001", "reads")
    assert not _has_edge(workflow, "input_fastq_001", "reads", "fastqc_001", "reads")
    assert workflow["outputs"]["trimmed_reads"] == "fastp_001"


def test_fastq_qc_template_validates_input_reads_before_trimming() -> None:
    workflow = _load_template("fastq_qc_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["validate_reads_001"] == "data_validator"
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_reads_001")
    assert validator["params"]["expected_format"] == "fastq"
    assert validator["params"]["min_records"] >= 1
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "input_fastq_001", "reads", "validate_reads_001", "input")
    assert _has_edge(workflow, "validate_reads_001", "passthrough", "fastp_001", "reads")
    assert not _has_edge(workflow, "input_fastq_001", "reads", "fastp_001", "reads")
    assert workflow["outputs"]["validated_reads"] == "validate_reads_001"


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


def test_phylogenetics_template_validates_input_fasta_before_alignment() -> None:
    workflow = _load_template("phylogenetics_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["ncbi_efetch_001"] == "ncbi_efetch"
    assert node_types["validate_fasta_001"] == "data_validator"
    efetch = next(node for node in workflow["nodes"] if node["id"] == "ncbi_efetch_001")
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_fasta_001")
    assert efetch["params"]["database"] == "nuccore"
    assert efetch["params"]["rettype"] == "fasta"
    assert efetch["params"]["retmode"] == "text"
    assert efetch["params"]["id_list"] == "NR_024570.1,NR_027552.1,NR_036781.1,NR_026078.1,NR_028747.1"
    assert efetch["params"]["output_name"] == "16s_sequences.fasta"
    assert validator["params"]["expected_format"] == "fasta"
    assert validator["params"]["min_records"] >= 3
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "ncbi_efetch_001", "records", "validate_fasta_001", "input")
    assert _has_edge(workflow, "validate_fasta_001", "passthrough", "mafft_001", "input")
    assert not _has_edge(workflow, "seqs_001", "reference", "validate_fasta_001", "input")
    assert not _has_edge(workflow, "seqs_001", "reference", "mafft_001", "input")
    assert workflow["outputs"]["fetched_fasta"] == "ncbi_efetch_001"
    assert workflow["outputs"]["validated_fasta"] == "validate_fasta_001"


def test_phylogenetics_template_gates_validated_fasta_before_alignment() -> None:
    workflow = _load_template("phylogenetics_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["gate_fasta_001"] == "gate"
    gate = next(node for node in workflow["nodes"] if node["id"] == "gate_fasta_001")
    assert gate["params"]["condition_mode"] == "boolean_is_true"
    assert gate["params"]["on_fail"] == "halt"
    assert "FASTA validation failed" in gate["params"]["error_message"]
    assert _has_edge(workflow, "validate_fasta_001", "passed", "gate_fasta_001", "value")
    assert workflow["outputs"]["fasta_quality_gate"] == "gate_fasta_001"


def test_rna_seq_template_adds_alignment_qc_dashboard() -> None:
    workflow = _load_template("rna_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["qualimap_001"] == "qualimap"
    assert node_types["flagstat_001"] == "samtools_flagstat"
    assert node_types["qc_dashboard_001"] == "qc_dashboard"
    dashboard = next(node for node in workflow["nodes"] if node["id"] == "qc_dashboard_001")
    assert dashboard["params"]["run_name"] == "RNA-Seq QC"
    assert _has_edge(workflow, "sort_001", "sorted_bam", "qualimap_001", "bam")
    assert _has_edge(workflow, "validate_annotation_001", "passthrough", "qualimap_001", "feature_file")
    assert _has_edge(workflow, "sort_001", "sorted_bam", "flagstat_001", "bam")
    assert _has_edge(workflow, "qc_001", "report_dir", "qc_dashboard_001", "fastqc_dir")
    assert _has_edge(workflow, "flagstat_001", "stats", "qc_dashboard_001", "alignment_stats")
    assert workflow["outputs"]["alignment_qc"] == "qualimap_001"
    assert workflow["outputs"]["qc_dashboard"] == "qc_dashboard_001"
    assert workflow["outputs"]["report"] == "qc_dashboard_001"


def test_rna_seq_template_aggregates_alignment_stats_in_multiqc() -> None:
    workflow = _load_template("rna_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["flagstat_001"] == "samtools_flagstat"
    assert node_types["mqc_001"] == "multiqc"
    assert _has_edge(workflow, "flagstat_001", "stats", "mqc_001", "reports")


def test_rna_seq_template_validates_multiqc_report_before_preview() -> None:
    workflow = _load_template("rna_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["validate_multiqc_001"] == "data_validator"
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_multiqc_001")
    assert validator["params"]["expected_format"] == "text"
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "mqc_001", "report", "validate_multiqc_001", "input")
    assert _has_edge(workflow, "validate_multiqc_001", "passthrough", "html_preview_001", "file")
    assert not _has_edge(workflow, "mqc_001", "report", "html_preview_001", "file")
    assert workflow["outputs"]["validated_multiqc_report"] == "validate_multiqc_001"


def test_rna_seq_template_validates_reference_fasta_before_indexing() -> None:
    workflow = _load_template("rna_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["validate_reference_001"] == "data_validator"
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_reference_001")
    assert validator["params"]["expected_format"] == "fasta"
    assert validator["params"]["min_records"] >= 1
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "ref_001", "reference", "validate_reference_001", "input")
    assert _has_edge(workflow, "validate_reference_001", "passthrough", "hisat2_build_001", "reference")
    assert not _has_edge(workflow, "ref_001", "reference", "hisat2_build_001", "reference")
    assert workflow["outputs"]["validated_reference"] == "validate_reference_001"


def test_rna_seq_template_validates_reads_before_trimming_and_qc() -> None:
    workflow = _load_template("rna_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["validate_reads_001"] == "data_validator"
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_reads_001")
    assert validator["params"]["expected_format"] == "fastq"
    assert validator["params"]["min_records"] >= 1
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "reads_001", "reads", "validate_reads_001", "input")
    assert _has_edge(workflow, "validate_reads_001", "passthrough", "fastp_001", "reads")
    assert _has_edge(workflow, "validate_reads_001", "passthrough", "qc_001", "reads")
    assert not _has_edge(workflow, "reads_001", "reads", "fastp_001", "reads")
    assert not _has_edge(workflow, "reads_001", "reads", "qc_001", "reads")
    assert workflow["outputs"]["validated_reads"] == "validate_reads_001"


def test_rna_seq_template_gates_trimmed_reads_before_alignment() -> None:
    workflow = _load_template("rna_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["gate_trimmed_reads_001"] == "gate"
    gate = next(node for node in workflow["nodes"] if node["id"] == "gate_trimmed_reads_001")
    assert gate["params"]["condition_mode"] == "is_not_empty"
    assert gate["params"]["on_fail"] == "halt"
    assert "trimmed reads" in gate["params"]["error_message"]
    assert _has_edge(workflow, "fastp_001", "trimmed_reads", "gate_trimmed_reads_001", "value")
    assert _has_edge(workflow, "gate_trimmed_reads_001", "output", "hisat2_001", "reads")
    assert not _has_edge(workflow, "fastp_001", "trimmed_reads", "hisat2_001", "reads")
    assert workflow["outputs"]["trimmed_reads_quality_gate"] == "gate_trimmed_reads_001"


def test_rna_seq_template_validates_annotation_before_counts_and_alignment_qc() -> None:
    workflow = _load_template("rna_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["validate_annotation_001"] == "data_validator"
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_annotation_001")
    assert validator["params"]["expected_format"] == "text"
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "annot_001", "annotation", "validate_annotation_001", "input")
    assert _has_edge(workflow, "validate_annotation_001", "passthrough", "counts_001", "gtf")
    assert _has_edge(workflow, "validate_annotation_001", "passthrough", "qualimap_001", "feature_file")
    assert not _has_edge(workflow, "annot_001", "annotation", "counts_001", "gtf")
    assert not _has_edge(workflow, "annot_001", "annotation", "qualimap_001", "feature_file")
    assert workflow["outputs"]["validated_annotation"] == "validate_annotation_001"


def test_rna_seq_template_normalizes_featurecounts_output() -> None:
    workflow = _load_template("rna_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["normalize_counts_001"] == "normalize_data"
    normalizer = next(node for node in workflow["nodes"] if node["id"] == "normalize_counts_001")
    assert normalizer["params"]["method"] == "cpm"
    assert normalizer["params"]["id_columns"] == "Geneid"
    assert normalizer["params"]["axis"] == "rows"
    assert normalizer["params"]["output_type"] == "TSV"
    assert _has_edge(workflow, "counts_001", "counts", "normalize_counts_001", "table")
    assert workflow["outputs"]["normalized_counts"] == "normalize_counts_001"


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


def test_deseq2_template_extracts_significant_genes() -> None:
    workflow = _load_template("deseq2_differential_expression.json")
    node_types = _node_types(workflow)

    assert node_types["significant_genes_001"] == "filter_rows"
    filter_node = next(node for node in workflow["nodes"] if node["id"] == "significant_genes_001")
    assert filter_node["params"]["column"] == "padj"
    assert filter_node["params"]["operator"] == "less_or_equal"
    assert filter_node["params"]["value"] == "0.05"
    assert filter_node["params"]["column_2"] == "log2FoldChange"
    assert filter_node["params"]["operator_2"] == "is_not_empty"
    assert filter_node["params"]["logical_op"] == "AND"
    assert filter_node["params"]["output_type"] == "CSV"
    assert _has_edge(workflow, "deseq2_001", "results_csv", "significant_genes_001", "table")
    assert _has_edge(workflow, "significant_genes_001", "filtered_table", "de_report_001", "tables")
    assert workflow["outputs"]["significant_genes"] == "significant_genes_001"


def test_deseq2_template_validates_count_matrix_and_sample_info_before_analysis() -> None:
    workflow = _load_template("deseq2_differential_expression.json")
    node_types = _node_types(workflow)

    assert node_types["validate_counts_001"] == "data_validator"
    assert node_types["validate_samples_001"] == "data_validator"
    counts_validator = next(node for node in workflow["nodes"] if node["id"] == "validate_counts_001")
    samples_validator = next(node for node in workflow["nodes"] if node["id"] == "validate_samples_001")
    assert counts_validator["params"]["expected_format"] == "csv"
    assert counts_validator["params"]["min_records"] >= 1
    assert counts_validator["params"]["min_size_bytes"] > 0
    assert counts_validator["params"]["fail_on_error"] is True
    assert samples_validator["params"]["expected_format"] == "csv"
    assert samples_validator["params"]["min_records"] >= 2
    assert samples_validator["params"]["required_fields"] == "sample,condition"
    assert samples_validator["params"]["min_size_bytes"] > 0
    assert samples_validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "counts_001", "file", "validate_counts_001", "input")
    assert _has_edge(workflow, "validate_counts_001", "passthrough", "deseq2_001", "count_matrix")
    assert _has_edge(workflow, "samples_001", "file", "validate_samples_001", "input")
    assert _has_edge(workflow, "validate_samples_001", "passthrough", "deseq2_001", "sample_info")
    assert not _has_edge(workflow, "counts_001", "file", "deseq2_001", "count_matrix")
    assert not _has_edge(workflow, "samples_001", "file", "deseq2_001", "sample_info")
    assert workflow["outputs"]["validated_counts"] == "validate_counts_001"
    assert workflow["outputs"]["validated_sample_info"] == "validate_samples_001"


def test_r_visualization_template_validates_heatmap_csv_before_pheatmap() -> None:
    workflow = _load_template("r_visualization_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["validate_heatmap_csv_001"] == "data_validator"
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_heatmap_csv_001")
    assert validator["params"]["expected_format"] == "csv"
    assert validator["params"]["min_records"] >= 1
    assert validator["params"]["required_fields"] == "gene"
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "heatmap_data_001", "file", "validate_heatmap_csv_001", "input")
    assert _has_edge(workflow, "validate_heatmap_csv_001", "passthrough", "pheatmap_001", "data_csv")
    assert not _has_edge(workflow, "heatmap_data_001", "file", "pheatmap_001", "data_csv")
    assert workflow["outputs"]["validated_heatmap_data"] == "validate_heatmap_csv_001"


def test_r_visualization_template_combines_plots_into_html_report() -> None:
    workflow = _load_template("r_visualization_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["viz_report_001"] == "html_report"
    report = next(node for node in workflow["nodes"] if node["id"] == "viz_report_001")
    assert report["params"]["title"] == "R Visualization Report"
    assert "Sequencing depth" in report["params"]["text_sections"]
    assert report["params"]["section_names"] == "QC plot,Expression plot,Heatmap"
    assert _has_edge(workflow, "qc_plot_001", "plot_png", "viz_report_001", "images")
    assert _has_edge(workflow, "expr_plot_001", "plot_png", "viz_report_001", "images")
    assert _has_edge(workflow, "pheatmap_001", "plot_png", "viz_report_001", "images")
    assert workflow["outputs"]["report"] == "viz_report_001"


def test_biopython_template_validates_input_fastas_before_sequence_tools() -> None:
    workflow = _load_template("biopython_analysis_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["ncbi_efetch_001"] == "ncbi_efetch"
    assert node_types["validate_sequences_001"] == "data_validator"
    assert node_types["validate_coding_001"] == "data_validator"
    efetch = next(node for node in workflow["nodes"] if node["id"] == "ncbi_efetch_001")
    sequences_validator = next(node for node in workflow["nodes"] if node["id"] == "validate_sequences_001")
    coding_validator = next(node for node in workflow["nodes"] if node["id"] == "validate_coding_001")
    assert efetch["params"]["database"] == "nuccore"
    assert efetch["params"]["rettype"] == "fasta"
    assert efetch["params"]["retmode"] == "text"
    assert sequences_validator["params"]["expected_format"] == "fasta"
    assert sequences_validator["params"]["min_records"] >= 2
    assert sequences_validator["params"]["min_size_bytes"] > 0
    assert sequences_validator["params"]["fail_on_error"] is True
    assert coding_validator["params"]["expected_format"] == "fasta"
    assert coding_validator["params"]["min_records"] >= 1
    assert coding_validator["params"]["min_size_bytes"] > 0
    assert coding_validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "ncbi_efetch_001", "records", "validate_sequences_001", "input")
    assert _has_edge(workflow, "validate_sequences_001", "passthrough", "seqio_read_001", "input_file")
    assert _has_edge(workflow, "validate_sequences_001", "passthrough", "seq_stats_001", "input_file")
    assert _has_edge(workflow, "validate_sequences_001", "passthrough", "blast_001", "query")
    assert _has_edge(workflow, "validate_sequences_001", "passthrough", "blast_001", "subject")
    assert _has_edge(workflow, "coding_001", "reference", "validate_coding_001", "input")
    assert _has_edge(workflow, "validate_coding_001", "passthrough", "translate_001", "input_file")
    assert _has_edge(workflow, "validate_coding_001", "passthrough", "biostrings_001", "input_fasta")
    assert not _has_edge(workflow, "seqs_001", "reference", "validate_sequences_001", "input")
    assert not _has_edge(workflow, "seqs_001", "reference", "seqio_read_001", "input_file")
    assert not _has_edge(workflow, "seqs_001", "reference", "seq_stats_001", "input_file")
    assert not _has_edge(workflow, "seqs_001", "reference", "blast_001", "query")
    assert not _has_edge(workflow, "seqs_001", "reference", "blast_001", "subject")
    assert not _has_edge(workflow, "coding_001", "reference", "translate_001", "input_file")
    assert not _has_edge(workflow, "coding_001", "reference", "biostrings_001", "input_fasta")
    assert workflow["outputs"]["fetched_fasta"] == "ncbi_efetch_001"
    assert workflow["outputs"]["validated_sequences"] == "validate_sequences_001"
    assert workflow["outputs"]["validated_coding_sequences"] == "validate_coding_001"


def test_biopython_template_adds_sequence_stats_chart_report() -> None:
    workflow = _load_template("biopython_analysis_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["seq_length_chart_001"] == "bar_chart"
    assert node_types["sequence_report_001"] == "html_report"
    chart = next(node for node in workflow["nodes"] if node["id"] == "seq_length_chart_001")
    report = next(node for node in workflow["nodes"] if node["id"] == "sequence_report_001")
    assert chart["params"]["x_column"] == "id"
    assert chart["params"]["y_column"] == "length"
    assert chart["params"]["orientation"] == "horizontal"
    assert chart["params"]["format"] == "png"
    assert report["params"]["section_names"] == "Sequence length chart,Sequence statistics"
    assert _has_edge(workflow, "seq_stats_001", "stats_tsv", "seq_length_chart_001", "table")
    assert _has_edge(workflow, "seq_length_chart_001", "chart_image", "sequence_report_001", "images")
    assert _has_edge(workflow, "seq_stats_001", "stats_tsv", "sequence_report_001", "tables")
    assert workflow["outputs"]["sequence_length_chart"] == "seq_length_chart_001"
    assert workflow["outputs"]["report"] == "sequence_report_001"


def test_differential_expression_template_validates_transcriptome_before_indexing() -> None:
    workflow = _load_template("differential_expression.json")
    node_types = _node_types(workflow)

    assert node_types["validate_transcriptome_001"] == "data_validator"
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_transcriptome_001")
    assert validator["params"]["expected_format"] == "fasta"
    assert validator["params"]["min_records"] >= 1
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "tx_001", "reference", "validate_transcriptome_001", "input")
    assert _has_edge(workflow, "validate_transcriptome_001", "passthrough", "salmon_idx_001", "transcripts")
    assert _has_edge(workflow, "validate_transcriptome_001", "passthrough", "kallisto_idx_001", "transcripts")
    assert not _has_edge(workflow, "tx_001", "reference", "salmon_idx_001", "transcripts")
    assert not _has_edge(workflow, "tx_001", "reference", "kallisto_idx_001", "transcripts")
    assert workflow["outputs"]["validated_transcriptome"] == "validate_transcriptome_001"


def test_differential_expression_template_validates_reads_before_quantification() -> None:
    workflow = _load_template("differential_expression.json")
    node_types = _node_types(workflow)

    assert node_types["validate_reads_001"] == "data_validator"
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_reads_001")
    assert validator["params"]["expected_format"] == "fastq"
    assert validator["params"]["min_records"] >= 1
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "reads_001", "reads", "validate_reads_001", "input")
    assert _has_edge(workflow, "validate_reads_001", "passthrough", "salmon_quant_001", "reads")
    assert _has_edge(workflow, "validate_reads_001", "passthrough", "kallisto_quant_001", "reads")
    assert not _has_edge(workflow, "reads_001", "reads", "salmon_quant_001", "reads")
    assert not _has_edge(workflow, "reads_001", "reads", "kallisto_quant_001", "reads")
    assert workflow["outputs"]["validated_reads"] == "validate_reads_001"


def test_differential_expression_template_is_labeled_as_transcript_quantification() -> None:
    workflow = _load_template("differential_expression.json")
    note = next(node for node in workflow["nodes"] if node["id"] == "note_differential_expression")
    note_text = note["params"]["text"]

    assert workflow["name"] == "Transcript Quantification"
    assert "transcript quantification" in workflow["description"].lower()
    assert "differential expression" not in workflow["description"].lower()
    assert "Transcript quantification" in note_text
    assert "DESeq2/edgeR" not in note_text


def test_differential_expression_template_aggregates_both_quantifiers_in_multiqc() -> None:
    workflow = _load_template("differential_expression.json")
    node_types = _node_types(workflow)

    assert node_types["mqc_001"] == "multiqc"
    assert _has_edge(workflow, "salmon_quant_001", "counts", "mqc_001", "reports")
    assert _has_edge(workflow, "kallisto_quant_001", "abundance", "mqc_001", "reports")
    assert _has_edge(workflow, "mqc_001", "report", "validate_multiqc_001", "input")
    assert workflow["outputs"]["report"] == "mqc_001"


def test_differential_expression_template_validates_multiqc_report_before_preview() -> None:
    workflow = _load_template("differential_expression.json")
    node_types = _node_types(workflow)

    assert node_types["validate_multiqc_001"] == "data_validator"
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_multiqc_001")
    assert validator["params"]["expected_format"] == "text"
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "mqc_001", "report", "validate_multiqc_001", "input")
    assert _has_edge(workflow, "validate_multiqc_001", "passthrough", "html_preview_001", "file")
    assert not _has_edge(workflow, "mqc_001", "report", "html_preview_001", "file")
    assert workflow["outputs"]["validated_multiqc_report"] == "validate_multiqc_001"


def test_differential_expression_template_adds_quantification_html_report() -> None:
    workflow = _load_template("differential_expression.json")
    node_types = _node_types(workflow)

    assert node_types["quant_report_001"] == "html_report"
    assert node_types["quant_report_preview_001"] == "html_preview"
    report = next(node for node in workflow["nodes"] if node["id"] == "quant_report_001")
    assert report["params"]["title"] == "Transcript Quantification Report"
    assert report["params"]["section_names"] == "Salmon quantification,Kallisto abundance"
    assert report["params"]["max_table_rows"] == 100
    assert _has_edge(workflow, "salmon_quant_001", "counts", "quant_report_001", "tables")
    assert _has_edge(workflow, "kallisto_quant_001", "abundance", "quant_report_001", "tables")
    assert _has_edge(workflow, "quant_report_001", "html_report", "quant_report_preview_001", "file")
    assert workflow["outputs"]["quantification_report"] == "quant_report_001"


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
    assert _has_edge(workflow, "validate_assembly_001", "passthrough", "gate_assembly_001", "value")
    assert not _has_edge(workflow, "spades_001", "assembly", "quast_001", "assembly")
    assert not _has_edge(workflow, "spades_001", "assembly", "prokka_001", "assembly")
    assert workflow["outputs"]["validated_assembly"] == "validate_assembly_001"


def test_assembly_template_adds_megahit_switch_alternative() -> None:
    workflow = _load_template("assembly_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["switch_assembler_001"] == "switch"
    assert node_types["megahit_001"] == "megahit"
    switch = next(node for node in workflow["nodes"] if node["id"] == "switch_assembler_001")
    megahit = next(node for node in workflow["nodes"] if node["id"] == "megahit_001")
    assert switch["params"]["value"] == "spades"
    assert switch["params"]["cases"] == "spades,megahit"
    assert switch["params"]["num_branches"] == 2
    assert megahit["params"]["threads"] == 8
    assert megahit["params"]["min_contig_len"] == 200

    assert _has_edge(workflow, "fastp_001", "trimmed_reads", "switch_assembler_001", "passthrough_data")
    assert _has_edge(workflow, "switch_assembler_001", "output_1", "spades_001", "reads")
    assert _has_edge(workflow, "switch_assembler_001", "output_2", "megahit_001", "reads")
    assert _has_edge(workflow, "spades_001", "assembly", "validate_assembly_001", "input")
    assert _has_edge(workflow, "megahit_001", "contigs", "validate_assembly_001", "input")
    assert not _has_edge(workflow, "fastp_001", "trimmed_reads", "spades_001", "reads")
    assert workflow["outputs"]["assembler_switch"] == "switch_assembler_001"
    assert workflow["outputs"]["megahit_assembly"] == "megahit_001"


def test_assembly_template_gates_validated_assembly_before_quast_and_prokka() -> None:
    workflow = _load_template("assembly_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["gate_assembly_001"] == "gate"
    gate = next(node for node in workflow["nodes"] if node["id"] == "gate_assembly_001")
    assert gate["params"]["condition_mode"] == "file_exists"
    assert gate["params"]["on_fail"] == "halt"
    assert "assembly validation failed" in gate["params"]["error_message"]
    assert _has_edge(workflow, "validate_assembly_001", "passthrough", "gate_assembly_001", "value")
    assert _has_edge(workflow, "gate_assembly_001", "output", "quast_001", "assembly")
    assert _has_edge(workflow, "gate_assembly_001", "output", "prokka_001", "assembly")
    assert not _has_edge(workflow, "validate_assembly_001", "passthrough", "quast_001", "assembly")
    assert not _has_edge(workflow, "validate_assembly_001", "passthrough", "prokka_001", "assembly")
    assert workflow["outputs"]["assembly_quality_gate"] == "gate_assembly_001"


def test_assembly_template_validates_reads_before_trimming() -> None:
    workflow = _load_template("assembly_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["validate_reads_001"] == "data_validator"
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_reads_001")
    assert validator["params"]["expected_format"] == "fastq"
    assert validator["params"]["min_records"] >= 1
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "reads_001", "reads", "validate_reads_001", "input")
    assert _has_edge(workflow, "validate_reads_001", "passthrough", "fastp_001", "reads")
    assert _has_edge(workflow, "fastp_001", "trimmed_reads", "switch_assembler_001", "passthrough_data")
    assert not _has_edge(workflow, "reads_001", "reads", "fastp_001", "reads")
    assert not _has_edge(workflow, "reads_001", "reads", "spades_001", "reads")
    assert not _has_edge(workflow, "fastp_001", "trimmed_reads", "spades_001", "reads")
    assert workflow["outputs"]["validated_reads"] == "validate_reads_001"


def test_assembly_template_validates_reference_before_quast() -> None:
    workflow = _load_template("assembly_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["validate_reference_001"] == "data_validator"
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_reference_001")
    assert validator["params"]["expected_format"] == "fasta"
    assert validator["params"]["min_records"] >= 1
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "ref_001", "reference", "validate_reference_001", "input")
    assert _has_edge(workflow, "validate_reference_001", "passthrough", "quast_001", "reference")
    assert not _has_edge(workflow, "ref_001", "reference", "quast_001", "reference")
    assert workflow["outputs"]["validated_reference"] == "validate_reference_001"


def test_assembly_template_adds_annotation_html_report() -> None:
    workflow = _load_template("assembly_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["assembly_report_001"] == "html_report"
    report = next(node for node in workflow["nodes"] if node["id"] == "assembly_report_001")
    assert report["params"]["title"] == "Assembly Annotation Report"
    assert report["params"]["section_names"] == "Prokka annotation"
    assert _has_edge(workflow, "prokka_001", "gff", "assembly_report_001", "tables")
    assert workflow["outputs"]["report"] == "assembly_report_001"


def test_assembly_template_validates_quast_report_before_preview() -> None:
    workflow = _load_template("assembly_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["validate_quast_001"] == "data_validator"
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_quast_001")
    assert validator["params"]["expected_format"] == "text"
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "quast_001", "report", "validate_quast_001", "input")
    assert _has_edge(workflow, "validate_quast_001", "passthrough", "html_preview_001", "file")
    assert not _has_edge(workflow, "quast_001", "report", "html_preview_001", "file")
    assert workflow["outputs"]["validated_quast_report"] == "validate_quast_001"


def test_chip_seq_template_trims_reads_before_alignment_and_qc() -> None:
    workflow = _load_template("chip_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["fastp_001"] == "fastp"
    fastp = next(node for node in workflow["nodes"] if node["id"] == "fastp_001")
    assert fastp["params"]["threads"] == 4
    assert _has_edge(workflow, "validate_reads_001", "passthrough", "fastp_001", "reads")
    assert _has_edge(workflow, "fastp_001", "trimmed_reads", "gate_trimmed_reads_001", "value")
    assert not _has_edge(workflow, "treat_001", "reads", "fastp_001", "reads")
    assert not _has_edge(workflow, "treat_001", "reads", "bt2_001", "reads")
    assert not _has_edge(workflow, "treat_001", "reads", "qc_001", "reads")
    assert workflow["outputs"]["trimmed_reads"] == "fastp_001"


def test_chip_seq_template_gates_trimmed_reads_before_alignment_and_qc() -> None:
    workflow = _load_template("chip_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["gate_trimmed_reads_001"] == "gate"
    gate = next(node for node in workflow["nodes"] if node["id"] == "gate_trimmed_reads_001")
    assert gate["params"]["condition_mode"] == "is_not_empty"
    assert gate["params"]["on_fail"] == "halt"
    assert "trimmed reads" in gate["params"]["error_message"]
    assert _has_edge(workflow, "fastp_001", "trimmed_reads", "gate_trimmed_reads_001", "value")
    assert _has_edge(workflow, "gate_trimmed_reads_001", "output", "bt2_001", "reads")
    assert _has_edge(workflow, "gate_trimmed_reads_001", "output", "qc_001", "reads")
    assert not _has_edge(workflow, "fastp_001", "trimmed_reads", "bt2_001", "reads")
    assert not _has_edge(workflow, "fastp_001", "trimmed_reads", "qc_001", "reads")
    assert workflow["outputs"]["trimmed_reads_quality_gate"] == "gate_trimmed_reads_001"


def test_chip_seq_template_validates_input_reads_before_trimming() -> None:
    workflow = _load_template("chip_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["validate_reads_001"] == "data_validator"
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_reads_001")
    assert validator["params"]["expected_format"] == "fastq"
    assert validator["params"]["min_records"] >= 1
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "treat_001", "reads", "validate_reads_001", "input")
    assert _has_edge(workflow, "validate_reads_001", "passthrough", "fastp_001", "reads")
    assert not _has_edge(workflow, "treat_001", "reads", "fastp_001", "reads")
    assert workflow["outputs"]["validated_reads"] == "validate_reads_001"


def test_chip_seq_template_adds_control_sample_for_macs2() -> None:
    workflow = _load_template("chip_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["control_001"] == "input_fastq"
    assert node_types["validate_control_reads_001"] == "data_validator"
    assert node_types["fastp_control_001"] == "fastp"
    assert node_types["gate_control_reads_001"] == "gate"
    assert node_types["bt2_control_001"] == "bowtie2_align"
    assert node_types["view_control_001"] == "samtools_view"
    assert node_types["sort_control_001"] == "samtools_sort"

    control = next(node for node in workflow["nodes"] if node["id"] == "control_001")
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_control_reads_001")
    gate = next(node for node in workflow["nodes"] if node["id"] == "gate_control_reads_001")
    assert control["params"]["sample_name"] == "control"
    assert validator["params"]["expected_format"] == "fastq"
    assert validator["params"]["fail_on_error"] is True
    assert gate["params"]["condition_mode"] == "is_not_empty"
    assert gate["params"]["on_fail"] == "halt"

    assert _has_edge(workflow, "control_001", "reads", "validate_control_reads_001", "input")
    assert _has_edge(workflow, "validate_control_reads_001", "passthrough", "fastp_control_001", "reads")
    assert _has_edge(workflow, "fastp_control_001", "trimmed_reads", "gate_control_reads_001", "value")
    assert _has_edge(workflow, "gate_control_reads_001", "output", "bt2_control_001", "reads")
    assert _has_edge(workflow, "validate_index_001", "passthrough", "bt2_control_001", "index")
    assert _has_edge(workflow, "bt2_control_001", "alignment", "view_control_001", "sam")
    assert _has_edge(workflow, "view_control_001", "bam", "sort_control_001", "bam")
    assert _has_edge(workflow, "sort_control_001", "sorted_bam", "macs2_001", "control")
    assert workflow["outputs"]["control_alignment"] == "sort_control_001"
    assert workflow["outputs"]["validated_control_reads"] == "validate_control_reads_001"


def test_chip_seq_template_validates_index_directory_before_alignment() -> None:
    workflow = _load_template("chip_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["validate_index_001"] == "data_validator"
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_index_001")
    assert validator["params"]["expected_format"] == "directory"
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "idx_001", "directory", "validate_index_001", "input")
    assert _has_edge(workflow, "validate_index_001", "passthrough", "bt2_001", "index")
    assert not _has_edge(workflow, "idx_001", "directory", "bt2_001", "index")
    assert workflow["outputs"]["validated_index"] == "validate_index_001"


def test_chip_seq_template_generates_bigwig_coverage_track() -> None:
    workflow = _load_template("chip_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["coverage_001"] == "deeptools_bamcoverage"
    coverage = next(node for node in workflow["nodes"] if node["id"] == "coverage_001")
    assert coverage["params"]["threads"] == 4
    assert coverage["params"]["normalize_using"] == "CPM"
    assert coverage["params"]["bin_size"] == 10
    assert coverage["params"]["ignore_duplicates"] is True
    assert _has_edge(workflow, "sort_001", "sorted_bam", "coverage_001", "bam")
    assert workflow["outputs"]["coverage_track"] == "coverage_001"


def test_chip_seq_template_validates_macs2_peak_output() -> None:
    workflow = _load_template("chip_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["validate_peaks_001"] == "data_validator"
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_peaks_001")
    assert validator["params"]["expected_format"] == "text"
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "macs2_001", "peaks", "validate_peaks_001", "input")
    assert workflow["outputs"]["validated_peaks"] == "validate_peaks_001"


def test_chip_seq_template_validates_multiqc_report_before_preview() -> None:
    workflow = _load_template("chip_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["validate_multiqc_001"] == "data_validator"
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_multiqc_001")
    assert validator["params"]["expected_format"] == "text"
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "mqc_001", "report", "validate_multiqc_001", "input")
    assert _has_edge(workflow, "validate_multiqc_001", "passthrough", "html_preview_001", "file")
    assert not _has_edge(workflow, "mqc_001", "report", "html_preview_001", "file")
    assert workflow["outputs"]["validated_multiqc_report"] == "validate_multiqc_001"


def test_metagenomics_template_adds_bracken_taxonomy_chart_report() -> None:
    workflow = _load_template("metagenomics_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["bracken_bar_001"] == "bar_chart"
    assert node_types["taxonomy_report_001"] == "html_report"
    chart = next(node for node in workflow["nodes"] if node["id"] == "bracken_bar_001")
    assert chart["params"]["x_column"] == "name"
    assert chart["params"]["y_column"] == "fraction_total_reads"
    assert chart["params"]["orientation"] == "horizontal"
    assert chart["params"]["format"] == "png"
    assert _has_edge(workflow, "validate_bracken_001", "passthrough", "bracken_bar_001", "table")
    assert _has_edge(workflow, "bracken_bar_001", "chart_image", "taxonomy_report_001", "images")
    assert _has_edge(workflow, "validate_bracken_001", "passthrough", "taxonomy_report_001", "tables")
    assert workflow["outputs"]["taxonomy_chart"] == "bracken_bar_001"
    assert workflow["outputs"]["taxonomy_report"] == "taxonomy_report_001"


def test_metagenomics_template_validates_reads_before_trimming_and_qc() -> None:
    workflow = _load_template("metagenomics_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["validate_reads_001"] == "data_validator"
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_reads_001")
    assert validator["params"]["expected_format"] == "fastq"
    assert validator["params"]["min_records"] >= 1
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "reads_001", "reads", "validate_reads_001", "input")
    assert _has_edge(workflow, "validate_reads_001", "passthrough", "fastp_001", "reads")
    assert _has_edge(workflow, "validate_reads_001", "passthrough", "qc_001", "reads")
    assert not _has_edge(workflow, "reads_001", "reads", "fastp_001", "reads")
    assert not _has_edge(workflow, "reads_001", "reads", "qc_001", "reads")
    assert workflow["outputs"]["validated_reads"] == "validate_reads_001"


def test_metagenomics_template_gates_trimmed_reads_before_profiling() -> None:
    workflow = _load_template("metagenomics_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["gate_trimmed_reads_001"] == "gate"
    gate = next(node for node in workflow["nodes"] if node["id"] == "gate_trimmed_reads_001")
    assert gate["params"]["condition_mode"] == "is_not_empty"
    assert gate["params"]["on_fail"] == "halt"
    assert "trimmed reads" in gate["params"]["error_message"]
    assert _has_edge(workflow, "fastp_001", "trimmed_reads", "gate_trimmed_reads_001", "value")
    assert _has_edge(workflow, "gate_trimmed_reads_001", "output", "kraken2_001", "reads")
    assert _has_edge(workflow, "gate_trimmed_reads_001", "output", "metaphlan_001", "reads")
    assert _has_edge(workflow, "gate_trimmed_reads_001", "output", "humann_001", "reads")
    assert not _has_edge(workflow, "fastp_001", "trimmed_reads", "kraken2_001", "reads")
    assert not _has_edge(workflow, "fastp_001", "trimmed_reads", "metaphlan_001", "reads")
    assert not _has_edge(workflow, "fastp_001", "trimmed_reads", "humann_001", "reads")
    assert workflow["outputs"]["trimmed_reads_quality_gate"] == "gate_trimmed_reads_001"


def test_metagenomics_template_validates_database_directory_before_profiling() -> None:
    workflow = _load_template("metagenomics_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["validate_db_001"] == "data_validator"
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_db_001")
    assert validator["params"]["expected_format"] == "directory"
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "db_001", "directory", "validate_db_001", "input")
    assert _has_edge(workflow, "validate_db_001", "passthrough", "kraken2_001", "db")
    assert _has_edge(workflow, "validate_db_001", "passthrough", "bracken_001", "db")
    assert not _has_edge(workflow, "db_001", "directory", "kraken2_001", "db")
    assert not _has_edge(workflow, "db_001", "directory", "bracken_001", "db")
    assert workflow["outputs"]["validated_db"] == "validate_db_001"


def test_metagenomics_template_validates_bracken_report_before_visualization() -> None:
    workflow = _load_template("metagenomics_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["validate_bracken_001"] == "data_validator"
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_bracken_001")
    assert validator["params"]["expected_format"] == "text"
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "bracken_001", "report", "validate_bracken_001", "input")
    assert _has_edge(workflow, "validate_bracken_001", "passthrough", "bracken_bar_001", "table")
    assert _has_edge(workflow, "validate_bracken_001", "passthrough", "taxonomy_report_001", "tables")
    assert not _has_edge(workflow, "bracken_001", "report", "bracken_bar_001", "table")
    assert not _has_edge(workflow, "bracken_001", "report", "taxonomy_report_001", "tables")
    assert workflow["outputs"]["validated_bracken_report"] == "validate_bracken_001"


def test_metagenomics_template_validates_multiqc_report_before_preview() -> None:
    workflow = _load_template("metagenomics_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["validate_multiqc_001"] == "data_validator"
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_multiqc_001")
    assert validator["params"]["expected_format"] == "text"
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "mqc_001", "report", "validate_multiqc_001", "input")
    assert _has_edge(workflow, "validate_multiqc_001", "passthrough", "html_preview_001", "file")
    assert not _has_edge(workflow, "mqc_001", "report", "html_preview_001", "file")
    assert workflow["outputs"]["validated_multiqc_report"] == "validate_multiqc_001"


def test_single_cell_template_validates_input_directories_before_cellranger() -> None:
    workflow = _load_template("single_cell_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["validate_fastq_dir_001"] == "data_validator"
    assert node_types["validate_reference_dir_001"] == "data_validator"
    fastq_validator = next(node for node in workflow["nodes"] if node["id"] == "validate_fastq_dir_001")
    ref_validator = next(node for node in workflow["nodes"] if node["id"] == "validate_reference_dir_001")
    assert fastq_validator["params"]["expected_format"] == "directory"
    assert ref_validator["params"]["expected_format"] == "directory"
    assert fastq_validator["params"]["min_size_bytes"] > 0
    assert ref_validator["params"]["min_size_bytes"] > 0
    assert fastq_validator["params"]["fail_on_error"] is True
    assert ref_validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "fastq_001", "directory", "validate_fastq_dir_001", "input")
    assert _has_edge(workflow, "validate_fastq_dir_001", "passthrough", "cr_count_001", "fastq_dir")
    assert _has_edge(workflow, "ref_001", "directory", "validate_reference_dir_001", "input")
    assert _has_edge(workflow, "validate_reference_dir_001", "passthrough", "cr_count_001", "transcriptome")
    assert not _has_edge(workflow, "fastq_001", "directory", "cr_count_001", "fastq_dir")
    assert not _has_edge(workflow, "ref_001", "directory", "cr_count_001", "transcriptome")
    assert workflow["outputs"]["validated_fastq_dir"] == "validate_fastq_dir_001"
    assert workflow["outputs"]["validated_reference_dir"] == "validate_reference_dir_001"


def test_single_cell_template_validates_cellranger_web_summary_before_preview() -> None:
    workflow = _load_template("single_cell_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["validate_web_summary_001"] == "data_validator"
    assert node_types["gate_web_summary_001"] == "gate"
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_web_summary_001")
    gate = next(node for node in workflow["nodes"] if node["id"] == "gate_web_summary_001")
    assert validator["params"]["expected_format"] == "text"
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert gate["params"]["condition_mode"] == "file_exists"
    assert gate["params"]["on_fail"] == "halt"
    assert "web_summary" in gate["params"]["error_message"]
    assert _has_edge(workflow, "cr_count_001", "web_summary", "validate_web_summary_001", "input")
    assert _has_edge(workflow, "validate_web_summary_001", "passthrough", "gate_web_summary_001", "value")
    assert _has_edge(workflow, "gate_web_summary_001", "output", "html_preview_001", "file")
    assert not _has_edge(workflow, "cr_count_001", "web_summary", "html_preview_001", "file")
    assert not _has_edge(workflow, "validate_web_summary_001", "passthrough", "html_preview_001", "file")
    assert workflow["outputs"]["validated_web_summary"] == "validate_web_summary_001"
    assert workflow["outputs"]["web_summary_quality_gate"] == "gate_web_summary_001"


def test_single_cell_template_adds_qc_dashboard_and_report() -> None:
    workflow = _load_template("single_cell_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["qc_dashboard_001"] == "qc_dashboard"
    assert node_types["qc_dashboard_preview_001"] == "html_preview"
    assert node_types["single_cell_report_001"] == "html_report"
    assert node_types["single_cell_report_preview_001"] == "html_preview"

    dashboard = next(node for node in workflow["nodes"] if node["id"] == "qc_dashboard_001")
    report = next(node for node in workflow["nodes"] if node["id"] == "single_cell_report_001")
    assert dashboard["params"]["run_name"] == "Single Cell QC"
    assert dashboard["params"]["title"] == "Single Cell QC Dashboard"
    assert report["params"]["title"] == "Single Cell RNA-Seq Report"
    assert "Cell Ranger" in report["params"]["text_sections"]
    assert report["params"]["section_names"] == "Cell Ranger web summary"

    assert _has_edge(workflow, "qc_dashboard_001", "qc_dashboard", "qc_dashboard_preview_001", "file")
    assert _has_edge(workflow, "single_cell_report_001", "html_report", "single_cell_report_preview_001", "file")
    assert workflow["outputs"]["qc_dashboard"] == "qc_dashboard_001"
    assert workflow["outputs"]["report"] == "single_cell_report_001"
