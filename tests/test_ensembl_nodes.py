"""Source-pinned Ensembl REST lookup and VEP contracts."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from bionodulo.nodes.registry import NodeRegistry


def _node(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node = registry.get(node_id)
    assert node is not None
    return node


def test_ensembl_nodes_have_pinned_focused_contracts() -> None:
    lookup = _node("ensembl_gene_lookup")
    vep = _node("ensembl_vep")
    adapter = importlib.import_module("bionodulo.nodes.builtin.ensembl_family.adapter")

    assert lookup.__module__ == "bionodulo.nodes.builtin.ensembl_family.gene_lookup"
    assert vep.__module__ == "bionodulo.nodes.builtin.ensembl_family.vep"
    assert lookup.GIT_COMMIT == "79f8dcc5cb3a0e8aef81273d118d7a514d43358d"
    assert lookup.UPSTREAM_SOURCE_REVISION == "2026-04-07T09:29:16+01:00"
    assert lookup.SOURCE_REVISION == vep.SOURCE_REVISION == "2026-07"
    assert lookup.SOURCE_SHA256 == "7ac58aff9772fea75ef3178767648d3bff889a7e5a58e5a86c842776e4d9ee00"
    assert lookup.ID_LOOKUP_SOURCE_SHA256 == (
        "81b1cf120ebcc6cc007885afc7b2a59869d2b7656e0d0906582b0e7c18e325c4"
    )
    assert lookup.HOMOLOGY_SOURCE_SHA256 == (
        "3a0cdb7cbeb7b6a843b4687f6fb023bb06359171730b9c3f139ad32a9c784f37"
    )
    assert lookup.GRCH37_HOMOLOGY_SOURCE_SHA256 == (
        "5fa524b1922b961cdde3f87673d7c8bffb95a31350e94d78f7a2a30ef2ac418e"
    )
    assert vep.SOURCE_SHA256 == "6c26cc4d1baa6eda1d8773884d8f762660cdf941ef84de92e7ad173ee6497464"
    assert vep.HGVS_SOURCE_SHA256 == "dc03a41b4a2575569f3b6bf7fa7f8cf25f046e449dd25a31948ed1029a288646"
    assert adapter.ENSEMBL_RATE_LIMITER.rate_per_second == 15.0
    assert adapter.MAX_RETRIES == 3
    assert adapter.REQUEST_TIMEOUT_SECONDS == 30.0
    assert adapter.is_stable_id("ENSG00000141510.5")
    assert not adapter.is_stable_id("ENSG00000141510-extra")

    lookup_optional = lookup.INPUT_TYPES()["optional"]
    assert lookup.RETURN_NAMES == ("gene_info", "transcripts")
    assert lookup_optional["expand"][1]["default"] is False
    assert set(lookup.INPUT_TYPES()["required"]) == {"species"}

    vep_optional = vep.INPUT_TYPES()["optional"]
    assert vep.RETURN_NAMES == ("vep_json", "annotation_table")
    assert set(vep_optional) == {
        "variants",
        "variant_format",
        "vcf_file",
        "assembly",
        "canonical",
        "domains",
        "variant_class",
    }
    assert vep_optional["variant_format"][1]["options"] == ["hgvs", "vcf"]
    assert vep_optional["variants"][1]["displayOptions"] == {"show": {"variant_format": ["hgvs"]}}
    assert all(vep_optional[name][1]["default"] is False for name in ("canonical", "domains", "variant_class"))


@pytest.mark.asyncio
async def test_adapter_uses_documented_transport_policy_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("bionodulo.nodes.builtin.ensembl_family.adapter")
    calls: list[dict[str, Any]] = []

    class FakeClient:
        def __init__(self, *, cache: Any, rate_limiter: Any) -> None:
            self.cache = cache
            self.rate_limiter = rate_limiter

        async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
            calls.append(
                {
                    "method": method,
                    "url": url,
                    "cache": self.cache,
                    "rate_limiter": self.rate_limiter,
                    **kwargs,
                }
            )
            payload: Any = {"id": "ENSG1"} if method == "GET" else [{"input": "x"}]
            return httpx.Response(200, json=payload, request=httpx.Request(method, url))

    monkeypatch.setattr(module, "APIHttpClient", FakeClient)
    assert await module.request_json("lookup/id/ENSG1", {"species": "homo_sapiens"}) == {"id": "ENSG1"}
    assert await module.post_json("vep/homo_sapiens/hgvs", {"hgvs_notations": ["x"]}) == [{"input": "x"}]

    get_call, post_call = calls
    assert get_call["method"] == "GET"
    assert get_call["url"] == "https://rest.ensembl.org/lookup/id/ENSG1"
    assert get_call["params"] == {"species": "homo_sapiens"}
    assert get_call["headers"] == module.ENSEMBL_JSON_HEADERS
    assert get_call["timeout"] == 30.0
    assert get_call["retries"] == 3
    assert get_call["retry_delay"] == 1.0
    assert get_call["cache_ttl"] == 300.0
    assert get_call["rate_limiter"] is module.ENSEMBL_RATE_LIMITER
    assert post_call["method"] == "POST"
    assert post_call["json"] == {"hgvs_notations": ["x"]}
    assert post_call["cache_ttl"] is None


@pytest.mark.asyncio
async def test_adapter_rejects_invalid_and_error_json(monkeypatch: pytest.MonkeyPatch) -> None:
    module = importlib.import_module("bionodulo.nodes.builtin.ensembl_family.adapter")
    response = httpx.Response(200, json=[], request=httpx.Request("GET", "https://rest.ensembl.org/x"))

    async def fake_request(*args: Any, **kwargs: Any) -> httpx.Response:
        return response

    monkeypatch.setattr(module, "request", fake_request)
    with pytest.raises(RuntimeError, match="non-object JSON response"):
        await module.request_json("lookup/id/ENSG1")

    response = httpx.Response(
        200,
        json={"error": "unknown identifier"},
        request=httpx.Request("GET", "https://rest.ensembl.org/x"),
    )
    with pytest.raises(RuntimeError, match="unknown identifier"):
        await module.request_json("lookup/id/ENSG1")

    response = httpx.Response(200, text="{", request=httpx.Request("GET", "https://rest.ensembl.org/x"))
    with pytest.raises(RuntimeError, match="returned invalid JSON"):
        await module.request_json("lookup/id/ENSG1")


@pytest.mark.asyncio
async def test_adapter_bounds_http_errors_without_credential_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("bionodulo.nodes.builtin.ensembl_family.adapter")
    body = "x" * 600

    class FailingClient:
        def __init__(self, *, cache: Any, rate_limiter: Any) -> None:
            pass

        async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
            request = httpx.Request(method, url)
            response = httpx.Response(400, text=body, request=request)
            raise httpx.HTTPStatusError("bad response", request=request, response=response)

    monkeypatch.setattr(module, "APIHttpClient", FailingClient)
    with pytest.raises(RuntimeError) as exc_info:
        await module.request("GET", "lookup/id/ENSG1")
    message = str(exc_info.value)
    assert message == f"Ensembl lookup/id/ENSG1 failed with HTTP 400: {'x' * 500}"

    for node_id in ("ensembl_gene_lookup", "ensembl_vep"):
        inputs = _node(node_id).INPUT_TYPES()
        assert not {"api_key", "token", "password"}.intersection(inputs["optional"] | inputs["hidden"])


@pytest.mark.asyncio
async def test_gene_lookup_routes_symbols_ids_and_homology(monkeypatch: pytest.MonkeyPatch) -> None:
    node = _node("ensembl_gene_lookup")
    module = importlib.import_module(node.__module__)
    calls: list[tuple[str, dict[str, Any], str]] = []

    async def fake_request(resource: str, params: dict[str, Any], *, base_url: str) -> dict[str, Any]:
        calls.append((resource, params, base_url))
        if resource.startswith("homology/"):
            return {"data": []}
        return {
            "id": "ENSG00000141510",
            "display_name": "TP53",
            "object_type": "Gene",
            "Transcript": [{"id": "ENST1"}],
        }

    monkeypatch.setattr(module, "request_json", fake_request)
    result = await node().run(
        gene_symbol="TP53",
        species="homo_sapiens",
        expand=True,
        fetch_homologs=True,
        homolog_species="mus_musculus,rattus_norvegicus",
    )
    assert result["outputs"]["transcripts"] == [{"id": "ENST1"}]
    assert calls == [
        ("lookup/symbol/homo_sapiens/TP53", {"expand": 1}, "https://rest.ensembl.org"),
        (
            "homology/id/homo_sapiens/ENSG00000141510",
            {"type": "orthologues", "target_species": "mus_musculus"},
            "https://rest.ensembl.org",
        ),
        (
            "homology/id/homo_sapiens/ENSG00000141510",
            {"type": "orthologues", "target_species": "rattus_norvegicus"},
            "https://rest.ensembl.org",
        ),
    ]

    calls.clear()
    await node().run(gene_symbol="ENSG00000141510", species="homo_sapiens", assembly="GRCh37")
    assert calls == [
        (
            "lookup/id/ENSG00000141510",
            {"expand": 0, "species": "homo_sapiens"},
            "https://grch37.rest.ensembl.org",
        )
    ]


@pytest.mark.asyncio
async def test_gene_lookup_fails_closed_for_invalid_assembly_and_homology(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    node = _node("ensembl_gene_lookup")
    module = importlib.import_module(node.__module__)

    async def fake_request(resource: str, params: dict[str, Any], *, base_url: str) -> dict[str, Any]:
        return {"id": "ENST1", "object_type": "Transcript"}

    monkeypatch.setattr(module, "request_json", fake_request)
    with pytest.raises(ValueError, match="supported only for homo_sapiens"):
        await node().run(gene_symbol="Trp53", species="mus_musculus", assembly="GRCh37")
    with pytest.raises(ValueError, match="Unsupported Ensembl assembly"):
        await node().run(gene_symbol="TP53", species="homo_sapiens", assembly="GRCh36")
    with pytest.raises(ValueError, match="requires a resolved gene stable ID"):
        await node().run(
            gene_symbol="ENST1",
            species="homo_sapiens",
            fetch_homologs=True,
        )
    with pytest.raises(ValueError, match="does not support orthologue lookup"):
        await node().run(
            gene_symbol="ENST1",
            species="homo_sapiens",
            assembly="GRCh37",
            fetch_homologs=True,
        )


@pytest.mark.asyncio
async def test_vep_chunks_hgvs_at_documented_limit_and_writes_deterministic_outputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node = _node("ensembl_vep")
    module = importlib.import_module(node.__module__)
    calls: list[tuple[str, dict[str, Any], dict[str, Any], str]] = []

    async def fake_post(
        resource: str,
        body: dict[str, Any],
        params: dict[str, Any],
        *,
        base_url: str,
    ) -> list[dict[str, Any]]:
        calls.append((resource, body, params, base_url))
        return [
            {
                "z_field": "last",
                "input": variant,
                "a_field": "first",
                "transcript_consequences": [
                    {
                        "gene_symbol": "TP53",
                        "gene_id": "ENSG00000141510",
                        "transcript_id": "ENST1",
                        "consequence_terms": ["missense_variant"],
                        "impact": "MODERATE",
                    }
                ],
            }
            for variant in body["hgvs_notations"]
        ]

    monkeypatch.setattr(module, "post_json", fake_post)
    variants = "\n".join(f"ENST000001:c.{index}A>G" for index in range(201))
    result = await node().run(
        variants=variants,
        species="homo_sapiens",
        variant_format="hgvs",
        context=SimpleNamespace(node_dir=tmp_path),
    )
    assert [len(call[1]["hgvs_notations"]) for call in calls] == [200, 1]
    assert all(call[0] == "vep/homo_sapiens/hgvs" for call in calls)
    assert all(call[2] == {"canonical": 0, "domains": 0, "variant_class": 0} for call in calls)
    json_text = Path(result["outputs"]["vep_json"]).read_text(encoding="utf-8")
    table = Path(result["outputs"]["annotation_table"]).read_text(encoding="utf-8")
    assert len(json.loads(json_text)) == 201
    assert json_text.index('"a_field"') < json_text.index('"z_field"')
    assert json_text.endswith("\n")
    assert "TP53\tENSG00000141510\tENST1\tmissense_variant\tMODERATE" in table


@pytest.mark.asyncio
async def test_vep_region_post_uses_documented_vcf_body(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node = _node("ensembl_vep")
    module = importlib.import_module(node.__module__)
    vcf = tmp_path / "variants.vcf"
    vcf.write_text(
        "##fileformat=VCFv4.2\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE\n"
        "21\t26960070\trs116645811\tG\tA\t.\t.\t.\tGT\t0/1\n",
        encoding="utf-8",
    )
    calls: list[tuple[str, dict[str, Any], dict[str, Any], str]] = []

    async def fake_post(
        resource: str,
        body: dict[str, Any],
        params: dict[str, Any],
        *,
        base_url: str,
    ) -> list[dict[str, Any]]:
        calls.append((resource, body, params, base_url))
        return [{"input": body["variants"][0]}]

    monkeypatch.setattr(module, "post_json", fake_post)
    await node().run(
        species="homo_sapiens",
        variant_format="vcf",
        vcf_file=str(vcf),
        canonical=True,
        domains=True,
        variant_class=True,
        context=SimpleNamespace(node_dir=tmp_path),
    )
    assert calls == [
        (
            "vep/homo_sapiens/region",
            {"variants": ["21 26960070 rs116645811 G A . . ."]},
            {"canonical": 1, "domains": 1, "variant_class": 1},
            "https://rest.ensembl.org",
        )
    ]


@pytest.mark.asyncio
async def test_vep_rejects_invalid_inputs_and_responses(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node = _node("ensembl_vep")
    module = importlib.import_module(node.__module__)
    short_vcf = tmp_path / "short.vcf"
    short_vcf.write_text("1\t100\t.\tA\tG\n", encoding="utf-8")

    with pytest.raises(ValueError, match="at least one variant"):
        await node().run(variants="", variant_format="hgvs", species="homo_sapiens")
    with pytest.raises(ValueError, match="requires a VCF file"):
        await node().run(variant_format="vcf", species="homo_sapiens")
    with pytest.raises(ValueError, match="at least 8 columns"):
        await node().run(variant_format="vcf", vcf_file=str(short_vcf), species="homo_sapiens")
    with pytest.raises(ValueError, match="Unsupported Ensembl VEP variant_format"):
        await node().run(variants="1 100 100 A/G 1", variant_format="ensembl", species="homo_sapiens")
    with pytest.raises(ValueError, match="supported only for homo_sapiens"):
        await node().run(
            variants="ENST1:c.1A>G",
            variant_format="hgvs",
            species="mus_musculus",
            assembly="GRCh38",
        )

    async def empty_post(*args: Any, **kwargs: Any) -> list[Any]:
        return []

    monkeypatch.setattr(module, "post_json", empty_post)
    with pytest.raises(RuntimeError, match="empty response"):
        await node().run(variants="ENST1:c.1A>G", variant_format="hgvs", species="homo_sapiens")

    async def malformed_post(*args: Any, **kwargs: Any) -> list[Any]:
        return [{"input": "x", "transcript_consequences": "invalid"}]

    monkeypatch.setattr(module, "post_json", malformed_post)
    with pytest.raises(RuntimeError, match="invalid transcript consequences"):
        await node().run(
            variants="ENST1:c.1A>G",
            variant_format="hgvs",
            species="homo_sapiens",
            context=SimpleNamespace(node_dir=tmp_path),
        )
