"""Open Targets Platform target-disease association queries."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import httpx

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin.api.http import APICache, APIHttpClient, TokenBucketRateLimiter


OPENTARGETS_GRAPHQL_URL = "https://api.platform.opentargets.org/api/v4/graphql"
OPENTARGETS_SOURCE_COMMIT = "4e04aaa289d7d7a3e79e966679da12eb0fc82aab"
OPENTARGETS_USER_AGENT = "BioNodulo/2.0 (Open Targets Platform node)"
OPENTARGETS_API_CACHE = APICache.from_environment(default_ttl_seconds=300.0)
OPENTARGETS_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=5.0, burst=1)

TARGET_ASSOCIATED_DISEASES_QUERY = """
query TargetAssociatedDiseases($ensemblId: String!, $size: Int!) {
  meta { name apiVersion dataVersion product }
  target(ensemblId: $ensemblId) {
    id approvedSymbol approvedName
    associatedDiseases(page: { index: 0, size: $size }) {
      count
      rows { score disease { id name } datatypeScores { id score } }
    }
  }
}
"""

DISEASE_ASSOCIATED_TARGETS_QUERY = """
query DiseaseAssociatedTargets($efoId: String!, $size: Int!) {
  meta { name apiVersion dataVersion product }
  disease(efoId: $efoId) {
    id name
    associatedTargets(page: { index: 0, size: $size }) {
      count
      rows { score target { id approvedSymbol approvedName } datatypeScores { id score } }
    }
  }
}
"""

PAIR_EVIDENCE_QUERY = """
query TargetDiseaseEvidence($ensemblId: String!, $efoIds: [String!]!, $size: Int!) {
  meta { name apiVersion dataVersion product }
  target(ensemblId: $ensemblId) {
    id approvedSymbol approvedName
    evidences(efoIds: $efoIds, size: $size) {
      count
      rows {
        datasourceId datatypeId score
        target { id approvedSymbol }
        disease { id name }
      }
    }
  }
}
"""


def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    output = base / node.NODE_ID
    output.mkdir(parents=True, exist_ok=True)
    return output


async def _graphql_request(
    query: str,
    variables: dict[str, Any],
    *,
    retries: int = 3,
    timeout: float = 60.0,
) -> dict[str, Any]:
    client = APIHttpClient(cache=OPENTARGETS_API_CACHE, rate_limiter=OPENTARGETS_RATE_LIMITER)
    try:
        response = await client.request(
            "POST",
            OPENTARGETS_GRAPHQL_URL,
            headers={"User-Agent": OPENTARGETS_USER_AGENT},
            json={"query": query, "variables": variables},
            timeout=timeout,
            retries=retries,
            retry_delay=1.0,
            cache_ttl=None,
        )
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("Open Targets GraphQL returned a non-object payload")
        if payload.get("errors"):
            raise RuntimeError(f"Open Targets GraphQL returned errors: {payload['errors']}")
        return payload
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Open Targets GraphQL failed with HTTP {exc.response.status_code}: {exc.response.text[:500]}"
        ) from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Open Targets GraphQL request failed: {exc}") from exc


def _score_map(value: Any) -> dict[str, float]:
    scores: dict[str, float] = {}
    for item in value if isinstance(value, list) else []:
        if isinstance(item, dict) and item.get("id"):
            scores[str(item["id"])] = float(item.get("score", 0.0) or 0.0)
    return scores


def _target_summary(value: Any) -> dict[str, str]:
    payload = value if isinstance(value, dict) else {}
    return {
        "id": str(payload.get("id", "") or ""),
        "symbol": str(payload.get("approvedSymbol", "") or ""),
        "name": str(payload.get("approvedName", "") or ""),
    }


def _disease_summary(value: Any) -> dict[str, str]:
    payload = value if isinstance(value, dict) else {}
    return {"id": str(payload.get("id", "") or ""), "name": str(payload.get("name", "") or "")}


def _target_associations(payload: dict[str, Any], min_score: float) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    target = data.get("target") if isinstance(data.get("target"), dict) else None
    if target is None:
        raise RuntimeError("Open Targets did not resolve the requested target")
    target_info = _target_summary(target)
    associated = target.get("associatedDiseases") if isinstance(target.get("associatedDiseases"), dict) else {}
    rows = associated.get("rows", []) if isinstance(associated, dict) else []
    associations = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or float(row.get("score", 0.0) or 0.0) < min_score:
            continue
        disease = _disease_summary(row.get("disease"))
        associations.append(
            {
                "target_id": target_info["id"],
                "target_symbol": target_info["symbol"],
                "target_name": target_info["name"],
                "disease_id": disease["id"],
                "disease_name": disease["name"],
                "score": float(row.get("score", 0.0) or 0.0),
                "datatype_scores": _score_map(row.get("datatypeScores")),
            }
        )
    return {
        "target": target_info,
        "disease": {},
        "total_available": int(associated.get("count", len(associations)) or 0),
        "associations": associations,
        "release": data.get("meta", {}),
    }


def _disease_associations(payload: dict[str, Any], min_score: float) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    disease = data.get("disease") if isinstance(data.get("disease"), dict) else None
    if disease is None:
        raise RuntimeError("Open Targets did not resolve the requested disease")
    disease_info = _disease_summary(disease)
    associated = disease.get("associatedTargets") if isinstance(disease.get("associatedTargets"), dict) else {}
    rows = associated.get("rows", []) if isinstance(associated, dict) else []
    associations = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or float(row.get("score", 0.0) or 0.0) < min_score:
            continue
        target = _target_summary(row.get("target"))
        associations.append(
            {
                "target_id": target["id"],
                "target_symbol": target["symbol"],
                "target_name": target["name"],
                "disease_id": disease_info["id"],
                "disease_name": disease_info["name"],
                "score": float(row.get("score", 0.0) or 0.0),
                "datatype_scores": _score_map(row.get("datatypeScores")),
            }
        )
    return {
        "target": {},
        "disease": disease_info,
        "total_available": int(associated.get("count", len(associations)) or 0),
        "associations": associations,
        "release": data.get("meta", {}),
    }


def _evidence_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    target = data.get("target") if isinstance(data.get("target"), dict) else {}
    evidence = target.get("evidences") if isinstance(target.get("evidences"), dict) else {}
    rows: list[dict[str, Any]] = []
    for item in evidence.get("rows", []) if isinstance(evidence.get("rows"), list) else []:
        if not isinstance(item, dict):
            continue
        target_info = _target_summary(item.get("target"))
        disease_info = _disease_summary(item.get("disease"))
        rows.append(
            {
                "target_id": target_info["id"],
                "target_symbol": target_info["symbol"],
                "disease_id": disease_info["id"],
                "disease_name": disease_info["name"],
                "score": float(item.get("score", 0.0) or 0.0),
                "datatype_scores": f"{item.get('datatypeId', '')}/{item.get('datasourceId', '')}",
                "evidence_count": 1,
            }
        )
    return rows


def _write_tsv(path: Path, associations: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> None:
    fields = ("target_id", "target_symbol", "disease_id", "disease_name", "score", "datatype_scores", "evidence_count")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in associations:
            copy = dict(row)
            scores = copy.get("datatype_scores", {})
            if isinstance(scores, dict):
                copy["datatype_scores"] = ";".join(f"{key}:{float(value):.6g}" for key, value in sorted(scores.items()))
            copy.setdefault("evidence_count", 0)
            writer.writerow(copy)
        writer.writerows(evidence)


class OpenTargetsNode(BaseNode):
    """Query source-pinned Open Targets association and evidence schema fields."""

    NODE_ID = "opentargets"
    DISPLAY_NAME = "Open Targets"
    CATEGORY = "databases"
    DESCRIPTION = "Query Open Targets Platform target-disease associations and optional pair evidence."
    SEARCH_ALIASES = ["Open Targets", "target disease", "evidence", "genetics", "drug discovery"]
    RETURN_TYPES = ("JSON", "TSV")
    RETURN_NAMES = ("associations_json", "evidence_table")
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True
    VERSION = "Open Targets Platform API source snapshot 2026-07-19"
    GIT_URL = "https://github.com/opentargets/platform-api.git"
    GIT_COMMIT = OPENTARGETS_SOURCE_COMMIT
    SOURCE_URL = GIT_URL
    DOCUMENTATION_URL = "https://platform.opentargets.org/api"
    UPSTREAM_SOURCE = "app/models/GQLSchema.scala; app/models/gql/Objects.scala; app/models/gql/Arguments.scala"
    NETWORK_SEMANTICS = "Each response records the live API and dataVersion metadata returned by the platform."

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {},
            "optional": {
                "target": (
                    "STRING",
                    {
                        "default": "",
                        "description": "Ensembl target ID",
                        "displayOptions": {"show": {"query_mode": ["association", "target_to_diseases"]}},
                    },
                ),
                "disease": (
                    "STRING",
                    {
                        "default": "",
                        "description": "EFO disease ID",
                        "displayOptions": {"show": {"query_mode": ["association", "disease_to_targets"]}},
                    },
                ),
                "query_mode": ("STRING", {"default": "association", "options": ["association", "target_to_diseases", "disease_to_targets"]}),
                "max_results": ("INT", {"default": 25, "min": 1, "max": 3000}),
                "min_score": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0}),
                "include_evidence": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"context": ("CONTEXT", {})},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        target = str(kwargs.get("target", "") or "").strip()
        disease = str(kwargs.get("disease", "") or "").strip()
        mode = str(kwargs.get("query_mode", "association") or "association")
        if mode not in {"association", "target_to_diseases", "disease_to_targets"}:
            raise ValueError(f"Unsupported Open Targets query_mode: {mode}")
        raw_max_results = kwargs.get("max_results", 25)
        max_results = int(25 if raw_max_results in (None, "") else raw_max_results)
        raw_min_score = kwargs.get("min_score", 0.0)
        min_score = float(0.0 if raw_min_score in (None, "") else raw_min_score)
        if not 1 <= max_results <= 3000:
            raise ValueError("Open Targets max_results must be between 1 and 3000")
        if not 0 <= min_score <= 1:
            raise ValueError("Open Targets min_score must be between 0 and 1")
        if kwargs.get("include_evidence", False) and (not target or not disease):
            raise ValueError("Open Targets include_evidence requires both target and disease")
        if mode == "target_to_diseases" or (mode == "association" and target):
            if not target:
                raise ValueError("Open Targets target query requires target")
            normalized = _target_associations(
                await _graphql_request(TARGET_ASSOCIATED_DISEASES_QUERY, {"ensemblId": target, "size": max_results}),
                min_score,
            )
            if mode == "association" and disease:
                normalized["associations"] = [row for row in normalized["associations"] if row["disease_id"] == disease]
        elif mode == "disease_to_targets" or disease:
            if not disease:
                raise ValueError("Open Targets disease query requires disease")
            normalized = _disease_associations(
                await _graphql_request(DISEASE_ASSOCIATED_TARGETS_QUERY, {"efoId": disease, "size": max_results}),
                min_score,
            )
        else:
            raise ValueError("Open Targets association mode requires target or disease")
        evidence: list[dict[str, Any]] = []
        if kwargs.get("include_evidence", False):
            evidence = _evidence_rows(
                await _graphql_request(
                    PAIR_EVIDENCE_QUERY,
                    {"ensemblId": target, "efoIds": [disease], "size": max_results},
                )
            )
            for association in normalized["associations"]:
                if association["target_id"] == target and association["disease_id"] == disease:
                    association["evidence_count"] = len(evidence)
        result = {
            "query_mode": mode,
            "target": normalized["target"],
            "disease": normalized["disease"],
            "record_count": len(normalized["associations"]),
            "total_available": normalized["total_available"],
            "min_score": min_score,
            "include_evidence": bool(kwargs.get("include_evidence", False)),
            "release": normalized["release"],
            "associations": normalized["associations"],
        }
        output = _node_output_dir(self, context)
        table = output / "evidence.tsv"
        _write_tsv(table, normalized["associations"], evidence)
        return {"outputs": {"associations_json": result, "evidence_table": str(table)}}
