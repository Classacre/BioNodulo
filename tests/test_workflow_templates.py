from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bionodulo.nodes.registry import NodeRegistry
from bionodulo.workflow.validation import validate_workflow


ROOT = Path(__file__).resolve().parents[1]


def _load_template(name: str) -> dict[str, Any]:
    return json.loads((ROOT / "templates" / name).read_text(encoding="utf-8"))


def _node_types(workflow: dict[str, Any]) -> dict[str, str]:
    return {str(node["id"]): str(node["type"]) for node in workflow["nodes"]}


def _node_by_id(workflow: dict[str, Any], node_id: str) -> dict[str, Any]:
    return next(node for node in workflow["nodes"] if node["id"] == node_id)


def _output_validation(workflow: dict[str, Any], node_id: str, output: str) -> dict[str, Any]:
    node = _node_by_id(workflow, node_id)
    return node.get("ui", {}).get("validation", {}).get("outputs", {}).get(output, {})


def _has_edge(workflow: dict[str, Any], source: str, source_output: str, target: str, target_input: str) -> bool:
    return any(
        edge.get("from") == {"node": source, "output": source_output}
        and edge.get("to") == {"node": target, "input": target_input}
        for edge in workflow["edges"]
    )


def _assert_edge(
    workflow: dict[str, Any],
    edge_id: str,
    source: str,
    source_output: str,
    target: str,
    target_input: str,
) -> None:
    expected = {
        "id": edge_id,
        "from": {"node": source, "output": source_output},
        "to": {"node": target, "input": target_input},
    }
    assert [edge for edge in workflow["edges"] if edge.get("id") == edge_id] == [expected]


def test_official_samtools_view_and_sort_edges_use_canonical_alignment_ports() -> None:
    expected_edges = {
        "variant_calling_pipeline.json": (
            ("bwa_001", "alignment", "view_001"),
            ("fixmate_001", "fixmate_bam", "sort_001"),
        ),
        "wgs_variant_pipeline.json": (
            ("bwa_001", "alignment", "view_001"),
            ("fixmate_001", "fixmate_bam", "sort_001"),
        ),
        "chip_seq_pipeline.json": (
            ("bt2_001", "alignment", "view_001"),
            ("view_001", "bam", "sort_001"),
            ("bt2_control_001", "alignment", "view_control_001"),
            ("view_control_001", "bam", "sort_control_001"),
        ),
        "rna_seq_pipeline.json": (
            ("hisat2_001", "alignment", "view_001"),
            ("view_001", "bam", "sort_001"),
        ),
    }

    for template_name, expected in expected_edges.items():
        workflow = _load_template(template_name)
        node_types = _node_types(workflow)
        affected_nodes = {
            node_id for node_id, node_type in node_types.items() if node_type in {"samtools_view", "samtools_sort"}
        }
        affected_edges = [edge for edge in workflow["edges"] if edge.get("to", {}).get("node") in affected_nodes]

        assert len(affected_edges) == len(expected)
        for source, source_output, target in expected:
            assert _has_edge(workflow, source, source_output, target, "alignment")
        assert not any(edge.get("to", {}).get("input") in {"sam", "bam"} for edge in affected_edges)


def test_variant_calling_template_marks_duplicates_before_gatk_and_adds_annotation_report() -> None:
    workflow = _load_template("variant_calling_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["markdup_001"] == "samtools_markdup"
    assert node_types["index_001"] == "samtools_index"
    assert node_types["snpeff_001"] == "snpeff"
    assert "vep_001" not in node_types
    assert "render_vep_tab_1" not in node_types
    assert node_types["vcf_stats_001"] == "vcf_stats_chart"
    assert "render_vcf_stats_ima_2" not in node_types
    assert _has_edge(workflow, "view_001", "bam", "collate_001", "bam")
    assert _has_edge(workflow, "collate_001", "name_collated_bam", "fixmate_001", "bam")
    assert _has_edge(workflow, "fixmate_001", "fixmate_bam", "sort_001", "alignment")
    assert _has_edge(workflow, "sort_001", "sorted_bam", "markdup_001", "bam")
    _assert_edge(workflow, "e6", "markdup_001", "marked_bam", "index_001", "bam")
    _assert_edge(workflow, "e7", "index_001", "indexed_bam", "gatk_retry_001", "input")
    _assert_edge(workflow, "e7_retry", "gatk_retry_001", "passthrough", "gatk_001", "bam")
    _assert_edge(workflow, "e7_bai", "index_001", "bai", "gatk_001", "bam_index")
    _assert_edge(workflow, "e10", "markdup_001", "marked_bam", "flagstat_001", "bam")
    assert not _has_edge(workflow, "markdup_001", "marked_bam", "gatk_retry_001", "input")
    assert not _has_edge(workflow, "markdup_001", "marked_bam", "gatk_001", "bam")
    assert _has_edge(workflow, "filter_001", "filtered_vcf", "snpeff_001", "vcf")
    assert _has_edge(workflow, "filter_001", "filtered_vcf", "vcf_stats_001", "vcf")
    assert _has_edge(workflow, "gate_prioritized_vcf_001", "output", "render_gate_prioritized_vcf_tab_0", "vcf")
    assert next(node for node in workflow["nodes"] if node["id"] == "vcf_stats_001")["params"]["format"] == "html"
    assert workflow["outputs"]["vcf"] == "prioritize_vcf_001"
    assert workflow["outputs"]["variant_stats"] == "vcf_stats_001"
    assert "vep_annotation" not in workflow["outputs"]


def test_variant_calling_template_genotypes_gvcf_before_filtering() -> None:
    workflow = _load_template("variant_calling_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["gatk_001"] == "gatk_haplotype_caller"
    assert node_types["gatk_genotype_001"] == "gatk_genotype_gvcfs"
    assert _node_by_id(workflow, "gatk_001")["params"] == {"emit_ref_confidence": "GVCF"}
    assert _node_by_id(workflow, "gatk_genotype_001")["params"] == {"standard_min_confidence": 30}
    _assert_edge(
        workflow,
        "e9_gvcf",
        "gatk_001",
        "vcf",
        "gatk_genotype_001",
        "gvcf",
    )
    _assert_edge(
        workflow,
        "e9_gvcf_index",
        "gatk_001",
        "vcf_index",
        "gatk_genotype_001",
        "gvcf_index",
    )
    _assert_edge(
        workflow,
        "e9_reference",
        "ref_sidecars_001",
        "reference",
        "gatk_genotype_001",
        "reference",
    )
    _assert_edge(
        workflow,
        "e9_fai",
        "ref_sidecars_001",
        "fai_index",
        "gatk_genotype_001",
        "reference_index",
    )
    _assert_edge(
        workflow,
        "e9_dict",
        "ref_sidecars_001",
        "sequence_dictionary",
        "gatk_genotype_001",
        "sequence_dictionary",
    )
    _assert_edge(
        workflow,
        "e9",
        "gatk_genotype_001",
        "vcf",
        "filter_001",
        "input_file",
    )
    assert not _has_edge(workflow, "gatk_001", "vcf", "filter_001", "input_file")
    result = validate_workflow(workflow, NodeRegistry.create_isolated())
    assert result.valid, result.errors


def test_variant_calling_template_validates_reference_before_alignment_and_calling() -> None:
    workflow = _load_template("variant_calling_pipeline.json")
    node_types = _node_types(workflow)

    assert "validate_reference_001" not in node_types
    validator = _output_validation(workflow, "ref_001", "reference")
    assert validator["expected_format"] == "fasta"
    assert validator["min_records"] >= 1
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert not _has_edge(workflow, "ref_001", "reference", "validate_reference_001", "input")
    assert node_types["ref_sidecars_001"] == "samtools_faidx"
    assert _has_edge(workflow, "ref_001", "reference", "ref_sidecars_001", "reference")
    assert _has_edge(workflow, "ref_sidecars_001", "reference", "bwa_idx_001", "reference")
    assert _has_edge(workflow, "ref_sidecars_001", "reference", "gatk_001", "reference")
    assert _has_edge(workflow, "ref_sidecars_001", "fai_index", "gatk_001", "reference_index")
    assert _has_edge(
        workflow,
        "ref_sidecars_001",
        "sequence_dictionary",
        "gatk_001",
        "sequence_dictionary",
    )
    assert not _has_edge(workflow, "ref_001", "reference", "gatk_001", "reference")
    assert workflow["outputs"]["validated_reference"] == "ref_001"


def test_variant_calling_template_validates_reads_before_alignment_and_qc() -> None:
    workflow = _load_template("variant_calling_pipeline.json")
    node_types = _node_types(workflow)

    assert "validate_reads_001" not in node_types
    validator = _output_validation(workflow, "reads_001", "reads")
    assert validator["expected_format"] == "fastq"
    assert validator["min_records"] >= 1
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert not _has_edge(workflow, "reads_001", "reads", "validate_reads_001", "input")
    assert _has_edge(workflow, "reads_001", "reads", "bwa_001", "reads")
    assert _has_edge(workflow, "reads_001", "reads", "qc_001", "reads")
    assert _has_edge(workflow, "reads_001", "reads", "bwa_001", "reads")
    assert _has_edge(workflow, "reads_001", "reads", "qc_001", "reads")
    bwa = _node_by_id(workflow, "bwa_001")
    assert bwa["params"]["read_group"] == "@RG\\tID:sample1\\tSM:sample1\\tPL:ILLUMINA"
    assert bwa["params"]["mark_shorter_splits"] is True
    assert workflow["outputs"]["validated_reads"] == "reads_001"


def test_variant_calling_template_validates_multiqc_report_before_preview() -> None:
    workflow = _load_template("variant_calling_pipeline.json")
    node_types = _node_types(workflow)

    assert "validate_multiqc_001" not in node_types
    validator = _output_validation(workflow, "mqc_001", "report")
    assert validator["expected_format"] == "text"
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert not _has_edge(workflow, "mqc_001", "report", "validate_multiqc_001", "input")
    assert workflow["outputs"]["validated_multiqc_report"] == "mqc_001"


def test_variant_calling_template_adds_coverage_plot_from_indexed_bam_pair() -> None:
    workflow = _load_template("variant_calling_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["coverage_plot_001"] == "coverage_plot"
    coverage = next(node for node in workflow["nodes"] if node["id"] == "coverage_plot_001")
    assert coverage["params"]["region"] == "Wildtype:1-50000"
    assert coverage["params"]["window_size"] == 100
    assert coverage["params"]["format"] == "html"
    _assert_edge(workflow, "e18", "index_001", "indexed_bam", "coverage_plot_001", "alignment")
    _assert_edge(workflow, "e18_bai", "index_001", "bai", "coverage_plot_001", "alignment_index")
    assert not _has_edge(workflow, "markdup_001", "marked_bam", "coverage_plot_001", "alignment")
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
    assert "output_type" not in prioritizer["params"]
    assert gate["params"]["condition_mode"] == "file_exists"
    assert gate["params"]["on_fail"] == "halt"
    assert "prioritized VCF" in gate["params"]["error_message"]
    assert _has_edge(workflow, "snpeff_001", "annotated_vcf", "prioritize_vcf_001", "vcf")
    assert _has_edge(workflow, "prioritize_vcf_001", "filtered_vcf", "gate_prioritized_vcf_001", "value")
    assert _has_edge(workflow, "gate_prioritized_vcf_001", "output", "render_gate_prioritized_vcf_tab_0", "vcf")
    assert not _has_edge(workflow, "snpeff_001", "annotated_vcf", "render_gate_prioritized_vcf_tab_0", "vcf")
    assert not _has_edge(workflow, "prioritize_vcf_001", "filtered_vcf", "render_gate_prioritized_vcf_tab_0", "vcf")
    assert workflow["outputs"]["vcf"] == "prioritize_vcf_001"
    assert workflow["outputs"]["prioritized_vcf"] == "prioritize_vcf_001"
    assert workflow["outputs"]["prioritized_vcf_quality_gate"] == "gate_prioritized_vcf_001"


def test_wgs_variant_template_marks_duplicates_before_freebayes_and_adds_annotation_report() -> None:
    workflow = _load_template("wgs_variant_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["markdup_001"] == "samtools_markdup"
    assert node_types["idx_001"] == "samtools_index"
    assert node_types["snpeff_001"] == "snpeff"
    assert "vep_001" not in node_types
    assert "render_vep_tab_1" not in node_types
    assert node_types["vcf_stats_001"] == "vcf_stats_chart"
    assert "render_vcf_stats_ima_2" not in node_types
    assert _has_edge(workflow, "view_001", "bam", "collate_001", "bam")
    assert _has_edge(workflow, "collate_001", "name_collated_bam", "fixmate_001", "bam")
    assert _has_edge(workflow, "fixmate_001", "fixmate_bam", "sort_001", "alignment")
    assert _has_edge(workflow, "sort_001", "sorted_bam", "markdup_001", "bam")
    _assert_edge(workflow, "e7", "markdup_001", "marked_bam", "idx_001", "bam")
    _assert_edge(workflow, "e8", "idx_001", "indexed_bam", "fb_001", "bam")
    _assert_edge(workflow, "e8_bai", "idx_001", "bai", "fb_001", "bam_index")
    assert not _has_edge(workflow, "markdup_001", "marked_bam", "fb_001", "bam")
    assert _has_edge(workflow, "filter_001", "filtered_vcf", "snpeff_001", "vcf")
    assert _has_edge(workflow, "filter_001", "filtered_vcf", "vcf_stats_001", "vcf")
    assert _has_edge(workflow, "gate_prioritized_vcf_001", "output", "render_gate_prioritized_vcf_tab_0", "vcf")
    assert next(node for node in workflow["nodes"] if node["id"] == "vcf_stats_001")["params"]["format"] == "html"
    assert workflow["outputs"]["vcf"] == "prioritize_vcf_001"
    assert workflow["outputs"]["variant_stats"] == "vcf_stats_001"
    assert "vep_annotation" not in workflow["outputs"]


def test_wgs_variant_template_validates_reference_before_alignment_and_calling() -> None:
    workflow = _load_template("wgs_variant_pipeline.json")
    node_types = _node_types(workflow)

    assert "validate_reference_001" not in node_types
    validator = _output_validation(workflow, "ref_001", "reference")
    assert validator["expected_format"] == "fasta"
    assert validator["min_records"] >= 1
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert not _has_edge(workflow, "ref_001", "reference", "validate_reference_001", "input")
    assert node_types["ref_sidecars_001"] == "samtools_faidx"
    assert _has_edge(workflow, "ref_001", "reference", "ref_sidecars_001", "reference")
    assert _has_edge(workflow, "ref_sidecars_001", "reference", "bwa_idx_001", "reference")
    assert _has_edge(workflow, "ref_sidecars_001", "reference", "fb_001", "reference")
    assert _has_edge(workflow, "ref_sidecars_001", "fai_index", "fb_001", "reference_index")
    assert not _has_edge(workflow, "ref_001", "reference", "fb_001", "reference")
    assert workflow["outputs"]["validated_reference"] == "ref_001"


def test_wgs_variant_template_validates_reads_before_trimming_and_qc() -> None:
    workflow = _load_template("wgs_variant_pipeline.json")
    node_types = _node_types(workflow)

    assert "validate_reads_001" not in node_types
    validator = _output_validation(workflow, "reads_001", "reads")
    assert validator["expected_format"] == "fastq"
    assert validator["min_records"] >= 1
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert not _has_edge(workflow, "reads_001", "reads", "validate_reads_001", "input")
    assert _has_edge(workflow, "reads_001", "reads", "fastp_001", "reads")
    assert _has_edge(workflow, "reads_001", "reads", "qc_001", "reads")
    assert _has_edge(workflow, "reads_001", "reads", "fastp_001", "reads")
    assert _has_edge(workflow, "reads_001", "reads", "qc_001", "reads")
    bwa = _node_by_id(workflow, "bwa_001")
    assert bwa["params"]["read_group"] == "@RG\\tID:wgs1\\tSM:wgs1\\tPL:ILLUMINA"
    assert bwa["params"]["mark_shorter_splits"] is True
    assert workflow["outputs"]["validated_reads"] == "reads_001"


def test_wgs_variant_template_validates_multiqc_report_before_preview() -> None:
    workflow = _load_template("wgs_variant_pipeline.json")
    node_types = _node_types(workflow)

    assert "validate_multiqc_001" not in node_types
    validator = _output_validation(workflow, "mqc_001", "report")
    assert validator["expected_format"] == "text"
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert not _has_edge(workflow, "mqc_001", "report", "validate_multiqc_001", "input")
    assert workflow["outputs"]["validated_multiqc_report"] == "mqc_001"


def test_wgs_variant_template_adds_coverage_plot_from_indexed_bam_pair() -> None:
    workflow = _load_template("wgs_variant_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["coverage_plot_001"] == "coverage_plot"
    coverage = next(node for node in workflow["nodes"] if node["id"] == "coverage_plot_001")
    assert coverage["params"]["region"] == "NC_000913.3:1-50000"
    assert coverage["params"]["window_size"] == 100
    assert coverage["params"]["format"] == "html"
    _assert_edge(workflow, "e18", "idx_001", "indexed_bam", "coverage_plot_001", "alignment")
    _assert_edge(workflow, "e18_bai", "idx_001", "bai", "coverage_plot_001", "alignment_index")
    assert not _has_edge(workflow, "markdup_001", "marked_bam", "coverage_plot_001", "alignment")
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
    assert "output_type" not in prioritizer["params"]
    assert gate["params"]["condition_mode"] == "file_exists"
    assert gate["params"]["on_fail"] == "halt"
    assert "prioritized VCF" in gate["params"]["error_message"]
    assert _has_edge(workflow, "snpeff_001", "annotated_vcf", "prioritize_vcf_001", "vcf")
    assert _has_edge(workflow, "prioritize_vcf_001", "filtered_vcf", "gate_prioritized_vcf_001", "value")
    assert _has_edge(workflow, "gate_prioritized_vcf_001", "output", "render_gate_prioritized_vcf_tab_0", "vcf")
    assert not _has_edge(workflow, "snpeff_001", "annotated_vcf", "render_gate_prioritized_vcf_tab_0", "vcf")
    assert not _has_edge(workflow, "prioritize_vcf_001", "filtered_vcf", "render_gate_prioritized_vcf_tab_0", "vcf")
    assert workflow["outputs"]["vcf"] == "prioritize_vcf_001"
    assert workflow["outputs"]["prioritized_vcf"] == "prioritize_vcf_001"
    assert workflow["outputs"]["prioritized_vcf_quality_gate"] == "gate_prioritized_vcf_001"


def test_variant_templates_supply_exact_snpeff_database_dependencies() -> None:
    expected_defaults = {
        "variant_calling_pipeline.json": None,
        "wgs_variant_pipeline.json": ("Escherichia_coli_str_k_12_substr_mg1655_gca_000005845"),
    }
    registry = NodeRegistry.create_isolated()
    file_node = registry.get("input_file")
    snpeff_node = registry.get("snpeff")
    assert file_node is not None
    assert snpeff_node is not None

    snpeff_input_types = snpeff_node.INPUT_TYPES()
    assert file_node.RETURN_TYPES[file_node.RETURN_NAMES.index("file")] == "FILE"
    assert snpeff_input_types["required"]["genome"][0] == "STRING"
    assert snpeff_input_types["required"]["database"][0] == "FILE"
    assert snpeff_input_types["optional"]["data_dir"][0] == "DIRECTORY"

    for template_name, expected_default in expected_defaults.items():
        workflow = _load_template(template_name)
        node_types = _node_types(workflow)
        parameters = {parameter["name"]: parameter for parameter in workflow["parameters"]}
        database = _node_by_id(workflow, "snpeff_database_001")
        snpeff = _node_by_id(workflow, "snpeff_001")

        assert "snpeff_data_dir_001" not in node_types
        assert node_types["snpeff_database_001"] == "input_file"
        assert "snpeff_data_dir" not in parameters
        assert parameters["snpeff_genome"]["type"] == "STRING"
        assert parameters["snpeff_genome"]["required"] is True
        assert parameters["snpeff_genome"].get("default") == expected_default
        assert parameters["snpeff_database"]["type"] == "FILE"
        assert parameters["snpeff_database"]["required"] is True
        assert database["params"] == {"file": "{{snpeff_database}}", "source": "local"}
        assert snpeff["params"]["genome"] == "{{snpeff_genome}}"
        assert not any(edge.get("to") == {"node": "snpeff_001", "input": "data_dir"} for edge in workflow["edges"])
        _assert_edge(
            workflow,
            "e14_snpeff_database",
            "snpeff_database_001",
            "file",
            "snpeff_001",
            "database",
        )

    variant_parameters = {
        parameter["name"]: parameter for parameter in _load_template("variant_calling_pipeline.json")["parameters"]
    }
    assert "default" not in variant_parameters["snpeff_genome"]
    for parameter_name in ("snpeff_genome", "snpeff_database"):
        description = variant_parameters[parameter_name]["description"]
        assert "custom" in description
        assert "exact Staphylococcus aureus wildtype.fna tutorial reference" in description


def test_official_variant_templates_wire_every_required_sidecar_input() -> None:
    """Keep template DAG dependencies aligned with the focused node contracts."""
    expected_by_template = {
        "variant_calling_pipeline.json": {
            "gatk_001": {"bam_index", "reference_index", "sequence_dictionary"},
            "gatk_genotype_001": {
                "gvcf_index",
                "reference_index",
                "sequence_dictionary",
            },
            "manta_sv_001": {"bam_index", "reference_index"},
            "delly_sv_001": {"bam_index", "reference_index"},
            "snpeff_001": {"database"},
        },
        "wgs_variant_pipeline.json": {
            "fb_001": {"bam_index", "reference_index"},
            "manta_sv_001": {"bam_index", "reference_index"},
            "delly_sv_001": {"bam_index", "reference_index"},
            "snpeff_001": {"database"},
        },
    }
    sidecar_inputs = {
        "bam_index",
        "database",
        "gvcf_index",
        "normal_bam_index",
        "reference_index",
        "sequence_dictionary",
    }
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    for template_name, expected_nodes in expected_by_template.items():
        workflow = _load_template(template_name)
        node_types = _node_types(workflow)
        incoming = {
            node_id: {
                str(edge["to"]["input"])
                for edge in workflow["edges"]
                if edge.get("to", {}).get("node") == node_id
            }
            for node_id in expected_nodes
        }

        producer = registry.get(node_types["ref_sidecars_001"])
        assert producer is not None
        assert set(producer.RETURN_NAMES) == {
            "reference",
            "fai_index",
            "sequence_dictionary",
        }

        for node_id, expected_inputs in expected_nodes.items():
            node_class = registry.get(node_types[node_id])
            assert node_class is not None
            declared_required = set(node_class.INPUT_TYPES()["required"]) & sidecar_inputs
            assert declared_required == expected_inputs
            assert incoming[node_id] & sidecar_inputs == expected_inputs

        for node_id in ("manta_sv_001", "delly_sv_001"):
            node_class = registry.get(node_types[node_id])
            assert node_class is not None
            assert "normal_bam_index" in node_class.INPUT_TYPES()["optional"]
            assert incoming[node_id].isdisjoint({"normal_bam", "normal_bam_index"})


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
    assert _has_edge(workflow, "input_fastq_001", "reads", "fastp_001", "reads")
    assert _has_edge(workflow, "fastp_001", "trimmed_reads", "fastqc_001", "reads")
    assert _has_edge(workflow, "input_fastq_001", "reads", "fastp_001", "reads")
    assert not _has_edge(workflow, "input_fastq_001", "reads", "fastqc_001", "reads")
    assert workflow["outputs"]["trimmed_reads"] == "fastp_001"


def test_fastq_qc_template_validates_input_reads_before_trimming() -> None:
    workflow = _load_template("fastq_qc_pipeline.json")
    node_types = _node_types(workflow)

    assert "validate_reads_001" not in node_types
    validator = _output_validation(workflow, "input_fastq_001", "reads")
    assert validator["expected_format"] == "fastq"
    assert validator["min_records"] >= 1
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert not _has_edge(workflow, "input_fastq_001", "reads", "validate_reads_001", "input")
    assert _has_edge(workflow, "input_fastq_001", "reads", "fastp_001", "reads")
    assert _has_edge(workflow, "input_fastq_001", "reads", "fastp_001", "reads")
    assert workflow["outputs"]["validated_reads"] == "input_fastq_001"


def test_fastq_qc_template_demonstrates_sample_sheet_input_validation() -> None:
    workflow = _load_template("fastq_qc_pipeline.json")
    node_types = _node_types(workflow)

    # The sample_sheet_001 demo node was removed from the template by design.
    assert "sample_sheet_001" not in node_types
    assert "validate_sample_sheet_001" not in node_types
    assert "sample_sheet" not in workflow["outputs"]
    assert "validated_sample_sheet" not in workflow["outputs"]


def test_phylogenetics_template_renders_tree_and_adds_report() -> None:
    workflow = _load_template("phylogenetics_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["tree_viewer_001"] == "phylo_tree_viewer"
    # The phylo_report_001 html_report was removed by design; figures feed preview nodes.
    assert "phylo_report_001" not in node_types
    assert "render_tree_viewer_ima_0" not in node_types
    assert node_types["image_preview_001"] == "image_preview"
    tree_viewer = next(node for node in workflow["nodes"] if node["id"] == "tree_viewer_001")
    iqtree = next(node for node in workflow["nodes"] if node["id"] == "iqtree_001")
    assert tree_viewer["params"]["format"] == "png"
    assert tree_viewer["params"]["layout"] == "rectangular"
    assert iqtree["params"]["ufboot_replicates"] == 1000
    assert iqtree["params"]["alrt_replicates"] == 1000
    assert "bootstrap" not in iqtree["params"]
    assert _has_edge(workflow, "iqtree_001", "tree", "tree_viewer_001", "tree_file")
    assert _has_edge(workflow, "msa_view_001", "alignment_image", "image_preview_001", "file")
    assert workflow["outputs"]["tree_image"] == "tree_viewer_001"
    assert "report" not in workflow["outputs"]


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
    assert efetch["params"]["accessions"] == "NR_024570.1,NR_027552.1,NR_036781.1,NR_026078.1,NR_028747.1"
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
    assert _has_edge(workflow, "annot_001", "annotation", "qualimap_001", "feature_file")
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

    assert "validate_multiqc_001" not in node_types
    validator = _output_validation(workflow, "mqc_001", "report")
    assert validator["expected_format"] == "text"
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert not _has_edge(workflow, "mqc_001", "report", "validate_multiqc_001", "input")
    assert workflow["outputs"]["validated_multiqc_report"] == "mqc_001"


def test_rna_seq_template_validates_reference_fasta_before_indexing() -> None:
    workflow = _load_template("rna_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert "validate_reference_001" not in node_types
    validator = _output_validation(workflow, "ref_001", "reference")
    assert validator["expected_format"] == "fasta"
    assert validator["min_records"] >= 1
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert not _has_edge(workflow, "ref_001", "reference", "validate_reference_001", "input")
    assert _has_edge(workflow, "ref_001", "reference", "hisat2_build_001", "reference")
    assert _has_edge(workflow, "ref_001", "reference", "hisat2_build_001", "reference")
    assert workflow["outputs"]["validated_reference"] == "ref_001"


def test_rna_seq_template_validates_reads_before_trimming_and_qc() -> None:
    workflow = _load_template("rna_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert "validate_reads_001" not in node_types
    validator = _output_validation(workflow, "reads_001", "reads")
    assert validator["expected_format"] == "fastq"
    assert validator["min_records"] >= 1
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert not _has_edge(workflow, "reads_001", "reads", "validate_reads_001", "input")
    assert _has_edge(workflow, "reads_001", "reads", "fastp_001", "reads")
    assert _has_edge(workflow, "reads_001", "reads", "qc_001", "reads")
    assert _has_edge(workflow, "reads_001", "reads", "fastp_001", "reads")
    assert _has_edge(workflow, "reads_001", "reads", "qc_001", "reads")
    assert workflow["outputs"]["validated_reads"] == "reads_001"


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

    assert "validate_annotation_001" not in node_types
    validator = _output_validation(workflow, "annot_001", "annotation")
    assert validator["expected_format"] == "text"
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert not _has_edge(workflow, "annot_001", "annotation", "validate_annotation_001", "input")
    assert _has_edge(workflow, "annot_001", "annotation", "counts_001", "reference_gene_sets")
    assert _has_edge(workflow, "annot_001", "annotation", "qualimap_001", "feature_file")
    assert _has_edge(workflow, "annot_001", "annotation", "counts_001", "reference_gene_sets")
    assert _has_edge(workflow, "annot_001", "annotation", "qualimap_001", "feature_file")
    assert workflow["outputs"]["validated_annotation"] == "annot_001"


def test_rna_seq_template_normalizes_featurecounts_output() -> None:
    workflow = _load_template("rna_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["normalize_counts_001"] == "normalize_data"
    counts = next(node for node in workflow["nodes"] if node["id"] == "counts_001")
    # The normalized-count heatmap uses R's pheatmap (clustered expression
    # heatmap is the RNA-seq standard); normalization emits CSV so pheatmap and
    # the table preview can both read it.
    assert node_types["counts_heatmap_001"] == "r_pheatmap"
    normalizer = next(node for node in workflow["nodes"] if node["id"] == "normalize_counts_001")
    heatmap = next(node for node in workflow["nodes"] if node["id"] == "counts_heatmap_001")
    assert counts["params"]["gff_feature_type"] == "gene"
    assert counts["params"]["gff_feature_attribute"] == "ID"
    assert counts["params"]["paired_end_status"] == "PE_fragments"
    assert _has_edge(workflow, "sort_001", "sorted_bam", "counts_001", "alignment")
    assert _has_edge(workflow, "annot_001", "annotation", "counts_001", "reference_gene_sets")
    assert normalizer["params"]["method"] == "cpm"
    assert normalizer["params"]["id_columns"] == "Geneid"
    assert normalizer["params"]["axis"] == "rows"
    assert normalizer["params"]["output_type"] == "CSV"
    assert heatmap["params"]["scale"] == "row"
    assert heatmap["params"]["cluster_rows"] is True
    assert _has_edge(workflow, "counts_001", "counts", "normalize_counts_001", "table")
    assert _has_edge(workflow, "normalize_counts_001", "normalized_table", "counts_heatmap_001", "data_csv")
    assert workflow["outputs"]["normalized_counts"] == "normalize_counts_001"
    assert workflow["outputs"]["counts_heatmap"] == "counts_heatmap_001"


def test_deseq2_template_adds_volcano_ma_and_report_outputs() -> None:
    workflow = _load_template("deseq2_differential_expression.json")
    node_types = _node_types(workflow)

    assert node_types["volcano_001"] == "volcano_plot"
    assert node_types["ma_plot_001"] == "ma_plot"
    assert "render_volcano_ima_6" not in node_types
    assert node_types["render_deseq2_tab_0"] == "table_preview"
    volcano = next(node for node in workflow["nodes"] if node["id"] == "volcano_001")
    ma_plot = next(node for node in workflow["nodes"] if node["id"] == "ma_plot_001")
    assert volcano["params"]["format"] == "html"
    assert ma_plot["params"]["format"] == "html"
    assert _has_edge(workflow, "deseq2_001", "results_csv", "volcano_001", "results_table")
    assert _has_edge(workflow, "deseq2_001", "results_csv", "ma_plot_001", "results_table")
    assert _has_edge(workflow, "deseq2_001", "results_csv", "render_deseq2_tab_0", "file")
    assert workflow["outputs"]["volcano_plot"] == "volcano_001"
    assert workflow["outputs"]["ma_plot"] == "ma_plot_001"


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
    assert _has_edge(workflow, "significant_genes_001", "filtered_table", "render_significant_genes_tab_3", "file")
    assert workflow["outputs"]["significant_genes"] == "significant_genes_001"


def test_deseq2_template_transposes_normalized_counts_for_sample_reporting() -> None:
    workflow = _load_template("deseq2_differential_expression.json")
    node_types = _node_types(workflow)

    assert node_types["normalized_counts_transpose_001"] == "transpose_table"
    transpose_node = next(node for node in workflow["nodes"] if node["id"] == "normalized_counts_transpose_001")
    assert transpose_node["params"]["id_column"] == "gene"
    assert transpose_node["params"]["new_header"] == "sample"
    assert transpose_node["params"]["output_type"] == "CSV"
    assert _has_edge(workflow, "deseq2_001", "normalized_counts_csv", "normalized_counts_transpose_001", "table")
    assert _has_edge(
        workflow,
        "normalized_counts_transpose_001",
        "transposed_table",
        "render_normalized_counts_transpose_tab_2",
        "file",
    )
    assert workflow["outputs"]["normalized_counts_transposed"] == "normalized_counts_transpose_001"


def test_deseq2_template_validates_count_matrix_and_sample_info_before_analysis() -> None:
    workflow = _load_template("deseq2_differential_expression.json")
    node_types = _node_types(workflow)

    assert "validate_counts_001" not in node_types
    assert "validate_samples_001" not in node_types
    counts_validator = _output_validation(workflow, "counts_001", "file")
    samples_validator = _output_validation(workflow, "samples_001", "file")
    assert counts_validator["expected_format"] == "csv"
    assert counts_validator["min_records"] >= 1
    assert counts_validator["min_size_bytes"] > 0
    assert counts_validator["fail_on_error"] is True
    assert samples_validator["expected_format"] == "csv"
    assert samples_validator["min_records"] >= 2
    assert samples_validator["required_fields"] == "sample,condition"
    assert samples_validator["min_size_bytes"] > 0
    assert samples_validator["fail_on_error"] is True
    assert not _has_edge(workflow, "counts_001", "file", "validate_counts_001", "input")
    assert _has_edge(workflow, "counts_001", "file", "deseq2_001", "count_matrix")
    assert not _has_edge(workflow, "samples_001", "file", "validate_samples_001", "input")
    assert _has_edge(workflow, "samples_001", "file", "deseq2_001", "sample_info")
    assert _has_edge(workflow, "counts_001", "file", "deseq2_001", "count_matrix")
    assert _has_edge(workflow, "samples_001", "file", "deseq2_001", "sample_info")
    assert workflow["outputs"]["validated_counts"] == "counts_001"
    assert workflow["outputs"]["validated_sample_info"] == "samples_001"


def test_r_visualization_template_validates_heatmap_csv_before_pheatmap() -> None:
    workflow = _load_template("r_visualization_pipeline.json")
    node_types = _node_types(workflow)

    assert "validate_heatmap_csv_001" not in node_types
    validator = _output_validation(workflow, "heatmap_data_001", "file")
    assert validator["expected_format"] == "csv"
    assert validator["min_records"] >= 1
    assert validator["required_fields"] == "gene"
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert not _has_edge(workflow, "heatmap_data_001", "file", "validate_heatmap_csv_001", "input")
    assert _has_edge(workflow, "heatmap_data_001", "file", "pheatmap_001", "data_csv")
    assert _has_edge(workflow, "heatmap_data_001", "file", "pheatmap_001", "data_csv")
    assert workflow["outputs"]["validated_heatmap_data"] == "heatmap_data_001"


def test_r_visualization_template_combines_plots_into_html_report() -> None:
    workflow = _load_template("r_visualization_pipeline.json")
    node_types = _node_types(workflow)

    # The viz_report_001 html_report and its html_preview were removed by design;
    # each figure feeds its own curated image_preview node instead.
    assert "viz_report_001" not in node_types
    assert "viz_report_preview_001" not in node_types
    assert "qc_preview_001" not in node_types
    assert "expr_preview_001" not in node_types
    assert "heatmap_preview_001" not in node_types
    assert "volcano_preview_001" not in node_types
    assert "ma_preview_001" not in node_types
    assert "report" not in workflow["outputs"]
    assert "report_preview" not in workflow["outputs"]


def test_biopython_template_validates_input_fastas_before_sequence_tools() -> None:
    workflow = _load_template("biopython_analysis_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["ncbi_efetch_001"] == "ncbi_efetch"
    assert "validate_sequences_001" not in node_types
    assert "validate_coding_001" not in node_types
    efetch = next(node for node in workflow["nodes"] if node["id"] == "ncbi_efetch_001")
    sequences_validator = _output_validation(workflow, "ncbi_efetch_001", "records")
    coding_validator = _output_validation(workflow, "coding_001", "reference")
    assert efetch["params"]["database"] == "nuccore"
    assert efetch["params"]["rettype"] == "fasta"
    assert efetch["params"]["retmode"] == "text"
    assert sequences_validator["expected_format"] == "fasta"
    assert sequences_validator["min_records"] >= 2
    assert sequences_validator["min_size_bytes"] > 0
    assert sequences_validator["fail_on_error"] is True
    assert coding_validator["expected_format"] == "fasta"
    assert coding_validator["min_records"] >= 1
    assert coding_validator["min_size_bytes"] > 0
    assert coding_validator["fail_on_error"] is True
    assert not _has_edge(workflow, "ncbi_efetch_001", "records", "validate_sequences_001", "input")
    assert _has_edge(workflow, "ncbi_efetch_001", "records", "seqio_read_001", "input_file")
    assert _has_edge(workflow, "ncbi_efetch_001", "records", "seq_stats_001", "input_file")
    assert _has_edge(workflow, "ncbi_efetch_001", "records", "blast_001", "query")
    assert _has_edge(workflow, "ncbi_efetch_001", "records", "blast_001", "subject")
    assert not _has_edge(workflow, "coding_001", "reference", "validate_coding_001", "input")
    assert _has_edge(workflow, "coding_001", "reference", "translate_001", "input_file")
    assert _has_edge(workflow, "coding_001", "reference", "biostrings_001", "input_fasta")
    assert not _has_edge(workflow, "seqs_001", "reference", "validate_sequences_001", "input")
    assert not _has_edge(workflow, "seqs_001", "reference", "seqio_read_001", "input_file")
    assert not _has_edge(workflow, "seqs_001", "reference", "seq_stats_001", "input_file")
    assert not _has_edge(workflow, "seqs_001", "reference", "blast_001", "query")
    assert not _has_edge(workflow, "seqs_001", "reference", "blast_001", "subject")
    assert _has_edge(workflow, "coding_001", "reference", "translate_001", "input_file")
    assert _has_edge(workflow, "coding_001", "reference", "biostrings_001", "input_fasta")
    assert workflow["outputs"]["fetched_fasta"] == "ncbi_efetch_001"
    assert workflow["outputs"]["validated_sequences"] == "ncbi_efetch_001"
    assert workflow["outputs"]["validated_coding_sequences"] == "coding_001"


def test_biopython_template_adds_sequence_stats_chart_report() -> None:
    workflow = _load_template("biopython_analysis_pipeline.json")
    node_types = _node_types(workflow)

    # Charting goes through ggplot2 (r_plot) for proper axes/titles.
    assert node_types["seq_length_chart_001"] == "r_plot"
    assert "render_seq_length_chart_ima_2" not in node_types
    assert node_types["table_preview_001"] == "table_preview"
    chart = next(node for node in workflow["nodes"] if node["id"] == "seq_length_chart_001")
    assert chart["params"]["x_axis"] == "id"
    assert chart["params"]["y_axis"] == "length"
    assert chart["params"]["plot_type"] == "bar"
    assert _has_edge(workflow, "seq_stats_001", "stats_csv", "seq_length_chart_001", "data_csv")
    assert _has_edge(workflow, "seq_stats_001", "stats_tsv", "table_preview_001", "file")
    assert workflow["outputs"]["sequence_length_chart"] == "seq_length_chart_001"


def test_biopython_template_does_not_present_fixture_scores_as_sequence_classification() -> None:
    workflow = _load_template("biopython_analysis_pipeline.json")
    node_types = _node_types(workflow)

    assert "sequence_classification_001" not in node_types
    assert "render_sequence_classification_tab_1" not in node_types
    assert "sequence_classifications" not in workflow["outputs"]
    assert "sequence_classifications_csv" not in workflow["outputs"]


def test_biopython_template_does_not_advertise_generic_http_api_lookup() -> None:
    workflow = _load_template("biopython_analysis_pipeline.json")
    node_types = _node_types(workflow)

    # The http_gene_lookup_001 demo node was removed from the template by design.
    assert "http_gene_lookup_001" not in node_types
    assert "api_gene_lookup" not in workflow["outputs"]


def test_differential_expression_template_validates_transcriptome_before_indexing() -> None:
    workflow = _load_template("differential_expression.json")
    node_types = _node_types(workflow)

    assert "validate_transcriptome_001" not in node_types
    validator = _output_validation(workflow, "tx_001", "reference")
    assert validator["expected_format"] == "fasta"
    assert validator["min_records"] >= 1
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert not _has_edge(workflow, "tx_001", "reference", "validate_transcriptome_001", "input")
    assert _has_edge(workflow, "tx_001", "reference", "salmon_idx_001", "transcripts")
    assert _has_edge(workflow, "tx_001", "reference", "kallisto_idx_001", "transcripts")
    assert _has_edge(workflow, "tx_001", "reference", "salmon_idx_001", "transcripts")
    assert _has_edge(workflow, "tx_001", "reference", "kallisto_idx_001", "transcripts")
    assert workflow["outputs"]["validated_transcriptome"] == "tx_001"


def test_differential_expression_template_validates_reads_before_quantification() -> None:
    workflow = _load_template("differential_expression.json")
    node_types = _node_types(workflow)

    assert "validate_reads_001" not in node_types
    validator = _output_validation(workflow, "reads_001", "reads")
    assert validator["expected_format"] == "fastq"
    assert validator["min_records"] >= 1
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert not _has_edge(workflow, "reads_001", "reads", "validate_reads_001", "input")
    assert _has_edge(workflow, "reads_001", "reads", "salmon_quant_001", "reads")
    assert _has_edge(workflow, "reads_001", "reads", "kallisto_quant_001", "reads")
    assert _has_edge(workflow, "reads_001", "reads", "salmon_quant_001", "reads")
    assert _has_edge(workflow, "reads_001", "reads", "kallisto_quant_001", "reads")
    assert workflow["outputs"]["validated_reads"] == "reads_001"


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
    assert _has_edge(workflow, "salmon_quant_001", "quant_dir", "mqc_001", "reports")
    assert _has_edge(workflow, "kallisto_quant_001", "report", "mqc_001", "reports")
    assert not _has_edge(workflow, "salmon_quant_001", "counts", "mqc_001", "reports")
    assert not _has_edge(workflow, "kallisto_quant_001", "abundance", "mqc_001", "reports")
    assert not _has_edge(workflow, "mqc_001", "report", "validate_multiqc_001", "input")
    assert workflow["outputs"]["report"] == "mqc_001"


def test_differential_expression_template_validates_multiqc_report_before_preview() -> None:
    workflow = _load_template("differential_expression.json")
    node_types = _node_types(workflow)

    assert "validate_multiqc_001" not in node_types
    validator = _output_validation(workflow, "mqc_001", "report")
    assert validator["expected_format"] == "text"
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert not _has_edge(workflow, "mqc_001", "report", "validate_multiqc_001", "input")
    assert workflow["outputs"]["validated_multiqc_report"] == "mqc_001"


def test_differential_expression_template_adds_quantification_table_previews() -> None:
    workflow = _load_template("differential_expression.json")
    node_types = _node_types(workflow)

    assert node_types["render_salmon_quant_tab_0"] == "table_preview"
    assert node_types["render_kallisto_quant_tab_1"] == "table_preview"
    assert node_types["render_quant_comparison_tab_2"] == "table_preview"
    assert _has_edge(workflow, "salmon_quant_001", "counts", "render_salmon_quant_tab_0", "file")
    assert _has_edge(workflow, "kallisto_quant_001", "abundance", "render_kallisto_quant_tab_1", "file")
    assert _has_edge(workflow, "quant_comparison_001", "joined_table", "render_quant_comparison_tab_2", "file")


def test_differential_expression_template_compares_quantifier_outputs() -> None:
    workflow = _load_template("differential_expression.json")
    node_types = _node_types(workflow)

    assert node_types["salmon_quant_columns_001"] == "extract_columns"
    assert node_types["kallisto_quant_columns_001"] == "extract_columns"
    assert node_types["quant_comparison_001"] == "join_tables"

    salmon_columns = next(node for node in workflow["nodes"] if node["id"] == "salmon_quant_columns_001")
    kallisto_columns = next(node for node in workflow["nodes"] if node["id"] == "kallisto_quant_columns_001")
    comparison = next(node for node in workflow["nodes"] if node["id"] == "quant_comparison_001")

    assert salmon_columns["params"]["columns"] == "Name,TPM,NumReads"
    assert salmon_columns["params"]["rename_to"] == "target_id,salmon_tpm,salmon_reads"
    assert salmon_columns["params"]["output_type"] == "TSV"
    assert kallisto_columns["params"]["columns"] == "target_id,tpm,est_counts"
    assert kallisto_columns["params"]["rename_to"] == "target_id,kallisto_tpm,kallisto_est_counts"
    assert kallisto_columns["params"]["output_type"] == "TSV"
    assert comparison["params"]["join_keys"] == "target_id"
    assert comparison["params"]["how"] == "outer"
    assert comparison["params"]["delimiter"] == "tsv"
    assert comparison["params"]["left_suffix"] == "_salmon"
    assert comparison["params"]["right_suffix"] == "_kallisto"

    assert _has_edge(workflow, "salmon_quant_001", "counts", "salmon_quant_columns_001", "table")
    assert _has_edge(workflow, "kallisto_quant_001", "abundance", "kallisto_quant_columns_001", "table")
    assert _has_edge(workflow, "salmon_quant_columns_001", "extracted_table", "quant_comparison_001", "table_a")
    assert _has_edge(workflow, "kallisto_quant_columns_001", "extracted_table", "quant_comparison_001", "table_b")
    assert _has_edge(workflow, "quant_comparison_001", "joined_table", "render_quant_comparison_tab_2", "file")
    assert workflow["outputs"]["quantifier_comparison"] == "quant_comparison_001"


def test_assembly_template_validates_spades_assembly_before_quast_and_prokka() -> None:
    workflow = _load_template("assembly_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["validate_assembly_001"] == "data_validator"
    validator = next(node for node in workflow["nodes"] if node["id"] == "validate_assembly_001")
    assert validator["params"]["expected_format"] == "fasta"
    assert validator["params"]["min_records"] >= 1
    assert validator["params"]["min_size_bytes"] > 0
    assert validator["params"]["fail_on_error"] is True
    assert _has_edge(workflow, "select_assembly_001", "merged", "validate_assembly_001", "input")
    assert not _has_edge(workflow, "spades_001", "assembly", "validate_assembly_001", "input")
    assert not _has_edge(workflow, "megahit_001", "contigs", "validate_assembly_001", "input")
    assert _has_edge(workflow, "validate_assembly_001", "passthrough", "gate_assembly_001", "value")
    assert not _has_edge(workflow, "spades_001", "assembly", "quast_001", "assembly")
    assert not _has_edge(workflow, "spades_001", "assembly", "prokka_001", "assembly")
    assert workflow["outputs"]["validated_assembly"] == "validate_assembly_001"


def test_assembly_template_adds_megahit_switch_alternative() -> None:
    workflow = _load_template("assembly_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["switch_assembler_001"] == "switch"
    assert node_types["megahit_001"] == "megahit"
    assert node_types["select_assembly_001"] == "merge"
    switch = next(node for node in workflow["nodes"] if node["id"] == "switch_assembler_001")
    megahit = next(node for node in workflow["nodes"] if node["id"] == "megahit_001")
    selector = next(node for node in workflow["nodes"] if node["id"] == "select_assembly_001")
    assert switch["params"]["value"] == "spades"
    assert switch["params"]["cases"] == "spades,megahit"
    assert switch["params"]["num_branches"] == 2
    assert megahit["params"]["threads"] == 8
    assert megahit["params"]["min_contig_len"] == 200
    assert selector["params"] == {
        "num_inputs": 2,
        "strategy": "first_valid",
        "wait_mode": "any",
        "ignore_none": True,
    }

    assert _has_edge(workflow, "fastp_001", "trimmed_reads", "switch_assembler_001", "passthrough_data")
    assert _has_edge(workflow, "switch_assembler_001", "output_1", "spades_retry_001", "input")
    assert _has_edge(workflow, "spades_retry_001", "passthrough", "spades_001", "reads")
    assert _has_edge(workflow, "switch_assembler_001", "output_2", "megahit_001", "reads")
    assert _has_edge(workflow, "spades_001", "assembly", "select_assembly_001", "input_0")
    assert _has_edge(workflow, "megahit_001", "contigs", "select_assembly_001", "input_1")
    assert _has_edge(workflow, "select_assembly_001", "merged", "validate_assembly_001", "input")
    assert not _has_edge(workflow, "spades_001", "assembly", "validate_assembly_001", "input")
    assert not _has_edge(workflow, "megahit_001", "contigs", "validate_assembly_001", "input")
    assert not _has_edge(workflow, "fastp_001", "trimmed_reads", "spades_001", "reads")
    assert workflow["outputs"]["assembler_switch"] == "switch_assembler_001"
    assert workflow["outputs"]["megahit_assembly"] == "megahit_001"
    assert workflow["outputs"]["assembly"] == "select_assembly_001"
    assert workflow["outputs"]["selected_assembly"] == "select_assembly_001"


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

    assert "validate_reads_001" not in node_types
    validator = _output_validation(workflow, "reads_001", "reads")
    assert validator["expected_format"] == "fastq"
    assert validator["min_records"] >= 1
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert not _has_edge(workflow, "reads_001", "reads", "validate_reads_001", "input")
    assert _has_edge(workflow, "reads_001", "reads", "fastp_001", "reads")
    assert _has_edge(workflow, "fastp_001", "trimmed_reads", "switch_assembler_001", "passthrough_data")
    assert _has_edge(workflow, "reads_001", "reads", "fastp_001", "reads")
    assert not _has_edge(workflow, "reads_001", "reads", "spades_001", "reads")
    assert not _has_edge(workflow, "fastp_001", "trimmed_reads", "spades_001", "reads")
    assert workflow["outputs"]["validated_reads"] == "reads_001"


def test_assembly_template_validates_reference_before_quast() -> None:
    workflow = _load_template("assembly_pipeline.json")
    node_types = _node_types(workflow)

    assert "validate_reference_001" not in node_types
    validator = _output_validation(workflow, "ref_001", "reference")
    assert validator["expected_format"] == "fasta"
    assert validator["min_records"] >= 1
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert not _has_edge(workflow, "ref_001", "reference", "validate_reference_001", "input")
    assert _has_edge(workflow, "ref_001", "reference", "quast_001", "reference")
    assert _has_edge(workflow, "ref_001", "reference", "quast_001", "reference")
    assert workflow["outputs"]["validated_reference"] == "ref_001"


def test_assembly_template_adds_annotation_html_report() -> None:
    workflow = _load_template("assembly_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["render_prokka_tab_0"] == "table_preview"
    assert node_types["render_assembly_stats_tab_1"] == "table_preview"
    assert _has_edge(workflow, "prokka_001", "gff", "render_prokka_tab_0", "file")
    assert _has_edge(workflow, "assembly_stats_001", "stats_tsv", "render_assembly_stats_tab_1", "file")


def test_assembly_template_validates_quast_report_before_preview() -> None:
    workflow = _load_template("assembly_pipeline.json")
    node_types = _node_types(workflow)

    assert "validate_quast_001" not in node_types
    validator = _output_validation(workflow, "quast_001", "report")
    assert validator["expected_format"] == "text"
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert not _has_edge(workflow, "quast_001", "report", "validate_quast_001", "input")
    assert workflow["outputs"]["validated_quast_report"] == "quast_001"


def test_chip_seq_template_trims_reads_before_alignment_and_qc() -> None:
    workflow = _load_template("chip_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["fastp_001"] == "fastp"
    fastp = next(node for node in workflow["nodes"] if node["id"] == "fastp_001")
    assert fastp["params"]["threads"] == 4
    assert _has_edge(workflow, "treat_001", "reads", "fastp_001", "reads")
    assert _has_edge(workflow, "fastp_001", "trimmed_reads", "gate_trimmed_reads_001", "value")
    assert _has_edge(workflow, "treat_001", "reads", "fastp_001", "reads")
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

    assert "validate_reads_001" not in node_types
    validator = _output_validation(workflow, "treat_001", "reads")
    assert validator["expected_format"] == "fastq"
    assert validator["min_records"] >= 1
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert not _has_edge(workflow, "treat_001", "reads", "validate_reads_001", "input")
    assert _has_edge(workflow, "treat_001", "reads", "fastp_001", "reads")
    assert _has_edge(workflow, "treat_001", "reads", "fastp_001", "reads")
    assert workflow["outputs"]["validated_reads"] == "treat_001"


def test_chip_seq_template_adds_control_sample_for_macs2() -> None:
    workflow = _load_template("chip_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["control_001"] == "input_fastq"
    assert "validate_control_reads_001" not in node_types
    assert node_types["fastp_control_001"] == "fastp"
    assert node_types["gate_control_reads_001"] == "gate"
    assert node_types["bt2_control_001"] == "bowtie2_align"
    assert node_types["view_control_001"] == "samtools_view"
    assert node_types["sort_control_001"] == "samtools_sort"

    control = next(node for node in workflow["nodes"] if node["id"] == "control_001")
    validator = _output_validation(workflow, "control_001", "reads")
    gate = next(node for node in workflow["nodes"] if node["id"] == "gate_control_reads_001")
    assert control["params"]["sample_name"] == "control"
    assert validator["expected_format"] == "fastq"
    assert validator["fail_on_error"] is True
    assert gate["params"]["condition_mode"] == "is_not_empty"
    assert gate["params"]["on_fail"] == "halt"

    assert not _has_edge(workflow, "control_001", "reads", "validate_control_reads_001", "input")
    assert _has_edge(workflow, "control_001", "reads", "fastp_control_001", "reads")
    assert _has_edge(workflow, "fastp_control_001", "trimmed_reads", "gate_control_reads_001", "value")
    assert _has_edge(workflow, "gate_control_reads_001", "output", "bt2_control_001", "reads")
    assert _has_edge(workflow, "bt2build_001", "index", "bt2_control_001", "index")
    assert _has_edge(workflow, "bt2_control_001", "alignment", "view_control_001", "alignment")
    assert _has_edge(workflow, "view_control_001", "bam", "sort_control_001", "alignment")
    assert _has_edge(workflow, "sort_control_001", "sorted_bam", "macs2_001", "control")
    assert workflow["outputs"]["control_alignment"] == "sort_control_001"
    assert workflow["outputs"]["validated_control_reads"] == "control_001"


def test_chip_seq_template_builds_index_from_real_reference_before_alignment() -> None:
    # The placeholder bowtie2_index dir was replaced with the real yeast reference
    # (nf-core chipseq) + a bowtie2_build step feeding both alignments.
    workflow = _load_template("chip_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert "idx_001" not in node_types
    assert node_types["genome_001"] == "input_fasta"
    assert node_types["bt2build_001"] == "bowtie2_build"
    genome = next(n for n in workflow["nodes"] if n["id"] == "genome_001")
    assert genome["params"]["reference"] == "templates/data/smoke/reference.fasta"
    assert _has_edge(workflow, "genome_001", "reference", "bt2build_001", "reference")
    assert _has_edge(workflow, "bt2build_001", "index", "bt2_001", "index")
    assert _has_edge(workflow, "bt2build_001", "index", "bt2_control_001", "index")


def test_chip_seq_template_generates_bigwig_coverage_track() -> None:
    workflow = _load_template("chip_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["index_001"] == "samtools_index"
    assert node_types["coverage_001"] == "deeptools_bamcoverage"
    coverage = next(node for node in workflow["nodes"] if node["id"] == "coverage_001")
    assert coverage["params"]["threads"] == 4
    assert coverage["params"]["normalize_using"] == "CPM"
    assert coverage["params"]["bin_size"] == 10
    assert coverage["params"]["ignore_duplicates"] is True
    _assert_edge(workflow, "e4", "sort_001", "sorted_bam", "macs2_001", "treatment")
    _assert_edge(workflow, "e4_index", "sort_001", "sorted_bam", "index_001", "bam")
    _assert_edge(workflow, "e4a", "index_001", "indexed_bam", "coverage_001", "bam")
    _assert_edge(workflow, "e4a_bai", "index_001", "bai", "coverage_001", "bam_index")
    assert not _has_edge(workflow, "sort_001", "sorted_bam", "coverage_001", "bam")
    assert workflow["outputs"]["coverage_track"] == "coverage_001"


def test_chip_seq_template_validates_macs2_peak_output() -> None:
    workflow = _load_template("chip_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert "validate_peaks_001" not in node_types
    validator = _output_validation(workflow, "macs2_001", "peaks")
    assert validator["expected_format"] == "text"
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert not _has_edge(workflow, "macs2_001", "peaks", "validate_peaks_001", "input")
    assert workflow["outputs"]["validated_peaks"] == "macs2_001"


def test_chip_seq_template_annotates_validated_peaks_to_nearest_features() -> None:
    workflow = _load_template("chip_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["peak_annotation_bed_001"] == "input_file"
    assert "validate_peak_annotation_bed_001" not in node_types
    assert node_types["sort_peaks_bed_001"] == "bedtools_sortbed"
    assert node_types["sort_peak_annotations_bed_001"] == "bedtools_sortbed"
    assert node_types["peak_annotation_001"] == "bedtools_closest"

    annotation_input = next(node for node in workflow["nodes"] if node["id"] == "peak_annotation_bed_001")
    validator = _output_validation(workflow, "peak_annotation_bed_001", "file")
    annotator = next(node for node in workflow["nodes"] if node["id"] == "peak_annotation_001")
    assert annotation_input["params"]["file"].endswith("genes.bed")
    assert validator["expected_format"] == "text"
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert annotator["params"]["distance"] is True
    assert annotator["params"]["mode"] == "first"

    assert not _has_edge(workflow, "peak_annotation_bed_001", "file", "validate_peak_annotation_bed_001", "input")
    assert _has_edge(workflow, "macs2_001", "peaks", "sort_peaks_bed_001", "input")
    assert _has_edge(
        workflow,
        "peak_annotation_bed_001",
        "file",
        "sort_peak_annotations_bed_001",
        "input",
    )
    assert _has_edge(
        workflow,
        "sort_peaks_bed_001",
        "sorted_intervals",
        "peak_annotation_001",
        "variants",
    )
    assert _has_edge(
        workflow,
        "sort_peak_annotations_bed_001",
        "sorted_intervals",
        "peak_annotation_001",
        "annotations",
    )
    assert not _has_edge(workflow, "macs2_001", "peaks", "peak_annotation_001", "variants")
    assert not _has_edge(workflow, "peak_annotation_bed_001", "file", "peak_annotation_001", "annotations")
    assert _has_edge(workflow, "peak_annotation_001", "closest", "render_peak_annotation_tab_1", "file")
    assert workflow["outputs"]["validated_peak_annotation_bed"] == "peak_annotation_bed_001"
    assert workflow["outputs"]["peak_annotation"] == "peak_annotation_001"
    result = validate_workflow(workflow, NodeRegistry.create_isolated())
    assert result.valid, result.errors


def test_chip_seq_template_validates_multiqc_report_before_preview() -> None:
    workflow = _load_template("chip_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert "validate_multiqc_001" not in node_types
    validator = _output_validation(workflow, "mqc_001", "report")
    assert validator["expected_format"] == "text"
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert not _has_edge(workflow, "mqc_001", "report", "validate_multiqc_001", "input")
    assert workflow["outputs"]["validated_multiqc_report"] == "mqc_001"


def test_metagenomics_template_adds_bracken_taxonomy_chart_report() -> None:
    workflow = _load_template("metagenomics_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["bracken_bar_001"] == "bar_chart"
    assert "bracken_heatmap_001" not in node_types
    assert "render_bracken_bar_ima_1" not in node_types
    assert node_types["render_bracken_tab_0"] == "table_preview"
    chart = next(node for node in workflow["nodes"] if node["id"] == "bracken_bar_001")
    assert chart["params"]["x_column"] == "name"
    assert chart["params"]["y_column"] == "fraction_total_reads"
    assert chart["params"]["orientation"] == "horizontal"
    assert chart["params"]["format"] == "svg"
    assert _has_edge(workflow, "bracken_001", "abundance", "bracken_bar_001", "table")
    assert _has_edge(workflow, "bracken_001", "report", "render_bracken_tab_0", "file")
    assert workflow["outputs"]["taxonomy_chart"] == "bracken_bar_001"
    assert "taxonomy_heatmap" not in workflow["outputs"]


def test_metagenomics_template_validates_reads_before_trimming_and_qc() -> None:
    workflow = _load_template("metagenomics_pipeline.json")
    node_types = _node_types(workflow)

    assert "validate_reads_001" not in node_types
    validator = _output_validation(workflow, "reads_001", "reads")
    assert validator["expected_format"] == "fastq"
    assert validator["min_records"] >= 1
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert not _has_edge(workflow, "reads_001", "reads", "validate_reads_001", "input")
    assert _has_edge(workflow, "reads_001", "reads", "fastp_001", "reads")
    assert _has_edge(workflow, "reads_001", "reads", "qc_001", "reads")
    assert _has_edge(workflow, "reads_001", "reads", "fastp_001", "reads")
    assert _has_edge(workflow, "reads_001", "reads", "qc_001", "reads")
    assert workflow["outputs"]["validated_reads"] == "reads_001"


def test_metagenomics_template_gates_trimmed_reads_before_profiling() -> None:
    workflow = _load_template("metagenomics_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["gate_trimmed_reads_001"] == "gate"
    gate = next(node for node in workflow["nodes"] if node["id"] == "gate_trimmed_reads_001")
    assert gate["params"]["condition_mode"] == "is_not_empty"
    assert gate["params"]["on_fail"] == "halt"
    assert "trimmed reads" in gate["params"]["error_message"]
    assert _has_edge(workflow, "fastp_001", "trimmed_reads", "gate_trimmed_reads_001", "value")
    assert _has_edge(workflow, "gate_trimmed_reads_001", "output", "kraken2_retry_001", "input")
    assert _has_edge(workflow, "kraken2_retry_001", "passthrough", "kraken2_001", "reads")
    assert _has_edge(workflow, "gate_trimmed_reads_001", "output", "metaphlan_001", "reads")
    assert node_types["humann_reads_001"] == "input_file"
    assert _has_edge(workflow, "humann_reads_001", "file", "humann_retry_001", "input")
    assert _has_edge(workflow, "humann_retry_001", "passthrough", "humann_001", "input")
    assert _has_edge(workflow, "metaphlan_001", "profile", "humann_001", "taxonomic_profile")
    assert _has_edge(
        workflow,
        "humann_nucleotide_db_001",
        "directory",
        "humann_001",
        "nucleotide_database",
    )
    assert _has_edge(
        workflow,
        "humann_protein_db_001",
        "directory",
        "humann_001",
        "protein_database",
    )
    assert not _has_edge(workflow, "fastp_001", "trimmed_reads", "kraken2_001", "reads")
    assert not _has_edge(workflow, "fastp_001", "trimmed_reads", "metaphlan_001", "reads")
    assert not _has_edge(workflow, "fastp_001", "trimmed_reads", "humann_001", "input")
    assert workflow["outputs"]["trimmed_reads_quality_gate"] == "gate_trimmed_reads_001"


def test_metagenomics_template_validates_database_directory_before_profiling() -> None:
    workflow = _load_template("metagenomics_pipeline.json")
    node_types = _node_types(workflow)

    assert "validate_db_001" not in node_types
    validator = _output_validation(workflow, "db_001", "directory")
    assert validator["expected_format"] == "directory"
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert not _has_edge(workflow, "db_001", "directory", "validate_db_001", "input")
    assert _has_edge(workflow, "db_001", "directory", "kraken2_001", "db")
    assert _has_edge(workflow, "db_001", "directory", "bracken_001", "db")
    assert _has_edge(workflow, "metaphlan_db_001", "directory", "metaphlan_001", "database")
    assert _has_edge(workflow, "krona_taxonomy_001", "directory", "krona_001", "taxonomy")
    assert _has_edge(workflow, "kraken2_001", "classification", "krona_001", "classification")
    assert workflow["outputs"]["validated_db"] == "db_001"


def test_metagenomics_template_validates_bracken_report_before_visualization() -> None:
    workflow = _load_template("metagenomics_pipeline.json")
    node_types = _node_types(workflow)

    assert "validate_bracken_001" not in node_types
    validator = _output_validation(workflow, "bracken_001", "report")
    assert validator["expected_format"] == "text"
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert not _has_edge(workflow, "bracken_001", "report", "validate_bracken_001", "input")
    assert _has_edge(workflow, "bracken_001", "abundance", "bracken_bar_001", "table")
    assert "bracken_heatmap_001" not in node_types
    assert _has_edge(workflow, "bracken_001", "report", "render_bracken_tab_0", "file")
    assert workflow["outputs"]["validated_bracken_report"] == "bracken_001"


def test_metagenomics_template_validates_metaphlan_profile_before_visualization() -> None:
    workflow = _load_template("metagenomics_pipeline.json")
    node_types = _node_types(workflow)

    assert "validate_metaphlan_profile_001" not in node_types
    validator = _output_validation(workflow, "metaphlan_001", "profile")
    assert validator["expected_format"] == "tsv"
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert not _has_edge(workflow, "metaphlan_001", "profile", "validate_metaphlan_profile_001", "input")
    assert _has_edge(workflow, "metaphlan_001", "profile", "metaphlan_bar_001", "table")
    assert _has_edge(workflow, "metaphlan_001", "profile", "metaphlan_bar_001", "table")
    assert workflow["outputs"]["validated_metaphlan_profile"] == "metaphlan_001"


def test_metagenomics_template_validates_humann_pathcoverage_before_reporting() -> None:
    workflow = _load_template("metagenomics_pipeline.json")
    node_types = _node_types(workflow)

    assert "validate_humann_pathcoverage_001" not in node_types
    validator = _output_validation(workflow, "humann_001", "pathcoverage")
    assert validator["expected_format"] == "tsv"
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert not _has_edge(workflow, "humann_001", "pathcoverage", "validate_humann_pathcoverage_001", "input")
    assert _has_edge(workflow, "humann_001", "pathcoverage", "humann_pathcoverage_bar_001", "table")
    assert _has_edge(workflow, "humann_001", "pathcoverage", "render_humann_tab_1", "file")
    assert workflow["outputs"]["validated_humann_pathcoverage"] == "humann_001"
    assert workflow["outputs"]["functional_pathcoverage_chart"] == "humann_pathcoverage_bar_001"


def test_metagenomics_template_validates_multiqc_report_before_preview() -> None:
    workflow = _load_template("metagenomics_pipeline.json")
    node_types = _node_types(workflow)

    assert "validate_multiqc_001" not in node_types
    validator = _output_validation(workflow, "mqc_001", "report")
    assert validator["expected_format"] == "text"
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert not _has_edge(workflow, "mqc_001", "report", "validate_multiqc_001", "input")
    assert workflow["outputs"]["validated_multiqc_report"] == "mqc_001"


def test_single_cell_template_validates_input_directories_before_cellranger() -> None:
    workflow = _load_template("single_cell_pipeline.json")
    node_types = _node_types(workflow)

    assert "validate_fastq_dir_001" not in node_types
    assert "validate_reference_dir_001" not in node_types
    fastq_validator = _output_validation(workflow, "fastq_001", "directory")
    ref_validator = _output_validation(workflow, "ref_001", "directory")
    assert fastq_validator["expected_format"] == "directory"
    assert ref_validator["expected_format"] == "directory"
    assert fastq_validator["min_size_bytes"] > 0
    assert ref_validator["min_size_bytes"] > 0
    assert fastq_validator["fail_on_error"] is True
    assert ref_validator["fail_on_error"] is True
    assert not _has_edge(workflow, "fastq_001", "directory", "validate_fastq_dir_001", "input")
    assert _has_edge(workflow, "fastq_001", "directory", "cr_count_retry_001", "input")
    assert _has_edge(workflow, "cr_count_retry_001", "passthrough", "cr_count_001", "fastq_dir")
    assert not _has_edge(workflow, "ref_001", "directory", "validate_reference_dir_001", "input")
    assert _has_edge(workflow, "ref_001", "directory", "cr_count_001", "transcriptome")
    assert not _has_edge(workflow, "fastq_001", "directory", "cr_count_001", "fastq_dir")
    assert _has_edge(workflow, "ref_001", "directory", "cr_count_001", "transcriptome")
    assert workflow["outputs"]["validated_fastq_dir"] == "fastq_001"
    assert workflow["outputs"]["validated_reference_dir"] == "ref_001"


def test_single_cell_template_validates_cellranger_web_summary_before_preview() -> None:
    workflow = _load_template("single_cell_pipeline.json")
    node_types = _node_types(workflow)

    assert "validate_web_summary_001" not in node_types
    assert node_types["gate_web_summary_001"] == "gate"
    validator = _output_validation(workflow, "cr_count_001", "web_summary")
    gate = next(node for node in workflow["nodes"] if node["id"] == "gate_web_summary_001")
    assert validator["expected_format"] == "text"
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert gate["params"]["condition_mode"] == "file_exists"
    assert gate["params"]["on_fail"] == "halt"
    assert "web_summary" in gate["params"]["error_message"]
    assert not _has_edge(workflow, "cr_count_001", "web_summary", "validate_web_summary_001", "input")
    assert _has_edge(workflow, "cr_count_001", "web_summary", "gate_web_summary_001", "value")
    assert workflow["outputs"]["validated_web_summary"] == "cr_count_001"
    assert workflow["outputs"]["web_summary_quality_gate"] == "gate_web_summary_001"


def test_single_cell_template_adds_qc_dashboard_and_report() -> None:
    workflow = _load_template("single_cell_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["qc_dashboard_001"] == "qc_dashboard"
    assert node_types["qc_dashboard_preview_001"] == "html_preview"
    # The single_cell_report_001 html_report and its html_preview were removed by design.
    assert "single_cell_report_001" not in node_types
    assert "single_cell_report_preview_001" not in node_types
    assert node_types["render_cr_count_tab_0"] == "table_preview"
    assert "render_metrics_summary_chart_ima_1" not in node_types
    # Cell Ranger 9.0.1 writes a wide, two-line metrics CSV rather than a
    # Metric Name/Metric Value table; preview the native table directly.
    assert "metrics_summary_chart_001" not in node_types

    dashboard = next(node for node in workflow["nodes"] if node["id"] == "qc_dashboard_001")
    assert dashboard["params"]["run_name"] == "Single Cell QC"
    assert dashboard["params"]["title"] == "Single Cell QC Dashboard"

    assert _has_edge(workflow, "qc_dashboard_001", "qc_dashboard", "qc_dashboard_preview_001", "file")
    assert not _has_edge(workflow, "cr_count_001", "metrics_summary", "metrics_summary_chart_001", "table")
    assert _has_edge(workflow, "cr_count_001", "metrics_summary", "render_cr_count_tab_0", "file")
    assert workflow["outputs"]["qc_dashboard"] == "qc_dashboard_001"
    assert "metrics_summary_chart" not in workflow["outputs"]
    assert "report" not in workflow["outputs"]
