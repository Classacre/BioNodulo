"""Source-only, digest-locked CWL container contracts.

These contracts are deliberately separate from native Conda-backed NodeSpecs.
An OCI node can be registered only by explicit experimental catalog opt-in;
readiness and execution require a proven host-local runtime. No bio.tools
identity is inferred from an image name or command.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from typing import Annotated, Any, Self
from urllib.parse import urlsplit

import yaml  # type: ignore[import-untyped]
from pydantic import Field, StringConstraints, model_validator

from bionodulo.nodes.contract.artifacts import _StrictFrozenModel
from bionodulo.nodes.contract.cwl_reference import (
    CwlReferenceInspection,
    CwlReferenceImportError,
    _UniqueKeyLoader,
    inspect_reference_document,
)
from bionodulo.nodes.contract.environments import ExecutionPlatform, Sha256Digest, _validate_oci_reference


_IMAGE_RE = re.compile(
    r"^(?P<name>[a-z0-9][a-z0-9._/-]*|[a-z0-9][a-z0-9.-]*(?::[0-9]+)?/[a-z0-9][a-z0-9._/-]*)"
    r"(?::(?P<tag>[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}))?"
    r"(?:@sha256:(?P<digest>[0-9a-f]{64}))?$"
)
_MAX_SOURCE_BYTES = 4 * 1024 * 1024


class CwlOciImportError(ValueError):
    """The source cannot enter the digest-locked container profile."""


def canonical_image(value: str) -> tuple[str, str | None, str | None]:
    """Return explicit registry repository, tag, and optional digest."""

    if not isinstance(value, str) or len(value) > 512 or any(ch.isspace() for ch in value):
        raise CwlOciImportError("Docker image must be a bounded, non-whitespace string")
    match = _IMAGE_RE.fullmatch(value)
    if match is None:
        raise CwlOciImportError(f"invalid Docker image reference: {value!r}")
    name = match.group("name")
    tag = match.group("tag")
    digest = match.group("digest")
    first, separator, rest = name.partition("/")
    if separator and ("." in first or ":" in first or first == "localhost"):
        registry, repository = first, rest
    else:
        registry, repository = "registry-1.docker.io", name
        if "/" not in repository:
            repository = "library/" + repository
    if registry in {"docker.io", "index.docker.io"}:
        registry = "registry-1.docker.io"
    if not repository or any(segment in {"", ".", ".."} for segment in repository.split("/")):
        raise CwlOciImportError("Docker repository path is not canonical")
    return f"{registry}/{repository}", tag, digest


def _docker_declarations(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    declarations: list[dict[str, Any]] = []
    for location in ("requirements", "hints"):
        raw = document.get(location)
        if isinstance(raw, Mapping):
            declaration = raw.get("DockerRequirement")
            if declaration is not None:
                if not isinstance(declaration, dict):
                    raise CwlOciImportError("DockerRequirement must be an object")
                declarations.append(declaration)
        elif isinstance(raw, list):
            declarations.extend(
                item for item in raw
                if isinstance(item, dict) and item.get("class") == "DockerRequirement"
            )
    return declarations


def declared_docker_pull(document: Mapping[str, Any]) -> str:
    declarations = _docker_declarations(document)
    if len(declarations) != 1 or not isinstance(declarations[0].get("dockerPull"), str):
        raise CwlOciImportError("exactly one source-declared DockerRequirement.dockerPull is required")
    pull = declarations[0]["dockerPull"]
    canonical_image(pull)
    return pull


def _parse_source(source: bytes | str) -> tuple[bytes, str, dict[str, Any]]:
    raw = source.encode("utf-8") if isinstance(source, str) else source
    if not raw or len(raw) > _MAX_SOURCE_BYTES or b"\x00" in raw:
        raise CwlOciImportError("CWL source is empty, unsafe, or exceeds 4 MiB")
    try:
        text = raw.decode("utf-8")
        document = yaml.load(text, Loader=_UniqueKeyLoader)
    except (UnicodeError, yaml.YAMLError) as error:
        raise CwlOciImportError(f"invalid UTF-8 CWL source: {error}") from error
    if type(document) is not dict:
        raise CwlOciImportError("CWL source must be an object")
    return raw, text, document


class CwlOciContract(_StrictFrozenModel):
    source_uri: Annotated[str, StringConstraints(min_length=1, max_length=4096)]
    source_text: Annotated[str, StringConstraints(min_length=1)]
    source_sha256: Sha256Digest
    source_size_bytes: Annotated[int, Field(strict=True, ge=1, le=_MAX_SOURCE_BYTES)]
    source_docker_pull: Annotated[str, StringConstraints(min_length=1, max_length=512)]
    image_index: Annotated[str, StringConstraints(min_length=1, max_length=512)]
    image_platform: Annotated[str, StringConstraints(min_length=1, max_length=512)]
    platform: ExecutionPlatform
    inspection: CwlReferenceInspection
    profile: str = "oci-reference"
    verification: str = "source_only_unverified"

    @property
    def input_mappings(self) -> tuple[Any, ...]:
        return self.inspection.input_mappings

    @property
    def output_mappings(self) -> tuple[Any, ...]:
        return self.inspection.output_mappings

    @property
    def unfulfilled_hints(self) -> tuple[str, ...]:
        return self.inspection.unfulfilled_hints

    @model_validator(mode="after")
    def _check_identity(self) -> Self:
        parsed = urlsplit(self.source_uri)
        if parsed.scheme not in {"https", "file"} or parsed.fragment or parsed.username or parsed.password:
            raise ValueError("source URI must be an absolute credential-free HTTPS or file URI")
        if parsed.scheme == "https" and not parsed.hostname:
            raise ValueError("HTTPS source URI requires a host")
        if parsed.scheme == "file" and not parsed.path.startswith("/"):
            raise ValueError("file source URI must be absolute")
        raw, _, document = _parse_source(self.source_text)
        if len(raw) != self.source_size_bytes or "sha256:" + hashlib.sha256(raw).hexdigest() != self.source_sha256:
            raise ValueError("retained CWL source identity changed")
        if declared_docker_pull(document) != self.source_docker_pull:
            raise ValueError("Docker pull declaration differs from retained source")
        source_repository, _, source_digest = canonical_image(self.source_docker_pull)
        index_repository, _, index_digest = canonical_image(self.image_index)
        platform_repository, _, platform_digest = canonical_image(self.image_platform)
        if source_repository != index_repository or source_repository != platform_repository:
            raise ValueError("resolved image repository differs from source declaration")
        if index_digest is None or platform_digest is None:
            raise ValueError("OCI images must use immutable sha256 digests")
        if source_digest is not None and index_digest != source_digest:
            raise ValueError("source-declared image digest differs from resolved immutable index")
        _validate_oci_reference(self.image_index)
        _validate_oci_reference(self.image_platform)
        if self.inspection != inspect_reference_document(document, allow_container_requirement=True):
            raise ValueError("CWL projection differs from retained source")
        if self.profile != "oci-reference" or self.verification != "source_only_unverified":
            raise ValueError("OCI source profile cannot assert execution verification")
        return self

    def effective_source(self) -> tuple[bytes, str]:
        """Substitute only the Docker pull with the locked platform manifest."""

        _, _, document = _parse_source(self.source_text)
        declared = declared_docker_pull(document)
        declaration = _docker_declarations(document)[0]
        assert declaration["dockerPull"] == declared
        declaration["dockerPull"] = self.image_platform
        rendered = yaml.safe_dump(document, sort_keys=False, allow_unicode=True).encode("utf-8")
        return rendered, "sha256:" + hashlib.sha256(rendered).hexdigest()


def import_cwl_oci(
    source: bytes | str,
    *,
    source_uri: str,
    image_index: str,
    image_platform: str,
    platform: ExecutionPlatform,
) -> CwlOciContract:
    raw, text, document = _parse_source(source)
    pull = declared_docker_pull(document)
    try:
        inspection = inspect_reference_document(document, allow_container_requirement=True)
    except CwlReferenceImportError as error:
        raise CwlOciImportError(str(error)) from error
    return CwlOciContract(
        source_uri=source_uri,
        source_text=text,
        source_sha256="sha256:" + hashlib.sha256(raw).hexdigest(),
        source_size_bytes=len(raw),
        source_docker_pull=pull,
        image_index=image_index,
        image_platform=image_platform,
        platform=platform,
        inspection=inspection,
    )


def import_cwl_oci_spec(contract: CwlOciContract, *, node_id: str) -> Any:
    """Project a resolved source contract into one experimental app NodeSpec.

    The source image tag is the container release identity, not a bio.tools
    accession or a claim about the executable's own upstream version.
    """

    from bionodulo.nodes.contract.environments import ContainerEnvironment, ContainerImageLock
    from bionodulo.nodes.contract.model import (
        ExecutionKind, NodeIdentity, NodeOwnership, NodePresentation, NodeSpec, RuntimeBinding,
    )

    repository, tag, _ = canonical_image(contract.source_docker_pull)
    match = re.fullmatch(r"v?([0-9]+(?:\.[0-9]+)*)", tag or "")
    if match is None:
        raise CwlOciImportError("app projection requires a source-declared numeric container release tag")
    tool_id = repository.rsplit("/", 1)[-1]
    environment = ContainerEnvironment(
        environment_id="oci_" + contract.source_sha256[7:23],
        platforms=(contract.platform,),
        image=contract.image_index,
        image_locks=(ContainerImageLock(
            platform=contract.platform,
            resolver_platform={ExecutionPlatform.LINUX_AMD64: "linux-64", ExecutionPlatform.LINUX_ARM64: "linux-aarch64"}[contract.platform],
            index_image=contract.image_index,
            image=contract.image_platform,
        ),),
    )
    factory = "bionodulo.nodes.cwl_oci_runtime:CwlOciNode"
    try:
        return NodeSpec(
            identity=NodeIdentity(
                stable_id=f"cwloci::{node_id}", machine_id=node_id,
                contract_version="1.0.0", implementation_version="1.0.0",
                tool_id=tool_id, tool_version=match.group(1),
            ),
            presentation=NodePresentation(
                display_name=node_id.replace("_", " ").title(),
                description=f"Experimental CWL container from {contract.source_uri}.",
                palette_path=("Generated", "CWL", "OCI"),
                domain_tags=("cwl", "oci"), operation_kind="transform",
                owner=NodeOwnership.EXTERNAL_TOOL, tool_family=tool_id,
            ),
            artifact_inputs=contract.inspection.artifact_inputs,
            parameters=contract.inspection.parameters,
            outputs=contract.inspection.outputs,
            environment=environment,
            execution_kind=ExecutionKind.CONTAINER,
            execution_factory=factory,
            runtime_binding=RuntimeBinding(
                tool_id=tool_id, tool_version=match.group(1),
                execution_kind=ExecutionKind.CONTAINER,
                execution_factory=factory, container_image=contract.image_index,
            ),
            cwl_oci=contract,
        )
    except ValueError as error:
        raise CwlOciImportError(f"OCI app projection is invalid: {error}") from error
