from __future__ import annotations

import csv
import importlib
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


def test_ensembl_gene_lookup_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    assert info["ensembl_gene_lookup"]["display_name"] == "Ensembl Gene Lookup"
    assert info["ensembl_gene_lookup"]["category"] == "databases"
    assert info["ensembl_gene_lookup"]["output_name"] == ["gene_info", "transcripts"]
    assert info["ensembl_vep"]["display_name"] == "Ensembl VEP"
    assert info["ensembl_vep"]["category"] == "databases"
    assert info["ensembl_vep"]["output_name"] == ["vep_json", "annotation_table"]


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
            },
            "base_url": "https://rest.ensembl.org",
        }
    ]
