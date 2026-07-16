"""Canonical environment registry and workflow request projections."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from bionodulo.nodes.contract.artifacts import ArtifactId, _StrictFrozenModel
from bionodulo.nodes.contract.environments import ExecutionPlatform, Sha256Digest


def environment_registry_digest(content: bytes) -> str:
    """Digest exact registry bytes without adding a self-reference field."""

    if type(content) is not bytes:
        raise TypeError("environment registry content must be exact bytes")
    return "sha256:" + hashlib.sha256(content).hexdigest()


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


class EnvironmentRegistryEntry(_CanonicalModel):
    environment_id: ArtifactId
    lock_set: EnvironmentLockSetDescriptor


class EnvironmentRegistry(_CanonicalModel):
    schema_version: Literal[1] = 1
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


class WorkflowEnvironmentSelection(_CanonicalModel):
    environment_id: ArtifactId
    platform: ExecutionPlatform


class WorkflowEnvironmentRequestItem(_CanonicalModel):
    environment_id: ArtifactId
    environment_name: ArtifactId
    platform: ExecutionPlatform
    platform_lock_digest: Sha256Digest
    lock_set_digest: Sha256Digest


class WorkflowEnvironmentRequest(_CanonicalModel):
    schema_version: Literal[1] = 1
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


def compile_workflow_environment_request(
    registry: EnvironmentRegistry,
    selections: Iterable[WorkflowEnvironmentSelection],
) -> WorkflowEnvironmentRequest:
    """Project unordered workflow selections through one canonical registry."""

    validated_registry = EnvironmentRegistry.model_validate(registry)
    entries = {entry.environment_id: entry for entry in validated_registry.environments}
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
            environment_name=entry.lock_set.environment_name,
            platform=selection.platform,
            platform_lock_digest=binding.lock_digest,
            lock_set_digest=entry.lock_set.lock_set_digest(),
        )
    return WorkflowEnvironmentRequest(
        schema_version=1,
        environment_registry_sha256=validated_registry.registry_digest(),
        environments=tuple(requested[key] for key in sorted(requested)),
    )
