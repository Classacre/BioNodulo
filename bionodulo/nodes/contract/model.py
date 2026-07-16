"""Strict immutable node specifications and local cross-field validation."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Self

from pydantic import Field, StringConstraints, field_validator, model_validator

from bionodulo.nodes.contract.artifacts import ArtifactId, ArtifactPort, _StrictFrozenModel
from bionodulo.nodes.contract.environments import (
    ContainerEnvironment,
    EnvironmentSpec,
    ExactVersion,
    PixiEnvironment,
    PythonEnvironment,
    REnvironment,
    _validate_exact_version,
)
from bionodulo.nodes.contract.evidence import EvidenceRecord
from bionodulo.nodes.contract.maturity import MaturityRecord
from bionodulo.nodes.contract.outputs import ConditionalCollector, OutputSpec
from bionodulo.nodes.contract.parameters import ParameterSpec, SecretSpec, ValuePort


MACHINE_ID_PATTERN = r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$"
SEMVER_PATTERN = (
    r"^(?:0|[1-9][0-9]*)\."
    r"(?:0|[1-9][0-9]*)\."
    r"(?:0|[1-9][0-9]*)"
    r"(?:-(?:"
    r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*"
    r"))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)

_MACHINE_ID_RE = re.compile(MACHINE_ID_PATTERN)
_SEMVER_RE = re.compile(SEMVER_PATTERN)
_FACTORY_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+:"
    r"[A-Za-z_][A-Za-z0-9_]*$"
)
_MAX_ID_LENGTH = 128
_MAX_TEXT_LENGTH = 2_048

StableId = Annotated[str, StringConstraints(min_length=1, max_length=_MAX_ID_LENGTH)]
MachineId = Annotated[str, StringConstraints(min_length=1, max_length=_MAX_ID_LENGTH)]
SemVer = Annotated[str, StringConstraints(min_length=5, max_length=_MAX_ID_LENGTH)]
PresentationText = Annotated[
    str,
    StringConstraints(min_length=1, max_length=_MAX_TEXT_LENGTH),
]
PaletteSegment = Annotated[str, StringConstraints(min_length=1, max_length=128)]
ExecutionFactory = Annotated[str, StringConstraints(min_length=3, max_length=512)]


def _validate_printable_text(
    value: str,
    *,
    label: str,
    allow_outer_whitespace: bool,
) -> str:
    if not allow_outer_whitespace and value != value.strip():
        raise ValueError(f"{label} must not have outer whitespace")
    if not all(character.isprintable() for character in value):
        raise ValueError(f"{label} must contain only printable characters")
    return value


class ExecutionKind(StrEnum):
    ARGV = "argv"
    PIPELINE = "pipeline"
    SCRIPT = "script"
    PYTHON = "python"
    R = "r"
    HTTP = "http"
    CONTAINER = "container"


class NodeOwnership(StrEnum):
    BIONODULO_CORE = "bionodulo_core"
    EXTERNAL_TOOL = "external_tool"
    EXTERNAL_LIBRARY = "external_library"
    EXTERNAL_PROVIDER = "external_provider"


class PortAliasScope(StrEnum):
    ARTIFACT_INPUT = "artifact_input"
    VALUE_INPUT = "value_input"
    PARAMETER = "parameter"
    SECRET = "secret"
    OUTPUT = "output"


class PortAlias(_StrictFrozenModel):
    scope: PortAliasScope
    old_id: ArtifactId
    canonical_id: ArtifactId

    @model_validator(mode="after")
    def _validate_mapping(self) -> Self:
        if self.old_id == self.canonical_id:
            raise ValueError("port alias cannot map an ID to itself")
        return self


class NodeIdentity(_StrictFrozenModel):
    stable_id: StableId
    machine_id: MachineId
    contract_version: SemVer
    implementation_version: SemVer
    tool_id: ArtifactId | None = None
    tool_version: ExactVersion | None = None
    aliases: Annotated[tuple[StableId, ...], Field(max_length=1_024)] = ()
    port_aliases: Annotated[tuple[PortAlias, ...], Field(max_length=4_096)] = ()

    @property
    def node_id(self) -> str:
        """Compatibility access for callers that still read identity.node_id."""

        return self.stable_id

    @field_validator("stable_id")
    @classmethod
    def _validate_stable_id(cls, value: str) -> str:
        return _validate_printable_text(
            value,
            label="stable ID",
            allow_outer_whitespace=True,
        )

    @field_validator("machine_id")
    @classmethod
    def _validate_machine_id(cls, value: str) -> str:
        if _MACHINE_ID_RE.fullmatch(value) is None:
            raise ValueError(f"machine ID must match {MACHINE_ID_PATTERN}")
        return value

    @field_validator("contract_version", "implementation_version")
    @classmethod
    def _validate_semver(cls, value: str) -> str:
        if _SEMVER_RE.fullmatch(value) is None:
            raise ValueError("version must be a strict semantic version")
        return value

    @field_validator("tool_version")
    @classmethod
    def _validate_tool_version(cls, value: str | None) -> str | None:
        return None if value is None else _validate_exact_version(value)

    @field_validator("aliases")
    @classmethod
    def _validate_alias_text(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        for value in values:
            _validate_printable_text(
                value,
                label="identity alias",
                allow_outer_whitespace=True,
            )
        return values

    @model_validator(mode="after")
    def _validate_identity(self) -> Self:
        if (self.tool_id is None) != (self.tool_version is None):
            raise ValueError("tool identity requires both tool ID and exact tool version")

        if len(set(self.aliases)) != len(self.aliases):
            raise ValueError("identity aliases must be unique")
        if self.stable_id in self.aliases:
            raise ValueError("identity alias cannot equal the stable ID")

        seen_port_aliases: set[tuple[PortAliasScope, str]] = set()
        for alias in self.port_aliases:
            key = (alias.scope, alias.old_id)
            if key in seen_port_aliases:
                raise ValueError(f"port alias is ambiguous in {alias.scope.value}: {alias.old_id}")
            seen_port_aliases.add(key)
        return self


class NodePresentation(_StrictFrozenModel):
    display_name: Annotated[str, StringConstraints(min_length=1, max_length=256)]
    description: PresentationText
    palette_path: Annotated[
        tuple[PaletteSegment, ...],
        Field(min_length=1, max_length=16),
    ]
    domain_tags: Annotated[tuple[ArtifactId, ...], Field(min_length=1, max_length=64)]
    operation_kind: ArtifactId
    owner: NodeOwnership
    tool_family: ArtifactId | None = None
    provider: ArtifactId | None = None

    @field_validator("display_name", "description")
    @classmethod
    def _validate_human_text(cls, value: str, info: object) -> str:
        label = getattr(info, "field_name", "presentation text").replace("_", " ")
        return _validate_printable_text(
            value,
            label=label,
            allow_outer_whitespace=False,
        )

    @field_validator("palette_path")
    @classmethod
    def _validate_palette_path(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        for value in values:
            _validate_printable_text(
                value,
                label="palette path segment",
                allow_outer_whitespace=False,
            )
        return values

    @model_validator(mode="after")
    def _validate_metadata(self) -> Self:
        if len(set(self.domain_tags)) != len(self.domain_tags):
            raise ValueError("domain tags must be unique")
        if (
            self.owner
            in (
                NodeOwnership.EXTERNAL_TOOL,
                NodeOwnership.EXTERNAL_LIBRARY,
            )
            and self.tool_family is None
        ):
            raise ValueError("external tool or library ownership requires tool family metadata")
        if self.owner is NodeOwnership.EXTERNAL_PROVIDER and self.provider is None:
            raise ValueError("external provider ownership requires provider metadata")
        return self


class NodeSpec(_StrictFrozenModel):
    identity: NodeIdentity
    presentation: NodePresentation
    artifact_inputs: Annotated[tuple[ArtifactPort, ...], Field(max_length=1_024)] = ()
    value_inputs: Annotated[tuple[ValuePort, ...], Field(max_length=1_024)] = ()
    parameters: Annotated[tuple[ParameterSpec, ...], Field(max_length=1_024)] = ()
    secrets: Annotated[tuple[SecretSpec, ...], Field(max_length=1_024)] = ()
    outputs: Annotated[tuple[OutputSpec, ...], Field(max_length=1_024)] = ()
    environment: EnvironmentSpec | None = None
    execution_kind: ExecutionKind
    execution_factory: ExecutionFactory
    evidence: EvidenceRecord | None = None
    maturity: MaturityRecord | None = None

    @field_validator("execution_factory")
    @classmethod
    def _validate_execution_factory(cls, value: str) -> str:
        if _FACTORY_RE.fullmatch(value) is None:
            raise ValueError("execution factory must be an absolute module.path:symbol reference")
        module, symbol = value.split(":", 1)
        components = (*module.split("."), symbol)
        if any(component.startswith("__") or component.endswith("__") for component in components):
            raise ValueError("execution factory must not reference dunder components")
        return value

    @model_validator(mode="after")
    def _validate_composition(self) -> Self:
        self._validate_input_and_output_ids()
        self._validate_port_aliases()
        self._validate_execution_environment()
        self._validate_ownership_and_evidence()
        return self

    def _validate_input_and_output_ids(self) -> None:
        input_ids = (
            *(port.port_id for port in self.artifact_inputs),
            *(port.port_id for port in self.value_inputs),
            *(parameter.parameter_id for parameter in self.parameters),
            *(secret.secret_id for secret in self.secrets),
        )
        duplicate_input = _first_duplicate(input_ids)
        if duplicate_input is not None:
            raise ValueError(f"duplicate input ID: {duplicate_input}")

        output_ids = tuple(output.port_id for output in self.outputs)
        duplicate_output = _first_duplicate(output_ids)
        if duplicate_output is not None:
            raise ValueError(f"duplicate output ID: {duplicate_output}")

        environment_names = tuple(secret.environment_variable for secret in self.secrets)
        duplicate_environment_name = _first_duplicate(environment_names)
        if duplicate_environment_name is not None:
            raise ValueError(f"secret environment variable bindings must be unique: {duplicate_environment_name}")

        parameter_ids = {parameter.parameter_id for parameter in self.parameters}
        for output in self.outputs:
            collector = output.collector
            if isinstance(collector, ConditionalCollector) and collector.condition_key not in parameter_ids:
                raise ValueError(
                    f"conditional output {output.port_id} references missing parameter {collector.condition_key}"
                )

    def _validate_port_aliases(self) -> None:
        declared: dict[PortAliasScope, set[str]] = {
            PortAliasScope.ARTIFACT_INPUT: {port.port_id for port in self.artifact_inputs},
            PortAliasScope.VALUE_INPUT: {port.port_id for port in self.value_inputs},
            PortAliasScope.PARAMETER: {parameter.parameter_id for parameter in self.parameters},
            PortAliasScope.SECRET: {secret.secret_id for secret in self.secrets},
            PortAliasScope.OUTPUT: {output.port_id for output in self.outputs},
        }
        for alias in self.identity.port_aliases:
            scoped_ids = declared[alias.scope]
            if alias.canonical_id not in scoped_ids:
                raise ValueError(f"port alias target {alias.canonical_id} is missing from {alias.scope.value}")
            if alias.old_id in scoped_ids:
                raise ValueError(f"port alias {alias.old_id} collides with a canonical {alias.scope.value} ID")

    def _validate_execution_environment(self) -> None:
        environment = self.environment
        is_core_python = (
            self.presentation.owner is NodeOwnership.BIONODULO_CORE and self.execution_kind is ExecutionKind.PYTHON
        )
        if environment is None:
            if is_core_python:
                return
            raise ValueError("only a BioNodulo-owned in-process core Python node may omit its execution environment")

        if not environment.is_fully_locked:
            raise ValueError("declared execution environment must be fully locked")

        if self.execution_kind in (
            ExecutionKind.ARGV,
            ExecutionKind.PIPELINE,
            ExecutionKind.SCRIPT,
        ):
            if not isinstance(
                environment,
                (PixiEnvironment, PythonEnvironment, REnvironment),
            ):
                raise ValueError("process execution requires a locked package environment")
            return
        if self.execution_kind is ExecutionKind.PYTHON:
            if not isinstance(environment, PythonEnvironment):
                raise ValueError("Python execution requires a Python environment")
            return
        if self.execution_kind is ExecutionKind.R:
            if not isinstance(environment, REnvironment):
                raise ValueError("R execution requires an R environment")
            return
        if self.execution_kind is ExecutionKind.HTTP:
            if not isinstance(environment, PythonEnvironment):
                raise ValueError("HTTP execution requires a locked Python environment")
            return
        if not isinstance(environment, ContainerEnvironment):
            raise ValueError("container execution requires a container environment")

    def _validate_ownership_and_evidence(self) -> None:
        is_core_python = (
            self.presentation.owner is NodeOwnership.BIONODULO_CORE and self.execution_kind is ExecutionKind.PYTHON
        )
        if not is_core_python:
            if self.identity.tool_id is None or self.identity.tool_version is None:
                raise ValueError("only a BioNodulo-owned in-process core Python node may omit its exact tool identity")
            if self.evidence is None:
                raise ValueError("only a BioNodulo-owned in-process core Python node may omit tool evidence")

        if self.evidence is None:
            if self.identity.tool_id is not None:
                raise ValueError("declared tool identity requires a matching evidence record")
            return
        if self.identity.tool_id != self.evidence.tool_id or self.identity.tool_version != self.evidence.tool_version:
            raise ValueError("evidence tool ID and version must equal the declared tool identity")


def _first_duplicate(values: tuple[str, ...]) -> str | None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            return value
        seen.add(value)
    return None


__all__ = [
    "ExecutionKind",
    "MACHINE_ID_PATTERN",
    "NodeIdentity",
    "NodeOwnership",
    "NodePresentation",
    "NodeSpec",
    "PortAlias",
    "PortAliasScope",
    "SEMVER_PATTERN",
]
