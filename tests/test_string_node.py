"""Compact STRING 12.0 API contracts."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from bionodulo.nodes.registry import NodeRegistry


def _node() -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node = registry.get("string_db")
    assert node is not None
    return node


def test_string_node_is_version_pinned_and_preserves_template_ports() -> None:
    node = _node()
    module = importlib.import_module(node.__module__)
    assert node.__module__ == "bionodulo.nodes.builtin.string_db_family.network"
    assert node.VERSION == "12.0"
    assert module.STRING_BASE_URL == "https://version-12-0.string-db.org/api"
    assert node.RETURN_NAMES == ("interaction_network", "network_metadata")
    options = node.INPUT_TYPES()
    assert options["required"] == {}
    assert "protein_ids" in options["optional"]
    assert options["optional"]["protein_ids"][1]["displayOptions"] == {
        "show": {"protein_table": [""]},
    }
    assert options["optional"]["query_type"][1]["options"] == [
        "network",
        "interactions",
        "enrichment",
        "mapping",
    ]
    assert "protein_table" in options["optional"]
    assert "network_flavor" not in options["optional"]
    assert "image" not in options["optional"]["query_type"][1]["options"]


@pytest.mark.asyncio
async def test_string_transport_posts_to_stable_address(monkeypatch: pytest.MonkeyPatch) -> None:
    node = _node()
    module = importlib.import_module(node.__module__)
    calls: list[dict[str, Any]] = []

    class FakeClient:
        def __init__(self, *, cache: object | None = None, rate_limiter: object | None = None) -> None:
            self.cache = cache
            self.rate_limiter = rate_limiter

        async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
            calls.append({"method": method, "url": url, **kwargs})
            return httpx.Response(200, text="preferredName_A\tpreferredName_B\nTP53\tMDM2\n", request=httpx.Request(method, url))

    monkeypatch.setattr(module, "APIHttpClient", FakeClient)
    text = await module._request_text("tsv/network", {"identifiers": "TP53\rMDM2", "species": 9606})
    assert text.startswith("preferredName_A")
    assert calls[0]["method"] == "POST"
    assert calls[0]["url"] == "https://version-12-0.string-db.org/api/tsv/network"
    assert calls[0]["data"] == {"identifiers": "TP53\rMDM2", "species": 9606}


@pytest.mark.asyncio
async def test_string_network_uses_documented_text_parameters(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node = _node()
    module = importlib.import_module(node.__module__)
    calls: list[tuple[str, dict[str, Any]]] = []
    response = "preferredName_A\tpreferredName_B\tscore\nTP53\tMDM2\t0.999\n"

    async def fake_text(endpoint: str, data: dict[str, Any]) -> str:
        calls.append((endpoint, dict(data)))
        return response

    monkeypatch.setattr(module, "_request_text", fake_text)
    result = await node().run(
        protein_ids="TP53,MDM2,TP53",
        species=9606,
        query_type="network",
        required_score=700,
        network_type="physical",
        add_nodes=2,
        context=SimpleNamespace(node_dir=tmp_path),
    )
    assert calls == [
        (
            "tsv/network",
            {
                "identifiers": "TP53\rMDM2",
                "species": 9606,
                "caller_identity": "BioNodulo",
                "required_score": 700,
                "add_nodes": 2,
                "network_type": "physical",
            },
        )
    ]
    metadata = json.loads(Path(result["outputs"]["network_metadata"]).read_text(encoding="utf-8"))
    assert metadata["string_version"] == "12.0"
    assert metadata["identifiers"] == ["TP53", "MDM2"]
    assert metadata["record_count"] == 1


@pytest.mark.asyncio
async def test_string_preserves_zero_required_score(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    node = _node()
    module = importlib.import_module(node.__module__)

    async def fake_text(endpoint: str, data: dict[str, Any]) -> str:
        assert data["required_score"] == 0
        return "preferredName_A\tpreferredName_B\nTP53\tMDM2\n"

    monkeypatch.setattr(module, "_request_text", fake_text)
    await node().run(
        protein_ids="TP53,MDM2",
        required_score=0,
        context=SimpleNamespace(node_dir=tmp_path),
    )


@pytest.mark.asyncio
async def test_string_reads_template_table_and_rejects_removed_image_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node = _node()
    module = importlib.import_module(node.__module__)
    table = tmp_path / "genes.tsv"
    table.write_text("gene\tpadj\nTP53\t0.01\nMDM2\t0.02\n", encoding="utf-8")

    async def fake_text(endpoint: str, data: dict[str, Any]) -> str:
        assert data["identifiers"] == "TP53\rMDM2"
        return "category\tterm\nProcess\tGO:0006915\n"

    monkeypatch.setattr(module, "_request_text", fake_text)
    await node().run(
        protein_ids="",
        protein_table=str(table),
        id_column="gene",
        query_type="enrichment",
        context=SimpleNamespace(node_dir=tmp_path),
    )
    with pytest.raises(ValueError, match="Unsupported STRING query_type"):
        await node().run(protein_ids="TP53", query_type="image")
