from __future__ import annotations

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


def test_uniprot_retrieve_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    assert info["uniprot_retrieve"]["display_name"] == "UniProt Retrieve"
    assert info["uniprot_retrieve"]["category"] == "databases"
    assert info["uniprot_retrieve"]["output_name"] == ["protein_data", "sequence"]


def test_uniprot_search_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    assert info["uniprot_search"]["display_name"] == "UniProt Search"
    assert info["uniprot_search"]["category"] == "databases"
    assert info["uniprot_search"]["output_name"] == ["results_table", "results_data"]


@pytest.mark.asyncio
async def test_uniprot_retrieve_fetches_json_and_writes_fasta(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("uniprot_retrieve")
    module = importlib.import_module(node_class.__module__)
    calls: list[tuple[str, str]] = []

    async def fake_json(resource: str, **_: Any) -> dict[str, Any]:
        calls.append(("json", resource))
        return {
            "primaryAccession": "P04637",
            "uniProtkbId": "P53_HUMAN",
            "proteinDescription": {
                "recommendedName": {"fullName": {"value": "Cellular tumor antigen p53"}},
            },
            "organism": {"scientificName": "Homo sapiens"},
            "genes": [{"geneName": {"value": "TP53"}}],
            "sequence": {"length": 393, "value": "MEEPQSDPSV"},
        }

    async def fake_text(resource: str, **_: Any) -> str:
        calls.append(("text", resource))
        return ">sp|P04637|P53_HUMAN Cellular tumor antigen p53\nMEEPQSDPSV\n"

    monkeypatch.setattr(module, "_request_json", fake_json)
    monkeypatch.setattr(module, "_request_text", fake_text)
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(
        accession="P04637",
        output_name="tp53",
        include_fasta=True,
        context=context,
    )

    protein_data = result["outputs"]["protein_data"]
    sequence_path = Path(result["outputs"]["sequence"])
    assert protein_data["primaryAccession"] == "P04637"
    assert protein_data["summary"] == {
        "accession": "P04637",
        "entry_name": "P53_HUMAN",
        "protein_name": "Cellular tumor antigen p53",
        "organism": "Homo sapiens",
        "gene_names": ["TP53"],
        "sequence_length": 393,
    }
    assert sequence_path.name == "tp53.fasta"
    assert sequence_path.read_text(encoding="utf-8") == ">sp|P04637|P53_HUMAN Cellular tumor antigen p53\nMEEPQSDPSV\n"
    assert calls == [
        ("json", "uniprotkb/P04637.json"),
        ("text", "uniprotkb/P04637.fasta"),
    ]


@pytest.mark.asyncio
async def test_uniprot_retrieve_supports_comma_separated_accessions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("uniprot_retrieve")
    module = importlib.import_module(node_class.__module__)
    json_calls: list[str] = []
    fasta_calls: list[str] = []

    async def fake_json(resource: str, **_: Any) -> dict[str, Any]:
        accession = resource.split("/")[1].split(".")[0]
        json_calls.append(resource)
        return {"primaryAccession": accession, "uniProtkbId": f"{accession}_ENTRY"}

    async def fake_text(resource: str, **_: Any) -> str:
        accession = resource.split("/")[1].split(".")[0]
        fasta_calls.append(resource)
        return f">sp|{accession}|{accession}_ENTRY\nMSEQ\n"

    monkeypatch.setattr(module, "_request_json", fake_json)
    monkeypatch.setattr(module, "_request_text", fake_text)
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(
        accession="P04637, Q9Y6K9",
        include_fasta=True,
        context=context,
    )

    assert [entry["primaryAccession"] for entry in result["outputs"]["protein_data"]["entries"]] == [
        "P04637",
        "Q9Y6K9",
    ]
    assert Path(result["outputs"]["sequence"]).read_text(encoding="utf-8") == (
        ">sp|P04637|P04637_ENTRY\nMSEQ\n"
        ">sp|Q9Y6K9|Q9Y6K9_ENTRY\nMSEQ\n"
    )
    assert json_calls == ["uniprotkb/P04637.json", "uniprotkb/Q9Y6K9.json"]
    assert fasta_calls == ["uniprotkb/P04637.fasta", "uniprotkb/Q9Y6K9.fasta"]


@pytest.mark.asyncio
async def test_uniprot_search_writes_summary_tsv_and_returns_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("uniprot_search")
    module = importlib.import_module(node_class.__module__)
    calls: list[tuple[str, dict[str, Any] | None]] = []

    async def fake_json(resource: str, *, params: dict[str, Any] | None = None, **_: Any) -> dict[str, Any]:
        calls.append((resource, params))
        return {
            "results": [
                {
                    "primaryAccession": "P04637",
                    "uniProtkbId": "P53_HUMAN",
                    "proteinDescription": {
                        "recommendedName": {"fullName": {"value": "Cellular tumor antigen p53"}},
                    },
                    "organism": {"scientificName": "Homo sapiens"},
                    "genes": [{"geneName": {"value": "TP53"}}],
                    "sequence": {"length": 393},
                },
                {
                    "primaryAccession": "Q9Y6K9",
                    "uniProtkbId": "NEMO_HUMAN",
                    "proteinDescription": {
                        "recommendedName": {"fullName": {"value": "NF-kappa-B essential modulator"}},
                    },
                    "organism": {"scientificName": "Homo sapiens"},
                    "genes": [{"geneName": {"value": "IKBKG"}, "synonyms": [{"value": "NEMO"}]}],
                    "sequence": {"length": 419},
                },
            ]
        }

    monkeypatch.setattr(module, "_request_json", fake_json)
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(
        query="gene:TP53 OR gene:IKBKG",
        max_results=2,
        reviewed_only=True,
        output_name="nfkb_tp53",
        context=context,
    )

    table_path = Path(result["outputs"]["results_table"])
    results_data = result["outputs"]["results_data"]
    assert table_path.name == "nfkb_tp53.tsv"
    assert table_path.read_text(encoding="utf-8") == (
        "accession\tentry_name\tprotein_name\torganism\tgene_names\tsequence_length\n"
        "P04637\tP53_HUMAN\tCellular tumor antigen p53\tHomo sapiens\tTP53\t393\n"
        "Q9Y6K9\tNEMO_HUMAN\tNF-kappa-B essential modulator\tHomo sapiens\tIKBKG;NEMO\t419\n"
    )
    assert results_data["query"] == "gene:TP53 OR gene:IKBKG"
    assert results_data["record_count"] == 2
    assert [entry["summary"]["accession"] for entry in results_data["entries"]] == ["P04637", "Q9Y6K9"]
    assert calls == [
        (
            "uniprotkb/search",
            {
                "query": "(gene:TP53 OR gene:IKBKG) AND reviewed:true",
                "format": "json",
                "fields": "accession,id,gene_names,organism_name,protein_name,length",
                "size": 2,
            },
        )
    ]
