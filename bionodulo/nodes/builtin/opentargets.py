"""Open Targets Platform integration nodes."""
from __future__ import annotations

import asyncio
import csv
from pathlib import Path
from typing import Any

import httpx

from bionodulo.nodes.base import BaseNode


OPENTARGETS_GRAPHQL_URL = "https://api.platform.opentargets.org/api/v4/graphql"
OPENTARGETS_USER_AGENT = "BioNodulo/2.0 (workflow node; Open Targets Platform)"
MAX_RETRIES = 3
RETRY_DELAY_S = 1.0
REQUEST_TIMEOUT_S = 60.0

TARGET_ASSOCIATED_DISEASES_QUERY = """
query TargetAssociatedDiseases($ensemblId: String!, $size: Int!) {
  target(ensemblId: $ensemblId) {
    id
    approvedSymbol
    approvedName
    associatedDiseases(page: { index: 0, size: $size }) {
      count
      rows {
        score
        disease {
          id
          name
        }
        datatypeScores {
          id
          score
        }
      }
    }
  }
}
"""

DISEASE_ASSOCIATED_TARGETS_QUERY = """
query DiseaseAssociatedTargets($efoId: String!, $size: Int!) {
  disease(efoId: $efoId) {
    id
    name
    associatedTargets(page: { index: 0, size: $size }) {
      count
      rows {
        score
        target {
          id
          approvedSymbol
          approvedName
        }
        datatypeScores {
          id
          score
        }
      }
    }
  }
}
"""

PAIR_EVIDENCE_QUERY = """
query TargetDiseaseEvidence($ensemblId: String!, $efoIds: [String!]!, $size: Int!) {
  target(ensemblId: $ensemblId) {
    id
    approvedSymbol
    approvedName
    evidences(efoIds: $efoIds, size: $size) {
      count
      rows {
        datasourceId
        datatypeId
        score
        target {
          id
          approvedSymbol
        }
        disease {
          id
          name
        }
      }
    }
  }
}
"""


def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


async def _graphql_request(
    query: str,
    variables: dict[str, Any],
    *,
    retries: int = MAX_RETRIES,
    timeout: float = REQUEST_TIMEOUT_S,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                headers={"User-Agent": OPENTARGETS_USER_AGENT},
            ) as client:
                response = await client.post(
                    OPENTARGETS_GRAPHQL_URL,
                    json={"query": query, "variables": variables},
                )
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict) and payload.get("errors"):
                raise RuntimeError(f"Open Targets GraphQL returned errors: {payload['errors']}")
            return payload if isinstance(payload, dict) else {}
        except httpx.HTTPStatusError as exc:
            last_error = exc
            status = exc.response.status_code
            if status < 500 or attempt >= retries - 1:
                body = exc.response.text[:500]
                raise RuntimeError(f"Open Targets GraphQL failed with HTTP {status}: {body}") from exc
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt >= retries - 1:
                raise RuntimeError(f"Open Targets GraphQL request failed: {exc}") from exc
        await asyncio.sleep(RETRY_DELAY_S * (2 ** attempt))
    raise RuntimeError(f"Open Targets GraphQL request failed: {last_error}")


def _clean_id(value: Any) -> str:
    return str(value or "").strip()


def _score_map(datatype_scores: Any) -> dict[str, float]:
    scores: dict[str, float] = {}
    if not isinstance(datatype_scores, list):
        return scores
    for item in datatype_scores:
        if not isinstance(item, dict):
            continue
        key = str(item.get("id", "") or "")
        if not key:
            continue
        scores[key] = float(item.get("score", 0.0) or 0.0)
    return scores


def _target_summary(payload: dict[str, Any] | None) -> dict[str, str]:
    payload = payload or {}
    return {
        "id": str(payload.get("id", "") or ""),
        "symbol": str(payload.get("approvedSymbol", "") or ""),
        "name": str(payload.get("approvedName", "") or ""),
    }


def _disease_summary(payload: dict[str, Any] | None) -> dict[str, str]:
    payload = payload or {}
    return {
        "id": str(payload.get("id", "") or ""),
        "name": str(payload.get("name", "") or ""),
    }


def _target_to_disease_payload(payload: dict[str, Any], *, min_score: float) -> dict[str, Any]:
    target = payload.get("data", {}).get("target") if isinstance(payload.get("data"), dict) else {}
    if not isinstance(target, dict):
        target = {}
    target_info = _target_summary(target)
    associated = target.get("associatedDiseases") if isinstance(target.get("associatedDiseases"), dict) else {}
    rows = associated.get("rows", []) if isinstance(associated, dict) else []
    associations = [
        _association_from_target_row(target_info, row)
        for row in rows
        if isinstance(row, dict) and float(row.get("score", 0.0) or 0.0) >= min_score
    ]
    return {
        "target": target_info,
        "disease": {},
        "total_available": int(associated.get("count", len(rows)) or 0) if isinstance(associated, dict) else 0,
        "associations": associations,
    }


def _disease_to_target_payload(payload: dict[str, Any], *, min_score: float) -> dict[str, Any]:
    disease = payload.get("data", {}).get("disease") if isinstance(payload.get("data"), dict) else {}
    if not isinstance(disease, dict):
        disease = {}
    disease_info = _disease_summary(disease)
    associated = disease.get("associatedTargets") if isinstance(disease.get("associatedTargets"), dict) else {}
    rows = associated.get("rows", []) if isinstance(associated, dict) else []
    associations = [
        _association_from_disease_row(disease_info, row)
        for row in rows
        if isinstance(row, dict) and float(row.get("score", 0.0) or 0.0) >= min_score
    ]
    return {
        "target": {},
        "disease": disease_info,
        "total_available": int(associated.get("count", len(rows)) or 0) if isinstance(associated, dict) else 0,
        "associations": associations,
    }


def _association_from_target_row(target: dict[str, str], row: dict[str, Any]) -> dict[str, Any]:
    disease = row.get("disease") if isinstance(row.get("disease"), dict) else {}
    return {
        "target_id": target["id"],
        "target_symbol": target["symbol"],
        "target_name": target["name"],
        "disease_id": str(disease.get("id", "") or ""),
        "disease_name": str(disease.get("name", "") or ""),
        "score": float(row.get("score", 0.0) or 0.0),
        "datatype_scores": _score_map(row.get("datatypeScores")),
    }


def _association_from_disease_row(disease: dict[str, str], row: dict[str, Any]) -> dict[str, Any]:
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    return {
        "target_id": str(target.get("id", "") or ""),
        "target_symbol": str(target.get("approvedSymbol", "") or ""),
        "target_name": str(target.get("approvedName", "") or ""),
        "disease_id": disease["id"],
        "disease_name": disease["name"],
        "score": float(row.get("score", 0.0) or 0.0),
        "datatype_scores": _score_map(row.get("datatypeScores")),
    }


def _evidence_from_pair_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    evidence_rows: list[dict[str, Any]] = []
    target = payload.get("data", {}).get("target") if isinstance(payload.get("data"), dict) else {}
    target_info = _target_summary(target if isinstance(target, dict) else {})
    evidences = target.get("evidences") if isinstance(target, dict) else {}
    evidence_items = evidences.get("rows", []) if isinstance(evidences, dict) else []
    if not evidence_items:
        return evidence_rows
    for item in evidence_items:
        if not isinstance(item, dict):
            continue
        disease = item.get("disease") if isinstance(item.get("disease"), dict) else {}
        item_target = item.get("target") if isinstance(item.get("target"), dict) else {}
        evidence_rows.append({
            "target_id": str(item_target.get("id", "") or target_info["id"]),
            "target_symbol": str(item_target.get("approvedSymbol", "") or target_info["symbol"]),
            "disease_id": str(disease.get("id", "") or ""),
            "disease_name": str(disease.get("name", "") or ""),
            "score": float(item.get("score", 0.0) or 0.0),
            "datatype_scores": f"{item.get('datatypeId', '')}/{item.get('datasourceId', '')}",
            "evidence_count": 1,
        })
    return evidence_rows


def _format_score(value: Any) -> str:
    return f"{float(value):.6g}"


def _format_datatype_scores(value: Any) -> str:
    if isinstance(value, dict):
        return ";".join(f"{key}:{_format_score(score)}" for key, score in sorted(value.items()))
    return str(value or "")


def _write_evidence_tsv(path: Path, associations: list[dict[str, Any]], evidence_rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow([
            "target_id",
            "target_symbol",
            "disease_id",
            "disease_name",
            "score",
            "datatype_scores",
            "evidence_count",
        ])
        for association in associations:
            writer.writerow([
                association.get("target_id", ""),
                association.get("target_symbol", ""),
                association.get("disease_id", ""),
                association.get("disease_name", ""),
                _format_score(association.get("score", 0.0)),
                _format_datatype_scores(association.get("datatype_scores", {})),
                int(association.get("evidence_count", 0) or 0),
            ])
        for evidence in evidence_rows:
            writer.writerow([
                evidence.get("target_id", ""),
                evidence.get("target_symbol", ""),
                evidence.get("disease_id", ""),
                evidence.get("disease_name", ""),
                _format_score(evidence.get("score", 0.0)),
                _format_datatype_scores(evidence.get("datatype_scores", "")),
                int(evidence.get("evidence_count", 0) or 0),
            ])


class OpenTargetsNode(BaseNode):
    """Query Open Targets target-disease association summaries."""

    NODE_ID = "opentargets"
    DISPLAY_NAME = "Open Targets"
    CATEGORY = "databases"
    DESCRIPTION = "Query Open Targets Platform target-disease associations and supporting evidence."
    SEARCH_ALIASES = [
        "open targets",
        "opentargets",
        "target-disease",
        "association",
        "evidence",
        "drug discovery",
        "genetics",
    ]
    RETURN_TYPES = ("JSON", "TSV")
    RETURN_NAMES = ("associations_json", "evidence_table")
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True
    DOCUMENTATION_URL = "https://platform.opentargets.org/api"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "target": ("STRING", {"default": "", "description": "Ensembl target ID, e.g. ENSG00000141510"}),
                "disease": ("STRING", {"default": "", "description": "EFO disease ID, e.g. EFO_0000616"}),
            },
            "optional": {
                "query_mode": (
                    "STRING",
                    {
                        "default": "association",
                        "options": ["association", "target_to_diseases", "disease_to_targets"],
                    },
                ),
                "max_results": ("INT", {"default": 25, "min": 1, "max": 500}),
                "min_score": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.05}),
                "include_evidence": ("BOOLEAN", {"default": False}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        target = _clean_id(kwargs.get("target"))
        disease = _clean_id(kwargs.get("disease"))
        query_mode = str(kwargs.get("query_mode", "association") or "association")
        max_results = max(1, int(kwargs.get("max_results", 25) or 25))
        min_score = max(0.0, min(float(kwargs.get("min_score", 0.0) or 0.0), 1.0))
        include_evidence = bool(kwargs.get("include_evidence", False))

        if query_mode == "target_to_diseases":
            if not target:
                raise ValueError("Open Targets target_to_diseases mode requires target")
            payload = await _graphql_request(
                TARGET_ASSOCIATED_DISEASES_QUERY,
                {"ensemblId": target, "size": max_results},
            )
            normalized = _target_to_disease_payload(payload, min_score=min_score)
        elif query_mode == "disease_to_targets":
            if not disease:
                raise ValueError("Open Targets disease_to_targets mode requires disease")
            payload = await _graphql_request(
                DISEASE_ASSOCIATED_TARGETS_QUERY,
                {"efoId": disease, "size": max_results},
            )
            normalized = _disease_to_target_payload(payload, min_score=min_score)
        else:
            if not target and not disease:
                raise ValueError("Open Targets association mode requires target or disease")
            payload = await _graphql_request(
                TARGET_ASSOCIATED_DISEASES_QUERY,
                {"ensemblId": target, "size": max_results},
            ) if target else await _graphql_request(
                DISEASE_ASSOCIATED_TARGETS_QUERY,
                {"efoId": disease, "size": max_results},
            )
            normalized = _target_to_disease_payload(payload, min_score=min_score) if target else _disease_to_target_payload(
                payload,
                min_score=min_score,
            )

        evidence_rows: list[dict[str, Any]] = []
        if include_evidence and target and disease:
            pair_payload = await _graphql_request(
                PAIR_EVIDENCE_QUERY,
                {"ensemblId": target, "efoIds": [disease], "size": max_results},
            )
            evidence_rows = _evidence_from_pair_payload(pair_payload)
            for association in normalized["associations"]:
                if association["target_id"] == target and association["disease_id"] == disease:
                    association["evidence_count"] = len(evidence_rows)

        result = {
            "query_mode": query_mode,
            "target": normalized["target"],
            "disease": normalized["disease"],
            "record_count": len(normalized["associations"]),
            "total_available": normalized["total_available"],
            "min_score": min_score,
            "include_evidence": include_evidence,
            "associations": normalized["associations"],
        }

        out_dir = _node_output_dir(self, context)
        evidence_path = out_dir / "evidence.tsv"
        _write_evidence_tsv(evidence_path, normalized["associations"], evidence_rows)
        return {"outputs": {"associations_json": result, "evidence_table": str(evidence_path)}}
