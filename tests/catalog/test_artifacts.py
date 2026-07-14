import importlib
import json
import os
import subprocess
import sys
import warnings
from pathlib import Path

import pytest
from pydantic import ValidationError

from bionodulo.nodes.catalog.artifacts import ARTIFACT_REGISTRY, ARTIFACT_TYPES
from bionodulo.nodes.contract.artifacts import (
    ArtifactContainer,
    ArtifactPort,
    ArtifactRegistry,
    ArtifactType,
    Cardinality,
    UnknownArtifactTypeError,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def run_fresh_python(source: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPOSITORY_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_artifact_enum_values_are_exact() -> None:
    assert tuple(ArtifactContainer) == (
        ArtifactContainer.FILE,
        ArtifactContainer.DIRECTORY,
    )
    assert tuple(member.value for member in ArtifactContainer) == ("file", "directory")
    assert tuple(member.value for member in Cardinality) == (
        "one",
        "optional_one",
        "many",
        "nonempty_many",
    )


def test_artifact_models_preserve_explicit_tuple_fields() -> None:
    artifact_type = ArtifactType(
        type_id="file.text",
        container=ArtifactContainer.FILE,
        parents=("artifact.file",),
        accepted_sources=("value.string",),
        extensions=(".txt",),
    )
    port = ArtifactPort(
        port_id="input.text",
        artifact_type="file.text",
        cardinality=Cardinality.ONE,
    )

    assert artifact_type.parents == ("artifact.file",)
    assert artifact_type.accepted_sources == ("value.string",)
    assert artifact_type.extensions == (".txt",)
    assert port.artifact_type == "file.text"


def test_value_artifact_has_no_container() -> None:
    artifact_type = ArtifactType(type_id="value.string", container=None)

    assert artifact_type.container is None
    assert artifact_type.parents == ()
    assert artifact_type.accepted_sources == ()
    assert artifact_type.extensions == ()


@pytest.mark.parametrize(
    "type_id",
    (
        "",
        "Artifact.file",
        "BAM LIST",
        "1artifact",
        "artifact/file",
        " artifact.file",
        "artifact.file ",
        "artifact.file\n",
    ),
)
def test_artifact_type_rejects_invalid_ids_without_normalizing(type_id: str) -> None:
    with pytest.raises(ValidationError):
        ArtifactType(type_id=type_id, container=ArtifactContainer.FILE)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("parents", ("Artifact.file",)),
        ("accepted_sources", ("value/string",)),
    ),
)
def test_artifact_type_references_use_the_same_id_contract(field: str, value: tuple[str, ...]) -> None:
    with pytest.raises(ValidationError):
        ArtifactType(
            type_id="file.text",
            container=ArtifactContainer.FILE,
            **{field: value},
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("port_id", "Input"),
        ("artifact_type", "file/text"),
    ),
)
def test_artifact_port_fields_use_the_same_id_contract(field: str, value: str) -> None:
    values = {
        "port_id": "input",
        "artifact_type": "file.text",
        "cardinality": Cardinality.ONE,
    }
    values[field] = value

    with pytest.raises(ValidationError):
        ArtifactPort(**values)


@pytest.mark.parametrize("model", (ArtifactType, ArtifactPort))
def test_artifact_models_have_the_exact_strict_frozen_config(model: type) -> None:
    assert model.model_config["extra"] == "forbid"
    assert model.model_config["frozen"] is True
    assert model.model_config["strict"] is True
    assert model.model_config["validate_default"] is True


def test_artifact_models_reject_extras_and_mutation() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ArtifactType(
            type_id="artifact.file",
            container=ArtifactContainer.FILE,
            unexpected=True,
        )

    artifact_type = ArtifactType(
        type_id="file.text",
        container=ArtifactContainer.FILE,
        parents=("artifact.file",),
    )
    with pytest.raises(ValidationError, match="frozen_instance"):
        artifact_type.type_id = "file.other"
    with pytest.raises(ValidationError, match="frozen_instance"):
        artifact_type.parents += ("file.other",)


def test_artifact_models_reject_coercion_and_mutable_collections() -> None:
    with pytest.raises(ValidationError):
        ArtifactType(type_id="artifact.file", container="file")
    with pytest.raises(ValidationError):
        ArtifactType(
            type_id="file.text",
            container=ArtifactContainer.FILE,
            parents=["artifact.file"],
        )
    with pytest.raises(ValidationError):
        ArtifactPort(
            port_id="input",
            artifact_type="file.text",
            cardinality="one",
        )


@pytest.mark.parametrize(
    "update",
    (
        {"type_id": "BAD"},
        {"parents": ["artifact.file"]},
        {"accepted_sources": ["value.string"]},
        {"extensions": [".txt"]},
        {"container": ArtifactContainer.DIRECTORY, "extensions": (".txt",)},
    ),
)
def test_artifact_type_copy_revalidates_updates(update: dict[str, object]) -> None:
    artifact_type = ArtifactType(
        type_id="file.text",
        container=ArtifactContainer.FILE,
    )

    with pytest.raises(ValidationError):
        artifact_type.model_copy(update=update)


@pytest.mark.parametrize(
    "update",
    (
        {"port_id": "BAD"},
        {"artifact_type": "file/text"},
        {"cardinality": "many"},
    ),
)
def test_artifact_port_copy_revalidates_updates(update: dict[str, object]) -> None:
    port = ArtifactPort(
        port_id="input",
        artifact_type="file.text",
        cardinality=Cardinality.ONE,
    )

    with pytest.raises(ValidationError):
        port.model_copy(update=update)


def test_artifact_registry_copy_rejects_mutable_and_invalid_graph_updates() -> None:
    root = ArtifactType(
        type_id="artifact.file",
        container=ArtifactContainer.FILE,
    )
    registry = ArtifactRegistry(types=(root,))
    missing_parent = ArtifactType(
        type_id="file.text",
        container=ArtifactContainer.FILE,
        parents=("artifact.missing",),
    )
    self_cycle = ArtifactType(
        type_id="cycle.self",
        container=ArtifactContainer.FILE,
        parents=("cycle.self",),
    )
    multi_cycle = (
        ArtifactType(
            type_id="cycle.a",
            container=ArtifactContainer.FILE,
            parents=("cycle.b",),
        ),
        ArtifactType(
            type_id="cycle.b",
            container=ArtifactContainer.FILE,
            parents=("cycle.a",),
        ),
    )

    with pytest.raises(ValidationError):
        registry.model_copy(update={"types": [root]})
    with pytest.raises(ValidationError, match="missing parent"):
        registry.model_copy(update={"types": (missing_parent,)})
    with pytest.raises(ValidationError, match="cannot parent itself"):
        registry.model_copy(update={"types": (self_cycle,)})
    with pytest.raises(ValidationError, match="parent cycle detected"):
        registry.model_copy(update={"types": multi_cycle})


def test_nested_constructed_artifact_is_revalidated_by_registry() -> None:
    invalid = ArtifactType.model_construct(
        type_id="BAD",
        container=ArtifactContainer.FILE,
        parents=[],
        accepted_sources=(),
        extensions=(),
    )

    with pytest.raises(ValidationError):
        ArtifactRegistry(types=(invalid,))

    constructed_registry = ArtifactRegistry.model_construct(types=(invalid,))
    with pytest.raises(ValidationError):
        ArtifactRegistry.model_validate(constructed_registry)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(ValidationError):
            invalid.model_copy()
    assert caught == []


def test_validated_copies_preserve_values_subclasses_and_fresh_registry_state() -> None:
    class SpecializedArtifactType(ArtifactType):
        label: str

    specialized = SpecializedArtifactType(
        type_id="file.text",
        container=ArtifactContainer.FILE,
        label="Text",
    )
    updated_type = specialized.model_copy(
        update={"type_id": "file.plain", "label": "Plain text"}
    )
    port = ArtifactPort(
        port_id="input",
        artifact_type="file.text",
        cardinality=Cardinality.ONE,
    )
    updated_port = port.model_copy(update={"cardinality": Cardinality.MANY})
    original_registry = ArtifactRegistry(
        types=(
            ArtifactType(
                type_id="artifact.file",
                container=ArtifactContainer.FILE,
            ),
            ArtifactType(
                type_id="file.text",
                container=ArtifactContainer.FILE,
                parents=("artifact.file",),
            ),
        )
    )
    replacement_types = (
        ArtifactType(type_id="value.string", container=None),
        ArtifactType(
            type_id="value.label",
            container=None,
            parents=("value.string",),
        ),
    )
    updated_registry = original_registry.model_copy(
        update={"types": replacement_types}
    )

    assert isinstance(updated_type, SpecializedArtifactType)
    assert updated_type.type_id == "file.plain"
    assert updated_type.label == "Plain text"
    assert updated_port.cardinality is Cardinality.MANY
    assert updated_registry.is_type_compatible("value.label", "value.string")
    with pytest.raises(UnknownArtifactTypeError):
        updated_registry.is_type_compatible("file.text", "artifact.file")
    assert original_registry.is_type_compatible("file.text", "artifact.file")
    assert original_registry.model_copy() == original_registry
    assert original_registry.model_copy(deep=True) == original_registry


@pytest.mark.parametrize(
    "extension",
    ("", "txt", ".", "..txt", ".tar.", ".bad/path", " .txt", ".txt "),
)
def test_artifact_type_rejects_invalid_extension_syntax(extension: str) -> None:
    with pytest.raises(ValidationError, match="extension"):
        ArtifactType(
            type_id="file.text",
            container=ArtifactContainer.FILE,
            extensions=(extension,),
        )


def test_artifact_type_accepts_simple_and_compound_extensions() -> None:
    artifact_type = ArtifactType(
        type_id="file.archive",
        container=ArtifactContainer.FILE,
        extensions=(".txt", ".tar.gz", ".RData"),
    )

    assert artifact_type.extensions == (".txt", ".tar.gz", ".RData")


@pytest.mark.parametrize("container", (ArtifactContainer.DIRECTORY, None))
def test_only_file_artifacts_can_declare_extensions(
    container: ArtifactContainer | None,
) -> None:
    with pytest.raises(ValidationError, match="file artifacts"):
        ArtifactType(
            type_id="artifact.invalid",
            container=container,
            extensions=(".txt",),
        )


def test_artifact_registry_preserves_an_explicit_type_tuple() -> None:
    artifact_types = (
        ArtifactType(type_id="artifact.file", container=ArtifactContainer.FILE),
        ArtifactType(
            type_id="file.text",
            container=ArtifactContainer.FILE,
            parents=("artifact.file",),
        ),
    )

    registry = ArtifactRegistry(types=artifact_types)

    assert registry.types == artifact_types


def test_artifact_registry_is_a_strict_frozen_value_object() -> None:
    artifact_types = (
        ArtifactType(type_id="artifact.file", container=ArtifactContainer.FILE),
    )
    first = ArtifactRegistry(types=artifact_types)
    second = ArtifactRegistry(types=artifact_types)

    assert first == second
    assert hash(first) == hash(second)
    assert first.model_config["extra"] == "forbid"
    assert first.model_config["frozen"] is True
    assert first.model_config["strict"] is True
    assert first.model_config["validate_default"] is True
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ArtifactRegistry(types=artifact_types, unexpected=True)
    with pytest.raises(ValidationError):
        ArtifactRegistry(types=list(artifact_types))
    with pytest.raises(ValidationError, match="frozen_instance"):
        first.types = ()


def test_registry_rejects_duplicate_type_ids() -> None:
    duplicate = ArtifactType(
        type_id="artifact.file",
        container=ArtifactContainer.FILE,
    )

    with pytest.raises(ValidationError, match="duplicate artifact type ID: artifact.file"):
        ArtifactRegistry(types=(duplicate, duplicate))


@pytest.mark.parametrize(
    ("field", "message"),
    (
        ("parents", "duplicate parent: artifact.file"),
        ("accepted_sources", "duplicate accepted source: artifact.file"),
    ),
)
def test_registry_rejects_duplicate_direct_references(field: str, message: str) -> None:
    root = ArtifactType(
        type_id="artifact.file",
        container=ArtifactContainer.FILE,
    )
    child = ArtifactType(
        type_id="file.text",
        container=ArtifactContainer.FILE,
        **{field: ("artifact.file", "artifact.file")},
    )

    with pytest.raises(ValidationError, match=message):
        ArtifactRegistry(types=(root, child))


@pytest.mark.parametrize(
    ("field", "message"),
    (
        ("parents", "missing parent: artifact.file"),
        ("accepted_sources", "missing accepted source: value.string"),
    ),
)
def test_registry_rejects_missing_references(field: str, message: str) -> None:
    reference = "artifact.file" if field == "parents" else "value.string"
    artifact_type = ArtifactType(
        type_id="file.text",
        container=ArtifactContainer.FILE,
        **{field: (reference,)},
    )

    with pytest.raises(ValidationError, match=message):
        ArtifactRegistry(types=(artifact_type,))


def test_registry_rejects_self_parent_cycles() -> None:
    artifact_type = ArtifactType(
        type_id="artifact.file",
        container=ArtifactContainer.FILE,
        parents=("artifact.file",),
    )

    with pytest.raises(ValidationError, match="cannot parent itself"):
        ArtifactRegistry(types=(artifact_type,))


def test_registry_rejects_multi_node_parent_cycles() -> None:
    artifact_types = (
        ArtifactType(
            type_id="cycle.a",
            container=ArtifactContainer.FILE,
            parents=("cycle.b",),
        ),
        ArtifactType(
            type_id="cycle.b",
            container=ArtifactContainer.FILE,
            parents=("cycle.c",),
        ),
        ArtifactType(
            type_id="cycle.c",
            container=ArtifactContainer.FILE,
            parents=("cycle.a",),
        ),
    )

    with pytest.raises(ValidationError, match="parent cycle detected"):
        ArtifactRegistry(types=artifact_types)


def test_registry_accepts_a_diamond_parent_dag() -> None:
    artifact_types = (
        ArtifactType(type_id="artifact.file", container=ArtifactContainer.FILE),
        ArtifactType(
            type_id="file.left",
            container=ArtifactContainer.FILE,
            parents=("artifact.file",),
        ),
        ArtifactType(
            type_id="file.right",
            container=ArtifactContainer.FILE,
            parents=("artifact.file",),
        ),
        ArtifactType(
            type_id="file.leaf",
            container=ArtifactContainer.FILE,
            parents=("file.left", "file.right"),
        ),
    )

    registry = ArtifactRegistry(types=artifact_types)

    assert registry.types == artifact_types


@pytest.mark.parametrize(
    ("child_container", "parent_container"),
    (
        (ArtifactContainer.FILE, ArtifactContainer.DIRECTORY),
        (ArtifactContainer.DIRECTORY, ArtifactContainer.FILE),
        (None, ArtifactContainer.FILE),
        (ArtifactContainer.FILE, None),
    ),
)
def test_registry_rejects_incompatible_container_ancestry(
    child_container: ArtifactContainer | None,
    parent_container: ArtifactContainer | None,
) -> None:
    artifact_types = (
        ArtifactType(type_id="artifact.parent", container=parent_container),
        ArtifactType(
            type_id="artifact.child",
            container=child_container,
            parents=("artifact.parent",),
        ),
    )

    with pytest.raises(ValidationError, match="incompatible container ancestry"):
        ArtifactRegistry(types=artifact_types)


def compatibility_registry() -> ArtifactRegistry:
    return ArtifactRegistry(
        types=(
            ArtifactType(
                type_id="artifact.file",
                container=ArtifactContainer.FILE,
            ),
            ArtifactType(
                type_id="file.text",
                container=ArtifactContainer.FILE,
                parents=("artifact.file",),
                accepted_sources=("value.string",),
            ),
            ArtifactType(
                type_id="report.html",
                container=ArtifactContainer.FILE,
                parents=("file.text",),
            ),
            ArtifactType(
                type_id="file.markdown",
                container=ArtifactContainer.FILE,
                parents=("file.text",),
            ),
            ArtifactType(
                type_id="file.textual",
                container=ArtifactContainer.FILE,
            ),
            ArtifactType(type_id="value.string", container=None),
        )
    )


def artifact_port(
    artifact_type: str,
    cardinality: Cardinality = Cardinality.ONE,
) -> ArtifactPort:
    return ArtifactPort(
        port_id="port",
        artifact_type=artifact_type,
        cardinality=cardinality,
    )


@pytest.mark.parametrize(
    ("source_type", "target_type"),
    (
        ("file.text", "file.text"),
        ("report.html", "file.text"),
        ("report.html", "artifact.file"),
    ),
)
def test_type_compatibility_accepts_equality_and_source_ancestry(
    source_type: str,
    target_type: str,
) -> None:
    registry = compatibility_registry()

    assert registry.is_type_compatible(source_type, target_type) is True


@pytest.mark.parametrize(
    ("source_type", "target_type"),
    (
        ("artifact.file", "report.html"),
        ("report.html", "file.markdown"),
        ("file.markdown", "report.html"),
        ("file.textual", "file.text"),
    ),
)
def test_type_compatibility_does_not_reverse_or_infer_families(
    source_type: str,
    target_type: str,
) -> None:
    registry = compatibility_registry()

    assert registry.is_type_compatible(source_type, target_type) is False


def test_accepted_source_compatibility_is_explicit_and_directional() -> None:
    registry = compatibility_registry()

    assert registry.is_type_compatible("value.string", "file.text") is True
    assert registry.is_type_compatible("file.text", "value.string") is False


@pytest.mark.parametrize(
    ("source_type", "target_type", "message"),
    (
        ("missing.source", "file.text", "unknown source artifact type ID: missing.source"),
        ("file.text", "missing.target", "unknown target artifact type ID: missing.target"),
    ),
)
def test_type_compatibility_fails_closed_for_unknown_ids(
    source_type: str,
    target_type: str,
    message: str,
) -> None:
    with pytest.raises(UnknownArtifactTypeError) as caught:
        compatibility_registry().is_type_compatible(source_type, target_type)

    assert type(caught.value) is UnknownArtifactTypeError
    assert str(caught.value) == message


CARDINALITY_CASES = (
    (Cardinality.ONE, Cardinality.ONE, True),
    (Cardinality.ONE, Cardinality.OPTIONAL_ONE, True),
    (Cardinality.ONE, Cardinality.MANY, True),
    (Cardinality.ONE, Cardinality.NONEMPTY_MANY, True),
    (Cardinality.OPTIONAL_ONE, Cardinality.ONE, False),
    (Cardinality.OPTIONAL_ONE, Cardinality.OPTIONAL_ONE, True),
    (Cardinality.OPTIONAL_ONE, Cardinality.MANY, True),
    (Cardinality.OPTIONAL_ONE, Cardinality.NONEMPTY_MANY, False),
    (Cardinality.MANY, Cardinality.ONE, False),
    (Cardinality.MANY, Cardinality.OPTIONAL_ONE, False),
    (Cardinality.MANY, Cardinality.MANY, True),
    (Cardinality.MANY, Cardinality.NONEMPTY_MANY, False),
    (Cardinality.NONEMPTY_MANY, Cardinality.ONE, False),
    (Cardinality.NONEMPTY_MANY, Cardinality.OPTIONAL_ONE, False),
    (Cardinality.NONEMPTY_MANY, Cardinality.MANY, True),
    (Cardinality.NONEMPTY_MANY, Cardinality.NONEMPTY_MANY, True),
)


@pytest.mark.parametrize(
    ("source_cardinality", "target_cardinality", "expected"),
    CARDINALITY_CASES,
)
def test_all_cardinality_compatibility_pairs(
    source_cardinality: Cardinality,
    target_cardinality: Cardinality,
    expected: bool,
) -> None:
    registry = compatibility_registry()

    assert (
        registry.is_cardinality_compatible(source_cardinality, target_cardinality)
        is expected
    )


@pytest.mark.parametrize(
    ("source_type", "source_cardinality", "target_type", "target_cardinality", "expected"),
    (
        ("report.html", Cardinality.ONE, "file.text", Cardinality.ONE, True),
        ("report.html", Cardinality.MANY, "file.text", Cardinality.ONE, False),
        ("file.text", Cardinality.ONE, "report.html", Cardinality.ONE, False),
    ),
)
def test_can_connect_requires_type_and_cardinality_compatibility(
    source_type: str,
    source_cardinality: Cardinality,
    target_type: str,
    target_cardinality: Cardinality,
    expected: bool,
) -> None:
    source = artifact_port(source_type, source_cardinality)
    target = artifact_port(target_type, target_cardinality)

    assert compatibility_registry().can_connect(source, target) is expected


def test_can_connect_fails_closed_for_an_unknown_port_type() -> None:
    source = artifact_port("missing.source")
    target = artifact_port("artifact.file")

    with pytest.raises(UnknownArtifactTypeError) as caught:
        compatibility_registry().can_connect(source, target)

    assert str(caught.value) == "unknown source artifact type ID: missing.source"


def test_seed_catalog_contains_exactly_five_explicit_types() -> None:
    assert isinstance(ARTIFACT_TYPES, tuple)
    assert tuple(artifact.type_id for artifact in ARTIFACT_TYPES) == (
        "artifact.file",
        "artifact.directory",
        "file.text",
        "report.html",
        "value.string",
    )
    assert ARTIFACT_REGISTRY.types == ARTIFACT_TYPES


def test_seed_catalog_declares_exact_ancestry_and_containers() -> None:
    types_by_id = {artifact.type_id: artifact for artifact in ARTIFACT_TYPES}

    assert types_by_id["artifact.file"].container is ArtifactContainer.FILE
    assert types_by_id["artifact.file"].parents == ()
    assert (
        types_by_id["artifact.directory"].container
        is ArtifactContainer.DIRECTORY
    )
    assert types_by_id["artifact.directory"].parents == ()
    assert types_by_id["file.text"].container is ArtifactContainer.FILE
    assert types_by_id["file.text"].parents == ("artifact.file",)
    assert types_by_id["report.html"].container is ArtifactContainer.FILE
    assert types_by_id["report.html"].parents == ("file.text",)
    assert types_by_id["value.string"].container is None
    assert types_by_id["value.string"].parents == ()


def test_seed_catalog_has_no_implicit_legacy_or_wildcard_types() -> None:
    seed_ids = {artifact.type_id for artifact in ARTIFACT_TYPES}

    assert len(seed_ids) == 5
    assert "*" not in seed_ids
    assert "any" not in seed_ids
    assert all(artifact.accepted_sources == () for artifact in ARTIFACT_TYPES)


@pytest.mark.parametrize(
    "model",
    (
        ArtifactType(
            type_id="file.text",
            container=ArtifactContainer.FILE,
            parents=("artifact.file",),
            extensions=(".txt",),
        ),
        ArtifactPort(
            port_id="input",
            artifact_type="file.text",
            cardinality=Cardinality.NONEMPTY_MANY,
        ),
        ARTIFACT_REGISTRY,
    ),
    ids=("artifact-type", "artifact-port", "artifact-registry"),
)
def test_strict_python_payloads_reject_json_forms_but_json_roundtrips(model: object) -> None:
    model_type = type(model)
    json_payload = model.model_dump_json()
    python_payload = json.loads(json_payload)

    with pytest.raises(ValidationError):
        model_type.model_validate(python_payload)

    assert model_type.model_validate_json(json_payload) == model


def test_registry_serialization_contains_only_declared_type_state() -> None:
    assert ARTIFACT_REGISTRY.is_type_compatible("report.html", "artifact.file")

    dumped = ARTIFACT_REGISTRY.model_dump(mode="python")

    assert tuple(dumped) == ("types",)
    assert len(dumped["types"]) == 5


def test_contract_package_reexports_artifact_symbols() -> None:
    contract = importlib.import_module("bionodulo.nodes.contract")

    assert contract.ArtifactContainer is ArtifactContainer
    assert contract.ArtifactPort is ArtifactPort
    assert contract.ArtifactRegistry is ArtifactRegistry
    assert contract.ArtifactType is ArtifactType
    assert contract.Cardinality is Cardinality


def test_catalog_artifacts_imports_without_a_catalog_initializer() -> None:
    catalog_artifacts = importlib.import_module("bionodulo.nodes.catalog.artifacts")

    assert catalog_artifacts.ARTIFACT_TYPES is ARTIFACT_TYPES
    assert catalog_artifacts.ARTIFACT_REGISTRY is ARTIFACT_REGISTRY


@pytest.mark.parametrize(
    "module_name",
    (
        "bionodulo.nodes.contract.artifacts",
        "bionodulo.nodes.catalog.artifacts",
    ),
)
def test_artifact_imports_do_not_load_or_register_legacy_nodes(
    module_name: str,
) -> None:
    result = run_fresh_python(
        f"""
import importlib
import sys

legacy_modules = (
    "bionodulo.nodes.base",
    "bionodulo.nodes.command_node",
    "bionodulo.nodes.registry",
    "bionodulo.nodes.schema_api",
)
importlib.import_module({module_name!r})
loaded = tuple(name for name in legacy_modules if name in sys.modules)
assert loaded == (), loaded

from bionodulo.nodes.base import BaseNode

assert BaseNode._SUBCLASSES == [], BaseNode._SUBCLASSES
"""
    )

    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"


def test_legacy_node_package_exports_resolve_lazily_on_demand() -> None:
    result = run_fresh_python(
        """
import sys

import bionodulo.nodes as nodes

legacy_modules = (
    "bionodulo.nodes.base",
    "bionodulo.nodes.command_node",
    "bionodulo.nodes.registry",
    "bionodulo.nodes.schema_api",
)
assert tuple(name for name in legacy_modules if name in sys.modules) == ()
assert nodes.__all__ == ["BaseNode", "CommandNode", "NodeRegistry", "io", "ui"]
assert not hasattr(nodes, "ArtifactType")

from bionodulo.nodes import BaseNode, CommandNode, NodeRegistry, io, ui

assert BaseNode.__module__ == "bionodulo.nodes.base"
assert CommandNode.__module__ == "bionodulo.nodes.command_node"
assert NodeRegistry.__module__ == "bionodulo.nodes.registry"
assert io.__module__ == "bionodulo.nodes.schema_api"
assert ui.__module__ == "bionodulo.nodes.schema_api"
assert CommandNode in BaseNode._SUBCLASSES
assert all(name in sys.modules for name in legacy_modules)
assert nodes.BaseNode is BaseNode
assert nodes.CommandNode is CommandNode
assert nodes.NodeRegistry is NodeRegistry
assert nodes.io is io
assert nodes.ui is ui
"""
    )

    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
