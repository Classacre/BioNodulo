"""Validated descriptive knowledge attached to a node.

Knowledge links document provenance and relationships. They do not change ports,
runtime admission, or scientific compatibility checks.
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Set
from datetime import date
from typing import Any
from urllib.parse import urlsplit


_EDAM_URI = re.compile(r"^https?://edamontology\.org/(?:topic|operation)_[0-9]{4,}$")
_ISO_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_DNS_HOST = re.compile(r"^(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$")
_RELATION_KINDS = frozenset({"alternative_to", "complements", "documented_successor", "superseded_by"})


def _object(value: object, label: str, allowed: set[str], required: Set[str] = frozenset()) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    if missing := required - value.keys():
        raise ValueError(f"{label} is missing {', '.join(sorted(missing))}")
    if unknown := value.keys() - allowed:
        raise ValueError(f"{label} has unknown fields: {', '.join(sorted(unknown))}")
    return value


def _text(value: object, label: str, *, maximum: int = 2048) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > maximum:
        raise ValueError(f"{label} must be nonempty, trimmed text of at most {maximum} characters")
    if not all(character.isprintable() for character in value):
        raise ValueError(f"{label} must contain only printable characters")
    return value


def _url(value: object, label: str) -> str:
    uri = _text(value, label)
    try:
        parsed = urlsplit(uri)
        port = parsed.port
    except ValueError as error:
        raise ValueError(f"{label} must be a safe HTTP(S) URL") from error
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password
            or "\\" in uri):
        raise ValueError(f"{label} must be a safe HTTP(S) URL")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError(f"{label} must be a safe HTTP(S) URL")
    host = parsed.hostname.casefold()
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise ValueError(f"{label} must use a public host")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if _DNS_HOST.fullmatch(host) is None or host.rsplit(".", 1)[-1].isdigit():
            raise ValueError(f"{label} must use a public host")
    else:
        # Evidence links must use DNS names. This also avoids a frontend/backend
        # disagreement about which routable address ranges count as public.
        raise ValueError(f"{label} must use a public DNS host")
    return uri


def _date(value: object, label: str) -> str:
    text = _text(value, label, maximum=10)
    if not _ISO_DATE.fullmatch(text):
        raise ValueError(f"{label} must be an ISO date (YYYY-MM-DD)")
    try:
        date.fromisoformat(text)
    except ValueError as error:
        raise ValueError(f"{label} must be a valid ISO date") from error
    return text


def _array(value: object, label: str) -> list[Any]:
    if not isinstance(value, list) or len(value) > 1024:
        raise ValueError(f"{label} must be an array of at most 1024 entries")
    return value


def validate_knowledge(value: object, *, node_id: str | None = None) -> dict[str, Any]:
    """Return a detached, JSON-ready copy of schema v1 or raise ValueError."""
    raw = _object(value, "knowledge", {
        "schema_version", "tool_id", "topics", "operations", "relations",
        "citation_evidence", "reviewed_at", "introduced_at",
    }, {"schema_version"})
    if type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
        raise ValueError("knowledge.schema_version must be 1")
    result: dict[str, Any] = {"schema_version": 1}
    if "tool_id" in raw:
        result["tool_id"] = _url(raw["tool_id"], "knowledge.tool_id")
    for field in ("reviewed_at", "introduced_at"):
        if field in raw:
            result[field] = _date(raw[field], f"knowledge.{field}")
    for field, edam_type in (("topics", "topic"), ("operations", "operation")):
        if field not in raw:
            continue
        entries: list[dict[str, str]] = []
        seen: set[str] = set()
        for index, item in enumerate(_array(raw[field], f"knowledge.{field}")):
            label = f"knowledge.{field}[{index}]"
            annotation = _object(item, label, {"uri", "label"}, {"uri", "label"})
            uri = _url(annotation["uri"], f"{label}.uri")
            if not _EDAM_URI.fullmatch(uri) or f"/{edam_type}_" not in uri:
                raise ValueError(f"{label}.uri must identify an EDAM {edam_type}")
            if uri in seen:
                raise ValueError(f"knowledge.{field} contains duplicate URI {uri}")
            seen.add(uri)
            entries.append({"uri": uri, "label": _text(annotation["label"], f"{label}.label", maximum=256)})
        result[field] = entries
    if "relations" in raw:
        relations: list[dict[str, Any]] = []
        seen_relations: set[tuple[str, str, str | None, str | None]] = set()
        for index, item in enumerate(_array(raw["relations"], "knowledge.relations")):
            label = f"knowledge.relations[{index}]"
            relation = _object(item, label, {"target_node_id", "kind", "evidence", "source_port", "target_port"},
                               {"target_node_id", "kind", "evidence"})
            target = _text(relation["target_node_id"], f"{label}.target_node_id", maximum=128)
            if node_id is not None and target == node_id:
                raise ValueError(f"{label} must not point to itself")
            kind = _text(relation["kind"], f"{label}.kind", maximum=64)
            if kind not in _RELATION_KINDS:
                raise ValueError(f"{label}.kind is unknown: {kind}")
            source_port = _text(relation["source_port"], f"{label}.source_port", maximum=128) if "source_port" in relation else None
            target_port = _text(relation["target_port"], f"{label}.target_port", maximum=128) if "target_port" in relation else None
            key = (target, kind, source_port, target_port)
            if key in seen_relations:
                raise ValueError(f"knowledge.relations contains duplicate relation to {target}")
            seen_relations.add(key)
            evidence = _object(relation["evidence"], f"{label}.evidence", {"url", "checked_at", "note"},
                               {"url", "checked_at", "note"})
            item_result: dict[str, Any] = {
                "target_node_id": target, "kind": kind,
                "evidence": {
                    "url": _url(evidence["url"], f"{label}.evidence.url"),
                    "checked_at": _date(evidence["checked_at"], f"{label}.evidence.checked_at"),
                    "note": _text(evidence["note"], f"{label}.evidence.note"),
                },
            }
            if source_port is not None:
                item_result["source_port"] = source_port
            if target_port is not None:
                item_result["target_port"] = target_port
            relations.append(item_result)
        result["relations"] = relations
    if "citation_evidence" in raw:
        citations: list[dict[str, str]] = []
        seen_citations: set[tuple[str, str]] = set()
        for index, item in enumerate(_array(raw["citation_evidence"], "knowledge.citation_evidence")):
            label = f"knowledge.citation_evidence[{index}]"
            citation = _object(item, label, {"identifier", "source_url", "checked_at", "note"},
                               {"identifier", "source_url", "checked_at", "note"})
            identifier = _text(citation["identifier"], f"{label}.identifier", maximum=256)
            source_url = _url(citation["source_url"], f"{label}.source_url")
            citation_key = (identifier.casefold(), source_url)
            if citation_key in seen_citations:
                raise ValueError(f"knowledge.citation_evidence contains duplicate entry {identifier}")
            seen_citations.add(citation_key)
            citations.append({"identifier": identifier, "source_url": source_url,
                              "checked_at": _date(citation["checked_at"], f"{label}.checked_at"),
                              "note": _text(citation["note"], f"{label}.note")})
        result["citation_evidence"] = citations
    return result
