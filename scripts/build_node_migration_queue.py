#!/usr/bin/env python3
"""Build the quarantined node-family work queue from the immutable ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit


DEFAULT_BASELINE = Path("bionodulo/nodes/generated/baseline-ledger.json")
DEFAULT_RULES = Path("bionodulo/nodes/catalog/family-assignment-rules.json")
DEFAULT_OUTPUT = Path("bionodulo/nodes/generated/migration-queue.json")
EXPECTED_NODE_COUNT = 943
_SAFE_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,127}$")
_SAFE_PATH_RE = re.compile(r"^[a-z0-9_./-]+$")
_HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
_RELEASE_TAG_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._-]{0,127}$")


class MigrationQueueError(RuntimeError):
    """Raised when family assignments are incomplete or ambiguous."""


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")


def _sha256(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _expect_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise MigrationQueueError(f"{label} must be an object")
    return value


def _expect_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise MigrationQueueError(f"{label} must be a nonempty string")
    return value


def _safe_identifier(value: str, label: str) -> str:
    if _SAFE_ID_RE.fullmatch(value) is None:
        raise MigrationQueueError(f"{label} must be a canonical lowercase identifier")
    return value


def _safe_path(value: str, label: str) -> str:
    if (
        _SAFE_PATH_RE.fullmatch(value) is None
        or value.startswith("/")
        or value.endswith("/")
        or "//" in value
        or any(part in ("", ".", "..") for part in value.split("/"))
    ):
        raise MigrationQueueError(f"{label} must be a canonical repository-relative path")
    return value


def _https_url(value: object, label: str) -> str:
    source = _expect_string(value, label)
    try:
        source.encode("ascii")
        parsed = urlsplit(source)
    except (UnicodeEncodeError, ValueError) as error:
        raise MigrationQueueError(f"{label} must be a canonical HTTPS URL") from error
    if (
        parsed.scheme != "https"
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not parsed.path
        or "\\" in source
        or "%" in source
    ):
        raise MigrationQueueError(f"{label} must be a canonical HTTPS URL")
    return source


def _validated_upstream(value: object) -> Mapping[str, str]:
    upstream = _expect_mapping(value, "upstream")
    expected = {
        "repository_url",
        "release_tag",
        "tag_object",
        "commit",
        "documentation_url",
    }
    if set(upstream) != expected:
        raise MigrationQueueError("upstream contains unknown or missing fields")
    commit = _expect_string(upstream["commit"], "upstream commit")
    tag_object = _expect_string(upstream["tag_object"], "upstream tag_object")
    if _HEX40_RE.fullmatch(commit) is None:
        raise MigrationQueueError("upstream commit must be 40 lowercase hexadecimal characters")
    if _HEX40_RE.fullmatch(tag_object) is None:
        raise MigrationQueueError("upstream tag_object must be 40 lowercase hexadecimal characters")
    release_tag = _expect_string(upstream["release_tag"], "upstream release_tag")
    if _RELEASE_TAG_RE.fullmatch(release_tag) is None:
        raise MigrationQueueError("upstream release_tag must be a canonical immutable tag")
    return {
        "commit": commit,
        "documentation_url": _https_url(upstream["documentation_url"], "upstream documentation_url"),
        "release_tag": release_tag,
        "repository_url": _https_url(upstream["repository_url"], "upstream repository_url"),
        "tag_object": tag_object,
    }


def _legacy_lane(module: str) -> str:
    prefix = "bionodulo.nodes.builtin."
    relative = module[len(prefix) :] if module.startswith(prefix) else module
    lane = re.sub(r"[^a-z0-9]+", "_", relative.lower()).strip("_")
    if not lane:
        raise MigrationQueueError(f"cannot derive legacy lane from module {module!r}")
    return "legacy_" + lane


def _validated_rules(rules: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    if set(rules) != {"schema_version", "confirmed_families"}:
        raise MigrationQueueError("assignment rules contain unknown or missing fields")
    if rules["schema_version"] != 1:
        raise MigrationQueueError("assignment rules schema_version must equal 1")
    families = rules["confirmed_families"]
    if not isinstance(families, list):
        raise MigrationQueueError("confirmed_families must be an array")

    result: list[Mapping[str, Any]] = []
    family_ids: set[str] = set()
    exclusive_paths: set[str] = set()
    for index, raw_family in enumerate(families):
        family = _expect_mapping(raw_family, f"confirmed_families[{index}]")
        expected = {
            "family_id",
            "ownership",
            "node_id_prefix",
            "expected_count",
            "exclusive_path",
            "fixture_prefix",
            "cloud_job_label",
            "r2_test_prefix",
            "upstream",
        }
        if set(family) != expected:
            raise MigrationQueueError(f"confirmed_families[{index}] contains unknown or missing fields")
        family_id = _safe_identifier(_expect_string(family["family_id"], "family_id"), "family_id")
        if family_id in family_ids:
            raise MigrationQueueError(f"duplicate confirmed family {family_id}")
        family_ids.add(family_id)
        path = _safe_path(
            _expect_string(family["exclusive_path"], "exclusive_path"),
            "exclusive_path",
        )
        if path in exclusive_paths:
            raise MigrationQueueError(f"duplicate exclusive path {path}")
        exclusive_paths.add(path)
        if not isinstance(family["expected_count"], int) or family["expected_count"] < 1:
            raise MigrationQueueError("expected_count must be a positive integer")
        result.append({**family, "upstream": _validated_upstream(family["upstream"])})
    return tuple(result)


def build_queue(
    baseline_value: object,
    rules_value: object,
) -> dict[str, Any]:
    baseline = _expect_mapping(baseline_value, "baseline ledger")
    rules = _expect_mapping(rules_value, "assignment rules")
    families = _validated_rules(rules)
    entries = baseline.get("entries")
    if not isinstance(entries, list) or len(entries) != EXPECTED_NODE_COUNT:
        raise MigrationQueueError(f"baseline ledger must contain exactly {EXPECTED_NODE_COUNT} entries")

    nodes_by_rule: dict[str, list[str]] = {}
    matched_rules: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for family in families:
        prefix = _expect_string(family["node_id_prefix"], "node_id_prefix")
        matching = sorted(
            entry["node_id"]
            for entry in entries
            if isinstance(entry, dict) and isinstance(entry.get("node_id"), str) and entry["node_id"].startswith(prefix)
        )
        expected_count = family["expected_count"]
        if len(matching) != expected_count:
            raise MigrationQueueError(
                f"{family['family_id']} expected {expected_count} matching nodes, found {len(matching)}"
            )
        nodes_by_rule[family["family_id"]] = matching
        for node_id in matching:
            matched_rules[node_id].append(family)

    assignments: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw_entry in sorted(entries, key=lambda item: item["node_id"]):
        entry = _expect_mapping(raw_entry, "baseline entry")
        node_id = _expect_string(entry.get("node_id"), "node_id")
        if node_id in seen_ids:
            raise MigrationQueueError(f"duplicate baseline node ID {node_id}")
        seen_ids.add(node_id)
        matching = matched_rules.get(node_id, [])
        if len(matching) > 1:
            family_names = ", ".join(sorted(item["family_id"] for item in matching))
            raise MigrationQueueError(f"node {node_id} is assigned by multiple confirmed families: {family_names}")

        template_references = entry.get("template_references")
        if not isinstance(template_references, list):
            raise MigrationQueueError(f"node {node_id} template_references must be an array")
        template_paths = sorted(
            {
                _expect_string(reference.get("source_path"), "template source_path")
                for reference in template_references
                if isinstance(reference, dict)
            }
        )
        current = entry.get("current_source")
        if not isinstance(current, dict):
            current = _expect_mapping(entry.get("behavior_source"), "behavior_source")
        module = _expect_string(current.get("module"), "source module")
        source = {
            "ast_sha256": _expect_string(current.get("ast_sha256"), "source ast_sha256"),
            "module": module,
            "path": _expect_string(current.get("path"), "source path"),
            "qualified_class": _expect_string(current.get("qualified_class"), "source qualified_class"),
        }

        if matching:
            family = matching[0]
            family_id: str | None = family["family_id"]
            lane_id = family_id
            assignment_status = "upstream_owner_confirmed"
            assignment_basis = "reviewed_family_rule"
            ownership = family["ownership"]
            exclusive_path = family["exclusive_path"]
            upstream: Mapping[str, Any] | None = family["upstream"]
            agent_scope = {
                "cloud_job_label": family["cloud_job_label"],
                "fixture_prefix": family["fixture_prefix"],
                "r2_test_prefix": family["r2_test_prefix"],
            }
        else:
            family_id = None
            lane_id = _legacy_lane(module)
            assignment_status = "family_review_pending"
            assignment_basis = "legacy_source_module"
            ownership = "unresolved"
            exclusive_path = f"bionodulo/nodes/catalog/migration_lanes/{lane_id}"
            upstream = None
            agent_scope = {
                "cloud_job_label": f"catalog-{lane_id}",
                "fixture_prefix": lane_id,
                "r2_test_prefix": f"catalog-tests/{lane_id}",
            }

        assignments.append(
            {
                "agent_scope": agent_scope,
                "alias_of": entry.get("alias_of"),
                "assignment_basis": assignment_basis,
                "assignment_status": assignment_status,
                "contract_status": "evidence_pending",
                "disposition": "quarantined",
                "exclusive_path": exclusive_path,
                "family_id": family_id,
                "lane_id": lane_id,
                "node_id": node_id,
                "ownership": ownership,
                "priority": "template" if template_paths else "catalog",
                "source": source,
                "template_paths": template_paths,
                "upstream": upstream,
            }
        )

    if len(seen_ids) != EXPECTED_NODE_COUNT:
        raise MigrationQueueError(
            f"migration queue accounted for {len(seen_ids)} nodes, expected {EXPECTED_NODE_COUNT}"
        )

    lanes: dict[str, dict[str, Any]] = {}
    for assignment in assignments:
        lane = lanes.setdefault(
            assignment["lane_id"],
            {
                "assignment_status": assignment["assignment_status"],
                "exclusive_path": assignment["exclusive_path"],
                "lane_id": assignment["lane_id"],
                "node_ids": [],
            },
        )
        if lane["exclusive_path"] != assignment["exclusive_path"]:
            raise MigrationQueueError(f"lane {assignment['lane_id']} resolves to multiple exclusive paths")
        lane["node_ids"].append(assignment["node_id"])

    confirmed = sum(item["assignment_status"] == "upstream_owner_confirmed" for item in assignments)
    preimage: dict[str, Any] = {
        "assignments": assignments,
        "baseline_aggregate_sha256": _expect_string(baseline.get("aggregate_sha256"), "baseline aggregate_sha256"),
        "lanes": [lanes[key] for key in sorted(lanes)],
        "rules_sha256": _sha256(rules),
        "schema_version": 1,
        "summary": {
            "confirmed_family_nodes": confirmed,
            "family_review_pending": EXPECTED_NODE_COUNT - confirmed,
            "quarantined": EXPECTED_NODE_COUNT,
            "stable_node_ids": EXPECTED_NODE_COUNT,
            "template_priority_nodes": sum(item["priority"] == "template" for item in assignments),
        },
    }
    return {**preimage, "queue_sha256": _sha256(preimage)}


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MigrationQueueError(f"cannot read canonical JSON from {path}") from error


def write_or_check(path: Path, payload: bytes, *, check: bool) -> None:
    if check:
        try:
            existing = path.read_bytes()
        except OSError as error:
            raise MigrationQueueError(f"migration queue is missing: {path}") from error
        if existing != payload:
            raise MigrationQueueError(f"migration queue is stale: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        queue = build_queue(_read_json(args.baseline), _read_json(args.rules))
        write_or_check(args.output, canonical_json_bytes(queue), check=args.check)
    except MigrationQueueError as error:
        parser.error(str(error))
    print(
        f"{queue['summary']['stable_node_ids']} nodes queued; "
        f"{queue['summary']['confirmed_family_nodes']} upstream-owner confirmed; "
        f"{queue['summary']['family_review_pending']} pending family review"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
