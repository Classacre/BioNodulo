from __future__ import annotations

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


def test_opentargets_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    node_info = info["opentargets"]
    assert node_info["display_name"] == "Open Targets"
    assert node_info["category"] == "databases"
    assert node_info["output"] == ["JSON", "TSV"]
    assert node_info["output_name"] == ["associations_json", "evidence_table"]
    assert node_info["requires_external_tools"] is False
    assert node_info["experimental"] is True
    assert "target-disease" in node_info["search_aliases"]
    assert "drug discovery" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"target", "disease"}
    assert set(inputs["optional"]) == {"query_mode", "max_results", "min_score", "include_evidence"}


@pytest.mark.asyncio
async def test_opentargets_graphql_uses_shared_http_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    node_class = _node_class("opentargets")
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
            request = httpx.Request(method, url, headers=kwargs.get("headers"))
            return httpx.Response(200, json={"data": {"ok": True}}, request=request)

    monkeypatch.setattr(module, "APIHttpClient", FakeClient)

    payload = await module._graphql_request(
        "query Test { ok }",
        {"size": 3},
        retries=4,
        timeout=12.5,
    )

    assert payload == {"data": {"ok": True}}
    assert len(calls) == 1
    assert calls[0]["method"] == "POST"
    assert calls[0]["url"] == module.OPENTARGETS_GRAPHQL_URL
    assert calls[0]["json"] == {"query": "query Test { ok }", "variables": {"size": 3}}
    assert calls[0]["headers"] == {"User-Agent": module.OPENTARGETS_USER_AGENT}
    assert calls[0]["timeout"] == 12.5
    assert calls[0]["retries"] == 4
    assert calls[0]["retry_delay"] == module.RETRY_DELAY_S
    assert calls[0]["cache_ttl"] is None
    assert calls[0]["cache"] is module.OPENTARGETS_API_CACHE
    assert calls[0]["rate_limiter"] is module.OPENTARGETS_RATE_LIMITER


@pytest.mark.asyncio
async def test_opentargets_queries_target_associated_diseases(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("opentargets")
    module = importlib.import_module(node_class.__module__)
    calls: list[tuple[str, dict[str, Any]]] = []

    async def fake_graphql(query: str, variables: dict[str, Any], **_: Any) -> dict[str, Any]:
        calls.append((query, variables))
        return {
            "data": {
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
                                "score": 0.21,
                                "disease": {"id": "EFO_0000311", "name": "cancer"},
                                "datatypeScores": [{"id": "known_drug", "score": 0.2}],
                            },
                        ],
                    },
                }
            }
        }

    monkeypatch.setattr(module, "_graphql_request", fake_graphql)

    result = await node_class().run(
        target="ENSG00000141510",
        disease="",
        query_mode="target_to_diseases",
        max_results=5,
        min_score=0.5,
        include_evidence=False,
        context=SimpleNamespace(node_dir=tmp_path),
    )

    payload = result["outputs"]["associations_json"]
    evidence_path = Path(result["outputs"]["evidence_table"])

    assert payload["query_mode"] == "target_to_diseases"
    assert payload["target"] == {"id": "ENSG00000141510", "symbol": "TP53", "name": "tumor protein p53"}
    assert payload["record_count"] == 1
    assert payload["total_available"] == 2
    assert payload["associations"][0] == {
        "target_id": "ENSG00000141510",
        "target_symbol": "TP53",
        "target_name": "tumor protein p53",
        "disease_id": "EFO_0000616",
        "disease_name": "neoplasm",
        "score": 0.91,
        "datatype_scores": {"genetic_association": 0.7},
    }
    assert evidence_path.read_text(encoding="utf-8") == (
        "target_id\ttarget_symbol\tdisease_id\tdisease_name\tscore\tdatatype_scores\tevidence_count\n"
        "ENSG00000141510\tTP53\tEFO_0000616\tneoplasm\t0.91\tgenetic_association:0.7\t0\n"
    )
    assert calls[0][1] == {"ensemblId": "ENSG00000141510", "size": 5}
    assert "associatedDiseases" in calls[0][0]


@pytest.mark.asyncio
async def test_opentargets_queries_disease_associated_targets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("opentargets")
    module = importlib.import_module(node_class.__module__)

    async def fake_graphql(query: str, variables: dict[str, Any], **_: Any) -> dict[str, Any]:
        assert "associatedTargets" in query
        assert variables == {"efoId": "EFO_0000616", "size": 2}
        return {
            "data": {
                "disease": {
                    "id": "EFO_0000616",
                    "name": "neoplasm",
                    "associatedTargets": {
                        "count": 1,
                        "rows": [
                            {
                                "score": 0.88,
                                "target": {
                                    "id": "ENSG00000141510",
                                    "approvedSymbol": "TP53",
                                    "approvedName": "tumor protein p53",
                                },
                                "datatypeScores": [{"id": "genetic_association", "score": 0.6}],
                            }
                        ],
                    },
                }
            }
        }

    monkeypatch.setattr(module, "_graphql_request", fake_graphql)

    result = await node_class().run(
        target="",
        disease="EFO_0000616",
        query_mode="disease_to_targets",
        max_results=2,
        context=SimpleNamespace(node_dir=tmp_path),
    )

    payload = result["outputs"]["associations_json"]

    assert payload["query_mode"] == "disease_to_targets"
    assert payload["disease"] == {"id": "EFO_0000616", "name": "neoplasm"}
    assert payload["record_count"] == 1
    assert payload["associations"][0]["target_symbol"] == "TP53"
    assert payload["associations"][0]["disease_name"] == "neoplasm"


@pytest.mark.asyncio
async def test_opentargets_fetches_pair_evidence_when_requested(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("opentargets")
    module = importlib.import_module(node_class.__module__)
    calls: list[tuple[str, dict[str, Any]]] = []

    async def fake_graphql(query: str, variables: dict[str, Any], **_: Any) -> dict[str, Any]:
        calls.append((query, variables))
        if "evidences" in query:
            return {
                "data": {
                    "target": {
                        "id": "ENSG00000141510",
                        "approvedSymbol": "TP53",
                        "approvedName": "tumor protein p53",
                        "evidences": {
                            "count": 2,
                            "rows": [
                                {
                                    "datasourceId": "eva",
                                    "datatypeId": "genetic_association",
                                    "score": 0.45,
                                    "target": {"id": "ENSG00000141510", "approvedSymbol": "TP53"},
                                    "disease": {"id": "EFO_0000616", "name": "neoplasm"},
                                },
                                {
                                    "datasourceId": "chembl",
                                    "datatypeId": "known_drug",
                                    "score": 0.3,
                                    "target": {"id": "ENSG00000141510", "approvedSymbol": "TP53"},
                                    "disease": {"id": "EFO_0000616", "name": "neoplasm"},
                                },
                            ],
                        },
                    }
                }
            }
        return {
            "data": {
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
                                "datatypeScores": [{"id": "genetic_association", "score": 0.7}],
                            }
                        ],
                    },
                }
            }
        }

    monkeypatch.setattr(module, "_graphql_request", fake_graphql)

    result = await node_class().run(
        target="ENSG00000141510",
        disease="EFO_0000616",
        query_mode="association",
        max_results=5,
        include_evidence=True,
        context=SimpleNamespace(node_dir=tmp_path),
    )

    payload = result["outputs"]["associations_json"]
    evidence_path = Path(result["outputs"]["evidence_table"])

    assert payload["record_count"] == 1
    assert payload["associations"][0]["evidence_count"] == 2
    assert evidence_path.read_text(encoding="utf-8") == (
        "target_id\ttarget_symbol\tdisease_id\tdisease_name\tscore\tdatatype_scores\tevidence_count\n"
        "ENSG00000141510\tTP53\tEFO_0000616\tneoplasm\t0.91\tgenetic_association:0.7\t2\n"
        "ENSG00000141510\tTP53\tEFO_0000616\tneoplasm\t0.45\tgenetic_association/eva\t1\n"
        "ENSG00000141510\tTP53\tEFO_0000616\tneoplasm\t0.3\tknown_drug/chembl\t1\n"
    )
    assert len(calls) == 2
    assert calls[0][1] == {"ensemblId": "ENSG00000141510", "size": 5}
    assert calls[1][1] == {"ensemblId": "ENSG00000141510", "efoIds": ["EFO_0000616"], "size": 5}
