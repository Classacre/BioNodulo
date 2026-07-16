from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from bionodulo.nodes.catalog import environment_registry as registry
from bionodulo.nodes.contract.environments import ExecutionPlatform


SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64


def platform_binding(
    platform: ExecutionPlatform = ExecutionPlatform.LINUX_AMD64,
    digest: str = SHA_A,
) -> registry.EnvironmentPlatformLockBinding:
    return registry.EnvironmentPlatformLockBinding(platform=platform, lock_digest=digest)


def lock_set(
    environment_name: str = "alignment-tools",
    bindings: tuple[registry.EnvironmentPlatformLockBinding, ...] | None = None,
) -> registry.EnvironmentLockSetDescriptor:
    return registry.EnvironmentLockSetDescriptor(
        environment_name=environment_name,
        platform_locks=bindings or (platform_binding(),),
    )


def entry(
    environment_id: str = "env.alignment-tools",
    *,
    environment_name: str = "alignment-tools",
    bindings: tuple[registry.EnvironmentPlatformLockBinding, ...] | None = None,
) -> registry.EnvironmentRegistryEntry:
    return registry.EnvironmentRegistryEntry(
        environment_id=environment_id,
        lock_set=lock_set(environment_name, bindings),
    )


def environment_registry() -> registry.EnvironmentRegistry:
    return registry.EnvironmentRegistry(
        schema_version=1,
        environments=(
            entry(),
            entry(
                "env.python-analysis",
                environment_name="python-analysis",
                bindings=(
                    platform_binding(ExecutionPlatform.LINUX_AMD64, SHA_B),
                    platform_binding(ExecutionPlatform.LINUX_ARM64, SHA_C),
                ),
            ),
        ),
    )


def test_lock_set_descriptor_binds_environment_name_and_platform_digests() -> None:
    descriptor = lock_set()
    renamed = descriptor.model_copy(update={"environment_name": "other-environment"})
    changed_lock = lock_set(bindings=(platform_binding(digest=SHA_B),))

    assert descriptor.lock_set_digest() != renamed.lock_set_digest()
    assert descriptor.lock_set_digest() != changed_lock.lock_set_digest()
    assert descriptor == registry.EnvironmentLockSetDescriptor.model_validate_json(descriptor.model_dump_json())
    assert hash(descriptor)


def test_lock_set_platform_bindings_must_be_unique_and_canonical() -> None:
    amd = platform_binding()
    arm = platform_binding(ExecutionPlatform.LINUX_ARM64, SHA_B)

    with pytest.raises(ValidationError, match="canonical"):
        lock_set(bindings=(arm, amd))
    with pytest.raises(ValidationError, match="unique"):
        lock_set(bindings=(amd, amd))


def test_registry_entries_bind_unique_sorted_ids_and_names() -> None:
    first = entry()
    second = entry("env.python-analysis", environment_name="python-analysis")

    with pytest.raises(ValidationError, match="canonical"):
        registry.EnvironmentRegistry(schema_version=1, environments=(second, first))
    with pytest.raises(ValidationError, match="environment IDs.*unique"):
        registry.EnvironmentRegistry(schema_version=1, environments=(first, first))
    with pytest.raises(ValidationError, match="environment names.*unique"):
        registry.EnvironmentRegistry(
            schema_version=1,
            environments=(first, entry("env.other", environment_name="alignment-tools")),
        )


def test_registry_canonical_bytes_are_exact_and_omit_catalog_digest() -> None:
    value = registry.EnvironmentRegistry(
        schema_version=1,
        environments=(entry(),),
    )

    assert value.canonical_json_bytes() == (
        b'{"environments":[{"environment_id":"env.alignment-tools","lock_set":'
        b'{"environment_name":"alignment-tools","platform_locks":['
        b'{"lock_digest":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
        b'"platform":"linux/amd64"}]}}],"schema_version":1}'
    )
    assert b"catalog_digest" not in value.canonical_json_bytes()
    assert value.registry_digest() == registry.environment_registry_digest(value.canonical_json_bytes())


def test_registry_forbids_catalog_digest_in_authoring_or_wire_data() -> None:
    values = json.loads(environment_registry().model_dump_json())
    values["catalog_digest"] = SHA_A

    with pytest.raises(ValidationError, match="catalog_digest"):
        registry.EnvironmentRegistry.model_validate(values)


def test_one_byte_registry_mutation_changes_registry_digest() -> None:
    content = environment_registry().canonical_json_bytes()
    offset = content.index(b"alignment-tools")
    mutated = content[:offset] + b"Alignment-tools" + content[offset + len("alignment-tools") :]

    assert len(mutated) == len(content)
    assert registry.environment_registry_digest(mutated) != registry.environment_registry_digest(content)


def test_workflow_request_compiler_is_stable_under_input_order_and_duplicates() -> None:
    source = environment_registry()
    first = registry.WorkflowEnvironmentSelection(
        environment_id="env.python-analysis",
        platform=ExecutionPlatform.LINUX_ARM64,
    )
    second = registry.WorkflowEnvironmentSelection(
        environment_id="env.alignment-tools",
        platform=ExecutionPlatform.LINUX_AMD64,
    )

    forward = registry.compile_workflow_environment_request(source, (first, second, first))
    reverse = registry.compile_workflow_environment_request(source, (second, first))

    assert forward == reverse
    assert forward.canonical_json_bytes() == reverse.canonical_json_bytes()
    assert tuple(item.environment_id for item in forward.environments) == (
        "env.alignment-tools",
        "env.python-analysis",
    )
    assert forward.environment_registry_sha256 == source.registry_digest()


def test_workflow_request_projection_has_a_deterministic_cross_language_wire_shape() -> None:
    source = registry.EnvironmentRegistry(schema_version=1, environments=(entry(),))
    request = registry.compile_workflow_environment_request(
        source,
        (
            registry.WorkflowEnvironmentSelection(
                environment_id="env.alignment-tools",
                platform=ExecutionPlatform.LINUX_AMD64,
            ),
        ),
    )
    expected = {
        "environment_registry_sha256": source.registry_digest(),
        "environments": [
            {
                "environment_id": "env.alignment-tools",
                "environment_name": "alignment-tools",
                "lock_set_digest": source.environments[0].lock_set.lock_set_digest(),
                "platform": "linux/amd64",
                "platform_lock_digest": SHA_A,
            }
        ],
        "schema_version": 1,
    }

    assert request.canonical_json_bytes() == json.dumps(
        expected,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def test_workflow_request_rejects_unknown_environment_or_unlocked_platform() -> None:
    source = registry.EnvironmentRegistry(schema_version=1, environments=(entry(),))

    with pytest.raises(ValueError, match="unknown environment"):
        registry.compile_workflow_environment_request(
            source,
            (
                registry.WorkflowEnvironmentSelection(
                    environment_id="env.unknown",
                    platform=ExecutionPlatform.LINUX_AMD64,
                ),
            ),
        )
    with pytest.raises(ValueError, match="platform"):
        registry.compile_workflow_environment_request(
            source,
            (
                registry.WorkflowEnvironmentSelection(
                    environment_id="env.alignment-tools",
                    platform=ExecutionPlatform.LINUX_ARM64,
                ),
            ),
        )


@pytest.mark.parametrize(
    "model_name",
    (
        "EnvironmentPlatformLockBinding",
        "EnvironmentLockSetDescriptor",
        "EnvironmentRegistryEntry",
        "EnvironmentRegistry",
        "WorkflowEnvironmentSelection",
        "WorkflowEnvironmentRequestItem",
        "WorkflowEnvironmentRequest",
    ),
)
def test_registry_models_are_strict_frozen_and_forbid_extras(model_name: str) -> None:
    model = getattr(registry, model_name)

    assert model.model_config["strict"] is True
    assert model.model_config["frozen"] is True
    assert model.model_config["extra"] == "forbid"
    assert model.model_config["revalidate_instances"] == "always"
