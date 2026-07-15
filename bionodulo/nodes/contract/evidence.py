"""Immutable authoritative source and retained verification evidence."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from enum import StrEnum
from typing import Annotated, Self
from urllib.parse import urlsplit

from pydantic import Field, StringConstraints, field_validator, model_validator

from bionodulo.nodes.contract.artifacts import ArtifactId, _StrictFrozenModel
from bionodulo.nodes.contract.environments import (
    ExactVersion,
    Sha256Digest,
    _validate_exact_version,
    _validate_https_url,
)


_GIT_COMMIT_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_RECIPE_REVISION_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._+-]{0,127}$")
_SOURCE_PATH_SEGMENT_RE = re.compile(r"^[0-9A-Za-z._+-]+$")
_SYMBOL_LOCATOR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:-]{0,255}$")
_MOVING_REVISIONS = frozenset({"current", "head", "latest", "main", "master", "stable"})
_SHELL_META_RE = re.compile(r"[;&|`$<>]")
_ABSOLUTE_PATH_RE = re.compile(r"(?:^|=)(?:/|[A-Za-z]:[\\/])")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)(?:^|[\s,;])(?:--)?(?:api[_-]?key|license[_-]?key|password|secret|token)\s*[:=]\s*(?P<value>\S+)"
)
_REDACTED_SECRET_RE = re.compile(r"(?i)^(?:<[A-Z][A-Z0-9_-]*>|\$\{[A-Z][A-Z0-9_-]*\}|\[REDACTED\]|REDACTED|\*{3,})$")
_HELP_TOKENS = frozenset({"--help", "-h", "-help", "help"})
_MAX_ID_LENGTH = 128
_MAX_POINTER_DEPTH = 64


Title = Annotated[str, StringConstraints(min_length=1, max_length=256)]
Description = Annotated[str, StringConstraints(min_length=1, max_length=2048)]
VersionLocator = Annotated[str, StringConstraints(min_length=1, max_length=512)]
RecipeRevision = Annotated[str, StringConstraints(min_length=1, max_length=128)]
RepositoryPath = Annotated[str, StringConstraints(min_length=1, max_length=1024)]
SymbolLocator = Annotated[str, StringConstraints(min_length=1, max_length=256)]
HelpArgument = Annotated[str, StringConstraints(min_length=1, max_length=4096)]
JsonPointer = Annotated[str, StringConstraints(min_length=2, max_length=2048)]
ClaimLocator = Annotated[str, StringConstraints(min_length=1, max_length=512)]
ClaimStatement = Annotated[str, StringConstraints(min_length=1, max_length=4096)]
VerificationSummary = Annotated[str, StringConstraints(min_length=1, max_length=2048)]


def _canonical_digest(value: _StrictFrozenModel) -> str:
    payload = json.dumps(
        value.model_dump(mode="json", round_trip=True),
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _validate_bounded_id(value: str, *, label: str) -> str:
    if len(value) > _MAX_ID_LENGTH:
        raise ValueError(f"{label} must be at most {_MAX_ID_LENGTH} characters")
    return value


def _validate_text(value: str, *, label: str) -> str:
    if value != value.strip():
        raise ValueError(f"{label} must not have outer whitespace")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError(f"{label} must be a single printable line")
    for match in _SECRET_ASSIGNMENT_RE.finditer(value):
        if _REDACTED_SECRET_RE.fullmatch(match.group("value")) is None:
            raise ValueError(f"{label} must not retain secret values")
    if _ABSOLUTE_PATH_RE.search(value) is not None:
        raise ValueError(f"{label} must not retain absolute host paths")
    return value


def _validate_repository_path(value: str) -> str:
    try:
        value.encode("ascii")
    except UnicodeEncodeError as error:
        raise ValueError("source path must use canonical ASCII") from error
    if value.startswith("/") or value.endswith("/") or "\\" in value:
        raise ValueError("source path must be repository-relative POSIX syntax")
    segments = value.split("/")
    if any(segment in ("", ".", "..") or _SOURCE_PATH_SEGMENT_RE.fullmatch(segment) is None for segment in segments):
        raise ValueError("source path must be canonical and traversal-free")
    return value


def _validate_json_pointer(value: str) -> str:
    if not value.startswith("/"):
        raise ValueError("contract pointer must start with /")
    segments = value[1:].split("/")
    if len(segments) > _MAX_POINTER_DEPTH:
        raise ValueError(f"contract pointer may have at most {_MAX_POINTER_DEPTH} segments")
    for segment in segments:
        if not segment or segment != segment.strip():
            raise ValueError("contract pointer segments must be nonempty and canonical")
        index = 0
        while index < len(segment):
            character = segment[index]
            if ord(character) < 32 or ord(character) == 127:
                raise ValueError("contract pointer must not contain control characters")
            if character == "~":
                if index + 1 >= len(segment) or segment[index + 1] not in "01":
                    raise ValueError("contract pointer must use only canonical ~0 and ~1 escapes")
                index += 2
                continue
            index += 1
        decoded = segment.replace("~1", "/").replace("~0", "~")
        if decoded in (".", ".."):
            raise ValueError("contract pointer must not contain traversal segments")
    return value


def _validate_unique_ordered(values: tuple[str, ...], *, label: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{label} must be unique")
    if values != tuple(sorted(values)):
        raise ValueError(f"{label} must use canonical order")


class SourceKind(StrEnum):
    OFFICIAL_MANUAL = "official_manual"
    OFFICIAL_API_SCHEMA = "official_api_schema"
    UPSTREAM_SOURCE = "upstream_source"
    INSTALLED_HELP = "installed_help"
    PACKAGE_RECIPE = "package_recipe"


class EvidenceSource(_StrictFrozenModel):
    source_id: ArtifactId
    kind: SourceKind
    tool_version: ExactVersion
    retrieved_at: date
    content_sha256: Sha256Digest
    title: Title
    description: Description
    url: Annotated[str, StringConstraints(min_length=1, max_length=2048)] | None = None
    version_locator: VersionLocator | None = None
    recipe_revision: RecipeRevision | None = None
    commit: Annotated[str, StringConstraints(min_length=40, max_length=64)] | None = None
    source_path: RepositoryPath | None = None
    symbol_locator: SymbolLocator | None = None
    environment_digest: Sha256Digest | None = None
    executable_probe_id: ArtifactId | None = None
    argv: Annotated[tuple[HelpArgument, ...], Field(min_length=1, max_length=16)] | None = None
    output_sha256: Sha256Digest | None = None

    @field_validator("source_id")
    @classmethod
    def _validate_source_id(cls, value: str) -> str:
        return _validate_bounded_id(value, label="source ID")

    @field_validator("tool_version")
    @classmethod
    def _validate_tool_version(cls, value: str) -> str:
        return _validate_exact_version(value)

    @field_validator("title", "description", "version_locator")
    @classmethod
    def _validate_human_text(cls, value: str | None, info: object) -> str | None:
        if value is None:
            return None
        label = getattr(info, "field_name", "text").replace("_", " ")
        return _validate_text(value, label=label)

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_https_url(value, require_path=True)

    @field_validator("recipe_revision")
    @classmethod
    def _validate_recipe_revision(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if _RECIPE_REVISION_RE.fullmatch(value) is None or value.lower() in _MOVING_REVISIONS:
            raise ValueError("recipe revision must be an exact immutable revision")
        return value

    @field_validator("commit")
    @classmethod
    def _validate_commit(cls, value: str | None) -> str | None:
        if value is not None and _GIT_COMMIT_RE.fullmatch(value) is None:
            raise ValueError("commit must be an exact lowercase 40- or 64-hex Git object ID")
        return value

    @field_validator("source_path")
    @classmethod
    def _validate_source_path(cls, value: str | None) -> str | None:
        return None if value is None else _validate_repository_path(value)

    @field_validator("symbol_locator")
    @classmethod
    def _validate_symbol_locator(cls, value: str | None) -> str | None:
        if value is not None and _SYMBOL_LOCATOR_RE.fullmatch(value) is None:
            raise ValueError("symbol locator must be an exact canonical symbol identity")
        return value

    @field_validator("executable_probe_id")
    @classmethod
    def _validate_probe_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_bounded_id(value, label="executable probe ID")

    @field_validator("argv")
    @classmethod
    def _validate_argv(cls, value: tuple[str, ...] | None) -> tuple[str, ...] | None:
        if value is None:
            return None
        for argument in value:
            if argument != argument.strip() or any(character.isspace() for character in argument):
                raise ValueError("installed-help argv entries must be exact single arguments")
            if any(ord(character) < 32 or ord(character) == 127 for character in argument):
                raise ValueError("installed-help argv must not contain control characters")
            if _SHELL_META_RE.search(argument) is not None:
                raise ValueError("installed-help argv must not contain shell syntax")
            if _ABSOLUTE_PATH_RE.search(argument) is not None:
                raise ValueError("installed-help argv must not contain absolute host paths")
            if _SECRET_ASSIGNMENT_RE.search(argument) is not None:
                raise ValueError("installed-help argv must not retain secret values")
        if not any(argument in _HELP_TOKENS for argument in value):
            raise ValueError("installed-help argv must contain an explicit help token")
        return value

    @model_validator(mode="after")
    def _validate_kind_specific_capture(self) -> Self:
        documentation_fields = ("url", "version_locator")
        package_fields = ("url", "recipe_revision")
        upstream_fields = ("url", "commit", "source_path")
        installed_fields = ("environment_digest", "executable_probe_id", "argv", "output_sha256")
        all_specific_fields = {
            "url",
            "version_locator",
            "recipe_revision",
            "commit",
            "source_path",
            "symbol_locator",
            "environment_digest",
            "executable_probe_id",
            "argv",
            "output_sha256",
        }

        if self.kind in (SourceKind.OFFICIAL_MANUAL, SourceKind.OFFICIAL_API_SCHEMA):
            required = documentation_fields
            allowed = set(documentation_fields)
        elif self.kind is SourceKind.PACKAGE_RECIPE:
            required = package_fields
            allowed = set(package_fields)
        elif self.kind is SourceKind.UPSTREAM_SOURCE:
            required = upstream_fields
            allowed = {*upstream_fields, "symbol_locator"}
        else:
            required = installed_fields
            allowed = set(installed_fields)

        missing = tuple(field for field in required if getattr(self, field) is None)
        if missing:
            raise ValueError(f"{self.kind.value} source is missing required fields: {', '.join(missing)}")
        irrelevant = tuple(field for field in sorted(all_specific_fields - allowed) if getattr(self, field) is not None)
        if irrelevant:
            raise ValueError(f"{self.kind.value} source has irrelevant fields: {', '.join(irrelevant)}")

        if self.kind is SourceKind.UPSTREAM_SOURCE:
            assert self.url is not None and self.commit is not None and self.source_path is not None
            pinned_suffix = f"/{self.commit}/{self.source_path}"
            if not urlsplit(self.url).path.endswith(pinned_suffix):
                raise ValueError("upstream URL must bind the exact commit and source path")
        elif self.kind is SourceKind.PACKAGE_RECIPE:
            assert self.url is not None and self.recipe_revision is not None
            if _GIT_COMMIT_RE.fullmatch(self.recipe_revision) is not None:
                url_segments = urlsplit(self.url).path.split("/")
                if self.recipe_revision not in url_segments:
                    raise ValueError("package recipe URL must bind its exact Git revision")
        elif self.kind is SourceKind.INSTALLED_HELP and self.output_sha256 != self.content_sha256:
            raise ValueError("installed-help output digest must equal the captured content digest")
        return self


class EvidenceClaim(_StrictFrozenModel):
    claim_id: ArtifactId
    contract_pointer: JsonPointer
    source_id: ArtifactId
    locator: ClaimLocator
    statement: ClaimStatement
    source_content_sha256: Sha256Digest
    excerpt_sha256: Sha256Digest
    contract_value_sha256: Sha256Digest

    @field_validator("claim_id", "source_id")
    @classmethod
    def _validate_ids(cls, value: str, info: object) -> str:
        label = getattr(info, "field_name", "ID").replace("_", " ")
        return _validate_bounded_id(value, label=label)

    @field_validator("contract_pointer")
    @classmethod
    def _validate_contract_pointer(cls, value: str) -> str:
        return _validate_json_pointer(value)

    @field_validator("locator", "statement")
    @classmethod
    def _validate_claim_text(cls, value: str, info: object) -> str:
        label = getattr(info, "field_name", "claim text").replace("_", " ")
        return _validate_text(value, label=label)


class VerificationEvidence(_StrictFrozenModel):
    evidence_id: ArtifactId
    kind: ArtifactId
    test_id: ArtifactId
    result_sha256: Sha256Digest
    fixture_id: ArtifactId | None = None
    fixture_sha256: Sha256Digest | None = None
    environment_sha256: Sha256Digest | None = None
    catalog_sha256: Sha256Digest | None = None
    platform_sha256: Sha256Digest | None = None
    release_sha256: Sha256Digest | None = None
    verified_at: date
    summary: VerificationSummary

    @field_validator("evidence_id", "kind", "test_id", "fixture_id")
    @classmethod
    def _validate_ids(cls, value: str | None, info: object) -> str | None:
        if value is None:
            return None
        label = getattr(info, "field_name", "ID").replace("_", " ")
        return _validate_bounded_id(value, label=label)

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str) -> str:
        return _validate_text(value, label="verification summary")

    @model_validator(mode="after")
    def _validate_fixture_identity(self) -> Self:
        if (self.fixture_id is None) != (self.fixture_sha256 is None):
            raise ValueError("fixture ID and digest must be supplied together")
        return self

    def verification_digest(self) -> str:
        return _canonical_digest(self)


class EvidenceRecord(_StrictFrozenModel):
    tool_id: ArtifactId
    tool_version: ExactVersion
    sources: Annotated[tuple[EvidenceSource, ...], Field(min_length=1, max_length=512)]
    claims: Annotated[tuple[EvidenceClaim, ...], Field(min_length=1, max_length=4096)]
    verifications: Annotated[tuple[VerificationEvidence, ...], Field(max_length=4096)] = ()

    @field_validator("tool_id")
    @classmethod
    def _validate_tool_id(cls, value: str) -> str:
        return _validate_bounded_id(value, label="tool ID")

    @field_validator("tool_version")
    @classmethod
    def _validate_tool_version(cls, value: str) -> str:
        return _validate_exact_version(value)

    @model_validator(mode="after")
    def _validate_evidence_graph(self) -> Self:
        source_ids = tuple(item.source_id for item in self.sources)
        claim_ids = tuple(item.claim_id for item in self.claims)
        verification_ids = tuple(item.evidence_id for item in self.verifications)
        _validate_unique_ordered(source_ids, label="source IDs")
        _validate_unique_ordered(claim_ids, label="claim IDs")
        _validate_unique_ordered(verification_ids, label="verification evidence IDs")

        sources_by_id = {item.source_id: item for item in self.sources}
        for captured in self.sources:
            if captured.tool_version != self.tool_version:
                raise ValueError("source tool version must equal the evidence record tool version")

        bindings: set[tuple[str, ...]] = set()
        pointer_sources: set[tuple[str, str]] = set()
        for asserted in self.claims:
            captured = sources_by_id.get(asserted.source_id)
            if captured is None:
                raise ValueError(f"claim {asserted.claim_id} references missing source {asserted.source_id}")
            if asserted.source_content_sha256 != captured.content_sha256:
                raise ValueError(f"claim {asserted.claim_id} source content digest does not match its source")
            binding = (
                asserted.contract_pointer,
                asserted.source_id,
                asserted.locator,
                asserted.statement,
                asserted.source_content_sha256,
                asserted.excerpt_sha256,
                asserted.contract_value_sha256,
            )
            if binding in bindings:
                raise ValueError("duplicate exact claim binding")
            bindings.add(binding)
            pointer_source = (asserted.contract_pointer, asserted.source_id)
            if pointer_source in pointer_sources:
                raise ValueError("claims for one contract pointer must use distinct sources")
            pointer_sources.add(pointer_source)
        return self

    def evidence_digest(self) -> str:
        return _canonical_digest(self)


__all__ = [
    "EvidenceClaim",
    "EvidenceRecord",
    "EvidenceSource",
    "SourceKind",
    "VerificationEvidence",
]
