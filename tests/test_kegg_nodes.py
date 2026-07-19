"""Compact KEGG REST contract tests."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from bionodulo.nodes.registry import NodeRegistry


def _node() -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node = registry.get("kegg_pathway")
    assert node is not None
    return node


def test_kegg_node_is_focused_rate_limited_and_has_no_hidden_image_mode() -> None:
    node = _node()
    assert node.__module__ == "bionodulo.nodes.builtin.kegg_family.pathway"
    assert node.RETURN_NAMES == ("pathway_data", "gene_list_tsv")
    options = node.INPUT_TYPES()
    assert options["required"]["query_type"][1]["options"] == [
        "pathway_info",
        "pathway_genes",
        "list_pathways",
        "gene_info",
        "find_genes",
        "compound_info",
        "find_compounds",
        "link_kegg",
    ]
    assert "download_image" not in options["optional"]
    assert "three per second" in node.RATE_LIMIT_SEMANTICS
    assert "commercial" in node.LICENSE_SEMANTICS


@pytest.mark.asyncio
async def test_kegg_pathway_genes_uses_documented_link_resource(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node = _node()
    module = importlib.import_module(node.__module__)
    calls: list[str] = []

    async def fake_text(resource: str) -> str:
        calls.append(resource)
        return "path:hsa04110\thsa:1017\npath:hsa04110\thsa:1019\n"

    monkeypatch.setattr(module, "_request_text", fake_text)
    result = await node().run(
        query="04110",
        query_type="pathway_genes",
        organism="hsa",
        context=SimpleNamespace(node_dir=tmp_path),
    )
    payload = json.loads(Path(result["outputs"]["pathway_data"]).read_text(encoding="utf-8"))
    table = Path(result["outputs"]["gene_list_tsv"]).read_text(encoding="utf-8")
    assert calls == ["link/genes/hsa04110"]
    assert payload["effective_query"] == "hsa04110"
    assert payload["entries"] == [
        {"id": "path:hsa04110", "value": "hsa:1017"},
        {"id": "path:hsa04110", "value": "hsa:1019"},
    ]
    assert table == "id\tvalue\npath:hsa04110\thsa:1017\npath:hsa04110\thsa:1019\n"


@pytest.mark.asyncio
async def test_kegg_rejects_empty_non_list_query() -> None:
    node = _node()
    with pytest.raises(ValueError, match="non-empty query"):
        await node().run(query="", query_type="pathway_info")
