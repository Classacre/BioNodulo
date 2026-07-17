#!/usr/bin/env python3
"""Build the quarantined node-family work queue from the immutable ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit


DEFAULT_BASELINE = Path("bionodulo/nodes/generated/baseline-ledger.json")
DEFAULT_RULES = Path("bionodulo/nodes/catalog/family-assignment-rules.json")
DEFAULT_OUTPUT = Path("bionodulo/nodes/generated/migration-queue.json")
EXPECTED_NODE_COUNT = 943
_SAFE_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,127}$")
_SAFE_PATH_RE = re.compile(r"^[a-z0-9_./-]+$")
_REPOSITORY_PATH_RE = re.compile(r"^[A-Za-z0-9_./-]+$")
_CLOUD_JOB_LABEL_RE = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")
_NODE_ID_PREFIX_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*_$")
_PYTHON_REFERENCE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$")
_HOST_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)
_HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_RELEASE_TAG_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._-]{0,127}$")
_LITERAL_PREFIX_SCOPE_FIELDS = ("fixture_prefix", "r2_test_prefix")
_NODE_OWNERSHIP_VALUES = frozenset({"bionodulo_core", "external_tool", "external_library", "external_provider"})
_MAX_NODE_ID_PREFIX_LENGTH = 128
_MAX_QUEUE_BYTES = 8 * 1024 * 1024
_BASELINE_FIELDS = frozenset(
    {
        "aggregate_sha256",
        "anomalies",
        "canonicalizer",
        "current_snapshot",
        "digests",
        "entries",
        "origin_collisions",
        "refs",
        "schema_version",
        "summary",
    }
)
_BASELINE_ENTRY_FIELDS = frozenset(
    {
        "alias_of",
        "behavior_source",
        "comparison_locations",
        "current_source",
        "immediate_split_locations",
        "node_id",
        "origin",
        "qualified_class",
        "rebuild",
        "semantic_candidates",
        "template_references",
    }
)
_CURRENT_SOURCE_FIELDS = frozenset(
    {
        "ast_sha256",
        "comparison_git_blob",
        "comparison_path",
        "module",
        "path",
        "qualified_class",
        "raw_class_sha256",
    }
)
_TEMPLATE_REFERENCE_FIELDS = frozenset(
    {"input_ports", "instance_id", "kind", "output_ports", "source_blob", "source_path"}
)


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


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise MigrationQueueError(f"duplicate JSON object member {key!r}")
        result[key] = value
    return result


def _sha256(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _verify_baseline_aggregate(baseline: Mapping[str, Any]) -> str:
    if "aggregate_sha256" not in baseline:
        raise MigrationQueueError("baseline aggregate_sha256 is missing")
    aggregate = baseline["aggregate_sha256"]
    if not isinstance(aggregate, str) or _HEX64_RE.fullmatch(aggregate) is None:
        raise MigrationQueueError("baseline aggregate_sha256 must be 64 lowercase hexadecimal characters")
    preimage = dict(baseline)
    del preimage["aggregate_sha256"]
    try:
        actual = hashlib.sha256(canonical_json_bytes(preimage)).hexdigest()
    except (TypeError, ValueError) as error:
        raise MigrationQueueError("baseline ledger cannot be encoded as canonical JSON") from error
    if actual != aggregate:
        raise MigrationQueueError("baseline aggregate_sha256 mismatch")
    return aggregate


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


def _closed_mapping(value: object, label: str, expected_fields: frozenset[str]) -> Mapping[str, Any]:
    mapping = _expect_mapping(value, label)
    if set(mapping) != expected_fields:
        raise MigrationQueueError(f"{label} contains unknown or missing fields")
    return mapping


def _hex_digest(value: object, label: str, pattern: re.Pattern[str], length: int) -> str:
    digest = _expect_string(value, label)
    if pattern.fullmatch(digest) is None:
        raise MigrationQueueError(f"{label} must be {length} lowercase hexadecimal characters")
    return digest


def _repository_path(value: object, label: str) -> str:
    path = _expect_string(value, label)
    if (
        len(path) > 512
        or _REPOSITORY_PATH_RE.fullmatch(path) is None
        or path.startswith("/")
        or path.endswith("/")
        or "//" in path
        or any(part in ("", ".", "..") for part in path.split("/"))
    ):
        raise MigrationQueueError(f"{label} must be a canonical repository-relative path")
    return path


def _stable_node_id(value: object, label: str) -> str:
    node_id = _expect_string(value, label)
    try:
        node_id.encode("ascii")
    except UnicodeEncodeError as error:
        raise MigrationQueueError(f"{label} must be a safe stable identifier") from error
    if (
        len(node_id) > 128
        or node_id != node_id.strip()
        or "/" in node_id
        or "\\" in node_id
        or any(ord(character) < 32 or ord(character) == 127 for character in node_id)
    ):
        raise MigrationQueueError(f"{label} must be a safe stable identifier")
    return node_id


def _python_reference(value: object, label: str) -> str:
    reference = _expect_string(value, label)
    if len(reference) > 512 or _PYTHON_REFERENCE_RE.fullmatch(reference) is None:
        raise MigrationQueueError(f"{label} must be a canonical dotted Python reference")
    return reference


def _canonical_port_ids(value: object, label: str) -> list[str]:
    if not isinstance(value, list):
        raise MigrationQueueError(f"{label} must be an array")
    ports = [
        _safe_identifier(_expect_string(port, f"{label}[{index}]"), f"{label}[{index}]")
        for index, port in enumerate(value)
    ]
    if len(ports) != len(set(ports)) or ports != sorted(ports):
        raise MigrationQueueError(f"{label} must be canonical sorted unique identifiers")
    return ports


def _validated_current_source(value: object, label: str) -> dict[str, str]:
    source = _closed_mapping(value, label, _CURRENT_SOURCE_FIELDS)
    path = _repository_path(source["path"], f"{label} path")
    comparison_path = _repository_path(source["comparison_path"], f"{label} comparison_path")
    module = _python_reference(source["module"], f"{label} module")
    qualified_class = _python_reference(source["qualified_class"], f"{label} qualified_class")
    if not path.startswith("bionodulo/nodes/builtin/") or not path.endswith(".py"):
        raise MigrationQueueError(f"{label} path must identify a builtin Python source")
    if not comparison_path.startswith("bionodulo/nodes/builtin/") or not comparison_path.endswith(".py"):
        raise MigrationQueueError(f"{label} comparison_path must identify a builtin Python source")
    if not module.startswith("bionodulo.nodes.builtin."):
        raise MigrationQueueError(f"{label} module must identify a builtin Python module")
    if not qualified_class.startswith(module + "."):
        raise MigrationQueueError(f"{label} qualified_class must belong to its module")
    return {
        "ast_sha256": _hex_digest(source["ast_sha256"], f"{label} ast_sha256", _HEX64_RE, 64),
        "comparison_git_blob": _hex_digest(
            source["comparison_git_blob"],
            f"{label} comparison_git_blob",
            _HEX40_RE,
            40,
        ),
        "comparison_path": comparison_path,
        "module": module,
        "path": path,
        "qualified_class": qualified_class,
        "raw_class_sha256": _hex_digest(
            source["raw_class_sha256"],
            f"{label} raw_class_sha256",
            _HEX64_RE,
            64,
        ),
    }


def _validated_template_reference(value: object, label: str) -> dict[str, Any]:
    reference = _closed_mapping(value, label, _TEMPLATE_REFERENCE_FIELDS)
    source_path = _repository_path(reference["source_path"], f"{label} source_path")
    if not source_path.endswith(".json") or not source_path.startswith(("templates/", "examples/workflows/")):
        raise MigrationQueueError(f"{label} source_path must identify a template or example JSON document")
    kind = _expect_string(reference["kind"], f"{label} kind")
    if kind not in {"template", "example"}:
        raise MigrationQueueError(f"{label} kind must be template or example")
    expected_kind = "template" if source_path.startswith("templates/") else "example"
    if kind != expected_kind:
        raise MigrationQueueError(f"{label} kind must agree with source_path namespace")
    return {
        "input_ports": _canonical_port_ids(reference["input_ports"], f"{label} input_ports"),
        "instance_id": _safe_identifier(
            _expect_string(reference["instance_id"], f"{label} instance_id"),
            f"{label} instance_id",
        ),
        "kind": kind,
        "output_ports": _canonical_port_ids(reference["output_ports"], f"{label} output_ports"),
        "source_blob": _hex_digest(reference["source_blob"], f"{label} source_blob", _HEX40_RE, 40),
        "source_path": source_path,
    }


def _validated_template_references(value: object, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise MigrationQueueError(f"{label} must be an array")
    references = [
        _validated_template_reference(reference, f"template reference {index}") for index, reference in enumerate(value)
    ]
    keys = [(reference["source_path"], reference["instance_id"]) for reference in references]
    if len(keys) != len(set(keys)):
        raise MigrationQueueError(f"{label} must contain unique workflow instances")
    if keys != sorted(keys):
        raise MigrationQueueError(f"{label} must use canonical order")
    return references


def _validated_baseline_entry(value: object, index: int) -> dict[str, Any]:
    label = f"baseline entry {index}"
    entry = _expect_mapping(value, label)
    if "current_source" not in entry or not isinstance(entry["current_source"], dict):
        raise MigrationQueueError(f"{label} current_source must be an object")
    if set(entry) != _BASELINE_ENTRY_FIELDS:
        raise MigrationQueueError(f"{label} contains unknown or missing fields")
    alias = entry["alias_of"]
    if alias is not None:
        alias = _stable_node_id(alias, f"{label} alias_of")
    _python_reference(entry["qualified_class"], f"{label} qualified_class")
    return {
        "alias_of": alias,
        "current_source": _validated_current_source(entry["current_source"], f"{label} current_source"),
        "node_id": _stable_node_id(entry["node_id"], f"{label} node_id"),
        "template_references": _validated_template_references(
            entry["template_references"],
            f"{label} template_references",
        ),
    }


def _validated_baseline(baseline: Mapping[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    aggregate = _verify_baseline_aggregate(baseline)
    if set(baseline) != _BASELINE_FIELDS:
        raise MigrationQueueError("baseline ledger contains unknown or missing fields")
    if type(baseline["schema_version"]) is not int or baseline["schema_version"] != 1:
        raise MigrationQueueError("baseline schema_version must be exact integer 1")
    raw_entries = baseline["entries"]
    if not isinstance(raw_entries, list) or len(raw_entries) != EXPECTED_NODE_COUNT:
        raise MigrationQueueError(f"baseline ledger must contain exactly {EXPECTED_NODE_COUNT} entries")
    entries = [_validated_baseline_entry(entry, index) for index, entry in enumerate(raw_entries)]
    node_ids = [entry["node_id"] for entry in entries]
    if node_ids != sorted(node_ids):
        raise MigrationQueueError("baseline entries must use canonical node_id order")
    if len(node_ids) != len(set(node_ids)):
        raise MigrationQueueError("baseline entries contain duplicate node IDs")
    node_id_set = set(node_ids)
    for entry in entries:
        alias = entry["alias_of"]
        if alias is not None and alias not in node_id_set:
            raise MigrationQueueError(f"node {entry['node_id']} alias_of references unknown node {alias}")
    return aggregate, entries


def _exclusive_path(value: object) -> str:
    path = _safe_path(_expect_string(value, "exclusive_path"), "exclusive_path")
    if not path.startswith("bionodulo/nodes/catalog/"):
        raise MigrationQueueError("exclusive_path must stay under bionodulo/nodes/catalog/")
    return path


def _namespace_prefix(value: object, label: str) -> str:
    prefix = _expect_string(value, label)
    if not prefix.endswith("/"):
        raise MigrationQueueError(f"{label} must be a canonical relative namespace root ending in /")
    try:
        _safe_path(prefix[:-1], label)
    except MigrationQueueError as error:
        raise MigrationQueueError(f"{label} must be a canonical relative namespace root ending in /") from error
    return prefix


def _cloud_job_label(value: object) -> str:
    label = _expect_string(value, "cloud_job_label")
    if len(label) > 128 or _CLOUD_JOB_LABEL_RE.fullmatch(label) is None:
        raise MigrationQueueError("cloud_job_label must be a canonical lowercase job label")
    return label


def _scope_values_overlap(left: str, right: str) -> bool:
    left_parts = left.split("/")
    right_parts = right.split("/")
    shared = min(len(left_parts), len(right_parts))
    return left_parts[:shared] == right_parts[:shared]


def _validate_scope_collisions(
    scopes: Sequence[tuple[str, Mapping[str, str]]],
) -> None:
    for field in ("exclusive_path", *_LITERAL_PREFIX_SCOPE_FIELDS):
        for index, (left_id, left_scope) in enumerate(scopes):
            for right_id, right_scope in scopes[index + 1 :]:
                left = left_scope[field]
                right = right_scope[field]
                if field == "exclusive_path":
                    overlaps = _scope_values_overlap(left, right)
                else:
                    overlaps = left.startswith(right) or right.startswith(left)
                if overlaps:
                    raise MigrationQueueError(f"{field} overlap between {left_id} ({left}) and {right_id} ({right})")

    cloud_labels: dict[str, str] = {}
    for owner_id, scope in scopes:
        label = scope["cloud_job_label"]
        previous = cloud_labels.get(label)
        if previous is not None:
            raise MigrationQueueError(f"cloud_job_label collision between {previous} and {owner_id}: {label}")
        cloud_labels[label] = owner_id


def _https_url(value: object, label: str) -> str:
    source = _expect_string(value, label)
    try:
        source.encode("ascii")
        if (
            "%" in source
            or "\\" in source
            or any(ord(character) <= 32 or ord(character) == 127 for character in source)
        ):
            raise ValueError("noncanonical URL characters")
        if not source.startswith("https://") or "?" in source or "#" in source:
            raise ValueError("noncanonical HTTPS spelling")
        parsed = urlsplit(source)
        port = parsed.port
        if parsed.scheme != "https" or not parsed.netloc or parsed.hostname is None:
            raise ValueError("missing HTTPS hostname")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("URL user information is forbidden")
        raw_host = parsed.netloc.rsplit(":", 1)[0] if port is not None else parsed.netloc
        if raw_host != parsed.hostname or _HOST_RE.fullmatch(raw_host) is None:
            raise ValueError("noncanonical DNS hostname")
        if port is not None and not 1 <= port <= 65535:
            raise ValueError("port outside valid range")
        if port == 443:
            raise ValueError("default HTTPS port must be omitted")
        canonical_netloc = parsed.hostname
        if port is not None:
            raw_port = parsed.netloc.rsplit(":", 1)[1]
            if raw_port != str(port):
                raise ValueError("noncanonical decimal port")
            canonical_netloc = f"{canonical_netloc}:{port}"
        if parsed.netloc != canonical_netloc:
            raise ValueError("noncanonical authority")
        if not parsed.path or parsed.path == "/":
            raise ValueError("missing resource path")
        segments = parsed.path.split("/")
        if "" in segments[1:-1] or any(segment in (".", "..") for segment in segments):
            raise ValueError("noncanonical path segments")
        if source != f"https://{canonical_netloc}{parsed.path}":
            raise ValueError("URL does not use its canonical raw spelling")
    except (UnicodeEncodeError, ValueError) as error:
        raise MigrationQueueError(f"{label} must be a canonical HTTPS URL") from error
    return source


def _node_ownership(value: object) -> str:
    if not isinstance(value, str) or value not in _NODE_OWNERSHIP_VALUES:
        raise MigrationQueueError("ownership must be one of the closed NodeOwnership values")
    return value


def _node_id_prefix(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) > _MAX_NODE_ID_PREFIX_LENGTH
        or _NODE_ID_PREFIX_RE.fullmatch(value) is None
    ):
        raise MigrationQueueError("node_id_prefix must be a canonical lowercase machine-ID prefix ending in _")
    return value


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


def _legacy_lanes(modules: set[str]) -> dict[str, str]:
    modules_by_lane: dict[str, list[str]] = defaultdict(list)
    for module in sorted(modules):
        modules_by_lane[_legacy_lane(module)].append(module)

    result: dict[str, str] = {}
    used_lane_ids: set[str] = set()
    for base_lane in sorted(modules_by_lane):
        grouped_modules = modules_by_lane[base_lane]
        for index, module in enumerate(grouped_modules):
            lane_id = base_lane
            if len(grouped_modules) > 1:
                digest = hashlib.sha256(module.encode("utf-8")).hexdigest()[:12]
                lane_id = f"{base_lane}_{digest}"
                if len(lane_id) > 128:
                    lane_id = f"{base_lane[:115].rstrip('_')}_{digest}"
                if lane_id in used_lane_ids:
                    lane_id = f"{lane_id[:123].rstrip('_')}_{index + 1}"
            lane_id = _safe_identifier(lane_id, "legacy lane_id")
            if lane_id in used_lane_ids:
                raise MigrationQueueError(f"cannot derive unique legacy lane for module {module!r}")
            used_lane_ids.add(lane_id)
            result[module] = lane_id
    return result


def _validated_scope(exclusive_path: object, agent_scope_value: object) -> dict[str, str]:
    agent_scope = _expect_mapping(agent_scope_value, "agent_scope")
    expected = {"cloud_job_label", "fixture_prefix", "r2_test_prefix"}
    if set(agent_scope) != expected:
        raise MigrationQueueError("agent_scope contains unknown or missing fields")
    return {
        "cloud_job_label": _cloud_job_label(agent_scope["cloud_job_label"]),
        "exclusive_path": _exclusive_path(exclusive_path),
        "fixture_prefix": _namespace_prefix(agent_scope["fixture_prefix"], "fixture_prefix"),
        "r2_test_prefix": _namespace_prefix(agent_scope["r2_test_prefix"], "r2_test_prefix"),
    }


def _validated_rules(rules: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    if set(rules) != {"schema_version", "confirmed_families"}:
        raise MigrationQueueError("assignment rules contain unknown or missing fields")
    if type(rules["schema_version"]) is not int or rules["schema_version"] != 1:
        raise MigrationQueueError("assignment rules schema_version must be exact integer 1")
    families = rules["confirmed_families"]
    if not isinstance(families, list):
        raise MigrationQueueError("confirmed_families must be an array")

    result: list[Mapping[str, Any]] = []
    family_ids: set[str] = set()
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
        expected_count = family["expected_count"]
        if type(expected_count) is not int or not 1 <= expected_count <= EXPECTED_NODE_COUNT:
            raise MigrationQueueError(f"expected_count must be an exact integer between 1 and {EXPECTED_NODE_COUNT}")
        scope = {
            "cloud_job_label": _cloud_job_label(family["cloud_job_label"]),
            "exclusive_path": _exclusive_path(family["exclusive_path"]),
            "fixture_prefix": _namespace_prefix(family["fixture_prefix"], "fixture_prefix"),
            "r2_test_prefix": _namespace_prefix(family["r2_test_prefix"], "r2_test_prefix"),
        }
        result.append(
            {
                **family,
                **scope,
                "expected_count": expected_count,
                "node_id_prefix": _node_id_prefix(family["node_id_prefix"]),
                "ownership": _node_ownership(family["ownership"]),
                "upstream": _validated_upstream(family["upstream"]),
            }
        )
    _validate_scope_collisions([(str(family["family_id"]), family) for family in result])
    return tuple(result)


def build_queue(
    baseline_value: object,
    rules_value: object,
) -> dict[str, Any]:
    baseline = _expect_mapping(baseline_value, "baseline ledger")
    baseline_aggregate_sha256, entries = _validated_baseline(baseline)
    rules = _expect_mapping(rules_value, "assignment rules")
    families = _validated_rules(rules)

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
        for node_id in matching:
            matched_rules[node_id].append(family)

    provisional_modules: set[str] = set()
    for entry in entries:
        node_id = entry["node_id"]
        if matched_rules.get(node_id):
            continue
        provisional_modules.add(entry["current_source"]["module"])
    legacy_lanes = _legacy_lanes(provisional_modules)

    assignments: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for entry in entries:
        node_id = entry["node_id"]
        if node_id in seen_ids:
            raise MigrationQueueError(f"duplicate baseline node ID {node_id}")
        seen_ids.add(node_id)
        matching = matched_rules.get(node_id, [])
        if len(matching) > 1:
            family_names = ", ".join(sorted(item["family_id"] for item in matching))
            raise MigrationQueueError(f"node {node_id} is assigned by multiple confirmed families: {family_names}")

        template_paths = sorted({reference["source_path"] for reference in entry["template_references"]})
        current = entry["current_source"]
        module = current["module"]
        source = {
            "ast_sha256": current["ast_sha256"],
            "module": module,
            "path": current["path"],
            "qualified_class": current["qualified_class"],
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
            lane_id = legacy_lanes[module]
            assignment_status = "family_review_pending"
            assignment_basis = "legacy_source_module"
            ownership = "unresolved"
            exclusive_path = f"bionodulo/nodes/catalog/migration_lanes/{lane_id}"
            upstream = None
            agent_scope = {
                "cloud_job_label": f"catalog-{lane_id}",
                "fixture_prefix": f"{lane_id}/",
                "r2_test_prefix": f"catalog-tests/{lane_id}/",
            }

        assignments.append(
            {
                "agent_scope": agent_scope,
                "alias_of": entry["alias_of"],
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
                "agent_scope": dict(assignment["agent_scope"]),
                "assignment_status": assignment["assignment_status"],
                "exclusive_path": assignment["exclusive_path"],
                "lane_id": assignment["lane_id"],
                "node_ids": [],
            },
        )
        if lane["exclusive_path"] != assignment["exclusive_path"] or lane["agent_scope"] != assignment["agent_scope"]:
            raise MigrationQueueError(f"lane {assignment['lane_id']} resolves to multiple isolation scopes")
        if lane["assignment_status"] != assignment["assignment_status"]:
            raise MigrationQueueError(f"lane {assignment['lane_id']} resolves to multiple assignment statuses")
        lane["node_ids"].append(assignment["node_id"])

    lane_scopes = [
        (lane_id, _validated_scope(lane["exclusive_path"], lane["agent_scope"]))
        for lane_id, lane in sorted(lanes.items())
    ]
    _validate_scope_collisions(lane_scopes)

    confirmed = sum(item["assignment_status"] == "upstream_owner_confirmed" for item in assignments)
    preimage: dict[str, Any] = {
        "assignments": assignments,
        "baseline_aggregate_sha256": baseline_aggregate_sha256,
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
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_json_object,
        )
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
    if len(payload) > _MAX_QUEUE_BYTES:
        raise MigrationQueueError(f"migration queue payload exceeds {_MAX_QUEUE_BYTES} bytes")

    temporary_path: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            output_mode = stat.S_IMODE(path.stat().st_mode)
        except FileNotFoundError:
            output_mode = 0o644
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            os.fchmod(temporary.fileno(), output_mode)
            if temporary.write(payload) != len(payload):
                raise OSError("short migration queue write")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    except OSError as error:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise MigrationQueueError(f"cannot atomically write migration queue: {path}") from error


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
