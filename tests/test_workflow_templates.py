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
