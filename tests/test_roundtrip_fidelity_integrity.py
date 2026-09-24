"""Metric regressions: unavailable execution is not perfect roundtrip fidelity."""
from __future__ import annotations

import json

from scripts.roundtrip_fidelity import evaluate_template, score_roundtrip


def test_unsupported_computational_nodes_are_failures_for_every_target(tmp_path):
    path = tmp_path / "unsupported.json"
    path.write_text(json.dumps({"nodes": [{"id": "n", "type": "unsupported_phd_tool", "params": {"method": "cpm"}}], "edges": []}))
    result = evaluate_template(path)
    assert len(result["targets"]) == 4
    for entry in result["targets"].values():
        assert "unsupported node type" in entry["error"]
        assert entry["f_target"] == 0


def test_rewired_edges_lose_topology_even_when_edge_count_is_equal():
    nodes = [{"id": name, "type": "fastqc"} for name in "abc"]
    original = {"nodes": nodes, "edges": [{"source": "a", "target": "b", "source_output": "report", "target_input": "reads"}]}
    restored = {"nodes": nodes, "edges": [{"source": "b", "target": "c", "source_output": "report", "target_input": "reads"}]}
    result = score_roundtrip(original, restored)
    assert result["s_nodes"] == 1
    assert result["s_edges"] == 0
    assert result["f_target"] == 0


def test_lost_annotations_and_provenance_are_measured_not_assumed():
    original = {"provenance": {"run": "actual-run"}, "nodes": [{"id": "n", "type": "fastqc", "semantic_state": {"reference_assembly": "grch38"}}], "edges": []}
    restored = {"nodes": [{"id": "n", "type": "fastqc"}], "edges": []}
    result = score_roundtrip(original, restored)
    assert result["s_ann"] == 0
    assert result["s_provenance"] == 0
    assert result["f_target"] == 0
    no_annotations = score_roundtrip(restored, restored)
    assert no_annotations["s_ann"] is None
    assert no_annotations["s_provenance"] is None


def test_empty_graph_has_no_roundtrip_score():
    assert score_roundtrip({"nodes": [], "edges": []}, {"nodes": [], "edges": []})["f_target"] is None
