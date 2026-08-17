from __future__ import annotations

import csv
import io
import re
from typing import Any

import pytest

from bionodulo.converter.references import collect_references, export_references
from bionodulo.nodes.registry import NodeRegistry
from bionodulo.workflow.export import export_workflow


@pytest.fixture(scope="module")
def registry() -> NodeRegistry:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    return registry


def _workflow(*node_types: str, node_info: dict[str, Any] | None = None) -> dict:
    return {
        "id": "references-test",
        "name": "References Test",
        "nodes": [
            {
                "id": f"node-{index}",
                "type": node_type,
                "position": {"x": 0.0, "y": 0.0},
                "params": {},
                **({"node_info": node_info} if node_info else {}),
            }
            for index, node_type in enumerate(node_types)
        ],
        "edges": [],
    }


def test_collect_references_gathers_single_doi_node(registry: NodeRegistry) -> None:
    references = collect_references(_workflow("bayescan"), registry)
    node_class = registry.get("bayescan")

    assert len(references) == 1
    reference = references[0]
    assert reference["dois"] == ["10.1534/genetics.108.092221"]
    assert reference["nodes"] == [
        {
            "id": "node-0",
            "display_name": node_class.DISPLAY_NAME,
            "version": node_class.VERSION,
        }
    ]
    assert reference["text"]


def test_collect_references_skips_note_and_uncited_nodes(registry: NodeRegistry) -> None:
    references = collect_references(_workflow("note", "bayescan"), registry)

    node_ids = [node["id"] for reference in references for node in reference["nodes"]]
    assert node_ids == ["node-1"]


def test_collect_references_dedupes_nodes_sharing_a_doi(registry: NodeRegistry) -> None:
    references = collect_references(_workflow("abyss-pe", "abyss_pe"), registry)

    assert len(references) == 1
    assert references[0]["dois"] == ["10.1101/gr.214346.116", "10.1101/gr.089532.108"]
    assert [node["id"] for node in references[0]["nodes"]] == ["node-0", "node-1"]


def test_collect_references_falls_back_to_embedded_node_info() -> None:
    workflow = _workflow(
        "custom_unregistered",
        node_info={
            "display_name": "Custom Tool",
            "version": "2.1.0",
            "citation_dois": ["10.9999/fake"],
            "citation_urls": [],
            "citation_text": "A custom tool citation.",
        },
    )

    references = collect_references(workflow, None)

    assert references == [
        {
            "dois": ["10.9999/fake"],
            "urls": [],
            "text": "A custom tool citation.",
            "nodes": [{"id": "node-0", "display_name": "Custom Tool", "version": "2.1.0"}],
        }
    ]


def test_ris_multi_doi_reference_yields_one_record_per_doi(registry: NodeRegistry) -> None:
    exported = export_references(_workflow("abyss-pe"), registry, "ris")

    assert exported.count("TY  - JOUR") == 2
    assert exported.count("ER  - ") == 2
    assert "DO  - 10.1101/gr.214346.116" in exported
    assert "DO  - 10.1101/gr.089532.108" in exported


def test_ris_structure(registry: NodeRegistry) -> None:
    exported = export_references(_workflow("bayescan"), registry, "ris")

    assert exported.startswith("TY  - ")
    assert "DO  - 10.1534/genetics.108.092221" in exported
    assert exported.endswith("ER  - \n")
    assert "\r" not in exported
    assert "DB  - BioNodulo" in exported
    assert "KW  - node-0" in exported
    assert "TY  - COMP" not in exported


def test_ris_url_only_reference_uses_comp_type() -> None:
    workflow = _workflow(
        "custom_unregistered",
        node_info={
            "display_name": "Web Tool",
            "citation_urls": ["https://example.org/tool"],
            "citation_text": "A web tool without a DOI.",
        },
    )

    exported = export_references(workflow, None, "ris")

    assert "TY  - COMP" in exported
    assert "UR  - https://example.org/tool" in exported
    assert "DO  - " not in exported


def test_bibtex_entries_balance_braces_and_use_unique_keys(registry: NodeRegistry) -> None:
    workflow = _workflow("bayescan", "abyss-pe", "abyss_pe")
    exported = export_references(workflow, registry, "bibtex")

    entries = re.findall(r"@misc\{([^,]+),", exported)
    assert len(entries) == 2
    assert len(set(entries)) == len(entries)
    assert all(entry.startswith("bionodulo_") and len(entry) == len("bionodulo_") + 8 for entry in entries)

    assert exported.count("{") == exported.count("}")
    assert "10.1534/genetics.108.092221" in exported
    assert "used by: node-1, node-2" in exported


def test_csv_rows_parse_with_header_and_skip_doi_mirror_urls(registry: NodeRegistry) -> None:
    exported = export_references(_workflow("abyss-pe"), registry, "csv")

    rows = list(csv.reader(io.StringIO(exported, newline="")))
    assert rows[0] == ["node_id", "node_display_name", "node_version", "doi", "url", "citation_text"]
    assert len(rows) == 3
    assert rows[1][3] == "10.1101/gr.214346.116"
    assert rows[2][3] == "10.1101/gr.089532.108"
    assert all(row[4] == "" for row in rows[1:])


def test_empty_workflow_returns_empty_string_for_every_format(registry: NodeRegistry) -> None:
    for fmt in ("ris", "bibtex", "csv"):
        assert export_references({"nodes": [], "edges": []}, registry, fmt) == ""


def test_export_workflow_dispatches_reference_formats(registry: NodeRegistry) -> None:
    workflow = _workflow("bayescan")

    assert export_workflow(workflow, "ris", registry=registry).startswith("TY  - ")
    assert export_workflow(workflow, "bibtex", registry=registry).startswith("@misc{bionodulo_")
    assert export_workflow(workflow, "csv", registry=registry).startswith("node_id,")


def test_export_references_rejects_unknown_format(registry: NodeRegistry) -> None:
    with pytest.raises(ValueError, match="Unsupported references export format: 'xml'"):
        export_references(_workflow("bayescan"), registry, "xml")
