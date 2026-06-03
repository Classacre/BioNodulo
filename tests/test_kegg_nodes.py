from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_kegg_pathway_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    assert info["kegg_pathway"]["display_name"] == "KEGG Pathway"
    assert info["kegg_pathway"]["category"] == "databases"
    assert info["kegg_pathway"]["output_name"] == ["pathway_data", "gene_list_tsv"]


@pytest.mark.asyncio
async def test_kegg_pathway_genes_writes_json_and_tsv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("kegg_pathway")
    module = importlib.import_module(node_class.__module__)
    calls: list[str] = []

    async def fake_text(resource: str, **_: Any) -> str:
        calls.append(resource)
        return (
            "path:hsa04110\thsa:1029\n"
            "path:hsa04110\thsa:51343\n"
        )

    monkeypatch.setattr(module, "_request_text", fake_text)
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(
        query="04110",
        query_type="pathway_genes",
        organism="hsa",
        output_name="cell_cycle",
        context=context,
    )

    json_path = Path(result["outputs"]["pathway_data"])
    tsv_path = Path(result["outputs"]["gene_list_tsv"])
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert json_path.name == "cell_cycle.json"
    assert tsv_path.name == "cell_cycle.tsv"
    assert payload["query"] == "04110"
    assert payload["effective_query"] == "hsa04110"
    assert payload["query_type"] == "pathway_genes"
    assert payload["entries"] == [
        {"id": "path:hsa04110", "value": "hsa:1029"},
        {"id": "path:hsa04110", "value": "hsa:51343"},
    ]
    assert tsv_path.read_text(encoding="utf-8") == (
        "id\tvalue\n"
        "path:hsa04110\thsa:1029\n"
        "path:hsa04110\thsa:51343\n"
    )
    assert calls == ["link/genes/hsa04110"]
