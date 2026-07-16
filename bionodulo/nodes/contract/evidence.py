"""Immutable authoritative sources and structured verification evidence."""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self, TypeAlias
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
_SOURCE_PATH_SEGMENT_RE = re.compile(r"^[0-9A-Za-z._+-]+$")
_SYMBOL_LOCATOR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:-]{0,255}$")
_SHELL_META_RE = re.compile(r"[;&|`$<>]")
_HELP_FLAG_TOKENS = frozenset({"--help", "-h", "-help"})
_HELP_WORD_TOKEN = "help"
_HELP_TOKENS = frozenset({*_HELP_FLAG_TOKENS, _HELP_WORD_TOKEN})
_HELP_SUBCOMMAND_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_MAX_ID_LENGTH = 128
_MAX_POINTER_DEPTH = 64
_MAX_BYTE_OFFSET = 2**63 - 1
_MAX_LOCATOR_SPAN = 1024 * 1024
_MAX_JSON_NUMBER_COEFFICIENT_DIGITS = 256
_MAX_JSON_NUMBER_EXPONENT = 4096
_MAX_JSON_NUMBER_ADJUSTED_EXPONENT = 4096
_MAX_JSON_INTEGER_BITS = 851  # ceil(256 * log2(10))
_MAX_JSON_INPUT_BYTES = 8 * 1024 * 1024
_MAX_JSON_NESTING_DEPTH = 64
_MAX_CANONICAL_JSON_BYTES = 1024 * 1024
_CATALOG_AUTHORING_PREFIX = "bionodulo/nodes/catalog/"
_CATALOG_AUTHORING_SUFFIX = ".authoring.json"
_CATALOG_AUTHORING_RESERVED_FIELDS = frozenset(
    {
        "catalog_content_sha256",
        "catalog_path",
        "field_pointer",
        "provenance",
    }
)
_JSON_NUMBER_RE = re.compile(
    r"(?P<sign>-?)(?P<integer>0|[1-9][0-9]*)(?:\.(?P<fraction>[0-9]+))?"
    r"(?:[eE](?P<exponent_sign>[+-]?)(?P<exponent>[0-9]+))?"
)


RepositoryPath = Annotated[str, StringConstraints(min_length=1, max_length=1024)]
JsonPointer = Annotated[str, StringConstraints(min_length=2, max_length=2048)]
SymbolIdentity = Annotated[str, StringConstraints(min_length=1, max_length=256)]
HelpArgument = Annotated[str, StringConstraints(min_length=1, max_length=4096)]
RetainedTextValue = Annotated[str, StringConstraints(min_length=1, max_length=4096)]
CanonicalUrl = Annotated[str, StringConstraints(min_length=1, max_length=2048)]


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


def _validate_printable_unicode(value: str, *, label: str) -> str:
    for character in value:
        category = unicodedata.category(character)
        if category.startswith("C") or category in ("Zl", "Zp"):
            raise ValueError(f"{label} must contain only printable Unicode characters")
    return value


def _validate_retained_value(value: str, *, label: str) -> str:
    if value != value.strip():
        raise ValueError(f"{label} must not have outer whitespace")
    return _validate_printable_unicode(value, label=label)


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


def _validate_catalog_authoring_path(value: str) -> str:
    value = _validate_repository_path(value)
    segments = value.split("/")
    if not value.startswith(_CATALOG_AUTHORING_PREFIX):
        raise ValueError("catalog provenance path must be under the checked-in catalog directory")
    if "generated" in segments or "compiled" in segments:
        raise ValueError("catalog provenance path must not point to generated content")
    if not value.endswith(_CATALOG_AUTHORING_SUFFIX):
        raise ValueError("catalog provenance path must name an authoring JSON blob")
    return value


def _decode_json_pointer(value: str) -> tuple[str, ...]:
    return tuple(segment.replace("~1", "/").replace("~0", "~") for segment in value[1:].split("/"))


def _validate_json_pointer(value: str) -> str:
    _validate_printable_unicode(value, label="JSON pointer")
    if not value.startswith("/"):
        raise ValueError("JSON pointer must start with /")
    segments = value[1:].split("/")
    if len(segments) > _MAX_POINTER_DEPTH:
        raise ValueError(f"JSON pointer may have at most {_MAX_POINTER_DEPTH} segments")
    for segment in segments:
        if not segment or segment != segment.strip():
            raise ValueError("JSON pointer segments must be nonempty and canonical")
        index = 0
        while index < len(segment):
            if segment[index] == "~":
                if index + 1 >= len(segment) or segment[index + 1] not in "01":
                    raise ValueError("JSON pointer must use only canonical ~0 and ~1 escapes")
                index += 2
                continue
            index += 1
        if segment.replace("~1", "/").replace("~0", "~") in (".", ".."):
            raise ValueError("JSON pointer must not contain traversal segments")
    return value


def _validate_symbol(value: str) -> str:
    if _SYMBOL_LOCATOR_RE.fullmatch(value) is None:
        raise ValueError("symbol must be an exact canonical identity")
    return value


def _reject_duplicate_json_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    parsed: dict[str, object] = {}
    for key, value in pairs:
        if key in parsed:
            raise ValueError(f"duplicate JSON object key: {key}")
        parsed[key] = value
    return parsed


def _reject_nonfinite_json_constant(value: str) -> object:
    raise ValueError(f"non-finite JSON number: {value}")


@dataclass(frozen=True, slots=True)
class _JsonNumber:
    canonical: str


def _parse_bounded_json_exponent(sign: str, digits: str) -> int:
    significant = digits.lstrip("0") or "0"
    maximum = str(_MAX_JSON_NUMBER_EXPONENT)
    if len(significant) > len(maximum) or (len(significant) == len(maximum) and significant > maximum):
        raise ValueError(f"JSON number exponent magnitude may be at most {_MAX_JSON_NUMBER_EXPONENT}")
    exponent = int(significant)
    return -exponent if sign == "-" else exponent


def _normalize_json_number(
    *,
    negative: bool,
    coefficient: str,
    exponent: int,
) -> _JsonNumber:
    if len(coefficient) > _MAX_JSON_NUMBER_COEFFICIENT_DIGITS:
        raise ValueError(f"JSON number coefficient may have at most {_MAX_JSON_NUMBER_COEFFICIENT_DIGITS} digits")

    significant = coefficient.lstrip("0")
    if not significant:
        return _JsonNumber("0")
    trimmed = significant.rstrip("0")
    exponent += len(significant) - len(trimmed)
    adjusted_exponent = exponent + len(trimmed) - 1
    if abs(adjusted_exponent) > _MAX_JSON_NUMBER_ADJUSTED_EXPONENT:
        raise ValueError(f"JSON number adjusted exponent magnitude may be at most {_MAX_JSON_NUMBER_ADJUSTED_EXPONENT}")

    mantissa = trimmed if len(trimmed) == 1 else f"{trimmed[0]}.{trimmed[1:]}"
    exponent_suffix = "" if adjusted_exponent == 0 else f"e{adjusted_exponent}"
    sign = "-" if negative else ""
    return _JsonNumber(f"{sign}{mantissa}{exponent_suffix}")


def _parse_json_number(value: str) -> _JsonNumber:
    matched = _JSON_NUMBER_RE.fullmatch(value)
    if matched is None:
        raise ValueError(f"invalid JSON number: {value}")
    fraction = matched.group("fraction") or ""
    exponent_digits = matched.group("exponent") or "0"
    explicit_exponent = _parse_bounded_json_exponent(
        matched.group("exponent_sign") or "",
        exponent_digits,
    )
    return _normalize_json_number(
        negative=matched.group("sign") == "-",
        coefficient=matched.group("integer") + fraction,
        exponent=explicit_exponent - len(fraction),
    )


def _decimal_json_number(value: Decimal) -> _JsonNumber:
    if not value.is_finite():
        raise ValueError("JSON numbers must be finite")
    parts = value.as_tuple()
    exponent = parts.exponent
    if not isinstance(exponent, int) or abs(exponent) > _MAX_JSON_NUMBER_EXPONENT:
        raise ValueError(f"JSON number exponent magnitude may be at most {_MAX_JSON_NUMBER_EXPONENT}")
    coefficient = "".join(str(digit) for digit in parts.digits) or "0"
    return _normalize_json_number(
        negative=bool(parts.sign),
        coefficient=coefficient,
        exponent=exponent,
    )


def _canonical_json_bytes(value: object, *, label: str) -> bytes:
    parts: list[str] = []
    size = 0
    active_containers: set[int] = set()

    def append(token: str) -> None:
        nonlocal size
        size += len(token)
        if size > _MAX_CANONICAL_JSON_BYTES:
            raise ValueError(f"canonical JSON may be at most {_MAX_CANONICAL_JSON_BYTES} bytes")
        parts.append(token)

    def serialize(selected: object, depth: int) -> None:
        if selected is None:
            append("null")
            return
        if type(selected) is bool:
            append("true" if selected else "false")
            return
        if isinstance(selected, _JsonNumber):
            append(selected.canonical)
            return
        if type(selected) is int:
            if selected.bit_length() > _MAX_JSON_INTEGER_BITS:
                raise ValueError(
                    f"JSON number coefficient may have at most {_MAX_JSON_NUMBER_COEFFICIENT_DIGITS} digits"
                )
            append(_parse_json_number(str(selected)).canonical)
            return
        if type(selected) is float:
            if not math.isfinite(selected):
                raise ValueError("JSON numbers must be finite")
            append(_parse_json_number(repr(selected)).canonical)
            return
        if isinstance(selected, Decimal):
            append(_decimal_json_number(selected).canonical)
            return
        if type(selected) is str:
            if len(selected) + 2 > _MAX_CANONICAL_JSON_BYTES - size:
                raise ValueError(f"canonical JSON may be at most {_MAX_CANONICAL_JSON_BYTES} bytes")
            append(json.dumps(selected, ensure_ascii=True))
            return
        if type(selected) is list:
            container_depth = depth + 1
            if container_depth > _MAX_JSON_NESTING_DEPTH:
                raise ValueError(f"JSON nesting depth may be at most {_MAX_JSON_NESTING_DEPTH}")
            if 2 * len(selected) + 1 > _MAX_CANONICAL_JSON_BYTES:
                raise ValueError(f"canonical JSON may be at most {_MAX_CANONICAL_JSON_BYTES} bytes")
            identity = id(selected)
            if identity in active_containers:
                raise ValueError("canonical JSON must not contain container cycles")
            active_containers.add(identity)
            try:
                append("[")
                for index, item in enumerate(selected):
                    if index:
                        append(",")
                    serialize(item, container_depth)
                append("]")
            finally:
                active_containers.remove(identity)
            return
        if type(selected) is dict:
            container_depth = depth + 1
            if container_depth > _MAX_JSON_NESTING_DEPTH:
                raise ValueError(f"JSON nesting depth may be at most {_MAX_JSON_NESTING_DEPTH}")
            if any(type(key) is not str for key in selected):
                raise ValueError("JSON object keys must be strings")
            if 5 * len(selected) + 1 > _MAX_CANONICAL_JSON_BYTES:
                raise ValueError(f"canonical JSON may be at most {_MAX_CANONICAL_JSON_BYTES} bytes")
            identity = id(selected)
            if identity in active_containers:
                raise ValueError("canonical JSON must not contain container cycles")
            active_containers.add(identity)
            try:
                append("{")
                for index, key in enumerate(sorted(selected)):
                    if index:
                        append(",")
                    if len(key) + 2 > _MAX_CANONICAL_JSON_BYTES - size:
                        raise ValueError(f"canonical JSON may be at most {_MAX_CANONICAL_JSON_BYTES} bytes")
                    append(json.dumps(key, ensure_ascii=True))
                    append(":")
                    serialize(selected[key], container_depth)
                append("}")
            finally:
                active_containers.remove(identity)
            return
        raise ValueError(f"unsupported JSON value type: {type(selected).__name__}")

    try:
        serialize(value, 0)
        return "".join(parts).encode("ascii")
    except (RecursionError, ValueError) as error:
        raise ValueError(f"{label} must be canonical finite JSON: {error}") from error


def _validate_json_nesting(text: str, *, label: str) -> None:
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
                raise ValueError(f"{label} JSON nesting depth may be at most {_MAX_JSON_NESTING_DEPTH}")
        elif character in "]}":
            depth -= 1


def _load_strict_json(content: bytes, *, label: str) -> object:
    if len(content) > _MAX_JSON_INPUT_BYTES:
        raise ValueError(f"{label} JSON input may be at most {_MAX_JSON_INPUT_BYTES} bytes")
    try:
        text = content.decode("utf-8")
        _validate_json_nesting(text, label=label)
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=_reject_nonfinite_json_constant,
            parse_float=_parse_json_number,
            parse_int=_parse_json_number,
        )
    except (RecursionError, UnicodeDecodeError, ValueError) as error:
        raise ValueError(
            f"{label} must be strict JSON with unique keys, bounded numbers, and UTF-8 encoding: {error}"
        ) from error


def _resolve_json_pointer(document: object, pointer: str, *, label: str) -> object:
    selected = document
    for segment in _decode_json_pointer(pointer):
        if isinstance(selected, dict):
            if segment not in selected:
                raise ValueError(f"{label} pointer is absent from content")
            selected = selected[segment]
        elif isinstance(selected, list):
            if re.fullmatch(r"[0-9]+", segment) is None or (segment != "0" and segment.startswith("0")):
                raise ValueError(f"{label} pointer has a noncanonical array index")
            index = int(segment)
            if index >= len(selected):
                raise ValueError(f"{label} pointer is absent from content")
            selected = selected[index]
        else:
            raise ValueError(f"{label} pointer does not resolve to a value")
    return selected


def _reject_authoring_reserved_fields(document: object) -> None:
    pending = [document]
    while pending:
        selected = pending.pop()
        if isinstance(selected, dict):
            for key, value in selected.items():
                if key in _CATALOG_AUTHORING_RESERVED_FIELDS:
                    raise ValueError(f"catalog authoring content contains reserved compiler field: {key}")
                pending.append(value)
        elif isinstance(selected, list):
            pending.extend(selected)


def _validate_unique_ordered(values: tuple[str, ...], *, label: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{label} must be unique")
    if values != tuple(sorted(values)):
        raise ValueError(f"{label} must use canonical order")


def _url_path_ends_with(url: str, *segments: str) -> bool:
    path_segments = tuple(urlsplit(url).path.removeprefix("/").split("/"))
    return len(path_segments) >= len(segments) and path_segments[-len(segments) :] == segments


class RetainedTextOrigin(StrEnum):
    """Origins authorized to retain prose in catalog evidence."""

    CATALOG_AUTHOR = "catalog_author"


class RetainedTextProvenance(_StrictFrozenModel):
    """Immutable identity of prose selected from a checked-in catalog blob.

    The Task 9 catalog loader is the trust boundary that verifies the path,
    content digest, pointer, and selected value. Runtime capture code has no
    retained-text origin and must use digest-only models below.
    """

    origin: RetainedTextOrigin
    catalog_path: RepositoryPath
    catalog_content_sha256: Sha256Digest
    field_pointer: JsonPointer

    @field_validator("catalog_path")
    @classmethod
    def _validate_catalog_path(cls, value: str) -> str:
        return _validate_catalog_authoring_path(value)

    @field_validator("field_pointer")
    @classmethod
    def _validate_field_pointer(cls, value: str) -> str:
        return _validate_json_pointer(value)


class RetainedText(_StrictFrozenModel):
    value: RetainedTextValue
    provenance: RetainedTextProvenance

    @field_validator("value")
    @classmethod
    def _validate_value(cls, value: str) -> str:
        return _validate_retained_value(value, label="retained author text")


def verify_retained_text_selection(
    retained: RetainedText,
    *,
    catalog_path: str,
    catalog_content: bytes,
    expected_field_pointer: str,
) -> RetainedText:
    """Verify loader-injected provenance against compiler-owned source data.

    Task 9 must reopen the declared path, resolve the pointer itself, and pass
    those results here. Values supplied by an arbitrary node factory are not a
    substitute for that compiler-owned operation.
    """

    validated = RetainedText.model_validate(retained)
    canonical_path = _validate_catalog_authoring_path(catalog_path)
    if type(catalog_content) is not bytes:
        raise TypeError("catalog content must be exact bytes reopened by the compiler")
    content_digest = "sha256:" + hashlib.sha256(catalog_content).hexdigest()
    declared = validated.provenance
    declared_pointer = _validate_json_pointer(declared.field_pointer)
    if declared_pointer != _validate_json_pointer(expected_field_pointer):
        raise ValueError("retained text provenance does not match the compiler-selected field pointer")

    document = _load_strict_json(catalog_content, label="catalog content")
    _reject_authoring_reserved_fields(document)
    selected = _resolve_json_pointer(document, declared_pointer, label="retained text provenance")

    if (
        declared.catalog_path != canonical_path
        or declared.catalog_content_sha256 != content_digest
        or type(selected) is not str
        or validated.value != selected
    ):
        raise ValueError("retained text provenance does not match the compiler-selected catalog value")
    return validated


class ContentLocatorKind(StrEnum):
    BYTE_RANGE = "byte_range"
    JSON_POINTER = "json_pointer"
    SYMBOL = "symbol"


class SourceContentFormat(StrEnum):
    TEXT = "text"
    JSON = "json"
    SOURCE_CODE = "source_code"


class ByteRangeLocator(_StrictFrozenModel):
    kind: Literal[ContentLocatorKind.BYTE_RANGE]
    start_byte: Annotated[int, Field(ge=0, le=_MAX_BYTE_OFFSET)]
    end_byte_exclusive: Annotated[int, Field(ge=1, le=_MAX_BYTE_OFFSET)]

    @model_validator(mode="after")
    def _validate_range(self) -> Self:
        if self.end_byte_exclusive <= self.start_byte:
            raise ValueError("byte range end must be greater than its start")
        if self.end_byte_exclusive - self.start_byte > _MAX_LOCATOR_SPAN:
            raise ValueError(f"byte range may select at most {_MAX_LOCATOR_SPAN} bytes")
        return self


class JsonPointerLocator(_StrictFrozenModel):
    kind: Literal[ContentLocatorKind.JSON_POINTER]
    pointer: JsonPointer

    @field_validator("pointer")
    @classmethod
    def _validate_pointer(cls, value: str) -> str:
        return _validate_json_pointer(value)


class SymbolLocator(_StrictFrozenModel):
    kind: Literal[ContentLocatorKind.SYMBOL]
    symbol: SymbolIdentity

    @field_validator("symbol")
    @classmethod
    def _validate_symbol_identity(cls, value: str) -> str:
        return _validate_symbol(value)


ContentLocator: TypeAlias = Annotated[
    ByteRangeLocator | JsonPointerLocator | SymbolLocator,
    Field(discriminator="kind"),
]

DocumentationProofLocator: TypeAlias = Annotated[
    ByteRangeLocator | JsonPointerLocator,
    Field(discriminator="kind"),
]


class DocumentationProofKind(StrEnum):
    DECLARED_METADATA = "declared_metadata"
    SCHEMA_FIELD = "schema_field"
    RELEASE_MANIFEST = "release_manifest"


class DocumentationVersionProof(_StrictFrozenModel):
    proof_kind: DocumentationProofKind
    tool_id: ArtifactId
    tool_version: ExactVersion
    source_url: CanonicalUrl
    source_content_sha256: Sha256Digest
    locator: DocumentationProofLocator
    proof_content_sha256: Sha256Digest

    @field_validator("tool_id")
    @classmethod
    def _validate_tool_id(cls, value: str) -> str:
        return _validate_bounded_id(value, label="proof tool ID")

    @field_validator("tool_version")
    @classmethod
    def _validate_tool_version(cls, value: str) -> str:
        return _validate_exact_version(value)

    @field_validator("source_url")
    @classmethod
    def _validate_source_url(cls, value: str) -> str:
        return _validate_https_url(value, require_path=True)

    def proof_digest(self) -> str:
        return _canonical_digest(self)


def verify_documentation_proof_content(
    proof: DocumentationVersionProof,
    *,
    source_content: bytes,
) -> DocumentationVersionProof:
    """Recompute a documentation proof from compiler-owned captured bytes."""

    validated = DocumentationVersionProof.model_validate(proof)
    if type(source_content) is not bytes:
        raise TypeError("documentation source content must be exact captured bytes")
    source_digest = "sha256:" + hashlib.sha256(source_content).hexdigest()
    if source_digest != validated.source_content_sha256:
        raise ValueError("documentation proof source content digest does not match captured bytes")

    locator = validated.locator
    if isinstance(locator, ByteRangeLocator):
        if locator.end_byte_exclusive > len(source_content):
            raise ValueError("documentation proof locator exceeds captured source content")
        selected_content = source_content[locator.start_byte : locator.end_byte_exclusive]
    else:
        document = _load_strict_json(source_content, label="documentation source content")
        selected = _resolve_json_pointer(document, locator.pointer, label="documentation proof locator")
        selected_content = _canonical_json_bytes(
            selected,
            label="documentation proof selected value",
        )

    selected_digest = "sha256:" + hashlib.sha256(selected_content).hexdigest()
    if selected_digest != validated.proof_content_sha256:
        raise ValueError("documentation proof content digest does not match selected source content")
    return validated


class SourceKind(StrEnum):
    OFFICIAL_MANUAL = "official_manual"
    OFFICIAL_API_SCHEMA = "official_api_schema"
    UPSTREAM_SOURCE = "upstream_source"
    INSTALLED_HELP = "installed_help"
    PACKAGE_RECIPE = "package_recipe"


_SOURCE_KIND_PRECEDENCE = {kind: index for index, kind in enumerate(SourceKind)}
_DOCUMENTATION_PROOF_LOCATOR_FORMATS = {
    ByteRangeLocator: frozenset(SourceContentFormat),
    JsonPointerLocator: frozenset({SourceContentFormat.JSON}),
}
_CLAIM_LOCATOR_FORMATS = {
    ByteRangeLocator: frozenset(SourceContentFormat),
    JsonPointerLocator: frozenset({SourceContentFormat.JSON}),
    SymbolLocator: frozenset({SourceContentFormat.SOURCE_CODE}),
}


class EvidenceSource(_StrictFrozenModel):
    source_id: ArtifactId
    tool_id: ArtifactId
    kind: SourceKind
    tool_version: ExactVersion
    retrieved_at: date
    content_sha256: Sha256Digest
    content_format: SourceContentFormat
    title: RetainedText
    description: RetainedText
    url: CanonicalUrl | None = None
    documentation_proof: DocumentationVersionProof | None = None
    recipe_revision: Annotated[str, StringConstraints(min_length=40, max_length=64)] | None = None
    recipe_path: RepositoryPath | None = None
    commit: Annotated[str, StringConstraints(min_length=40, max_length=64)] | None = None
    source_path: RepositoryPath | None = None
    symbol_locator: SymbolIdentity | None = None
    environment_digest: Sha256Digest | None = None
    executable_probe_id: ArtifactId | None = None
    argv: Annotated[tuple[HelpArgument, ...], Field(min_length=1, max_length=16)] | None = None
    output_sha256: Sha256Digest | None = None

    @field_validator("source_id", "tool_id")
    @classmethod
    def _validate_source_identity(cls, value: str, info: object) -> str:
        label = getattr(info, "field_name", "source ID").replace("_", " ")
        return _validate_bounded_id(value, label=label)

    @field_validator("tool_version")
    @classmethod
    def _validate_tool_version(cls, value: str) -> str:
        return _validate_exact_version(value)

    @field_validator("title", "description")
    @classmethod
    def _validate_authored_text_bounds(cls, value: RetainedText, info: object) -> RetainedText:
        field_name = getattr(info, "field_name", "description")
        maximum = 256 if field_name == "title" else 2048
        if len(value.value) > maximum:
            raise ValueError(f"{field_name} must be at most {maximum} characters")
        return value

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str | None) -> str | None:
        return None if value is None else _validate_https_url(value, require_path=True)

    @field_validator("recipe_revision", "commit")
    @classmethod
    def _validate_git_object(cls, value: str | None, info: object) -> str | None:
        if value is not None and _GIT_COMMIT_RE.fullmatch(value) is None:
            label = getattr(info, "field_name", "revision").replace("_", " ")
            raise ValueError(f"{label} must be an exact lowercase 40- or 64-hex Git object ID")
        return value

    @field_validator("recipe_path", "source_path")
    @classmethod
    def _validate_source_path(cls, value: str | None) -> str | None:
        return None if value is None else _validate_repository_path(value)

    @field_validator("symbol_locator")
    @classmethod
    def _validate_symbol_locator(cls, value: str | None) -> str | None:
        return None if value is None else _validate_symbol(value)

    @field_validator("executable_probe_id")
    @classmethod
    def _validate_probe_id(cls, value: str | None) -> str | None:
        return None if value is None else _validate_bounded_id(value, label="executable probe ID")

    @field_validator("argv")
    @classmethod
    def _validate_argv(cls, value: tuple[str, ...] | None) -> tuple[str, ...] | None:
        if value is None:
            return None
        for argument in value:
            _validate_printable_unicode(argument, label="installed-help argument")
            if argument != argument.strip() or any(character.isspace() for character in argument):
                raise ValueError("installed-help argv entries must be exact single arguments")
            if _SHELL_META_RE.search(argument) is not None:
                raise ValueError("installed-help argv must not contain shell syntax")
        if len(value) == 1:
            if value[0] not in _HELP_TOKENS:
                raise ValueError("installed-help argv must use a canonical help form")
            return value
        if len(value) != 2:
            raise ValueError("installed-help argv must be a help token with at most one subcommand")
        first, second = value
        flag_form = (
            first not in _HELP_TOKENS
            and _HELP_SUBCOMMAND_RE.fullmatch(first) is not None
            and second in _HELP_FLAG_TOKENS
        )
        word_form = (
            first == _HELP_WORD_TOKEN
            and second not in _HELP_TOKENS
            and _HELP_SUBCOMMAND_RE.fullmatch(second) is not None
        )
        if not flag_form and not word_form:
            raise ValueError("installed-help argv must use canonical help token ordering")
        return value

    @model_validator(mode="after")
    def _validate_kind_specific_capture(self) -> Self:
        documentation_fields = ("url", "documentation_proof")
        package_fields = ("url", "recipe_revision", "recipe_path")
        upstream_fields = ("url", "commit", "source_path")
        installed_fields = ("environment_digest", "executable_probe_id", "argv", "output_sha256")
        all_specific_fields = {
            "url",
            "documentation_proof",
            "recipe_revision",
            "recipe_path",
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

        if self.kind in (SourceKind.OFFICIAL_MANUAL, SourceKind.OFFICIAL_API_SCHEMA):
            assert self.url is not None and self.documentation_proof is not None
            proof = self.documentation_proof
            if self.content_format not in _DOCUMENTATION_PROOF_LOCATOR_FORMATS[type(proof.locator)]:
                raise ValueError("documentation proof locator is not supported for the source content format")
            if (
                proof.tool_id != self.tool_id
                or proof.tool_version != self.tool_version
                or proof.source_url != self.url
                or proof.source_content_sha256 != self.content_sha256
            ):
                raise ValueError("documentation proof must match the enclosing source exactly")
        elif self.kind is SourceKind.UPSTREAM_SOURCE:
            assert self.url is not None and self.commit is not None and self.source_path is not None
            if self.symbol_locator is not None and self.content_format is not SourceContentFormat.SOURCE_CODE:
                raise ValueError("upstream symbol locator requires source-code content")
            if not _url_path_ends_with(self.url, self.commit, *self.source_path.split("/")):
                raise ValueError("upstream URL must bind the exact commit and source path")
        elif self.kind is SourceKind.PACKAGE_RECIPE:
            assert self.url is not None and self.recipe_revision is not None and self.recipe_path is not None
            if not _url_path_ends_with(self.url, self.recipe_revision, *self.recipe_path.split("/")):
                raise ValueError("package recipe URL must bind its exact revision and recipe path")
        elif self.output_sha256 != self.content_sha256:
            raise ValueError("installed-help output digest must equal the captured content digest")
        return self


def _source_provenance(captured: EvidenceSource) -> tuple[object, ...]:
    return (
        captured.tool_id,
        captured.kind,
        captured.tool_version,
        captured.content_format,
        captured.url,
        captured.recipe_revision,
        captured.recipe_path,
        captured.commit,
        captured.source_path,
        captured.symbol_locator,
        captured.environment_digest,
        captured.executable_probe_id,
        captured.argv,
    )


def _documentation_proof_provenance(proof: DocumentationVersionProof) -> tuple[object, ...]:
    return (
        proof.source_url,
        proof.source_content_sha256,
        proof.proof_kind,
        proof.locator,
    )


class EvidenceClaim(_StrictFrozenModel):
    claim_id: ArtifactId
    contract_pointer: JsonPointer
    source_id: ArtifactId
    locator: ContentLocator
    statement: RetainedText
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


def verify_evidence_claim_content(
    claim: EvidenceClaim,
    *,
    source_content: bytes,
    expected_contract_pointer: str,
    contract_value: object,
    symbol_selector: Callable[[bytes, str], bytes] | None = None,
) -> EvidenceClaim:
    """Recompute a claim excerpt and contract value from compiler-owned data.

    Byte ranges and JSON pointers are resolved here. Symbol claims require a
    trusted language-aware selector, which is invoked with the exact captured
    bytes and canonical symbol identity. The compiler resolves the expected
    pointer against its authoritative contract projection and supplies that
    selected JSON value.
    """

    validated = EvidenceClaim.model_validate(claim)
    if validated.contract_pointer != _validate_json_pointer(expected_contract_pointer):
        raise ValueError("claim contract pointer does not match the compiler-resolved contract pointer")
    if type(source_content) is not bytes:
        raise TypeError("claim source content must be exact captured bytes")
    source_digest = "sha256:" + hashlib.sha256(source_content).hexdigest()
    if source_digest != validated.source_content_sha256:
        raise ValueError("claim source content digest does not match captured bytes")

    locator = validated.locator
    if isinstance(locator, ByteRangeLocator):
        if locator.end_byte_exclusive > len(source_content):
            raise ValueError("claim locator exceeds captured source content")
        selected_content = source_content[locator.start_byte : locator.end_byte_exclusive]
    elif isinstance(locator, JsonPointerLocator):
        document = _load_strict_json(source_content, label="claim source content")
        selected = _resolve_json_pointer(document, locator.pointer, label="claim locator")
        selected_content = _canonical_json_bytes(selected, label="claim selected value")
    else:
        if symbol_selector is None:
            raise ValueError("symbol claim requires a trusted language-aware symbol selector")
        selected_content = symbol_selector(source_content, locator.symbol)
        if type(selected_content) is not bytes:
            raise TypeError("trusted symbol selector must return exact bytes")

    selected_digest = "sha256:" + hashlib.sha256(selected_content).hexdigest()
    if selected_digest != validated.excerpt_sha256:
        raise ValueError("claim excerpt digest does not match selected source content")

    contract_content = _canonical_json_bytes(
        contract_value,
        label="compiler-resolved contract value",
    )
    contract_digest = "sha256:" + hashlib.sha256(contract_content).hexdigest()
    if contract_digest != validated.contract_value_sha256:
        raise ValueError("claim contract value digest does not match the compiler-resolved contract value")
    return validated


class VerificationKind(StrEnum):
    INVENTORY = "inventory"
    EVIDENCE_COVERAGE = "evidence_coverage"
    CONTRACT_COMPILE = "contract_compile"
    COMMAND_FIXTURE = "command_fixture"
    ENVIRONMENT_PROBE = "environment_probe"
    TOOL_SMOKE = "tool_smoke"
    CLOUD_RUN = "cloud_run"
    WORKFLOW_RUN = "workflow_run"


class VerificationOutcome(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class FailureCode(StrEnum):
    INVENTORY_MISSING = "inventory_missing"
    EVIDENCE_MISSING = "evidence_missing"
    EVIDENCE_CONFLICT = "evidence_conflict"
    CONTRACT_INVALID = "contract_invalid"
    COMMAND_FIXTURE_FAILED = "command_fixture_failed"
    ENVIRONMENT_RESOLUTION_FAILED = "environment_resolution_failed"
    TOOL_SMOKE_FAILED = "tool_smoke_failed"
    CLOUD_RUN_FAILED = "cloud_run_failed"
    WORKFLOW_RUN_FAILED = "workflow_run_failed"


_VERIFICATION_FAILURE_CODES = {
    VerificationKind.INVENTORY: frozenset({FailureCode.INVENTORY_MISSING}),
    VerificationKind.EVIDENCE_COVERAGE: frozenset({FailureCode.EVIDENCE_MISSING, FailureCode.EVIDENCE_CONFLICT}),
    VerificationKind.CONTRACT_COMPILE: frozenset({FailureCode.CONTRACT_INVALID}),
    VerificationKind.COMMAND_FIXTURE: frozenset({FailureCode.COMMAND_FIXTURE_FAILED}),
    VerificationKind.ENVIRONMENT_PROBE: frozenset({FailureCode.ENVIRONMENT_RESOLUTION_FAILED}),
    VerificationKind.TOOL_SMOKE: frozenset({FailureCode.TOOL_SMOKE_FAILED}),
    VerificationKind.CLOUD_RUN: frozenset({FailureCode.CLOUD_RUN_FAILED}),
    VerificationKind.WORKFLOW_RUN: frozenset({FailureCode.WORKFLOW_RUN_FAILED}),
}

_VERIFICATION_UI_LABELS = {
    VerificationKind.INVENTORY: "Inventory verification",
    VerificationKind.EVIDENCE_COVERAGE: "Evidence verification",
    VerificationKind.CONTRACT_COMPILE: "Contract verification",
    VerificationKind.COMMAND_FIXTURE: "Command verification",
    VerificationKind.ENVIRONMENT_PROBE: "Environment verification",
    VerificationKind.TOOL_SMOKE: "Tool smoke verification",
    VerificationKind.CLOUD_RUN: "Cloud verification",
    VerificationKind.WORKFLOW_RUN: "Workflow verification",
}

_VERIFICATION_REQUIRED_CONTEXT = {
    VerificationKind.INVENTORY: frozenset({"catalog_sha256"}),
    VerificationKind.EVIDENCE_COVERAGE: frozenset({"catalog_sha256"}),
    VerificationKind.CONTRACT_COMPILE: frozenset({"catalog_sha256"}),
    VerificationKind.COMMAND_FIXTURE: frozenset(
        {"fixture_id", "fixture_sha256", "environment_sha256", "catalog_sha256"}
    ),
    VerificationKind.ENVIRONMENT_PROBE: frozenset({"environment_sha256", "catalog_sha256", "platform_sha256"}),
    VerificationKind.TOOL_SMOKE: frozenset(
        {"fixture_id", "fixture_sha256", "environment_sha256", "catalog_sha256", "platform_sha256"}
    ),
    VerificationKind.CLOUD_RUN: frozenset(
        {
            "fixture_id",
            "fixture_sha256",
            "environment_sha256",
            "catalog_sha256",
            "platform_sha256",
            "release_sha256",
        }
    ),
    VerificationKind.WORKFLOW_RUN: frozenset(
        {
            "fixture_id",
            "fixture_sha256",
            "environment_sha256",
            "catalog_sha256",
            "platform_sha256",
            "release_sha256",
        }
    ),
}

_VERIFICATION_ALLOWED_CONTEXT = {
    VerificationKind.INVENTORY: frozenset({"catalog_sha256"}),
    VerificationKind.EVIDENCE_COVERAGE: frozenset({"catalog_sha256"}),
    VerificationKind.CONTRACT_COMPILE: frozenset({"catalog_sha256"}),
    VerificationKind.COMMAND_FIXTURE: frozenset(
        {"fixture_id", "fixture_sha256", "environment_sha256", "catalog_sha256", "platform_sha256"}
    ),
    VerificationKind.ENVIRONMENT_PROBE: frozenset({"environment_sha256", "catalog_sha256", "platform_sha256"}),
    VerificationKind.TOOL_SMOKE: frozenset(
        {"fixture_id", "fixture_sha256", "environment_sha256", "catalog_sha256", "platform_sha256"}
    ),
    VerificationKind.CLOUD_RUN: _VERIFICATION_REQUIRED_CONTEXT[VerificationKind.CLOUD_RUN],
    VerificationKind.WORKFLOW_RUN: _VERIFICATION_REQUIRED_CONTEXT[VerificationKind.WORKFLOW_RUN],
}

_FAILURE_UI_REASONS = {
    FailureCode.INVENTORY_MISSING: "Inventory evidence is missing",
    FailureCode.EVIDENCE_MISSING: "Required authoritative evidence is missing",
    FailureCode.EVIDENCE_CONFLICT: "Authoritative evidence contains a conflict",
    FailureCode.CONTRACT_INVALID: "Typed contract verification failed",
    FailureCode.COMMAND_FIXTURE_FAILED: "Command fixture verification failed",
    FailureCode.ENVIRONMENT_RESOLUTION_FAILED: "Environment resolution verification failed",
    FailureCode.TOOL_SMOKE_FAILED: "Pinned tool smoke verification failed",
    FailureCode.CLOUD_RUN_FAILED: "Cloud run verification failed",
    FailureCode.WORKFLOW_RUN_FAILED: "Workflow verification failed",
}


def failure_code_ui_reason(code: FailureCode) -> str:
    return _FAILURE_UI_REASONS[code]


class VerificationEvidence(_StrictFrozenModel):
    evidence_id: ArtifactId
    tool_id: ArtifactId
    tool_version: ExactVersion
    kind: VerificationKind
    outcome: VerificationOutcome
    failure_code: FailureCode | None = None
    test_id: ArtifactId
    result_sha256: Sha256Digest
    fixture_id: ArtifactId | None = None
    fixture_sha256: Sha256Digest | None = None
    environment_sha256: Sha256Digest | None = None
    catalog_sha256: Sha256Digest | None = None
    platform_sha256: Sha256Digest | None = None
    release_sha256: Sha256Digest | None = None
    verified_at: date
    verifier_id: ArtifactId
    verifier_version: ExactVersion

    @field_validator("evidence_id", "tool_id", "test_id", "fixture_id", "verifier_id")
    @classmethod
    def _validate_ids(cls, value: str | None, info: object) -> str | None:
        if value is None:
            return None
        label = getattr(info, "field_name", "ID").replace("_", " ")
        return _validate_bounded_id(value, label=label)

    @field_validator("tool_version", "verifier_version")
    @classmethod
    def _validate_verifier_version(cls, value: str) -> str:
        return _validate_exact_version(value)

    @model_validator(mode="after")
    def _validate_result(self) -> Self:
        context = {
            "fixture_id": self.fixture_id,
            "fixture_sha256": self.fixture_sha256,
            "environment_sha256": self.environment_sha256,
            "catalog_sha256": self.catalog_sha256,
            "platform_sha256": self.platform_sha256,
            "release_sha256": self.release_sha256,
        }
        missing = tuple(sorted(field for field in _VERIFICATION_REQUIRED_CONTEXT[self.kind] if context[field] is None))
        if missing:
            raise ValueError(f"{self.kind.value} verification is missing required context: {', '.join(missing)}")
        irrelevant = tuple(
            sorted(
                field
                for field, value in context.items()
                if value is not None and field not in _VERIFICATION_ALLOWED_CONTEXT[self.kind]
            )
        )
        if irrelevant:
            raise ValueError(f"{self.kind.value} verification has irrelevant context: {', '.join(irrelevant)}")
        if (self.fixture_id is None) != (self.fixture_sha256 is None):
            raise ValueError("fixture ID and digest must be supplied together")
        if self.outcome is VerificationOutcome.PASSED:
            if self.failure_code is not None:
                raise ValueError("passed verification must not declare a failure code")
        elif self.failure_code is None:
            raise ValueError("failed verification requires a failure code")
        elif self.failure_code not in _VERIFICATION_FAILURE_CODES[self.kind]:
            raise ValueError("verification failure code is not valid for its kind")
        return self

    def verification_digest(self) -> str:
        return _canonical_digest(self)

    @property
    def ui_summary(self) -> str:
        suffix = "passed" if self.outcome is VerificationOutcome.PASSED else "failed"
        return f"{_VERIFICATION_UI_LABELS[self.kind]} {suffix}"

    @property
    def ui_reason(self) -> str | None:
        return None if self.failure_code is None else failure_code_ui_reason(self.failure_code)


def _verification_provenance(captured: VerificationEvidence) -> tuple[object, ...]:
    return (
        captured.tool_id,
        captured.tool_version,
        captured.kind,
        captured.test_id,
        captured.fixture_id,
        captured.fixture_sha256,
        captured.environment_sha256,
        captured.catalog_sha256,
        captured.platform_sha256,
        captured.release_sha256,
        captured.verifier_id,
        captured.verifier_version,
    )


class EvidenceRecord(_StrictFrozenModel):
    schema_version: Literal[2]
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
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("source IDs must be unique")
        source_order = tuple((_SOURCE_KIND_PRECEDENCE[item.kind], item.source_id) for item in self.sources)
        if source_order != tuple(sorted(source_order)):
            raise ValueError("source captures must use authoritative kind precedence then source ID")
        _validate_unique_ordered(claim_ids, label="claim IDs")
        _validate_unique_ordered(verification_ids, label="verification evidence IDs")

        sources_by_id = {item.source_id: item for item in self.sources}
        source_contents: dict[tuple[object, ...], str] = {}
        proof_results: dict[tuple[object, ...], str] = {}
        document_bindings: dict[tuple[str, str], tuple[str, str]] = {}
        for captured in self.sources:
            if captured.tool_id != self.tool_id:
                raise ValueError("source tool ID must equal the evidence record tool ID")
            if captured.tool_version != self.tool_version:
                raise ValueError("source tool version must equal the evidence record tool version")
            provenance = _source_provenance(captured)
            if provenance in source_contents:
                if source_contents[provenance] == captured.content_sha256:
                    raise ValueError("duplicate source capture provenance")
                raise ValueError("conflicting source capture content for one provenance")
            source_contents[provenance] = captured.content_sha256

            proof = captured.documentation_proof
            if proof is None:
                continue
            document_key = (proof.source_url, proof.source_content_sha256)
            binding = (proof.tool_id, proof.tool_version)
            prior_binding = document_bindings.get(document_key)
            if prior_binding is not None and prior_binding != binding:
                raise ValueError("documentation content has conflicting tool/version bindings")
            document_bindings[document_key] = binding
            proof_key = _documentation_proof_provenance(proof)
            prior_proof = proof_results.get(proof_key)
            if prior_proof is not None:
                if prior_proof == proof.proof_content_sha256:
                    raise ValueError("duplicate documentation proof provenance")
                raise ValueError("conflicting documentation proof content for one provenance")
            proof_results[proof_key] = proof.proof_content_sha256

        verification_results: dict[tuple[object, ...], tuple[VerificationOutcome, FailureCode | None, str]] = {}
        for captured in self.verifications:
            if captured.tool_id != self.tool_id or captured.tool_version != self.tool_version:
                raise ValueError("verification tool ID and version must equal the evidence record tool")
            provenance = _verification_provenance(captured)
            result = (captured.outcome, captured.failure_code, captured.result_sha256)
            if provenance in verification_results:
                if verification_results[provenance] == result:
                    raise ValueError("duplicate verification capture provenance")
                raise ValueError("conflicting verification capture result for one provenance")
            verification_results[provenance] = result

        bindings: set[tuple[object, ...]] = set()
        pointer_sources: set[tuple[str, str]] = set()
        pointer_values: dict[str, str] = {}
        for asserted in self.claims:
            captured = sources_by_id.get(asserted.source_id)
            if captured is None:
                raise ValueError(f"claim {asserted.claim_id} references missing source {asserted.source_id}")
            if asserted.source_content_sha256 != captured.content_sha256:
                raise ValueError(f"claim {asserted.claim_id} source content digest does not match its source")
            if captured.content_format not in _CLAIM_LOCATOR_FORMATS[type(asserted.locator)]:
                raise ValueError("claim locator kind is not supported for the captured content format")
            if isinstance(asserted.locator, SymbolLocator) and (
                captured.kind is not SourceKind.UPSTREAM_SOURCE or asserted.locator.symbol != captured.symbol_locator
            ):
                raise ValueError("symbol claim locator requires upstream source with the exact source symbol")
            if captured.kind is SourceKind.PACKAGE_RECIPE:
                pointer_segments = _decode_json_pointer(asserted.contract_pointer)
                if pointer_segments[:2] != ("environment", "packages"):
                    raise ValueError("package recipe claims must target /environment/packages")
            prior_value = pointer_values.get(asserted.contract_pointer)
            if prior_value is not None and prior_value != asserted.contract_value_sha256:
                raise ValueError("claims for one contract pointer have conflicting contract values")
            pointer_values[asserted.contract_pointer] = asserted.contract_value_sha256
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
    "ByteRangeLocator",
    "ContentLocator",
    "ContentLocatorKind",
    "DocumentationProofKind",
    "DocumentationProofLocator",
    "DocumentationVersionProof",
    "EvidenceClaim",
    "EvidenceRecord",
    "EvidenceSource",
    "FailureCode",
    "JsonPointerLocator",
    "RetainedText",
    "RetainedTextOrigin",
    "RetainedTextProvenance",
    "SourceContentFormat",
    "SourceKind",
    "SymbolLocator",
    "VerificationEvidence",
    "VerificationKind",
    "VerificationOutcome",
    "failure_code_ui_reason",
    "verify_documentation_proof_content",
    "verify_evidence_claim_content",
    "verify_retained_text_selection",
]
