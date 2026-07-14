import importlib

import pytest
from pydantic import ValidationError

from bionodulo.nodes.catalog.artifacts import ARTIFACT_REGISTRY, ARTIFACT_TYPES
from bionodulo.nodes.contract.artifacts import (
    ArtifactContainer,
    ArtifactPort,
    ArtifactRegistry,
    ArtifactType,
    Cardinality,
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
    with pytest.raises(ValueError, match=message):
        compatibility_registry().is_type_compatible(source_type, target_type)


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

    with pytest.raises(ValueError, match="unknown source artifact type ID"):
        compatibility_registry().can_connect(source, target)


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
