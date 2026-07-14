import re
from collections.abc import Mapping
from copy import deepcopy
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Any, Final, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    PrivateAttr,
    StringConstraints,
    model_validator,
)


ARTIFACT_ID_PATTERN = r"^[a-z][a-z0-9_.-]*$"
_ARTIFACT_ID_RE = re.compile(ARTIFACT_ID_PATTERN)
_EXTENSION_RE = re.compile(
    r"^\.[A-Za-z0-9][A-Za-z0-9_+-]*(?:\.[A-Za-z0-9][A-Za-z0-9_+-]*)*$"
)
_STRICT_MODEL_CONFIG = ConfigDict(
    extra="forbid",
    frozen=True,
    revalidate_instances="always",
    strict=True,
    validate_default=True,
)


def _require_full_artifact_id_match(value: str) -> str:
    if _ARTIFACT_ID_RE.fullmatch(value) is None:
        raise ValueError(f"must match {ARTIFACT_ID_PATTERN}")
    return value


ArtifactId = Annotated[
    str,
    StringConstraints(pattern=ARTIFACT_ID_PATTERN),
    AfterValidator(_require_full_artifact_id_match),
]


class _StrictFrozenModel(BaseModel):
    """Strict value model; ``model_construct`` remains a trusted-only escape hatch."""

    model_config = _STRICT_MODEL_CONFIG

    def model_copy(
        self,
        *,
        update: Mapping[str, Any] | None = None,
        deep: bool = False,
    ) -> Self:
        validated = type(self).model_validate(self)
        values = validated.model_dump(mode="python", round_trip=True)
        if deep:
            values = deepcopy(values)
        if update is not None:
            values.update(update)
        return type(self).model_validate(values)


class ArtifactContainer(StrEnum):
    FILE = "file"
    DIRECTORY = "directory"


class Cardinality(StrEnum):
    ONE = "one"
    OPTIONAL_ONE = "optional_one"
    MANY = "many"
    NONEMPTY_MANY = "nonempty_many"


CARDINALITY_COMPATIBILITY: Final[
    Mapping[tuple[Cardinality, Cardinality], bool]
] = MappingProxyType(
    {
        (Cardinality.ONE, Cardinality.ONE): True,
        (Cardinality.ONE, Cardinality.OPTIONAL_ONE): True,
        (Cardinality.ONE, Cardinality.MANY): True,
        (Cardinality.ONE, Cardinality.NONEMPTY_MANY): True,
        (Cardinality.OPTIONAL_ONE, Cardinality.ONE): False,
        (Cardinality.OPTIONAL_ONE, Cardinality.OPTIONAL_ONE): True,
        (Cardinality.OPTIONAL_ONE, Cardinality.MANY): True,
        (Cardinality.OPTIONAL_ONE, Cardinality.NONEMPTY_MANY): False,
        (Cardinality.MANY, Cardinality.ONE): False,
        (Cardinality.MANY, Cardinality.OPTIONAL_ONE): False,
        (Cardinality.MANY, Cardinality.MANY): True,
        (Cardinality.MANY, Cardinality.NONEMPTY_MANY): False,
        (Cardinality.NONEMPTY_MANY, Cardinality.ONE): False,
        (Cardinality.NONEMPTY_MANY, Cardinality.OPTIONAL_ONE): False,
        (Cardinality.NONEMPTY_MANY, Cardinality.MANY): True,
        (Cardinality.NONEMPTY_MANY, Cardinality.NONEMPTY_MANY): True,
    }
)


class UnknownArtifactTypeError(ValueError):
    """Raised when compatibility is requested for an unregistered type."""


class ArtifactType(_StrictFrozenModel):
    type_id: ArtifactId
    container: ArtifactContainer | None
    parents: tuple[ArtifactId, ...] = ()
    accepted_sources: tuple[ArtifactId, ...] = ()
    extensions: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate_extensions(self) -> Self:
        for extension in self.extensions:
            if _EXTENSION_RE.fullmatch(extension) is None:
                raise ValueError(f"invalid artifact extension: {extension!r}")
        if self.extensions and self.container is not ArtifactContainer.FILE:
            raise ValueError("only file artifacts can declare extensions")
        return self


class ArtifactPort(_StrictFrozenModel):
    port_id: ArtifactId
    artifact_type: ArtifactId
    cardinality: Cardinality


class ArtifactRegistry(_StrictFrozenModel):
    types: tuple[ArtifactType, ...]
    _type_index: Mapping[str, ArtifactType] = PrivateAttr()
    _ancestor_closure: Mapping[str, frozenset[str]] = PrivateAttr()

    def is_type_compatible(
        self,
        source_type_id: ArtifactId,
        target_type_id: ArtifactId,
    ) -> bool:
        source = self._require_registered_type(
            source_type_id,
            role="source",
            types_by_id=self._type_index,
        )
        target = self._require_registered_type(
            target_type_id,
            role="target",
            types_by_id=self._type_index,
        )

        if source.type_id == target.type_id:
            return True
        if source.type_id in target.accepted_sources:
            return True

        return target.type_id in self._ancestor_closure[source.type_id]

    @staticmethod
    def is_cardinality_compatible(
        source: Cardinality,
        target: Cardinality,
    ) -> bool:
        return CARDINALITY_COMPATIBILITY[(source, target)]

    def can_connect(self, source: ArtifactPort, target: ArtifactPort) -> bool:
        return self.is_type_compatible(
            source.artifact_type,
            target.artifact_type,
        ) and self.is_cardinality_compatible(
            source.cardinality,
            target.cardinality,
        )

    @staticmethod
    def _require_registered_type(
        type_id: str,
        *,
        role: str,
        types_by_id: Mapping[str, ArtifactType],
    ) -> ArtifactType:
        try:
            return types_by_id[type_id]
        except KeyError as error:
            raise UnknownArtifactTypeError(
                f"unknown {role} artifact type ID: {type_id}"
            ) from error

    @model_validator(mode="after")
    def _validate_type_graph(self) -> Self:
        types_by_id: dict[str, ArtifactType] = {}
        for artifact_type in self.types:
            if artifact_type.type_id in types_by_id:
                raise ValueError(
                    f"duplicate artifact type ID: {artifact_type.type_id}"
                )
            types_by_id[artifact_type.type_id] = artifact_type

        for artifact_type in self.types:
            self._validate_direct_references(artifact_type, types_by_id)

        self._validate_parent_graph_is_acyclic(types_by_id)
        self._type_index = MappingProxyType(dict(types_by_id))
        self._ancestor_closure = MappingProxyType(
            {
                type_id: self._collect_ancestors(type_id, types_by_id)
                for type_id in types_by_id
            }
        )
        return self

    @staticmethod
    def _collect_ancestors(
        type_id: str,
        types_by_id: Mapping[str, ArtifactType],
    ) -> frozenset[str]:
        ancestors: set[str] = set()
        pending = list(types_by_id[type_id].parents)
        while pending:
            parent_id = pending.pop()
            if parent_id not in ancestors:
                ancestors.add(parent_id)
                pending.extend(types_by_id[parent_id].parents)
        return frozenset(ancestors)

    @staticmethod
    def _validate_direct_references(
        artifact_type: ArtifactType,
        types_by_id: Mapping[str, ArtifactType],
    ) -> None:
        duplicate_parent = _first_duplicate(artifact_type.parents)
        if duplicate_parent is not None:
            raise ValueError(
                f"artifact type {artifact_type.type_id} has duplicate parent: "
                f"{duplicate_parent}"
            )

        duplicate_source = _first_duplicate(artifact_type.accepted_sources)
        if duplicate_source is not None:
            raise ValueError(
                f"artifact type {artifact_type.type_id} has duplicate accepted source: "
                f"{duplicate_source}"
            )

        for parent_id in artifact_type.parents:
            parent = types_by_id.get(parent_id)
            if parent is None:
                raise ValueError(
                    f"artifact type {artifact_type.type_id} references missing parent: "
                    f"{parent_id}"
                )
            if parent_id == artifact_type.type_id:
                raise ValueError(
                    f"artifact type {artifact_type.type_id} cannot parent itself"
                )
            if parent.container is not artifact_type.container:
                raise ValueError(
                    f"artifact type {artifact_type.type_id} has incompatible "
                    f"container ancestry through {parent_id}"
                )

        for source_id in artifact_type.accepted_sources:
            if source_id not in types_by_id:
                raise ValueError(
                    f"artifact type {artifact_type.type_id} references missing "
                    f"accepted source: {source_id}"
                )

    @staticmethod
    def _validate_parent_graph_is_acyclic(
        types_by_id: Mapping[str, ArtifactType],
    ) -> None:
        states: dict[str, int] = {}
        path: list[str] = []

        def visit(type_id: str) -> None:
            states[type_id] = 1
            path.append(type_id)
            for parent_id in types_by_id[type_id].parents:
                if states.get(parent_id) == 1:
                    cycle_start = path.index(parent_id)
                    cycle = (*path[cycle_start:], parent_id)
                    raise ValueError(
                        f"artifact parent cycle detected: {' -> '.join(cycle)}"
                    )
                if states.get(parent_id, 0) == 0:
                    visit(parent_id)
            path.pop()
            states[type_id] = 2

        for type_id in types_by_id:
            if states.get(type_id, 0) == 0:
                visit(type_id)


def _first_duplicate(values: tuple[str, ...]) -> str | None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            return value
        seen.add(value)
    return None
