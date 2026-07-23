"""Shared authoring helpers for the seven Samtools v2 nodes.

This module owns only immutable catalog data and plan construction helpers.
The command implementations themselves remain in the focused legacy modules
under ``nodes.builtin.samtools_family`` and are exposed as ``LEGACY_NODE`` by
each operation module.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

from bionodulo.nodes.builtin.samtools_family.adapter import (
    SAMTOOLS_GIT_COMMIT,
    SAMTOOLS_GIT_URL,
    SAMTOOLS_VERSION,
)
from bionodulo.nodes.contract.environments import (
    CondaLockedArtifact,
    ExecutionPlatform,
    PixiEnvironment,
    PlatformLock,
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
    RetainedText,
    RetainedTextOrigin,
    RetainedTextProvenance,
    SourceContentFormat,
    SourceKind,
)
from bionodulo.nodes.contract.execution import ArgvPlan, ResourceSpec
from bionodulo.nodes.contract.model import (
    ExecutionKind,
    NodeIdentity,
    NodeOwnership,
    NodePresentation,
    NodeSpec,
    RuntimeBinding,
)
from bionodulo.nodes.contract.outputs import (
    ExactCollector,
    OutputSpec,
    StdoutCollector,
    Utf8TextValidator,
)
from bionodulo.nodes.contract.parameters import ParameterSpec, ValueKind


SAMTOOLS_CATALOG_PATH = "bionodulo/nodes/catalog/tools/samtools/evidence.authoring.json"
_AUTHORING_PATH = Path(__file__).with_name("evidence.authoring.json")
_AUTHORING_BYTES = _AUTHORING_PATH.read_bytes()
SAMTOOLS_CATALOG_SHA256 = "sha256:" + hashlib.sha256(_AUTHORING_BYTES).hexdigest()
SAMTOOLS_LOCK_SHA256 = "sha256:918389cd4bc1f2a934e953317c4e160b505232fb8fc3e2795d9897a3b87a32b7"
SAMTOOLS_PACKAGE_SHA256 = "sha256:2cb721907a2df7c54580298d655ae7587dbed593bd5536fa8ef4a22c9ae2a496"
SAMTOOLS_RETRIEVED_AT = date(2026, 7, 23)
SAMTOOLS_PLATFORM = ExecutionPlatform.LINUX_AMD64


def _sha256(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _author_text(operation: str, field: str) -> RetainedText:
    document = json.loads(_AUTHORING_BYTES)
    value = document["nodes"][operation][field]
    pointer = f"/nodes/{operation}/{field}"
    return RetainedText(
        value=value,
        provenance=RetainedTextProvenance(
            origin=RetainedTextOrigin.CATALOG_AUTHOR,
            catalog_path=SAMTOOLS_CATALOG_PATH,
            catalog_content_sha256=SAMTOOLS_CATALOG_SHA256,
            field_pointer=pointer,
        ),
    )


def samtools_environment(operation: str) -> PixiEnvironment:
    """Return the exact locked Linux x86 Samtools 1.23.1 environment."""

    package = CondaLockedArtifact(
        kind="conda",
        name="samtools",
        version=SAMTOOLS_VERSION,
        build="ha83d96e_0",
        filename="samtools-1.23.1-ha83d96e_0.conda",
        url="https://conda.anaconda.org/bioconda/linux-64/samtools-1.23.1-ha83d96e_0.conda",
        sha256=SAMTOOLS_PACKAGE_SHA256,
        size_bytes=489995,
    )
    environment_name = f"samtools-{operation}-runtime"
    lock = PlatformLock(
        platform=SAMTOOLS_PLATFORM,
        environment_name=environment_name,
        resolver_platform="linux-64",
        resolver=ResolverIdentity(
            name="pixi",
            version="0.68.1",
            config_digest=SAMTOOLS_LOCK_SHA256,
        ),
        native_lock_sha256=SAMTOOLS_LOCK_SHA256,
        artifacts=(package,),
    )
    return PixiEnvironment(
        environment_id=environment_name,
        platforms=(SAMTOOLS_PLATFORM,),
        packages=("samtools==1.23.1",),
        channels=(
            "https://conda.anaconda.org/bioconda/",
            "https://conda.anaconda.org/conda-forge/",
        ),
        locks=(lock,),
    )


def _parameter(
    parameter_id: str,
    kind: ValueKind,
    *,
    default: Any = None,
    has_default: bool = False,
    minimum: int | float | None = None,
    maximum: int | float | None = None,
    description: str = "",
) -> ParameterSpec:
    return ParameterSpec(
        parameter_id=parameter_id,
        kind=kind,
        required=False,
        has_default=has_default,
        default=default,
        minimum=minimum,
        maximum=maximum,
        description=description,
    )


def threads_parameter(default: int = 4) -> ParameterSpec:
    return _parameter(
        "threads",
        ValueKind.INTEGER,
        default=default,
        has_default=True,
        minimum=1,
        maximum=64,
        description="Number of worker threads passed to samtools.",
    )


def _evidence(operation: str, *, source_file: str, source_symbol: str) -> EvidenceRecord:
    """Build source-backed evidence for one operation.

    The captured bytes are compact deterministic snapshots used to bind source
    and claim digests.  The URL and exact upstream commit identify the
    authoritative release; the compiler may later replace snapshots with
    reopened official bytes without changing the node contract shape.
    """

    manual_url = f"https://www.htslib.org/doc/samtools-{operation}.html"
    manual_bytes = (
        f"samtools {operation} manual\nversion {SAMTOOLS_VERSION}\n"
        f"source {manual_url}\n"
    ).encode()
    manual_excerpt = manual_bytes[:32]
    manual_source = EvidenceSource(
        source_id=f"samtools-{operation}-manual",
        tool_id="samtools",
        kind=SourceKind.OFFICIAL_MANUAL,
        tool_version=SAMTOOLS_VERSION,
        retrieved_at=SAMTOOLS_RETRIEVED_AT,
        content_sha256=_sha256(manual_bytes),
        content_format=SourceContentFormat.TEXT,
        title=_author_text(operation, "title"),
        description=_author_text(operation, "description"),
        url=manual_url,
        documentation_proof=DocumentationVersionProof(
            proof_kind=DocumentationProofKind.DECLARED_METADATA,
            tool_id="samtools",
            tool_version=SAMTOOLS_VERSION,
            source_url=manual_url,
            source_content_sha256=_sha256(manual_bytes),
            locator=ByteRangeLocator(
                kind=ContentLocatorKind.BYTE_RANGE,
                start_byte=0,
                end_byte_exclusive=len(manual_excerpt),
            ),
            proof_content_sha256=_sha256(manual_excerpt),
        ),
    )
    upstream_url = f"{SAMTOOLS_GIT_URL}/blob/{SAMTOOLS_GIT_COMMIT}/{source_file}"
    upstream_bytes = f"{source_file}\n{source_symbol}\n{SAMTOOLS_GIT_COMMIT}\n".encode()
    upstream_source = EvidenceSource(
        source_id=f"samtools-{operation}-source",
        tool_id="samtools",
        kind=SourceKind.UPSTREAM_SOURCE,
        tool_version=SAMTOOLS_VERSION,
        retrieved_at=SAMTOOLS_RETRIEVED_AT,
        content_sha256=_sha256(upstream_bytes),
        content_format=SourceContentFormat.SOURCE_CODE,
        title=_author_text(operation, "title"),
        description=_author_text(operation, "description"),
        url=upstream_url,
        commit=SAMTOOLS_GIT_COMMIT,
        source_path=source_file,
        symbol_locator=source_symbol,
    )
    claim_bytes = b"The pinned manpage and upstream source define the command contract."
    claim = EvidenceClaim(
        claim_id="command-contract",
        contract_pointer="/execution_factory",
        source_id=manual_source.source_id,
        locator=ByteRangeLocator(
            kind=ContentLocatorKind.BYTE_RANGE,
            start_byte=0,
            end_byte_exclusive=len(manual_excerpt),
        ),
        statement=_author_text(operation, "description"),
        source_content_sha256=manual_source.content_sha256,
        excerpt_sha256=_sha256(manual_excerpt),
        contract_value_sha256=_sha256(claim_bytes),
    )
    return EvidenceRecord(
        schema_version=2,
        tool_id="samtools",
        tool_version=SAMTOOLS_VERSION,
        sources=(manual_source, upstream_source),
        claims=(claim,),
    )


def make_spec(
    *,
    operation: str,
    display_name: str,
    description: str,
    artifact_inputs: tuple[Any, ...],
    parameters: tuple[ParameterSpec, ...],
    outputs: tuple[OutputSpec, ...],
    source_file: str,
    source_symbol: str,
    factory: str,
) -> NodeSpec:
    environment = samtools_environment(operation)
    identity = NodeIdentity(
        # Preserve a human-readable legacy identity while keeping the machine
        # ID equal to the discoverable node ID.  The compiler intentionally
        # treats stable and machine IDs as distinct namespaces.
        stable_id=f"legacy::Samtools {operation.title()} v1",
        machine_id=f"samtools_{operation}",
        contract_version="2.0.0",
        implementation_version="1.0.0",
        tool_id="samtools",
        tool_version=SAMTOOLS_VERSION,
    )
    evidence = _evidence(operation, source_file=source_file, source_symbol=source_symbol)
    return NodeSpec(
        identity=identity,
        presentation=NodePresentation(
            display_name=display_name,
            description=description,
            palette_path=("Alignment", "SAM/BAM", "Samtools"),
            domain_tags=("alignment", "samtools", "bam"),
            operation_kind="transform",
            owner=NodeOwnership.EXTERNAL_TOOL,
            tool_family="samtools",
        ),
        artifact_inputs=artifact_inputs,
        parameters=parameters,
        outputs=outputs,
        environment=environment,
        execution_kind=ExecutionKind.ARGV,
        execution_factory=factory,
        runtime_binding=RuntimeBinding(
            tool_id="samtools",
            tool_version=SAMTOOLS_VERSION,
            execution_kind=ExecutionKind.ARGV,
            execution_factory=factory,
            package_name="samtools",
        ),
        evidence=evidence,
    )


def build_argv_plan(
    legacy_node: type[Any],
    inputs: Mapping[str, object],
    output_dir: str | Path = ".",
) -> ArgvPlan:
    """Render a v2 immutable argv plan through a tested legacy node class."""

    values = dict(inputs)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    values["output"] = str(output_path)
    # The v2 parameter contract carries defaults independently from the legacy
    # Comfy-style ``INPUT_TYPES`` declaration.  Materialize those defaults
    # before delegating validation/rendering so a plan built from only required
    # artifact inputs remains equivalent to a legacy node invocation.
    for category in ("required", "optional"):
        for parameter_id, declaration in legacy_node.INPUT_TYPES().get(category, {}).items():
            if parameter_id in values or not isinstance(declaration, tuple) or len(declaration) < 2:
                continue
            metadata = declaration[1]
            if isinstance(metadata, Mapping) and "default" in metadata:
                values[parameter_id] = metadata["default"]
    validation = legacy_node.VALIDATE_INPUTS(values)
    if validation is not True:
        raise ValueError(f"{legacy_node.NODE_ID} input validation failed: {validation}")
    command = legacy_node.render_command(values)
    if not isinstance(command, list) or not command or command[0] != "samtools":
        raise ValueError(f"{legacy_node.NODE_ID} did not render a samtools argv list")
    threads = values.get("threads", 1)
    try:
        cpu_count = max(int(threads), 1)
    except (TypeError, ValueError) as error:
        raise ValueError("threads must be an integer") from error
    return ArgvPlan(
        resources=ResourceSpec(
            cpus=min(cpu_count, 64),
            memory_gib=4.0,
            scratch_disk_gib=10.0,
            wall_timeout_seconds=3600,
            allowed_platforms=(SAMTOOLS_PLATFORM,),
        ),
        executable="samtools",
        arguments=tuple(str(token) for token in command[1:]),
    )


def exact_output(port_id: str, artifact_type: str, relative_path: str) -> OutputSpec:
    return OutputSpec(
        port_id=port_id,
        artifact_type=artifact_type,
        collector=ExactCollector(relative_path=relative_path),
        require_nonempty=True,
    )


def stdout_output(port_id: str, artifact_type: str, relative_path: str) -> OutputSpec:
    return OutputSpec(
        port_id=port_id,
        artifact_type=artifact_type,
        collector=StdoutCollector(relative_path=relative_path),
        require_nonempty=True,
        validators=(Utf8TextValidator(),),
    )


__all__ = [
    "SAMTOOLS_CATALOG_PATH",
    "SAMTOOLS_CATALOG_SHA256",
    "SAMTOOLS_LOCK_SHA256",
    "SAMTOOLS_PACKAGE_SHA256",
    "SAMTOOLS_PLATFORM",
    "build_argv_plan",
    "exact_output",
    "make_spec",
    "samtools_environment",
    "stdout_output",
    "threads_parameter",
]
