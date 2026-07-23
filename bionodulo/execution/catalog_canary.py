"""Explicit, fail-closed execution bridge for promoted catalog canaries.

This module intentionally supports only the seven Samtools first-wave nodes.
It is selected per run through a structured executor option; normal workflow
execution continues to use the legacy registry when that option is absent.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import platform
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from bionodulo.nodes.catalog.registry import CatalogRegistry, CatalogRegistryError
from bionodulo.nodes.contract.artifacts import Cardinality
from bionodulo.nodes.contract.execution import ArgvPlan
from bionodulo.nodes.contract.model import NodeSpec
from bionodulo.nodes.contract.outputs import collect_outputs


CANARY_OPTION = "catalog_canary"
CANARY_NODE_MARKER = "_catalog_canary_runner"
SAMTOOLS_FIRST_WAVE_PROFILE = "samtools-first-wave"
SAMTOOLS_FIRST_WAVE_CATALOG_DIGEST = (
    "sha256:f070be36e0215603d7b5affb371fd1c6c528b02f996e4a1f145e6b2d2d467530"
)
SAMTOOLS_FIRST_WAVE_MACHINE_IDS = frozenset(
    {
        "samtools_view",
        "samtools_collate",
        "samtools_fixmate",
        "samtools_sort",
        "samtools_markdup",
        "samtools_index",
        "samtools_flagstat",
    }
)
SAMTOOLS_FIRST_WAVE_LOCK_SHA256 = (
    "sha256:918389cd4bc1f2a934e953317c4e160b505232fb8fc3e2795d9897a3b87a32b7"
)
SAMTOOLS_FIRST_WAVE_PACKAGE_SHA256 = (
    "sha256:2cb721907a2df7c54580298d655ae7587dbed593bd5536fa8ef4a22c9ae2a496"
)
SAMTOOLS_FIRST_WAVE_INPUT_TYPE = "input_file"
SAMTOOLS_FIRST_WAVE_INPUT_URL = (
    "https://raw.githubusercontent.com/Classacre/BioNodulo/"
    "2316c3ca54326229fe0aa236868369cfd442bfbd/"
    "tests/fixtures/samtools_first_wave/tiny.sam"
)
SAMTOOLS_FIRST_WAVE_INPUT_SHA256 = (
    "sha256:0b621dee8e14e8ebf5e52772c3c6695b47c312e5190b52591644ce872ee422c7"
)

_GENERATED_DIR = Path(__file__).resolve().parents[1] / "nodes" / "generated"
_ALLOWED_STATUSES = frozenset({"promotion_candidate", "released"})


class CatalogCanaryError(RuntimeError):
    """Raised when a catalog canary cannot be trusted or executed."""


@dataclass(frozen=True, slots=True)
class ResolvedCatalogCanaryNode:
    """One verified catalog factory plus its source contract metadata."""

    entry: Mapping[str, Any]
    factory: Callable[..., Any]
    spec: NodeSpec
    legacy_metadata: type[Any]


def _read_document(directory: Path, filename: str) -> dict[str, Any]:
    path = directory / filename
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CatalogCanaryError(f"cannot load committed catalog document {path}: {error}") from error
    if not isinstance(value, dict):
        raise CatalogCanaryError(f"committed catalog document {path} must contain an object")
    return value


class CatalogCanaryRunner:
    """Resolve and execute the exact Samtools first-wave promotion profile."""

    def __init__(
        self,
        *,
        profile: str,
        catalog_digest: str,
        generated_dir: str | Path = _GENERATED_DIR,
        importer: Callable[[str], ModuleType] = importlib.import_module,
    ) -> None:
        if profile != SAMTOOLS_FIRST_WAVE_PROFILE:
            raise CatalogCanaryError(f"unknown catalog canary profile: {profile!r}")
        if catalog_digest != SAMTOOLS_FIRST_WAVE_CATALOG_DIGEST:
            raise CatalogCanaryError(
                "catalog canary digest is not the committed Samtools first-wave digest"
            )
        machine = platform.machine().lower()
        if platform.system() != "Linux" or machine not in {"x86_64", "amd64"}:
            raise CatalogCanaryError(
                "Samtools first-wave catalog canary requires Linux amd64"
            )

        directory = Path(generated_dir)
        node_index = _read_document(directory, "node-index.json")
        runtime = _read_document(directory, "catalog.runtime.json")
        lock = _read_document(directory, "catalog.lock.json")
        promotion = _read_document(directory, "catalog.promotion.json")

        self.profile = profile
        self.catalog_digest = catalog_digest
        self._importer = importer
        self._imported_modules: dict[str, ModuleType] = {}
        self._resolved: dict[str, ResolvedCatalogCanaryNode] = {}

        def _recording_importer(module_name: str) -> ModuleType:
            module = self._importer(module_name)
            self._imported_modules[module_name] = module
            return module

        try:
            self._registry = CatalogRegistry.from_documents(
                node_index,
                runtime,
                importer=_recording_importer,
                allow_quarantined=True,
            )
        except CatalogRegistryError as error:
            raise CatalogCanaryError(f"catalog canary documents failed integrity checks: {error}") from error

        documents = {
            "node-index.json": node_index,
            "catalog.runtime.json": runtime,
            "catalog.lock.json": lock,
            "catalog.promotion.json": promotion,
        }
        for label, document in documents.items():
            if document.get("catalog_digest") != catalog_digest:
                raise CatalogCanaryError(f"{label} does not match the submitted catalog digest")
        if self._registry.catalog_digest != catalog_digest:
            raise CatalogCanaryError("catalog registry digest does not match the submitted digest")

        self._lock_contracts = lock.get("node_contract_digests")
        if not isinstance(self._lock_contracts, dict):
            raise CatalogCanaryError("catalog.lock.json has no node contract digest map")
        promotion_nodes = promotion.get("nodes")
        if not isinstance(promotion_nodes, list):
            raise CatalogCanaryError("catalog.promotion.json nodes must be an array")
        self._promotion_entries = {
            str(entry.get("node_id")): entry
            for entry in promotion_nodes
            if isinstance(entry, dict) and entry.get("node_id")
        }

        profile_ids: set[str] = set()
        for machine_id in sorted(SAMTOOLS_FIRST_WAVE_MACHINE_IDS):
            entry = self._entry(machine_id)
            self._validate_entry(entry)
            profile_ids.add(str(entry["node_id"]))
        self._profile_node_ids = frozenset(profile_ids)

    @classmethod
    def from_options(
        cls,
        options: Mapping[str, Any] | None,
    ) -> CatalogCanaryRunner | None:
        """Build a runner only for an explicitly submitted structured option."""

        if not options or CANARY_OPTION not in options:
            return None
        raw = options.get(CANARY_OPTION)
        if raw is None:
            return None
        if not isinstance(raw, Mapping):
            raise CatalogCanaryError("catalog_canary must be an object")
        unknown = sorted(set(raw) - {"profile", "catalog_digest"})
        if unknown:
            raise CatalogCanaryError(
                f"catalog_canary contains unsupported field(s): {', '.join(unknown)}"
            )
        profile = raw.get("profile")
        digest = raw.get("catalog_digest")
        if not isinstance(profile, str) or not profile:
            raise CatalogCanaryError("catalog_canary.profile must be a non-empty string")
        if not isinstance(digest, str) or not digest:
            raise CatalogCanaryError("catalog_canary.catalog_digest must be a non-empty string")
        return cls(profile=profile, catalog_digest=digest)

    def bind_nodes(self, nodes: Sequence[dict[str, Any]]) -> None:
        """Validate every executable node and mark it for this per-run bridge."""

        node_types = [str(node.get("type", "")) for node in nodes]
        counts = Counter(node_types)
        if counts.get(SAMTOOLS_FIRST_WAVE_INPUT_TYPE) != 1:
            raise CatalogCanaryError(
                "Samtools first-wave canary requires exactly one input_file prelude"
            )
        for machine_id in sorted(SAMTOOLS_FIRST_WAVE_MACHINE_IDS):
            if counts.get(machine_id) != 1:
                raise CatalogCanaryError(
                    f"Samtools first-wave canary requires exactly one {machine_id} node"
                )
        expected_count = len(SAMTOOLS_FIRST_WAVE_MACHINE_IDS) + 1
        if len(nodes) != expected_count:
            raise CatalogCanaryError(
                f"Samtools first-wave canary requires exactly {expected_count} executable nodes"
            )

        for node in nodes:
            node_type = node.get("type")
            if not isinstance(node_type, str) or not node_type:
                raise CatalogCanaryError("catalog canary workflow node has no type")
            meta = node.get("meta")
            if not isinstance(meta, Mapping):
                meta = {}
            if any(
                bool(container.get(key))
                for container in (node, meta)
                for key in ("muted", "bypassed", "continueOnFail", "continue_on_fail")
                if isinstance(container, Mapping)
            ):
                raise CatalogCanaryError(
                    f"catalog canary node {node.get('id', node_type)!r} cannot be skipped or continued on failure"
                )
            if node_type == SAMTOOLS_FIRST_WAVE_INPUT_TYPE:
                self._validate_input_prelude(node)
                node[CANARY_NODE_MARKER] = self
                continue
            entry = self._entry(node_type)
            if str(entry.get("node_id")) not in self._profile_node_ids:
                raise CatalogCanaryError(
                    f"node {node_type!r} is outside catalog canary profile {self.profile!r}"
                )
            self._validate_entry(entry)
            node[CANARY_NODE_MARKER] = self

        # Resolve and contract-check the full profile before the pinned input
        # is downloaded or any subprocess is started.
        for machine_id in sorted(SAMTOOLS_FIRST_WAVE_MACHINE_IDS):
            self.resolve(machine_id)

    def metadata(self) -> dict[str, Any]:
        """Return deterministic run metadata for this canary selection."""

        return {
            "profile": self.profile,
            "catalog_digest": self.catalog_digest,
            "required_platform": "linux/amd64",
            "required_environment_lock_sha256": SAMTOOLS_FIRST_WAVE_LOCK_SHA256,
            "required_samtools_package_sha256": SAMTOOLS_FIRST_WAVE_PACKAGE_SHA256,
            "provenance_embedding": False,
            "nodes": {},
        }

    def metadata_class(self, node_type: str) -> type[Any]:
        """Return declared legacy metadata without using the legacy registry."""

        if node_type == SAMTOOLS_FIRST_WAVE_INPUT_TYPE:
            from bionodulo.nodes.builtin.input_family.file import InputFileNode

            return InputFileNode
        return self.resolve(node_type).legacy_metadata

    def resolve(self, node_type: str) -> ResolvedCatalogCanaryNode:
        """Resolve one factory lazily and verify it against generated metadata."""

        entry = self._entry(node_type)
        canonical_id = str(entry["node_id"])
        cached = self._resolved.get(canonical_id)
        if cached is not None:
            return cached

        try:
            resolved = self._registry.resolve_node(node_type, allow_quarantined=True)
        except CatalogRegistryError as error:
            raise CatalogCanaryError(f"cannot resolve catalog canary node {node_type!r}: {error}") from error
        module_name = str(entry["module"])
        module = self._imported_modules.get(module_name)
        if module is None:
            raise CatalogCanaryError(f"catalog importer did not retain module {module_name}")

        factory = resolved.implementation
        spec = getattr(module, "SPEC", None)
        legacy_metadata = getattr(module, "LEGACY_NODE", None)
        if not callable(factory):
            raise CatalogCanaryError(f"catalog factory for {canonical_id} is not callable")
        if not isinstance(spec, NodeSpec):
            raise CatalogCanaryError(f"catalog module {module_name} has no typed SPEC")
        if not isinstance(legacy_metadata, type):
            raise CatalogCanaryError(f"catalog module {module_name} has no LEGACY_NODE metadata")

        contract_digest = spec.contract_digest()
        if contract_digest != entry.get("contract_digest"):
            raise CatalogCanaryError(f"contract digest mismatch for {canonical_id}")
        if spec.identity.stable_id != canonical_id:
            raise CatalogCanaryError(f"stable node ID mismatch for {canonical_id}")
        if spec.identity.machine_id != entry.get("machine_id"):
            raise CatalogCanaryError(f"machine node ID mismatch for {canonical_id}")
        if getattr(legacy_metadata, "NODE_ID", None) != spec.identity.machine_id:
            raise CatalogCanaryError(f"legacy metadata ID mismatch for {canonical_id}")
        if spec.execution_factory != entry.get("execution_factory"):
            raise CatalogCanaryError(f"execution factory mismatch for {canonical_id}")

        value = ResolvedCatalogCanaryNode(
            entry=dict(entry),
            factory=factory,
            spec=spec,
            legacy_metadata=legacy_metadata,
        )
        self._resolved[canonical_id] = value
        return value

    async def execute(
        self,
        *,
        context: Any,
        node: Mapping[str, Any],
        inputs: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Build the attested plan, execute it, and collect typed outputs."""

        node_type = str(node.get("type", ""))
        if node_type == SAMTOOLS_FIRST_WAVE_INPUT_TYPE:
            return await self._execute_input_prelude(
                context=context,
                inputs=inputs,
            )
        resolved = self.resolve(node_type)
        factory_inputs = {
            **dict(inputs),
            **{
                key: value
                for key, value in context.params.items()
                if not str(key).startswith("_")
            },
        }

        output_paths = self._declared_output_paths(resolved.spec, context.node_dir)
        prepare = getattr(resolved.legacy_metadata, "PREPARE_EXECUTION", None)
        if callable(prepare):
            prepare(factory_inputs, output_paths)

        plan = resolved.factory(factory_inputs, output_dir=context.node_dir)
        if not isinstance(plan, ArgvPlan):
            raise CatalogCanaryError(
                f"catalog canary factory for {resolved.entry['node_id']} did not return ArgvPlan"
            )

        node_attestation = {
            "catalog_node_id": resolved.entry["node_id"],
            "machine_id": resolved.entry["machine_id"],
            "status": resolved.entry["status"],
            "execution_factory": resolved.entry["execution_factory"],
            "contract_digest": resolved.entry["contract_digest"],
            "plan_digest": plan.plan_digest(),
        }
        canary_metadata = context.run_metadata.setdefault(CANARY_OPTION, self.metadata())
        node_metadata = canary_metadata.setdefault("nodes", {})
        node_metadata[context.node_id] = node_attestation

        process = await context.run_command(
            list(plan.token_array()),
            cwd=context.node_dir,
            timeout=plan.resources.wall_timeout_seconds,
        )
        collected = collect_outputs(
            resolved.spec.outputs,
            context.node_dir,
            stdout=process.get("stdout"),
            stdout_truncated=process.get("stdout_truncated"),
            conditions=factory_inputs,
        )
        outputs: dict[str, Any] = {}
        for output in collected.outputs:
            paths = [
                str(Path(context.node_dir) / artifact.relative_path)
                for artifact in output.artifacts
            ]
            if output.cardinality in (Cardinality.MANY, Cardinality.NONEMPTY_MANY):
                outputs[output.port_id] = paths
            else:
                outputs[output.port_id] = paths[0] if paths else None
        return {"outputs": outputs, CANARY_OPTION: node_attestation}

    async def _execute_input_prelude(
        self,
        *,
        context: Any,
        inputs: Mapping[str, Any],
    ) -> dict[str, Any]:
        from bionodulo.nodes.builtin.input_family.file import InputFileNode

        kwargs = {
            **dict(inputs),
            **{
                key: value
                for key, value in context.params.items()
                if not str(key).startswith("_")
            },
        }
        raw = await InputFileNode().run(context=context, **kwargs)
        outputs = raw.get("outputs") if isinstance(raw, dict) else None
        output_path = outputs.get("file") if isinstance(outputs, dict) else None
        if not isinstance(output_path, str) or not output_path:
            raise CatalogCanaryError("pinned input_file prelude produced no file output")
        path = Path(output_path)
        try:
            digest = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as error:
            raise CatalogCanaryError(f"cannot attest pinned input file {path}: {error}") from error
        if digest != SAMTOOLS_FIRST_WAVE_INPUT_SHA256:
            path.unlink(missing_ok=True)
            raise CatalogCanaryError("pinned input_file content digest mismatch")

        node_attestation = {
            "kind": "pinned_https_input",
            "source_url": SAMTOOLS_FIRST_WAVE_INPUT_URL,
            "content_digest": digest,
        }
        canary_metadata = context.run_metadata.setdefault(CANARY_OPTION, self.metadata())
        node_metadata = canary_metadata.setdefault("nodes", {})
        node_metadata[context.node_id] = node_attestation
        return {"outputs": {"file": str(path)}, CANARY_OPTION: node_attestation}

    def _entry(self, node_type: str) -> Mapping[str, Any]:
        try:
            return self._registry.entry(node_type)
        except CatalogRegistryError as error:
            raise CatalogCanaryError(
                f"node {node_type!r} is not available in catalog canary profile {self.profile!r}"
            ) from error

    def _validate_entry(self, entry: Mapping[str, Any]) -> None:
        node_id = str(entry.get("node_id", ""))
        machine_id = entry.get("machine_id")
        if machine_id not in SAMTOOLS_FIRST_WAVE_MACHINE_IDS:
            raise CatalogCanaryError(f"node {node_id!r} is not in the Samtools first-wave allowlist")
        status = entry.get("status")
        if status not in _ALLOWED_STATUSES:
            raise CatalogCanaryError(f"node {node_id} has disallowed promotion status {status!r}")
        if entry.get("implementation_status") != "implemented":
            raise CatalogCanaryError(f"node {node_id} is not marked implemented")
        if entry.get("execution_kind") != "argv":
            raise CatalogCanaryError(f"node {node_id} is not an argv implementation")
        contract_digest = entry.get("contract_digest")
        if self._lock_contracts.get(node_id) != contract_digest:
            raise CatalogCanaryError(f"catalog lock contract digest mismatch for {node_id}")
        promotion = self._promotion_entries.get(node_id)
        if not isinstance(promotion, Mapping):
            raise CatalogCanaryError(f"catalog promotion entry is missing for {node_id}")
        for key in (
            "machine_id",
            "status",
            "implementation_status",
            "contract_digest",
            "execution_factory",
        ):
            if promotion.get(key) != entry.get(key):
                raise CatalogCanaryError(f"catalog promotion {key} mismatch for {node_id}")

    @staticmethod
    def _validate_input_prelude(node: Mapping[str, Any]) -> None:
        params = node.get("params")
        if not isinstance(params, Mapping):
            params = node.get("inputs")
        if not isinstance(params, Mapping):
            raise CatalogCanaryError("input_file prelude must declare pinned URL parameters")
        raw_file = params.get("file")
        if isinstance(raw_file, Mapping) and "value" in raw_file:
            raw_file = raw_file.get("value")
        raw_source = params.get("source", "url")
        if isinstance(raw_source, Mapping) and "value" in raw_source:
            raw_source = raw_source.get("value")
        if raw_file != SAMTOOLS_FIRST_WAVE_INPUT_URL:
            raise CatalogCanaryError("input_file prelude URL is not the pinned tiny.sam fixture")
        if raw_source != "url":
            raise CatalogCanaryError("input_file prelude source must be explicitly set to 'url'")

    @staticmethod
    def _declared_output_paths(spec: NodeSpec, root: Path) -> list[Path]:
        paths: list[Path] = []
        for output in spec.outputs:
            relative_path = getattr(output.collector, "relative_path", None)
            if not isinstance(relative_path, str) or not relative_path:
                raise CatalogCanaryError(
                    f"catalog canary output {output.port_id!r} has no concrete relative path"
                )
            paths.append(Path(root) / relative_path)
        return paths


__all__ = [
    "CANARY_NODE_MARKER",
    "CANARY_OPTION",
    "CatalogCanaryError",
    "CatalogCanaryRunner",
    "SAMTOOLS_FIRST_WAVE_CATALOG_DIGEST",
    "SAMTOOLS_FIRST_WAVE_INPUT_SHA256",
    "SAMTOOLS_FIRST_WAVE_INPUT_TYPE",
    "SAMTOOLS_FIRST_WAVE_INPUT_URL",
    "SAMTOOLS_FIRST_WAVE_MACHINE_IDS",
    "SAMTOOLS_FIRST_WAVE_PROFILE",
]
