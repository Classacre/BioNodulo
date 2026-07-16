"""Immutable authoritative source and retained verification evidence."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
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
_SOURCE_PATH_SEGMENT_RE = re.compile(r"^[0-9A-Za-z._+-]+$")
_SYMBOL_LOCATOR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:-]{0,255}$")
_SHELL_META_RE = re.compile(r"[;&|`$<>]")
_SECRET_ASSIGNMENT_HEAD_RE = re.compile(
    r"(?i)(?<![0-9A-Za-z_.-])(?:--)?(?P<quote>[\"']?)(?P<key>[A-Za-z][A-Za-z0-9_.-]{0,127})"
    r"(?P=quote)\s*[:=]\s*"
)
_SECRET_OPTION_HEAD_RE = re.compile(
    r"(?i)(?<![0-9A-Za-z_.-])(?P<tick>`?)--"
    r"(?P<key>[A-Za-z](?:[A-Za-z0-9_.-]{0,126}[A-Za-z0-9])?)\s*(?:=\s*|\s+)"
)
_SECRET_PROSE_KEY = (
    r"(?:api[ _-]+key|access[ _-]+key|client[ _-]+secret|private[ _-]+key|"
    r"license[ _-]+key|password|passwd|pwd|token|secret|credentials?|auth(?:entication|orization)?)"
)
_SECRET_LINK_HEAD_RE = re.compile(
    rf"(?i)(?<![0-9A-Za-z_.-])(?:the\s+)?{_SECRET_PROSE_KEY}"
    r"(?:\s+(?:value|argument|parameter))?\s+(?:is|was|are|were)\s+"
)
_SECRET_ACTION_HEAD_RE = re.compile(
    rf"(?i)(?<![0-9A-Za-z_.-])"
    r"(?:use|set|pass|provide|send|enter|supply|include|add|configure|specify|export)\s+"
    rf"(?:the\s+)?{_SECRET_PROSE_KEY}(?:\s+(?:value|argument|parameter))?\s+"
)
_AUTHORIZATION_SCHEME_RE = re.compile(
    r"(?i)(?<![0-9A-Za-z._~/\\-])authorization(?:\s+header)?\s*(?::|=)?\s*(?:bearer|basic)\s+"
)
_URL_USERINFO_RE = re.compile(r"(?i)(?:[A-Za-z][A-Za-z0-9+.-]*:)?//[^/\s?#]*@")
_REDACTED_SECRET_VALUES = frozenset({"<TOKEN>", "${TOKEN}", "[REDACTED]", "REDACTED", "***"})
_REDACTION_TRAILING_PUNCTUATION = ".,;:!?)]}"
_CREDENTIAL_TOKEN_RE = re.compile(
    r"(?i)(?<![0-9A-Za-z])(?:"
    r"(?:akia|asia)[0-9A-Z]{12,}"
    r"|(?:live|secret|token|password)[-_][0-9A-Za-z][0-9A-Za-z._+-]*"
    r"|sk-[0-9A-Za-z][0-9A-Za-z._+-]*"
    r"|gh[pousr]_[0-9A-Za-z][0-9A-Za-z_-]*"
    r"|xox[a-z]-[0-9A-Za-z][0-9A-Za-z-]*"
    r"|eyJ[0-9A-Za-z_-]{8,}"
    r"|hunter[0-9]+"
    r")(?![0-9A-Za-z])"
)
_SAFE_SECRET_STATE_WORDS = frozenset(
    {"configured", "documented", "provided", "redacted", "required", "supplied", "unavailable", "unset"}
)
_CAPTURE_PATH_BOUNDARY = r"(?<![0-9A-Za-z._~/\\-])"
_CAPTURE_HOST_PATH_RES = (
    re.compile(r"file://[^/\\\s]+/(?:home|Users)/[^/\\\s\"'`]+", re.IGNORECASE),
    re.compile(
        r"file://[^/\\\s]+/root(?=$|[/\\\s.,;:!?\"'`)\]}])",
        re.IGNORECASE,
    ),
    re.compile(
        _CAPTURE_PATH_BOUNDARY + r"file://(?:localhost|127\.0\.0\.1)/(?:home|Users)/[^/\\\s\"'`]+",
        re.IGNORECASE,
    ),
    re.compile(
        _CAPTURE_PATH_BOUNDARY + r"(?:file://)?/(?:home|Users)/[^/\\\s\"'`]+",
        re.IGNORECASE,
    ),
    re.compile(
        _CAPTURE_PATH_BOUNDARY + r"(?:file://)?/root(?=$|[/\\\s.,;:!?\"'`)\]}])",
        re.IGNORECASE,
    ),
    re.compile(
        _CAPTURE_PATH_BOUNDARY
        + r"(?:(?:file:///)?[A-Za-z]:[\\/]|/mnt/[A-Za-z]/)(?:Users|Documents and Settings)[\\/]"
        + r"[^/\\\s\"'`]+",
        re.IGNORECASE,
    ),
    re.compile(
        _CAPTURE_PATH_BOUNDARY + r"(?:\\\\|//)[^/\\\s]+[\\/](?:Users|Documents and Settings)[\\/]" + r"[^/\\\s\"'`]+",
        re.IGNORECASE,
    ),
    re.compile(
        _CAPTURE_PATH_BOUNDARY
        + r"(?:(?:file://)?/|[A-Za-z]:[\\/])[^\s\"'`]*?[\\/]pytest-of-[^/\\\s\"'`]+[\\/]"
        + r"pytest-(?:[0-9]+|current)(?=$|[/\\\s.,;:!?\"'`)\]}])",
        re.IGNORECASE,
    ),
)
_MOVING_DOCUMENT_SEGMENTS = frozenset(
    {"latest", "stable", "current", "main", "master", "head", "develop", "release", "trunk"}
)
_MOVING_DOCUMENT_TOKEN_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9])(?:latest|stable|current|main|master|head|develop|release|trunk)(?![A-Za-z0-9])"
)
_DOCUMENT_VERSION_BODY = (
    r"[0-9]+\.[0-9]+(?:\.[0-9]+)*"
    r"(?:[A-Za-z][0-9A-Za-z._+-]*|[._+-][0-9A-Za-z][0-9A-Za-z._+-]*)?"
)
_DOCUMENT_VERSION_SCAN_RE = re.compile(
    rf"(?<![0-9A-Za-z])v?{_DOCUMENT_VERSION_BODY}(?![0-9A-Za-z])",
    re.IGNORECASE,
)
_IGNORED_DOCUMENT_VERSION_CONTEXT_RE = re.compile(
    r"(?:^|[^0-9A-Za-z])(?:api|section)[\s:/_-]*$",
    re.IGNORECASE,
)
_DOCUMENT_FILE_EXTENSIONS = (".html", ".htm", ".json", ".yaml", ".yml", ".xml", ".txt")
_HELP_FLAG_TOKENS = frozenset({"--help", "-h", "-help"})
_HELP_WORD_TOKEN = "help"
_HELP_TOKENS = frozenset({*_HELP_FLAG_TOKENS, _HELP_WORD_TOKEN})
_HELP_SUBCOMMAND_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
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


def _validate_printable_unicode(value: str, *, label: str) -> str:
    for character in value:
        category = unicodedata.category(character)
        if category.startswith("C") or category in ("Zl", "Zp"):
            raise ValueError(f"{label} must contain only printable Unicode characters")
    return value


def _is_secret_assignment_key(value: str) -> bool:
    compact = value.casefold().replace("_", "").replace("-", "").replace(".", "")
    return compact in {"auth", "authentication", "authorization", "credential", "credentials"} or compact.endswith(
        (
            "token",
            "secret",
            "password",
            "passwd",
            "pwd",
            "apikey",
            "authkey",
            "secretkey",
            "privatekey",
            "refreshkey",
            "licensekey",
            "accesskey",
            "accesskeyid",
        )
    )


def _assignment_value(value: str, start: int) -> tuple[str, bool, str]:
    if start >= len(value):
        return "", False, ""
    if value[start] in ('"', "'"):
        quote = value[start]
        end = value.find(quote, start + 1)
        if end < 0:
            return value[start:], True, ""
        suffix_end = end + 1
        while suffix_end < len(value) and not value[suffix_end].isspace() and value[suffix_end] not in "&,;#":
            suffix_end += 1
        remainder_start = suffix_end
        while remainder_start < len(value) and value[remainder_start].isspace():
            remainder_start += 1
        remainder_end = remainder_start
        while remainder_end < len(value) and value[remainder_end] not in "&,;#":
            remainder_end += 1
        return (
            value[start + 1 : end] + value[end + 1 : suffix_end],
            True,
            value[remainder_start:remainder_end].strip(),
        )
    end = start
    while end < len(value) and value[end] not in "&,;#":
        end += 1
    raw = value[start:end].strip()
    parts = raw.split(maxsplit=1)
    return (parts[0], False, parts[1] if len(parts) > 1 else "") if parts else ("", False, "")


def _looks_like_credential_token(value: str) -> bool:
    token = value.strip("\"'`()[]{}<>,.;:!?")
    if not token:
        return False
    folded = token.casefold()
    if folded in {"credential", "password", "secret", "token"}:
        return True
    if folded.startswith(("akia", "asia", "eyj", "ghp_", "live-", "live_", "sk-", "xox")):
        return True
    if any(character.isdigit() for character in token) and any(character.isalpha() for character in token):
        return True
    if any(character in "-_/+=" for character in token):
        return True
    if len(token) >= 16 or sum(character.isupper() for character in token) > 1:
        return True
    return False


def _is_redaction_token(value: str) -> bool:
    candidate = value.strip("\"'`().,;:!?")
    return candidate in _REDACTED_SECRET_VALUES


def _contains_credential_indicator(value: str) -> bool:
    for token in value.split():
        if _is_redaction_token(token):
            continue
        if _CREDENTIAL_TOKEN_RE.search(token) is not None or _looks_like_credential_token(token):
            return True
    return False


def _secret_tail(value: str, start: int, *, backticked: bool = False) -> str:
    end = value.find("`", start) if backticked else -1
    return value[start : end if end >= 0 else len(value)].strip()


def _is_redacted_secret_tail(value: str) -> bool:
    if _is_redacted_secret(value):
        return True
    first, _, remainder = value.partition(" ")
    return _is_redaction_token(first) and len(remainder.split()) >= 3 and not _contains_credential_indicator(remainder)


def _is_redacted_secret(value: str) -> bool:
    candidate = value.strip()
    for redaction in _REDACTED_SECRET_VALUES:
        if candidate == redaction:
            return True
        if not candidate.startswith(redaction):
            continue
        suffix = candidate[len(redaction) :]
        punctuation_length = 0
        while punctuation_length < len(suffix) and suffix[punctuation_length] in _REDACTION_TRAILING_PUNCTUATION:
            punctuation_length += 1
        if not punctuation_length:
            continue
        if punctuation_length == len(suffix):
            return True
        if not suffix[punctuation_length].isspace():
            continue
        prose = suffix[punctuation_length:].strip()
        prose_tokens = prose.split()
        if len(prose_tokens) > 1 and not _contains_credential_indicator(prose):
            return True
    return False


def _validate_retained_secrets(value: str, *, label: str) -> None:
    for match in _SECRET_ASSIGNMENT_HEAD_RE.finditer(value):
        key = match.group("key")
        if not _is_secret_assignment_key(key):
            continue
        retained, quoted, remainder = _assignment_value(value, match.end())
        if not quoted and remainder:
            retained = f"{retained} {remainder}".strip()
        if key.casefold().replace("_", "").replace("-", "").replace(".", "") == "authorization":
            parts = retained.split()
            if parts and parts[0].casefold() in ("bearer", "basic"):
                if quoted:
                    retained = " ".join((*parts[1:], remainder)).strip()
                else:
                    retained = " ".join(parts[1:]) if len(parts) > 1 else ""
            elif parts:
                retained = " ".join((retained, remainder)).strip() if quoted else retained
        elif quoted and remainder:
            retained = f"{retained} {remainder}".strip()
        if retained and not _is_redacted_secret(retained):
            raise ValueError(f"{label} must not retain secret values")

    for match in _SECRET_OPTION_HEAD_RE.finditer(value):
        key = match.group("key")
        if not _is_secret_assignment_key(key):
            continue
        retained = _secret_tail(value, match.end(), backticked=bool(match.group("tick")))
        if not retained or _is_redacted_secret_tail(retained):
            continue
        raise ValueError(f"{label} must not retain secret values")

    for match in _SECRET_ACTION_HEAD_RE.finditer(value):
        retained = _secret_tail(value, match.end())
        if not retained or _is_redacted_secret_tail(retained):
            continue
        raise ValueError(f"{label} must not retain secret values")

    for match in _SECRET_LINK_HEAD_RE.finditer(value):
        retained = _secret_tail(value, match.end())
        if not retained or _is_redacted_secret_tail(retained):
            continue
        first, _, remainder = retained.partition(" ")
        state = first.strip("\"'`()[]{}<>,.;:!?").casefold()
        if state in _SAFE_SECRET_STATE_WORDS and not _contains_credential_indicator(remainder):
            continue
        raise ValueError(f"{label} must not retain secret values")

    for match in _AUTHORIZATION_SCHEME_RE.finditer(value):
        retained = _secret_tail(value, match.end())
        if not _is_redacted_secret(retained):
            raise ValueError(f"{label} must not retain secret values")


def _validate_retained_text(value: str, *, label: str) -> str:
    if value != value.strip():
        raise ValueError(f"{label} must not have outer whitespace")
    _validate_printable_unicode(value, label=label)
    _validate_retained_secrets(value, label=label)
    if _URL_USERINFO_RE.search(value) is not None:
        raise ValueError(f"{label} must not retain URL userinfo credentials")
    for pattern in _CAPTURE_HOST_PATH_RES:
        for match in pattern.finditer(value):
            captured_path = match.group(0).replace("\\", "/").rstrip(_REDACTION_TRAILING_PUNCTUATION)
            if not captured_path.endswith("/<USER>"):
                raise ValueError(f"{label} must not retain capture host paths")
    return value


def _normalized_document_version(value: str) -> str:
    return value[1:] if value[:1].casefold() == "v" else value


def _tool_adjacent_document_versions(value: str, *, tool_id: str) -> tuple[str, ...]:
    pattern = re.compile(
        rf"(?i)(?<![0-9A-Za-z]){re.escape(tool_id)}[._-]?v?"
        rf"(?P<version>{_DOCUMENT_VERSION_BODY})(?![0-9A-Za-z])"
    )
    return tuple(match.group("version") for match in pattern.finditer(value))


def _validate_official_documentation_binding(
    *,
    tool_id: str,
    tool_version: str,
    url: str,
    version_locator: str,
) -> None:
    path_segments = tuple(segment for segment in urlsplit(url).path.split("/") if segment)
    path_candidates: list[str] = []
    for segment in path_segments:
        lowered = segment.casefold()
        stem = lowered.rsplit(".", 1)[0]
        if lowered in _MOVING_DOCUMENT_SEGMENTS or stem in _MOVING_DOCUMENT_SEGMENTS:
            raise ValueError("official documentation URL must not use moving revision segments")
        candidate = segment
        for extension in _DOCUMENT_FILE_EXTENSIONS:
            if lowered.endswith(extension):
                candidate = segment[: -len(extension)]
                break
        path_candidates.append(candidate)

    path_bound = False
    for index, candidate in enumerate(path_candidates):
        for match in _DOCUMENT_VERSION_SCAN_RE.finditer(candidate):
            normalized = _normalized_document_version(match.group(0))
            if normalized == tool_version:
                path_bound = True
            elif index > 0 and path_candidates[index - 1].casefold() == tool_id.casefold():
                raise ValueError("official documentation URL must bind the exact tool version")
        for normalized in _tool_adjacent_document_versions(candidate, tool_id=tool_id):
            if normalized != tool_version:
                raise ValueError("official documentation URL must bind the exact tool version")
            path_bound = True

    if _MOVING_DOCUMENT_TOKEN_RE.search(version_locator) is not None:
        raise ValueError("official documentation version locator must not use moving revisions")
    locator_bound = False
    for match in _DOCUMENT_VERSION_SCAN_RE.finditer(version_locator):
        normalized = _normalized_document_version(match.group(0))
        if normalized == tool_version:
            locator_bound = True
        elif _IGNORED_DOCUMENT_VERSION_CONTEXT_RE.search(version_locator[: match.start()]) is None:
            raise ValueError("official documentation version locator must bind the exact tool version")
    for normalized in _tool_adjacent_document_versions(version_locator, tool_id=tool_id):
        if normalized != tool_version:
            raise ValueError("official documentation version locator must bind the exact tool version")
        locator_bound = True
    if not locator_bound and not path_bound:
        raise ValueError("official documentation must bind the exact tool version")


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


def _decode_json_pointer(value: str) -> tuple[str, ...]:
    return tuple(segment.replace("~1", "/").replace("~0", "~") for segment in value[1:].split("/"))


def _validate_json_pointer(value: str) -> str:
    _validate_printable_unicode(value, label="contract pointer")
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


_SOURCE_KIND_PRECEDENCE = {kind: index for index, kind in enumerate(SourceKind)}


class EvidenceSource(_StrictFrozenModel):
    source_id: ArtifactId
    tool_id: ArtifactId
    kind: SourceKind
    tool_version: ExactVersion
    retrieved_at: date
    content_sha256: Sha256Digest
    title: Title
    description: Description
    url: Annotated[str, StringConstraints(min_length=1, max_length=2048)] | None = None
    version_locator: VersionLocator | None = None
    recipe_revision: RecipeRevision | None = None
    recipe_path: RepositoryPath | None = None
    commit: Annotated[str, StringConstraints(min_length=40, max_length=64)] | None = None
    source_path: RepositoryPath | None = None
    symbol_locator: SymbolLocator | None = None
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

    @field_validator("title", "description", "version_locator")
    @classmethod
    def _validate_human_text(cls, value: str | None, info: object) -> str | None:
        if value is None:
            return None
        label = getattr(info, "field_name", "text").replace("_", " ")
        return _validate_retained_text(value, label=label)

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if _URL_USERINFO_RE.search(value) is not None:
            raise ValueError("URL must not contain userinfo")
        return _validate_https_url(value, require_path=True)

    @field_validator("recipe_revision")
    @classmethod
    def _validate_recipe_revision(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if _GIT_COMMIT_RE.fullmatch(value) is None:
            raise ValueError("recipe revision must be an exact lowercase 40- or 64-hex Git object ID")
        return value

    @field_validator("commit")
    @classmethod
    def _validate_commit(cls, value: str | None) -> str | None:
        if value is not None and _GIT_COMMIT_RE.fullmatch(value) is None:
            raise ValueError("commit must be an exact lowercase 40- or 64-hex Git object ID")
        return value

    @field_validator("recipe_path", "source_path")
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
            _validate_retained_text(argument, label="installed-help argv")
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
        documentation_fields = ("url", "version_locator")
        package_fields = ("url", "recipe_revision", "recipe_path")
        upstream_fields = ("url", "commit", "source_path")
        installed_fields = ("environment_digest", "executable_probe_id", "argv", "output_sha256")
        all_specific_fields = {
            "url",
            "version_locator",
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
            assert self.url is not None and self.version_locator is not None
            _validate_official_documentation_binding(
                tool_id=self.tool_id,
                tool_version=self.tool_version,
                url=self.url,
                version_locator=self.version_locator,
            )
        elif self.kind is SourceKind.UPSTREAM_SOURCE:
            assert self.url is not None and self.commit is not None and self.source_path is not None
            pinned_suffix = f"/{self.commit}/{self.source_path}"
            if not urlsplit(self.url).path.endswith(pinned_suffix):
                raise ValueError("upstream URL must bind the exact commit and source path")
        elif self.kind is SourceKind.PACKAGE_RECIPE:
            assert self.url is not None and self.recipe_revision is not None and self.recipe_path is not None
            pinned_suffix = f"/{self.recipe_revision}/{self.recipe_path}"
            if not urlsplit(self.url).path.endswith(pinned_suffix):
                raise ValueError("package recipe URL must bind its exact revision and recipe path")
        elif self.kind is SourceKind.INSTALLED_HELP and self.output_sha256 != self.content_sha256:
            raise ValueError("installed-help output digest must equal the captured content digest")
        return self


def _source_provenance(captured: EvidenceSource) -> tuple[object, ...]:
    return (
        captured.tool_id,
        captured.kind,
        captured.tool_version,
        captured.url,
        captured.version_locator,
        captured.recipe_revision,
        captured.recipe_path,
        captured.commit,
        captured.source_path,
        captured.symbol_locator,
        captured.environment_digest,
        captured.executable_probe_id,
        captured.argv,
    )


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
        return _validate_retained_text(value, label=label)


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
        return _validate_retained_text(value, label="verification summary")

    @model_validator(mode="after")
    def _validate_fixture_identity(self) -> Self:
        if (self.fixture_id is None) != (self.fixture_sha256 is None):
            raise ValueError("fixture ID and digest must be supplied together")
        return self

    def verification_digest(self) -> str:
        return _canonical_digest(self)


def _verification_provenance(captured: VerificationEvidence) -> tuple[object, ...]:
    return (
        captured.kind,
        captured.test_id,
        captured.fixture_id,
        captured.fixture_sha256,
        captured.environment_sha256,
        captured.catalog_sha256,
        captured.platform_sha256,
        captured.release_sha256,
    )


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
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("source IDs must be unique")
        source_order = tuple((_SOURCE_KIND_PRECEDENCE[item.kind], item.source_id) for item in self.sources)
        if source_order != tuple(sorted(source_order)):
            raise ValueError("source captures must use authoritative kind precedence then source ID")
        _validate_unique_ordered(claim_ids, label="claim IDs")
        _validate_unique_ordered(verification_ids, label="verification evidence IDs")

        sources_by_id = {item.source_id: item for item in self.sources}
        source_contents: dict[tuple[object, ...], str] = {}
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

        verification_results: dict[tuple[object, ...], str] = {}
        for captured in self.verifications:
            provenance = _verification_provenance(captured)
            if provenance in verification_results:
                if verification_results[provenance] == captured.result_sha256:
                    raise ValueError("duplicate verification capture provenance")
                raise ValueError("conflicting verification capture result for one provenance")
            verification_results[provenance] = captured.result_sha256

        bindings: set[tuple[str, ...]] = set()
        pointer_sources: set[tuple[str, str]] = set()
        pointer_values: dict[str, str] = {}
        for asserted in self.claims:
            captured = sources_by_id.get(asserted.source_id)
            if captured is None:
                raise ValueError(f"claim {asserted.claim_id} references missing source {asserted.source_id}")
            if asserted.source_content_sha256 != captured.content_sha256:
                raise ValueError(f"claim {asserted.claim_id} source content digest does not match its source")
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
    "EvidenceClaim",
    "EvidenceRecord",
    "EvidenceSource",
    "SourceKind",
    "VerificationEvidence",
]
