"""Canonical generic package URLs as serialized by purl 0.1.6."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import unquote_to_bytes


# rattler_conda_types 0.46.0 aliases PackageUrl to GenericPurl<String>.
# Exact behavior is pinned by purl 0.1.6 src/{parse,format,builder,qualifiers}.rs.
_PACKAGE_TYPE = re.compile(r"^[A-Za-z][A-Za-z0-9.+-]*$")
_QUALIFIER_KEY = re.compile(r"^[A-Za-z0-9._-]+$")
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")

_PATH_BLOCKED = frozenset(' "#<>?`{}@%')
_NAME_BLOCKED = _PATH_BLOCKED | frozenset("/")
_QUALIFIER_BLOCKED = frozenset(' "#<>@?+%&')
_SUBPATH_BLOCKED = frozenset(' "<>`@?#%')


@dataclass(frozen=True, order=True)
class _CanonicalPackageUrl:
    package_type: str
    namespace: str
    name: str
    version: str
    qualifiers: tuple[tuple[str, str], ...]
    subpath: str
    canonical: str = field(compare=False)


def _ascii_lower(value: str) -> str:
    return "".join(chr(ord(character) + 32) if "A" <= character <= "Z" else character for character in value)


def _decode(value: str, *, label: str) -> str:
    try:
        return unquote_to_bytes(value).decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"{label} contains invalid percent-encoded UTF-8") from error


def _decode_namespace(value: str, *, label: str) -> str:
    segments: list[str] = []
    for raw_segment in value.strip("/").split("/"):
        if not raw_segment:
            continue
        segment = _decode(raw_segment, label=label)
        if "/" in segment:
            raise ValueError(f"{label} contains an encoded namespace slash")
        segments.append(segment)
    return "/".join(segments)


def _decode_subpath(value: str, *, label: str) -> str:
    segments: list[str] = []
    for raw_segment in value.strip("/").split("/"):
        if not raw_segment:
            continue
        segment = _decode(raw_segment, label=label)
        if "/" in segment:
            raise ValueError(f"{label} contains an encoded subpath slash")
        if len(segment) < 3 and segment and all(character == "." for character in segment):
            continue
        segments.append(segment)
    return "/".join(segments)


def _canonical_checksum(value: str, *, label: str) -> str:
    algorithms: dict[str, str] = {}
    for checksum in value.split(","):
        if ":" not in checksum:
            raise ValueError(f"{label} checksum qualifier is malformed")
        algorithm, digest = checksum.rsplit(":", 1)
        # purl 0.1.6 qualifiers/well_known.rs:124-128 uses Unicode lowercase.
        algorithm = algorithm.lower()
        if algorithm in algorithms:
            raise ValueError(f"{label} checksum qualifier repeats an algorithm")
        if len(digest) % 2 or any(character not in _HEX_DIGITS for character in digest):
            raise ValueError(f"{label} checksum qualifier contains invalid hexadecimal bytes")
        algorithms[algorithm] = _ascii_lower(digest)
    return ",".join(f"{algorithm}:{algorithms[algorithm]}" for algorithm in sorted(algorithms))


def _decode_qualifiers(value: str, *, label: str) -> tuple[tuple[str, str], ...]:
    qualifiers: dict[str, str] = {}
    for raw_qualifier in value.split("&"):
        if "=" not in raw_qualifier:
            raise ValueError(f"{label} qualifier must contain key=value")
        raw_key, raw_value = raw_qualifier.split("=", 1)
        if _QUALIFIER_KEY.fullmatch(raw_key) is None:
            raise ValueError(f"{label} qualifier key is malformed")
        key = _ascii_lower(raw_key)
        decoded = _decode(raw_value, label=label)
        if not decoded:
            continue
        if key in qualifiers:
            raise ValueError(f"{label} qualifier key is duplicated")
        qualifiers[key] = decoded
    if "checksum" in qualifiers:
        qualifiers["checksum"] = _canonical_checksum(qualifiers["checksum"], label=label)
    return tuple(sorted(qualifiers.items()))


def _encode(value: str, *, blocked: frozenset[str]) -> str:
    encoded: list[str] = []
    for byte in value.encode("utf-8"):
        character = chr(byte)
        if byte >= 128 or byte < 32 or byte == 127 or character in blocked:
            encoded.append(f"%{byte:02X}")
        else:
            encoded.append(character)
    return "".join(encoded)


def _format_package_url(
    *,
    package_type: str,
    namespace: str,
    name: str,
    version: str,
    qualifiers: tuple[tuple[str, str], ...],
    subpath: str,
) -> str:
    result = f"pkg:{package_type}/"
    if namespace:
        result += _encode(namespace, blocked=_PATH_BLOCKED) + "/"
    result += _encode(name, blocked=_NAME_BLOCKED)
    if version:
        result += "@" + _encode(version, blocked=_PATH_BLOCKED)
    if qualifiers:
        result += "?" + "&".join(
            f"{_encode(key, blocked=_QUALIFIER_BLOCKED)}={_encode(value, blocked=_QUALIFIER_BLOCKED)}"
            for key, value in qualifiers
        )
    if subpath:
        result += "#" + _encode(subpath, blocked=_SUBPATH_BLOCKED)
    return result


def _parse_canonical_package_url(value: str, *, label: str) -> _CanonicalPackageUrl:
    if not value.startswith("pkg:"):
        raise ValueError(f"{label} must use the pkg: scheme")
    body = value[4:].lstrip("/")
    if "#" in body:
        body, raw_subpath = body.rsplit("#", 1)
        subpath = _decode_subpath(raw_subpath, label=label)
    else:
        subpath = ""
    if "?" in body:
        body, raw_qualifiers = body.rsplit("?", 1)
        qualifiers = _decode_qualifiers(raw_qualifiers, label=label)
    else:
        qualifiers = ()
    if not body or "/" not in body:
        raise ValueError(f"{label} must contain package type and name")
    raw_package_type, path = body.split("/", 1)
    if _PACKAGE_TYPE.fullmatch(raw_package_type) is None:
        raise ValueError(f"{label} package type is malformed")
    package_type = _ascii_lower(raw_package_type)
    if "@" in path:
        path, raw_version = path.rsplit("@", 1)
        version = _decode(raw_version, label=label)
    else:
        version = ""
    if "/" in path:
        raw_namespace, raw_name = path.rsplit("/", 1)
        namespace = _decode_namespace(raw_namespace, label=label)
    else:
        namespace = ""
        raw_name = path
    name = _decode(raw_name, label=label)
    if not name:
        raise ValueError(f"{label} package name must not be empty")
    canonical = _format_package_url(
        package_type=package_type,
        namespace=namespace,
        name=name,
        version=version,
        qualifiers=qualifiers,
        subpath=subpath,
    )
    if canonical != value:
        raise ValueError(f"{label} must use canonical package URL spelling")
    return _CanonicalPackageUrl(
        package_type=package_type,
        namespace=namespace,
        name=name,
        version=version,
        qualifiers=qualifiers,
        subpath=subpath,
        canonical=canonical,
    )
