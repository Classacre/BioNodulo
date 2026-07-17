"""Canonical environment registry and workflow request projections."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, field_validator, model_validator

from bionodulo.nodes.contract.artifacts import ArtifactId, _StrictFrozenModel
from bionodulo.nodes.contract.environments import (
    ContainerEnvironment,
    ExecutionPlatform,
    PixiEnvironment,
    PythonEnvironment,
    REnvironment,
    Sha256Digest,
)
from bionodulo.nodes.contract.model import NodeSpec


_MAX_REGISTRY_BYTES = 1024 * 1024
_MAX_JSON_NESTING_DEPTH = 64
_UNSAFE_JSON_KEYS = frozenset({"__proto__", "constructor", "prototype"})


def environment_registry_digest(content: bytes) -> str:
    """Digest exact registry bytes without adding a self-reference field."""

    if type(content) is not bytes:
        raise TypeError("environment registry content must be exact bytes")
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in _UNSAFE_JSON_KEYS:
            raise ValueError(f"unsafe JSON key: {key}")
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"non-finite JSON number is forbidden: {value}")


def _validate_json_nesting(text: str) -> None:
    depth = 0
    in_string = False
    escaped = False
    for character in text:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
        elif character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > _MAX_JSON_NESTING_DEPTH:
                raise ValueError(f"environment registry JSON nesting depth may be at most {_MAX_JSON_NESTING_DEPTH}")
        elif character in "]}":
            depth -= 1


class _CanonicalModel(_StrictFrozenModel):
    def canonical_json_bytes(self) -> bytes:
        return json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")

    def canonical_digest(self) -> str:
        return environment_registry_digest(self.canonical_json_bytes())


class EnvironmentPlatformLockBinding(_CanonicalModel):
    platform: ExecutionPlatform
    lock_digest: Sha256Digest


class EnvironmentLockSetDescriptor(_CanonicalModel):
    environment_name: ArtifactId
    platform_locks: Annotated[
        tuple[EnvironmentPlatformLockBinding, ...],
        Field(min_length=1, max_length=2),
    ]

    @model_validator(mode="after")
    def _validate_platform_locks(self) -> Self:
        platforms = tuple(binding.platform.value for binding in self.platform_locks)
        if len(set(platforms)) != len(platforms):
            raise ValueError("lock-set platforms must be unique")
        if platforms != tuple(sorted(platforms)):
            raise ValueError("lock-set platforms must use canonical ordering")
        digests = tuple(binding.lock_digest for binding in self.platform_locks)
        if len(set(digests)) != len(digests):
            raise ValueError("lock-set platform digests must be unique")
        return self

    def lock_set_digest(self) -> str:
        return self.canonical_digest()


class EnvironmentRuntimeBinding(_CanonicalModel):
    node_id: ArtifactId
    tool_id: ArtifactId
    tool_version: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    binding_kind: Literal["package", "probe", "container"]
    binding_id: Annotated[str, StringConstraints(min_length=1, max_length=512)]

    @field_validator("tool_version", "binding_id")
    @classmethod
    def _validate_printable_ascii(cls, value: str) -> str:
        if any(ord(character) < 0x20 or ord(character) > 0x7E for character in value):
            raise ValueError("runtime binding values must contain only printable ASCII characters")
        if value != value.strip():
            raise ValueError("runtime binding values must not have outer whitespace")
        return value


class EnvironmentRegistryEntry(_CanonicalModel):
    environment_id: ArtifactId
    environment_digest: Sha256Digest
    lock_set: EnvironmentLockSetDescriptor
    runtime_bindings: Annotated[tuple[EnvironmentRuntimeBinding, ...], Field(min_length=1, max_length=4096)]

    @model_validator(mode="after")
    def _validate_runtime_bindings(self) -> Self:
        identities = tuple(binding.node_id for binding in self.runtime_bindings)
        if len(set(identities)) != len(identities):
            raise ValueError("environment runtime binding node IDs must be unique")
        if identities != tuple(sorted(identities)):
            raise ValueError("environment runtime bindings must use canonical node ID ordering")
        return self


class EnvironmentRegistry(_CanonicalModel):
    schema_version: Literal[2]
    environments: Annotated[tuple[EnvironmentRegistryEntry, ...], Field(min_length=1, max_length=4096)]

    @model_validator(mode="after")
    def _validate_environments(self) -> Self:
        environment_ids = tuple(entry.environment_id for entry in self.environments)
        if len(set(environment_ids)) != len(environment_ids):
            raise ValueError("registry environment IDs must be unique")
        if environment_ids != tuple(sorted(environment_ids)):
            raise ValueError("registry environment IDs must use canonical ordering")
        environment_names = tuple(entry.lock_set.environment_name for entry in self.environments)
        if len(set(environment_names)) != len(environment_names):
            raise ValueError("registry environment names must be unique")
        return self

    def registry_digest(self) -> str:
        return self.canonical_digest()


def _runtime_binding_from_node_spec(spec: NodeSpec) -> EnvironmentRuntimeBinding:
    binding = spec.runtime_binding
    if binding is None:
        raise ValueError("NodeSpec environment requires an explicit runtime binding")
    binding_kind: Literal["package", "probe", "container"]
    if binding.package_name is not None:
        binding_kind = "package"
        binding_id = binding.package_name
    elif binding.probe_id is not None:
        binding_kind = "probe"
        binding_id = binding.probe_id
    else:
        assert binding.container_image is not None
        binding_kind = "container"
        binding_id = binding.container_image
    return EnvironmentRuntimeBinding(
        node_id=spec.identity.machine_id,
        tool_id=binding.tool_id,
        tool_version=binding.tool_version,
        binding_kind=binding_kind,
        binding_id=binding_id,
    )


def _lock_set_from_node_spec(spec: NodeSpec) -> EnvironmentLockSetDescriptor:
    environment = spec.environment
    if environment is None:
        raise ValueError("NodeSpec environment is absent")
    if isinstance(environment, (PixiEnvironment, PythonEnvironment, REnvironment)):
        environment_names = {lock.environment_name for lock in environment.locks}
        if len(environment_names) != 1:
            raise ValueError("NodeSpec PlatformLocks must share exactly one environment_name")
        environment_name = next(iter(environment_names))
        platform_locks = tuple(
            EnvironmentPlatformLockBinding(
                platform=lock.platform,
                lock_digest=lock.lock_digest(),
            )
            for lock in environment.locks
        )
    elif isinstance(environment, ContainerEnvironment):
        environment_name = environment.environment_id
        platform_locks = tuple(
            EnvironmentPlatformLockBinding(
                platform=lock.platform,
                lock_digest=lock.lock_digest(),
            )
            for lock in environment.image_locks
        )
    else:  # pragma: no cover - closed EnvironmentSpec union
        raise TypeError(f"unsupported NodeSpec environment: {type(environment).__name__}")
    return EnvironmentLockSetDescriptor(
        environment_name=environment_name,
        platform_locks=platform_locks,
    )


def derive_environment_registry(node_specs: Iterable[NodeSpec]) -> EnvironmentRegistry:
    """Derive registry identities only from fully revalidated NodeSpec contracts."""

    captured: dict[str, tuple[object, EnvironmentLockSetDescriptor, list[EnvironmentRuntimeBinding]]] = {}
    for raw_spec in node_specs:
        spec = NodeSpec.model_validate(raw_spec)
        environment = spec.environment
        if environment is None:
            continue
        lock_set = _lock_set_from_node_spec(spec)
        runtime_binding = _runtime_binding_from_node_spec(spec)
        previous = captured.get(environment.environment_id)
        if previous is None:
            captured[environment.environment_id] = (environment, lock_set, [runtime_binding])
            continue
        previous_environment, previous_lock_set, runtime_bindings = previous
        if previous_environment != environment or previous_lock_set != lock_set:
            raise ValueError(f"NodeSpecs disagree about environment {environment.environment_id} content or lock set")
        runtime_bindings.append(runtime_binding)
    if not captured:
        raise ValueError("NodeSpecs do not declare any locked environments")
    entries: list[EnvironmentRegistryEntry] = []
    for environment_id in sorted(captured):
        raw_environment, lock_set, runtime_bindings = captured[environment_id]
        if not isinstance(raw_environment, (PixiEnvironment, PythonEnvironment, REnvironment, ContainerEnvironment)):
            raise TypeError(f"unsupported NodeSpec environment: {type(raw_environment).__name__}")
        entries.append(
            EnvironmentRegistryEntry(
                environment_id=environment_id,
                environment_digest=raw_environment.environment_digest(),
                lock_set=lock_set,
                runtime_bindings=tuple(sorted(runtime_bindings, key=lambda binding: binding.node_id)),
            )
        )
    return EnvironmentRegistry(schema_version=2, environments=tuple(entries))


def validate_environment_registry(
    registry: EnvironmentRegistry,
    node_specs: Iterable[NodeSpec],
) -> EnvironmentRegistry:
    """Require a registry to equal the authoritative NodeSpec-derived registry."""

    validated = EnvironmentRegistry.model_validate(registry)
    expected = derive_environment_registry(node_specs)
    if validated != expected:
        raise ValueError("environment registry does not match validated NodeSpec environments")
    return validated


def decode_environment_registry(
    content: bytes,
    *,
    node_specs: Iterable[NodeSpec],
) -> EnvironmentRegistry:
    """Decode exact canonical persisted bytes and bind them to NodeSpec authority."""

    if type(content) is not bytes:
        raise TypeError("environment registry content must be exact bytes")
    if not content or len(content) > _MAX_REGISTRY_BYTES:
        raise ValueError(f"environment registry must be between 1 and {_MAX_REGISTRY_BYTES} bytes")
    try:
        text = content.decode("ascii")
        _validate_json_nesting(text)
        document = json.loads(
            text,
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"environment registry must be strict ASCII JSON: {error}") from error
    if type(document) is not dict:
        raise ValueError("environment registry must be a JSON object")
    if "schema_version" not in document:
        raise ValueError("environment registry requires schema_version")
    decoded = EnvironmentRegistry.model_validate_json(content)
    if decoded.canonical_json_bytes() != content:
        raise ValueError("environment registry bytes must use canonical JSON encoding")
    return validate_environment_registry(decoded, node_specs)


class WorkflowEnvironmentSelection(_CanonicalModel):
    environment_id: ArtifactId
    platform: ExecutionPlatform


class WorkflowEnvironmentRequestItem(_CanonicalModel):
    environment_id: ArtifactId
    environment_digest: Sha256Digest
    environment_name: ArtifactId
    platform: ExecutionPlatform
    platform_lock_digest: Sha256Digest
    lock_set_digest: Sha256Digest


class WorkflowEnvironmentRequest(_CanonicalModel):
    schema_version: Literal[2]
    environment_registry_sha256: Sha256Digest
    environments: Annotated[tuple[WorkflowEnvironmentRequestItem, ...], Field(max_length=8192)] = ()

    @model_validator(mode="after")
    def _validate_environments(self) -> Self:
        identities = tuple((item.environment_id, item.platform.value) for item in self.environments)
        if len(set(identities)) != len(identities):
            raise ValueError("workflow environment request identities must be unique")
        if identities != tuple(sorted(identities)):
            raise ValueError("workflow environment requests must use canonical ordering")
        return self


def _project_workflow_environment_request(
    registry: EnvironmentRegistry,
    selections: Iterable[WorkflowEnvironmentSelection],
    *,
    registry_digest: Sha256Digest,
) -> WorkflowEnvironmentRequest:
    entries = {entry.environment_id: entry for entry in registry.environments}
    requested: dict[tuple[str, str], WorkflowEnvironmentRequestItem] = {}
    for raw_selection in selections:
        selection = WorkflowEnvironmentSelection.model_validate(raw_selection)
        try:
            entry = entries[selection.environment_id]
        except KeyError as error:
            raise ValueError(f"unknown environment ID: {selection.environment_id}") from error
        platform_bindings = {binding.platform: binding for binding in entry.lock_set.platform_locks}
        try:
            binding = platform_bindings[selection.platform]
        except KeyError as error:
            raise ValueError(
                f"environment {selection.environment_id} has no lock for platform {selection.platform.value}"
            ) from error
        key = (selection.environment_id, selection.platform.value)
        requested[key] = WorkflowEnvironmentRequestItem(
            environment_id=selection.environment_id,
            environment_digest=entry.environment_digest,
            environment_name=entry.lock_set.environment_name,
            platform=selection.platform,
            platform_lock_digest=binding.lock_digest,
            lock_set_digest=entry.lock_set.lock_set_digest(),
        )
    return WorkflowEnvironmentRequest(
        schema_version=2,
        environment_registry_sha256=registry_digest,
        environments=tuple(requested[key] for key in sorted(requested)),
    )


def compile_workflow_environment_request(
    registry_content: bytes,
    selections: Iterable[WorkflowEnvironmentSelection],
    *,
    node_specs: Iterable[NodeSpec],
) -> WorkflowEnvironmentRequest:
    """Project selections only through exact persisted, NodeSpec-bound registry bytes."""

    specs = tuple(node_specs)
    decoded = decode_environment_registry(registry_content, node_specs=specs)
    return _project_workflow_environment_request(
        decoded,
        selections,
        registry_digest=environment_registry_digest(registry_content),
    )


def admit_workflow_environment_request(
    request: WorkflowEnvironmentRequest,
    *,
    registry_content: bytes,
    node_specs: Iterable[NodeSpec],
) -> WorkflowEnvironmentRequest:
    """Reopen registry bytes and recompute the complete request before admission."""

    validated_request = WorkflowEnvironmentRequest.model_validate(request)
    specs = tuple(node_specs)
    decoded = decode_environment_registry(registry_content, node_specs=specs)
    raw_digest = environment_registry_digest(registry_content)
    if validated_request.environment_registry_sha256 != raw_digest:
        raise ValueError("workflow request raw registry digest does not match persisted registry bytes")
    expected = _project_workflow_environment_request(
        decoded,
        (
            WorkflowEnvironmentSelection(
                environment_id=item.environment_id,
                platform=item.platform,
            )
            for item in validated_request.environments
        ),
        registry_digest=raw_digest,
    )
    if validated_request != expected:
        raise ValueError("workflow environment request does not match persisted registry projection")
    return validated_request
