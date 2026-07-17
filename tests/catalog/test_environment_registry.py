from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from bionodulo.nodes.catalog import environment_registry as registry
from bionodulo.nodes.contract.environments import ExecutionPlatform
from test_node_spec import evidence_record, external_identity, external_spec, pixi_environment


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
    tool_id = environment_name.split("-", 1)[0]
    return registry.EnvironmentRegistryEntry(
        environment_id=environment_id,
        environment_digest=SHA_C,
        lock_set=lock_set(environment_name, bindings),
        runtime_bindings=(
            registry.EnvironmentRuntimeBinding(
                node_id=f"{tool_id}-node",
                tool_id=tool_id,
                tool_version="1.0",
                binding_kind="package",
                binding_id=tool_id,
            ),
        ),
    )


def environment_registry() -> registry.EnvironmentRegistry:
    return registry.EnvironmentRegistry(
        schema_version=2,
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


def validated_node_specs() -> tuple[object, object]:
    samtools = external_spec()
    bcftools = external_spec(
        identity=external_identity(
            stable_id="legacy::Bcftools Call v1",
            machine_id="bcftools_call",
            tool_id="bcftools",
        ),
        environment=pixi_environment(tool_id="bcftools"),
        evidence=evidence_record(tool_id="bcftools"),
    )
    return samtools, bcftools


def test_environment_registry_and_request_protocol_is_schema_version_two() -> None:
    spec = external_spec()
    source = registry.derive_environment_registry((spec,))
    request = registry.compile_workflow_environment_request(
        source.canonical_json_bytes(),
        (
            registry.WorkflowEnvironmentSelection(
                environment_id=source.environments[0].environment_id,
                platform=ExecutionPlatform.LINUX_AMD64,
            ),
        ),
        node_specs=(spec,),
    )

    assert source.schema_version == 2
    assert request.schema_version == 2
    with pytest.raises(ValidationError, match="schema_version"):
        registry.EnvironmentRegistry.model_validate({**source.model_dump(mode="python"), "schema_version": 1})
    with pytest.raises(ValidationError, match="schema_version"):
        registry.WorkflowEnvironmentRequest.model_validate({**request.model_dump(mode="python"), "schema_version": 1})


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("tool_version", "1.0\n"),
        ("tool_version", "1.0β"),
        ("binding_id", "samtools\x7f"),
        ("binding_id", "samtoolsβ"),
    ),
)
def test_environment_runtime_binding_requires_printable_ascii(field: str, value: str) -> None:
    payload = entry().runtime_bindings[0].model_dump(mode="python")
    payload[field] = value

    with pytest.raises(ValidationError, match="printable ASCII"):
        registry.EnvironmentRuntimeBinding.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("tool_version", " 1.0"),
        ("tool_version", "1.0 "),
        ("binding_id", " samtools"),
        ("binding_id", "samtools "),
    ),
)
def test_environment_runtime_binding_rejects_outer_whitespace(field: str, value: str) -> None:
    payload = entry().runtime_bindings[0].model_dump(mode="python")
    payload[field] = value

    with pytest.raises(ValidationError, match="outer whitespace"):
        registry.EnvironmentRuntimeBinding.model_validate(payload)


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
        registry.EnvironmentRegistry(schema_version=2, environments=(second, first))
    with pytest.raises(ValidationError, match="environment IDs.*unique"):
        registry.EnvironmentRegistry(schema_version=2, environments=(first, first))
    with pytest.raises(ValidationError, match="environment names.*unique"):
        registry.EnvironmentRegistry(
            schema_version=2,
            environments=(first, entry("env.other", environment_name="alignment-tools")),
        )


def test_registry_canonical_bytes_are_exact_and_omit_catalog_digest() -> None:
    value = registry.EnvironmentRegistry(
        schema_version=2,
        environments=(entry(),),
    )

    expected = {
        "environments": [
            {
                "environment_digest": SHA_C,
                "environment_id": "env.alignment-tools",
                "lock_set": {
                    "environment_name": "alignment-tools",
                    "platform_locks": [
                        {
                            "lock_digest": SHA_A,
                            "platform": "linux/amd64",
                        }
                    ],
                },
                "runtime_bindings": [
                    {
                        "binding_id": "alignment",
                        "binding_kind": "package",
                        "node_id": "alignment-node",
                        "tool_id": "alignment",
                        "tool_version": "1.0",
                    }
                ],
            }
        ],
        "schema_version": 2,
    }
    assert value.canonical_json_bytes() == json.dumps(
        expected,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
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


def test_registry_is_derived_from_validated_node_spec_environment_and_runtime_binding() -> None:
    spec = external_spec()
    assert spec.environment is not None
    assert spec.runtime_binding is not None

    source = registry.derive_environment_registry((spec,))

    assert len(source.environments) == 1
    captured = source.environments[0]
    assert captured.environment_id == spec.environment.environment_id
    assert captured.environment_digest == spec.environment.environment_digest()
    assert captured.lock_set.environment_name == spec.environment.locks[0].environment_name
    assert captured.lock_set.platform_locks[0].lock_digest == spec.environment.locks[0].lock_digest()
    assert captured.runtime_bindings == (
        registry.EnvironmentRuntimeBinding(
            node_id=spec.identity.machine_id,
            tool_id=spec.runtime_binding.tool_id,
            tool_version=spec.runtime_binding.tool_version,
            binding_kind="package",
            binding_id=spec.runtime_binding.package_name,
        ),
    )


def test_registry_validation_rejects_zero_digest_substitution_for_same_environment_id() -> None:
    spec = external_spec()
    source = registry.derive_environment_registry((spec,))
    captured = source.environments[0]
    substituted = registry.EnvironmentRegistry(
        schema_version=2,
        environments=(
            captured.model_copy(
                update={
                    "lock_set": captured.lock_set.model_copy(
                        update={
                            "platform_locks": (
                                captured.lock_set.platform_locks[0].model_copy(
                                    update={"lock_digest": "sha256:" + "0" * 64}
                                ),
                            )
                        }
                    )
                }
            ),
        ),
    )

    with pytest.raises(ValueError, match="NodeSpec|lock digest"):
        registry.validate_environment_registry(substituted, (spec,))


def test_registry_validation_rejects_environment_and_runtime_binding_substitution() -> None:
    spec = external_spec()
    source = registry.derive_environment_registry((spec,))
    captured = source.environments[0]
    substituted = registry.EnvironmentRegistry(
        schema_version=2,
        environments=(
            captured.model_copy(
                update={
                    "environment_digest": "sha256:" + "0" * 64,
                    "runtime_bindings": (
                        captured.runtime_bindings[0].model_copy(update={"binding_id": "bcftools"}),
                    ),
                }
            ),
        ),
    )

    with pytest.raises(ValueError, match="NodeSpec|environment digest|runtime"):
        registry.validate_environment_registry(substituted, (spec,))


def test_persisted_registry_decoder_requires_unique_canonical_versioned_json_bytes() -> None:
    spec = external_spec()
    content = registry.derive_environment_registry((spec,)).canonical_json_bytes()
    duplicate = content.replace(b'{"environments":', b'{"schema_version":2,"environments":', 1)
    omitted_version = content.replace(b',"schema_version":2}', b'}', 1)

    with pytest.raises(ValueError, match="duplicate JSON key: schema_version"):
        registry.decode_environment_registry(duplicate, node_specs=(spec,))
    with pytest.raises((ValidationError, ValueError), match="schema_version"):
        registry.decode_environment_registry(omitted_version, node_specs=(spec,))
    with pytest.raises(ValueError, match="canonical"):
        registry.decode_environment_registry(content + b"\n", node_specs=(spec,))


def test_persisted_registry_decoder_limits_transport_to_one_mibibyte() -> None:
    spec = external_spec()
    content = registry.derive_environment_registry((spec,)).canonical_json_bytes()
    oversized = content + b" " * (1024 * 1024 + 1 - len(content))

    assert len(oversized) == 1024 * 1024 + 1
    with pytest.raises(ValueError, match="1048576|size|between"):
        registry.decode_environment_registry(oversized, node_specs=(spec,))


def test_persisted_registry_decoder_enforces_64_level_json_nesting_bound() -> None:
    registry._validate_json_nesting("[" * 64 + "0" + "]" * 64)
    registry._validate_json_nesting(json.dumps("[" * 128 + "]" * 128))

    with pytest.raises(ValueError, match="nesting depth.*64|64.*nesting depth"):
        registry._validate_json_nesting("[" * 65 + "0" + "]" * 65)

    spec = external_spec()
    content = registry.derive_environment_registry((spec,)).canonical_json_bytes()
    nested = b"[" * 65 + b"0" + b"]" * 65
    noncanonical = content[:-1] + b',"unknown":' + nested + b"}"
    with pytest.raises(ValueError, match="nesting depth.*64|64.*nesting depth"):
        registry.decode_environment_registry(noncanonical, node_specs=(spec,))


@pytest.mark.parametrize("unsafe_key", ("__proto__", "constructor", "prototype"))
def test_persisted_registry_decoder_rejects_unsafe_keys_at_any_depth(unsafe_key: str) -> None:
    spec = external_spec()
    content = registry.derive_environment_registry((spec,)).canonical_json_bytes()
    injected = content.replace(
        b'{"environment_name":',
        b'{"' + unsafe_key.encode("ascii") + b'":{},"environment_name":',
        1,
    )

    with pytest.raises(ValueError, match=f"unsafe JSON key: {unsafe_key}"):
        registry.decode_environment_registry(injected, node_specs=(spec,))


def test_request_admission_reopens_exact_registry_bytes_and_rejects_stale_or_tampered_content() -> None:
    spec = external_spec()
    source = registry.derive_environment_registry((spec,))
    content = source.canonical_json_bytes()
    selection = registry.WorkflowEnvironmentSelection(
        environment_id=source.environments[0].environment_id,
        platform=ExecutionPlatform.LINUX_AMD64,
    )
    request = registry.compile_workflow_environment_request(
        content,
        (selection,),
        node_specs=(spec,),
    )
    stale_content = source.model_copy(
        update={
            "environments": (
                source.environments[0].model_copy(
                    update={"environment_digest": "sha256:" + "0" * 64}
                ),
            )
        }
    ).canonical_json_bytes()

    assert request.environments[0].environment_digest == spec.environment.environment_digest()
    assert registry.admit_workflow_environment_request(
        request,
        registry_content=content,
        node_specs=(spec,),
    ) == request
    with pytest.raises(ValueError, match="registry|digest|NodeSpec"):
        registry.admit_workflow_environment_request(
            request,
            registry_content=stale_content,
            node_specs=(spec,),
        )


def test_request_admission_rejects_forged_stored_raw_registry_digest() -> None:
    spec = external_spec()
    content = registry.derive_environment_registry((spec,)).canonical_json_bytes()
    request = registry.compile_workflow_environment_request(
        content,
        (
            registry.WorkflowEnvironmentSelection(
                environment_id=spec.environment.environment_id,
                platform=ExecutionPlatform.LINUX_AMD64,
            ),
        ),
        node_specs=(spec,),
    )
    forged = request.model_copy(update={"environment_registry_sha256": "sha256:" + "0" * 64})

    with pytest.raises(ValueError, match="raw registry|digest"):
        registry.admit_workflow_environment_request(
            forged,
            registry_content=content,
            node_specs=(spec,),
        )


def test_workflow_request_compiler_is_stable_under_input_order_and_duplicates() -> None:
    specs = validated_node_specs()
    source = registry.derive_environment_registry(specs)
    content = source.canonical_json_bytes()
    first = registry.WorkflowEnvironmentSelection(
        environment_id="samtools-runtime",
        platform=ExecutionPlatform.LINUX_AMD64,
    )
    second = registry.WorkflowEnvironmentSelection(
        environment_id="bcftools-runtime",
        platform=ExecutionPlatform.LINUX_AMD64,
    )

    forward = registry.compile_workflow_environment_request(content, (first, second, first), node_specs=specs)
    reverse = registry.compile_workflow_environment_request(content, (second, first), node_specs=specs)

    assert forward == reverse
    assert forward.canonical_json_bytes() == reverse.canonical_json_bytes()
    assert tuple(item.environment_id for item in forward.environments) == (
        "bcftools-runtime",
        "samtools-runtime",
    )
    assert forward.environment_registry_sha256 == registry.environment_registry_digest(content)


def test_workflow_request_projection_has_a_deterministic_cross_language_wire_shape() -> None:
    spec = external_spec()
    assert spec.environment is not None
    source = registry.derive_environment_registry((spec,))
    content = source.canonical_json_bytes()
    request = registry.compile_workflow_environment_request(
        content,
        (
            registry.WorkflowEnvironmentSelection(
                environment_id=spec.environment.environment_id,
                platform=ExecutionPlatform.LINUX_AMD64,
            ),
        ),
        node_specs=(spec,),
    )
    expected = {
        "environment_registry_sha256": registry.environment_registry_digest(content),
        "environments": [
            {
                "environment_digest": spec.environment.environment_digest(),
                "environment_id": "samtools-runtime",
                "environment_name": "samtools-runtime",
                "lock_set_digest": source.environments[0].lock_set.lock_set_digest(),
                "platform": "linux/amd64",
                "platform_lock_digest": spec.environment.locks[0].lock_digest(),
            }
        ],
        "schema_version": 2,
    }

    assert request.canonical_json_bytes() == json.dumps(
        expected,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def test_workflow_request_rejects_unknown_environment_or_unlocked_platform() -> None:
    spec = external_spec()
    source = registry.derive_environment_registry((spec,))
    content = source.canonical_json_bytes()

    with pytest.raises(ValueError, match="unknown environment"):
        registry.compile_workflow_environment_request(
            content,
            (
                registry.WorkflowEnvironmentSelection(
                    environment_id="env.unknown",
                    platform=ExecutionPlatform.LINUX_AMD64,
                ),
            ),
            node_specs=(spec,),
        )
    with pytest.raises(ValueError, match="platform"):
        registry.compile_workflow_environment_request(
            content,
            (
                registry.WorkflowEnvironmentSelection(
                    environment_id="samtools-runtime",
                    platform=ExecutionPlatform.LINUX_ARM64,
                ),
            ),
            node_specs=(spec,),
        )


@pytest.mark.parametrize(
    "model_name",
    (
        "EnvironmentPlatformLockBinding",
        "EnvironmentLockSetDescriptor",
        "EnvironmentRuntimeBinding",
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
