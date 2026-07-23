from __future__ import annotations

from types import SimpleNamespace

import pytest

from bionodulo.nodes.catalog.registry import (
    CatalogRegistry,
    QuarantinedNodeError,
    UnknownNodeError,
)
from bionodulo.nodes.contract.compiler import CatalogCompiler, CatalogError
from bionodulo.nodes.contract.model import (
    ExecutionKind,
    NodeIdentity,
    NodeOwnership,
    NodePresentation,
    NodeSpec,
)
from bionodulo.nodes.contract.parameters import ParameterSpec, ValueKind


def _samtools_compiled():
    from bionodulo.nodes.catalog.tools.samtools.artifacts import SAMTOOLS_ARTIFACT_REGISTRY
    from bionodulo.nodes.catalog.tools.samtools import SPECS

    return CatalogCompiler(artifact_registry=SAMTOOLS_ARTIFACT_REGISTRY).compile(SPECS)


def _spec(*, stable_id: str = "legacy::String Value", machine_id: str = "string_primitive") -> NodeSpec:
    return NodeSpec(
        identity=NodeIdentity(
            stable_id=stable_id,
            machine_id=machine_id,
            contract_version="2.0.0",
            implementation_version="1.0.0",
        ),
        presentation=NodePresentation(
            display_name="String",
            description="Emit a string.",
            palette_path=("Core", "Values"),
            domain_tags=("core",),
            operation_kind="source",
            owner=NodeOwnership.BIONODULO_CORE,
        ),
        parameters=(ParameterSpec(parameter_id="value", kind=ValueKind.STRING, required=True),),
        execution_kind=ExecutionKind.PYTHON,
        execution_factory="bionodulo.nodes.catalog.core.values.string:build_plan",
    )


def test_compiler_rejects_duplicate_ids_and_digest_is_stable() -> None:
    compiler = CatalogCompiler()
    spec = _spec()
    with pytest.raises(CatalogError, match="duplicate node_id"):
        compiler.compile((spec, spec))
    first = compiler.compile((spec,))
    second = compiler.compile((spec,))
    assert first.catalog_digest == second.catalog_digest
    assert first.node_index["catalog_digest"] == first.catalog_digest


def test_compile_modules_fails_closed_on_import_error() -> None:
    def broken_importer(_module_name: str) -> object:
        raise RuntimeError("broken")

    with pytest.raises(CatalogError, match="broken"):
        CatalogCompiler(importer=broken_importer).compile_modules(("bad.module",))


def test_registry_is_lazy_and_requires_explicit_quarantine_override() -> None:
    spec = _spec()
    compiled = CatalogCompiler().compile((spec,))
    imported: list[str] = []

    def importer(name: str) -> object:
        imported.append(name)
        return SimpleNamespace(build_plan=lambda **kwargs: kwargs)

    registry = CatalogRegistry(compiled, importer=importer)
    assert imported == []
    with pytest.raises(QuarantinedNodeError):
        registry.resolve("string_primitive")
    assert imported == []

    implementation = registry.resolve("string_primitive", allow_quarantined=True)
    assert implementation(value="ok") == {"value": "ok"}
    assert imported == ["bionodulo.nodes.catalog.core.values.string"]


def test_registry_unknown_ids_never_fall_back_to_legacy() -> None:
    registry = CatalogRegistry(CatalogCompiler().compile((_spec(),)), allow_quarantined=True)
    with pytest.raises(UnknownNodeError):
        registry.resolve("not_a_node")


def test_promotion_candidates_require_explicit_promotion_override() -> None:
    compiled = _samtools_compiled()
    imported: list[str] = []

    def importer(name: str) -> object:
        imported.append(name)
        module = __import__(name, fromlist=["build_plan"])
        return module

    registry = CatalogRegistry(compiled, importer=importer)
    with pytest.raises(QuarantinedNodeError):
        registry.resolve("samtools_view")
    assert imported == []
    resolved = registry.resolve("samtools_view", allow_quarantined=True)
    assert resolved is not None
    assert imported == ["bionodulo.nodes.catalog.tools.samtools.view"]
    assert registry.entry("samtools_view")["status"] == "promotion_candidate"


def test_unknown_status_stays_fail_closed() -> None:
    spec = _spec()
    compiled = CatalogCompiler().compile((spec,))
    runtime = {**compiled.runtime, "nodes": {**compiled.runtime["nodes"], spec.identity.stable_id: {
        **compiled.runtime["nodes"][spec.identity.stable_id], "status": "future"
    }}}
    index = {**compiled.node_index, "nodes": {**compiled.node_index["nodes"], spec.identity.stable_id: {
        **compiled.node_index["nodes"][spec.identity.stable_id], "status": "future"
    }}}
    registry = CatalogRegistry.from_documents(index, runtime)
    with pytest.raises(QuarantinedNodeError):
        registry.resolve(spec.identity.stable_id)
