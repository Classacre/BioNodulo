#!/usr/bin/env python3
"""Build the immutable legacy-node reconciliation ledger from Git objects."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping, Sequence


DEFAULT_ORIGIN_REF = "44c247986f3bcfe8f8d93d0d719a53e4853d0437"
DEFAULT_SPLIT_REF = "a346ded79659d5a10e3056d7cf8ea2bf482606a7"
DEFAULT_BEHAVIOR_REF = "4092ad63a8f60e5b8080711a66428ba191bdc7b7"
DEFAULT_COMPARISON_REF = "ce54d30e4fd07cf26809d99d25bdb267d121e525"
DEFAULT_OUTPUT = Path("bionodulo/nodes/generated/baseline-ledger.json")
EXPECTED_NODE_COUNT = 943
EXPECTED_ALIAS_COUNT = 22
EXPECTED_TEMPLATE_COUNT = 22
EXPECTED_EXAMPLE_COUNT = 1
EXPECTED_TEMPLATE_INSTANCES = 329
EXPECTED_TEMPLATE_EDGES = 291
FORENSIC_RAW_AST_DIGEST = "1b9b2abbd518dc8ed22e53e333a74f37b93fb156266e7a1262495227ebc910c3"
AST_GOLDEN_SHA256 = "e56fe5584149ad41156fd05ffe79dc51a63bf5fe84ba63ad94a6e2aa501ac700"
_AST_GOLDEN_SOURCE = 'class A:\n    NODE_ID = "alpha"\n'
_BUILTIN_PATH = "bionodulo/nodes/builtin"
_ALIAS_METADATA_FIELDS = {
    "CATEGORY",
    "DESCRIPTION",
    "DISPLAY_NAME",
    "NODE_ID",
    "SEARCH_ALIASES",
}
_BLAME_HEADER = re.compile(r"\^?([0-9a-f]{40}) \d+ (\d+) (\d+)")
_DEEPTOOLS_COLLISION = frozenset(
    {
        (
            "bionodulo/nodes/builtin/chip_seq.py",
            "bionodulo.nodes.builtin.chip_seq.DeepToolsBamCoverageNode",
        ),
        (
            "bionodulo/nodes/builtin/epigenomics.py",
            "bionodulo.nodes.builtin.epigenomics.DeepToolsBamCoverageNode",
        ),
    }
)
_ALLOWED_HISTORICAL_COLLISIONS = {"deeptools_bamcoverage": _DEEPTOOLS_COLLISION}
_CURRENT_PATH_REPAIRS = {
    "break_continue": (
        "bionodulo/nodes/builtin/flow_control/break.py",
        "bionodulo/nodes/builtin/flow_control/break_.py",
    ),
    "if_condition": (
        "bionodulo/nodes/builtin/flow_control/if.py",
        "bionodulo/nodes/builtin/flow_control/if_.py",
    ),
    "try_catch": (
        "bionodulo/nodes/builtin/flow_control/try.py",
        "bionodulo/nodes/builtin/flow_control/try_.py",
    ),
    "type_cast": (
        "bionodulo/nodes/builtin/utils/dev/type.py",
        "bionodulo/nodes/builtin/utils/dev/type_.py",
    ),
    "while_loop": (
        "bionodulo/nodes/builtin/flow_control/while.py",
        "bionodulo/nodes/builtin/flow_control/while_.py",
    ),
}
_CURRENT_EMPTY_ANOMALY = {
    "class_name": "FeatureCountsNode",
    "kind": "empty_node_id",
    "module": "bionodulo.nodes.builtin.rna_seq.featurecountsnode",
    "path": "bionodulo/nodes/builtin/rna_seq/featurecountsnode.py",
}


class LedgerError(RuntimeError):
    """Base error for deterministic ledger construction failures."""


class GitCommandError(LedgerError):
    """Raised when an immutable Git-object read fails."""


class DuplicateNodeIdError(LedgerError):
    """Raised when a canonical inventory contains duplicate stable IDs."""


class ReconciliationError(LedgerError):
    """Raised when source inventories do not reconcile exactly."""


@dataclass(frozen=True)
class SourceNode:
    """One literal class-level ``NODE_ID`` declaration and its source identity."""

    node_id: str
    module: str
    class_name: str
    qualified_name: str
    qualified_class: str
    line: int
    node_id_line: int
    raw_class_sha256: str
    ast_sha256: str
    base_symbols: tuple[str, ...]
    metadata_only: bool
    source_path: str = ""
    git_blob: str = ""
    provenance: str | None = None
    blame_commit: str | None = None

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "ast_sha256": self.ast_sha256,
            "class_name": self.class_name,
            "git_blob": self.git_blob,
            "line": self.line,
            "module": self.module,
            "node_id_line": self.node_id_line,
            "path": self.source_path,
            "qualified_class": self.qualified_class,
            "raw_class_sha256": self.raw_class_sha256,
        }
        if self.provenance is not None:
            data["provenance"] = self.provenance
        if self.blame_commit is not None:
            data["blame_commit"] = self.blame_commit
        return data


@dataclass(frozen=True)
class CurrentSourceEvidence:
    """Reproducible class evidence projected onto the repaired source layout."""

    node_id: str
    module: str
    qualified_class: str
    source_path: str
    raw_class_sha256: str
    ast_sha256: str
    comparison_path: str
    comparison_git_blob: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "ast_sha256": self.ast_sha256,
            "comparison_git_blob": self.comparison_git_blob,
            "comparison_path": self.comparison_path,
            "module": self.module,
            "path": self.source_path,
            "qualified_class": self.qualified_class,
            "raw_class_sha256": self.raw_class_sha256,
        }


@dataclass(frozen=True)
class CurrentRepair:
    node_id: str
    comparison_path: str
    current_path: str

    def as_dict(self) -> dict[str, str]:
        return {
            "comparison_path": self.comparison_path,
            "current_path": self.current_path,
            "node_id": self.node_id,
        }


@dataclass(frozen=True)
class CurrentSnapshot:
    kind: str
    base_ref: str
    base_builtin_tree: str
    repairs: tuple[CurrentRepair, ...]
    repair_map_sha256: str
    projected_inventory_sha256: str
    limitations: str
    snapshot_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "base_builtin_tree": self.base_builtin_tree,
            "base_ref": self.base_ref,
            "kind": self.kind,
            "limitations": self.limitations,
            "projected_inventory_sha256": self.projected_inventory_sha256,
            "repair_map": [repair.as_dict() for repair in self.repairs],
            "repair_map_sha256": self.repair_map_sha256,
            "snapshot_sha256": self.snapshot_sha256,
        }


@dataclass(frozen=True)
class AliasResolution:
    """A module-aware static inheritance result for one stable node ID."""

    node_id: str
    status: str = "none"
    alias_of: str | None = None
    semantic_candidates: tuple[str, ...] = ()


@dataclass(frozen=True)
class TemplateReference:
    """One node instance and the edge ports used by its workflow source."""

    source_path: str
    source_blob: str
    kind: str
    instance_id: str
    input_ports: tuple[str, ...]
    output_ports: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "input_ports": list(self.input_ports),
            "instance_id": self.instance_id,
            "kind": self.kind,
            "output_ports": list(self.output_ports),
            "source_blob": self.source_blob,
            "source_path": self.source_path,
        }


@dataclass(frozen=True)
class OriginCollision:
    """All declarations for an ID that collided in the origin snapshot."""

    node_id: str
    declarations: tuple[SourceNode, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "declarations": [item.as_dict() for item in self.declarations],
            "node_id": self.node_id,
        }


@dataclass(frozen=True)
class LedgerEntry:
    """Immutable reconciliation evidence for one canonical stable node ID."""

    node_id: str
    behavior: SourceNode
    origin: SourceNode
    origin_declarations: tuple[SourceNode, ...]
    split_locations: tuple[SourceNode, ...]
    comparison_locations: tuple[SourceNode, ...]
    current: CurrentSourceEvidence | None = None
    alias_of: str | None = None
    semantic_candidates: tuple[str, ...] = ()
    template_references: tuple[TemplateReference, ...] = ()
    status: str = "inventoried"
    disposition: str = "quarantined"
    family: str | None = None
    operation: str | None = None
    contract_version: str | None = None
    evidence_record: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "alias_of": self.alias_of,
            "behavior_source": self.behavior.as_dict(),
            "comparison_locations": [item.as_dict() for item in self.comparison_locations],
            "current_source": self.current.as_dict() if self.current is not None else None,
            "immediate_split_locations": [item.as_dict() for item in self.split_locations],
            "node_id": self.node_id,
            "origin": {
                "declarations": [item.as_dict() for item in self.origin_declarations],
                "selected": self.origin.as_dict(),
            },
            "qualified_class": self.behavior.qualified_class,
            "rebuild": {
                "contract_version": self.contract_version,
                "disposition": self.disposition,
                "evidence_record": self.evidence_record,
                "family": self.family,
                "operation": self.operation,
                "status": self.status,
            },
            "semantic_candidates": list(self.semantic_candidates),
            "template_references": [item.as_dict() for item in self.template_references],
        }


@dataclass(frozen=True)
class Reconciliation:
    """Exact baseline/comparison result plus optional repository evidence."""

    missing_ids: tuple[str, ...] = ()
    added_ids: tuple[str, ...] = ()
    source_drift_ids: tuple[str, ...] = ()
    entries: tuple[LedgerEntry, ...] = ()
    anomalies: tuple[dict[str, Any], ...] = ()
    origin_collisions: tuple[OriginCollision, ...] = ()
    current_snapshot: CurrentSnapshot | None = None
    origin_ref: str = ""
    split_ref: str = ""
    behavior_ref: str = ""
    comparison_ref: str = ""
    behavior_declaration_count: int = 0
    template_count: int = 0
    example_workflow_count: int = 0
    template_instance_count: int = 0
    template_edge_count: int = 0

    @property
    def ok(self) -> bool:
        return not (self.missing_ids or self.added_ids or self.source_drift_ids)


@dataclass(frozen=True)
class _RefInventory:
    ref: str
    declarations: tuple[SourceNode, ...]
    anomalies: tuple[dict[str, Any], ...]
    module_sources: Mapping[str, str]


@dataclass(frozen=True)
class _ClassSymbol:
    module: str
    class_name: str
    qualified_name: str
    node_id: str | None
    base_symbols: tuple[str, ...]
    metadata_only: bool


@dataclass(frozen=True)
class _ModuleAnalysis:
    classes: Mapping[str, _ClassSymbol]
    imported_symbols: Mapping[str, tuple[str, str]]
    imported_modules: Mapping[str, str]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _literal_node_id(class_node: ast.ClassDef) -> tuple[str | None, int]:
    value: str | None = None
    value_line = 0
    for statement in class_node.body:
        expression: ast.expr | None = None
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "NODE_ID" for target in statement.targets
        ):
            expression = statement.value
        elif (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == "NODE_ID"
        ):
            expression = statement.value
        if isinstance(expression, ast.Constant) and isinstance(expression.value, str):
            value = expression.value
            value_line = statement.lineno
    return value, value_line


def _assignment_names(statement: ast.Assign | ast.AnnAssign) -> set[str] | None:
    targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
    names: set[str] = set()
    for target in targets:
        if not isinstance(target, ast.Name):
            return None
        names.add(target.id)
    return names


def _is_metadata_only(class_node: ast.ClassDef) -> bool:
    for statement in class_node.body:
        if isinstance(statement, ast.Pass):
            continue
        if (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        ):
            continue
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            names = _assignment_names(statement)
            if names is not None and names <= _ALIAS_METADATA_FIELDS:
                continue
        return False
    return True


def _class_source_segment(source: str, class_node: ast.ClassDef) -> str:
    segment = ast.get_source_segment(source, class_node)
    if segment is not None:
        return segment
    lines = source.splitlines(keepends=True)
    return "".join(lines[class_node.lineno - 1 : class_node.end_lineno])


def _canonical_ast_value(value: Any) -> Any:
    if isinstance(value, ast.AST):
        result: dict[str, Any] = {"_type": type(value).__name__}
        for field_name, field_value in ast.iter_fields(value):
            if isinstance(field_value, (list, tuple)) and not field_value:
                continue
            result[field_name] = _canonical_ast_value(field_value)
        return result
    if isinstance(value, (list, tuple)):
        return [_canonical_ast_value(item) for item in value]
    if value is Ellipsis:
        return {"_scalar": "ellipsis"}
    if isinstance(value, bytes):
        return {"_scalar": "bytes", "hex": value.hex()}
    if isinstance(value, complex):
        return {
            "_scalar": "complex",
            "imaginary_hex": value.imag.hex(),
            "real_hex": value.real.hex(),
        }
    if isinstance(value, float):
        return {"_scalar": "float", "hex": value.hex()}
    if value is None or isinstance(value, (bool, int, str)):
        return value
    raise TypeError(f"unsupported AST scalar: {type(value).__name__}")


def _canonical_ast_sha256(node: ast.AST) -> str:
    return _sha256(canonical_json_bytes(_canonical_ast_value(node)))


def _canonical_ast_self_test() -> str:
    class_node = ast.parse(_AST_GOLDEN_SOURCE).body[0]
    actual = _canonical_ast_sha256(class_node)
    if actual != AST_GOLDEN_SHA256:
        raise ReconciliationError(
            f"AST canonicalizer self-test failed: actual={actual}, expected={AST_GOLDEN_SHA256}"
        )
    return actual


def extract_nodes(
    source: str,
    module: str,
    *,
    source_path: str = "",
    git_blob: str = "",
) -> tuple[tuple[SourceNode, ...], tuple[dict[str, Any], ...]]:
    """Extract only literal class-level node IDs without importing the source."""

    tree = ast.parse(source, filename=source_path or module)
    found: list[SourceNode] = []
    anomalies: list[dict[str, Any]] = []

    def visit_classes(body: Sequence[ast.stmt], parents: tuple[str, ...] = ()) -> None:
        for statement in body:
            if not isinstance(statement, ast.ClassDef):
                continue
            qualified_name = ".".join((*parents, statement.name))
            node_id, node_id_line = _literal_node_id(statement)
            if node_id is not None:
                if node_id:
                    raw_segment = _class_source_segment(source, statement)
                    found.append(
                        SourceNode(
                            node_id=node_id,
                            module=module,
                            class_name=statement.name,
                            qualified_name=qualified_name,
                            qualified_class=f"{module}.{qualified_name}",
                            line=statement.lineno,
                            node_id_line=node_id_line,
                            raw_class_sha256=_sha256(raw_segment.encode("utf-8")),
                            ast_sha256=_canonical_ast_sha256(statement),
                            base_symbols=tuple(ast.unparse(base) for base in statement.bases),
                            metadata_only=_is_metadata_only(statement),
                            source_path=source_path,
                            git_blob=git_blob,
                        )
                    )
                else:
                    anomaly: dict[str, Any] = {
                        "class_name": statement.name,
                        "kind": "empty_node_id",
                        "module": module,
                    }
                    if source_path:
                        anomaly.update(
                            {
                                "blob": git_blob,
                                "line": statement.lineno,
                                "path": source_path,
                            }
                        )
                    anomalies.append(anomaly)
            visit_classes(statement.body, (*parents, statement.name))

    visit_classes(tree.body)
    found.sort(key=lambda item: (item.line, item.qualified_name, item.node_id))
    anomalies.sort(key=lambda item: (str(item.get("path", "")), int(item.get("line", 0))))
    return tuple(found), tuple(anomalies)


def _module_name(source_path: str) -> str:
    module = source_path.removesuffix(".py").replace("/", ".")
    if module.endswith(".__init__"):
        module = module[: -len(".__init__")]
    return module


def _git(repo: Path, *arguments: str) -> bytes:
    process = subprocess.run(
        ["git", "-C", os.fspath(repo), *arguments],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.returncode:
        stderr = process.stderr.decode("utf-8", errors="replace").strip()
        raise GitCommandError(f"git {' '.join(arguments)} failed: {stderr}")
    return process.stdout


def _tree_blobs(repo: Path, ref: str, *paths: str) -> dict[str, str]:
    output = _git(repo, "ls-tree", "-r", ref, "--", *paths).decode("utf-8")
    blobs: dict[str, str] = {}
    for line in output.splitlines():
        metadata, source_path = line.split("\t", 1)
        _mode, object_type, object_id = metadata.split()
        if object_type == "blob":
            blobs[source_path] = object_id
    return dict(sorted(blobs.items()))


def _load_ref_inventory(repo: Path, ref: str) -> _RefInventory:
    declarations: list[SourceNode] = []
    anomalies: list[dict[str, Any]] = []
    module_sources: dict[str, str] = {}
    for source_path, git_blob in _tree_blobs(repo, ref, _BUILTIN_PATH).items():
        if not source_path.endswith(".py"):
            continue
        source = _git(repo, "show", f"{ref}:{source_path}").decode("utf-8")
        module = _module_name(source_path)
        nodes, module_anomalies = extract_nodes(
            source,
            module,
            source_path=source_path,
            git_blob=git_blob,
        )
        declarations.extend(nodes)
        anomalies.extend(module_anomalies)
        module_sources[module] = source
    declarations.sort(key=lambda item: (item.node_id, item.qualified_class, item.line))
    anomalies.sort(key=lambda item: (str(item.get("path", "")), int(item.get("line", 0))))
    return _RefInventory(
        ref=ref,
        declarations=tuple(declarations),
        anomalies=tuple(anomalies),
        module_sources=module_sources,
    )


def _current_inventory_rows(evidence: Sequence[CurrentSourceEvidence]) -> list[dict[str, str]]:
    return [
        {
            "ast_sha256": item.ast_sha256,
            "module": item.module,
            "node_id": item.node_id,
            "path": item.source_path,
            "qualified_class": item.qualified_class,
            "raw_class_sha256": item.raw_class_sha256,
        }
        for item in sorted(evidence, key=lambda item: item.node_id)
    ]


def _project_current_sources(
    comparison: Sequence[SourceNode],
    *,
    comparison_ref: str,
    base_builtin_tree: str,
) -> tuple[dict[str, CurrentSourceEvidence], CurrentSnapshot]:
    comparison_index = _unique_index(comparison, "comparison")
    repairs = tuple(
        CurrentRepair(node_id=node_id, comparison_path=paths[0], current_path=paths[1])
        for node_id, paths in sorted(_CURRENT_PATH_REPAIRS.items())
    )
    repair_by_id = {repair.node_id: repair for repair in repairs}
    current: dict[str, CurrentSourceEvidence] = {}
    for node_id, source in sorted(comparison_index.items()):
        repair = repair_by_id.get(node_id)
        if repair is not None and source.source_path != repair.comparison_path:
            raise ReconciliationError(
                f"current repair source mismatch for {node_id!r}: "
                f"actual={source.source_path!r}, expected={repair.comparison_path!r}"
            )
        current_path = repair.current_path if repair is not None else source.source_path
        current_module = _module_name(current_path)
        current[node_id] = CurrentSourceEvidence(
            node_id=node_id,
            module=current_module,
            qualified_class=f"{current_module}.{source.qualified_name}",
            source_path=current_path,
            raw_class_sha256=source.raw_class_sha256,
            ast_sha256=source.ast_sha256,
            comparison_path=source.source_path,
            comparison_git_blob=source.git_blob,
        )
    missing_repairs = sorted(set(repair_by_id) - set(comparison_index))
    if missing_repairs:
        raise ReconciliationError(f"current repair map references missing IDs: {missing_repairs}")

    repair_rows = [repair.as_dict() for repair in repairs]
    repair_map_sha256 = _sha256(canonical_json_bytes(repair_rows))
    projected_inventory_sha256 = _sha256(canonical_json_bytes(_current_inventory_rows(tuple(current.values()))))
    limitations = (
        "Forensic path/import repair evidence only; class-body equivalence is not proof of runtime correctness."
    )
    snapshot_identity = {
        "base_builtin_tree": base_builtin_tree,
        "base_ref": comparison_ref,
        "kind": "forensic_path_import_repair_projection",
        "limitations": limitations,
        "projected_inventory_sha256": projected_inventory_sha256,
        "repair_map": repair_rows,
        "repair_map_sha256": repair_map_sha256,
    }
    snapshot = CurrentSnapshot(
        kind="forensic_path_import_repair_projection",
        base_ref=comparison_ref,
        base_builtin_tree=base_builtin_tree,
        repairs=repairs,
        repair_map_sha256=repair_map_sha256,
        projected_inventory_sha256=projected_inventory_sha256,
        limitations=limitations,
        snapshot_sha256=_sha256(canonical_json_bytes(snapshot_identity)),
    )
    return current, snapshot


def _load_worktree_inventory(repo: Path) -> tuple[tuple[SourceNode, ...], tuple[dict[str, Any], ...]]:
    builtin_root = repo / _BUILTIN_PATH
    if not builtin_root.is_dir():
        raise ReconciliationError(f"current source root is missing: {builtin_root}")
    declarations: list[SourceNode] = []
    anomalies: list[dict[str, Any]] = []
    for local_path in sorted(builtin_root.rglob("*.py")):
        source_path = local_path.relative_to(repo).as_posix()
        raw = local_path.read_bytes()
        source = raw.decode("utf-8")
        nodes, module_anomalies = extract_nodes(
            source,
            _module_name(source_path),
            source_path=source_path,
            git_blob="",
        )
        declarations.extend(nodes)
        anomalies.extend(module_anomalies)
    return tuple(declarations), tuple(anomalies)


def validate_current_source(
    repo: Path | str,
    expected: Sequence[CurrentSourceEvidence | SourceNode],
) -> str:
    """Read and fail-closed validate a repaired worktree without importing it."""

    declarations, anomalies = _load_worktree_inventory(Path(repo).resolve())
    actual_index = _unique_index(declarations, "current repaired source")
    anomaly_identities = tuple(
        {
            "class_name": anomaly.get("class_name"),
            "kind": anomaly.get("kind"),
            "module": anomaly.get("module"),
            "path": anomaly.get("path"),
        }
        for anomaly in anomalies
    )
    if anomaly_identities != (_CURRENT_EMPTY_ANOMALY,):
        raise ReconciliationError(f"unexpected current source anomalies: {anomaly_identities}")

    expected_by_id = {item.node_id: item for item in expected}
    if len(expected_by_id) != len(expected):
        raise DuplicateNodeIdError("expected current projection contains duplicate node IDs")
    missing = sorted(set(expected_by_id) - set(actual_index))
    added = sorted(set(actual_index) - set(expected_by_id))
    if missing or added:
        raise ReconciliationError(f"current source ID set differs: missing={missing}, added={added}")

    actual_evidence: list[CurrentSourceEvidence] = []
    for node_id, expected_item in sorted(expected_by_id.items()):
        actual = actual_index[node_id]
        expected_path = expected_item.source_path
        expected_module = expected_item.module
        expected_qualified_class = expected_item.qualified_class
        differences = {
            "path": (actual.source_path, expected_path),
            "module": (actual.module, expected_module),
            "qualified_class": (actual.qualified_class, expected_qualified_class),
            "raw_class_sha256": (actual.raw_class_sha256, expected_item.raw_class_sha256),
            "ast_sha256": (actual.ast_sha256, expected_item.ast_sha256),
        }
        changed = {key: values for key, values in differences.items() if values[0] != values[1]}
        if changed:
            raise ReconciliationError(f"current source drift for {node_id!r}: {changed}")
        actual_evidence.append(
            CurrentSourceEvidence(
                node_id=node_id,
                module=actual.module,
                qualified_class=actual.qualified_class,
                source_path=actual.source_path,
                raw_class_sha256=actual.raw_class_sha256,
                ast_sha256=actual.ast_sha256,
                comparison_path=expected_path,
                comparison_git_blob="",
            )
        )
    return _sha256(canonical_json_bytes(_current_inventory_rows(actual_evidence)))


def _relative_module(current_module: str, level: int, imported_module: str | None) -> str:
    if level == 0:
        return imported_module or ""
    package_parts = current_module.split(".")[:-1]
    keep = len(package_parts) - (level - 1)
    if keep < 0:
        return imported_module or ""
    prefix = package_parts[:keep]
    if imported_module:
        prefix.extend(imported_module.split("."))
    return ".".join(prefix)


def _module_analysis(module: str, source: str, known_modules: set[str]) -> _ModuleAnalysis:
    tree = ast.parse(source, filename=module)
    classes: dict[str, _ClassSymbol] = {}
    imported_symbols: dict[str, tuple[str, str]] = {}
    imported_modules: dict[str, str] = {}
    def collect_classes(body: Sequence[ast.stmt], parents: tuple[str, ...] = ()) -> None:
        for statement in body:
            if not isinstance(statement, ast.ClassDef):
                continue
            qualified_name = ".".join((*parents, statement.name))
            node_id, _line = _literal_node_id(statement)
            classes[qualified_name] = _ClassSymbol(
                module=module,
                class_name=statement.name,
                qualified_name=qualified_name,
                node_id=node_id,
                base_symbols=tuple(ast.unparse(base) for base in statement.bases),
                metadata_only=_is_metadata_only(statement),
            )
            collect_classes(statement.body, (*parents, statement.name))

    collect_classes(tree.body)
    for statement in tree.body:
        if isinstance(statement, ast.Import):
            for name in statement.names:
                local_name = name.asname or name.name
                imported_modules[local_name] = name.name
        elif isinstance(statement, ast.ImportFrom):
            target_module = _relative_module(module, statement.level, statement.module)
            for name in statement.names:
                if name.name == "*":
                    continue
                local_name = name.asname or name.name
                possible_module = ".".join(part for part in (target_module, name.name) if part)
                if possible_module in known_modules:
                    imported_modules[local_name] = possible_module
                else:
                    imported_symbols[local_name] = (target_module, name.name)
    return _ModuleAnalysis(
        classes=classes,
        imported_symbols=imported_symbols,
        imported_modules=imported_modules,
    )


def _resolve_base_symbol(
    module: str,
    qualified_name: str,
    base_symbol: str,
    analyses: Mapping[str, _ModuleAnalysis],
) -> tuple[str, str] | None:
    analysis = analyses[module]
    enclosing_scope = qualified_name.split(".")[:-1]
    for depth in range(len(enclosing_scope), 0, -1):
        lexical_candidate = ".".join((*enclosing_scope[:depth], base_symbol))
        if lexical_candidate in analysis.classes:
            return module, lexical_candidate
    if base_symbol in analysis.classes:
        return module, base_symbol
    if "." not in base_symbol:
        return analysis.imported_symbols.get(base_symbol)
    root, remainder = base_symbol.split(".", 1)
    for local_name, imported_module in sorted(
        analysis.imported_modules.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        prefix = f"{local_name}."
        if base_symbol.startswith(prefix):
            return imported_module, base_symbol.removeprefix(prefix)
    if root in analysis.imported_symbols:
        imported_module, imported_name = analysis.imported_symbols[root]
        return imported_module, f"{imported_name}.{remainder}"
    target_module, _, class_name = base_symbol.rpartition(".")
    if target_module in analyses:
        return target_module, class_name
    return None


def resolve_aliases(module_sources: Mapping[str, str]) -> dict[str, AliasResolution]:
    """Resolve metadata-only inheritance using module-qualified symbol bindings."""

    known_modules = set(module_sources)
    analyses = {
        module: _module_analysis(module, source, known_modules)
        for module, source in sorted(module_sources.items())
    }
    symbols: dict[tuple[str, str], _ClassSymbol] = {}
    for module, analysis in analyses.items():
        for qualified_name, symbol in analysis.classes.items():
            symbols[(module, qualified_name)] = symbol

    resolutions: dict[str, AliasResolution] = {}
    for (module, _class_name), symbol in sorted(symbols.items()):
        if not symbol.node_id:
            continue
        resolution = AliasResolution(node_id=symbol.node_id)
        if symbol.metadata_only:
            for base_symbol in symbol.base_symbols:
                target_key = _resolve_base_symbol(
                    module,
                    symbol.qualified_name,
                    base_symbol,
                    analyses,
                )
                target = symbols.get(target_key) if target_key is not None else None
                if target is None:
                    continue
                if target.node_id:
                    resolution = AliasResolution(
                        node_id=symbol.node_id,
                        status="proven",
                        alias_of=target.node_id,
                    )
                    break
                if target.node_id == "":
                    candidates = tuple(
                        sorted(
                            {
                                other.node_id
                                for other in symbols.values()
                                if other.class_name == target.class_name and other.node_id
                            }
                        )
                    )
                    if candidates:
                        resolution = AliasResolution(
                            node_id=symbol.node_id,
                            status="unresolved",
                            semantic_candidates=candidates,
                        )
                    break
        resolutions[symbol.node_id] = resolution
    return dict(sorted(resolutions.items()))


def _group_declarations(declarations: Sequence[SourceNode]) -> dict[str, tuple[SourceNode, ...]]:
    grouped: defaultdict[str, list[SourceNode]] = defaultdict(list)
    for declaration in declarations:
        grouped[declaration.node_id].append(declaration)
    return {
        node_id: tuple(sorted(items, key=lambda item: (item.source_path, item.line, item.qualified_class)))
        for node_id, items in sorted(grouped.items())
    }


def _unique_index(declarations: Sequence[SourceNode], label: str) -> dict[str, SourceNode]:
    grouped = _group_declarations(declarations)
    duplicates = {node_id: items for node_id, items in grouped.items() if len(items) > 1}
    if duplicates:
        details = ", ".join(
            f"{node_id} ({'; '.join(item.qualified_class for item in items)})"
            for node_id, items in duplicates.items()
        )
        raise DuplicateNodeIdError(f"{label} duplicate NODE_ID declarations: {details}")
    return {node_id: items[0] for node_id, items in grouped.items()}


def _validate_duplicate_allowlist(
    declarations: Sequence[SourceNode],
    label: str,
    allowed: Mapping[str, frozenset[tuple[str, str]]],
) -> None:
    grouped = _group_declarations(declarations)
    duplicates = {node_id: items for node_id, items in grouped.items() if len(items) > 1}
    for node_id in sorted(set(duplicates) | set(allowed)):
        items = duplicates.get(node_id, ())
        actual = frozenset((item.source_path, item.qualified_class) for item in items)
        expected = allowed.get(node_id, frozenset())
        if actual != expected or len(items) != len(expected):
            raise DuplicateNodeIdError(
                f"{label} duplicate allowlist mismatch for {node_id!r}: "
                f"actual={sorted(actual)}, expected={sorted(expected)}"
            )


def reconcile(
    behavior: Sequence[SourceNode],
    comparison: Sequence[SourceNode],
) -> Reconciliation:
    """Compare exact stable-ID sets and normalized class ASTs."""

    behavior_index = _unique_index(behavior, "behavior baseline")
    comparison_index = _unique_index(comparison, "comparison")
    behavior_ids = set(behavior_index)
    comparison_ids = set(comparison_index)
    common_ids = behavior_ids & comparison_ids
    return Reconciliation(
        missing_ids=tuple(sorted(behavior_ids - comparison_ids)),
        added_ids=tuple(sorted(comparison_ids - behavior_ids)),
        source_drift_ids=tuple(
            sorted(
                node_id
                for node_id in common_ids
                if behavior_index[node_id].ast_sha256 != comparison_index[node_id].ast_sha256
            )
        ),
        behavior_declaration_count=len(behavior),
    )


def _blame_commits(repo: Path, ref: str, source_path: str, target_lines: set[int]) -> dict[int, str]:
    if not target_lines:
        return {}
    output = _git(repo, "blame", "--incremental", ref, "--", source_path).decode("utf-8")
    commits: dict[int, str] = {}
    for line in output.splitlines():
        match = _BLAME_HEADER.fullmatch(line)
        if match is None:
            continue
        commit, final_start_text, length_text = match.groups()
        final_start = int(final_start_text)
        final_end = final_start + int(length_text)
        for target_line in target_lines:
            if final_start <= target_line < final_end:
                commits[target_line] = commit
    return commits


def _add_origin_provenance(
    repo: Path,
    ref: str,
    declarations: Sequence[SourceNode],
) -> tuple[SourceNode, ...]:
    by_path: defaultdict[str, list[SourceNode]] = defaultdict(list)
    for declaration in declarations:
        by_path[declaration.source_path].append(declaration)
    enriched: list[SourceNode] = []
    for source_path, items in sorted(by_path.items()):
        commits = _blame_commits(
            repo,
            ref,
            source_path,
            {item.node_id_line for item in items},
        )
        provenance = "monolith" if source_path.endswith("/galaxy_parity.py") else "native"
        enriched.extend(
            replace(
                item,
                provenance=provenance,
                blame_commit=commits.get(item.node_id_line),
            )
            for item in items
        )
    return tuple(sorted(enriched, key=lambda item: (item.node_id, item.source_path, item.line)))


def _select_origin(behavior: SourceNode, declarations: Sequence[SourceNode]) -> SourceNode:
    if not declarations:
        raise ReconciliationError(f"origin snapshot has no declaration for {behavior.node_id!r}")

    def priority(candidate: SourceNode) -> tuple[int, str, int]:
        if candidate.module == behavior.module and candidate.class_name == behavior.class_name:
            rank = 0
        elif candidate.ast_sha256 == behavior.ast_sha256:
            rank = 1
        elif candidate.class_name == behavior.class_name:
            rank = 2
        else:
            rank = 3
        return rank, candidate.source_path, candidate.line

    return min(declarations, key=priority)


def _assert_same_ids(label: str, expected_ids: set[str], declarations: Sequence[SourceNode]) -> None:
    actual_ids = {item.node_id for item in declarations}
    missing = sorted(expected_ids - actual_ids)
    added = sorted(actual_ids - expected_ids)
    if missing or added:
        raise ReconciliationError(f"{label} ID set differs: missing={missing}, added={added}")


def extract_workflow_references(
    document: Mapping[str, Any],
    *,
    source_path: str,
    source_blob: str,
    kind: str,
    valid_node_ids: set[str],
) -> tuple[dict[str, tuple[TemplateReference, ...]], int]:
    """Validate one workflow and return all instance and edge-port evidence."""

    nodes = document.get("nodes")
    edges = document.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ReconciliationError(f"workflow {source_path} must contain node and edge lists")

    instances: dict[str, str] = {}
    for node in nodes:
        if not isinstance(node, dict):
            raise ReconciliationError(f"workflow {source_path} contains a non-object node")
        node_id = node.get("type")
        instance_id = node.get("id")
        if not isinstance(node_id, str) or not isinstance(instance_id, str):
            raise ReconciliationError(f"workflow {source_path} contains an invalid node identity")
        if instance_id in instances:
            raise ReconciliationError(
                f"workflow {source_path} has duplicate workflow instance ID {instance_id!r}"
            )
        if node_id not in valid_node_ids:
            raise ReconciliationError(f"workflow {source_path} references unknown node ID {node_id!r}")
        instances[instance_id] = node_id

    input_ports: defaultdict[str, set[str]] = defaultdict(set)
    output_ports: defaultdict[str, set[str]] = defaultdict(set)
    for edge in edges:
        if not isinstance(edge, dict):
            raise ReconciliationError(f"workflow {source_path} contains a non-object edge")
        source = edge.get("from")
        target = edge.get("to")
        if not isinstance(source, dict) or not isinstance(target, dict):
            raise ReconciliationError(f"workflow {source_path} edge must contain from/to objects")
        source_instance = source.get("node")
        target_instance = target.get("node")
        for endpoint in (source_instance, target_instance):
            if not isinstance(endpoint, str) or endpoint not in instances:
                raise ReconciliationError(
                    f"workflow {source_path} has dangling edge endpoint {endpoint!r}"
                )
        source_port = source.get("output")
        target_port = target.get("input")
        if not isinstance(source_port, str):
            raise ReconciliationError(f"edge from {source_instance!r} has no string output port")
        if not isinstance(target_port, str):
            raise ReconciliationError(f"edge to {target_instance!r} has no string input port")
        output_ports[source_instance].add(source_port)
        input_ports[target_instance].add(target_port)

    references: defaultdict[str, list[TemplateReference]] = defaultdict(list)
    for instance_id, node_id in instances.items():
        references[node_id].append(
            TemplateReference(
                source_path=source_path,
                source_blob=source_blob,
                kind=kind,
                instance_id=instance_id,
                input_ports=tuple(sorted(input_ports[instance_id])),
                output_ports=tuple(sorted(output_ports[instance_id])),
            )
        )
    return {
        node_id: tuple(sorted(items, key=lambda item: item.instance_id))
        for node_id, items in sorted(references.items())
    }, len(edges)


def _template_references(
    repo: Path,
    ref: str,
    valid_node_ids: set[str],
) -> tuple[dict[str, tuple[TemplateReference, ...]], int, int, int, int]:
    blobs = _tree_blobs(repo, ref, "templates", "examples/workflows")
    template_paths = sorted(
        path
        for path in blobs
        if path.startswith("templates/") and path.endswith(".json") and not path.startswith("templates/data/")
    )
    example_paths = sorted(
        path for path in blobs if path.startswith("examples/workflows/") and path.endswith(".json")
    )
    references: defaultdict[str, list[TemplateReference]] = defaultdict(list)
    edge_count = 0
    for kind, paths in (("template", template_paths), ("example", example_paths)):
        for source_path in paths:
            raw = _git(repo, "show", f"{ref}:{source_path}")
            document = json.loads(raw)
            if not isinstance(document, dict):
                raise ReconciliationError(f"workflow {source_path} must contain a JSON object")
            workflow_references, workflow_edge_count = extract_workflow_references(
                document,
                source_path=source_path,
                source_blob=blobs[source_path],
                kind=kind,
                valid_node_ids=valid_node_ids,
            )
            edge_count += workflow_edge_count
            for node_id, items in workflow_references.items():
                references[node_id].extend(items)
    frozen = {
        node_id: tuple(sorted(items, key=lambda item: (item.source_path, item.instance_id)))
        for node_id, items in sorted(references.items())
    }
    instance_count = sum(len(items) for items in frozen.values())
    return frozen, len(template_paths), len(example_paths), instance_count, edge_count


def _raise_reconciliation_differences(result: Reconciliation) -> None:
    if result.ok:
        return
    raise ReconciliationError(
        "behavior/comparison mismatch: "
        f"missing={list(result.missing_ids)}, "
        f"added={list(result.added_ids)}, "
        f"source_semantic_drift={list(result.source_drift_ids)}"
    )


def reconcile_repository(
    repo: Path | str,
    *,
    origin_ref: str = DEFAULT_ORIGIN_REF,
    split_ref: str = DEFAULT_SPLIT_REF,
    behavior_ref: str = DEFAULT_BEHAVIOR_REF,
    comparison_ref: str = DEFAULT_COMPARISON_REF,
) -> Reconciliation:
    """Build and strictly reconcile all Git, AST, alias, and workflow evidence."""

    repo_path = Path(repo).resolve()
    origin_inventory = _load_ref_inventory(repo_path, origin_ref)
    split_inventory = _load_ref_inventory(repo_path, split_ref)
    behavior_inventory = _load_ref_inventory(repo_path, behavior_ref)
    comparison_inventory = _load_ref_inventory(repo_path, comparison_ref)

    result = reconcile(behavior_inventory.declarations, comparison_inventory.declarations)
    _raise_reconciliation_differences(result)
    behavior_index = _unique_index(behavior_inventory.declarations, "behavior baseline")
    if len(behavior_index) != EXPECTED_NODE_COUNT:
        raise ReconciliationError(
            f"behavior baseline must contain exactly {EXPECTED_NODE_COUNT} unique nonempty IDs; "
            f"found {len(behavior_index)}"
        )
    behavior_ids = set(behavior_index)
    _validate_duplicate_allowlist(
        origin_inventory.declarations,
        "origin",
        _ALLOWED_HISTORICAL_COLLISIONS,
    )
    _validate_duplicate_allowlist(
        split_inventory.declarations,
        "immediate split",
        _ALLOWED_HISTORICAL_COLLISIONS,
    )
    _assert_same_ids("origin", behavior_ids, origin_inventory.declarations)
    _assert_same_ids("immediate split", behavior_ids, split_inventory.declarations)

    if len(behavior_inventory.anomalies) != 1 or not (
        behavior_inventory.anomalies[0].get("class_name") == "FeatureCountsNode"
        and behavior_inventory.anomalies[0].get("kind") == "empty_node_id"
    ):
        raise ReconciliationError(
            f"expected only the empty FeatureCountsNode anomaly; found {behavior_inventory.anomalies}"
        )

    origin_declarations = _add_origin_provenance(
        repo_path,
        origin_ref,
        origin_inventory.declarations,
    )
    origin_groups = _group_declarations(origin_declarations)
    split_groups = _group_declarations(split_inventory.declarations)
    comparison_groups = _group_declarations(comparison_inventory.declarations)
    base_builtin_tree = _git(
        repo_path,
        "rev-parse",
        f"{comparison_ref}:{_BUILTIN_PATH}",
    ).decode("ascii").strip()
    current_by_id, current_snapshot = _project_current_sources(
        comparison_inventory.declarations,
        comparison_ref=comparison_ref,
        base_builtin_tree=base_builtin_tree,
    )
    origin_collisions = tuple(
        OriginCollision(node_id=node_id, declarations=items)
        for node_id, items in origin_groups.items()
        if len(items) > 1
    )

    aliases = resolve_aliases(behavior_inventory.module_sources)
    proven_aliases = {node_id: item for node_id, item in aliases.items() if item.alias_of is not None}
    if len(proven_aliases) != EXPECTED_ALIAS_COUNT:
        raise ReconciliationError(
            f"expected {EXPECTED_ALIAS_COUNT} proven aliases; found {len(proven_aliases)}"
        )
    feature_counts = aliases.get("feature_counts")
    if feature_counts is None or feature_counts.alias_of is not None or feature_counts.semantic_candidates != (
        "featurecounts",
    ):
        raise ReconciliationError("feature_counts must remain unresolved with featurecounts as a semantic candidate")

    template_references, template_count, example_count, instance_count, edge_count = _template_references(
        repo_path,
        behavior_ref,
        behavior_ids,
    )
    expected_counts = (
        EXPECTED_TEMPLATE_COUNT,
        EXPECTED_EXAMPLE_COUNT,
        EXPECTED_TEMPLATE_INSTANCES,
        EXPECTED_TEMPLATE_EDGES,
    )
    if (template_count, example_count, instance_count, edge_count) != expected_counts:
        raise ReconciliationError(
            "workflow inventory count differs: "
            f"expected={expected_counts}, actual={(template_count, example_count, instance_count, edge_count)}"
        )

    entries: list[LedgerEntry] = []
    for node_id, behavior in sorted(behavior_index.items()):
        origins = origin_groups.get(node_id, ())
        alias = aliases.get(node_id, AliasResolution(node_id=node_id))
        entries.append(
            LedgerEntry(
                node_id=node_id,
                behavior=behavior,
                origin=_select_origin(behavior, origins),
                origin_declarations=origins,
                split_locations=split_groups.get(node_id, ()),
                comparison_locations=comparison_groups.get(node_id, ()),
                current=current_by_id[node_id],
                alias_of=alias.alias_of,
                semantic_candidates=alias.semantic_candidates,
                template_references=template_references.get(node_id, ()),
            )
        )

    monolith_count = sum(entry.origin.provenance == "monolith" for entry in entries)
    native_count = sum(entry.origin.provenance == "native" for entry in entries)
    if (monolith_count, native_count) != (551, 392):
        raise ReconciliationError(
            f"origin classification differs: expected=(551, 392), actual={(monolith_count, native_count)}"
        )
    unresolved_blame = [entry.node_id for entry in entries if entry.origin.blame_commit is None]
    if unresolved_blame:
        raise ReconciliationError(f"origin blame could not be resolved for IDs: {unresolved_blame}")

    return replace(
        result,
        entries=tuple(entries),
        anomalies=behavior_inventory.anomalies,
        origin_collisions=origin_collisions,
        current_snapshot=current_snapshot,
        origin_ref=origin_ref,
        split_ref=split_ref,
        behavior_ref=behavior_ref,
        comparison_ref=comparison_ref,
        template_count=template_count,
        example_workflow_count=example_count,
        template_instance_count=instance_count,
        template_edge_count=edge_count,
    )


def canonical_json_bytes(value: Any) -> bytes:
    """Encode canonical, newline-terminated JSON bytes."""

    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")


def _inventory_digest(entries: Sequence[LedgerEntry]) -> str:
    rows = [
        {
            "ast_sha256": entry.behavior.ast_sha256,
            "git_blob": entry.behavior.git_blob,
            "line": entry.behavior.line,
            "node_id": entry.node_id,
            "path": entry.behavior.source_path,
            "qualified_class": entry.behavior.qualified_class,
            "raw_class_sha256": entry.behavior.raw_class_sha256,
        }
        for entry in entries
    ]
    return _sha256(canonical_json_bytes(rows))


def ledger_document(result: Reconciliation) -> dict[str, Any]:
    """Return the canonical ledger document before final byte encoding."""

    if not result.ok or len(result.entries) != EXPECTED_NODE_COUNT:
        raise ReconciliationError("only a complete 943-ID reconciliation can be serialized")
    if result.current_snapshot is None or any(entry.current is None for entry in result.entries):
        raise ReconciliationError("current repair projection is incomplete")
    entries = [entry.as_dict() for entry in result.entries]
    monolith_count = sum(entry.origin.provenance == "monolith" for entry in result.entries)
    native_count = sum(entry.origin.provenance == "native" for entry in result.entries)
    proven_aliases = sum(entry.alias_of is not None for entry in result.entries)
    document: dict[str, Any] = {
        "anomalies": list(result.anomalies),
        "canonicalizer": {
            "ast_normalization": "canonical JSON AST; empty sequences omitted",
            "json_encoding": "sort_keys,compact,ascii,newline",
            "name": "bionodulo.catalog-ledger",
            "runtime_compatibility": ["3.11", "3.12", "3.13"],
            "version": 2,
        },
        "digests": {
            "behavior_inventory_sha256": _inventory_digest(result.entries),
            "entries_sha256": _sha256(canonical_json_bytes(entries)),
            "forensic_reference_4092_raw_ast_sha256": FORENSIC_RAW_AST_DIGEST,
        },
        "current_snapshot": result.current_snapshot.as_dict(),
        "entries": entries,
        "origin_collisions": [item.as_dict() for item in result.origin_collisions],
        "refs": {
            "behavior": result.behavior_ref,
            "comparison": result.comparison_ref,
            "immediate_split": result.split_ref,
            "origin": result.origin_ref,
        },
        "schema_version": 1,
        "summary": {
            "added_ids": len(result.added_ids),
            "behavior_declarations": result.behavior_declaration_count,
            "current_sources": sum(entry.current is not None for entry in result.entries),
            "empty_id_anomalies": len(result.anomalies),
            "example_workflows": result.example_workflow_count,
            "missing_ids": len(result.missing_ids),
            "native_origins": native_count,
            "origin_collisions": len(result.origin_collisions),
            "origin_monolith_ids": monolith_count,
            "proven_aliases": proven_aliases,
            "source_semantic_drift": len(result.source_drift_ids),
            "stable_node_ids": len(result.entries),
            "template_instances": result.template_instance_count,
            "template_edges": result.template_edge_count,
            "templates": result.template_count,
        },
    }
    document["aggregate_sha256"] = _sha256(canonical_json_bytes(document))
    return document


def ledger_bytes(result: Reconciliation) -> bytes:
    """Serialize a reconciliation as deterministic canonical bytes."""

    return canonical_json_bytes(ledger_document(result))


def write_or_check(output: Path, expected: bytes, *, check: bool) -> bool:
    """Compare canonical bytes, or replace the output atomically."""

    if check:
        return output.is_file() and output.read_bytes() == expected
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=output.parent,
            prefix=f".{output.name}.",
            delete=False,
        ) as temporary:
            temporary.write(expected)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, output)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return True


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."), help="Git repository root")
    parser.add_argument("--origin-ref", default=DEFAULT_ORIGIN_REF)
    parser.add_argument("--split-ref", default=DEFAULT_SPLIT_REF)
    parser.add_argument("--behavior-ref", default=DEFAULT_BEHAVIOR_REF)
    parser.add_argument("--comparison-ref", default=DEFAULT_COMPARISON_REF)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--validate-current-source",
        type=Path,
        help="read-only validate the projected repaired source tree at this path",
    )
    parser.add_argument("--self-test", action="store_true", help="run the portable AST golden self-test")
    parser.add_argument("--check", action="store_true", help="compare canonical bytes without writing")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.self_test:
        try:
            digest = _canonical_ast_self_test()
        except LedgerError as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(f"AST canonicalizer self-test passed: {digest}")
        return 0
    repo = args.repo.resolve()
    output = args.output if args.output.is_absolute() else repo / args.output
    current_validated = False
    try:
        result = reconcile_repository(
            repo,
            origin_ref=args.origin_ref,
            split_ref=args.split_ref,
            behavior_ref=args.behavior_ref,
            comparison_ref=args.comparison_ref,
        )
        if args.validate_current_source is not None:
            if result.current_snapshot is None:
                raise ReconciliationError("current repair projection is missing")
            projected = tuple(entry.current for entry in result.entries if entry.current is not None)
            if len(projected) != len(result.entries):
                raise ReconciliationError("current repair projection is incomplete")
            observed_digest = validate_current_source(args.validate_current_source, projected)
            if observed_digest != result.current_snapshot.projected_inventory_sha256:
                raise ReconciliationError(
                    "current repaired source digest differs: "
                    f"actual={observed_digest}, "
                    f"expected={result.current_snapshot.projected_inventory_sha256}"
                )
            current_validated = True
        expected = ledger_bytes(result)
        current = write_or_check(output, expected, check=args.check)
    except (LedgerError, OSError, UnicodeError, json.JSONDecodeError, SyntaxError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    detail = (
        f"{len(result.entries)} stable node IDs, {len(result.missing_ids)} missing, "
        f"{len(result.added_ids)} added, {len(result.anomalies)} excluded empty-ID anomaly"
    )
    if current_validated:
        detail += ", current repair projection validated"
    if args.check:
        if not current:
            print(f"STALE: {output} does not match canonical ledger bytes", file=sys.stderr)
            return 1
        print(f"Ledger is current: {detail}")
        return 0
    print(f"Wrote {output}: {detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
