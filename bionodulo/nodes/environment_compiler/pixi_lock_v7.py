"""Pinned Pixi lock-v7 decoding and exact list reconciliation."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Annotated, Literal, TypeAlias
from urllib.parse import urlsplit

import yaml  # type: ignore[import-untyped]
from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.utils import InvalidWheelFilename, canonicalize_name, parse_wheel_filename
from packaging.version import InvalidVersion, Version
from pydantic import Field, StringConstraints, TypeAdapter

from bionodulo.nodes.contract.artifacts import _StrictFrozenModel
from bionodulo.nodes.contract.environments import (
    CondaLockedArtifact,
    ExecutionPlatform,
    LockedArtifact,
    PlatformLock,
    PypiLockedArtifact,
    ResolverIdentity,
    Sha256Digest,
)
from bionodulo.nodes.environment_compiler import package_url


_MAX_PIXI_LOCK_BYTES = 8 * 1024 * 1024
_MAX_PIXI_LIST_BYTES = 16 * 1024 * 1024
_MAX_LOCK_DEPTH = 32
_MAX_LOCK_PACKAGES = 4096
_MAX_LOCK_ENVIRONMENTS = 4096
_MAX_LOCK_PLATFORMS = 64

_BareMd5 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$", min_length=32, max_length=32)]
_BareSha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$", min_length=64, max_length=64)]
_U64 = Annotated[int, Field(strict=True, ge=0, le=2**64 - 1)]
_I64 = Annotated[int, Field(strict=True, ge=-(2**63), le=2**63 - 1)]
_PackageKind: TypeAlias = Literal["conda", "pypi"]
_PackageIdentity: TypeAlias = tuple[_PackageKind, str]


PIXI_PLATFORM: Mapping[ExecutionPlatform, str] = MappingProxyType(
    {
        ExecutionPlatform.LINUX_AMD64: "linux-64",
        ExecutionPlatform.LINUX_ARM64: "linux-aarch64",
    }
)


class _PixiListRecordBase(_StrictFrozenModel):
    """The flat `Package` serializer from Pixi v0.68.1."""

    name: str
    version: str | None
    build: str | None
    build_number: _U64 | None
    size_bytes: _U64 | None
    # Upstream overloads source with channel, index, URL, or path provenance.
    source: str | None
    license: str | None
    license_family: str | None
    is_explicit: bool
    # Pixi omits this field when false, so normal records contain 24 fields.
    is_editable: bool = False
    md5: _BareMd5 | None
    sha256: _BareSha256 | None
    arch: str | None
    platform: str | None
    subdir: str | None
    timestamp: _I64 | None
    noarch: str | None
    file_name: str | None
    url: str | None
    index_url: str | None
    requested_spec: str | None
    constrains: tuple[str, ...]
    depends: tuple[str, ...]
    track_features: tuple[str, ...]


class PixiCondaListRecord(_PixiListRecordBase):
    kind: Literal["conda"]
    index_url: None


class PixiPypiListRecord(_PixiListRecordBase):
    kind: Literal["pypi"]
    build: None
    build_number: None
    license: None
    license_family: None
    arch: None
    platform: None
    subdir: None
    timestamp: None
    noarch: None
    file_name: None
    constrains: tuple[()]
    track_features: tuple[()]


PixiListRecord: TypeAlias = Annotated[
    PixiCondaListRecord | PixiPypiListRecord,
    Field(discriminator="kind"),
]
_PIXI_LIST_ADAPTER = TypeAdapter(tuple[PixiListRecord, ...])


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def decode_pixi_list_json(content: bytes) -> tuple[PixiListRecord, ...]:
    """Decode the exact top-level array emitted by Pixi v0.68.1."""

    if type(content) is not bytes:
        raise TypeError("Pixi list JSON must be exact captured bytes")
    if not content or len(content) > _MAX_PIXI_LIST_BYTES:
        raise ValueError(f"Pixi list JSON size must be between 1 and {_MAX_PIXI_LIST_BYTES} bytes")
    json.loads(content, object_pairs_hook=_unique_json_object)
    records = _PIXI_LIST_ADAPTER.validate_json(content)
    if len(records) > _MAX_LOCK_PACKAGES:
        raise ValueError(f"Pixi list package count exceeds {_MAX_LOCK_PACKAGES}")
    names = tuple(record.name for record in records)
    if names != tuple(sorted(names)):
        raise ValueError("Pixi list records must be sorted by name")
    return records


def _required(value: str | None, *, field: str, kind: str) -> str:
    if value is None:
        raise ValueError(f"{kind} record requires {field} for immutable admission")
    return value


def _admit_conda(record: PixiCondaListRecord, *, resolver_platform: str) -> CondaLockedArtifact:
    if record.is_editable:
        raise ValueError("editable Conda records are not immutable artifacts")
    subdir = _required(record.subdir, field="subdir", kind="Conda")
    if subdir not in (resolver_platform, "noarch"):
        raise ValueError(f"Conda record does not belong to selected platform {resolver_platform}")
    return CondaLockedArtifact(
        kind="conda",
        name=record.name,
        version=_required(record.version, field="version", kind="Conda"),
        build=_required(record.build, field="build", kind="Conda"),
        filename=_required(record.file_name, field="file_name", kind="Conda"),
        url=_required(record.url, field="url", kind="Conda"),
        sha256="sha256:" + _required(record.sha256, field="sha256", kind="Conda"),
        size_bytes=record.size_bytes,
    )


def _admit_pypi(record: PixiPypiListRecord) -> PypiLockedArtifact:
    if record.is_editable:
        raise ValueError("editable PyPI records are not immutable artifacts")
    url = _required(record.url, field="url", kind="PyPI")
    filename = urlsplit(url).path.rsplit("/", 1)[-1]
    if not filename:
        raise ValueError("PyPI record URL must contain an artifact filename")
    return PypiLockedArtifact(
        kind="pypi",
        name=canonicalize_name(record.name),
        version=_required(record.version, field="version", kind="PyPI"),
        filename=filename,
        url=url,
        sha256="sha256:" + _required(record.sha256, field="sha256", kind="PyPI"),
        size_bytes=record.size_bytes,
    )


def _admit_pixi_records(
    records: Iterable[PixiListRecord],
    *,
    resolver: ResolverIdentity,
    environment_name: str,
    target_platform: ExecutionPlatform,
    native_lock_sha256: Sha256Digest,
) -> PlatformLock:
    """Admit decoded transport records into the immutable BioNodulo contract."""

    decoded = tuple(records)
    if not decoded:
        raise ValueError("Pixi selected-platform output must not be empty")
    resolver_platform = PIXI_PLATFORM[target_platform]
    artifacts: list[LockedArtifact] = []
    for record in decoded:
        if isinstance(record, PixiCondaListRecord):
            artifacts.append(_admit_conda(record, resolver_platform=resolver_platform))
        elif isinstance(record, PixiPypiListRecord):
            artifacts.append(_admit_pypi(record))
        else:
            raise TypeError(f"unsupported decoded Pixi record: {type(record).__name__}")
    artifacts.sort(key=lambda artifact: artifact.name)
    return PlatformLock(
        platform=target_platform,
        environment_name=environment_name,
        resolver_platform=resolver_platform,
        resolver=resolver,
        native_lock_sha256=native_lock_sha256,
        artifacts=tuple(artifacts),
    )


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(loader: _UniqueKeyLoader, node: yaml.MappingNode) -> dict[object, object]:
    result: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=False)
        if type(key) is not str:
            raise ValueError("pixi.lock mapping keys must be strings")
        if key == "<<":
            raise ValueError("pixi.lock YAML merge keys are forbidden")
        if key in result:
            raise ValueError(f"pixi.lock contains duplicate key: {key}")
        result[key] = loader.construct_object(value_node, deep=False)
    return result


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


@dataclass(frozen=True)
class _NativePackage:
    kind: _PackageKind
    url: str
    name: str
    version: str
    filename: str
    sha256: str
    md5: str | None
    size_bytes: int | None
    build: str | None = None
    build_number: int | None = None
    subdir: str | None = None
    arch: str | None = None
    platform: str | None = None
    noarch: str | None = None
    source: str | None = None
    index_url: str | None = None
    license: str | None = None
    license_family: str | None = None
    timestamp: int | None = None
    depends: tuple[str, ...] = ()
    constrains: tuple[str, ...] = ()
    track_features: tuple[str, ...] = ()
    requires_dist: tuple[str, ...] = ()
    requires_python: str | None = None
    legacy_bz2_md5: str | None = None
    legacy_bz2_size: int | None = None
    features: str | None = None
    python_site_packages_path: str | None = None
    extra_depends: tuple[tuple[str, tuple[str, ...]], ...] = ()
    run_exports: tuple[tuple[str, tuple[str, ...]], ...] | None = None
    purls: tuple[str, ...] | None = None
    flags: tuple[str, ...] = ()


_ROOT_FIELDS = ("version", "platforms", "environments", "packages")
_PLATFORM_FIELDS = ("name", "subdir", "virtual-packages")
_ENVIRONMENT_FIELDS = ("channels", "indexes", "find-links", "options", "packages")
_CHANNEL_FIELDS = ("url", "used_env_vars")
_OPTION_FIELDS = ("strategy", "channel-priority", "pypi-prerelease-mode")
# rattler_lock 0.29.0 options.rs, backed by rattler_solve 6.0.1
# src/lib.rs:349-370 and 460-480.
_OPTION_VALUES: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "strategy": frozenset(("highest", "lowest-version", "lowest-version-direct")),
        "channel-priority": frozenset(("strict", "disabled")),
        "pypi-prerelease-mode": frozenset(
            ("disallow", "allow", "if-necessary", "explicit", "if-necessary-or-explicit")
        ),
    }
)
_OPTION_DEFAULTS: Mapping[str, str] = MappingProxyType(
    {
        "strategy": "highest",
        "channel-priority": "strict",
        "pypi-prerelease-mode": "if-necessary-or-explicit",
    }
)
_CONDA_FIELDS = (
    "conda",
    "name",
    "version",
    "build",
    "build_number",
    "subdir",
    "noarch",
    "variants",
    "sha256",
    "md5",
    "legacy_bz2_md5",
    "depends",
    "constrains",
    "extra_depends",
    "channel",
    "features",
    "flags",
    "track_features",
    "file_name",
    "license",
    "license_family",
    "purls",
    "run_exports",
    "size",
    "legacy_bz2_size",
    "timestamp",
    "python_site_packages_path",
)
_PYPI_FIELDS = (
    "pypi",
    "name",
    "version",
    "md5",
    "sha256",
    "index",
    "requires_dist",
    "requires_python",
    "build_packages",
    "host_packages",
)
_RUN_EXPORT_FIELDS = ("weak", "strong", "noarch", "weak_constrains", "strong_constrains")


def _scan_bounded_yaml(content: bytes) -> str:
    if not content or len(content) > _MAX_PIXI_LOCK_BYTES:
        raise ValueError(f"pixi.lock size must be between 1 and {_MAX_PIXI_LOCK_BYTES} bytes")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("pixi.lock must be UTF-8") from error
    if content.startswith(b"\xef\xbb\xbf") or "\r" in text or "\t" in text or "\x00" in text:
        raise ValueError("pixi.lock must use canonical UTF-8 with LF line endings and no tabs or BOM")
    if not text.endswith("\n"):
        raise ValueError("pixi.lock must end with one LF line ending")
    depth = 0
    starts = (
        yaml.tokens.BlockMappingStartToken,
        yaml.tokens.BlockSequenceStartToken,
        yaml.tokens.FlowMappingStartToken,
        yaml.tokens.FlowSequenceStartToken,
    )
    ends = (
        yaml.tokens.BlockEndToken,
        yaml.tokens.FlowMappingEndToken,
        yaml.tokens.FlowSequenceEndToken,
    )
    forbidden = {
        yaml.tokens.AnchorToken: "anchors",
        yaml.tokens.AliasToken: "aliases",
        yaml.tokens.TagToken: "explicit tags",
        yaml.tokens.DirectiveToken: "directives",
        yaml.tokens.DocumentStartToken: "document markers",
        yaml.tokens.DocumentEndToken: "document markers",
    }
    try:
        for token in yaml.scan(text, Loader=_UniqueKeyLoader):
            feature = next((label for token_type, label in forbidden.items() if isinstance(token, token_type)), None)
            if feature is not None:
                raise ValueError(f"pixi.lock YAML {feature} are forbidden")
            if isinstance(token, starts):
                depth += 1
                if depth > _MAX_LOCK_DEPTH:
                    raise ValueError(f"pixi.lock nested depth exceeds {_MAX_LOCK_DEPTH}")
            elif isinstance(token, ends):
                depth -= 1
    except yaml.YAMLError as error:
        raise ValueError(f"pixi.lock YAML is malformed: {error}") from error
    return text


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if type(value) is not dict:
        raise ValueError(f"{label} must be a mapping")
    if any(type(key) is not str for key in value):
        raise ValueError(f"{label} keys must be strings")
    return value


def _sequence(value: object, *, label: str, maximum: int) -> list[object]:
    if type(value) is not list:
        raise ValueError(f"{label} must be a sequence")
    if len(value) > maximum:
        raise ValueError(
            f"{label} package count exceeds {maximum}" if "package" in label else f"{label} exceeds {maximum}"
        )
    return value


def _text(value: object, *, label: str, maximum: int = 4096) -> str:
    if type(value) is not str or not value or len(value) > maximum:
        raise ValueError(f"{label} must be a nonempty string of at most {maximum} characters")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError(f"{label} must not contain control characters")
    return value


def _optional_text(value: object, *, label: str, maximum: int = 4096) -> str | None:
    if value is None:
        return None
    return _text(value, label=label, maximum=maximum)


def _present_text(
    mapping: dict[str, object],
    field: str,
    *,
    label: str,
    maximum: int,
) -> str | None:
    return _text(mapping[field], label=label, maximum=maximum) if field in mapping else None


def _bounded_string(value: object, *, label: str, maximum: int) -> str:
    if type(value) is not str or len(value) > maximum:
        raise ValueError(f"{label} must be a string of at most {maximum} characters")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError(f"{label} must not contain control characters")
    return value


def _bounded_int(value: object, *, label: str, maximum: int = 2**64 - 1) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(f"{label} must be an unsigned bounded integer")
    return value


def _bounded_signed_int(value: object, *, label: str) -> int:
    if type(value) is not int or not -(2**63) <= value <= 2**63 - 1:
        raise ValueError(f"{label} must be a signed 64-bit integer")
    return value


def _string_sequence(value: object, *, label: str, maximum: int = 4096) -> tuple[str, ...]:
    sequence = _sequence(value, label=label, maximum=maximum)
    return tuple(_text(item, label=f"{label} item") for item in sequence)


def _require_fields(
    value: dict[str, object],
    *,
    allowed: tuple[str, ...],
    required: tuple[str, ...],
    label: str,
) -> None:
    unknown = tuple(key for key in value if key not in allowed)
    if unknown:
        raise ValueError(f"{label} contains unknown fields: {', '.join(unknown)}")
    missing = tuple(key for key in required if key not in value)
    if missing:
        raise ValueError(f"{label} is missing required fields: {', '.join(missing)}")
    positions = {field: position for position, field in enumerate(allowed)}
    field_positions = tuple(positions[key] for key in value)
    if field_positions != tuple(sorted(field_positions)):
        raise ValueError(f"{label} fields must use canonical upstream order")


def _validate_https_artifact_url(value: object, *, label: str) -> str:
    url = _text(value, label=label, maximum=2048)
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or "%" in url
        or "\\" in url
    ):
        raise ValueError(f"{label} must be an immutable canonical HTTPS URL")
    if parsed.hostname != parsed.hostname.lower() or parsed.path.rsplit("/", 1)[-1] == "":
        raise ValueError(f"{label} must use canonical hostname and an artifact filename")
    return url


def _validate_https_base_url(value: object, *, label: str, allow_trailing_slash: bool) -> str:
    url = _text(value, label=label, maximum=2048)
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or "%" in url
        or "\\" in url
        or parsed.hostname != parsed.hostname.lower()
        or (not allow_trailing_slash and url.endswith("/"))
    ):
        raise ValueError(f"{label} must be a canonical HTTPS URL")
    return url


def _conda_url_identity(url: str) -> tuple[str, str, str, str, str, str | None, str | None, str | None]:
    parsed = urlsplit(url)
    filename = parsed.path.rsplit("/", 1)[-1]
    suffix = ".tar.bz2" if filename.endswith(".tar.bz2") else ".conda" if filename.endswith(".conda") else None
    if suffix is None:
        raise ValueError("native Conda package URL must reference a .conda or .tar.bz2 archive")
    components = filename[: -len(suffix)].rsplit("-", 2)
    if len(components) != 3 or any(not component for component in components):
        raise ValueError("native Conda package URL filename cannot derive name, version, and build")
    name, version, build = components
    subdir = parsed.path.rsplit("/", 2)[-2]
    if subdir == "linux-64":
        platform, arch, noarch = "linux", "x86_64", None
    elif subdir == "linux-aarch64":
        platform, arch, noarch = "linux", "aarch64", None
    elif subdir == "noarch":
        platform, arch = None, None
        noarch = "python" if "py" in build else "generic"
    else:
        platform, arch, noarch = None, None, None
    return name, version, build, filename, subdir, platform, arch, noarch


def _derived_build_number(build: str) -> int:
    trailing_digits = re.search(r"([0-9]+)$", build)
    return int(trailing_digits.group(1)) if trailing_digits is not None else 0


def _derived_channel(url: str, subdir: str) -> str:
    parsed = urlsplit(url)
    path = parsed.path.rsplit(f"/{subdir}/", 1)[0]
    return f"{parsed.scheme}://{parsed.netloc}{path}".rstrip("/")


def _string_list_mapping(value: object, *, label: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    mapping = _mapping(value, label=label)
    if not mapping or len(mapping) > _MAX_LOCK_PACKAGES:
        raise ValueError(f"{label} must contain 1..{_MAX_LOCK_PACKAGES} entries")
    if tuple(mapping) != tuple(sorted(mapping)):
        raise ValueError(f"{label} keys must use canonical BTreeMap ordering")
    result: list[tuple[str, tuple[str, ...]]] = []
    for key, items in mapping.items():
        _text(key, label=f"{label} key", maximum=256)
        result.append((key, _string_sequence(items, label=f"{label} {key}")))
    return tuple(result)


def _validate_package_url(value: str, *, label: str) -> package_url._CanonicalPackageUrl:
    return package_url._parse_canonical_package_url(value, label=label)


def _decode_native_conda(value: dict[str, object]) -> _NativePackage:
    _require_fields(value, allowed=_CONDA_FIELDS, required=("conda", "sha256", "md5", "size"), label="Conda package")
    url = _validate_https_artifact_url(value["conda"], label="native Conda URL")
    derived_name, derived_version, derived_build, filename, subdir, platform, arch, noarch = _conda_url_identity(url)
    name = _present_text(value, "name", label="Conda name", maximum=128) or derived_name
    version = _present_text(value, "version", label="Conda version", maximum=128) or derived_version
    build = _present_text(value, "build", label="Conda build", maximum=256) or derived_build
    explicit_subdir = _present_text(value, "subdir", label="Conda subdir", maximum=64)
    explicit_filename = _present_text(value, "file_name", label="Conda file_name", maximum=512)
    if (name, version, build) != (derived_name, derived_version, derived_build):
        raise ValueError("native Conda name, version, and build must agree with its URL")
    if explicit_subdir is not None and explicit_subdir != subdir:
        raise ValueError("native Conda subdir must agree with its URL")
    if explicit_filename is not None and explicit_filename != filename:
        raise ValueError("native Conda file_name must agree with its URL")
    native_noarch = noarch
    if "noarch" in value:
        native_noarch = _bounded_string(value["noarch"], label="Conda noarch", maximum=32)
        if native_noarch not in ("generic", "python"):
            raise ValueError("Conda noarch must be exactly generic or python")
    sha256 = _text(value["sha256"], label="Conda sha256", maximum=64)
    md5 = _text(value["md5"], label="Conda md5", maximum=32)
    if re.fullmatch(r"[0-9a-f]{64}", sha256) is None or re.fullmatch(r"[0-9a-f]{32}", md5) is None:
        raise ValueError("native Conda hashes must use lowercase hexadecimal spelling")
    legacy_bz2_md5 = None
    if "legacy_bz2_md5" in value:
        legacy_bz2_md5 = _text(value["legacy_bz2_md5"], label="Conda legacy_bz2_md5", maximum=32)
        if re.fullmatch(r"[0-9a-f]{32}", legacy_bz2_md5) is None:
            raise ValueError("Conda legacy_bz2_md5 must be a lowercase 32-character MD5 digest")
    legacy_bz2_size = None
    if "legacy_bz2_size" in value:
        legacy_bz2_size = _bounded_int(value["legacy_bz2_size"], label="Conda legacy_bz2_size")
    features = None
    if "features" in value:
        features = _bounded_string(value["features"], label="Conda features", maximum=256)
    python_site_packages_path = None
    if "python_site_packages_path" in value:
        python_site_packages_path = _bounded_string(
            value["python_site_packages_path"],
            label="Conda python_site_packages_path",
            maximum=1024,
        )
    build_number = (
        _bounded_int(value["build_number"], label="Conda build_number")
        if "build_number" in value
        else _derived_build_number(build)
    )
    if "variants" in value:
        raise ValueError("binary Conda package must not declare source variants")
    extra_depends: tuple[tuple[str, tuple[str, ...]], ...] = ()
    if "extra_depends" in value:
        extra_depends = _string_list_mapping(value["extra_depends"], label="Conda extra_depends")
    run_exports = None
    if "run_exports" in value:
        exports = _mapping(value["run_exports"], label="Conda run_exports")
        _require_fields(exports, allowed=_RUN_EXPORT_FIELDS, required=(), label="Conda run_exports")
        run_exports = tuple(
            (key, _string_sequence(items, label=f"Conda run_exports {key}")) for key, items in exports.items()
        )
    flags: tuple[str, ...] = ()
    if "flags" in value:
        flags = _string_sequence(value["flags"], label="Conda flags")
        if not flags:
            raise ValueError("Conda flags must be omitted rather than serialized as an empty vector")
    purls = None
    if "purls" in value:
        purls = _string_sequence(value["purls"], label="Conda purls")
        parsed_purls = tuple(_validate_package_url(purl, label="Conda purls item") for purl in purls)
        if parsed_purls != tuple(sorted(set(parsed_purls))):
            raise ValueError("Conda purls must be unique and use canonical BTreeSet ordering")
    source: str | None = _derived_channel(url, subdir)
    if "channel" in value:
        source = (
            None
            if value["channel"] is None
            else _validate_https_base_url(
                value["channel"],
                label="Conda channel",
                allow_trailing_slash=False,
            )
        )
    return _NativePackage(
        kind="conda",
        url=url,
        name=name,
        version=version,
        filename=filename,
        sha256=sha256,
        md5=md5,
        size_bytes=_bounded_int(value["size"], label="Conda size", maximum=2**50),
        build=build,
        build_number=build_number,
        subdir=subdir,
        arch=arch,
        platform=platform,
        noarch=native_noarch,
        source=source,
        license=_present_text(value, "license", label="Conda license", maximum=512),
        license_family=_present_text(value, "license_family", label="Conda license_family", maximum=256),
        timestamp=(_bounded_signed_int(value["timestamp"], label="Conda timestamp") if "timestamp" in value else None),
        depends=_string_sequence(value.get("depends", []), label="Conda depends"),
        constrains=_string_sequence(value.get("constrains", []), label="Conda constrains"),
        track_features=_string_sequence(value.get("track_features", []), label="Conda track_features"),
        legacy_bz2_md5=legacy_bz2_md5,
        legacy_bz2_size=legacy_bz2_size,
        features=features,
        python_site_packages_path=python_site_packages_path,
        extra_depends=extra_depends,
        run_exports=run_exports,
        purls=purls,
        flags=flags,
    )


def _decode_native_pypi(value: dict[str, object]) -> _NativePackage:
    _require_fields(
        value,
        allowed=_PYPI_FIELDS,
        required=("pypi", "name", "version", "sha256"),
        label="PyPI package",
    )
    url = _validate_https_artifact_url(value["pypi"], label="native PyPI URL")
    filename = urlsplit(url).path.rsplit("/", 1)[-1]
    try:
        wheel_name, wheel_version, _, _ = parse_wheel_filename(filename)
    except InvalidWheelFilename as error:
        raise ValueError("native PyPI package must reference an immutable wheel") from error
    name = _text(value["name"], label="PyPI name", maximum=128)
    version = _text(value["version"], label="PyPI version", maximum=128)
    if canonicalize_name(name) != name or wheel_name != name or str(wheel_version) != version:
        raise ValueError("native PyPI name and version must use canonical spelling and agree with its wheel URL")
    sha256 = _text(value["sha256"], label="PyPI sha256", maximum=64)
    if re.fullmatch(r"[0-9a-f]{64}", sha256) is None:
        raise ValueError("native PyPI sha256 must use lowercase hexadecimal spelling")
    md5 = _present_text(value, "md5", label="PyPI md5", maximum=32)
    if md5 is not None and re.fullmatch(r"[0-9a-f]{32}", md5) is None:
        raise ValueError("native PyPI md5 must use lowercase hexadecimal spelling")
    requires_dist = _string_sequence(value.get("requires_dist", []), label="PyPI requires_dist")
    for dependency in requires_dist:
        try:
            Requirement(dependency)
        except InvalidRequirement as error:
            raise ValueError(f"native PyPI dependency marker is malformed: {dependency}") from error
    requires_python = _present_text(
        value,
        "requires_python",
        label="PyPI requires_python",
        maximum=256,
    )
    if requires_python is not None:
        try:
            SpecifierSet(requires_python)
        except InvalidSpecifier as error:
            raise ValueError("native PyPI requires_python is malformed") from error
    for field in ("build_packages", "host_packages"):
        if field in value:
            raise ValueError(f"immutable PyPI wheel must not declare {field}")
    index_url = (
        _validate_https_base_url(value["index"], label="PyPI index", allow_trailing_slash=True)
        if "index" in value
        else None
    )
    return _NativePackage(
        kind="pypi",
        url=url,
        name=name,
        version=version,
        filename=filename,
        sha256=sha256,
        md5=md5,
        size_bytes=None,
        source=index_url,
        index_url=index_url,
        requires_dist=requires_dist,
        requires_python=requires_python,
    )


def _decode_reference(value: object, *, label: str) -> _PackageIdentity:
    reference = _mapping(value, label=label)
    if len(reference) != 1:
        raise ValueError(f"{label} must be a single-key package selector")
    kind, raw_url = next(iter(reference.items()))
    if kind == "conda_source":
        raise ValueError("source package selectors are not immutable binary artifacts")
    if kind == "conda":
        package_kind: _PackageKind = "conda"
    elif kind == "pypi":
        package_kind = "pypi"
    else:
        raise ValueError(f"{label} must select conda or pypi")
    return package_kind, _validate_https_artifact_url(raw_url, label=f"{label} URL")


def _validate_platforms(value: object, *, resolver_platform: str) -> set[str]:
    platforms = _sequence(value, label="pixi.lock platforms", maximum=_MAX_LOCK_PLATFORMS)
    if not platforms:
        raise ValueError("pixi.lock platforms must not be empty")
    names: list[str] = []
    effective_subdirs: dict[str, str] = {}
    for index, raw_platform in enumerate(platforms):
        platform = _mapping(raw_platform, label=f"pixi.lock platform {index}")
        _require_fields(platform, allowed=_PLATFORM_FIELDS, required=("name",), label="pixi.lock platform")
        name = _text(platform["name"], label="pixi.lock platform name", maximum=64)
        subdir = _optional_text(platform.get("subdir"), label="pixi.lock platform subdir", maximum=64) or name
        if "virtual-packages" in platform:
            virtual_packages = _string_sequence(platform["virtual-packages"], label="virtual-packages", maximum=256)
            if virtual_packages != tuple(sorted(set(virtual_packages))):
                raise ValueError("pixi.lock virtual-packages must be unique and canonically ordered")
        names.append(name)
        effective_subdirs[name] = subdir
    if names != sorted(set(names)):
        raise ValueError("pixi.lock platform names must be unique and canonically ordered")
    if resolver_platform not in effective_subdirs or effective_subdirs[resolver_platform] != resolver_platform:
        raise ValueError(f"pixi.lock platforms must declare exact selected platform {resolver_platform}")
    return set(names)


def _validate_channels(value: object) -> None:
    for index, raw_channel in enumerate(_sequence(value, label="environment channels", maximum=64)):
        channel = _mapping(raw_channel, label=f"environment channel {index}")
        _require_fields(channel, allowed=_CHANNEL_FIELDS, required=("url",), label="environment channel")
        _validate_https_base_url(
            channel["url"],
            label="environment channel URL",
            allow_trailing_slash=True,
        )
        if "used_env_vars" in channel:
            variables = _string_sequence(channel["used_env_vars"], label="channel used_env_vars", maximum=64)
            if variables != tuple(sorted(set(variables))):
                raise ValueError("channel used_env_vars must be unique and canonically ordered")


def _validate_environments(
    value: object,
    *,
    declared_platforms: set[str],
    environment_name: str,
    resolver_platform: str,
) -> tuple[tuple[_PackageIdentity, ...], tuple[_PackageIdentity, ...], str]:
    environments = _mapping(value, label="pixi.lock environments")
    if not environments or len(environments) > _MAX_LOCK_ENVIRONMENTS:
        raise ValueError(f"pixi.lock environments must contain 1..{_MAX_LOCK_ENVIRONMENTS} entries")
    if tuple(environments) != tuple(sorted(environments)):
        raise ValueError("pixi.lock environment names must use canonical ordering")
    if environment_name not in environments:
        raise ValueError("pixi.lock must contain the exact selected environment_name")
    all_references: list[_PackageIdentity] = []
    selected_references: tuple[_PackageIdentity, ...] | None = None
    selected_default_index = "https://pypi.org/simple"
    for name, raw_environment in environments.items():
        _text(name, label="pixi.lock environment name", maximum=128)
        environment = _mapping(raw_environment, label=f"environment {name}")
        _require_fields(
            environment,
            allowed=_ENVIRONMENT_FIELDS,
            required=("channels", "packages"),
            label=f"environment {name}",
        )
        _validate_channels(environment["channels"])
        indexes: tuple[str, ...] = ()
        if "indexes" in environment:
            indexes = tuple(
                _validate_https_base_url(
                    index,
                    label=f"environment {name} index",
                    allow_trailing_slash=True,
                )
                for index in _string_sequence(
                    environment["indexes"],
                    label=f"environment {name} indexes",
                    maximum=64,
                )
            )
        if "find-links" in environment:
            raise ValueError("environment find-links are not admitted immutable package indexes")
        if "options" in environment:
            options = _mapping(environment["options"], label=f"environment {name} options")
            _require_fields(options, allowed=_OPTION_FIELDS, required=(), label="environment options")
            if not options:
                raise ValueError("environment options must be omitted when all solver options are default")
            for key, option in options.items():
                validated = _text(option, label=f"environment option {key}", maximum=64)
                if validated not in _OPTION_VALUES[key]:
                    raise ValueError(f"environment option {key} is not an exact pinned solver enum")
                if validated == _OPTION_DEFAULTS[key]:
                    raise ValueError(f"environment option {key} default must be omitted by canonical serialization")
        packages = _mapping(environment["packages"], label=f"environment {name} packages")
        if tuple(packages) != tuple(sorted(packages)):
            raise ValueError("environment package platforms must use canonical ordering")
        if any(platform not in declared_platforms for platform in packages):
            raise ValueError("environment packages reference an undeclared platform")
        for package_platform, raw_references in packages.items():
            references = tuple(
                _decode_reference(reference, label=f"environment {name} {package_platform} package")
                for reference in _sequence(
                    raw_references,
                    label=f"environment {name} {package_platform} packages",
                    maximum=_MAX_LOCK_PACKAGES,
                )
            )
            if not references:
                raise ValueError(f"environment {name} platform {package_platform} must contain packages")
            if references != tuple(sorted(set(references))):
                raise ValueError("environment package references must be unique and canonically ordered")
            all_references.extend(references)
            if name == environment_name and package_platform == resolver_platform:
                selected_references = references
                if indexes:
                    selected_default_index = indexes[0]
    if selected_references is None:
        raise ValueError(f"pixi.lock must contain selected platform {resolver_platform}")
    return selected_references, tuple(all_references), selected_default_index


def _validate_pixi_lock(
    content: bytes,
    *,
    environment_name: str,
    resolver_platform: str,
) -> tuple[_NativePackage, ...]:
    if type(content) is not bytes:
        raise TypeError("pixi.lock content must be exact captured bytes")
    text = _scan_bounded_yaml(content)
    try:
        document = yaml.load(text, Loader=_UniqueKeyLoader)
    except (ValueError, yaml.YAMLError) as error:
        raise ValueError(f"pixi.lock must be unique-key UTF-8 YAML: {error}") from error
    root = _mapping(document, label="pixi.lock top-level document")
    if tuple(root) != _ROOT_FIELDS:
        unknown = tuple(key for key in root if key not in _ROOT_FIELDS)
        if unknown:
            raise ValueError(f"pixi.lock top-level document contains unknown fields: {', '.join(unknown)}")
        raise ValueError("pixi.lock top-level fields must be complete and use canonical order")
    if type(root["version"]) is not int or root["version"] != 7:
        raise ValueError("pixi.lock format must be exactly version 7")
    declared_platforms = _validate_platforms(root["platforms"], resolver_platform=resolver_platform)
    selected_references, all_references, selected_default_index = _validate_environments(
        root["environments"],
        declared_platforms=declared_platforms,
        environment_name=environment_name,
        resolver_platform=resolver_platform,
    )
    raw_packages = _sequence(root["packages"], label="pixi.lock top-level packages", maximum=_MAX_LOCK_PACKAGES)
    if not raw_packages:
        raise ValueError("pixi.lock top-level packages must not be empty")
    packages: list[_NativePackage] = []
    for index, raw_package in enumerate(raw_packages):
        package = _mapping(raw_package, label=f"pixi.lock top-level package {index}")
        if "conda_source" in package:
            raise ValueError("source package records are not immutable binary artifacts")
        if "conda" in package:
            packages.append(_decode_native_conda(package))
        elif "pypi" in package:
            packages.append(_decode_native_pypi(package))
        else:
            raise ValueError("top-level package record must contain conda or pypi discriminator")
    identities = tuple((package.kind, package.url) for package in packages)
    if identities != tuple(sorted(identities)):
        raise ValueError("top-level package records must use canonical kind and URL ordering")
    if len(set(identities)) != len(identities):
        raise ValueError("top-level package records must resolve each package exactly once; duplicate record found")
    package_by_identity = {identity: package for identity, package in zip(identities, packages, strict=True)}
    if set(all_references) != set(identities):
        missing = set(all_references) - set(identities)
        extra = set(identities) - set(all_references)
        if missing:
            raise ValueError("every environment reference must resolve to exactly one top-level package record")
        if extra:
            raise ValueError("top-level package records must all belong to an environment lock closure")
    selected_packages: list[_NativePackage] = []
    for reference in selected_references:
        selected_package = package_by_identity[reference]
        if selected_package.kind == "pypi" and selected_package.index_url is None:
            selected_package = replace(
                selected_package,
                source=selected_default_index,
                index_url=selected_default_index,
            )
        selected_packages.append(selected_package)
    return tuple(selected_packages)


def _metadata_mismatch(native: _NativePackage, field: str, listed: object, expected: object) -> None:
    if listed != expected:
        raise ValueError(
            f"Pixi list native metadata mismatch for {native.kind} {native.url}: "
            f"{field} is {listed!r}, expected {expected!r}"
        )


def _validate_native_list_records(
    native_packages: tuple[_NativePackage, ...],
    records: tuple[PixiListRecord, ...],
    *,
    requested_specs: Mapping[str, str],
) -> None:
    listed: dict[tuple[str, str], PixiListRecord] = {}
    for record in records:
        url = _required(record.url, field="url", kind=record.kind)
        identity = (record.kind, url)
        if identity in listed:
            raise ValueError("Pixi list output contains duplicate package URL identity")
        listed[identity] = record
    native_by_identity = {(package.kind, package.url): package for package in native_packages}
    if set(listed) != set(native_by_identity):
        raise ValueError("Pixi list output does not match selected platform package references")
    python_version: Version | None = None
    for native in native_packages:
        if native.kind == "conda" and native.name == "python":
            try:
                python_version = Version(native.version)
            except InvalidVersion as error:
                raise ValueError("native locked Python version is malformed") from error
    for identity, native in native_by_identity.items():
        record = listed[identity]
        requested_name = canonicalize_name(record.name).replace("-", "_") if native.kind == "pypi" else record.name
        expected_requested_spec = requested_specs.get(requested_name)
        _metadata_mismatch(native, "is_explicit", record.is_explicit, expected_requested_spec is not None)
        _metadata_mismatch(native, "requested_spec", record.requested_spec, expected_requested_spec)
        listed_name = canonicalize_name(record.name) if native.kind == "pypi" else record.name
        _metadata_mismatch(native, "name", listed_name, native.name)
        _metadata_mismatch(native, "version", record.version, native.version)
        _metadata_mismatch(native, "sha256", record.sha256, native.sha256)
        _metadata_mismatch(native, "md5", record.md5, native.md5)
        listed_source = record.source
        if native.kind == "conda" and listed_source is not None:
            listed_source = listed_source.rstrip("/")
        _metadata_mismatch(native, "source", listed_source, native.source)
        if isinstance(record, PixiCondaListRecord):
            _metadata_mismatch(native, "build", record.build, native.build)
            _metadata_mismatch(native, "build_number", record.build_number, native.build_number)
            _metadata_mismatch(native, "file_name", record.file_name, native.filename)
            _metadata_mismatch(native, "size_bytes", record.size_bytes, native.size_bytes)
            _metadata_mismatch(native, "subdir", record.subdir, native.subdir)
            _metadata_mismatch(native, "platform", record.platform, native.platform)
            _metadata_mismatch(native, "arch", record.arch, native.arch)
            _metadata_mismatch(native, "noarch", record.noarch, native.noarch)
            _metadata_mismatch(native, "license", record.license, native.license)
            _metadata_mismatch(native, "license_family", record.license_family, native.license_family)
            _metadata_mismatch(native, "timestamp", record.timestamp, native.timestamp)
            _metadata_mismatch(native, "depends", record.depends, native.depends)
            _metadata_mismatch(native, "constrains", record.constrains, native.constrains)
            _metadata_mismatch(native, "track_features", record.track_features, native.track_features)
            _metadata_mismatch(native, "index_url", record.index_url, None)
        elif isinstance(record, PixiPypiListRecord):
            _metadata_mismatch(native, "index_url", record.index_url, native.index_url)
            _metadata_mismatch(native, "depends", record.depends, native.requires_dist)
            if record.size_bytes is not None and record.size_bytes <= 0:
                raise ValueError("Pixi list PyPI record requires a positive size_bytes value")
            if native.requires_python is not None:
                if python_version is None:
                    raise ValueError("native PyPI wheel metadata requires a locked Python runtime")
                if python_version not in SpecifierSet(native.requires_python):
                    raise ValueError(
                        f"native PyPI requires_python {native.requires_python} excludes locked Python {python_version}"
                    )
        else:  # pragma: no cover - closed discriminated union
            raise TypeError(f"unsupported Pixi list record: {type(record).__name__}")


def _compile_captured_platform_lock(
    *,
    pixi_list_content: bytes,
    pixi_lock_content: bytes,
    resolver: ResolverIdentity,
    environment_name: str,
    target_platform: ExecutionPlatform,
    requested_specs: Mapping[str, str],
) -> PlatformLock:
    """Compile exact captured Pixi list and native lock bytes."""

    resolver_platform = PIXI_PLATFORM[target_platform]
    native_packages = _validate_pixi_lock(
        pixi_lock_content,
        environment_name=environment_name,
        resolver_platform=resolver_platform,
    )
    native_digest = "sha256:" + hashlib.sha256(pixi_lock_content).hexdigest()
    records = decode_pixi_list_json(pixi_list_content)
    if not records:
        raise ValueError("Pixi selected-platform output must not be empty")
    _validate_native_list_records(native_packages, records, requested_specs=requested_specs)
    return _admit_pixi_records(
        records,
        resolver=resolver,
        environment_name=environment_name,
        target_platform=target_platform,
        native_lock_sha256=native_digest,
    )
