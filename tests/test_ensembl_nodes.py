"""Compact Ensembl REST lookup and VEP contracts."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.nodes.registry import NodeRegistry


def _node(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node = registry.get(node_id)
    assert node is not None
    return node


def test_ensembl_nodes_have_focused_ownership_and_source_pin() -> None:
    lookup = _node("ensembl_gene_lookup")
    vep = _node("ensembl_vep")
    assert lookup.__module__ == "bionodulo.nodes.builtin.ensembl_family.gene_lookup"
    assert vep.__module__ == "bionodulo.nodes.builtin.ensembl_family.vep"
    assert lookup.GIT_COMMIT == "79f8dcc5cb3a0e8aef81273d118d7a514d43358d"
    assert vep.GIT_COMMIT == lookup.GIT_COMMIT
    assert lookup.RETURN_NAMES == ("gene_info", "transcripts")
    assert vep.RETURN_NAMES == ("vep_json", "annotation_table")
    assert "gene_symbol" in lookup.INPUT_TYPES()["optional"]
    assert "variants" in vep.INPUT_TYPES()["optional"]
    assert set(lookup.INPUT_TYPES()["required"]) == {"species"}
    assert set(vep.INPUT_TYPES()["required"]) == {"species"}
    optional = vep.INPUT_TYPES()["optional"]
    assert optional["assembly"][1]["options"] == ["current", "GRCh38", "GRCh37"]
    assert optional["variants"][1]["displayOptions"] == {
        "show": {"variant_format": ["hgvs", "ensembl"]},
    }
    assert optional["vcf_file"][1]["displayOptions"] == {
        "show": {"variant_format": ["vcf"]},
    }


@pytest.mark.asyncio
async def test_gene_lookup_routes_symbols_ids_and_grch37_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    node = _node("ensembl_gene_lookup")
    module = importlib.import_module(node.__module__)
    calls: list[tuple[str, dict[str, Any], str]] = []

    async def fake_request(resource: str, params: dict[str, Any], *, base_url: str) -> dict[str, Any]:
        calls.append((resource, params, base_url))
        return {"id": "ENSG00000141510", "display_name": "TP53", "Transcript": [{"id": "ENST1"}]}

    monkeypatch.setattr(module, "request_json", fake_request)
    result = await node().run(gene_symbol="TP53", species="homo_sapiens", expand=True)
    assert result["outputs"]["transcripts"] == [{"id": "ENST1"}]
    assert calls[0] == (
        "lookup/symbol/homo_sapiens/TP53",
        {"expand": 1},
        "https://rest.ensembl.org",
    )

    calls.clear()
    await node().run(gene_symbol="ENSG00000141510", species="homo_sapiens", assembly="GRCh37")
    assert calls[0][0] == "lookup/id/ENSG00000141510"
    assert calls[0][2] == "https://grch37.rest.ensembl.org"

    with pytest.raises(ValueError, match="only for homo_sapiens"):
        await node().run(gene_symbol="Trp53", species="mus_musculus", assembly="GRCh37")


@pytest.mark.asyncio
async def test_vep_chunks_at_source_defined_limit_and_writes_outputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node = _node("ensembl_vep")
    module = importlib.import_module(node.__module__)
    calls: list[tuple[str, list[str], dict[str, Any], str]] = []

    async def fake_post(
        resource: str,
        body: dict[str, Any],
        params: dict[str, Any],
        *,
        base_url: str,
    ) -> list[dict[str, Any]]:
        calls.append((resource, list(body["variants"]), dict(params), base_url))
        return [
            {
                "input": variant,
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
            for variant in body["variants"]
        ]

    monkeypatch.setattr(module, "post_json", fake_post)
    variants = "\n".join(f"ENST000001:c.{index}A>G" for index in range(1001))
    result = await node().run(
        variants=variants,
        species="homo_sapiens",
        variant_format="hgvs",
        context=SimpleNamespace(node_dir=tmp_path),
    )
    assert [len(call[1]) for call in calls] == [1000, 1]
    assert all(call[0] == "vep/homo_sapiens/hgvs" for call in calls)
    payload = json.loads(Path(result["outputs"]["vep_json"]).read_text(encoding="utf-8"))
    table = Path(result["outputs"]["annotation_table"]).read_text(encoding="utf-8")
    assert len(payload) == 1001
    assert "TP53\tENSG00000141510\tENST1\tmissense_variant\tMODERATE" in table


@pytest.mark.asyncio
async def test_vep_rejects_empty_or_mismatched_inputs() -> None:
    node = _node("ensembl_vep")
    with pytest.raises(ValueError, match="at least one variant"):
        await node().run(variants="", variant_format="hgvs", species="homo_sapiens")
    with pytest.raises(ValueError, match="requires a VCF file"):
        await node().run(variants="", variant_format="vcf", species="homo_sapiens")
    with pytest.raises(ValueError, match="only for homo_sapiens"):
        await node().run(
            variants="1 100 . A G . . .",
            variant_format="ensembl",
            species="mus_musculus",
            assembly="GRCh37",
        )
