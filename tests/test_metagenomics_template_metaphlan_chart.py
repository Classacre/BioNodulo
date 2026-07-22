from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.builtin.visualization_family.adapter import _read_bar_rows


ROOT = Path(__file__).resolve().parents[1]


def _load_template(name: str) -> dict[str, Any]:
    return json.loads((ROOT / "templates" / name).read_text(encoding="utf-8"))


def _node_types(workflow: dict[str, Any]) -> dict[str, str]:
    return {str(node["id"]): str(node["type"]) for node in workflow["nodes"]}


def _node_by_id(workflow: dict[str, Any], node_id: str) -> dict[str, Any]:
    return next(node for node in workflow["nodes"] if node["id"] == node_id)



def _output_validation(workflow: dict[str, Any], node_id: str, output: str) -> dict[str, Any]:
    node = _node_by_id(workflow, node_id)
    return (
        node.get("ui", {})
        .get("validation", {})
        .get("outputs", {})
        .get(output, {})
    )

def _has_edge(workflow: dict[str, Any], source: str, source_output: str, target: str, target_input: str) -> bool:
    return any(
        edge.get("from") == {"node": source, "output": source_output}
        and edge.get("to") == {"node": target, "input": target_input}
        for edge in workflow["edges"]
    )


def test_metagenomics_template_charts_metaphlan_profile_in_taxonomy_report() -> None:
    workflow = _load_template("metagenomics_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["metaphlan_001"] == "metaphlan"
    assert "validate_metaphlan_profile_001" not in node_types
    assert node_types["metaphlan_bar_001"] == "bar_chart"
    # The taxonomy_report_001 html_report and its html_preview were removed by design;
    # the MetaPhlAn chart renders into a dedicated image_preview node.
    assert "taxonomy_report_001" not in node_types
    assert "taxonomy_report_preview_001" not in node_types
    assert "render_metaphlan_bar_ima_3" not in node_types

    validator = _output_validation(workflow, "metaphlan_001", "profile")
    chart = _node_by_id(workflow, "metaphlan_bar_001")
    assert validator["expected_format"] == "tsv"
    assert validator["min_size_bytes"] > 0
    assert validator["fail_on_error"] is True
    assert chart["params"]["title"] == "MetaPhlAn Relative Abundance"
    assert chart["params"]["x_column"] == "clade_name"
    assert chart["params"]["y_column"] == "relative_abundance"
    assert chart["params"]["orientation"] == "horizontal"
    assert chart["params"]["format"] == "svg"

    assert not _has_edge(workflow, "metaphlan_001", "profile", "validate_metaphlan_profile_001", "input")
    assert _has_edge(workflow, "metaphlan_001", "profile", "metaphlan_bar_001", "table")
    assert workflow["outputs"]["validated_metaphlan_profile"] == "metaphlan_001"
    assert workflow["outputs"]["metaphlan_chart"] == "metaphlan_bar_001"
    assert "taxonomy_report_preview" not in workflow["outputs"]


def test_bar_parser_skips_only_leading_metaphlan_metadata(tmp_path: Path) -> None:
    profile = tmp_path / "sample.metaphlan.tsv"
    profile.write_text(
        "#mpa_vJun23_CHOCOPhlAnSGB_202403\n"
        "#MetaPhlAn version 4.2.4\n"
        "#clade_name\tNCBI_tax_id\trelative_abundance\n"
        "k__Bacteria\t2\t97.5\n"
        "k__Archaea\t2157\t2.5\n",
        encoding="utf-8",
    )

    rows = _read_bar_rows(
        profile,
        delimiter="auto",
        x_column="clade_name",
        y_column="relative_abundance",
        group_column="",
    )

    assert [(row.category, row.value) for row in rows] == [
        ("k__Bacteria", 97.5),
        ("k__Archaea", 2.5),
    ]


def test_metaphlan_bar_parser_fails_closed_without_exact_header(tmp_path: Path) -> None:
    profile = tmp_path / "sample.metaphlan.tsv"
    profile.write_text(
        "#mpa_vJun23_CHOCOPhlAnSGB_202403\n"
        "#clade_name_extra\tNCBI_tax_id\trelative_abundance\n"
        "k__Bacteria\t2\t97.5\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="#clade_name"):
        _read_bar_rows(
            profile,
            delimiter="auto",
            x_column="clade_name",
            y_column="relative_abundance",
            group_column="",
        )


def test_generic_tsv_header_is_not_normalized(tmp_path: Path) -> None:
    table = tmp_path / "ordinary.tsv"
    table.write_text("#clade_name\trelative_abundance\nk__Bacteria\t97.5\n", encoding="utf-8")

    rows = _read_bar_rows(
        table,
        delimiter="auto",
        x_column="#clade_name",
        y_column="relative_abundance",
        group_column="",
    )

    assert rows[0].category == "k__Bacteria"
