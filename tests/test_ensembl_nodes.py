from __future__ import annotations

import csv
import importlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_ensembl_gene_lookup_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    assert info["ensembl_gene_lookup"]["display_name"] == "Ensembl Gene Lookup"
    assert info["ensembl_gene_lookup"]["category"] == "databases"
    assert info["ensembl_gene_lookup"]["output_name"] == ["gene_info", "transcripts"]
    assert info["ensembl_gene_lookup"]["input"]["required"]["gene_symbol"] == (
        "STRING",
        {"default": "", "description": "Gene symbol or Ensembl stable ID"},
    )
    assert info["ensembl_gene_lookup"]["input"]["optional"]["query"] == (
        "STRING",
        {
            "default": "",
            "advanced": True,
            "description": "Backward-compatible gene symbol or stable ID input",
        },
    )
    assert info["ensembl_gene_lookup"]["input"]["optional"]["fetch_homologs"] == (
        "BOOLEAN",
        {"default": False, "advanced": True},
    )
    assert info["ensembl_gene_lookup"]["input"]["optional"]["homolog_species"] == (
        "STRING",
        {"default": "", "advanced": True, "description": "Optional target species for homology lookup"},
    )
    assert info["ensembl_vep"]["display_name"] == "Ensembl VEP"
    assert info["ensembl_vep"]["category"] == "databases"
    assert info["ensembl_vep"]["output_name"] == ["vep_json", "annotation_table"]
    assert info["ensembl_vep"]["input"]["required"]["variants"] == (
        "STRING",
        {"default": "", "multiline": True, "description": "HGVS variants, one per line"},
    )
    assert info["ensembl_vep"]["input"]["optional"]["variant_format"] == (
        "STRING",
        {"default": "hgvs", "options": ["hgvs", "vcf", "ensembl"]},
    )
    assert info["ensembl_vep"]["input"]["optional"]["vcf_file"] == (
        "VCF",
        {"default": "", "advanced": True, "description": "Backward-compatible VCF file containing variants to annotate"},
    )
    assert info["ensembl_vep"]["input"]["optional"]["sift"][0] == "BOOLEAN"
    assert info["ensembl_vep"]["input"]["optional"]["polyphen"][0] == "BOOLEAN"
    assert info["ensembl_vep"]["input"]["optional"]["maf"][0] == "BOOLEAN"


@pytest.mark.asyncio
async def test_ensembl_requests_use_shared_http_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    node_class = _node_class("ensembl_gene_lookup")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    class FakeClient:
        def __init__(self, *, cache: object | None = None, rate_limiter: object | None = None) -> None:
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
            request = httpx.Request(method, url, params=kwargs.get("params"), headers=kwargs.get("headers"))
            return httpx.Response(200, json={"ok": True}, request=request)

    monkeypatch.setattr(module, "APIHttpClient", FakeClient)

    get_response = await module._request(
        "lookup/id/ENSG00000141510",
        {"expand": 1},
        base_url=module.ENSEMBL_BASE_URL,
        retries=4,
        timeout=8.0,
    )
    post_response = await module._post(
        "vep/homo_sapiens/region",
        {"variants": ["13 32316461 . A G . . ."]},
        {"canonical": 1},
        base_url=module.ENSEMBL_GRCH37_BASE_URL,
        retries=2,
        timeout=9.0,
    )

    assert get_response.json() == {"ok": True}
    assert post_response.json() == {"ok": True}
    assert len(calls) == 2
    assert calls[0]["method"] == "GET"
    assert calls[0]["url"] == f"{module.ENSEMBL_BASE_URL}/lookup/id/ENSG00000141510"
    assert calls[0]["params"] == {"expand": 1}
    assert calls[0]["headers"] == module.ENSEMBL_JSON_HEADERS
    assert calls[0]["timeout"] == 8.0
    assert calls[0]["retries"] == 4
    assert calls[0]["retry_delay"] == module.RETRY_DELAY_S
    assert calls[0]["cache_ttl"] == module.ENSEMBL_CACHE_TTL_S
    assert calls[0]["cache"] is module.ENSEMBL_API_CACHE
    assert calls[0]["rate_limiter"] is module.ENSEMBL_RATE_LIMITER

    assert calls[1]["method"] == "POST"
    assert calls[1]["url"] == f"{module.ENSEMBL_GRCH37_BASE_URL}/vep/homo_sapiens/region"
    assert calls[1]["params"] == {"canonical": 1}
    assert calls[1]["json"] == {"variants": ["13 32316461 . A G . . ."]}
    assert calls[1]["headers"] == module.ENSEMBL_JSON_HEADERS
    assert calls[1]["timeout"] == 9.0
    assert calls[1]["retries"] == 2
    assert calls[1]["retry_delay"] == module.RETRY_DELAY_S
    assert calls[1]["cache_ttl"] is None
    assert calls[1]["cache"] is module.ENSEMBL_API_CACHE
    assert calls[1]["rate_limiter"] is module.ENSEMBL_RATE_LIMITER


@pytest.mark.asyncio
async def test_ensembl_gene_lookup_uses_symbol_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    node_class = _node_class("ensembl_gene_lookup")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    async def fake_json(resource: str, params: dict[str, Any] | None = None, base_url: str | None = None, **_: Any) -> dict[str, Any]:
        calls.append({"resource": resource, "params": dict(params or {}), "base_url": base_url})
        return {
            "id": "ENSG00000139618",
            "display_name": "BRCA2",
            "description": "BRCA2 DNA repair associated",
            "species": "homo_sapiens",
            "assembly_name": "GRCh38",
            "object_type": "Gene",
            "biotype": "protein_coding",
            "seq_region_name": "13",
            "start": 32315474,
            "end": 32400266,
            "strand": 1,
            "Transcript": [
                {"id": "ENST00000380152", "biotype": "protein_coding"},
                {"id": "ENST00000544455", "biotype": "retained_intron"},
            ],
        }

    monkeypatch.setattr(module, "_request_json", fake_json)

    result = await node_class().run(query="BRCA2", species="homo_sapiens", expand=True, assembly="current")

    assert result["outputs"]["gene_info"]["summary"] == {
        "id": "ENSG00000139618",
        "display_name": "BRCA2",
        "description": "BRCA2 DNA repair associated",
        "species": "homo_sapiens",
        "assembly_name": "GRCh38",
        "object_type": "Gene",
        "biotype": "protein_coding",
        "location": "13:32315474-32400266:1",
    }
    assert [tx["id"] for tx in result["outputs"]["transcripts"]] == [
        "ENST00000380152",
        "ENST00000544455",
    ]
    assert calls == [
        {
            "resource": "lookup/symbol/homo_sapiens/BRCA2",
            "params": {"expand": 1},
            "base_url": "https://rest.ensembl.org",
        }
    ]


@pytest.mark.asyncio
async def test_ensembl_gene_lookup_accepts_plan_gene_symbol_input(monkeypatch: pytest.MonkeyPatch) -> None:
    node_class = _node_class("ensembl_gene_lookup")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    async def fake_json(resource: str, params: dict[str, Any] | None = None, base_url: str | None = None, **_: Any) -> dict[str, Any]:
        calls.append({"resource": resource, "params": dict(params or {}), "base_url": base_url})
        return {
            "id": "ENSG00000139618",
            "display_name": "BRCA2",
            "species": "homo_sapiens",
            "object_type": "Gene",
        }

    monkeypatch.setattr(module, "_request_json", fake_json)

    result = await node_class().run(gene_symbol="BRCA2", species="homo_sapiens", expand=True, assembly="current")

    assert result["outputs"]["gene_info"]["id"] == "ENSG00000139618"
    assert calls == [
        {
            "resource": "lookup/symbol/homo_sapiens/BRCA2",
            "params": {"expand": 1},
            "base_url": "https://rest.ensembl.org",
        }
    ]


@pytest.mark.asyncio
async def test_ensembl_gene_lookup_uses_stable_id_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    node_class = _node_class("ensembl_gene_lookup")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    async def fake_json(resource: str, params: dict[str, Any] | None = None, base_url: str | None = None, **_: Any) -> dict[str, Any]:
        calls.append({"resource": resource, "params": dict(params or {}), "base_url": base_url})
        return {
            "id": "ENSG00000141510",
            "display_name": "TP53",
            "species": "homo_sapiens",
            "object_type": "Gene",
        }

    monkeypatch.setattr(module, "_request_json", fake_json)

    result = await node_class().run(
        query="ENSG00000141510",
        species="homo_sapiens",
        expand=False,
        assembly="GRCh37",
    )

    assert result["outputs"]["gene_info"]["id"] == "ENSG00000141510"
    assert result["outputs"]["transcripts"] == []
    assert calls == [
        {
            "resource": "lookup/id/ENSG00000141510",
            "params": {"expand": 0},
            "base_url": "https://grch37.rest.ensembl.org",
        }
    ]


@pytest.mark.asyncio
async def test_ensembl_gene_lookup_fetches_homologs_when_requested(monkeypatch: pytest.MonkeyPatch) -> None:
    node_class = _node_class("ensembl_gene_lookup")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    async def fake_json(resource: str, params: dict[str, Any] | None = None, base_url: str | None = None, **_: Any) -> dict[str, Any]:
        calls.append({"resource": resource, "params": dict(params or {}), "base_url": base_url})
        if resource == "lookup/symbol/homo_sapiens/TP53":
            return {
                "id": "ENSG00000141510",
                "display_name": "TP53",
                "species": "homo_sapiens",
                "object_type": "Gene",
                "Transcript": [{"id": "ENST00000269305"}],
            }
        if resource == "homology/id/ENSG00000141510":
            return {
                "data": [
                    {
                        "id": "ENSG00000141510",
                        "homologies": [
                            {
                                "type": "ortholog_one2one",
                                "target": {"species": "mus_musculus", "id": "ENSMUSG00000059552"},
                            }
                        ],
                    }
                ]
            }
        raise AssertionError(f"unexpected resource: {resource}")

    monkeypatch.setattr(module, "_request_json", fake_json)

    result = await node_class().run(
        query="TP53",
        species="homo_sapiens",
        expand=True,
        assembly="current",
        fetch_homologs=True,
        homolog_species="mus_musculus",
    )

    assert result["outputs"]["gene_info"]["homologs"]["data"][0]["homologies"][0]["target"]["id"] == (
        "ENSMUSG00000059552"
    )
    assert result["outputs"]["transcripts"] == [{"id": "ENST00000269305"}]
    assert calls == [
        {
            "resource": "lookup/symbol/homo_sapiens/TP53",
            "params": {"expand": 1},
            "base_url": "https://rest.ensembl.org",
        },
        {
            "resource": "homology/id/ENSG00000141510",
            "params": {"type": "orthologues", "target_species": "mus_musculus"},
            "base_url": "https://rest.ensembl.org",
        },
    ]


@pytest.mark.asyncio
async def test_ensembl_vep_posts_vcf_variants_and_writes_outputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("ensembl_vep")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []
    vcf = tmp_path / "variants.vcf"
    vcf.write_text(
        "\n".join([
            "##fileformat=VCFv4.2",
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO",
            "13\t32316461\t.\tA\tG\t.\t.\t.",
        ]) + "\n",
        encoding="utf-8",
    )
    payload = [
        {
            "input": "13 32316461 . A G . . .",
            "transcript_consequences": [
                {
                    "gene_symbol": "BRCA2",
                    "gene_id": "ENSG00000139618",
                    "transcript_id": "ENST00000380152",
                    "consequence_terms": ["missense_variant"],
                    "impact": "MODERATE",
                }
            ],
        }
    ]

    async def fake_post_json(
        resource: str,
        json_body: dict[str, Any],
        params: dict[str, Any] | None = None,
        base_url: str | None = None,
        **_: Any,
    ) -> list[dict[str, Any]]:
        calls.append({
            "resource": resource,
            "json_body": dict(json_body),
            "params": dict(params or {}),
            "base_url": base_url,
        })
        return payload

    monkeypatch.setattr(module, "_post_json", fake_post_json)
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(
        vcf_file=str(vcf),
        species="homo_sapiens",
        assembly="GRCh38",
        canonical=True,
        domains=False,
        gene_phenotype=True,
        variant_class=True,
        sift=True,
        polyphen=False,
        maf=True,
        context=context,
    )

    json_path = Path(result["outputs"]["vep_json"])
    table_path = Path(result["outputs"]["annotation_table"])
    with table_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))

    assert json_path.read_text(encoding="utf-8").startswith("[\n  {")
    assert rows == [
        {
            "input": "13 32316461 . A G . . .",
            "gene_symbol": "BRCA2",
            "gene_id": "ENSG00000139618",
            "transcript_id": "ENST00000380152",
            "consequence_terms": "missense_variant",
            "impact": "MODERATE",
        }
    ]
    assert calls == [
        {
            "resource": "vep/homo_sapiens/region",
            "json_body": {"variants": ["13 32316461 . A G . . ."]},
            "params": {
                "canonical": 1,
                "domains": 0,
                "gene_phenotype": 1,
                "variant_class": 1,
                "SiftPrediction": "yes",
                "PolyPhen": "no",
                "MAF": "yes",
            },
            "base_url": "https://rest.ensembl.org",
        }
    ]


@pytest.mark.asyncio
async def test_ensembl_vep_accepts_hgvs_variants_input(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("ensembl_vep")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []
    payload = [
        {
            "input": "9:g.22125503G>C",
            "transcript_consequences": [
                {
                    "gene_symbol": "CDKN2A",
                    "gene_id": "ENSG00000147889",
                    "transcript_id": "ENST00000304494",
                    "consequence_terms": ["missense_variant"],
                    "impact": "MODERATE",
                }
            ],
        }
    ]

    async def fake_post_json(
        resource: str,
        json_body: dict[str, Any],
        params: dict[str, Any] | None = None,
        base_url: str | None = None,
        **_: Any,
    ) -> list[dict[str, Any]]:
        calls.append({
            "resource": resource,
            "json_body": dict(json_body),
            "params": dict(params or {}),
            "base_url": base_url,
        })
        return payload

    monkeypatch.setattr(module, "_post_json", fake_post_json)

    result = await node_class().run(
        variants="9:g.22125503G>C",
        variant_format="hgvs",
        species="homo_sapiens",
        assembly="current",
        canonical=True,
        domains=True,
        gene_phenotype=False,
        variant_class=False,
        sift=False,
        polyphen=True,
        maf=False,
        context=SimpleNamespace(node_dir=tmp_path),
    )

    table_path = Path(result["outputs"]["annotation_table"])
    with table_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))

    assert rows == [
        {
            "input": "9:g.22125503G>C",
            "gene_symbol": "CDKN2A",
            "gene_id": "ENSG00000147889",
            "transcript_id": "ENST00000304494",
            "consequence_terms": "missense_variant",
            "impact": "MODERATE",
        }
    ]
    assert calls == [
        {
            "resource": "vep/homo_sapiens/hgvs",
            "json_body": {"variants": ["9:g.22125503G>C"]},
            "params": {
                "canonical": 1,
                "domains": 1,
                "gene_phenotype": 0,
                "variant_class": 0,
                "SiftPrediction": "no",
                "PolyPhen": "yes",
                "MAF": "no",
            },
            "base_url": "https://rest.ensembl.org",
        }
    ]


@pytest.mark.asyncio
async def test_ensembl_vep_accepts_inline_ensembl_region_variants(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("ensembl_vep")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []
    payload = [
        {
            "input": "13 32316461 . A G . . .",
            "transcript_consequences": [
                {
                    "gene_symbol": "BRCA2",
                    "gene_id": "ENSG00000139618",
                    "transcript_id": "ENST00000380152",
                    "consequence_terms": ["missense_variant"],
                    "impact": "MODERATE",
                }
            ],
        }
    ]

    async def fake_post_json(
        resource: str,
        json_body: dict[str, Any],
        params: dict[str, Any] | None = None,
        base_url: str | None = None,
        **_: Any,
    ) -> list[dict[str, Any]]:
        calls.append({
            "resource": resource,
            "json_body": dict(json_body),
            "params": dict(params or {}),
            "base_url": base_url,
        })
        return payload

    monkeypatch.setattr(module, "_post_json", fake_post_json)

    result = await node_class().run(
        variants="13 32316461 . A G . . .",
        variant_format="ensembl",
        species="homo_sapiens",
        assembly="current",
        canonical=False,
        domains=False,
        gene_phenotype=False,
        variant_class=True,
        sift=True,
        polyphen=True,
        maf=False,
        context=SimpleNamespace(node_dir=tmp_path),
    )

    table_path = Path(result["outputs"]["annotation_table"])
    with table_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))

    assert rows == [
        {
            "input": "13 32316461 . A G . . .",
            "gene_symbol": "BRCA2",
            "gene_id": "ENSG00000139618",
            "transcript_id": "ENST00000380152",
            "consequence_terms": "missense_variant",
            "impact": "MODERATE",
        }
    ]
    assert calls == [
        {
            "resource": "vep/homo_sapiens/region",
            "json_body": {"variants": ["13 32316461 . A G . . ."]},
            "params": {
                "canonical": 0,
                "domains": 0,
                "gene_phenotype": 0,
                "variant_class": 1,
                "SiftPrediction": "yes",
                "PolyPhen": "yes",
                "MAF": "no",
            },
            "base_url": "https://rest.ensembl.org",
        }
    ]
