"""Generated, searchable bio.tools definitions; metadata is never an execution contract.

Every verified source record becomes one stable node, with no per-tool Python or
name-based identity guesses. SQLite keeps the whole catalog off the startup path.
"""
from __future__ import annotations

import hashlib
import gzip
import json
import os
import re
import sqlite3
import tempfile
import zlib
from contextlib import closing
from functools import lru_cache
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import quote

from bionodulo.nodes.base import BaseNode

DEFAULT_CATALOG = Path(__file__).parent / "generated" / "biotools_catalog.sqlite.gz"
NODE_ID_PATTERN = re.compile(r"biotools_[a-f0-9]{32}\Z")
EXECUTION_BLOCKER = "No verified executable interface and pinned runtime are bound to this registry definition."


class RegistryCatalogError(ValueError):
    """The generated catalog is unavailable or inconsistent."""


class RegistryExecutionUnavailable(ValueError):
    """A registry description cannot be executed as a command."""


def generated_node_id(accession: str) -> str:
    return "biotools_" + hashlib.sha256(accession.casefold().encode("utf-8")).hexdigest()[:32]


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _terms(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted({str(item["term"]) for item in value if isinstance(item, dict) and item.get("term")})


def generate_definition(record: dict[str, Any], snapshot_sha256: str) -> dict[str, Any]:
    """Retain all annotations without inventing ports, commands, or dependencies."""
    from bionodulo.nodes.generation.discovery import discover_record

    discovery = discover_record(record)
    accession = record["biotoolsID"]
    operations = sorted({
        term for function in record.get("function", []) if isinstance(function, dict)
        for term in _terms(function.get("operation", []))
    })
    return {
        "node_id": generated_node_id(accession), "accession": accession,
        "name": str(record.get("name") or accession), "description": str(record.get("description") or ""),
        "tool_types": sorted(str(item) for item in record.get("toolType", []) if isinstance(item, str)),
        "topics": _terms(record.get("topic", [])), "operations": operations,
        "execution_status": "definition_only", "blockers": [EXECUTION_BLOCKER],
        "reference_url": "https://bio.tools/" + quote(accession, safe=""),
        "source_snapshot_sha256": snapshot_sha256,
        "source_record_sha256": hashlib.sha256(_canonical(record)).hexdigest(),
        "source_candidates": discovery["source_candidates"], "gap_states": discovery["gap_states"],
        "source_record": record,
    }


def generate_catalog(snapshot: Path, manifest_path: Path, destination: Path) -> dict[str, Any]:
    """Publish only after the complete input digest, denominator and IDs verify."""
    from bionodulo.nodes.generation.discovery import _verified_records

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise RegistryCatalogError("snapshot manifest must be an object")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".registry-catalog-", suffix=".sqlite", dir=destination.parent)
    os.close(fd)
    staging = Path(name)
    try:
        with closing(sqlite3.connect(staging)) as db:
            db.executescript("""
                CREATE TABLE catalog_metadata (value TEXT NOT NULL);
                CREATE TABLE definitions (
                    node_id TEXT PRIMARY KEY, accession TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL, search_text TEXT NOT NULL, definition BLOB NOT NULL
                );
                CREATE INDEX definitions_name ON definitions(name, node_id);
            """)
            count = 0
            for record in _verified_records(snapshot, manifest):
                definition = generate_definition(record, manifest["sha256"])
                searchable = " ".join([
                    definition["accession"], definition["name"], definition["description"],
                    *definition["tool_types"], *definition["topics"], *definition["operations"],
                ]).casefold()
                db.execute("INSERT INTO definitions VALUES (?, ?, ?, ?, ?)", (
                    definition["node_id"], definition["accession"].casefold(),
                    definition["name"].casefold(), searchable, zlib.compress(_canonical(definition), level=9),
                ))
                count += 1
            # Hash in stable ID order, independent of registry pagination order.
            digest = hashlib.sha256()
            for (blob,) in db.execute("SELECT definition FROM definitions ORDER BY node_id"):
                digest.update(zlib.decompress(blob) + b"\n")
            metadata = {
                "schema_version": 1, "records": count, "sha256": manifest["sha256"],
                "updated_at": manifest.get("completed_at"), "source": manifest.get("source"),
                "license": manifest.get("license", "CC-BY-4.0"), "attribution": "bio.tools contributors",
                "definition_digest": digest.hexdigest(), "execution_status": "definition_only",
                "scope": "All records in the verified snapshot; no execution or scientific validation inferred.",
            }
            db.execute("INSERT INTO catalog_metadata VALUES (?)", (_canonical(metadata).decode(),))
            db.commit()
        if destination.suffix == ".gz":
            # Deterministic compressed distribution; expand once per process for indexed reads.
            packed = staging.with_suffix(".gz")
            try:
                with staging.open("rb") as source, packed.open("wb") as target:
                    with gzip.GzipFile(fileobj=target, mode="wb", filename="", mtime=0) as compressor:
                        while chunk := source.read(1024 * 1024):
                            compressor.write(chunk)
                os.replace(packed, destination)
            finally:
                packed.unlink(missing_ok=True)
        else:
            os.replace(staging, destination)
        return metadata
    finally:
        staging.unlink(missing_ok=True)


@lru_cache(maxsize=2)
def _expand_catalog(path: str, size: int, modified: int) -> tempfile.TemporaryDirectory[str]:
    """Private process-local cache; no shared writable database or startup downloads."""
    directory = tempfile.TemporaryDirectory(prefix="bionodulo-registry-")
    try:
        total = 0
        with gzip.open(path, "rb") as source, (Path(directory.name) / "catalog.sqlite").open("wb") as output:
            while chunk := source.read(1024 * 1024):
                total += len(chunk)
                if total > 512 * 1024 * 1024:
                    raise RegistryCatalogError("Expanded catalog exceeds 512 MiB")
                output.write(chunk)
        return directory
    except Exception:
        directory.cleanup()
        raise


class RegistryCatalog:
    """Read-only, bounded queries against a generated catalog."""

    def __init__(self, path: Path | None = None):
        self.path = path or Path(os.environ.get("BIONODULO_REGISTRY_CATALOG", str(DEFAULT_CATALOG)))

    def _connect(self) -> sqlite3.Connection:
        try:
            path = self.path.resolve()
            if path.suffix == ".gz":
                stat = path.stat()
                directory = _expand_catalog(str(path), stat.st_size, stat.st_mtime_ns)
                path = Path(directory.name) / "catalog.sqlite"
            db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
            db.execute("PRAGMA trusted_schema=OFF")
            db.execute("PRAGMA query_only=ON")
            return db
        except (sqlite3.Error, OSError, EOFError) as error:
            raise RegistryCatalogError("Generated bio.tools catalog is unavailable") from error

    @staticmethod
    def _metadata(db: sqlite3.Connection) -> dict[str, Any]:
        rows = db.execute("SELECT value FROM catalog_metadata").fetchall()
        if len(rows) != 1:
            raise RegistryCatalogError("Catalog requires exactly one metadata record")
        metadata = json.loads(rows[0][0])
        if metadata.get("schema_version") != 1 or type(metadata.get("records")) is not int:
            raise RegistryCatalogError("Unsupported generated catalog metadata")
        return metadata

    @staticmethod
    def _decode(blob: bytes) -> dict[str, Any]:
        # Source records are bounded by the snapshot verifier; enforce on read as well.
        inflater = zlib.decompressobj()
        payload = inflater.decompress(blob, 32 * 1024 * 1024 + 1)
        if len(payload) > 32 * 1024 * 1024 or not inflater.eof or inflater.unused_data:
            raise RegistryCatalogError("Invalid or oversized catalog definition")
        value = json.loads(payload)
        if not isinstance(value, dict) or value.get("node_id") != generated_node_id(value.get("accession", "")):
            raise RegistryCatalogError("Catalog node identity mismatch")
        if value.get("execution_status") != "definition_only" or value.get("blockers") != [EXECUTION_BLOCKER]:
            raise RegistryCatalogError("Registry metadata cannot authorize execution")
        if hashlib.sha256(_canonical(value.get("source_record"))).hexdigest() != value.get("source_record_sha256"):
            raise RegistryCatalogError("Catalog source record digest mismatch")
        return value

    def get(self, node_id: str) -> dict[str, Any] | None:
        if NODE_ID_PATTERN.fullmatch(node_id) is None:
            return None
        with closing(self._connect()) as db:
            row = db.execute("SELECT definition FROM definitions WHERE node_id = ?", (node_id,)).fetchone()
            if row is None:
                return None
            value = self._decode(row[0])
            if value["node_id"] != node_id:
                raise RegistryCatalogError("Catalog lookup identity mismatch")
            return value

    def verify(self) -> dict[str, Any]:
        """Exhaustively verify every generated record, projection and denominator."""
        with closing(self._connect()) as db:
            metadata = self._metadata(db)
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RegistryCatalogError("Catalog SQLite integrity check failed")
            count = 0
            digest = hashlib.sha256()
            for node_id, accession, blob in db.execute(
                "SELECT node_id, accession, definition FROM definitions ORDER BY node_id"
            ):
                value = self._decode(blob)
                if value["node_id"] != node_id or value["accession"].casefold() != accession:
                    raise RegistryCatalogError("Catalog row identity mismatch")
                expected = generate_definition(value["source_record"], metadata["sha256"])
                if expected != value:
                    raise RegistryCatalogError("Catalog definition differs from source-derived projection")
                digest.update(_canonical(value) + b"\n")
                count += 1
            if count != metadata["records"] or digest.hexdigest() != metadata["definition_digest"]:
                raise RegistryCatalogError("Catalog count or definition digest mismatch")
            return {**metadata, "verified_definitions": count, "executable_definitions": 0}

    def search(self, query: str = "", *, offset: int = 0, limit: int = 40) -> dict[str, Any]:
        if not 1 <= limit <= 100 or offset < 0 or len(query) > 256:
            raise RegistryCatalogError("Invalid catalog query bounds")
        normalized = query.strip().casefold()
        literal = normalized.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = "%" + literal + "%"
        with closing(self._connect()) as db:
            metadata = self._metadata(db)
            if not normalized:
                matched = metadata["records"]
                rows = db.execute("SELECT definition FROM definitions ORDER BY name, node_id LIMIT ? OFFSET ?",
                                  (limit, offset))
            else:
                matched = db.execute("SELECT count(*) FROM definitions WHERE search_text LIKE ? ESCAPE '\\'",
                                     (pattern,)).fetchone()[0]
                rows = db.execute("""SELECT definition FROM definitions WHERE search_text LIKE ? ESCAPE '\\'
                    ORDER BY CASE WHEN accession = ? THEN 0 WHEN name = ? THEN 1 ELSE 2 END, name, node_id
                    LIMIT ? OFFSET ?""", (pattern, normalized, normalized, limit, offset))
            entries = []
            for (blob,) in rows:
                definition = self._decode(blob)
                entries.append({key: definition[key] for key in (
                    "node_id", "accession", "name", "description", "tool_types", "topics", "operations",
                    "execution_status", "blockers", "reference_url",
                )} | {"linked_node_ids": [], "runnable_node_ids": []})
            return {"schema_version": 1, "total": metadata["records"], "matched_count": matched,
                    "offset": offset, "limit": limit, "snapshot": metadata, "entries": entries}


class RegistryDefinitionNode(BaseNode):
    """One shared non-executable adapter for all generated registry definitions."""

    CATEGORY = "bio.tools / Generated definitions"
    REQUIRES_EXTERNAL_TOOLS = False
    OUTPUT_NODE = True  # A definition cannot be silently pruned as an unused intermediate.
    EXPERIMENTAL = True
    REGISTRY_ORIGIN: ClassVar[dict[str, Any]] = {}

    async def run(self, **kwargs: Any) -> tuple[Any, ...]:
        raise RegistryExecutionUnavailable(f"{self.NODE_ID}: {EXECUTION_BLOCKER}")


def bind_registry_definition(definition: dict[str, Any]) -> type[BaseNode]:
    origin = {key: value for key, value in definition.items() if key != "source_record"}
    return type("GeneratedRegistryDefinition", (RegistryDefinitionNode,), {
        "__module__": __name__, "NODE_ID": definition["node_id"],
        "DISPLAY_NAME": definition["name"], "DESCRIPTION": definition["description"],
        "SEARCH_ALIASES": [definition["accession"], *definition["operations"]],
        "DOCUMENTATION_URL": definition["reference_url"], "REGISTRY_ORIGIN": origin,
        "CITATION_TEXT": "bio.tools contributors, CC-BY-4.0. " + definition["reference_url"],
    })


def registry_execution_blockers(workflow: dict[str, Any], registry: Any = None) -> list[str]:
    """Definitions cannot execute, even with forged client flags or missing catalog.

    Executable adapters use their own contract-derived IDs. No custom class may
    turn the reserved registry-definition namespace into an execution admission.
    """
    blocked: list[str] = []
    pending = [workflow]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        nodes = current.get("nodes", [])
        if isinstance(nodes, dict):
            nodes = list(nodes.values())
        if not isinstance(nodes, (list, tuple)):
            continue
        for node in nodes:
            node_type = node.get("type", "") if isinstance(node, dict) else getattr(node, "type", "")
            if isinstance(node_type, str) and NODE_ID_PATTERN.fullmatch(node_type):
                blocked.append(f"{node_type}: {EXECUTION_BLOCKER}")
            if isinstance(node, dict) and node_type == "subgraph":
                params = node.get("params", {})
                inner = params.get("workflow") if isinstance(params, dict) else None
                if isinstance(inner, dict):
                    pending.append(inner)
    return sorted(set(blocked))
