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


def test_string_db_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    assert info["string_db"]["display_name"] == "STRING DB"
    assert info["string_db"]["category"] == "databases"
    assert info["string_db"]["output_name"] == ["interaction_network", "network_metadata"]
    assert info["string_db"]["output"] == ["TSV", "JSON"]


@pytest.mark.asyncio
async def test_string_db_network_writes_tsv_and_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("string_db")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    network_tsv = (
        "stringId_A\tstringId_B\tpreferredName_A\tpreferredName_B\tscore\n"
        "9606.ENSP00000269305\t9606.ENSP00000258149\tTP53\tMDM2\t0.999\n"
    )

    async def fake_text(endpoint: str, params: dict[str, Any], **_: Any) -> str:
        calls.append({"endpoint": endpoint, "params": dict(params)})
        return network_tsv

    monkeypatch.setattr(module, "_request_text", fake_text)

    result = await node_class().run(
        protein_ids="TP53, MDM2",
        species=9606,
        query_type="network",
        required_score=700,
        network_flavor="confidence",
        add_nodes=2,
        context=SimpleNamespace(node_dir=tmp_path),
    )

    tsv_path = Path(result["outputs"]["interaction_network"])
    metadata_path = Path(result["outputs"]["network_metadata"])
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert tsv_path.name == "interaction_network.tsv"
    assert tsv_path.read_text(encoding="utf-8") == network_tsv
    assert metadata_path.name == "network_metadata.json"
    assert metadata["query_type"] == "network"
    assert metadata["identifiers"] == ["TP53", "MDM2"]
    assert metadata["record_count"] == 1
    assert metadata["rows"][0]["preferredName_A"] == "TP53"
    assert calls == [
        {
            "endpoint": "tsv/network",
            "params": {
                "identifiers": "TP53\rMDM2",
                "species": 9606,
                "required_score": 700,
                "add_nodes": 2,
                "network_flavor": "confidence",
                "caller_identity": "BioNodulo",
            },
        }
    ]


@pytest.mark.asyncio
async def test_string_db_enrichment_writes_tsv_and_parsed_rows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("string_db")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    enrichment_tsv = (
        "category\tterm\tdescription\tp_value\tfdr\tinputGenes\n"
        "Process\tGO:0006915\tapoptotic process\t1.0e-05\t0.002\tTP53,MDM2\n"
    )

    async def fake_text(endpoint: str, params: dict[str, Any], **_: Any) -> str:
        calls.append({"endpoint": endpoint, "params": dict(params)})
        return enrichment_tsv

    monkeypatch.setattr(module, "_request_text", fake_text)

    result = await node_class().run(
        protein_ids=["TP53", "MDM2"],
        species=9606,
        query_type="enrichment",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    tsv_path = Path(result["outputs"]["interaction_network"])
    metadata = json.loads(Path(result["outputs"]["network_metadata"]).read_text(encoding="utf-8"))

    assert tsv_path.read_text(encoding="utf-8") == enrichment_tsv
    assert metadata["query_type"] == "enrichment"
    assert metadata["record_count"] == 1
    assert metadata["rows"] == [
        {
            "category": "Process",
            "term": "GO:0006915",
            "description": "apoptotic process",
            "p_value": "1.0e-05",
            "fdr": "0.002",
            "inputGenes": "TP53,MDM2",
        }
    ]
    assert calls == [
        {
            "endpoint": "tsv/enrichment",
            "params": {
                "identifiers": "TP53\rMDM2",
                "species": 9606,
                "caller_identity": "BioNodulo",
            },
        }
    ]


@pytest.mark.asyncio
async def test_string_db_rejects_empty_ids_and_bad_query_type() -> None:
    node_class = _node_class("string_db")

    with pytest.raises(ValueError, match="requires at least one protein ID"):
        await node_class().run(protein_ids="")

    with pytest.raises(ValueError, match="Unsupported STRING query_type"):
        await node_class().run(protein_ids="TP53", query_type="orthologs")
