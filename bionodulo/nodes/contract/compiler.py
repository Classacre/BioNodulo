"""Small, deterministic compiler for the typed node catalog.

The legacy node registry is intentionally not involved here.  A catalog build
starts from an explicit list of :class:`~bionodulo.nodes.contract.model.NodeSpec`
objects (or explicitly named authoring modules), validates that list, and
produces the projections consumed by the v2 runtime and editor.  Keeping this
boundary narrow is useful while families are being promoted incrementally: a
family can compile its own specs without making the 943-entry forensic ledger
look like a set of released nodes.

This module deliberately does not read generated files or walk a package with
``pkgutil``.  Callers must provide the modules they intend to compile.  The
compiler is also deliberately non-executing; it validates contracts and
factory references, while the registry lazily imports a selected factory when
the workflow actually requests a node.
"""

from __future__ import annotations

import hashlib
import importlib
import json
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from bionodulo.nodes.catalog.artifacts import ARTIFACT_REGISTRY
from bionodulo.nodes.contract.artifacts import ArtifactRegistry
from bionodulo.nodes.contract.model import NodeOwnership, NodeSpec


class CatalogError(ValueError):
    """Raised when an explicit catalog input cannot be compiled."""


def _canonical_json_bytes(value: object) -> bytes:
    """Return the one canonical JSON encoding used for catalog digests."""

    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as error:
        raise CatalogError(f"catalog projection is not canonical JSON: {error}") from error


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _factory_parts(factory: str) -> tuple[str, str]:
    # NodeSpec already performs the strict syntax validation.  Retaining this
    # guard here gives a stable CatalogError when a trusted constructed model is
    # handed to the compiler.
    if not isinstance(factory, str) or factory.count(":") != 1:
        raise CatalogError(f"invalid execution factory: {factory!r}")
    module, symbol = factory.split(":", 1)
    if not module or not symbol:
        raise CatalogError(f"invalid execution factory: {factory!r}")
    return module, symbol


def _maturity_status(spec: NodeSpec) -> str:
    """Map maturity evidence to a UI/runtime status.

    ``released`` is intentionally the only executable production status.  A
    spec with some contiguous passed gates is useful to the promotion tooling
    and is labelled ``promotion_candidate``; all other valid contracts remain
    ``quarantined``.  This lets the first-wave implementation be visible
    without forging cloud or workflow evidence.
    """

    maturity = spec.maturity
    if maturity is not None and maturity.released:
        return "released"
    if maturity is not None and maturity.assessments:
        return "promotion_candidate"
    if (
        spec.presentation.owner is not NodeOwnership.BIONODULO_CORE
        and spec.evidence is not None
        and spec.environment is not None
        and spec.runtime_binding is not None
    ):
        # A complete external authoring contract is ready for verification,
        # but it is still non-released until all maturity gates are retained.
        return "promotion_candidate"
    return "quarantined"


def _json_model(value: Any) -> Any:
    """Dump a Pydantic model without leaking enum instances into projections."""

    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", round_trip=True)
    return value


@dataclass(frozen=True, slots=True)
class CompiledCatalog:
    """Immutable in-memory catalog projections.

    The dictionaries contain only JSON-compatible primitives, so callers can
    serialize them directly or pass them to the registry.  ``NodeSpec`` values
    themselves remain immutable Pydantic models.
    """

    specs: tuple[NodeSpec, ...]
    catalog_digest: str
    node_index: Mapping[str, Mapping[str, Any]]
    runtime: Mapping[str, Any]
    ui: Mapping[str, Any]
    compatibility: Mapping[str, Any]
    lock: Mapping[str, Any]

    @property
    def entries(self) -> tuple[Mapping[str, Any], ...]:
        nodes = self.node_index.get("nodes", self.node_index)
        if not isinstance(nodes, Mapping):
            return ()
        return tuple(nodes.values())

    @property
    def nodes(self) -> Mapping[str, Mapping[str, Any]]:
        """The ID-keyed lazy-index entries without document metadata."""

        nodes = self.node_index.get("nodes", self.node_index)
        return nodes if isinstance(nodes, Mapping) else {}

    @property
    def catalog_lock(self) -> Mapping[str, Any]:
        """Compatibility alias for callers using the generated filename."""

        return self.lock

    def document(self, name: str) -> Mapping[str, Any]:
        """Return a generated projection by its conventional filename stem."""

        documents: dict[str, Mapping[str, Any]] = {
            "node-index": self.node_index,
            "catalog.runtime": self.runtime,
            "catalog.ui": self.ui,
            "compatibility": self.compatibility,
            "catalog.lock": self.lock,
        }
        try:
            return documents[name]
        except KeyError as error:
            raise KeyError(f"unknown catalog projection: {name}") from error

    def as_dict(self) -> dict[str, Mapping[str, Any]]:
        return {
            "node-index": self.node_index,
            "catalog.runtime": self.runtime,
            "catalog.ui": self.ui,
            "compatibility": self.compatibility,
            "catalog.lock": self.lock,
        }


class CatalogCompiler:
    """Compile explicitly supplied ``NodeSpec`` objects into v2 projections."""

    def __init__(
        self,
        *,
        artifact_registry: ArtifactRegistry | None = None,
        importer: Callable[[str], Any] | None = None,
    ) -> None:
        self.artifact_registry = artifact_registry or ARTIFACT_REGISTRY
        self.importer = importer or importlib.import_module

    def compile_modules(self, module_names: Iterable[str]) -> CompiledCatalog:
        """Import an explicit module list and compile its exported specs.

        Authoring modules may expose a single ``SPEC``, an iterable ``SPECS``,
        or a ``get_node_specs()`` function.  Supporting all three forms keeps
        the compiler compatible with focused one-node files while allowing a
        family package to publish a small explicit registration function.
        Import failures and malformed exports are fatal; no module is skipped.
        """

        names = tuple(module_names)
        if not names:
            raise CatalogError("compile_modules requires at least one explicit module")
        if any(not isinstance(name, str) or not name.strip() for name in names):
            raise CatalogError("module names must be nonempty strings")
        if len(set(names)) != len(names):
            raise CatalogError("duplicate catalog module name")

        specs: list[NodeSpec] = []
        source_modules: dict[str, str] = {}
        for module_name in names:
            try:
                module = self.importer(module_name)
            except Exception as error:  # pragma: no cover - exact importer varies by caller
                raise CatalogError(f"failed to import catalog module {module_name}: {error}") from error
            exported = self._module_specs(module, module_name)
            for spec in exported:
                specs.append(spec)
                source_modules[spec.identity.stable_id] = module_name
                source_modules[spec.identity.machine_id] = module_name
        return self.compile(specs, source_modules=source_modules)

    def compile_module(self, module_name: str) -> CompiledCatalog:
        return self.compile_modules((module_name,))

    def compile(
        self,
        specs: Iterable[NodeSpec],
        *,
        source_modules: Mapping[str, str] | None = None,
    ) -> CompiledCatalog:
        """Validate and deterministically project a sequence of node specs."""

        try:
            raw_specs = tuple(specs)
        except TypeError as error:
            raise CatalogError("catalog specs must be an iterable") from error
        if not raw_specs:
            raise CatalogError("catalog compilation requires at least one NodeSpec")

        validated: list[NodeSpec] = []
        by_stable: dict[str, NodeSpec] = {}
        by_machine: dict[str, NodeSpec] = {}
        by_alias: dict[str, str] = {}
        for index, raw_spec in enumerate(raw_specs):
            try:
                spec = NodeSpec.model_validate(raw_spec)
            except Exception as error:
                raise CatalogError(f"invalid NodeSpec at index {index}: {error}") from error

            stable_id = spec.identity.stable_id
            machine_id = spec.identity.machine_id
            if stable_id in by_stable:
                raise CatalogError(f"duplicate node_id: {stable_id}")
            if machine_id in by_machine:
                raise CatalogError(f"duplicate machine_id: {machine_id}")
            if stable_id in by_machine or machine_id in by_stable:
                raise CatalogError(f"node ID collides across stable and machine IDs: {stable_id}/{machine_id}")

            aliases = (*spec.identity.aliases, machine_id)
            for alias in aliases:
                if alias in by_alias or alias in by_stable or alias in by_machine:
                    raise CatalogError(f"duplicate node alias: {alias}")
                by_alias[alias] = stable_id

            self._validate_artifact_ports(spec)
            _factory_parts(spec.execution_factory)
            by_stable[stable_id] = spec
            by_machine[machine_id] = spec
            validated.append(spec)

        ordered = tuple(sorted(validated, key=lambda item: item.identity.stable_id))
        source_modules = source_modules or {}

        node_index: dict[str, dict[str, Any]] = {}
        runtime_nodes: dict[str, dict[str, Any]] = {}
        ui_nodes: dict[str, dict[str, Any]] = {}
        for spec in ordered:
            stable_id = spec.identity.stable_id
            module, symbol = _factory_parts(spec.execution_factory)
            # A module containing SPEC is authoritative only when the caller
            # supplied it; execution_factory remains the runtime import path.
            authoring_module = source_modules.get(
                stable_id,
                source_modules.get(spec.identity.machine_id, module),
            )
            aliases = tuple(sorted({*spec.identity.aliases, spec.identity.machine_id}))
            status = _maturity_status(spec)
            entry = {
                "node_id": stable_id,
                "machine_id": spec.identity.machine_id,
                "aliases": list(aliases),
                "module": module,
                "symbol": symbol,
                "execution_factory": spec.execution_factory,
                "contract_digest": spec.contract_digest(),
                "status": status,
                "implementation_status": "implemented",
                "authoring_module": authoring_module,
            }
            node_index[stable_id] = entry
            runtime_nodes[stable_id] = {
                "node_id": stable_id,
                "machine_id": spec.identity.machine_id,
                "execution_kind": spec.execution_kind.value,
                "execution_factory": spec.execution_factory,
                "module": module,
                "symbol": symbol,
                "contract_digest": spec.contract_digest(),
                "status": status,
                "maturity": None if spec.maturity is None else _json_model(spec.maturity),
            }
            ui_nodes[stable_id] = {
                "identity": _json_model(spec.identity),
                "presentation": _json_model(spec.presentation),
                "artifact_inputs": [
                    _json_model(item) for item in sorted(spec.artifact_inputs, key=lambda item: item.port_id)
                ],
                "value_inputs": [
                    _json_model(item) for item in sorted(spec.value_inputs, key=lambda item: item.port_id)
                ],
                "parameters": [
                    _json_model(item) for item in sorted(spec.parameters, key=lambda item: item.parameter_id)
                ],
                "secrets": [
                    _json_model(item) for item in sorted(spec.secrets, key=lambda item: item.secret_id)
                ],
                "outputs": [_json_model(item) for item in sorted(spec.outputs, key=lambda item: item.port_id)],
                "status": status,
                "contract_digest": spec.contract_digest(),
            }

        compatibility = self._compatibility_projection(ordered)
        # Digest only content that is independent of the digest itself.  Every
        # generated document then carries that single identity.
        payload = {
            "schema_version": 1,
            "node_index": node_index,
            "runtime": {"schema_version": 1, "nodes": runtime_nodes},
            "ui": {"schema_version": 1, "nodes": ui_nodes},
            "compatibility": compatibility,
        }
        catalog_digest = _digest(payload)
        runtime = {**payload["runtime"], "catalog_digest": catalog_digest}
        ui = {**payload["ui"], "catalog_digest": catalog_digest}
        compatibility_document = {**compatibility, "catalog_digest": catalog_digest}
        node_index_document = {
            "schema_version": 1,
            "catalog_digest": catalog_digest,
            "nodes": node_index,
        }
        statuses = Counter(entry["status"] for entry in node_index.values())
        lock = {
            "schema_version": 1,
            "catalog_digest": catalog_digest,
            "node_count": len(ordered),
            "status_counts": dict(sorted(statuses.items())),
            "node_contract_digests": {
                spec.identity.stable_id: spec.contract_digest() for spec in ordered
            },
        }
        return CompiledCatalog(
            specs=ordered,
            catalog_digest=catalog_digest,
            node_index=node_index_document,
            runtime=runtime,
            ui=ui,
            compatibility=compatibility_document,
            lock=lock,
        )

    def _module_specs(self, module: Any, module_name: str) -> tuple[NodeSpec, ...]:
        try:
            getter = getattr(module, "get_node_specs", None)
            if callable(getter):
                exported = getter()
            elif hasattr(module, "SPECS"):
                exported = getattr(module, "SPECS")
            elif hasattr(module, "SPEC"):
                exported = (getattr(module, "SPEC"),)
            else:
                raise CatalogError(
                    f"catalog module {module_name} must export SPEC, SPECS, or get_node_specs"
                )
            if isinstance(exported, NodeSpec):
                exported = (exported,)
            if isinstance(exported, (str, bytes)):
                raise CatalogError(f"catalog module {module_name} exported a non-iterable spec collection")
            values = tuple(exported)
        except CatalogError:
            raise
        except Exception as error:
            raise CatalogError(f"catalog module {module_name} has invalid spec exports: {error}") from error
        if not values:
            raise CatalogError(f"catalog module {module_name} exported no NodeSpecs")
        return values

    def _validate_artifact_ports(self, spec: NodeSpec) -> None:
        for port in (*spec.artifact_inputs, *spec.outputs):
            try:
                # A self-compatibility lookup validates registration while
                # avoiding assumptions about a particular ArtifactType class.
                self.artifact_registry.is_type_compatible(port.artifact_type, port.artifact_type)
            except Exception as error:
                raise CatalogError(
                    f"node {spec.identity.stable_id} references unknown artifact type "
                    f"{port.artifact_type}: {error}"
                ) from error

    def _compatibility_projection(self, specs: Sequence[NodeSpec]) -> dict[str, Any]:
        edges: list[dict[str, str]] = []
        for source in specs:
            for output in source.outputs:
                for target in specs:
                    for input_port in target.artifact_inputs:
                        try:
                            compatible = self.artifact_registry.can_connect(output, input_port)
                        except Exception as error:
                            raise CatalogError(
                                f"cannot compile compatibility for {source.identity.stable_id}"
                                f":{output.port_id} -> {target.identity.stable_id}:{input_port.port_id}: {error}"
                            ) from error
                        if compatible:
                            edges.append(
                                {
                                    "source_node": source.identity.stable_id,
                                    "source_port": output.port_id,
                                    "target_node": target.identity.stable_id,
                                    "target_port": input_port.port_id,
                                }
                            )
        edges.sort(key=lambda item: tuple(item[field] for field in ("source_node", "source_port", "target_node", "target_port")))
        return {"schema_version": 1, "artifact_edges": edges}


__all__ = ["CatalogCompiler", "CatalogError", "CompiledCatalog"]
