"""Strict immutable node specifications and local cross-field validation."""

from __future__ import annotations

import hashlib
import re
from enum import StrEnum
from typing import Annotated, Self

from pydantic import Field, StringConstraints, ValidationError, field_validator, model_validator

from bionodulo.nodes.contract.artifacts import ArtifactId, ArtifactPort, _StrictFrozenModel
from bionodulo.nodes.contract.environments import (
    ContainerEnvironment,
    ExecutableProbe,
    EnvironmentSpec,
    ExactVersion,
    ImportProbe,
    PixiEnvironment,
    PythonEnvironment,
    RPackageProbe,
    REnvironment,
    Sha256Digest,
    _validate_exact_version,
    _validate_oci_reference,
)
from bionodulo.nodes.contract.evidence import EvidenceRecord, VerificationOutcome, _canonical_json_bytes
from bionodulo.nodes.contract.maturity import Gate, GateResult, MaturityRecord
from bionodulo.nodes.contract.outputs import ConditionalCollector, OutputSpec
from bionodulo.nodes.contract.parameters import ParameterSpec, SecretSpec, ValueKind, ValuePort


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
_CORE_FACTORY_PREFIX = "bionodulo.nodes.catalog.core."
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


def _validate_factory_reference(value: str) -> str:
    if _FACTORY_RE.fullmatch(value) is None:
        raise ValueError("execution factory must be an absolute module.path:symbol reference")
    module, symbol = value.split(":", 1)
    components = (*module.split("."), symbol)
    if any(component.startswith("__") or component.endswith("__") for component in components):
        raise ValueError("execution factory must not reference dunder components")
    return value


class ExecutionKind(StrEnum):
    ARGV = "argv"
    PIPELINE = "pipeline"
    SCRIPT = "script"
    PYTHON = "python"
    R = "r"
    HTTP = "http"
    CONTAINER = "container"


class RuntimeBinding(_StrictFrozenModel):
    tool_id: ArtifactId
    tool_version: ExactVersion
    execution_kind: ExecutionKind
    execution_factory: ExecutionFactory
    package_name: ArtifactId | None = None
    probe_id: ArtifactId | None = None
    container_image: Annotated[str, StringConstraints(min_length=1, max_length=512)] | None = None

    @field_validator("tool_version")
    @classmethod
    def _validate_tool_version(cls, value: str) -> str:
        return _validate_exact_version(value)

    @field_validator("execution_factory")
    @classmethod
    def _validate_runtime_factory(cls, value: str) -> str:
        return _validate_factory_reference(value)

    @field_validator("container_image")
    @classmethod
    def _validate_container_image(cls, value: str | None) -> str | None:
        return None if value is None else _validate_oci_reference(value)

    @model_validator(mode="after")
    def _validate_single_reference(self) -> Self:
        references = (self.package_name, self.probe_id, self.container_image)
        if sum(reference is not None for reference in references) != 1:
            raise ValueError(
                "runtime binding requires exactly one package, probe, or immutable container image reference"
            )
        return self


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


class RetainedArtifactKind(StrEnum):
    CONTRACT = "contract"
    ENVIRONMENT = "environment"
    EVIDENCE_RECORD = "evidence_record"
    VERIFICATION = "verification"


class RetainedArtifact(_StrictFrozenModel):
    kind: RetainedArtifactKind
    artifact_id: ArtifactId
    sha256: Sha256Digest


class RetainedEvidenceInventory(_StrictFrozenModel):
    artifacts: Annotated[tuple[RetainedArtifact, ...], Field(min_length=1, max_length=4096)]

    @model_validator(mode="after")
    def _validate_inventory_order(self) -> Self:
        keys = tuple((artifact.kind.value, artifact.artifact_id) for artifact in self.artifacts)
        if len(set(keys)) != len(keys):
            raise ValueError("retained evidence artifact references must be unique")
        digests = tuple(artifact.sha256 for artifact in self.artifacts)
        if len(set(digests)) != len(digests):
            raise ValueError("retained evidence artifact digests must be unique")
        if keys != tuple(sorted(keys)):
            raise ValueError("retained evidence artifacts must use canonical order")
        return self


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
    runtime_binding: RuntimeBinding | None = None
    evidence: EvidenceRecord | None = None
    retained_evidence: RetainedEvidenceInventory | None = None
    maturity: MaturityRecord | None = None

    @field_validator("execution_factory")
    @classmethod
    def _validate_execution_factory(cls, value: str) -> str:
        return _validate_factory_reference(value)

    @model_validator(mode="after")
    def _validate_composition(self) -> Self:
        self._validate_input_and_output_ids()
        self._validate_port_aliases()
        self._validate_execution_environment()
        self._validate_ownership_and_evidence()
        self._validate_runtime_binding()
        self._validate_retained_evidence()
        self._validate_secret_access()
        return self

    def contract_projection(self) -> dict[str, object]:
        return {
            "identity": self.identity.model_dump(mode="json", round_trip=True),
            "presentation": self.presentation.model_dump(mode="json", round_trip=True),
            "artifact_inputs": {
                item.port_id: item.model_dump(mode="json", round_trip=True)
                for item in sorted(self.artifact_inputs, key=lambda item: item.port_id)
            },
            "value_inputs": {
                item.port_id: item.model_dump(mode="json", round_trip=True)
                for item in sorted(self.value_inputs, key=lambda item: item.port_id)
            },
            "parameters": {
                item.parameter_id: item.model_dump(mode="json", round_trip=True)
                for item in sorted(self.parameters, key=lambda item: item.parameter_id)
            },
            "secrets": {
                item.secret_id: item.model_dump(mode="json", round_trip=True)
                for item in sorted(self.secrets, key=lambda item: item.secret_id)
            },
            "outputs": {
                item.port_id: item.model_dump(mode="json", round_trip=True)
                for item in sorted(self.outputs, key=lambda item: item.port_id)
            },
            "environment": (
                None if self.environment is None else self.environment.model_dump(mode="json", round_trip=True)
            ),
            "execution_kind": self.execution_kind.value,
            "execution_factory": self.execution_factory,
            "runtime_binding": (
                None if self.runtime_binding is None else self.runtime_binding.model_dump(mode="json", round_trip=True)
            ),
        }

    def contract_digest(self) -> str:
        payload = _canonical_json_bytes(self.contract_projection(), label="node contract projection")
        return "sha256:" + hashlib.sha256(payload).hexdigest()

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
        parameters_by_id = {parameter.parameter_id: parameter for parameter in self.parameters}
        for output in self.outputs:
            collector = output.collector
            if not isinstance(collector, ConditionalCollector):
                continue
            if collector.condition_key not in parameter_ids:
                raise ValueError(
                    f"conditional output {output.port_id} references missing parameter {collector.condition_key}"
                )
            parameter = parameters_by_id[collector.condition_key]
            if collector.expected_value is None:
                if parameter.kind is ValueKind.JSON:
                    if not parameter.required:
                        raise ValueError(
                            f"conditional output {output.port_id} has ambiguous null expectation for optional JSON "
                            f"parameter {collector.condition_key}"
                        )
                elif not parameter.required and not parameter.has_default:
                    continue
            try:
                parameter.model_copy(
                    update={
                        "required": False,
                        "has_default": True,
                        "default": collector.expected_value,
                    }
                )
            except ValidationError as error:
                raise ValueError(
                    f"conditional output {output.port_id} expected value is unreachable by parameter "
                    f"{collector.condition_key}"
                ) from error

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
        is_core_python = self._is_core_python_exempt()
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

    def _is_core_python_exempt(self) -> bool:
        module = self.execution_factory.split(":", 1)[0]
        return (
            self.presentation.owner is NodeOwnership.BIONODULO_CORE
            and self.execution_kind is ExecutionKind.PYTHON
            and module.startswith(_CORE_FACTORY_PREFIX)
        )

    def _validate_ownership_and_evidence(self) -> None:
        is_core_python = self._is_core_python_exempt()
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

    def _validate_runtime_binding(self) -> None:
        binding = self.runtime_binding
        if binding is None:
            if self._is_core_python_exempt():
                return
            raise ValueError("non-core node requires an explicit runtime binding")

        if self.identity.tool_id is None or self.identity.tool_version is None:
            raise ValueError("runtime binding requires an exact declared tool identity")
        if binding.tool_id != self.identity.tool_id or binding.tool_version != self.identity.tool_version:
            raise ValueError("runtime binding tool ID and version must match the declared identity")
        if binding.execution_kind is not self.execution_kind:
            raise ValueError("runtime binding execution kind must match the node execution kind")
        if binding.execution_factory != self.execution_factory:
            raise ValueError("runtime binding execution factory must match the node execution factory")

        environment = self.environment
        if environment is None:
            raise ValueError("runtime binding requires a declared execution environment")

        if binding.package_name is not None:
            self._validate_package_runtime_reference(binding.package_name, binding.tool_version)
            return
        if binding.probe_id is not None:
            self._validate_probe_runtime_reference(binding.probe_id, binding.tool_version)
            return
        assert binding.container_image is not None
        if self.execution_kind is not ExecutionKind.CONTAINER or not isinstance(environment, ContainerEnvironment):
            raise ValueError("container runtime binding requires container execution and environment")
        if binding.container_image != environment.image:
            raise ValueError("container runtime binding image must equal the declared environment image")
        repository = environment.image.rsplit("@", 1)[0].rsplit("/", 1)[-1]
        if repository != self.identity.tool_id:
            raise ValueError("container runtime binding image repository must match the declared tool ID")

    def _validate_package_runtime_reference(self, package_name: str, tool_version: str) -> None:
        environment = self.environment
        if environment is None or isinstance(environment, ContainerEnvironment):
            raise ValueError("package runtime binding requires a package environment")
        if self.identity.tool_id != package_name:
            raise ValueError("runtime package name must match the declared tool ID")
        request = next((item for item in environment.packages if item.name == package_name), None)
        if request is None:
            raise ValueError(f"runtime binding package {package_name} is missing from the environment")
        for lock in environment.locks:
            artifact = next((item for item in lock.artifacts if item.name == package_name), None)
            if artifact is None or artifact.version != tool_version:
                raise ValueError(
                    f"runtime binding package {package_name} must resolve to version {tool_version} in every lock"
                )

    def _validate_probe_runtime_reference(self, probe_id: str, tool_version: str) -> None:
        environment = self.environment
        if environment is None:
            raise ValueError("probe runtime binding requires a declared execution environment")
        probes: tuple[ExecutableProbe | ImportProbe | RPackageProbe, ...] = environment.executable_probes
        if isinstance(environment, (PixiEnvironment, PythonEnvironment)):
            probes = (*probes, *environment.import_probes)
        elif isinstance(environment, REnvironment):
            probes = (*probes, *environment.package_probes)
        probe = next((item for item in probes if item.probe_id == probe_id), None)
        if probe is None:
            raise ValueError(f"runtime binding probe {probe_id} is missing from the environment")
        if probe.expected_version != tool_version:
            raise ValueError(f"runtime binding probe {probe_id} version must match the declared tool version")

        tool_id = self.identity.tool_id
        assert tool_id is not None
        if isinstance(probe, ExecutableProbe):
            if self.execution_kind not in (
                ExecutionKind.ARGV,
                ExecutionKind.PIPELINE,
                ExecutionKind.SCRIPT,
            ):
                raise ValueError("executable probe runtime binding is only valid for process execution kinds")
            locator_name = probe.locator.rsplit("/", 1)[-1]
            if locator_name not in (tool_id, tool_id.replace("-", "_")):
                raise ValueError("runtime binding executable probe locator must match the declared tool ID")
            return
        if isinstance(probe, ImportProbe):
            if self.execution_kind not in (ExecutionKind.PYTHON, ExecutionKind.HTTP):
                raise ValueError("Python import probe runtime binding requires Python or HTTP execution")
            module_name = probe.module.split(".", 1)[0]
            if module_name not in (tool_id, tool_id.replace("-", "_")):
                raise ValueError("runtime binding Python import probe module must match the declared tool ID")
            return
        if self.execution_kind is not ExecutionKind.R:
            raise ValueError("R package probe runtime binding requires R execution")
        if probe.package.lower() != tool_id.lower():
            raise ValueError("runtime binding R package probe must match the declared tool ID")

    def _validate_retained_evidence(self) -> None:
        inventory = self.retained_evidence
        maturity = self.maturity
        evidence_assessment = None
        if maturity is not None:
            evidence_assessment = next(
                (item for item in maturity.assessments if item.gate is Gate.EVIDENCE_VERIFIED),
                None,
            )
        if (
            evidence_assessment is not None
            and evidence_assessment.result is GateResult.PASSED
            and self.evidence is None
        ):
            raise ValueError("passing evidence_verified requires an evidence record in retained evidence inventory")
        if inventory is None:
            if maturity is not None and maturity.assessments:
                raise ValueError("maturity assessments require a retained evidence inventory")
            return

        artifacts_by_kind: dict[RetainedArtifactKind, tuple[RetainedArtifact, ...]] = {
            kind: tuple(item for item in inventory.artifacts if item.kind is kind) for kind in RetainedArtifactKind
        }
        verifications_by_digest = {}
        if self.evidence is None:
            if (
                artifacts_by_kind[RetainedArtifactKind.EVIDENCE_RECORD]
                or artifacts_by_kind[RetainedArtifactKind.VERIFICATION]
            ):
                raise ValueError("retained evidence inventory references an absent evidence record")
        else:
            expected_evidence = (
                RetainedArtifact(
                    kind=RetainedArtifactKind.EVIDENCE_RECORD,
                    artifact_id=self.evidence.tool_id,
                    sha256=self.evidence.evidence_digest(),
                ),
            )
            if artifacts_by_kind[RetainedArtifactKind.EVIDENCE_RECORD] != expected_evidence:
                raise ValueError("retained evidence inventory is not bound to the evidence record")
            expected_verifications = tuple(
                RetainedArtifact(
                    kind=RetainedArtifactKind.VERIFICATION,
                    artifact_id=item.evidence_id,
                    sha256=item.verification_digest(),
                )
                for item in self.evidence.verifications
            )
            if artifacts_by_kind[RetainedArtifactKind.VERIFICATION] != expected_verifications:
                raise ValueError("retained evidence inventory is not bound to evidence verifications")
            verifications_by_digest = {item.verification_digest(): item for item in self.evidence.verifications}

        if self.environment is None:
            if artifacts_by_kind[RetainedArtifactKind.ENVIRONMENT]:
                raise ValueError("retained evidence inventory references an absent environment")
            if any(
                verification.environment_sha256 is not None
                for verification in (() if self.evidence is None else self.evidence.verifications)
            ):
                raise ValueError("retained verification environment digest requires a declared environment")
        else:
            expected_environment = (
                RetainedArtifact(
                    kind=RetainedArtifactKind.ENVIRONMENT,
                    artifact_id=self.environment.environment_id,
                    sha256=self.environment.environment_digest(),
                ),
            )
            if artifacts_by_kind[RetainedArtifactKind.ENVIRONMENT] != expected_environment:
                raise ValueError("retained evidence inventory is not bound to the execution environment")
            for verification in () if self.evidence is None else self.evidence.verifications:
                if (
                    verification.environment_sha256 is not None
                    and verification.environment_sha256 != self.environment.environment_digest()
                ):
                    raise ValueError("retained verification environment digest must match the declared environment")

        expected_contract = (
            RetainedArtifact(
                kind=RetainedArtifactKind.CONTRACT,
                artifact_id=self.identity.machine_id,
                sha256=self.contract_digest(),
            ),
        )
        if artifacts_by_kind[RetainedArtifactKind.CONTRACT] != expected_contract:
            raise ValueError("retained contract artifact must match the authoritative node contract digest")

        available = {artifact.sha256: artifact.kind for artifact in inventory.artifacts}
        if maturity is not None:
            for assessment in maturity.assessments:
                expected_outcome = VerificationOutcome(assessment.result.value)
                for digest in assessment.verification_digests:
                    mismatch_context = f"maturity gate {assessment.gate.value} verification {digest}"
                    matched_verification = verifications_by_digest.get(digest)
                    if matched_verification is None:
                        raise ValueError(
                            f"{mismatch_context} resolution mismatch: expected retained verification evidence, "
                            "actual unresolved digest"
                        )
                    if matched_verification.kind is not assessment.verification_kind:
                        raise ValueError(
                            f"{mismatch_context} kind mismatch: expected {assessment.verification_kind.value}, "
                            f"actual {matched_verification.kind.value}"
                        )
                    if matched_verification.outcome is not expected_outcome:
                        raise ValueError(
                            f"{mismatch_context} outcome mismatch: expected {expected_outcome.value}, "
                            f"actual {matched_verification.outcome.value}"
                        )
                    if matched_verification.failure_code is not assessment.failure_code:
                        expected_failure_code = (
                            "none" if assessment.failure_code is None else assessment.failure_code.value
                        )
                        actual_failure_code = (
                            "none"
                            if matched_verification.failure_code is None
                            else matched_verification.failure_code.value
                        )
                        raise ValueError(
                            f"{mismatch_context} failure code mismatch: expected {expected_failure_code}, "
                            f"actual {actual_failure_code}"
                        )
                    if matched_verification.verifier_id != assessment.verifier_id:
                        raise ValueError(
                            f"{mismatch_context} verifier ID mismatch: expected {assessment.verifier_id}, "
                            f"actual {matched_verification.verifier_id}"
                        )
                    if matched_verification.verifier_version != assessment.verifier_version:
                        raise ValueError(
                            f"{mismatch_context} verifier version mismatch: expected {assessment.verifier_version}, "
                            f"actual {matched_verification.verifier_version}"
                        )
                    if (
                        matched_verification.tool_id != self.identity.tool_id
                        or matched_verification.tool_version != self.identity.tool_version
                    ):
                        raise ValueError(
                            f"{mismatch_context} tool identity mismatch: "
                            f"expected {self.identity.tool_id}@{self.identity.tool_version}, "
                            f"actual {matched_verification.tool_id}@{matched_verification.tool_version}"
                        )

            if maturity.released:
                required_kinds = set(RetainedArtifactKind)
                present_kinds = set(available.values())
                missing = required_kinds - present_kinds
                if missing:
                    names = ", ".join(sorted(kind.value for kind in missing))
                    raise ValueError(f"released maturity requires retained evidence artifacts: {names}")

    def _validate_secret_access(self) -> None:
        maturity = self.maturity
        required_secret = any(secret.required for secret in self.secrets)
        if not self.secrets:
            if maturity is not None and maturity.requires_secret:
                raise ValueError("secret_required maturity requires at least one required secret")
            return
        if maturity is None or not maturity.permits_secrets:
            raise ValueError("secret declarations require explicit secret-capable maturity")
        if required_secret and not maturity.permits_required_secrets:
            raise ValueError("required secret declarations require a required-secret-capable access class")
        if maturity.requires_secret and not required_secret:
            raise ValueError("secret_required maturity requires at least one required secret")


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
    "RetainedArtifact",
    "RetainedArtifactKind",
    "RetainedEvidenceInventory",
    "RuntimeBinding",
    "SEMVER_PATTERN",
]
