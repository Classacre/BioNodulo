#!/usr/bin/env python3
"""Validate the dependency-free canonical ledger consumed by the migration queue."""

from __future__ import annotations

import hashlib
import json
import re
from typing import TYPE_CHECKING, Any, Iterator, Mapping, Sequence

if TYPE_CHECKING:
    from scripts import node_source_identity as _source_identity
elif __package__:
    from scripts import node_source_identity as _source_identity
else:
    import node_source_identity as _source_identity


EXPECTED_NODE_COUNT = 943
EXPECTED_ALIAS_COUNT = 22
EXPECTED_TEMPLATE_COUNT = 22
EXPECTED_EXAMPLE_COUNT = 1
EXPECTED_TEMPLATE_INSTANCES = 329
EXPECTED_TEMPLATE_EDGES = 291
EXPECTED_BASELINE_AGGREGATE_SHA256 = "75643eb83592eccd492d65d3c53b40d45cc6d0e04c2363f5572aeb3492927210"
FORENSIC_RAW_AST_DIGEST = "1b9b2abbd518dc8ed22e53e333a74f37b93fb156266e7a1262495227ebc910c3"
MAX_CANONICAL_JSON_BYTES = 8 * 1024 * 1024
HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")

_SAFE_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,127}$")
_REPOSITORY_PATH_RE = re.compile(r"^[A-Za-z0-9_./-]+$")
_PYTHON_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PYTHON_REFERENCE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$")
_CURRENT_SNAPSHOT_KIND = "forensic_path_import_repair_projection"
CURRENT_SNAPSHOT_LIMITATIONS = (
    "Forensic path/import repair evidence only; class-body equivalence is not proof of runtime correctness."
)
EXPECTED_CANONICALIZER: Mapping[str, Any] = {
    "ast_normalization": "canonical JSON AST; empty sequences omitted",
    "json_encoding": "sort_keys,compact,ascii,newline",
    "name": "bionodulo.catalog-ledger",
    "runtime_compatibility": ["3.11", "3.12", "3.13"],
    "version": 2,
}
BASELINE_FIELDS = frozenset(
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
BASELINE_ENTRY_FIELDS = frozenset(
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
CURRENT_SOURCE_FIELDS = frozenset(
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
TEMPLATE_REFERENCE_FIELDS = frozenset(
    {"input_ports", "instance_id", "kind", "output_ports", "source_blob", "source_path"}
)
SOURCE_NODE_FIELDS = frozenset(
    {
        "ast_sha256",
        "class_name",
        "git_blob",
        "line",
        "module",
        "node_id_line",
        "path",
        "qualified_class",
        "raw_class_sha256",
    }
)
ORIGIN_SOURCE_NODE_FIELDS = SOURCE_NODE_FIELDS | {"blame_commit", "provenance"}
ORIGIN_FIELDS = frozenset({"declarations", "selected"})
REBUILD_FIELDS = frozenset({"contract_version", "disposition", "evidence_record", "family", "operation", "status"})
CURRENT_SNAPSHOT_FIELDS = frozenset(
    {
        "base_builtin_tree",
        "base_ref",
        "kind",
        "limitations",
        "projected_inventory_sha256",
        "repair_map",
        "repair_map_sha256",
        "snapshot_sha256",
    }
)
CURRENT_REPAIR_FIELDS = frozenset({"comparison_path", "current_path", "node_id"})
_DIGEST_FIELDS = frozenset({"behavior_inventory_sha256", "entries_sha256", "forensic_reference_4092_raw_ast_sha256"})
_REF_FIELDS = frozenset({"behavior", "comparison", "immediate_split", "origin"})
_SUMMARY_FIELDS = frozenset(
    {
        "added_ids",
        "behavior_declarations",
        "current_sources",
        "empty_id_anomalies",
        "example_workflows",
        "missing_ids",
        "native_origins",
        "origin_collisions",
        "origin_monolith_ids",
        "proven_aliases",
        "source_semantic_drift",
        "stable_node_ids",
        "template_edges",
        "template_instances",
        "templates",
    }
)
_ANOMALY_FIELDS = frozenset({"blob", "class_name", "kind", "line", "module", "path"})
ORIGIN_COLLISION_FIELDS = frozenset({"declarations", "node_id"})
_CANONICAL_JSON_ENCODER = json.JSONEncoder(
    ensure_ascii=True,
    allow_nan=False,
    separators=(",", ":"),
    sort_keys=True,
)


class MigrationQueueError(RuntimeError):
    """Raised when migration queue inputs are invalid or inconsistent."""


def canonical_json_chunks(value: object) -> Iterator[bytes]:
    size = 0
    for chunk in _CANONICAL_JSON_ENCODER.iterencode(value):
        encoded = chunk.encode("ascii")
        size += len(encoded)
        if size > MAX_CANONICAL_JSON_BYTES:
            raise MigrationQueueError(f"canonical JSON exceeds {MAX_CANONICAL_JSON_BYTES} bytes")
        yield encoded
    size += 1
    if size > MAX_CANONICAL_JSON_BYTES:
        raise MigrationQueueError(f"canonical JSON exceeds {MAX_CANONICAL_JSON_BYTES} bytes")
    yield b"\n"


def canonical_json_bytes(value: object) -> bytes:
    return b"".join(canonical_json_chunks(value))


def expect_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise MigrationQueueError(f"{label} must be an object")
    return value


def expect_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise MigrationQueueError(f"{label} must be a nonempty string")
    return value


def safe_identifier(value: str, label: str) -> str:
    if _SAFE_ID_RE.fullmatch(value) is None:
        raise MigrationQueueError(f"{label} must be a canonical lowercase identifier")
    return value


def _closed_mapping(value: object, label: str, expected_fields: frozenset[str]) -> Mapping[str, Any]:
    mapping = expect_mapping(value, label)
    if set(mapping) != expected_fields:
        raise MigrationQueueError(f"{label} contains unknown or missing fields")
    return mapping


def _hex_digest(value: object, label: str, pattern: re.Pattern[str], length: int) -> str:
    digest = expect_string(value, label)
    if pattern.fullmatch(digest) is None:
        raise MigrationQueueError(f"{label} must be {length} lowercase hexadecimal characters")
    return digest


def _repository_path(value: object, label: str) -> str:
    path = expect_string(value, label)
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
    node_id = expect_string(value, label)
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
    reference = expect_string(value, label)
    if len(reference) > 512 or _PYTHON_REFERENCE_RE.fullmatch(reference) is None:
        raise MigrationQueueError(f"{label} must be a canonical dotted Python reference")
    return reference


def _canonical_port_ids(value: object, label: str) -> list[str]:
    if not isinstance(value, list):
        raise MigrationQueueError(f"{label} must be an array")
    ports = [
        safe_identifier(expect_string(port, f"{label}[{index}]"), f"{label}[{index}]")
        for index, port in enumerate(value)
    ]
    if len(ports) != len(set(ports)) or ports != sorted(ports):
        raise MigrationQueueError(f"{label} must be canonical sorted unique identifiers")
    return ports


def _sha256_hex(value: object) -> str:
    digest = hashlib.sha256()
    for chunk in canonical_json_chunks(value):
        digest.update(chunk)
    return digest.hexdigest()


def _exact_positive_int(value: object, label: str) -> int:
    if type(value) is not int or value < 1:
        raise MigrationQueueError(f"{label} must be a positive exact integer")
    return value


def _validated_source_node(value: object, label: str, *, origin: bool = False) -> dict[str, Any]:
    expected_fields = ORIGIN_SOURCE_NODE_FIELDS if origin else SOURCE_NODE_FIELDS
    source = _closed_mapping(value, label, expected_fields)
    path = _repository_path(source["path"], f"{label} path")
    module = _python_reference(source["module"], f"{label} module")
    class_name = expect_string(source["class_name"], f"{label} class_name")
    qualified_class = _python_reference(source["qualified_class"], f"{label} qualified_class")
    if _PYTHON_NAME_RE.fullmatch(class_name) is None:
        raise MigrationQueueError(f"{label} class_name must be a canonical Python identifier")
    if not path.startswith("bionodulo/nodes/builtin/") or not path.endswith(".py"):
        raise MigrationQueueError(f"{label} path must identify a builtin Python source")
    if module != _source_identity.module_name(path):
        raise MigrationQueueError(f"{label} path must match module")
    try:
        qualified_name = _source_identity.qualified_name_suffix(module, qualified_class)
    except ValueError as error:
        raise MigrationQueueError(f"{label} qualified_class must match module and class_name") from error
    if qualified_name.rsplit(".", 1)[-1] != class_name:
        raise MigrationQueueError(f"{label} qualified_class must match module and class_name")
    line = _exact_positive_int(source["line"], f"{label} line")
    node_id_line = _exact_positive_int(source["node_id_line"], f"{label} node_id_line")
    if node_id_line < line:
        raise MigrationQueueError(f"{label} node_id_line must not precede its class line")
    result: dict[str, Any] = {
        "ast_sha256": _hex_digest(source["ast_sha256"], f"{label} ast_sha256", HEX64_RE, 64),
        "class_name": class_name,
        "git_blob": _hex_digest(source["git_blob"], f"{label} git_blob", HEX40_RE, 40),
        "line": line,
        "module": module,
        "node_id_line": node_id_line,
        "path": path,
        "qualified_class": qualified_class,
        "raw_class_sha256": _hex_digest(source["raw_class_sha256"], f"{label} raw_class_sha256", HEX64_RE, 64),
    }
    if origin:
        provenance = expect_string(source["provenance"], f"{label} provenance")
        if provenance not in {"monolith", "native"}:
            raise MigrationQueueError(f"{label} provenance must be monolith or native")
        result["blame_commit"] = _hex_digest(source["blame_commit"], f"{label} blame_commit", HEX40_RE, 40)
        result["provenance"] = provenance
    return result


def _validated_source_nodes(value: object, label: str, *, origin: bool = False) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise MigrationQueueError(f"{label} must be a nonempty array")
    sources = [_validated_source_node(source, f"{label}[{index}]", origin=origin) for index, source in enumerate(value)]
    keys = [(source["path"], source["qualified_class"], source["line"]) for source in sources]
    if len(keys) != len(set(keys)) or keys != sorted(keys):
        raise MigrationQueueError(f"{label} must use canonical unique source order")
    return sources


def _validated_current_source(value: object, label: str) -> dict[str, str]:
    source = _closed_mapping(value, label, CURRENT_SOURCE_FIELDS)
    path = _repository_path(source["path"], f"{label} path")
    comparison_path = _repository_path(source["comparison_path"], f"{label} comparison_path")
    module = _python_reference(source["module"], f"{label} module")
    qualified_class = _python_reference(source["qualified_class"], f"{label} qualified_class")
    if not path.startswith("bionodulo/nodes/builtin/") or not path.endswith(".py"):
        raise MigrationQueueError(f"{label} path must identify a builtin Python source")
    if not comparison_path.startswith("bionodulo/nodes/builtin/") or not comparison_path.endswith(".py"):
        raise MigrationQueueError(f"{label} comparison_path must identify a builtin Python source")
    if module != "bionodulo.nodes.builtin" and not module.startswith("bionodulo.nodes.builtin."):
        raise MigrationQueueError(f"{label} module must identify a builtin Python module")
    if module != _source_identity.module_name(path):
        raise MigrationQueueError(f"{label} path must match module")
    try:
        _source_identity.qualified_name_suffix(module, qualified_class)
    except ValueError as error:
        raise MigrationQueueError(f"{label} qualified_class must belong to its module") from error
    return {
        "ast_sha256": _hex_digest(source["ast_sha256"], f"{label} ast_sha256", HEX64_RE, 64),
        "comparison_git_blob": _hex_digest(source["comparison_git_blob"], f"{label} comparison_git_blob", HEX40_RE, 40),
        "comparison_path": comparison_path,
        "module": module,
        "path": path,
        "qualified_class": qualified_class,
        "raw_class_sha256": _hex_digest(source["raw_class_sha256"], f"{label} raw_class_sha256", HEX64_RE, 64),
    }


def _validated_template_reference(value: object, label: str) -> dict[str, Any]:
    reference = _closed_mapping(value, label, TEMPLATE_REFERENCE_FIELDS)
    source_path = _repository_path(reference["source_path"], f"{label} source_path")
    if not source_path.endswith(".json") or not source_path.startswith(("templates/", "examples/workflows/")):
        raise MigrationQueueError(f"{label} source_path must identify a template or example JSON document")
    kind = expect_string(reference["kind"], f"{label} kind")
    if kind not in {"template", "example"}:
        raise MigrationQueueError(f"{label} kind must be template or example")
    expected_kind = "template" if source_path.startswith("templates/") else "example"
    if kind != expected_kind:
        raise MigrationQueueError(f"{label} kind must agree with source_path namespace")
    return {
        "input_ports": _canonical_port_ids(reference["input_ports"], f"{label} input_ports"),
        "instance_id": safe_identifier(
            expect_string(reference["instance_id"], f"{label} instance_id"), f"{label} instance_id"
        ),
        "kind": kind,
        "output_ports": _canonical_port_ids(reference["output_ports"], f"{label} output_ports"),
        "source_blob": _hex_digest(reference["source_blob"], f"{label} source_blob", HEX40_RE, 40),
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


def _validated_origin(value: object, label: str) -> dict[str, Any]:
    origin = _closed_mapping(value, label, ORIGIN_FIELDS)
    declarations = _validated_source_nodes(origin["declarations"], f"{label} declarations", origin=True)
    selected = _validated_source_node(origin["selected"], f"{label} selected", origin=True)
    if selected not in declarations:
        raise MigrationQueueError(f"{label} selected source must be one of its declarations")
    return {"declarations": declarations, "selected": selected}


def _origin_priority(source: Mapping[str, Any], behavior: Mapping[str, Any]) -> tuple[int, str, int]:
    if source["module"] == behavior["module"] and source["class_name"] == behavior["class_name"]:
        rank = 0
    elif source["ast_sha256"] == behavior["ast_sha256"]:
        rank = 1
    elif source["class_name"] == behavior["class_name"]:
        rank = 2
    else:
        rank = 3
    return rank, str(source["path"]), int(source["line"])


def _validated_rebuild(value: object, label: str) -> dict[str, Any]:
    rebuild = _closed_mapping(value, label, REBUILD_FIELDS)
    expected = {
        "contract_version": None,
        "disposition": "quarantined",
        "evidence_record": None,
        "family": None,
        "operation": None,
        "status": "inventoried",
    }
    if rebuild != expected:
        raise MigrationQueueError(f"{label} must remain the canonical quarantined inventory state")
    return expected


def _validated_semantic_candidates(value: object, label: str) -> list[str]:
    if not isinstance(value, list):
        raise MigrationQueueError(f"{label} must be an array")
    candidates = [_stable_node_id(item, f"{label}[{index}]") for index, item in enumerate(value)]
    if candidates != sorted(set(candidates)):
        raise MigrationQueueError(f"{label} must use canonical sorted unique node IDs")
    return candidates


def _validated_baseline_entry(value: object, index: int) -> dict[str, Any]:
    label = f"baseline entry {index}"
    entry = expect_mapping(value, label)
    if "current_source" not in entry or not isinstance(entry["current_source"], dict):
        raise MigrationQueueError(f"{label} current_source must be an object")
    if "behavior_source" not in entry or not isinstance(entry["behavior_source"], dict):
        raise MigrationQueueError(f"{label} behavior_source must be an object")
    if set(entry) != BASELINE_ENTRY_FIELDS:
        raise MigrationQueueError(f"{label} contains unknown or missing fields")
    node_id = _stable_node_id(entry["node_id"], f"{label} node_id")
    alias = entry["alias_of"]
    if alias is not None:
        alias = _stable_node_id(alias, f"{label} alias_of")
        if alias == node_id:
            raise MigrationQueueError(f"{label} alias_of must not reference itself")
    behavior = _validated_source_node(entry["behavior_source"], f"{label} behavior_source")
    qualified_class = _python_reference(entry["qualified_class"], f"{label} qualified_class")
    if qualified_class != behavior["qualified_class"]:
        raise MigrationQueueError(f"{label} qualified_class must match behavior_source qualified_class")
    comparison_locations = _validated_source_nodes(entry["comparison_locations"], f"{label} comparison_locations")
    if len(comparison_locations) != 1:
        raise MigrationQueueError(f"{label} comparison_locations must contain exactly one source")
    comparison = comparison_locations[0]
    current = _validated_current_source(entry["current_source"], f"{label} current_source")
    if current["qualified_class"].rsplit(".", 1)[1] != behavior["class_name"]:
        raise MigrationQueueError(f"{label} current_source qualified_class must match behavior class_name")
    current_comparison_pairs = (
        ("ast_sha256", "ast_sha256"),
        ("comparison_git_blob", "git_blob"),
        ("comparison_path", "path"),
        ("raw_class_sha256", "raw_class_sha256"),
    )
    if any(
        current[current_key] != comparison[comparison_key] for current_key, comparison_key in current_comparison_pairs
    ):
        raise MigrationQueueError(f"{label} current_source must match comparison source evidence")
    comparison_qualified_name = _source_identity.qualified_name_suffix(
        comparison["module"], comparison["qualified_class"]
    )
    expected_current_qualified_class = _source_identity.qualified_class(current["module"], comparison_qualified_name)
    if current["qualified_class"] != expected_current_qualified_class:
        raise MigrationQueueError(f"{label} current_source qualified_class must match module and comparison class_name")
    origin = _validated_origin(entry["origin"], f"{label} origin")
    expected_origin = min(origin["declarations"], key=lambda source: _origin_priority(source, behavior))
    if origin["selected"] != expected_origin:
        raise MigrationQueueError(f"{label} origin selected source must match canonical origin priority")
    return {
        "alias_of": alias,
        "behavior_source": behavior,
        "comparison_locations": comparison_locations,
        "current_source": current,
        "immediate_split_locations": _validated_source_nodes(
            entry["immediate_split_locations"], f"{label} immediate_split_locations"
        ),
        "node_id": node_id,
        "origin": origin,
        "qualified_class": qualified_class,
        "rebuild": _validated_rebuild(entry["rebuild"], f"{label} rebuild"),
        "semantic_candidates": _validated_semantic_candidates(
            entry["semantic_candidates"], f"{label} semantic_candidates"
        ),
        "template_references": _validated_template_references(
            entry["template_references"], f"{label} template_references"
        ),
    }


def _validated_anomalies(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise MigrationQueueError("baseline anomalies must be an array")
    anomalies: list[dict[str, Any]] = []
    for index, raw_anomaly in enumerate(value):
        label = f"baseline anomaly {index}"
        anomaly = _closed_mapping(raw_anomaly, label, _ANOMALY_FIELDS)
        path = _repository_path(anomaly["path"], f"{label} path")
        module = _python_reference(anomaly["module"], f"{label} module")
        class_name = expect_string(anomaly["class_name"], f"{label} class_name")
        if not path.startswith("bionodulo/nodes/builtin/") or not path.endswith(".py"):
            raise MigrationQueueError(f"{label} path must identify a builtin Python source")
        if module != _source_identity.module_name(path):
            raise MigrationQueueError(f"{label} path must match module")
        if _PYTHON_NAME_RE.fullmatch(class_name) is None:
            raise MigrationQueueError(f"{label} class_name must be a canonical Python identifier")
        kind = expect_string(anomaly["kind"], f"{label} kind")
        if kind != "empty_node_id":
            raise MigrationQueueError(f"{label} kind must be empty_node_id")
        anomalies.append(
            {
                "blob": _hex_digest(anomaly["blob"], f"{label} blob", HEX40_RE, 40),
                "class_name": class_name,
                "kind": kind,
                "line": _exact_positive_int(anomaly["line"], f"{label} line"),
                "module": module,
                "path": path,
            }
        )
    keys = [(item["path"], item["line"]) for item in anomalies]
    if keys != sorted(keys):
        raise MigrationQueueError("baseline anomalies must use canonical order")
    if len(anomalies) != 1 or anomalies[0]["class_name"] != "FeatureCountsNode":
        raise MigrationQueueError("baseline anomalies must contain only the empty FeatureCountsNode anomaly")
    return anomalies


def _validated_origin_collisions(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise MigrationQueueError("baseline origin_collisions must be an array")
    collisions: list[dict[str, Any]] = []
    for index, raw_collision in enumerate(value):
        label = f"baseline origin collision {index}"
        collision = _closed_mapping(raw_collision, label, ORIGIN_COLLISION_FIELDS)
        collisions.append(
            {
                "declarations": _validated_source_nodes(
                    collision["declarations"], f"{label} declarations", origin=True
                ),
                "node_id": _stable_node_id(collision["node_id"], f"{label} node_id"),
            }
        )
    node_ids = [item["node_id"] for item in collisions]
    if node_ids != sorted(set(node_ids)):
        raise MigrationQueueError("baseline origin_collisions must use canonical unique node_id order")
    return collisions


def _validated_refs(value: object) -> dict[str, str]:
    refs = _closed_mapping(value, "baseline refs", _REF_FIELDS)
    return {key: _hex_digest(refs[key], f"baseline refs {key}", HEX40_RE, 40) for key in sorted(refs)}


def _validated_current_snapshot(value: object) -> dict[str, Any]:
    snapshot = _closed_mapping(value, "baseline current_snapshot", CURRENT_SNAPSHOT_FIELDS)
    kind = expect_string(snapshot["kind"], "baseline current_snapshot kind")
    limitations = expect_string(snapshot["limitations"], "baseline current_snapshot limitations")
    if kind != _CURRENT_SNAPSHOT_KIND:
        raise MigrationQueueError("baseline current_snapshot kind is not canonical")
    if limitations != CURRENT_SNAPSHOT_LIMITATIONS:
        raise MigrationQueueError("baseline current_snapshot limitations are not canonical")
    raw_repairs = snapshot["repair_map"]
    if not isinstance(raw_repairs, list):
        raise MigrationQueueError("baseline current_snapshot repair_map must be an array")
    repairs: list[dict[str, str]] = []
    for index, raw_repair in enumerate(raw_repairs):
        label = f"baseline current_snapshot repair_map[{index}]"
        repair = _closed_mapping(raw_repair, label, CURRENT_REPAIR_FIELDS)
        repairs.append(
            {
                "comparison_path": _repository_path(repair["comparison_path"], f"{label} comparison_path"),
                "current_path": _repository_path(repair["current_path"], f"{label} current_path"),
                "node_id": _stable_node_id(repair["node_id"], f"{label} node_id"),
            }
        )
    repair_ids = [item["node_id"] for item in repairs]
    if repair_ids != sorted(set(repair_ids)):
        raise MigrationQueueError("baseline current_snapshot repair_map must use canonical unique node_id order")
    return {
        "base_builtin_tree": _hex_digest(
            snapshot["base_builtin_tree"], "baseline current_snapshot base_builtin_tree", HEX40_RE, 40
        ),
        "base_ref": _hex_digest(snapshot["base_ref"], "baseline current_snapshot base_ref", HEX40_RE, 40),
        "kind": kind,
        "limitations": limitations,
        "projected_inventory_sha256": _hex_digest(
            snapshot["projected_inventory_sha256"],
            "baseline current_snapshot projected_inventory_sha256",
            HEX64_RE,
            64,
        ),
        "repair_map": repairs,
        "repair_map_sha256": _hex_digest(
            snapshot["repair_map_sha256"], "baseline current_snapshot repair_map_sha256", HEX64_RE, 64
        ),
        "snapshot_sha256": _hex_digest(
            snapshot["snapshot_sha256"], "baseline current_snapshot snapshot_sha256", HEX64_RE, 64
        ),
    }


def _validated_digests(value: object) -> dict[str, str]:
    digests = _closed_mapping(value, "baseline digests", _DIGEST_FIELDS)
    return {key: _hex_digest(digests[key], f"baseline digests {key}", HEX64_RE, 64) for key in sorted(digests)}


def _validated_summary(value: object) -> dict[str, int]:
    summary = _closed_mapping(value, "baseline summary", _SUMMARY_FIELDS)
    result: dict[str, int] = {}
    for key in sorted(summary):
        count = summary[key]
        if type(count) is not int or count < 0:
            raise MigrationQueueError(f"baseline summary {key} must be a nonnegative exact integer")
        result[key] = count
    return result


def _verify_aggregate(baseline: Mapping[str, Any]) -> str:
    if "aggregate_sha256" not in baseline:
        raise MigrationQueueError("baseline aggregate_sha256 is missing")
    aggregate = baseline["aggregate_sha256"]
    if not isinstance(aggregate, str) or HEX64_RE.fullmatch(aggregate) is None:
        raise MigrationQueueError("baseline aggregate_sha256 must be 64 lowercase hexadecimal characters")
    preimage = dict(baseline)
    del preimage["aggregate_sha256"]
    try:
        actual = _sha256_hex(preimage)
    except (TypeError, ValueError) as error:
        raise MigrationQueueError("baseline ledger cannot be encoded as canonical JSON") from error
    if actual != aggregate:
        raise MigrationQueueError("baseline aggregate_sha256 mismatch")
    return aggregate


def _validate_aliases(entries: Sequence[Mapping[str, Any]]) -> None:
    entries_by_id = {str(entry["node_id"]): entry for entry in entries}
    node_ids = set(entries_by_id)
    aliases = {str(entry["node_id"]): entry["alias_of"] for entry in entries}
    for node_id, alias in aliases.items():
        if alias is not None and alias not in node_ids:
            raise MigrationQueueError(f"node {node_id} alias_of references unknown node {alias}")
        for candidate in entries_by_id[node_id]["semantic_candidates"]:
            if candidate not in node_ids:
                raise MigrationQueueError(f"node {node_id} semantic_candidates references unknown node {candidate}")
            if candidate == node_id:
                raise MigrationQueueError(f"node {node_id} semantic_candidates must not reference itself")
        seen: set[str] = set()
        current: str | None = node_id
        while current is not None:
            if current in seen:
                raise MigrationQueueError(f"node {node_id} alias_of participates in a cycle")
            seen.add(current)
            next_alias = aliases.get(current)
            current = str(next_alias) if next_alias is not None else None


def _verify_snapshot(
    entries: Sequence[Mapping[str, Any]],
    refs: Mapping[str, str],
    snapshot: Mapping[str, Any],
) -> None:
    if snapshot["base_ref"] != refs["comparison"]:
        raise MigrationQueueError("baseline current_snapshot base_ref must match comparison ref")
    expected_repairs = [
        {
            "comparison_path": entry["current_source"]["comparison_path"],
            "current_path": entry["current_source"]["path"],
            "node_id": entry["node_id"],
        }
        for entry in entries
        if entry["current_source"]["path"] != entry["current_source"]["comparison_path"]
    ]
    if snapshot["repair_map"] != expected_repairs:
        raise MigrationQueueError("baseline current_snapshot repair_map must match current source repairs")
    if snapshot["repair_map_sha256"] != _sha256_hex(snapshot["repair_map"]):
        raise MigrationQueueError("baseline current_snapshot repair_map_sha256 mismatch")
    current_inventory = [
        {
            "ast_sha256": entry["current_source"]["ast_sha256"],
            "module": entry["current_source"]["module"],
            "node_id": entry["node_id"],
            "path": entry["current_source"]["path"],
            "qualified_class": entry["current_source"]["qualified_class"],
            "raw_class_sha256": entry["current_source"]["raw_class_sha256"],
        }
        for entry in entries
    ]
    if snapshot["projected_inventory_sha256"] != _sha256_hex(current_inventory):
        raise MigrationQueueError("baseline current_snapshot projected_inventory_sha256 mismatch")
    snapshot_identity = dict(snapshot)
    del snapshot_identity["snapshot_sha256"]
    if snapshot["snapshot_sha256"] != _sha256_hex(snapshot_identity):
        raise MigrationQueueError("baseline current_snapshot snapshot_sha256 mismatch")


def _verify_digests(entries: list[dict[str, Any]], digests: Mapping[str, str]) -> None:
    if digests["entries_sha256"] != _sha256_hex(entries):
        raise MigrationQueueError("baseline digests entries_sha256 mismatch")
    behavior_inventory = [
        {
            "ast_sha256": entry["behavior_source"]["ast_sha256"],
            "git_blob": entry["behavior_source"]["git_blob"],
            "line": entry["behavior_source"]["line"],
            "node_id": entry["node_id"],
            "path": entry["behavior_source"]["path"],
            "qualified_class": entry["behavior_source"]["qualified_class"],
            "raw_class_sha256": entry["behavior_source"]["raw_class_sha256"],
        }
        for entry in entries
    ]
    if digests["behavior_inventory_sha256"] != _sha256_hex(behavior_inventory):
        raise MigrationQueueError("baseline digests behavior_inventory_sha256 mismatch")
    if digests["forensic_reference_4092_raw_ast_sha256"] != FORENSIC_RAW_AST_DIGEST:
        raise MigrationQueueError("baseline forensic reference digest is not canonical")


def _verify_summary(
    entries: list[dict[str, Any]],
    anomalies: list[dict[str, Any]],
    collisions: list[dict[str, Any]],
    summary: Mapping[str, int],
) -> None:
    template_references = [reference for entry in entries for reference in entry["template_references"]]
    workflow_instances = [(item["source_path"], item["instance_id"]) for item in template_references]
    if len(workflow_instances) != len(set(workflow_instances)):
        raise MigrationQueueError("baseline template references contain duplicate workflow instances")
    source_blobs: dict[str, str] = {}
    for reference in template_references:
        previous = source_blobs.setdefault(reference["source_path"], reference["source_blob"])
        if previous != reference["source_blob"]:
            raise MigrationQueueError("baseline template source path resolves to multiple blobs")
    semantic_drift = sum(
        entry["behavior_source"]["ast_sha256"] != entry["comparison_locations"][0]["ast_sha256"] for entry in entries
    )
    if semantic_drift:
        raise MigrationQueueError("baseline entries contain source semantic drift")
    proven_aliases = sum(entry["alias_of"] is not None for entry in entries)
    template_paths = {item["source_path"] for item in template_references if item["kind"] == "template"}
    example_paths = {item["source_path"] for item in template_references if item["kind"] == "example"}
    if proven_aliases != EXPECTED_ALIAS_COUNT:
        raise MigrationQueueError(f"baseline must contain exactly {EXPECTED_ALIAS_COUNT} proven aliases")
    if len(template_paths) != EXPECTED_TEMPLATE_COUNT:
        raise MigrationQueueError(f"baseline must contain exactly {EXPECTED_TEMPLATE_COUNT} templates")
    if len(example_paths) != EXPECTED_EXAMPLE_COUNT:
        raise MigrationQueueError(f"baseline must contain exactly {EXPECTED_EXAMPLE_COUNT} example workflows")
    if len(template_references) != EXPECTED_TEMPLATE_INSTANCES:
        raise MigrationQueueError(f"baseline must contain exactly {EXPECTED_TEMPLATE_INSTANCES} template instances")
    expected_summary = {
        "added_ids": 0,
        "behavior_declarations": len(entries),
        "current_sources": len(entries),
        "empty_id_anomalies": len(anomalies),
        "example_workflows": len(example_paths),
        "missing_ids": 0,
        "native_origins": sum(entry["origin"]["selected"]["provenance"] == "native" for entry in entries),
        "origin_collisions": len(collisions),
        "origin_monolith_ids": sum(entry["origin"]["selected"]["provenance"] == "monolith" for entry in entries),
        "proven_aliases": proven_aliases,
        "source_semantic_drift": semantic_drift,
        "stable_node_ids": len(entries),
        "template_edges": EXPECTED_TEMPLATE_EDGES,
        "template_instances": len(template_references),
        "templates": len(template_paths),
    }
    for key, expected in expected_summary.items():
        if summary[key] != expected:
            raise MigrationQueueError(f"baseline summary {key} mismatch: expected {expected}, found {summary[key]}")


def validate_baseline(baseline: Mapping[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    """Validate and normalize every canonical ledger record and derived invariant."""

    aggregate = _verify_aggregate(baseline)
    if set(baseline) != BASELINE_FIELDS:
        raise MigrationQueueError("baseline ledger contains unknown or missing fields")
    if type(baseline["schema_version"]) is not int or baseline["schema_version"] != 1:
        raise MigrationQueueError("baseline schema_version must be exact integer 1")
    canonicalizer = _closed_mapping(
        baseline["canonicalizer"], "baseline canonicalizer", frozenset(EXPECTED_CANONICALIZER)
    )
    if canonicalizer != EXPECTED_CANONICALIZER:
        raise MigrationQueueError("baseline canonicalizer policy is not supported")
    refs = _validated_refs(baseline["refs"])
    snapshot = _validated_current_snapshot(baseline["current_snapshot"])
    digests = _validated_digests(baseline["digests"])
    summary = _validated_summary(baseline["summary"])
    raw_entries = baseline["entries"]
    if not isinstance(raw_entries, list) or len(raw_entries) != EXPECTED_NODE_COUNT:
        raise MigrationQueueError(f"baseline ledger must contain exactly {EXPECTED_NODE_COUNT} entries")
    entries = [_validated_baseline_entry(entry, index) for index, entry in enumerate(raw_entries)]
    node_ids = [entry["node_id"] for entry in entries]
    if node_ids != sorted(node_ids):
        raise MigrationQueueError("baseline entries must use canonical node_id order")
    if len(node_ids) != len(set(node_ids)):
        raise MigrationQueueError("baseline entries contain duplicate node IDs")
    _validate_aliases(entries)
    anomalies = _validated_anomalies(baseline["anomalies"])
    collisions = _validated_origin_collisions(baseline["origin_collisions"])
    expected_collisions = [
        {"declarations": entry["origin"]["declarations"], "node_id": entry["node_id"]}
        for entry in entries
        if len(entry["origin"]["declarations"]) > 1
    ]
    if collisions != expected_collisions:
        raise MigrationQueueError("baseline origin_collisions mismatch entry origin evidence")
    _verify_snapshot(entries, refs, snapshot)
    _verify_digests(entries, digests)
    _verify_summary(entries, anomalies, collisions, summary)
    if aggregate != EXPECTED_BASELINE_AGGREGATE_SHA256:
        raise MigrationQueueError("baseline aggregate_sha256 does not match the immutable baseline authority")
    return aggregate, entries
