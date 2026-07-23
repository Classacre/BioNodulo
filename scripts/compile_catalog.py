#!/usr/bin/env python3
"""Compile the first typed catalog promotion wave.

The migration ledger is forensic evidence and is intentionally read-only here.
This build compiles exactly the seven Samtools modules, writes the normal v2
runtime/UI/index/compatibility projections, and records a separate promotion
manifest showing the cumulative ``7/943`` implementation count.  A release
status is never inferred from implementation: the seven specs remain
``promotion_candidate`` until their cloud and workflow gates pass.

Usage::

    .venv/bin/python scripts/compile_catalog.py --write
    .venv/bin/python scripts/compile_catalog.py --check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
GENERATED_DIR = REPO_ROOT / "bionodulo" / "nodes" / "generated"
BASELINE_LEDGER = GENERATED_DIR / "baseline-ledger.json"
BASELINE_NODE_COUNT = 943
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
)


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
        "remaining_nodes": BASELINE_NODE_COUNT - len(compiled.specs),
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


def expected_documents() -> dict[Path, bytes]:
    """Build every first-wave generated document without writing files."""

    compiled, promotion = _compile()
    lock = dict(compiled.lock)
    lock["promotion"] = promotion["summary"]
    documents: dict[Path, object] = {
        GENERATED_DIR / "catalog.runtime.json": compiled.runtime,
        GENERATED_DIR / "catalog.ui.json": compiled.ui,
        GENERATED_DIR / "compatibility.json": compiled.compatibility,
        GENERATED_DIR / "node-index.json": compiled.node_index,
        GENERATED_DIR / "catalog.lock.json": lock,
        GENERATED_DIR / "catalog.promotion.json": promotion,
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
        print(f"Catalog projections are up to date ({len(documents)} files; 7/{BASELINE_NODE_COUNT} implemented).")
        return 0
    print(f"Wrote {len(documents)} catalog projections ({7}/{BASELINE_NODE_COUNT} implemented).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
