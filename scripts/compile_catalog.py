#!/usr/bin/env python3
"""Compile the typed catalog and the operational legacy compatibility catalog.

The migration ledger is forensic evidence and is intentionally read-only here.
The strict v2 projections still compile exactly the seven typed Samtools
modules.  In parallel, the operational projection exposes every existing
one-node-per-file ``BaseNode`` class through an explicitly marked
``legacy_compatible`` adapter lane.  This makes the classes selectable and
resolvable without pretending that their tool, cloud, and workflow evidence
has been completed.

Usage::

    .venv/bin/python scripts/compile_catalog.py --write
    .venv/bin/python scripts/compile_catalog.py --check
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import re
import stat
import sys
import tempfile
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
GENERATED_DIR = REPO_ROOT / "bionodulo" / "nodes" / "generated"
BASELINE_LEDGER = GENERATED_DIR / "baseline-ledger.json"
LEGACY_NODE_INDEX = REPO_ROOT / "bionodulo" / "nodes" / "node_index.json"
LEGACY_NODE_METADATA = REPO_ROOT / "bionodulo" / "nodes" / "node_metadata.json"
BASELINE_NODE_COUNT = 943
# Nodes written AFTER the forensic ledger was sealed. The ledger reconciles
# historical git refs, so a class authored today exists in none of them and can
# never be proven that way -- but the catalog still has to grow. Listing an ID
# here is the explicit, reviewable act of adding a node: it must still resolve
# its execution factory (see _blocked_reason), so `availability` stays a proof.
# Keep the ledger itself at exactly BASELINE_NODE_COUNT; it is forensic history,
# not a live inventory.
POST_BASELINE_NODE_IDS: frozenset[str] = frozenset(
    {
        "snpeff_build",
        "krona_build_taxonomy",
        "metaphlan_build_index",
        # Cell Ranger is BYOL (403 to any unattended fetch, redistributable
        # by no conda channel), so single-cell counting needs an open node.
        "starsolo_count",
    }
)
EXPECTED_NODE_COUNT = BASELINE_NODE_COUNT + len(POST_BASELINE_NODE_IDS)
SAMTOOLS_MODULES: tuple[str, ...] = (
    "bionodulo.nodes.catalog.tools.samtools.view",
    "bionodulo.nodes.catalog.tools.samtools.collate",
    "bionodulo.nodes.catalog.tools.samtools.fixmate",
    "bionodulo.nodes.catalog.tools.samtools.sort",
    "bionodulo.nodes.catalog.tools.samtools.markdup",
    "bionodulo.nodes.catalog.tools.samtools.index",
    "bionodulo.nodes.catalog.tools.samtools.flagstat",
)

OUTPUT_NAMES: tuple[str, ...] = (
    "catalog.runtime.json",
    "catalog.ui.json",
    "compatibility.json",
    "node-index.json",
    "catalog.lock.json",
    "catalog.promotion.json",
    "catalog.operational.json",
)

LEGACY_RUNTIME_ADAPTER = "base_node_v1"
LEGACY_STATUS = "legacy_compatible"
LEGACY_PENDING_STATUS = "evidence_pending"


class CatalogBuildError(RuntimeError):
    """Raised when promotion inputs or generated outputs are inconsistent."""


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=True,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("ascii")
            + b"\n"
        )
    except (TypeError, ValueError) as error:
        raise CatalogBuildError(f"projection is not canonical JSON: {error}") from error


def _sha256(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _read_baseline() -> tuple[dict[str, Any], str]:
    try:
        content = BASELINE_LEDGER.read_bytes()
        document = json.loads(content)
    except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CatalogBuildError(f"cannot read baseline ledger {BASELINE_LEDGER}: {error}") from error
    if not isinstance(document, dict):
        raise CatalogBuildError("baseline ledger must be a JSON object")
    entries = document.get("entries")
    if not isinstance(entries, list) or len(entries) != BASELINE_NODE_COUNT:
        actual = len(entries) if isinstance(entries, list) else "missing"
        raise CatalogBuildError(f"baseline ledger must contain exactly {BASELINE_NODE_COUNT} entries (found {actual})")
    aggregate = document.get("aggregate_sha256")
    if not isinstance(aggregate, str) or len(aggregate) != 64:
        raise CatalogBuildError("baseline ledger aggregate_sha256 is missing or malformed")
    return document, _sha256(content)


def _read_json_mapping(path: Path, *, label: str) -> tuple[dict[str, Any], str]:
    try:
        content = path.read_bytes()
        document = json.loads(content)
    except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CatalogBuildError(f"cannot read {label} {path}: {error}") from error
    if not isinstance(document, dict):
        raise CatalogBuildError(f"{label} must be a JSON object")
    return document, _sha256(content)


def _json_pointer_token(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _legacy_factory(
    node_id: str,
    module_name: object,
    metadata: Mapping[str, Any],
) -> tuple[str, str, str]:
    if not isinstance(module_name, str) or not module_name:
        raise CatalogBuildError(f"legacy node {node_id!r} has an invalid index module")
    python_class = metadata.get("python_class")
    if not isinstance(python_class, str) or not python_class:
        raise CatalogBuildError(f"legacy node {node_id!r} has no python_class metadata")
    class_module, separator, symbol = python_class.rpartition(".")
    if not separator or not class_module or not symbol:
        raise CatalogBuildError(f"legacy node {node_id!r} has malformed python_class metadata")
    if class_module != module_name:
        raise CatalogBuildError(
            f"legacy node {node_id!r} index/metadata module mismatch: {module_name!r} != {class_module!r}"
        )
    if not symbol.isidentifier():
        raise CatalogBuildError(f"legacy node {node_id!r} has an invalid class symbol {symbol!r}")
    return class_module, symbol, f"{class_module}:{symbol}"


_MAX_REASON_LENGTH = 300


def _sanitise_reason(reason: str) -> str:
    """Strip build-host detail out of a reason that ships to clients.

    catalog.operational.json is served to the editor, so an import traceback
    must not carry the build machine's directory layout into it — the same leak
    that put absolute asset paths into node_metadata.json.
    """
    cleaned = reason.replace(str(REPO_ROOT), "<repo>")
    # Any surviving absolute path is from outside the repo (a site-packages or
    # home directory) and is pure build-host detail.
    cleaned = re.sub(r"(?:/[\w.\-+]+){2,}/?", "<path>", cleaned)
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > _MAX_REASON_LENGTH:
        cleaned = cleaned[: _MAX_REASON_LENGTH - 1] + "…"
    return cleaned


def _blocked_reason(
    module_name: str,
    symbol: str,
    importer: Callable[[str], Any],
) -> str | None:
    """Resolve a legacy execution factory; return ``None`` when it is usable.

    The legacy lane is derived from the AST baseline ledger, which proves a
    class was *written*, not that it can be *imported*.  Resolving the factory
    here is what turns ``availability`` from an assertion into a proof and
    keeps unloadable nodes out of the palette.
    """
    try:
        module = importer(module_name)
    except Exception as error:  # noqa: BLE001 - any import failure blocks the node
        return _sanitise_reason(f"{type(error).__name__}: {error}")
    if module is None:
        raise CatalogBuildError(f"legacy importer returned None for module {module_name!r}")
    if not hasattr(module, symbol):
        return f"module {module_name} does not define {symbol}"
    return None


def _build_operational_document(
    compiled: Any,
    *,
    legacy_importer: Callable[[str], Any] | None = None,
) -> dict[str, Any]:
    """Project all focused legacy classes without manufacturing typed evidence."""

    importer = legacy_importer or importlib.import_module
    baseline, baseline_bytes_digest = _read_baseline()
    legacy_index, legacy_index_digest = _read_json_mapping(
        LEGACY_NODE_INDEX,
        label="legacy node index",
    )
    legacy_metadata, legacy_metadata_digest = _read_json_mapping(
        LEGACY_NODE_METADATA,
        label="legacy node metadata",
    )
    baseline_entries = baseline.get("entries")
    if not isinstance(baseline_entries, list):
        raise CatalogBuildError("baseline ledger entries are missing")
    baseline_by_id = {
        entry.get("node_id"): entry
        for entry in baseline_entries
        if isinstance(entry, dict) and isinstance(entry.get("node_id"), str)
    }
    baseline_ids = set(baseline_by_id)
    if len(baseline_ids) != BASELINE_NODE_COUNT:
        raise CatalogBuildError(f"baseline ledger must contain {BASELINE_NODE_COUNT} unique node IDs")
    # The ledger is sealed history; the live catalog is the ledger plus the
    # explicitly declared post-baseline IDs. Anything else in the index is drift.
    overlap = sorted(POST_BASELINE_NODE_IDS & baseline_ids)
    if overlap:
        raise CatalogBuildError(
            f"post-baseline IDs must not already exist in the forensic ledger: {overlap}"
        )
    expected_ids = baseline_ids | set(POST_BASELINE_NODE_IDS)
    if len(expected_ids) != EXPECTED_NODE_COUNT:
        raise CatalogBuildError(f"catalog must contain exactly {EXPECTED_NODE_COUNT} node IDs")
    if set(legacy_index) != expected_ids:
        unexpected = sorted(set(legacy_index) - expected_ids)
        absent = sorted(expected_ids - set(legacy_index))
        raise CatalogBuildError(
            "legacy node index IDs differ from the forensic baseline "
            f"(undeclared: {unexpected}; absent: {absent}). Declare a genuinely new "
            "node in POST_BASELINE_NODE_IDS."
        )
    if set(legacy_metadata) != expected_ids:
        raise CatalogBuildError("legacy node metadata IDs differ from the forensic baseline")

    typed_by_machine = {spec.identity.machine_id: spec for spec in compiled.specs}
    missing_typed = sorted(set(typed_by_machine) - expected_ids)
    if missing_typed:
        raise CatalogBuildError(f"typed catalog machine IDs are absent from the legacy catalog: {missing_typed}")
    typed_stable_ids = {spec.identity.stable_id for spec in compiled.specs}
    collisions = sorted(typed_stable_ids & expected_ids)
    if collisions:
        raise CatalogBuildError(f"typed stable IDs collide with legacy workflow IDs: {collisions}")

    operational_nodes: dict[str, dict[str, Any]] = {}
    qualified_classes: dict[str, str] = {}
    verification_counts: Counter[str] = Counter()
    availability_counts: Counter[str] = Counter()

    for node_id in sorted(expected_ids):
        metadata = legacy_metadata[node_id]
        if not isinstance(metadata, dict):
            raise CatalogBuildError(f"legacy node metadata for {node_id!r} must be an object")
        if metadata.get("name") != node_id:
            raise CatalogBuildError(f"legacy node {node_id!r} metadata name does not match its ID")
        module_name, symbol, execution_factory = _legacy_factory(
            node_id,
            legacy_index[node_id],
            metadata,
        )
        previous = qualified_classes.get(execution_factory)
        if previous is not None:
            raise CatalogBuildError(
                f"legacy execution factory {execution_factory} is shared by {previous!r} and {node_id!r}"
            )
        qualified_classes[execution_factory] = node_id

        typed_spec = typed_by_machine.get(node_id)
        typed_entry = None
        aliases: list[str] = []
        verification_status = LEGACY_PENDING_STATUS
        if typed_spec is not None:
            typed_entry = compiled.nodes[typed_spec.identity.stable_id]
            aliases.append(typed_spec.identity.stable_id)
            verification_status = str(typed_entry["status"])
        verification_counts[verification_status] += 1

        blocked_reason = _blocked_reason(module_name, symbol, importer)
        availability = "blocked" if blocked_reason is not None else "active"
        availability_counts[availability] += 1

        node_metadata_digest = _sha256(_canonical_json_bytes(metadata))
        # Post-baseline nodes have no ledger entry by construction: the ledger
        # records classes that existed at seal time. Absence here is expected
        # and carries no alias history.
        baseline_entry = baseline_by_id.get(node_id, {})
        legacy_alias_of = baseline_entry.get("alias_of")
        common: dict[str, Any] = {
            "aliases": aliases,
            "availability": availability,
            "execution_factory": execution_factory,
            "implementation_status": LEGACY_STATUS,
            "legacy_execution_factory": execution_factory,
            "machine_id": node_id,
            "metadata_digest": node_metadata_digest,
            "module": module_name,
            "node_id": node_id,
            "runtime_adapter": LEGACY_RUNTIME_ADAPTER,
            "status": LEGACY_STATUS,
            "symbol": symbol,
            "verification_status": verification_status,
        }
        if blocked_reason is not None:
            common["blocked_reason"] = blocked_reason
        if isinstance(legacy_alias_of, str):
            common["legacy_alias_of"] = legacy_alias_of
        if typed_spec is not None and typed_entry is not None:
            common.update(
                {
                    "typed_contract_digest": typed_spec.contract_digest(),
                    "typed_execution_factory": typed_spec.execution_factory,
                    "typed_stable_id": typed_spec.identity.stable_id,
                }
            )
        common["legacy_metadata_ref"] = "bionodulo/nodes/node_metadata.json#/" + _json_pointer_token(node_id)
        operational_nodes[node_id] = common

    typed_status_counts = Counter(entry["status"] for entry in compiled.nodes.values())
    released_typed_nodes = typed_status_counts.get("released", 0)
    active_nodes = availability_counts.get("active", 0)
    blocked_nodes = availability_counts.get("blocked", 0)
    summary = {
        "active_nodes": active_nodes,
        # Coverage is measured against the LIVE catalog (baseline + declared
        # post-baseline nodes), not the sealed ledger — otherwise adding a node
        # would make these read as complete while one node went unaccounted for.
        "all_nodes_active": blocked_nodes == 0 and len(operational_nodes) == EXPECTED_NODE_COUNT,
        "all_nodes_released": released_typed_nodes == EXPECTED_NODE_COUNT,
        "availability_counts": {"active": active_nodes, "blocked": blocked_nodes},
        "baseline_nodes": BASELINE_NODE_COUNT,
        "blocked_nodes": blocked_nodes,
        "evidence_pending_nodes": verification_counts.get(LEGACY_PENDING_STATUS, 0),
        "importability_verified": blocked_nodes == 0,
        "legacy_compatible_nodes": active_nodes,
        "operational_nodes": len(operational_nodes),
        "post_baseline_node_ids": sorted(POST_BASELINE_NODE_IDS),
        "post_baseline_nodes": len(POST_BASELINE_NODE_IDS),
        "released_typed_nodes": released_typed_nodes,
        "remaining_operational_nodes": EXPECTED_NODE_COUNT - len(operational_nodes),
        "remaining_typed_contract_nodes": EXPECTED_NODE_COUNT - len(compiled.specs),
        "total_nodes": EXPECTED_NODE_COUNT,
        "typed_contract_nodes": len(compiled.specs),
        "typed_status_counts": dict(sorted(typed_status_counts.items())),
        "verification_status_counts": dict(sorted(verification_counts.items())),
    }
    source_manifests = {
        "baseline_ledger_aggregate_sha256": baseline["aggregate_sha256"],
        "baseline_ledger_bytes_sha256": baseline_bytes_digest,
        "legacy_node_index_sha256": legacy_index_digest,
        "legacy_node_metadata_sha256": legacy_metadata_digest,
    }
    digest_payload = {
        "schema_version": 1,
        "nodes": operational_nodes,
        "source_manifests": source_manifests,
        "summary": summary,
        "typed_catalog_digest": compiled.catalog_digest,
    }
    catalog_digest = _sha256(_canonical_json_bytes(digest_payload))
    return {
        "schema_version": 1,
        "catalog_digest": catalog_digest,
        "nodes": operational_nodes,
        "source_manifests": source_manifests,
        "summary": summary,
        "typed_catalog_digest": compiled.catalog_digest,
    }


def _compile() -> tuple[Any, dict[str, Any]]:
    """Compile explicit modules and return the result plus promotion metadata."""

    # Imports live here so this script can be imported for tests without
    # eagerly importing the application node tree.
    from bionodulo.nodes.catalog.tools.samtools.artifacts import SAMTOOLS_ARTIFACT_REGISTRY
    from bionodulo.nodes.contract.compiler import CatalogCompiler

    # The Samtools registry includes the canonical seed types plus alignment
    # and sidecar types.  Pass it explicitly rather than mutating the seed
    # registry shared by unrelated families.
    compiler = CatalogCompiler(artifact_registry=SAMTOOLS_ARTIFACT_REGISTRY)
    compiled = compiler.compile_modules(SAMTOOLS_MODULES)
    baseline, baseline_bytes_digest = _read_baseline()
    if baseline_bytes_digest != _sha256(BASELINE_LEDGER.read_bytes()):  # pragma: no cover - defensive race guard
        raise CatalogBuildError("baseline ledger changed while compiling")

    statuses = {
        status: sum(entry.get("status") == status for entry in compiled.nodes.values())
        for status in sorted({entry.get("status") for entry in compiled.nodes.values()})
    }
    node_records = [
        {
            "node_id": spec.identity.stable_id,
            "machine_id": spec.identity.machine_id,
            "status": compiled.nodes[spec.identity.stable_id]["status"],
            "implementation_status": compiled.nodes[spec.identity.stable_id]["implementation_status"],
            "contract_digest": spec.contract_digest(),
            "execution_factory": spec.execution_factory,
        }
        for spec in compiled.specs
    ]
    summary = {
        "implemented_nodes": len(compiled.specs),
        "baseline_nodes": BASELINE_NODE_COUNT,
        "total_nodes": EXPECTED_NODE_COUNT,
        "remaining_nodes": EXPECTED_NODE_COUNT - len(compiled.specs),
        "status_counts": statuses,
        "all_nodes_released": all(record["status"] == "released" for record in node_records),
    }
    promotion_status = (
        "released"
        if summary["all_nodes_released"]
        else "promotion_candidate"
        if statuses.get("promotion_candidate", 0)
        else "quarantined"
    )
    summary["promotion_status"] = promotion_status
    promotion = {
        "schema_version": 1,
        "status": promotion_status,
        "catalog_digest": compiled.catalog_digest,
        "baseline_ledger_aggregate_sha256": baseline["aggregate_sha256"],
        "baseline_ledger_bytes_sha256": baseline_bytes_digest,
        "summary": summary,
        "nodes": node_records,
    }
    return compiled, promotion


def expected_documents(
    *,
    legacy_importer: Callable[[str], Any] | None = None,
) -> dict[Path, bytes]:
    """Build every typed and operational generated document without writing.

    ``legacy_importer`` exists so tests can prove the importability gate
    actually blocks a node; production always uses ``importlib.import_module``.
    """

    compiled, promotion = _compile()
    operational = _build_operational_document(compiled, legacy_importer=legacy_importer)
    promotion = {
        **promotion,
        "availability_status": "active",
        "operational_catalog_digest": operational["catalog_digest"],
        "operational_summary": operational["summary"],
    }
    lock = dict(compiled.lock)
    lock["promotion"] = promotion["summary"]
    lock["operational"] = {
        "catalog_digest": operational["catalog_digest"],
        **operational["summary"],
    }
    documents: dict[Path, object] = {
        GENERATED_DIR / "catalog.runtime.json": compiled.runtime,
        GENERATED_DIR / "catalog.ui.json": compiled.ui,
        GENERATED_DIR / "compatibility.json": compiled.compatibility,
        GENERATED_DIR / "node-index.json": compiled.node_index,
        GENERATED_DIR / "catalog.lock.json": lock,
        GENERATED_DIR / "catalog.promotion.json": promotion,
        GENERATED_DIR / "catalog.operational.json": operational,
    }
    return {path: _canonical_json_bytes(document) for path, document in documents.items()}


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        mode = 0o644
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
            temporary = Path(handle.name)
            os.fchmod(handle.fileno(), mode)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        # Directory-fsync is a POSIX durability step; Windows denies fsync
        # on directory handles (EACCES).
        if os.name == "posix":
            directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def write_or_check(documents: Mapping[Path, bytes], *, check: bool) -> tuple[str, ...]:
    stale: list[str] = []
    for path, expected in documents.items():
        if check:
            if not path.is_file() or path.read_bytes() != expected:
                stale.append(path.name)
        else:
            _write_atomic(path, expected)
    return tuple(stale)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="atomically write generated projections")
    mode.add_argument("--check", action="store_true", help="fail if any generated projection is stale")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        documents = expected_documents()
        stale = write_or_check(documents, check=args.check)
    except (CatalogBuildError, OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.check:
        if stale:
            print("STALE: " + ", ".join(stale) + ". Run --write.", file=sys.stderr)
            return 1
        print(
            f"Catalog projections are up to date ({len(documents)} files; "
            f"{EXPECTED_NODE_COUNT}/{EXPECTED_NODE_COUNT} operational, "
            f"{len(SAMTOOLS_MODULES)}/{EXPECTED_NODE_COUNT} typed)."
        )
        return 0
    print(
        f"Wrote {len(documents)} catalog projections "
        f"({EXPECTED_NODE_COUNT}/{EXPECTED_NODE_COUNT} operational, "
        f"{len(SAMTOOLS_MODULES)}/{EXPECTED_NODE_COUNT} typed)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
