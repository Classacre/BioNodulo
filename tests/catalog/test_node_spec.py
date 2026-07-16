from __future__ import annotations

import ast
import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

import bionodulo.nodes.contract as contract
from bionodulo.nodes.contract.artifacts import ArtifactPort, Cardinality
from bionodulo.nodes.contract.environments import (
    ContainerEnvironment,
    ContainerImageLock,
    ExecutableProbe,
    ExecutionPlatform,
    ImportProbe,
    LockedArtifact,
    PixiEnvironment,
    PlatformLock,
    PythonEnvironment,
    RPackageProbe,
    REnvironment,
    ResolverIdentity,
)
from bionodulo.nodes.contract.evidence import (
    ByteRangeLocator,
    ContentLocatorKind,
    DocumentationProofKind,
    DocumentationVersionProof,
    EvidenceClaim,
    EvidenceRecord,
    EvidenceSource,
    FailureCode,
    RetainedText,
    RetainedTextOrigin,
    RetainedTextProvenance,
    SourceContentFormat,
    SourceKind,
    VerificationEvidence,
    VerificationKind,
    VerificationOutcome,
)
from bionodulo.nodes.contract.maturity import (
    AccessClass,
    Gate,
    GateAssessment,
    GateResult,
    MaturityRecord,
)
from bionodulo.nodes.contract.model import (
    ExecutionKind,
    NodeIdentity,
    NodeOwnership,
    NodePresentation,
    NodeSpec,
    PortAlias,
    PortAliasScope,
)
from bionodulo.nodes.contract.outputs import (
    ConditionalCollector,
    ExactCollector,
    OutputSpec,
)
from bionodulo.nodes.contract.parameters import (
    ParameterSpec,
    SecretSpec,
    ValueKind,
    ValuePort,
)


SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64
SHA_D = "sha256:" + "d" * 64
PROJECTION_GOLDEN_CONTRACT_DIGEST = "sha256:e28ff7f63d100cd2bdb86b58c7e50a6da8f9eadd47850576fe85475c404b7b69"
CAPTURE_DATE = date(2026, 7, 16)
PLATFORM = ExecutionPlatform.LINUX_AMD64
CONTAINER_IMAGE = "registry.example.org/tools/samtools@" + SHA_A
CATALOG_PATH = "bionodulo/nodes/catalog/tools/samtools/evidence.authoring.json"


def locked_artifact(
    name: str,
    version: str,
    *,
    digest: str = SHA_B,
) -> LockedArtifact:
    filename = f"{name}-{version}-build.conda"
    return LockedArtifact(
        name=name,
        version=version,
        build="build",
        filename=filename,
        url=f"https://packages.example.org/linux-64/{filename}",
        sha256=digest,
        size_bytes=1024,
    )


def platform_lock(*artifacts: LockedArtifact) -> PlatformLock:
    return PlatformLock(
        platform=PLATFORM,
        resolver_platform="linux-64",
        resolver=ResolverIdentity(
            name="pixi",
            version="0.24.2",
            config_digest=SHA_A,
        ),
        lockfile_sha256=SHA_C,
        artifacts=artifacts,
    )


def pixi_environment(
    *,
    locked: bool = True,
    tool_id: str = "samtools",
    tool_version: str = "1.20",
) -> PixiEnvironment:
    return PixiEnvironment(
        environment_id=f"{tool_id}-runtime",
        platforms=(PLATFORM,),
        packages=(f"{tool_id}=={tool_version}",),
        locks=(platform_lock(locked_artifact(tool_id, tool_version)),) if locked else (),
    )


def python_environment(*, locked: bool = True) -> PythonEnvironment:
    return PythonEnvironment(
        environment_id="python-runtime",
        platforms=(PLATFORM,),
        python_version="==3.12.4",
        packages=("samtools==1.20",),
        locks=(
            platform_lock(
                locked_artifact("python", "3.12.4"),
                locked_artifact("samtools", "1.20", digest=SHA_D),
            ),
        )
        if locked
        else (),
        import_probes=(
            ImportProbe(
                probe_id="samtools-import",
                module="samtools",
                expected_version="1.20",
            ),
        ),
    )


def r_environment(*, locked: bool = True) -> REnvironment:
    return REnvironment(
        environment_id="r-runtime",
        platforms=(PLATFORM,),
        r_version="==4.4.1",
        packages=("samtools==1.20",),
        locks=(
            platform_lock(
                locked_artifact("r-base", "4.4.1"),
                locked_artifact("samtools", "1.20", digest=SHA_D),
            ),
        )
        if locked
        else (),
        package_probes=(
            RPackageProbe(
                probe_id="samtools-r-package",
                package="samtools",
                expected_version="1.20",
            ),
        ),
    )


def container_environment(*, locked: bool = True) -> ContainerEnvironment:
    return ContainerEnvironment(
        environment_id="container-runtime",
        platforms=(PLATFORM,),
        image=CONTAINER_IMAGE,
        image_locks=(
            ContainerImageLock(
                platform=PLATFORM,
                resolver_platform="linux-64",
                index_image=CONTAINER_IMAGE,
                image=CONTAINER_IMAGE,
            ),
        )
        if locked
        else (),
    )


def authored(value: str, pointer: str) -> RetainedText:
    return RetainedText(
        value=value,
        provenance=RetainedTextProvenance(
            origin=RetainedTextOrigin.CATALOG_AUTHOR,
            catalog_path=CATALOG_PATH,
            catalog_content_sha256=SHA_D,
            field_pointer=pointer,
        ),
    )


def byte_locator(start: int, end: int) -> ByteRangeLocator:
    return ByteRangeLocator(
        kind=ContentLocatorKind.BYTE_RANGE,
        start_byte=start,
        end_byte_exclusive=end,
    )


def evidence_record(
    *,
    tool_id: str = "samtools",
    tool_version: str = "1.20",
    verifications: tuple[VerificationEvidence, ...] = (),
) -> EvidenceRecord:
    source_url = f"https://docs.example.org/{tool_id}/{tool_version}/reference.html"
    source = EvidenceSource(
        source_id=f"{tool_id}-manual",
        tool_id=tool_id,
        kind=SourceKind.OFFICIAL_MANUAL,
        tool_version=tool_version,
        retrieved_at=CAPTURE_DATE,
        content_sha256=SHA_A,
        content_format=SourceContentFormat.TEXT,
        title=authored(f"{tool_id} {tool_version} manual", "/sources/manual/title"),
        description=authored(
            "Authoritative behavior reference for the pinned tool release.",
            "/sources/manual/description",
        ),
        url=source_url,
        documentation_proof=DocumentationVersionProof(
            proof_kind=DocumentationProofKind.DECLARED_METADATA,
            tool_id=tool_id,
            tool_version=tool_version,
            source_url=source_url,
            source_content_sha256=SHA_A,
            locator=byte_locator(0, 1),
            proof_content_sha256=SHA_B,
        ),
    )
    claim = EvidenceClaim(
        claim_id="output-contract",
        contract_pointer="/outputs/result/collector",
        source_id=source.source_id,
        locator=byte_locator(1, 2),
        statement=authored(
            "The command writes the declared result file.",
            "/claims/output-contract/statement",
        ),
        source_content_sha256=SHA_A,
        excerpt_sha256=SHA_B,
        contract_value_sha256=SHA_C,
    )
    return EvidenceRecord(
        schema_version=2,
        tool_id=tool_id,
        tool_version=tool_version,
        sources=(source,),
        claims=(claim,),
        verifications=tuple(sorted(verifications, key=lambda item: item.evidence_id)),
    )


_GATE_VERIFICATION_KINDS = dict(zip(Gate, VerificationKind, strict=True))
_VERIFICATION_FAILURE_CODES = {
    VerificationKind.INVENTORY: FailureCode.INVENTORY_MISSING,
    VerificationKind.EVIDENCE_COVERAGE: FailureCode.EVIDENCE_MISSING,
    VerificationKind.CONTRACT_COMPILE: FailureCode.CONTRACT_INVALID,
    VerificationKind.COMMAND_FIXTURE: FailureCode.COMMAND_FIXTURE_FAILED,
    VerificationKind.ENVIRONMENT_PROBE: FailureCode.ENVIRONMENT_RESOLUTION_FAILED,
    VerificationKind.TOOL_SMOKE: FailureCode.TOOL_SMOKE_FAILED,
    VerificationKind.CLOUD_RUN: FailureCode.CLOUD_RUN_FAILED,
    VerificationKind.WORKFLOW_RUN: FailureCode.WORKFLOW_RUN_FAILED,
}
_GATE_FAILURE_CODES = dict(zip(Gate, _VERIFICATION_FAILURE_CODES.values(), strict=True))


def verification_evidence(
    environment: object,
    *,
    kind: VerificationKind = VerificationKind.TOOL_SMOKE,
    outcome: VerificationOutcome = VerificationOutcome.PASSED,
    failure_code: FailureCode | None = None,
    evidence_id: str | None = None,
    test_id: str | None = None,
    tool_id: str = "samtools",
    tool_version: str = "1.20",
    verifier_id: str = "catalog-verifier",
    verifier_version: str = "1.0.0",
    environment_sha256: str | None = None,
) -> VerificationEvidence:
    assert isinstance(
        environment,
        (PixiEnvironment, PythonEnvironment, REnvironment, ContainerEnvironment),
    )
    context: dict[str, object] = {
        "fixture_id": None,
        "fixture_sha256": None,
        "environment_sha256": None,
        "catalog_sha256": SHA_A,
        "platform_sha256": None,
        "release_sha256": None,
    }
    if kind in (
        VerificationKind.COMMAND_FIXTURE,
        VerificationKind.TOOL_SMOKE,
        VerificationKind.CLOUD_RUN,
        VerificationKind.WORKFLOW_RUN,
    ):
        context.update(fixture_id="tiny-bam-v1", fixture_sha256=SHA_C)
    if kind in (
        VerificationKind.COMMAND_FIXTURE,
        VerificationKind.ENVIRONMENT_PROBE,
        VerificationKind.TOOL_SMOKE,
        VerificationKind.CLOUD_RUN,
        VerificationKind.WORKFLOW_RUN,
    ):
        context["environment_sha256"] = environment.environment_digest()
    if kind in (
        VerificationKind.ENVIRONMENT_PROBE,
        VerificationKind.TOOL_SMOKE,
        VerificationKind.CLOUD_RUN,
        VerificationKind.WORKFLOW_RUN,
    ):
        context["platform_sha256"] = SHA_B
    if kind in (VerificationKind.CLOUD_RUN, VerificationKind.WORKFLOW_RUN):
        context["release_sha256"] = SHA_D
    if environment_sha256 is not None:
        context["environment_sha256"] = environment_sha256
    if outcome is VerificationOutcome.FAILED and failure_code is None:
        failure_code = _VERIFICATION_FAILURE_CODES[kind]
    return VerificationEvidence(
        evidence_id=evidence_id or f"{kind.value}-{outcome.value}-linux-amd64",
        tool_id=tool_id,
        tool_version=tool_version,
        kind=kind,
        outcome=outcome,
        failure_code=failure_code,
        test_id=test_id or f"{kind.value}-fixture-v1",
        result_sha256=SHA_D,
        verified_at=CAPTURE_DATE,
        verifier_id=verifier_id,
        verifier_version=verifier_version,
        **context,
    )


def verification_for_gate(
    gate: Gate,
    environment: object,
    **updates: object,
) -> VerificationEvidence:
    return verification_evidence(
        environment,
        kind=_GATE_VERIFICATION_KINDS[gate],
        **updates,
    )


def gate_assessment(
    gate: Gate,
    *digests: str,
    result: GateResult = GateResult.PASSED,
    failure_code: FailureCode | None = None,
    verifier_id: str = "catalog-verifier",
    verifier_version: str = "1.0.0",
) -> GateAssessment:
    if result is GateResult.FAILED and failure_code is None:
        failure_code = _GATE_FAILURE_CODES[gate]
    return GateAssessment(
        gate=gate,
        result=result,
        verification_digests=tuple(sorted(digests)),
        verified_at=CAPTURE_DATE,
        verifier_id=verifier_id,
        verifier_version=verifier_version,
        failure_code=failure_code,
    )


def maturity_record(
    *,
    access_classes: tuple[AccessClass, ...] = (AccessClass.PUBLIC,),
    assessments: tuple[GateAssessment, ...] = (),
) -> MaturityRecord:
    return MaturityRecord(
        schema_version=2,
        access_classes=access_classes,
        assessments=assessments,
    )


def runtime_binding(
    *,
    tool_id: str = "samtools",
    tool_version: str = "1.20",
    execution_kind: ExecutionKind = ExecutionKind.ARGV,
    execution_factory: str = "bionodulo.nodes.catalog.tools.samtools.sort:build_plan",
    **updates: object,
) -> object:
    values: dict[str, object] = {
        "tool_id": tool_id,
        "tool_version": tool_version,
        "execution_kind": execution_kind,
        "execution_factory": execution_factory,
        "package_name": None,
        "probe_id": None,
        "container_image": None,
    }
    if execution_kind in (ExecutionKind.ARGV, ExecutionKind.PIPELINE, ExecutionKind.SCRIPT):
        values["package_name"] = tool_id
    elif execution_kind in (ExecutionKind.PYTHON, ExecutionKind.HTTP):
        values["probe_id"] = f"{tool_id}-import"
    elif execution_kind is ExecutionKind.R:
        values["probe_id"] = f"{tool_id}-r-package"
    else:
        values["container_image"] = CONTAINER_IMAGE
    values.update(updates)
    return contract.RuntimeBinding(**values)


def retained_artifact(
    kind: object,
    artifact_id: str,
    digest: str,
) -> object:
    return contract.RetainedArtifact(
        kind=kind,
        artifact_id=artifact_id,
        sha256=digest,
    )


def retained_inventory(
    *,
    identity: NodeIdentity,
    environment: object,
    evidence: EvidenceRecord,
    contract_digest: str | None = None,
) -> object:
    assert isinstance(
        environment,
        (PixiEnvironment, PythonEnvironment, REnvironment, ContainerEnvironment),
    )
    if contract_digest is None:
        contract_digest = external_spec(
            identity=identity,
            environment=environment,
            evidence=evidence,
            maturity=None,
        ).contract_digest()
    artifacts = [
        retained_artifact(
            contract.RetainedArtifactKind.CONTRACT,
            identity.machine_id,
            contract_digest,
        ),
        retained_artifact(
            contract.RetainedArtifactKind.ENVIRONMENT,
            environment.environment_id,
            environment.environment_digest(),
        ),
        retained_artifact(
            contract.RetainedArtifactKind.EVIDENCE_RECORD,
            evidence.tool_id,
            evidence.evidence_digest(),
        ),
    ]
    artifacts.extend(
        retained_artifact(
            contract.RetainedArtifactKind.VERIFICATION,
            verification.evidence_id,
            verification.verification_digest(),
        )
        for verification in evidence.verifications
    )
    return contract.RetainedEvidenceInventory(
        artifacts=tuple(sorted(artifacts, key=lambda item: (item.kind.value, item.artifact_id))),
    )


def external_identity(**updates: object) -> NodeIdentity:
    values: dict[str, object] = {
        "stable_id": "legacy::Samtools Sort v1",
        "machine_id": "samtools_sort",
        "contract_version": "2.0.0",
        "implementation_version": "1.0.0",
        "tool_id": "samtools",
        "tool_version": "1.20",
        "aliases": (),
        "port_aliases": (),
    }
    values.update(updates)
    return NodeIdentity(**values)


def presentation(**updates: object) -> NodePresentation:
    values: dict[str, object] = {
        "display_name": "Samtools Sort",
        "description": "Sort a BAM alignment file.",
        "palette_path": ("Alignment", "SAM/BAM"),
        "domain_tags": ("alignment", "bam"),
        "operation_kind": "transform",
        "owner": NodeOwnership.EXTERNAL_TOOL,
        "tool_family": "samtools",
        "provider": None,
    }
    values.update(updates)
    return NodePresentation(**values)


def external_spec(**updates: object) -> NodeSpec:
    values: dict[str, object] = {
        "identity": external_identity(),
        "presentation": presentation(),
        "artifact_inputs": (
            ArtifactPort(
                port_id="input_bam",
                artifact_type="alignment.bam",
                cardinality=Cardinality.ONE,
            ),
        ),
        "value_inputs": (),
        "parameters": (ParameterSpec(parameter_id="threads", kind=ValueKind.INTEGER),),
        "secrets": (),
        "outputs": (
            OutputSpec(
                port_id="result",
                artifact_type="alignment.bam",
                collector=ExactCollector(relative_path="result.bam"),
            ),
        ),
        "environment": pixi_environment(),
        "execution_kind": ExecutionKind.ARGV,
        "execution_factory": "bionodulo.nodes.catalog.tools.samtools.sort:build_plan",
        "runtime_binding": None,
        "evidence": evidence_record(),
        "retained_evidence": None,
        "maturity": maturity_record(),
    }
    values.update(updates)
    if "runtime_binding" not in updates:
        identity = values["identity"]
        assert isinstance(identity, NodeIdentity)
        execution_kind = values["execution_kind"]
        assert isinstance(execution_kind, ExecutionKind)
        execution_factory = values["execution_factory"]
        assert isinstance(execution_factory, str)
        if identity.tool_id is not None and identity.tool_version is not None:
            values["runtime_binding"] = runtime_binding(
                tool_id=identity.tool_id,
                tool_version=identity.tool_version,
                execution_kind=execution_kind,
                execution_factory=execution_factory,
            )
    return NodeSpec(**values)


def core_spec(**updates: object) -> NodeSpec:
    values: dict[str, object] = {
        "identity": NodeIdentity(
            stable_id="legacy::String Value",
            machine_id="string_primitive",
            contract_version="2.0.0",
            implementation_version="1.0.0",
        ),
        "presentation": NodePresentation(
            display_name="String",
            description="Emit a string value.",
            palette_path=("Core", "Values"),
            domain_tags=("core",),
            operation_kind="source",
            owner=NodeOwnership.BIONODULO_CORE,
        ),
        "artifact_inputs": (),
        "value_inputs": (),
        "parameters": (
            ParameterSpec(
                parameter_id="value",
                kind=ValueKind.STRING,
                required=True,
            ),
        ),
        "secrets": (),
        "outputs": (),
        "environment": None,
        "execution_kind": ExecutionKind.PYTHON,
        "execution_factory": "bionodulo.nodes.catalog.core.values.string:build_plan",
        "runtime_binding": None,
        "evidence": None,
        "retained_evidence": None,
        "maturity": maturity_record(),
    }
    values.update(updates)
    return NodeSpec(**values)


def test_public_wire_values_are_exact() -> None:
    assert tuple(kind.value for kind in ExecutionKind) == (
        "argv",
        "pipeline",
        "script",
        "python",
        "r",
        "http",
        "container",
    )
    assert tuple(owner.value for owner in NodeOwnership) == (
        "bionodulo_core",
        "external_tool",
        "external_library",
        "external_provider",
    )
    assert tuple(scope.value for scope in PortAliasScope) == (
        "artifact_input",
        "value_input",
        "parameter",
        "secret",
        "output",
    )
    assert tuple(kind.value for kind in contract.RetainedArtifactKind) == (
        "contract",
        "environment",
        "evidence_record",
        "verification",
    )


@pytest.mark.parametrize(
    ("stable_id", "machine_id"),
    (
        ("BayeScan", "bayescan"),
        ("abyss-pe", "abyss_pe"),
        ("bedops-sort-bed", "bedops_sort_bed"),
        ("Legacy Node.Name-v1", "legacy_node_name_v1"),
    ),
)
def test_stable_identity_is_preserved_and_machine_identity_is_explicit(
    stable_id: str,
    machine_id: str,
) -> None:
    identity = external_identity(stable_id=stable_id, machine_id=machine_id)

    assert identity.stable_id == stable_id
    assert identity.machine_id == machine_id
    assert identity.node_id == stable_id
    assert identity.model_dump()["stable_id"] == stable_id


def test_unrelated_legacy_ids_are_not_merged_by_implicit_normalization() -> None:
    underscored = external_identity(
        stable_id="feature_counts",
        machine_id="feature_counts",
    )
    compact = external_identity(
        stable_id="featurecounts",
        machine_id="featurecounts",
    )

    assert underscored.stable_id != compact.stable_id
    assert underscored.machine_id != compact.machine_id


def test_stable_identity_is_not_trimmed_or_unicode_normalized() -> None:
    stable_id = " Caf\u00e9\u0301 Node "
    identity = external_identity(
        stable_id=stable_id,
        machine_id="cafe_node",
    )

    assert identity.stable_id == stable_id
    assert identity.node_id == stable_id


@pytest.mark.parametrize(
    "stable_id",
    ("", "line\nbreak", "nul\x00byte", "x" * 129),
)
def test_stable_identity_is_nonempty_printable_and_bounded(stable_id: str) -> None:
    with pytest.raises(ValidationError):
        external_identity(stable_id=stable_id)


@pytest.mark.parametrize(
    "machine_id",
    (
        "",
        "Samtools",
        "samtools-sort",
        "samtools.sort",
        "samtools sort",
        "samtools__sort",
        "_samtools",
        "samtools_",
        "1samtools",
        "sämtools",
    ),
)
def test_machine_identity_uses_segmented_lowercase_ascii(machine_id: str) -> None:
    with pytest.raises(ValidationError):
        external_identity(machine_id=machine_id)


@pytest.mark.parametrize(
    "version",
    (
        "0.0.0",
        "1.2.3",
        "1.2.3-alpha.1",
        "1.2.3+linux.amd64",
        "1.2.3-rc.1+build.7",
    ),
)
def test_contract_versions_accept_strict_semver(version: str) -> None:
    identity = external_identity(
        contract_version=version,
        implementation_version=version,
    )

    assert identity.contract_version == version
    assert identity.implementation_version == version


@pytest.mark.parametrize(
    ("field", "version"),
    (
        ("contract_version", "2"),
        ("contract_version", "2.0"),
        ("contract_version", "02.0.0"),
        ("contract_version", "1.02.0"),
        ("implementation_version", "1.0.0.0"),
        ("implementation_version", "v1.0.0"),
        ("implementation_version", "1.0.0-01"),
        ("implementation_version", "1.0.0+build!"),
        ("implementation_version", "1.0.0\n"),
        ("implementation_version", ">=1.0.0"),
    ),
)
def test_contract_versions_reject_non_semver(field: str, version: str) -> None:
    with pytest.raises(ValidationError):
        external_identity(**{field: version})


def test_upstream_tool_version_is_exact_but_not_forced_to_semver() -> None:
    identity = external_identity(tool_version="2024.04p1")

    assert identity.tool_version == "2024.04p1"
    with pytest.raises(ValidationError):
        external_identity(tool_version="latest")


@pytest.mark.parametrize(
    "updates",
    (
        {"tool_id": None},
        {"tool_version": None},
    ),
)
def test_tool_id_and_version_are_declared_together(updates: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="tool identity"):
        external_identity(**updates)


def test_identity_aliases_are_explicit_exact_and_unique() -> None:
    identity = external_identity(
        aliases=("Samtools Sort", "samtools-sort"),
    )

    assert identity.aliases == ("Samtools Sort", "samtools-sort")
    with pytest.raises(ValidationError, match="alias"):
        external_identity(aliases=("Samtools Sort", "Samtools Sort"))
    with pytest.raises(ValidationError, match="alias"):
        external_identity(aliases=("legacy::Samtools Sort v1",))


def test_node_id_is_read_only_compatibility_and_not_serialized() -> None:
    identity = external_identity()
    dumped = identity.model_dump()

    assert identity.node_id == identity.stable_id
    assert "node_id" not in dumped
    assert tuple(dumped) == (
        "stable_id",
        "machine_id",
        "contract_version",
        "implementation_version",
        "tool_id",
        "tool_version",
        "aliases",
        "port_aliases",
    )
    with pytest.raises(ValidationError):
        identity.model_copy(update={"node_id": "replacement"})
    with pytest.raises(ValidationError, match="frozen_instance"):
        identity.node_id = "replacement"


def test_presentation_is_strict_metadata_not_runtime_routing() -> None:
    presented = presentation(
        palette_path=("Different UI", "Location"),
        domain_tags=("reporting",),
        operation_kind="sink",
    )
    spec = external_spec(presentation=presented)

    assert spec.execution_factory.endswith("samtools.sort:build_plan")
    assert spec.presentation.palette_path == ("Different UI", "Location")


@pytest.mark.parametrize(
    "updates",
    (
        {"display_name": ""},
        {"display_name": " Sort"},
        {"description": "Description\nwith control"},
        {"palette_path": ()},
        {"palette_path": ("Alignment", "")},
        {"domain_tags": ()},
        {"domain_tags": ("alignment", "alignment")},
        {"operation_kind": "Transform"},
        {"owner": "external_tool"},
    ),
)
def test_presentation_fields_are_strict_and_bounded(updates: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        presentation(**updates)


@pytest.mark.parametrize(
    ("owner", "updates"),
    (
        (NodeOwnership.EXTERNAL_TOOL, {"tool_family": None}),
        (NodeOwnership.EXTERNAL_LIBRARY, {"tool_family": None}),
        (NodeOwnership.EXTERNAL_PROVIDER, {"tool_family": None, "provider": None}),
    ),
)
def test_external_ownership_requires_explicit_family_or_provider_metadata(
    owner: NodeOwnership,
    updates: dict[str, object],
) -> None:
    with pytest.raises(ValidationError, match="metadata"):
        external_spec(presentation=presentation(owner=owner, **updates))


def test_scoped_port_aliases_resolve_only_in_their_namespace() -> None:
    aliases = (
        PortAlias(
            scope=PortAliasScope.ARTIFACT_INPUT,
            old_id="bam",
            canonical_id="input_bam",
        ),
        PortAlias(
            scope=PortAliasScope.OUTPUT,
            old_id="sorted_bam",
            canonical_id="result",
        ),
    )
    spec = external_spec(
        identity=external_identity(port_aliases=aliases),
    )

    assert spec.identity.port_aliases == aliases


def test_the_same_old_port_id_is_unambiguous_in_two_explicit_scopes() -> None:
    aliases = (
        PortAlias(
            scope=PortAliasScope.ARTIFACT_INPUT,
            old_id="data",
            canonical_id="input_bam",
        ),
        PortAlias(
            scope=PortAliasScope.OUTPUT,
            old_id="data",
            canonical_id="result",
        ),
    )

    spec = external_spec(
        identity=external_identity(port_aliases=aliases),
    )

    assert spec.identity.port_aliases == aliases


@pytest.mark.parametrize(
    "port_aliases",
    (
        (
            PortAlias(
                scope=PortAliasScope.ARTIFACT_INPUT,
                old_id="bam",
                canonical_id="input_bam",
            ),
            PortAlias(
                scope=PortAliasScope.ARTIFACT_INPUT,
                old_id="bam",
                canonical_id="input_bam",
            ),
        ),
        (
            PortAlias(
                scope=PortAliasScope.ARTIFACT_INPUT,
                old_id="bam",
                canonical_id="input_bam",
            ),
            PortAlias(
                scope=PortAliasScope.ARTIFACT_INPUT,
                old_id="bam",
                canonical_id="other",
            ),
        ),
    ),
)
def test_port_aliases_reject_duplicate_or_ambiguous_mappings(
    port_aliases: tuple[PortAlias, ...],
) -> None:
    with pytest.raises(ValidationError, match="alias"):
        external_identity(port_aliases=port_aliases)


def test_port_alias_rejects_a_self_mapping() -> None:
    with pytest.raises(ValidationError, match="itself"):
        PortAlias(
            scope=PortAliasScope.ARTIFACT_INPUT,
            old_id="input_bam",
            canonical_id="input_bam",
        )


@pytest.mark.parametrize(
    "alias",
    (
        PortAlias(
            scope=PortAliasScope.ARTIFACT_INPUT,
            old_id="bam",
            canonical_id="missing",
        ),
        PortAlias(
            scope=PortAliasScope.OUTPUT,
            old_id="sorted_bam",
            canonical_id="input_bam",
        ),
        PortAlias(
            scope=PortAliasScope.VALUE_INPUT,
            old_id="value",
            canonical_id="input_bam",
        ),
        PortAlias(
            scope=PortAliasScope.ARTIFACT_INPUT,
            old_id="input_bam",
            canonical_id="result",
        ),
    ),
)
def test_port_alias_targets_are_not_guessed_across_namespaces(alias: PortAlias) -> None:
    with pytest.raises(ValidationError, match="alias"):
        external_spec(
            identity=external_identity(port_aliases=(alias,)),
        )


def test_port_alias_old_id_cannot_shadow_a_canonical_id_in_its_scope() -> None:
    inputs = (
        ArtifactPort(
            port_id="input_bam",
            artifact_type="alignment.bam",
            cardinality=Cardinality.ONE,
        ),
        ArtifactPort(
            port_id="other_bam",
            artifact_type="alignment.bam",
            cardinality=Cardinality.ONE,
        ),
    )
    alias = PortAlias(
        scope=PortAliasScope.ARTIFACT_INPUT,
        old_id="input_bam",
        canonical_id="other_bam",
    )

    with pytest.raises(ValidationError, match="collides"):
        external_spec(
            artifact_inputs=inputs,
            identity=external_identity(port_aliases=(alias,)),
        )


def input_declaration(namespace: str, contract_id: str, index: int) -> object:
    if namespace == "artifact_inputs":
        return ArtifactPort(
            port_id=contract_id,
            artifact_type="alignment.bam",
            cardinality=Cardinality.ONE,
        )
    if namespace == "value_inputs":
        return ValuePort(port_id=contract_id, kind=ValueKind.STRING)
    if namespace == "parameters":
        return ParameterSpec(parameter_id=contract_id, kind=ValueKind.STRING)
    if namespace == "secrets":
        return SecretSpec(
            secret_id=contract_id,
            environment_variable=f"TOKEN_{index}",
            required=True,
        )
    raise AssertionError(namespace)


@pytest.mark.parametrize(
    ("left", "right"),
    (
        ("artifact_inputs", "artifact_inputs"),
        ("artifact_inputs", "value_inputs"),
        ("artifact_inputs", "parameters"),
        ("artifact_inputs", "secrets"),
        ("value_inputs", "value_inputs"),
        ("value_inputs", "parameters"),
        ("value_inputs", "secrets"),
        ("parameters", "parameters"),
        ("parameters", "secrets"),
        ("secrets", "secrets"),
    ),
)
def test_duplicate_ids_across_every_input_kind_are_rejected(
    left: str,
    right: str,
) -> None:
    updates: dict[str, tuple[object, ...]] = {
        "artifact_inputs": (),
        "value_inputs": (),
        "parameters": (),
        "secrets": (),
    }
    updates[left] += (input_declaration(left, "shared", 1),)
    updates[right] += (input_declaration(right, "shared", 2),)

    with pytest.raises(ValidationError, match="duplicate input ID"):
        external_spec(**updates)


def test_output_namespace_is_unique_but_separate_from_inputs() -> None:
    matching_output = OutputSpec(
        port_id="input_bam",
        artifact_type="alignment.bam",
        collector=ExactCollector(relative_path="result.bam"),
    )
    spec = external_spec(outputs=(matching_output,))

    assert spec.artifact_inputs[0].port_id == spec.outputs[0].port_id
    with pytest.raises(ValidationError, match="duplicate output ID"):
        external_spec(outputs=(matching_output, matching_output))


def test_secret_environment_variable_bindings_are_unique() -> None:
    with pytest.raises(ValidationError, match="environment variable"):
        external_spec(
            secrets=(
                SecretSpec(
                    secret_id="first_token",
                    environment_variable="API_TOKEN",
                    required=True,
                ),
                SecretSpec(
                    secret_id="second_token",
                    environment_variable="API_TOKEN",
                    required=True,
                ),
            )
        )


def conditional_output(condition_key: str, expected_value: object = True) -> OutputSpec:
    return OutputSpec(
        port_id="index",
        artifact_type="alignment.bai",
        cardinality=Cardinality.OPTIONAL_ONE,
        collector=ConditionalCollector(
            condition_key=condition_key,
            expected_value=expected_value,
            collector=ExactCollector(relative_path="result.bai"),
        ),
    )


def test_conditional_output_references_an_existing_parameter_only() -> None:
    spec = external_spec(
        parameters=(
            ParameterSpec(
                parameter_id="write_index",
                kind=ValueKind.BOOLEAN,
            ),
        ),
        outputs=(conditional_output("write_index"),),
    )

    assert spec.outputs[0].collector.condition_key == "write_index"
    with pytest.raises(ValidationError, match="conditional output"):
        external_spec(outputs=(conditional_output("missing"),))
    with pytest.raises(ValidationError, match="conditional output"):
        external_spec(
            value_inputs=(ValuePort(port_id="write_index", kind=ValueKind.BOOLEAN),),
            outputs=(conditional_output("write_index"),),
        )


@pytest.mark.parametrize(
    ("parameter", "expected_value"),
    (
        (ParameterSpec(parameter_id="condition", kind=ValueKind.BOOLEAN), "true"),
        (ParameterSpec(parameter_id="condition", kind=ValueKind.INTEGER), 1.0),
        (ParameterSpec(parameter_id="condition", kind=ValueKind.NUMBER), True),
        (ParameterSpec(parameter_id="condition", kind=ValueKind.INTEGER, minimum=2), 1),
        (ParameterSpec(parameter_id="condition", kind=ValueKind.INTEGER, maximum=2), 3),
        (ParameterSpec(parameter_id="condition", kind=ValueKind.STRING, min_length=2), "x"),
        (ParameterSpec(parameter_id="condition", kind=ValueKind.STRING, max_length=2), "xxx"),
        (ParameterSpec(parameter_id="condition", kind=ValueKind.STRING, pattern=r"^yes$"), "no"),
        (
            ParameterSpec(
                parameter_id="condition",
                kind=ValueKind.STRING,
                choices=("yes", "no"),
            ),
            "maybe",
        ),
    ),
)
def test_conditional_output_expected_value_must_be_reachable_by_its_parameter(
    parameter: ParameterSpec,
    expected_value: object,
) -> None:
    with pytest.raises(ValidationError, match="conditional output"):
        external_spec(
            parameters=(parameter,),
            outputs=(conditional_output(parameter.parameter_id, expected_value),),
        )


@pytest.mark.parametrize(
    ("parameter", "expected_value"),
    (
        (ParameterSpec(parameter_id="condition", kind=ValueKind.BOOLEAN), True),
        (ParameterSpec(parameter_id="condition", kind=ValueKind.INTEGER, minimum=2), 2),
        (ParameterSpec(parameter_id="condition", kind=ValueKind.NUMBER, maximum=2.5), 2.5),
        (
            ParameterSpec(
                parameter_id="condition",
                kind=ValueKind.STRING,
                choices=("no", "yes"),
                min_length=2,
                max_length=3,
                pattern=r"^[a-z]+$",
            ),
            "yes",
        ),
    ),
)
def test_conditional_output_accepts_an_exact_reachable_parameter_value(
    parameter: ParameterSpec,
    expected_value: object,
) -> None:
    spec = external_spec(
        parameters=(parameter,),
        outputs=(conditional_output(parameter.parameter_id, expected_value),),
    )

    assert spec.outputs[0].collector.expected_value == expected_value


@pytest.mark.parametrize(
    "kind",
    (ValueKind.STRING, ValueKind.INTEGER, ValueKind.NUMBER, ValueKind.BOOLEAN),
)
def test_conditional_output_accepts_none_as_absence_for_optional_non_json_without_default(
    kind: ValueKind,
) -> None:
    parameter = ParameterSpec(parameter_id="condition", kind=kind)

    spec = external_spec(
        parameters=(parameter,),
        outputs=(conditional_output(parameter.parameter_id, None),),
    )

    assert spec.outputs[0].collector.expected_value is None


@pytest.mark.parametrize(
    "kind",
    (ValueKind.STRING, ValueKind.INTEGER, ValueKind.NUMBER, ValueKind.BOOLEAN),
)
def test_conditional_output_rejects_none_for_required_non_json(kind: ValueKind) -> None:
    parameter = ParameterSpec(parameter_id="condition", kind=kind, required=True)

    with pytest.raises(ValidationError, match="conditional output"):
        external_spec(
            parameters=(parameter,),
            outputs=(conditional_output(parameter.parameter_id, None),),
        )


@pytest.mark.parametrize(
    ("kind", "default"),
    (
        (ValueKind.STRING, "value"),
        (ValueKind.INTEGER, 1),
        (ValueKind.NUMBER, 1.5),
        (ValueKind.BOOLEAN, True),
    ),
)
def test_conditional_output_rejects_none_when_optional_non_json_has_concrete_default(
    kind: ValueKind,
    default: object,
) -> None:
    parameter = ParameterSpec(
        parameter_id="condition",
        kind=kind,
        has_default=True,
        default=default,
    )

    with pytest.raises(ValidationError, match="conditional output"):
        external_spec(
            parameters=(parameter,),
            outputs=(conditional_output(parameter.parameter_id, None),),
        )


def test_conditional_output_accepts_required_json_null_when_allowed_by_choices() -> None:
    parameter = ParameterSpec(
        parameter_id="condition",
        kind=ValueKind.JSON,
        required=True,
        choices=(None, {"state": "set"}),
    )

    spec = external_spec(
        parameters=(parameter,),
        outputs=(conditional_output(parameter.parameter_id, None),),
    )

    assert spec.outputs[0].collector.expected_value is None


def test_conditional_output_required_json_null_still_obeys_choices() -> None:
    parameter = ParameterSpec(
        parameter_id="condition",
        kind=ValueKind.JSON,
        required=True,
        choices=({"state": "set"},),
    )

    with pytest.raises(ValidationError, match="conditional output"):
        external_spec(
            parameters=(parameter,),
            outputs=(conditional_output(parameter.parameter_id, None),),
        )


def test_conditional_output_rejects_ambiguous_optional_json_null() -> None:
    parameter = ParameterSpec(parameter_id="condition", kind=ValueKind.JSON)

    with pytest.raises(ValidationError, match="ambiguous"):
        external_spec(
            parameters=(parameter,),
            outputs=(conditional_output(parameter.parameter_id, None),),
        )


@pytest.mark.parametrize(
    "path",
    (
        "bionodulo.nodes.catalog.tools.samtools.sort.build_plan",
        "bionodulo.nodes.catalog.tools.samtools.sort:",
        ":build_plan",
        "relative:build_plan",
        ".relative.module:build_plan",
        "bionodulo.nodes.catalog..sort:build_plan",
        "bionodulo.nodes.catalog.sort:build-plan",
        "bionodulo.nodes.catalog.sort:build_plan()",
        "bionodulo.nodes.catalog.sort:__build_plan__",
        "bionodulo.nodes.catalog.sort:build_plan\n",
    ),
)
def test_execution_factory_is_a_strict_import_reference(path: str) -> None:
    with pytest.raises(ValidationError):
        external_spec(execution_factory=path)


@pytest.mark.parametrize(
    ("kind", "environment"),
    (
        (ExecutionKind.ARGV, pixi_environment()),
        (ExecutionKind.PIPELINE, pixi_environment()),
        (ExecutionKind.SCRIPT, python_environment()),
        (ExecutionKind.PYTHON, python_environment()),
        (ExecutionKind.R, r_environment()),
        (ExecutionKind.HTTP, python_environment()),
        (ExecutionKind.CONTAINER, container_environment()),
    ),
)
def test_execution_kind_accepts_only_compatible_locked_environments(
    kind: ExecutionKind,
    environment: object,
) -> None:
    spec = external_spec(
        execution_kind=kind,
        environment=environment,
    )

    assert spec.execution_kind is kind
    assert spec.environment == environment


@pytest.mark.parametrize(
    ("kind", "environment", "message"),
    (
        (ExecutionKind.ARGV, container_environment(), "process"),
        (ExecutionKind.PIPELINE, container_environment(), "process"),
        (ExecutionKind.SCRIPT, container_environment(), "process"),
        (ExecutionKind.PYTHON, pixi_environment(), "Python"),
        (ExecutionKind.R, pixi_environment(), "R environment"),
        (ExecutionKind.HTTP, pixi_environment(), "HTTP"),
        (ExecutionKind.CONTAINER, pixi_environment(), "container environment"),
    ),
)
def test_execution_kind_rejects_incompatible_environment_types(
    kind: ExecutionKind,
    environment: object,
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        external_spec(
            execution_kind=kind,
            environment=environment,
        )


@pytest.mark.parametrize(
    ("kind", "environment"),
    (
        (ExecutionKind.ARGV, pixi_environment(locked=False)),
        (ExecutionKind.PYTHON, python_environment(locked=False)),
        (ExecutionKind.R, r_environment(locked=False)),
        (ExecutionKind.HTTP, python_environment(locked=False)),
        (ExecutionKind.CONTAINER, container_environment(locked=False)),
    ),
)
def test_declared_environments_must_be_fully_locked(
    kind: ExecutionKind,
    environment: object,
) -> None:
    with pytest.raises(ValidationError, match="locked"):
        external_spec(
            execution_kind=kind,
            environment=environment,
        )


def test_only_owned_in_process_core_python_may_omit_tool_runtime_and_evidence() -> None:
    spec = core_spec()

    assert spec.presentation.owner is NodeOwnership.BIONODULO_CORE
    assert spec.execution_kind is ExecutionKind.PYTHON
    assert spec.identity.tool_id is None
    assert spec.identity.tool_version is None
    assert spec.environment is None
    assert spec.evidence is None

    with pytest.raises(ValidationError, match="core Python"):
        core_spec(execution_kind=ExecutionKind.ARGV)
    with pytest.raises(ValidationError, match="environment"):
        external_spec(environment=None)
    with pytest.raises(ValidationError, match="evidence"):
        external_spec(evidence=None)


def test_core_python_exemption_requires_the_canonical_core_factory_namespace() -> None:
    with pytest.raises(ValidationError, match="core Python"):
        core_spec(execution_factory="thirdparty.plugin:build_plan")


def test_external_runtime_binding_resolves_the_declared_tool_in_the_environment() -> None:
    spec = external_spec(runtime_binding=runtime_binding())

    assert spec.runtime_binding.tool_id == "samtools"
    assert spec.runtime_binding.package_name == "samtools"

    with pytest.raises(ValidationError, match="runtime binding"):
        external_spec(
            identity=external_identity(tool_id="bcftools"),
            evidence=evidence_record(tool_id="bcftools"),
            execution_kind=ExecutionKind.PYTHON,
            environment=python_environment(),
            runtime_binding=runtime_binding(
                tool_id="bcftools",
                execution_kind=ExecutionKind.PYTHON,
                probe_id="samtools-import",
            ),
        )


def test_runtime_binding_accepts_actual_executable_import_r_and_container_references() -> None:
    executable_environment = pixi_environment().model_copy(
        update={
            "executable_probes": (
                ExecutableProbe(
                    probe_id="samtools-executable",
                    locator="bin/samtools",
                    version_arguments=("--version",),
                    version_line_prefix="samtools ",
                    expected_version="1.20",
                ),
            ),
        }
    )
    executable = external_spec(
        environment=executable_environment,
        runtime_binding=runtime_binding(
            package_name=None,
            probe_id="samtools-executable",
        ),
    )
    imported = external_spec(
        execution_kind=ExecutionKind.PYTHON,
        environment=python_environment(),
        runtime_binding=runtime_binding(execution_kind=ExecutionKind.PYTHON),
    )
    r_package = external_spec(
        execution_kind=ExecutionKind.R,
        environment=r_environment(),
        runtime_binding=runtime_binding(execution_kind=ExecutionKind.R),
    )
    container = external_spec(
        execution_kind=ExecutionKind.CONTAINER,
        environment=container_environment(),
        runtime_binding=runtime_binding(execution_kind=ExecutionKind.CONTAINER),
    )

    assert executable.runtime_binding.probe_id == "samtools-executable"
    assert imported.runtime_binding.probe_id == "samtools-import"
    assert r_package.runtime_binding.probe_id == "samtools-r-package"
    assert container.runtime_binding.container_image == CONTAINER_IMAGE


def test_runtime_binding_can_use_an_exact_locked_package_for_python_execution() -> None:
    spec = external_spec(
        execution_kind=ExecutionKind.PYTHON,
        environment=python_environment(),
        runtime_binding=runtime_binding(
            execution_kind=ExecutionKind.PYTHON,
            package_name="samtools",
            probe_id=None,
        ),
    )

    assert spec.runtime_binding.package_name == "samtools"


def test_runtime_binding_requires_one_reference_and_matches_factory_and_execution_kind() -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        runtime_binding(package_name=None)
    with pytest.raises(ValidationError, match="exactly one"):
        runtime_binding(probe_id="samtools-executable")
    with pytest.raises(ValidationError, match="execution kind"):
        external_spec(
            runtime_binding=runtime_binding(execution_kind=ExecutionKind.PIPELINE),
        )
    with pytest.raises(ValidationError, match="execution factory"):
        external_spec(
            runtime_binding=runtime_binding(
                execution_factory="bionodulo.nodes.catalog.tools.samtools.index:build_plan"
            ),
        )


def test_only_canonical_core_python_may_omit_runtime_binding() -> None:
    assert core_spec().runtime_binding is None
    with pytest.raises(ValidationError, match="runtime binding"):
        external_spec(runtime_binding=None)


def retained_spec_with_assessments(
    reports: tuple[VerificationEvidence, ...],
    assessments: tuple[GateAssessment, ...],
    *,
    access_classes: tuple[AccessClass, ...] = (AccessClass.PUBLIC,),
) -> NodeSpec:
    identity = external_identity()
    environment = pixi_environment()
    retained_evidence = evidence_record(verifications=reports)
    inventory = retained_inventory(
        identity=identity,
        environment=environment,
        evidence=retained_evidence,
    )
    return external_spec(
        identity=identity,
        environment=environment,
        evidence=retained_evidence,
        retained_evidence=inventory,
        maturity=maturity_record(
            access_classes=access_classes,
            assessments=assessments,
        ),
    )


def test_gate_assessment_digests_must_resolve_to_retained_artifacts() -> None:
    maturity = maturity_record(
        assessments=tuple(gate_assessment(gate, SHA_A) for gate in Gate),
    )

    assert maturity.released is True
    with pytest.raises(ValidationError, match="retained evidence"):
        core_spec(maturity=maturity)


def test_passing_evidence_gate_requires_a_bound_evidence_record() -> None:
    maturity = maturity_record(
        assessments=(
            gate_assessment(Gate.INVENTORIED, SHA_A),
            gate_assessment(Gate.EVIDENCE_VERIFIED, SHA_A),
        ),
    )

    with pytest.raises(ValidationError, match="evidence record"):
        core_spec(maturity=maturity)


def test_release_resolves_evidence_verification_environment_and_contract_artifacts() -> None:
    environment = pixi_environment()
    reports = tuple(verification_for_gate(gate, environment) for gate in Gate)
    assessments = tuple(
        gate_assessment(gate, report.verification_digest()) for gate, report in zip(Gate, reports, strict=True)
    )

    spec = retained_spec_with_assessments(reports, assessments)

    assert spec.maturity is not None
    assert spec.maturity.released is True


def test_gate_assessment_resolves_only_evidence_verification_digests() -> None:
    environment = pixi_environment()
    report = verification_for_gate(Gate.INVENTORIED, environment)
    identity = external_identity()
    retained_evidence = evidence_record(verifications=(report,))
    inventory = retained_inventory(
        identity=identity,
        environment=environment,
        evidence=retained_evidence,
    )
    contract_digest = next(
        artifact.sha256 for artifact in inventory.artifacts if artifact.kind is contract.RetainedArtifactKind.CONTRACT
    )

    expected_message = (
        f"maturity gate {Gate.INVENTORIED.value} verification {contract_digest} resolution mismatch: "
        "expected retained verification evidence, actual unresolved digest"
    )
    with pytest.raises(ValidationError) as error:
        external_spec(
            identity=identity,
            environment=environment,
            evidence=retained_evidence,
            retained_evidence=inventory,
            maturity=maturity_record(
                assessments=(gate_assessment(Gate.INVENTORIED, contract_digest),),
            ),
        )
    assert expected_message in str(error.value)


def test_tool_smoke_report_cannot_be_replayed_for_an_unrelated_gate() -> None:
    environment = pixi_environment()
    smoke = verification_for_gate(Gate.TOOL_SMOKE_VERIFIED, environment)

    digest = smoke.verification_digest()
    expected_message = (
        f"maturity gate {Gate.INVENTORIED.value} verification {digest} kind mismatch: "
        f"expected {VerificationKind.INVENTORY.value}, actual {VerificationKind.TOOL_SMOKE.value}"
    )
    with pytest.raises(ValidationError) as error:
        retained_spec_with_assessments(
            (smoke,),
            (gate_assessment(Gate.INVENTORIED, digest),),
        )
    assert expected_message in str(error.value)


def test_gate_assessment_requires_matching_verification_outcome() -> None:
    environment = pixi_environment()
    failed = verification_for_gate(
        Gate.INVENTORIED,
        environment,
        outcome=VerificationOutcome.FAILED,
    )

    digest = failed.verification_digest()
    expected_message = (
        f"maturity gate {Gate.INVENTORIED.value} verification {digest} outcome mismatch: "
        f"expected {VerificationOutcome.PASSED.value}, actual {VerificationOutcome.FAILED.value}"
    )
    with pytest.raises(ValidationError) as error:
        retained_spec_with_assessments(
            (failed,),
            (gate_assessment(Gate.INVENTORIED, digest),),
        )
    assert expected_message in str(error.value)


def test_gate_assessment_requires_exact_matching_failure_code() -> None:
    environment = pixi_environment()
    inventoried = verification_for_gate(Gate.INVENTORIED, environment)
    failed_coverage = verification_for_gate(
        Gate.EVIDENCE_VERIFIED,
        environment,
        outcome=VerificationOutcome.FAILED,
        failure_code=FailureCode.EVIDENCE_CONFLICT,
    )
    assessments = (
        gate_assessment(Gate.INVENTORIED, inventoried.verification_digest()),
        gate_assessment(
            Gate.EVIDENCE_VERIFIED,
            failed_coverage.verification_digest(),
            result=GateResult.FAILED,
            failure_code=FailureCode.EVIDENCE_MISSING,
        ),
    )

    digest = failed_coverage.verification_digest()
    expected_message = (
        f"maturity gate {Gate.EVIDENCE_VERIFIED.value} verification {digest} failure code mismatch: "
        f"expected {FailureCode.EVIDENCE_MISSING.value}, actual {FailureCode.EVIDENCE_CONFLICT.value}"
    )
    with pytest.raises(ValidationError) as error:
        retained_spec_with_assessments((inventoried, failed_coverage), assessments)
    assert expected_message in str(error.value)


@pytest.mark.parametrize(
    ("assessment_updates", "field", "expected", "actual"),
    (
        ({"verifier_id": "other-verifier"}, "verifier ID", "other-verifier", "catalog-verifier"),
        ({"verifier_version": "2.0.0"}, "verifier version", "2.0.0", "1.0.0"),
    ),
)
def test_gate_assessment_requires_matching_verifier_identity(
    assessment_updates: dict[str, str],
    field: str,
    expected: str,
    actual: str,
) -> None:
    environment = pixi_environment()
    report = verification_for_gate(Gate.INVENTORIED, environment)
    digest = report.verification_digest()
    expected_message = (
        f"maturity gate {Gate.INVENTORIED.value} verification {digest} {field} mismatch: "
        f"expected {expected}, actual {actual}"
    )

    with pytest.raises(ValidationError) as error:
        retained_spec_with_assessments(
            (report,),
            (
                gate_assessment(
                    Gate.INVENTORIED,
                    digest,
                    **assessment_updates,
                ),
            ),
        )
    assert expected_message in str(error.value)


def test_gate_assessment_tool_identity_mismatch_names_gate_digest_and_values() -> None:
    environment = pixi_environment()
    report = verification_for_gate(Gate.INVENTORIED, environment)
    mismatched_report = report.model_copy(
        update={"tool_id": "bcftools", "tool_version": "1.21"},
    )
    valid_evidence = evidence_record(verifications=(report,))
    retained_evidence = EvidenceRecord.model_construct(
        **(valid_evidence.__dict__ | {"verifications": (mismatched_report,)}),
    )
    identity = external_identity()
    valid_spec = external_spec(
        identity=identity,
        environment=environment,
        evidence=valid_evidence,
        maturity=None,
    )
    inventory = retained_inventory(
        identity=identity,
        environment=environment,
        evidence=retained_evidence,
        contract_digest=valid_spec.contract_digest(),
    )
    digest = mismatched_report.verification_digest()
    expected_message = (
        f"maturity gate {Gate.INVENTORIED.value} verification {digest} tool identity mismatch: "
        "expected samtools@1.20, actual bcftools@1.21"
    )

    # Reach the defense-in-depth check through the model's documented trusted
    # construction escape hatch; normal EvidenceRecord validation rejects this
    # mismatch earlier.
    constructed = NodeSpec.model_construct(
        **(
            valid_spec.__dict__
            | {
                "evidence": retained_evidence,
                "retained_evidence": inventory,
                "maturity": maturity_record(
                    assessments=(gate_assessment(Gate.INVENTORIED, digest),),
                ),
            }
        ),
    )
    with pytest.raises(ValueError) as error:
        constructed._validate_retained_evidence()
    assert expected_message in str(error.value)


def test_multiple_same_kind_reports_all_must_agree_with_the_gate() -> None:
    environment = pixi_environment()
    first = verification_for_gate(
        Gate.INVENTORIED,
        environment,
        evidence_id="inventory-a",
        test_id="inventory-a-v1",
    )
    second = verification_for_gate(
        Gate.INVENTORIED,
        environment,
        evidence_id="inventory-b",
        test_id="inventory-b-v1",
    )
    assessment = gate_assessment(
        Gate.INVENTORIED,
        first.verification_digest(),
        second.verification_digest(),
    )

    assert retained_spec_with_assessments((first, second), (assessment,)).maturity is not None

    failed_second = second.model_copy(
        update={
            "outcome": VerificationOutcome.FAILED,
            "failure_code": FailureCode.INVENTORY_MISSING,
        }
    )
    with pytest.raises(ValidationError, match="outcome"):
        retained_spec_with_assessments(
            (first, failed_second),
            (
                gate_assessment(
                    Gate.INVENTORIED,
                    first.verification_digest(),
                    failed_second.verification_digest(),
                ),
            ),
        )


def test_verification_without_environment_context_does_not_require_an_environment_digest() -> None:
    environment = pixi_environment()
    report = verification_for_gate(Gate.INVENTORIED, environment)

    assert report.environment_sha256 is None
    assert retained_spec_with_assessments(
        (report,),
        (gate_assessment(Gate.INVENTORIED, report.verification_digest()),),
    )


def test_retained_inventory_is_canonical_and_bound_to_actual_node_artifacts() -> None:
    environment = pixi_environment()
    evidence = evidence_record(verifications=(verification_evidence(environment),))
    identity = external_identity()
    inventory = retained_inventory(identity=identity, environment=environment, evidence=evidence)

    with pytest.raises(ValidationError, match="canonical"):
        contract.RetainedEvidenceInventory(artifacts=tuple(reversed(inventory.artifacts)))
    with pytest.raises(ValidationError, match="evidence record"):
        external_spec(
            identity=identity,
            environment=environment,
            evidence=evidence,
            retained_evidence=inventory.model_copy(
                update={
                    "artifacts": tuple(
                        artifact.model_copy(update={"sha256": SHA_A})
                        if artifact.kind is contract.RetainedArtifactKind.EVIDENCE_RECORD
                        else artifact
                        for artifact in inventory.artifacts
                    )
                }
            ),
        )


def test_assessment_rejects_an_uninventoried_digest_even_when_the_inventory_is_valid() -> None:
    environment = pixi_environment()
    evidence = evidence_record()
    identity = external_identity()
    inventory = retained_inventory(identity=identity, environment=environment, evidence=evidence)

    with pytest.raises(ValidationError, match="verification"):
        external_spec(
            identity=identity,
            environment=environment,
            evidence=evidence,
            retained_evidence=inventory,
            maturity=maturity_record(
                assessments=(gate_assessment(Gate.INVENTORIED, SHA_A),),
            ),
        )


def test_retained_contract_artifact_digest_is_derived_from_authoritative_node_state() -> None:
    environment = pixi_environment()
    evidence = evidence_record()
    identity = external_identity()
    arbitrary_inventory = retained_inventory(
        identity=identity,
        environment=environment,
        evidence=evidence,
        contract_digest=SHA_D,
    )

    with pytest.raises(ValidationError, match="contract artifact"):
        external_spec(
            identity=identity,
            environment=environment,
            evidence=evidence,
            retained_evidence=arbitrary_inventory,
            maturity=None,
        )

    base = external_spec(
        identity=identity,
        environment=environment,
        evidence=evidence,
        maturity=None,
    )
    rebuilt = NodeSpec.model_validate_json(base.model_dump_json())
    valid_inventory = retained_inventory(
        identity=identity,
        environment=environment,
        evidence=evidence,
    )
    retained = external_spec(
        identity=identity,
        environment=environment,
        evidence=evidence,
        retained_evidence=valid_inventory,
        maturity=None,
    )

    assert retained.contract_digest() == base.contract_digest()
    assert rebuilt.contract_digest() == base.contract_digest()
    assert retained.contract_digest() != core_spec(maturity=None).contract_digest()


def projection_spec(*, reverse: bool = False, **updates: object) -> NodeSpec:
    collections: dict[str, tuple[object, ...]] = {
        "artifact_inputs": (
            ArtifactPort(
                port_id="a_artifact",
                artifact_type="alignment.bam",
                cardinality=Cardinality.ONE,
            ),
            ArtifactPort(
                port_id="z_artifact",
                artifact_type="sequence.fastq",
                cardinality=Cardinality.MANY,
            ),
        ),
        "value_inputs": (
            ValuePort(port_id="a_value", kind=ValueKind.STRING, description="First value."),
            ValuePort(port_id="z_value", kind=ValueKind.INTEGER, description="Last value."),
        ),
        "parameters": (
            ParameterSpec(parameter_id="a_parameter", kind=ValueKind.BOOLEAN, description="First parameter."),
            ParameterSpec(parameter_id="z_parameter", kind=ValueKind.STRING, description="Last parameter."),
        ),
        "secrets": (
            SecretSpec(
                secret_id="a_secret",
                environment_variable="A_SECRET",
                required=False,
                description="First secret.",
            ),
            SecretSpec(
                secret_id="z_secret",
                environment_variable="Z_SECRET",
                required=False,
                description="Last secret.",
            ),
        ),
        "outputs": (
            OutputSpec(
                port_id="a_output",
                artifact_type="alignment.bam",
                collector=ExactCollector(relative_path="a.bam"),
            ),
            OutputSpec(
                port_id="z_output",
                artifact_type="sequence.fastq",
                collector=ExactCollector(relative_path="z.fastq"),
            ),
        ),
    }
    if reverse:
        collections = {name: tuple(reversed(items)) for name, items in collections.items()}
    collections.update(updates)
    return external_spec(
        **collections,
        maturity=maturity_record(access_classes=(AccessClass.PUBLIC_RATE_LIMITED,)),
    )


def test_contract_projection_has_exact_evidence_free_top_level_shape() -> None:
    projection = projection_spec().contract_projection()

    assert tuple(projection) == (
        "identity",
        "presentation",
        "artifact_inputs",
        "value_inputs",
        "parameters",
        "secrets",
        "outputs",
        "environment",
        "execution_kind",
        "execution_factory",
        "runtime_binding",
    )
    assert not {"evidence", "retained_evidence", "maturity"} & projection.keys()


def test_contract_projection_uses_sorted_id_keyed_complete_collections() -> None:
    spec = projection_spec(reverse=True)
    projection = spec.contract_projection()
    collections = (
        ("artifact_inputs", spec.artifact_inputs, "port_id"),
        ("value_inputs", spec.value_inputs, "port_id"),
        ("parameters", spec.parameters, "parameter_id"),
        ("secrets", spec.secrets, "secret_id"),
        ("outputs", spec.outputs, "port_id"),
    )

    for field, items, id_field in collections:
        projected = projection[field]
        assert isinstance(projected, dict)
        expected_ids = tuple(sorted(getattr(item, id_field) for item in items))
        assert tuple(projected) == expected_ids
        for item in items:
            item_id = getattr(item, id_field)
            assert projected[item_id] == item.model_dump(mode="json", round_trip=True)


def test_contract_projection_keeps_stable_output_id_pointer_shape() -> None:
    index = OutputSpec(
        port_id="index",
        artifact_type="alignment.bai",
        cardinality=Cardinality.OPTIONAL_ONE,
        collector=ExactCollector(relative_path="result.bai"),
    )

    projection = external_spec(outputs=(index,)).contract_projection()

    assert projection["outputs"]["index"]["collector"] == {
        "kind": "exact",
        "relative_path": "result.bai",
    }


def test_contract_projection_and_digest_ignore_collection_insertion_order() -> None:
    first = projection_spec()
    second = projection_spec(reverse=True)
    first_projection = first.contract_projection()
    second_projection = second.contract_projection()

    assert first_projection == second_projection
    assert first.contract_digest() == second.contract_digest()


def test_contract_digest_matches_independent_hard_coded_golden_value() -> None:
    assert projection_spec().contract_digest() == PROJECTION_GOLDEN_CONTRACT_DIGEST


@pytest.mark.parametrize(
    ("field", "changed_item"),
    (
        (
            "artifact_inputs",
            ArtifactPort(
                port_id="a_artifact",
                artifact_type="alignment.cram",
                cardinality=Cardinality.ONE,
            ),
        ),
        (
            "value_inputs",
            ValuePort(port_id="a_value", kind=ValueKind.STRING, description="Changed value."),
        ),
        (
            "parameters",
            ParameterSpec(parameter_id="a_parameter", kind=ValueKind.BOOLEAN, description="Changed parameter."),
        ),
        (
            "secrets",
            SecretSpec(
                secret_id="a_secret",
                environment_variable="A_SECRET",
                required=False,
                description="Changed secret.",
            ),
        ),
        (
            "outputs",
            OutputSpec(
                port_id="a_output",
                artifact_type="alignment.bam",
                collector=ExactCollector(relative_path="a.bam"),
                require_nonempty=True,
            ),
        ),
    ),
)
def test_contract_digest_changes_when_any_complete_collection_item_field_changes(
    field: str,
    changed_item: object,
) -> None:
    base = projection_spec()
    items = getattr(base, field)
    changed = tuple(changed_item if item == items[0] else item for item in items)

    assert projection_spec(**{field: changed}).contract_digest() != base.contract_digest()


@pytest.mark.parametrize(
    "field",
    (
        "identity",
        "presentation",
        "environment",
        "execution_kind",
        "execution_factory",
        "runtime_binding",
    ),
)
def test_contract_digest_changes_when_any_non_collection_contract_field_changes(field: str) -> None:
    base = projection_spec()
    assert base.environment is not None
    assert base.runtime_binding is not None
    mutations: dict[str, object] = {
        "identity": base.identity.model_copy(update={"implementation_version": "1.0.1"}),
        "presentation": base.presentation.model_copy(update={"description": "Sort alignments reproducibly."}),
        "environment": base.environment.model_copy(update={"environment_id": "samtools-runtime-v2"}),
        "execution_kind": ExecutionKind.PIPELINE,
        "execution_factory": "bionodulo.nodes.catalog.tools.samtools.index:build_plan",
        "runtime_binding": base.runtime_binding.model_copy(
            update={"execution_factory": "bionodulo.nodes.catalog.tools.samtools.index:build_plan"},
        ),
    }
    # Isolate one digest input even where normal NodeSpec validation requires
    # coupled execution and runtime-binding changes.
    changed = NodeSpec.model_construct(**(base.__dict__ | {field: mutations[field]}))

    assert changed.contract_projection()[field] != base.contract_projection()[field]
    assert changed.contract_digest() != base.contract_digest()


def test_retained_verification_environment_digest_matches_the_declared_environment() -> None:
    environment = pixi_environment()
    verification = verification_evidence(environment).model_copy(update={"environment_sha256": SHA_A})
    evidence = evidence_record(verifications=(verification,))
    identity = external_identity()
    inventory = retained_inventory(
        identity=identity,
        environment=environment,
        evidence=evidence,
    )

    with pytest.raises(ValidationError, match="verification environment"):
        external_spec(
            identity=identity,
            environment=environment,
            evidence=evidence,
            retained_evidence=inventory,
            maturity=None,
        )


def test_any_secret_requires_explicit_secret_capable_maturity() -> None:
    required = SecretSpec(secret_id="api_token", environment_variable="API_TOKEN", required=True)
    optional = required.model_copy(update={"required": False})

    for secret in (optional, required):
        with pytest.raises(ValidationError, match="secret-capable"):
            external_spec(secrets=(secret,), maturity=None)
        with pytest.raises(ValidationError, match="secret-capable"):
            external_spec(secrets=(secret,), maturity=maturity_record())


def test_public_rate_limited_allows_only_optional_secrets() -> None:
    required = SecretSpec(secret_id="api_token", environment_variable="API_TOKEN", required=True)
    optional = required.model_copy(update={"required": False})
    maturity = maturity_record(access_classes=(AccessClass.PUBLIC_RATE_LIMITED,))

    assert external_spec(secrets=(optional,), maturity=maturity)
    with pytest.raises(ValidationError, match="required secret"):
        external_spec(secrets=(required,), maturity=maturity)


@pytest.mark.parametrize(
    "access_classes",
    (
        (AccessClass.SECRET_REQUIRED,),
        (AccessClass.BYOL,),
        (AccessClass.SERVICE_LICENSE,),
        (AccessClass.SECRET_REQUIRED, AccessClass.BYOL),
    ),
)
def test_required_secret_capable_access_classes_allow_required_credentials(
    access_classes: tuple[AccessClass, ...],
) -> None:
    required = SecretSpec(secret_id="api_token", environment_variable="API_TOKEN", required=True)

    spec = external_spec(
        secrets=(required,),
        maturity=maturity_record(access_classes=access_classes),
    )

    assert spec.secrets == (required,)
    if {AccessClass.BYOL, AccessClass.SERVICE_LICENSE} & set(access_classes):
        assert spec.maturity is not None
        assert spec.maturity.quarantined is True
        assert spec.maturity.released is False


def test_secret_required_access_class_mandates_at_least_one_required_secret() -> None:
    optional = SecretSpec(
        secret_id="api_token",
        environment_variable="API_TOKEN",
        required=False,
    )
    maturity = maturity_record(access_classes=(AccessClass.SECRET_REQUIRED,))

    with pytest.raises(ValidationError, match="required secret"):
        external_spec(maturity=maturity)
    with pytest.raises(ValidationError, match="required secret"):
        external_spec(secrets=(optional,), maturity=maturity)
    assert external_spec(maturity=None)


@pytest.mark.parametrize(
    ("identity", "evidence"),
    (
        (external_identity(tool_id="bcftools"), evidence_record()),
        (
            external_identity(tool_id="bcftools"),
            evidence_record(tool_id="bcftools"),
        ),
        (
            external_identity(tool_version="1.21"),
            evidence_record(tool_version="1.20"),
        ),
    ),
)
def test_evidence_tool_and_version_must_match_declared_identity(
    identity: NodeIdentity,
    evidence: EvidenceRecord,
) -> None:
    if identity.tool_id == evidence.tool_id and identity.tool_version == evidence.tool_version:
        assert identity.tool_id is not None and identity.tool_version is not None
        spec = external_spec(
            identity=identity,
            evidence=evidence,
            environment=pixi_environment(
                tool_id=identity.tool_id,
                tool_version=identity.tool_version,
            ),
        )
        assert spec.evidence == evidence
        return

    with pytest.raises(ValidationError, match="evidence"):
        external_spec(identity=identity, evidence=evidence)


@pytest.mark.parametrize(
    "model",
    (NodeIdentity, NodePresentation, PortAlias, NodeSpec),
)
def test_node_contract_models_share_the_strict_frozen_contract(model: type) -> None:
    assert model.model_config["extra"] == "forbid"
    assert model.model_config["frozen"] is True
    assert model.model_config["strict"] is True
    assert model.model_config["validate_default"] is True
    assert model.model_config["revalidate_instances"] == "always"


def test_runtime_and_retained_reference_models_share_the_strict_frozen_contract() -> None:
    for model in (
        contract.RuntimeBinding,
        contract.RetainedArtifact,
        contract.RetainedEvidenceInventory,
    ):
        assert model.model_config["extra"] == "forbid"
        assert model.model_config["frozen"] is True
        assert model.model_config["strict"] is True
        assert model.model_config["validate_default"] is True
        assert model.model_config["revalidate_instances"] == "always"


def test_new_reference_models_revalidate_model_construct_and_nested_forgery() -> None:
    valid_runtime = runtime_binding()
    invalid_runtime = contract.RuntimeBinding.model_construct(
        **{
            **valid_runtime.model_dump(mode="python"),
            "package_name": None,
        }
    )
    invalid_artifact = contract.RetainedArtifact.model_construct(
        kind=contract.RetainedArtifactKind.CONTRACT,
        artifact_id="Bad ID",
        sha256="not-a-digest",
    )
    invalid_inventory = contract.RetainedEvidenceInventory.model_construct(
        artifacts=(invalid_artifact,),
    )

    for model, forged in (
        (contract.RuntimeBinding, invalid_runtime),
        (contract.RetainedArtifact, invalid_artifact),
        (contract.RetainedEvidenceInventory, invalid_inventory),
    ):
        with pytest.raises(ValidationError):
            model.model_validate(forged)
        with pytest.raises(ValidationError):
            forged.model_copy()

    valid = external_spec(runtime_binding=valid_runtime)
    for field, forged in (
        ("runtime_binding", invalid_runtime),
        ("retained_evidence", invalid_inventory),
    ):
        forged_spec = NodeSpec.model_construct(
            **{
                **valid.model_dump(mode="python"),
                field: forged,
            }
        )
        with pytest.raises(ValidationError):
            NodeSpec.model_validate(forged_spec)
        with pytest.raises(ValidationError):
            forged_spec.model_copy()


def test_node_spec_rejects_extras_mutation_and_mutable_python_collections() -> None:
    spec = external_spec()

    with pytest.raises(ValidationError, match="extra_forbidden"):
        external_spec(released=True)
    with pytest.raises(ValidationError):
        external_spec(artifact_inputs=[])
    with pytest.raises(ValidationError):
        external_identity(aliases=["legacy-id"])
    with pytest.raises(ValidationError, match="frozen_instance"):
        spec.execution_factory = "bionodulo.nodes.catalog.core.values.string:build_plan"


def test_model_copy_and_validation_revalidate_nested_forgery() -> None:
    invalid_identity = NodeIdentity.model_construct(
        **{
            **external_identity().model_dump(mode="python"),
            "contract_version": "2",
        }
    )
    forged = NodeSpec.model_construct(
        **{
            **external_spec().model_dump(mode="python"),
            "identity": invalid_identity,
        }
    )

    with pytest.raises(ValidationError):
        NodeSpec.model_validate(forged)
    with pytest.raises(ValidationError):
        forged.model_copy()
    with pytest.raises(ValidationError):
        external_spec().model_copy(update={"artifact_inputs": []})


def test_node_spec_is_hashable_and_json_roundtrippable() -> None:
    spec = external_spec()
    rebuilt = NodeSpec.model_validate_json(spec.model_dump_json())

    assert rebuilt == spec
    assert hash(rebuilt) == hash(spec)


def test_json_dump_contains_only_declarative_authoritative_state() -> None:
    dumped = json.loads(external_spec().model_dump_json())

    assert tuple(dumped) == (
        "identity",
        "presentation",
        "artifact_inputs",
        "value_inputs",
        "parameters",
        "secrets",
        "outputs",
        "environment",
        "execution_kind",
        "execution_factory",
        "runtime_binding",
        "evidence",
        "retained_evidence",
        "maturity",
    )
    assert dumped["identity"]["stable_id"] == "legacy::Samtools Sort v1"
    assert dumped["identity"]["machine_id"] == "samtools_sort"
    assert "node_id" not in dumped["identity"]
    assert "released" not in dumped


def test_artifact_registry_membership_is_deferred_to_the_compiler() -> None:
    spec = external_spec(
        artifact_inputs=(
            ArtifactPort(
                port_id="input",
                artifact_type="unregistered.custom.type",
                cardinality=Cardinality.ONE,
            ),
        ),
        outputs=(
            OutputSpec(
                port_id="output",
                artifact_type="unregistered.custom.type",
                collector=ExactCollector(relative_path="result.bin"),
            ),
        ),
    )

    assert spec.artifact_inputs[0].artifact_type == "unregistered.custom.type"
    assert spec.outputs[0].artifact_type == "unregistered.custom.type"


def test_contract_package_exports_only_the_deliberate_node_spec_surface() -> None:
    assert contract.ExecutionKind is ExecutionKind
    assert contract.NodeIdentity is NodeIdentity
    assert contract.NodeOwnership is NodeOwnership
    assert contract.NodePresentation is NodePresentation
    assert contract.NodeSpec is NodeSpec
    assert contract.PortAlias is PortAlias
    assert contract.PortAliasScope is PortAliasScope
    assert contract.RetainedArtifact.__module__ == "bionodulo.nodes.contract.model"
    assert contract.RetainedArtifactKind.__module__ == "bionodulo.nodes.contract.model"
    assert contract.RetainedEvidenceInventory.__module__ == "bionodulo.nodes.contract.model"
    assert contract.RuntimeBinding.__module__ == "bionodulo.nodes.contract.model"


def test_model_module_is_declarative_and_has_no_import_or_execution_side_effects() -> None:
    path = Path("bionodulo/nodes/contract/model.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden_import_roots = {
        "aiohttp",
        "httpx",
        "importlib",
        "requests",
        "subprocess",
        "urllib",
    }
    forbidden_calls = {"__import__", "compile", "eval", "exec", "open"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".", 1)[0] not in forbidden_import_roots for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            assert node.module.split(".", 1)[0] not in forbidden_import_roots
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in forbidden_calls
