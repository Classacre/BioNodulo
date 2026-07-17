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
from typing import TYPE_CHECKING, Any, Mapping, Sequence
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from scripts import node_migration_ledger_validation as _ledger_validation
    from scripts import node_source_identity as _source_identity
elif __package__:
    from scripts import node_migration_ledger_validation as _ledger_validation
    from scripts import node_source_identity as _source_identity
else:
    import node_migration_ledger_validation as _ledger_validation
    import node_source_identity as _source_identity

EXPECTED_NODE_COUNT = _ledger_validation.EXPECTED_NODE_COUNT
MAX_CANONICAL_JSON_BYTES = _ledger_validation.MAX_CANONICAL_JSON_BYTES
_HEX40_RE = _ledger_validation.HEX40_RE
MigrationQueueError = _ledger_validation.MigrationQueueError
canonical_json_bytes = _ledger_validation.canonical_json_bytes
canonical_json_chunks = _ledger_validation.canonical_json_chunks
_expect_mapping = _ledger_validation.expect_mapping
_expect_string = _ledger_validation.expect_string
_safe_identifier = _ledger_validation.safe_identifier
_validated_baseline = _ledger_validation.validate_baseline


DEFAULT_BASELINE = Path("bionodulo/nodes/generated/baseline-ledger.json")
DEFAULT_RULES = Path("bionodulo/nodes/catalog/family-assignment-rules.json")
DEFAULT_OUTPUT = Path("bionodulo/nodes/generated/migration-queue.json")
_SAFE_PATH_RE = re.compile(r"^[a-z0-9_./-]+$")
_CLOUD_JOB_LABEL_RE = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")
_NODE_ID_PREFIX_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*_$")
_PYTHON_MODULE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
_REPOSITORY_SOURCE_PATH_RE = re.compile(r"^[A-Za-z0-9_./-]+$")
_HOST_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)
_RELEASE_TAG_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._-]{0,127}$")
_LITERAL_PREFIX_SCOPE_FIELDS = ("fixture_prefix", "r2_test_prefix")
_NODE_OWNERSHIP_VALUES = frozenset({"bionodulo_core", "external_tool", "external_library", "external_provider"})
_MAX_NODE_ID_PREFIX_LENGTH = 128
_MAX_PATH_LENGTH = 1024
_MAX_HTTPS_URL_LENGTH = 2048
_MAX_JSON_INPUT_BYTES = MAX_CANONICAL_JSON_BYTES
_MAX_JSON_DEPTH = 64
_MAX_QUEUE_BYTES = MAX_CANONICAL_JSON_BYTES
_UNSAFE_JSON_KEYS = frozenset({"__proto__", "constructor", "prototype"})


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise MigrationQueueError(f"duplicate JSON object member {key!r}")
        if key in _UNSAFE_JSON_KEYS:
            raise MigrationQueueError(f"unsafe JSON object member {key!r}")
        result[key] = value
    return result


def _validate_json_depth(value: object, path: Path) -> None:
    if not isinstance(value, (dict, list)):
        return
    stack: list[tuple[dict[Any, Any] | list[Any], int]] = [(value, 1)]
    while stack:
        current, depth = stack.pop()
        if depth > _MAX_JSON_DEPTH:
            raise MigrationQueueError(f"JSON nesting depth exceeds {_MAX_JSON_DEPTH}: {path}")
        children = current.values() if isinstance(current, dict) else current
        for child in children:
            if isinstance(child, (dict, list)):
                stack.append((child, depth + 1))


def _sha256(value: object) -> str:
    digest = hashlib.sha256()
    for chunk in canonical_json_chunks(value):
        digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _safe_path(value: str, label: str) -> str:
    if len(value) > _MAX_PATH_LENGTH:
        raise MigrationQueueError(f"{label} must not exceed {_MAX_PATH_LENGTH} ASCII characters")
    if (
        _SAFE_PATH_RE.fullmatch(value) is None
        or value.startswith("/")
        or value.endswith("/")
        or "//" in value
        or any(part in ("", ".", "..") for part in value.split("/"))
    ):
        raise MigrationQueueError(f"{label} must be a canonical repository-relative path")
    return value


def _exclusive_path(value: object) -> str:
    path = _safe_path(_expect_string(value, "exclusive_path"), "exclusive_path")
    if not path.startswith("bionodulo/nodes/catalog/"):
        raise MigrationQueueError("exclusive_path must stay under bionodulo/nodes/catalog/")
    return path


def _namespace_prefix(value: object, label: str) -> str:
    prefix = _expect_string(value, label)
    if len(prefix) > _MAX_PATH_LENGTH:
        raise MigrationQueueError(f"{label} must not exceed {_MAX_PATH_LENGTH} ASCII characters")
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
    if len(source) > _MAX_HTTPS_URL_LENGTH:
        raise MigrationQueueError(f"{label} must not exceed {_MAX_HTTPS_URL_LENGTH} ASCII characters")
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


def _source_module(value: object) -> str:
    module = _expect_string(value, "source_module")
    if len(module) > _MAX_PATH_LENGTH:
        raise MigrationQueueError(f"source_module must not exceed {_MAX_PATH_LENGTH} ASCII characters")
    if _PYTHON_MODULE_RE.fullmatch(module) is None:
        raise MigrationQueueError("source_module must be a canonical ASCII Python module")
    return module


def _source_path(value: object) -> str:
    path = _expect_string(value, "source_path")
    if len(path) > _MAX_PATH_LENGTH:
        raise MigrationQueueError(f"source_path must not exceed {_MAX_PATH_LENGTH} ASCII characters")
    if (
        _REPOSITORY_SOURCE_PATH_RE.fullmatch(path) is None
        or path.startswith("/")
        or path.endswith("/")
        or "//" in path
        or any(part in ("", ".", "..") for part in path.split("/"))
        or not path.startswith("bionodulo/nodes/builtin/")
        or not path.endswith(".py")
    ):
        raise MigrationQueueError("source_path must be a canonical repository-relative builtin Python path")
    return path


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
    if len(families) > EXPECTED_NODE_COUNT:
        raise MigrationQueueError(f"confirmed_families must contain at most {EXPECTED_NODE_COUNT} entries")

    result: list[Mapping[str, Any]] = []
    family_ids: set[str] = set()
    for index, raw_family in enumerate(families):
        family = _expect_mapping(raw_family, f"confirmed_families[{index}]")
        expected = {
            "family_id",
            "ownership",
            "node_id_prefix",
            "expected_count",
            "source_module",
            "source_path",
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
        source_path = _source_path(family["source_path"])
        source_module = _source_module(family["source_module"])
        if source_module != _source_identity.module_name(source_path):
            raise MigrationQueueError("source_module must equal the module derived from source_path")
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
                "source_module": source_module,
                "source_path": source_path,
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
        matching_entries = sorted(
            (
                entry
                for entry in entries
                if isinstance(entry, dict)
                and isinstance(entry.get("node_id"), str)
                and entry["node_id"].startswith(prefix)
            ),
            key=lambda entry: entry["node_id"],
        )
        matching = [entry["node_id"] for entry in matching_entries]
        expected_count = family["expected_count"]
        if len(matching) != expected_count:
            raise MigrationQueueError(
                f"{family['family_id']} expected {expected_count} matching nodes, found {len(matching)}"
            )
        expected_module = family["source_module"]
        expected_path = family["source_path"]
        for entry in matching_entries:
            current = entry["current_source"]
            if current["module"] != expected_module or current["path"] != expected_path:
                raise MigrationQueueError(
                    f"confirmed family {family['family_id']} source mismatch for node {entry['node_id']}: "
                    f"expected current_source.module {expected_module!r} and current_source.path {expected_path!r}; "
                    f"found current_source.module {current['module']!r} and current_source.path {current['path']!r}"
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
        with path.open("rb") as source:
            payload = source.read(_MAX_JSON_INPUT_BYTES + 1)
    except OSError as error:
        raise MigrationQueueError(f"cannot read canonical JSON from {path}") from error
    if len(payload) > _MAX_JSON_INPUT_BYTES:
        raise MigrationQueueError(f"JSON input exceeds {_MAX_JSON_INPUT_BYTES} bytes: {path}")
    if payload.startswith(b"\xef\xbb\xbf"):
        raise MigrationQueueError(f"JSON input uses a UTF-8 BOM: {path}")
    try:
        decoded = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise MigrationQueueError(f"JSON input is not valid UTF-8: {path}") from error
    try:
        value = json.loads(decoded, object_pairs_hook=_unique_json_object)
    except ValueError as error:
        raise MigrationQueueError(f"cannot read canonical JSON from {path}") from error
    except RecursionError as error:
        raise MigrationQueueError(f"JSON decoder recursion limit exceeded: {path}") from error
    _validate_json_depth(value, path)
    return value


def write_or_check(path: Path, payload: bytes, *, check: bool) -> None:
    if len(payload) > _MAX_QUEUE_BYTES:
        raise MigrationQueueError(f"migration queue payload exceeds {_MAX_QUEUE_BYTES} bytes")
    if check:
        try:
            with path.open("rb") as source:
                existing = source.read(_MAX_QUEUE_BYTES + 1)
        except OSError as error:
            raise MigrationQueueError(f"migration queue is missing: {path}") from error
        if len(existing) > _MAX_QUEUE_BYTES:
            raise MigrationQueueError(f"existing migration queue exceeds {_MAX_QUEUE_BYTES} bytes: {path}")
        if existing != payload:
            raise MigrationQueueError(f"migration queue is stale: {path}")
        return

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
        directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
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
