"""Compact Open Targets Platform GraphQL contracts."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.nodes.registry import NodeRegistry


def _node() -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node = registry.get("opentargets")
    assert node is not None
    return node


def test_opentargets_is_focused_and_pins_schema_authority() -> None:
    node = _node()
    module = importlib.import_module(node.__module__)
    assert node.__module__ == "bionodulo.nodes.builtin.opentargets_family.associations"
    assert node.GIT_COMMIT == "4e04aaa289d7d7a3e79e966679da12eb0fc82aab"
    assert node.RETURN_NAMES == ("associations_json", "evidence_table")
    assert node.EXPERIMENTAL is True
    assert node.INPUT_TYPES()["required"] == {}
    assert {"target", "disease"}.issubset(node.INPUT_TYPES()["optional"])
    optional = node.INPUT_TYPES()["optional"]
    assert optional["target"][1]["displayOptions"] == {
        "show": {"query_mode": ["association", "target_to_diseases"]},
    }
    assert optional["disease"][1]["displayOptions"] == {
        "show": {"query_mode": ["association", "disease_to_targets"]},
    }
    assert "meta { name apiVersion dataVersion product }" in module.TARGET_ASSOCIATED_DISEASES_QUERY
    assert "evidences(efoIds: $efoIds, size: $size)" in module.PAIR_EVIDENCE_QUERY
    assert node.INPUT_TYPES()["optional"]["max_results"][1]["max"] == 3000


@pytest.mark.asyncio
async def test_target_associations_record_release_and_filter_pair(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node = _node()
    module = importlib.import_module(node.__module__)
    calls: list[tuple[str, dict[str, Any]]] = []

    async def fake_graphql(query: str, variables: dict[str, Any], **_: Any) -> dict[str, Any]:
        calls.append((query, variables))
        return {
            "data": {
                "meta": {"apiVersion": "4", "dataVersion": "26.06", "product": "platform"},
                "target": {
                    "id": "ENSG00000141510",
                    "approvedSymbol": "TP53",
                    "approvedName": "tumor protein p53",
                    "associatedDiseases": {
                        "count": 2,
                        "rows": [
                            {
                                "score": 0.91,
                                "disease": {"id": "EFO_0000616", "name": "neoplasm"},
                                "datatypeScores": [{"id": "genetic_association", "score": 0.7}],
                            },
                            {
                                "score": 0.2,
                                "disease": {"id": "EFO_OTHER", "name": "other"},
                                "datatypeScores": [],
                            },
                        ],
                    },
                },
            }
        }

    monkeypatch.setattr(module, "_graphql_request", fake_graphql)
    result = await node().run(
        target="ENSG00000141510",
        disease="EFO_0000616",
        query_mode="association",
        min_score=0.1,
        context=SimpleNamespace(node_dir=tmp_path),
    )
    payload = result["outputs"]["associations_json"]
    assert payload["release"]["dataVersion"] == "26.06"
    assert payload["record_count"] == 1
    assert payload["associations"][0]["disease_id"] == "EFO_0000616"
    assert calls[0][1] == {"ensemblId": "ENSG00000141510", "size": 25}


@pytest.mark.asyncio
async def test_pair_evidence_is_explicit_and_counted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    node = _node()
    module = importlib.import_module(node.__module__)

    async def fake_graphql(query: str, variables: dict[str, Any], **_: Any) -> dict[str, Any]:
        if "evidences" in query:
            return {
                "data": {
                    "meta": {"dataVersion": "26.06"},
                    "target": {
                        "evidences": {
                            "count": 1,
                            "rows": [
                                {
                                    "datasourceId": "eva",
                                    "datatypeId": "genetic_association",
                                    "score": 0.45,
                                    "target": {"id": "ENSG00000141510", "approvedSymbol": "TP53"},
                                    "disease": {"id": "EFO_0000616", "name": "neoplasm"},
                                }
                            ],
                        }
                    },
                }
            }
        return {
            "data": {
                "meta": {"dataVersion": "26.06"},
                "target": {
                    "id": "ENSG00000141510",
                    "approvedSymbol": "TP53",
                    "approvedName": "tumor protein p53",
                    "associatedDiseases": {
                        "count": 1,
                        "rows": [
                            {
                                "score": 0.91,
                                "disease": {"id": "EFO_0000616", "name": "neoplasm"},
                                "datatypeScores": [],
                            }
                        ],
                    },
                },
            }
        }

    monkeypatch.setattr(module, "_graphql_request", fake_graphql)
    result = await node().run(
        target="ENSG00000141510",
        disease="EFO_0000616",
        include_evidence=True,
        context=SimpleNamespace(node_dir=tmp_path),
    )
    association = result["outputs"]["associations_json"]["associations"][0]
    table = Path(result["outputs"]["evidence_table"]).read_text(encoding="utf-8")
    assert association["evidence_count"] == 1
    assert "genetic_association/eva" in table


@pytest.mark.asyncio
async def test_opentargets_rejects_invalid_bounds_and_missing_pair() -> None:
    node = _node()
    with pytest.raises(ValueError, match="max_results"):
        await node().run(target="ENSG1", max_results=0)
    with pytest.raises(ValueError, match="min_score"):
        await node().run(target="ENSG1", min_score=1.1)
    with pytest.raises(ValueError, match="both target and disease"):
        await node().run(target="ENSG1", include_evidence=True)
