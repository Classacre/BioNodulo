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


INTERACTION_TSV = (
    "stringId_A\tstringId_B\tpreferredName_A\tpreferredName_B\tncbiTaxonId\tscore\tnscore\t"
    "fscore\tpscore\tascore\tescore\tdscore\ttscore\n"
    "9606.ENSP00000269305\t9606.ENSP00000258149\tTP53\tMDM2\t9606\t0.999\t0\t0\t0\t0\t0.999\t0\t0\n"
)
ENRICHMENT_TSV = (
    "category\tterm\tnumber_of_genes\tnumber_of_genes_in_background\tncbiTaxonId\tinputGenes\t"
    "preferredNames\tp_value\tfdr\tdescription\n"
    "Process\tGO:0006915\t2\t500\t9606\tTP53,MDM2\tTP53,MDM2\t0.001\t0.01\tapoptotic process\n"
)
MAPPING_TSV = (
    "queryItem\tqueryIndex\tstringId\tncbiTaxonId\ttaxonName\tpreferredName\tannotation\n"
    "TP53\t0\t9606.ENSP00000269305\t9606\tHomo sapiens\tTP53\tCellular tumor antigen p53\n"
)


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
    assert node.SOURCE_URL == "https://version-12-0.string-db.org/help/api/"
    assert node.SOURCE_REVISION == "2026-06-02T11:15:10Z"
    assert node.SOURCE_SHA256 == "4c5af2b0805b739902ea439ac410882969a56f3a00fd6125c7449fc5ba96544c"
    assert module.STRING_RATE_LIMITER.rate_per_second == 1.0
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
    assert calls[0]["timeout"] == 30.0
    assert calls[0]["retries"] == 3
    assert calls[0]["retry_delay"] == 1.0
    assert calls[0]["cache_ttl"] is None


@pytest.mark.parametrize(
    ("query_type", "expected_endpoint", "expected_extra"),
    [
        (
            "network",
            "tsv/network",
            {"required_score": 700, "add_nodes": 2, "network_type": "physical"},
        ),
        (
            "interactions",
            "tsv/interaction_partners",
            {"required_score": 700, "limit": 25, "network_type": "physical"},
        ),
        ("enrichment", "tsv/enrichment", {}),
        ("mapping", "tsv/get_string_ids", {}),
    ],
)
def test_string_all_query_modes_use_documented_post_bodies(
    query_type: str,
    expected_endpoint: str,
    expected_extra: dict[str, Any],
) -> None:
    node = _node()
    module = importlib.import_module(node.__module__)
    endpoint, body = module._request_contract(
        identifiers=["TP53", "MDM2"],
        species=9606,
        query_type=query_type,
        required_score=700,
        add_nodes=2,
        interaction_limit=25,
        network_type="physical",
    )
    assert endpoint == expected_endpoint
    assert body == {
        "identifiers": "TP53\rMDM2",
        "species": 9606,
        "caller_identity": "BioNodulo",
        **expected_extra,
    }


@pytest.mark.asyncio
async def test_string_network_uses_documented_text_parameters(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node = _node()
    module = importlib.import_module(node.__module__)
    calls: list[tuple[str, dict[str, Any]]] = []
    response = INTERACTION_TSV

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
        return INTERACTION_TSV

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
        return ENRICHMENT_TSV

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


@pytest.mark.parametrize(
    ("query_type", "response"),
    [
        ("network", INTERACTION_TSV),
        ("interactions", INTERACTION_TSV),
        ("enrichment", ENRICHMENT_TSV),
        ("mapping", MAPPING_TSV),
    ],
)
def test_string_parser_accepts_documented_query_specific_headers(query_type: str, response: str) -> None:
    node = _node()
    module = importlib.import_module(node.__module__)
    assert len(module._parse_tsv(response, query_type)) == 1


@pytest.mark.parametrize(
    ("response", "message"),
    [
        ("", "empty TSV response"),
        ("Error: identifier is not recognized\n", "invalid TSV header"),
        ("preferredName_A\tpreferredName_B\nTP53\tMDM2\n", "missing documented fields"),
        (
            INTERACTION_TSV.splitlines()[0] + "\n9606.ENSP00000269305\t9606.ENSP00000258149\n",
            "malformed TSV row",
        ),
    ],
)
def test_string_parser_rejects_empty_error_and_malformed_success_bodies(response: str, message: str) -> None:
    node = _node()
    module = importlib.import_module(node.__module__)
    with pytest.raises(RuntimeError, match=message):
        module._parse_tsv(response, "network")


@pytest.mark.asyncio
async def test_string_transport_reports_http_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    node = _node()
    module = importlib.import_module(node.__module__)

    class FakeClient:
        def __init__(self, *, cache: object | None = None, rate_limiter: object | None = None) -> None:
            pass

        async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
            request = httpx.Request(method, url)
            response = httpx.Response(503, text="temporarily unavailable", request=request)
            raise httpx.HTTPStatusError("service unavailable", request=request, response=response)

    monkeypatch.setattr(module, "APIHttpClient", FakeClient)
    with pytest.raises(RuntimeError, match="STRING tsv/network failed with HTTP 503"):
        await module._request_text("tsv/network", {"identifiers": "TP53", "species": 9606})
