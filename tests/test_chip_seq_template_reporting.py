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


def test_chip_seq_template_adds_final_html_report_from_validated_peaks() -> None:
    workflow = _load_template("chip_seq_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types.get("peak_annotation_001") == "bedtools_closest"
    assert node_types.get("sort_peaks_bed_001") == "bedtools_sortbed"
    assert node_types.get("sort_peak_annotations_bed_001") == "bedtools_sortbed"
    assert node_types.get("render_macs2_tab_0") == "table_preview"
    assert node_types.get("render_peak_annotation_tab_1") == "table_preview"
    assert "render_chip_signal_plot_ima_2" not in node_types

    annotator = _node_by_id(workflow, "peak_annotation_001")
    assert annotator["params"]["distance"] is True
    assert annotator["params"]["mode"] == "first"

    assert _has_edge(workflow, "macs2_001", "peaks", "render_macs2_tab_0", "file")
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
    assert _has_edge(workflow, "peak_annotation_001", "closest", "render_peak_annotation_tab_1", "file")
    assert workflow["outputs"]["peak_annotation"] == "peak_annotation_001"


def test_chip_seq_template_nodes_have_distinct_editor_positions() -> None:
    workflow = _load_template("chip_seq_pipeline.json")
    positions = [tuple(node["position"]) for node in workflow["nodes"]]

    assert len(positions) == len(set(positions))
