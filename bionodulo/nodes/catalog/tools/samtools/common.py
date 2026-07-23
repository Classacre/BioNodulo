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
SAMTOOLS_LOCK_SHA256 = "sha256:da58ebe2f489d3d740f23c302e9495ab23068491bad714f605438a92fb8afaa4"
SAMTOOLS_PACKAGE_SHA256 = "sha256:2cb721907a2df7c54580298d655ae7587dbed593bd5536fa8ef4a22c9ae2a496"
SAMTOOLS_RETRIEVED_AT = date(2026, 7, 23)
SAMTOOLS_PLATFORM = ExecutionPlatform.LINUX_AMD64

# SHA-256 identities of the exact files in the pinned upstream checkout
# ``/tmp/bionodulo-samtools-1.23.1`` at commit
# 6efb9b6da35224cf804921dedecf9fb8f411365d.  We retain only digests in the
# catalog; source bytes are reopened by evidence verification tooling.
SAMTOOLS_SOURCE_EVIDENCE: dict[str, dict[str, str | int]] = {
    "view": {
        "manual_sha256": "sha256:c4efdd51e9ad6a9f5ae1d8f752f3ed5412816cce1ff51063d108c603b99db05a",
        "manual_length": 21522,
        "manual_excerpt_sha256": "sha256:281fd9c75e15b194e69e9b72bab0a5a5d17aa2aca3fb1ef24feaafcb71f533a6",
        "source_sha256": "sha256:49102b2145657ed84e519423934050119990ca5aaf7a823df2cc4a63cb0e9c35",
        "source_length": 65557,
    },
    "collate": {
        "manual_sha256": "sha256:4a4546a49904ea0ee117f6eb3d136eb0dcb5de574563955399c1dd14517aab6d",
        "manual_length": 5045,
        "manual_excerpt_sha256": "sha256:840cdfbb81d06aa93dafef9488a0f20f18a1b6760dd69e1be811329c828ebef6",
        "source_sha256": "sha256:098fc15d22e0997f9707464858a12c645d7d2e4b60245393474218f2a3c999ef",
        "source_length": 20628,
    },
    "fixmate": {
        "manual_sha256": "sha256:f91e0ae8f6e8d25d3431744386f71f1b2edf8d6009c4e7e19b5354d078134a7d",
        "manual_length": 3549,
        "manual_excerpt_sha256": "sha256:2d79f056c993c45ba07f8010f6a9a16db90853a2699387b95f99fa502b2c3918",
        "source_sha256": "sha256:d01338f188c64a9f9d62308e084465d3252374374d15e1651791d42b89f15ecb",
        "source_length": 43201,
    },
    "sort": {
        "manual_sha256": "sha256:38a72be83b39bf93e8aee8a23d5c197ff0f296a9a251bc2d56a7afbebaa2434c",
        "manual_length": 11441,
        "manual_excerpt_sha256": "sha256:426a1a997edf78f1e4c6f5d6e69ed791bcced6820c4ef1a343810335dd3469a3",
        "source_sha256": "sha256:398e25e740dd3fb1ed0379c352c8da19248342ceb4ddf2931bb0a260f2b0a7d6",
        "source_length": 136849,
    },
    "markdup": {
        "manual_sha256": "sha256:42f3cd5f96188ece990929e1115584e2f8ad8d0ece63411a62b6176dfd2a8667",
        "manual_length": 9723,
        "manual_excerpt_sha256": "sha256:855469754360e9241630b3a62cc6926774cb9b633694bf3c216c1836b361ad76",
        "source_sha256": "sha256:9352675009926d2ba35c4d18d9322d0972eb1663fd61c2ffe5c65fa3e1c52d3d",
        "source_length": 84991,
    },
    "index": {
        "manual_sha256": "sha256:4eaf8f0b0298291d52ef5706056e74012dccfaa97d8fbf9a6777fac1585d1e6e",
        "manual_length": 3906,
        "manual_excerpt_sha256": "sha256:20cdbb81cf010c678a82e1c87e98d9227495e4deadb7f059353a18ad056f3bfe",
        "source_sha256": "sha256:ac7e0f4157c655c654cc8f264e66bb749c6938a9e3b7eaa85c40440207e4718b",
        "source_length": 9716,
    },
    "flagstat": {
        "manual_sha256": "sha256:38ac635d440c7d8a0758842ac217512e39df136a26c3cfafd9830afe69e26965",
        "manual_length": 6049,
        "manual_excerpt_sha256": "sha256:e3d804c2921a8fdefe0e4ace851838b6c21c0f5caeed5e91f45c26eab559b8ca",
        "source_sha256": "sha256:9a5623b2f3534045627ed7f6ed658a7e3645ab395ef6f5819dbbfca215f50c62",
        "source_length": 13640,
    },
}


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


def _evidence(
    operation: str,
    *,
    source_file: str,
    source_symbol: str,
    contract_factory: str,
) -> EvidenceRecord:
    """Build source-backed evidence for one operation.

    The source identities are SHA-256 digests of the exact pinned manpage and
    C source files.  Verification tooling reopens those files and checks the
    declared 0..1024-byte proof range before admitting evidence.
    """

    source_evidence = SAMTOOLS_SOURCE_EVIDENCE[operation]
    manual_url = f"https://www.htslib.org/doc/samtools-{operation}.html"
    manual_source = EvidenceSource(
        source_id=f"samtools-{operation}-manual",
        tool_id="samtools",
        kind=SourceKind.OFFICIAL_MANUAL,
        tool_version=SAMTOOLS_VERSION,
        retrieved_at=SAMTOOLS_RETRIEVED_AT,
        content_sha256=source_evidence["manual_sha256"],  # type: ignore[arg-type]
        content_format=SourceContentFormat.TEXT,
        title=_author_text(operation, "title"),
        description=_author_text(operation, "description"),
        url=manual_url,
        documentation_proof=DocumentationVersionProof(
            proof_kind=DocumentationProofKind.DECLARED_METADATA,
            tool_id="samtools",
            tool_version=SAMTOOLS_VERSION,
            source_url=manual_url,
            source_content_sha256=source_evidence["manual_sha256"],  # type: ignore[arg-type]
            locator=ByteRangeLocator(
                kind=ContentLocatorKind.BYTE_RANGE,
                start_byte=0,
                end_byte_exclusive=1024,
            ),
            proof_content_sha256=source_evidence["manual_excerpt_sha256"],  # type: ignore[arg-type]
        ),
    )
    upstream_url = f"{SAMTOOLS_GIT_URL.removesuffix('.git')}/blob/{SAMTOOLS_GIT_COMMIT}/{source_file}"
    upstream_source = EvidenceSource(
        source_id=f"samtools-{operation}-source",
        tool_id="samtools",
        kind=SourceKind.UPSTREAM_SOURCE,
        tool_version=SAMTOOLS_VERSION,
        retrieved_at=SAMTOOLS_RETRIEVED_AT,
        content_sha256=source_evidence["source_sha256"],  # type: ignore[arg-type]
        content_format=SourceContentFormat.SOURCE_CODE,
        title=_author_text(operation, "title"),
        description=_author_text(operation, "description"),
        url=upstream_url,
        commit=SAMTOOLS_GIT_COMMIT,
        source_path=source_file,
        symbol_locator=source_symbol,
    )
    contract_content = json.dumps(
        contract_factory,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    claim = EvidenceClaim(
        claim_id="command-contract",
        contract_pointer="/execution_factory",
        source_id=manual_source.source_id,
        locator=ByteRangeLocator(
            kind=ContentLocatorKind.BYTE_RANGE,
            start_byte=0,
            end_byte_exclusive=1024,
        ),
        statement=_author_text(operation, "description"),
        source_content_sha256=manual_source.content_sha256,
        excerpt_sha256=source_evidence["manual_excerpt_sha256"],  # type: ignore[arg-type]
        contract_value_sha256=_sha256(contract_content),
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
    evidence = _evidence(
        operation,
        source_file=source_file,
        source_symbol=source_symbol,
        contract_factory=factory,
    )
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
    "SAMTOOLS_SOURCE_EVIDENCE",
    "build_argv_plan",
    "exact_output",
    "make_spec",
    "samtools_environment",
    "stdout_output",
    "threads_parameter",
]
