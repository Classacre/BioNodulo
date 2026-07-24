"""Lazy runtime registry for compiled and operational catalog projections.

The v2 registry intentionally knows nothing about the legacy ``NodeRegistry``.
It accepts a compiler result (or the two generated runtime/index documents),
performs a cheap digest consistency check, and imports only the factory needed
for a requested node. Strict typed nodes must be released (or receive an
explicit test override). The separate operational projection may expose an
existing ``BaseNode`` class through the narrowly defined ``base_node_v1``
compatibility lane without claiming evidence-backed release maturity.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any


_LEGACY_COMPATIBLE_STATUS = "legacy_compatible"
_LEGACY_RUNTIME_ADAPTER = "base_node_v1"


class CatalogRegistryError(RuntimeError):
    """Base class for v2 catalog resolution failures."""


class UnknownNodeError(CatalogRegistryError, KeyError):
    """The requested stable ID, machine ID, or alias is absent."""


class QuarantinedNodeError(CatalogRegistryError):
    """The requested node has not passed all release gates."""


class CatalogIntegrityError(CatalogRegistryError):
    """Generated catalog documents disagree about their digest or shape."""


class NodeImportError(CatalogRegistryError):
    """The selected runtime factory could not be imported or resolved."""


@dataclass(frozen=True, slots=True)
class ResolvedNode:
    """Factory plus immutable catalog metadata for callers that need both."""

    node_id: str
    entry: Mapping[str, Any]
    implementation: Any

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        if not callable(self.implementation):
            raise TypeError(f"catalog node {self.node_id} implementation is not callable")
        return self.implementation(*args, **kwargs)


def _nodes_from_document(document: Mapping[str, Any], *, label: str) -> Mapping[str, Mapping[str, Any]]:
    if not isinstance(document, Mapping):
        raise CatalogIntegrityError(f"{label} document must be an object")
    raw_nodes = document.get("nodes", document)
    if not isinstance(raw_nodes, Mapping):
        raise CatalogIntegrityError(f"{label}.nodes must be an object")
    result: dict[str, Mapping[str, Any]] = {}
    for key, value in raw_nodes.items():
        if not isinstance(key, str) or not key:
            raise CatalogIntegrityError(f"{label} contains an invalid node ID")
        if not isinstance(value, Mapping):
            raise CatalogIntegrityError(f"{label}.{key} must be an object")
        result[key] = value
    return result


def _document_digest(document: Mapping[str, Any], *, label: str) -> str | None:
    digest = document.get("catalog_digest")
    if digest is None:
        return None
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        raise CatalogIntegrityError(f"{label}.catalog_digest is malformed")
    return digest


class CatalogRegistry:
    """Resolve one compiled node implementation at a time.

    ``compiled_catalog`` may be a ``CompiledCatalog`` instance, a mapping with
    ``node_index``/``runtime`` documents, or a pair of explicit documents via
    :meth:`from_documents`.  No module import occurs during construction.
    """

    def __init__(
        self,
        compiled_catalog: Any,
        *,
        importer: Callable[[str], Any] | None = None,
        allow_quarantined: bool = False,
    ) -> None:
        self._importer = importer or importlib.import_module
        self._allow_quarantined = bool(allow_quarantined)
        self._cache: dict[str, ResolvedNode] = {}

        index_document, runtime_document, specs = self._documents_from_catalog(compiled_catalog)
        self._catalog_digest = self._verify_documents(index_document, runtime_document)
        index_nodes = _nodes_from_document(index_document, label="node-index")
        runtime_nodes = _nodes_from_document(runtime_document, label="catalog.runtime")
        if set(index_nodes) != set(runtime_nodes):
            missing_runtime = sorted(set(index_nodes) - set(runtime_nodes))
            missing_index = sorted(set(runtime_nodes) - set(index_nodes))
            raise CatalogIntegrityError(
                "node-index and catalog.runtime IDs differ: "
                f"missing_runtime={missing_runtime}, missing_index={missing_index}"
            )

        entries: dict[str, dict[str, Any]] = {}
        aliases: dict[str, str] = {}
        for node_id in sorted(index_nodes):
            index_entry = dict(index_nodes[node_id])
            runtime_entry = dict(runtime_nodes[node_id])
            entry = {**runtime_entry, **index_entry}
            entry.setdefault("node_id", node_id)
            entry.setdefault("status", "quarantined")
            factory = entry.get("execution_factory")
            module = entry.get("module")
            symbol = entry.get("symbol")
            if not isinstance(factory, str):
                if not (isinstance(module, str) and isinstance(symbol, str)):
                    raise CatalogIntegrityError(f"catalog node {node_id} has no runtime factory")
                factory = f"{module}:{symbol}"
            if factory.count(":") != 1:
                raise CatalogIntegrityError(f"catalog node {node_id} has malformed runtime factory")
            factory_module, factory_symbol = factory.split(":", 1)
            if not factory_module or not factory_symbol:
                raise CatalogIntegrityError(f"catalog node {node_id} has malformed runtime factory")
            entry["execution_factory"] = factory
            entry["module"] = factory_module
            entry["symbol"] = factory_symbol
            entry_aliases = entry.get("aliases", ())
            if isinstance(entry_aliases, (str, bytes)) or not isinstance(entry_aliases, (tuple, list)):
                raise CatalogIntegrityError(f"catalog node {node_id}.aliases must be an array")
            raw_aliases = (node_id, entry.get("machine_id"), *entry_aliases)
            if any(not isinstance(alias, str) or not alias for alias in raw_aliases):
                raise CatalogIntegrityError(f"catalog node {node_id} contains an invalid alias")
            all_aliases = set(raw_aliases)
            entries[node_id] = entry
            for alias in all_aliases:
                if alias is None:
                    continue
                previous = aliases.get(alias)
                if previous is not None and previous != node_id:
                    raise CatalogIntegrityError(f"catalog node alias is ambiguous: {alias}")
                aliases[alias] = node_id

        self._entries = entries
        self._aliases = aliases
        self._specs_by_id = self._index_specs(specs)

    @classmethod
    def from_documents(
        cls,
        node_index: Mapping[str, Any],
        runtime: Mapping[str, Any],
        *,
        importer: Callable[[str], Any] | None = None,
        allow_quarantined: bool = False,
    ) -> "CatalogRegistry":
        return cls(
            {"node_index": node_index, "runtime": runtime},
            importer=importer,
            allow_quarantined=allow_quarantined,
        )

    @classmethod
    def from_operational_document(
        cls,
        document: Mapping[str, Any],
        *,
        importer: Callable[[str], Any] | None = None,
        allow_quarantined: bool = False,
    ) -> "CatalogRegistry":
        """Load the generated 943-node ``base_node_v1`` projection."""

        if not isinstance(document, Mapping):
            raise CatalogIntegrityError("operational catalog document must be an object")
        nodes = document.get("nodes")
        digest = document.get("catalog_digest")
        if not isinstance(nodes, Mapping):
            raise CatalogIntegrityError("operational catalog requires a nodes object")
        if not isinstance(digest, str):
            raise CatalogIntegrityError("operational catalog requires catalog_digest")
        projection = {
            "schema_version": document.get("schema_version", 1),
            "catalog_digest": digest,
            "nodes": nodes,
        }
        return cls.from_documents(
            projection,
            projection,
            importer=importer,
            allow_quarantined=allow_quarantined,
        )

    @property
    def catalog_digest(self) -> str:
        return self._catalog_digest

    @property
    def node_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))

    def has(self, node_id: str) -> bool:
        return node_id in self._aliases

    def entry(self, node_id: str) -> Mapping[str, Any]:
        canonical = self._canonical_id(node_id)
        return self._entries[canonical]

    def get_spec(self, node_id: str) -> Any:
        """Return the source ``NodeSpec`` when constructed from a compiler."""

        canonical = self._canonical_id(node_id)
        try:
            return self._specs_by_id[canonical]
        except KeyError as error:
            raise UnknownNodeError(f"compiled catalog has no in-memory spec for {node_id}") from error

    def resolve(
        self,
        node_id: str,
        *,
        allow_quarantined: bool | None = None,
        wrapped: bool = False,
    ) -> Any:
        """Lazily import and return one node's declared runtime factory.

        ``wrapped=True`` returns :class:`ResolvedNode`, preserving metadata
        alongside the callable.  The default returns the implementation itself
        for straightforward use by workflow executors and tests.
        """

        canonical = self._canonical_id(node_id)
        entry = self._entries[canonical]
        permitted = self._allow_quarantined if allow_quarantined is None else bool(allow_quarantined)
        status = entry.get("status", "quarantined")
        legacy_compatible = self._is_legacy_compatible(entry)
        if status != "released" and not legacy_compatible and not permitted:
            reason = entry.get("release_block_reason") or f"status is {status}"
            raise QuarantinedNodeError(f"node {canonical} is quarantined: {reason}")

        cached = self._cache.get(canonical)
        if cached is not None:
            return cached if wrapped else cached.implementation

        module_name = entry["module"]
        symbol = entry["symbol"]
        try:
            module = self._importer(module_name)
            implementation = getattr(module, symbol)
        except Exception as error:  # pragma: no cover - importer exceptions vary
            raise NodeImportError(f"failed to resolve {canonical} from {module_name}:{symbol}: {error}") from error
        if legacy_compatible:
            from bionodulo.nodes.base import BaseNode

            if not isinstance(implementation, type) or not issubclass(implementation, BaseNode):
                raise NodeImportError(f"legacy-compatible node {canonical} factory is not a BaseNode class")
            if implementation.NODE_ID != canonical:
                raise NodeImportError(
                    f"legacy-compatible node {canonical} factory declares NODE_ID {implementation.NODE_ID!r}"
                )
        resolved = ResolvedNode(node_id=canonical, entry=entry, implementation=implementation)
        self._cache[canonical] = resolved
        return resolved if wrapped else implementation

    def resolve_node(self, node_id: str, **kwargs: Any) -> ResolvedNode:
        result = self.resolve(node_id, wrapped=True, **kwargs)
        assert isinstance(result, ResolvedNode)
        return result

    def _canonical_id(self, node_id: str) -> str:
        if not isinstance(node_id, str) or not node_id:
            raise UnknownNodeError(f"unknown catalog node: {node_id!r}")
        try:
            return self._aliases[node_id]
        except KeyError as error:
            raise UnknownNodeError(f"unknown catalog node: {node_id}") from error

    @staticmethod
    def _is_legacy_compatible(entry: Mapping[str, Any]) -> bool:
        """Recognize only the explicit, generated BaseNode compatibility lane."""

        if entry.get("status") != _LEGACY_COMPATIBLE_STATUS:
            return False
        if entry.get("runtime_adapter") != _LEGACY_RUNTIME_ADAPTER:
            return False
        if entry.get("availability") != "active":
            return False
        factory = entry.get("execution_factory")
        return isinstance(factory, str) and entry.get("legacy_execution_factory") == factory

    @staticmethod
    def _documents_from_catalog(catalog: Any) -> tuple[Mapping[str, Any], Mapping[str, Any], Any]:
        if hasattr(catalog, "node_index") and hasattr(catalog, "runtime"):
            return catalog.node_index, catalog.runtime, getattr(catalog, "specs", ())
        if not isinstance(catalog, Mapping):
            raise CatalogIntegrityError("compiled catalog must be a compiler result or mapping")
        index = catalog.get("node_index") or catalog.get("node-index")
        runtime = catalog.get("runtime") or catalog.get("catalog.runtime")
        if index is None or runtime is None:
            raise CatalogIntegrityError("compiled catalog mapping requires node_index and runtime documents")
        return index, runtime, catalog.get("specs", ())

    @staticmethod
    def _verify_documents(index: Mapping[str, Any], runtime: Mapping[str, Any]) -> str:
        index_digest = _document_digest(index, label="node-index")
        runtime_digest = _document_digest(runtime, label="catalog.runtime")
        if index_digest is None or runtime_digest is None:
            raise CatalogIntegrityError("catalog documents must declare catalog_digest")
        if index_digest != runtime_digest:
            raise CatalogIntegrityError("node-index and catalog.runtime catalog_digest values differ")
        return index_digest

    @staticmethod
    def _index_specs(specs: Any) -> dict[str, Any]:
        if specs is None:
            return {}
        try:
            values = tuple(specs)
        except TypeError:
            return {}
        result: dict[str, Any] = {}
        for spec in values:
            identity = getattr(spec, "identity", None)
            stable_id = getattr(identity, "stable_id", None)
            if isinstance(stable_id, str):
                result[stable_id] = spec
        return result


__all__ = [
    "CatalogIntegrityError",
    "CatalogRegistry",
    "CatalogRegistryError",
    "NodeImportError",
    "QuarantinedNodeError",
    "ResolvedNode",
    "UnknownNodeError",
]
