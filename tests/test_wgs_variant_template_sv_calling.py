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


def test_wgs_variant_template_adds_parallel_manta_and_delly_sv_calling() -> None:
    workflow = _load_template("wgs_variant_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["manta_sv_001"] == "manta_call"
    assert node_types["delly_sv_001"] == "delly_call"
    assert node_types["idx_001"] == "samtools_index"
    assert node_types["render_manta_sv_tab_0"] == "vcf_stats_chart"
    assert node_types["render_delly_sv_tab_1"] == "vcf_stats_chart"

    manta = _node_by_id(workflow, "manta_sv_001")
    delly = _node_by_id(workflow, "delly_sv_001")
    assert manta["params"]["threads"] == 4
    assert manta["params"]["exome"] is False
    assert manta["params"]["rna"] is False
    assert delly["params"]["mode"] == "call"
    assert delly["params"]["map_qual"] == 1

    _assert_edge(workflow, "e19a", "idx_001", "indexed_bam", "manta_sv_001", "bam")
    _assert_edge(workflow, "e19a_bai", "idx_001", "bai", "manta_sv_001", "bam_index")
    assert _has_edge(workflow, "ref_sidecars_001", "reference", "manta_sv_001", "reference")
    assert _has_edge(workflow, "ref_sidecars_001", "fai_index", "manta_sv_001", "reference_index")
    _assert_edge(workflow, "e19c", "idx_001", "indexed_bam", "delly_sv_001", "bam")
    _assert_edge(workflow, "e19c_bai", "idx_001", "bai", "delly_sv_001", "bam_index")
    assert _has_edge(workflow, "ref_sidecars_001", "reference", "delly_sv_001", "reference")
    assert _has_edge(workflow, "ref_sidecars_001", "fai_index", "delly_sv_001", "reference_index")
    assert not _has_edge(workflow, "markdup_001", "marked_bam", "manta_sv_001", "bam")
    assert not _has_edge(workflow, "markdup_001", "marked_bam", "delly_sv_001", "bam")
    assert _has_edge(workflow, "manta_sv_001", "sv_vcf", "render_manta_sv_tab_0", "vcf")
    assert _has_edge(workflow, "delly_sv_001", "sv_vcf", "render_delly_sv_tab_1", "vcf")
    assert workflow["outputs"]["manta_sv"] == "manta_sv_001"
    assert workflow["outputs"]["delly_sv"] == "delly_sv_001"
