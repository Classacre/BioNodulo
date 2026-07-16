"""Strict Pixi transport decoding and immutable lock admission."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Literal, TypeAlias
from urllib.parse import urlsplit

import yaml  # type: ignore[import-untyped]
from packaging.utils import canonicalize_name
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


PIXI_VERSION = "0.68.1"
PIXI_TAG_COMMIT = "a2453cacd4a02bc99ee84b5e6015ec83bbb2d397"
_PIXI_RELEASE_BASE = f"https://github.com/prefix-dev/pixi/releases/download/v{PIXI_VERSION}"

_BareMd5 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$", min_length=32, max_length=32)]
_BareSha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$", min_length=64, max_length=64)]
_U64 = Annotated[int, Field(strict=True, ge=0, le=2**64 - 1)]
_I64 = Annotated[int, Field(strict=True, ge=-(2**63), le=2**63 - 1)]


class PixiDistribution(_StrictFrozenModel):
    filename: str
    url: str
    sha256: Sha256Digest


PIXI_DISTRIBUTIONS: Mapping[ExecutionPlatform, PixiDistribution] = MappingProxyType(
    {
        ExecutionPlatform.LINUX_AMD64: PixiDistribution(
            filename="pixi-x86_64-unknown-linux-musl.tar.gz",
            url=f"{_PIXI_RELEASE_BASE}/pixi-x86_64-unknown-linux-musl.tar.gz",
            sha256="sha256:f61a9546898cc1caad1956d1b5bba0408de5a24854b648631c0b49555520ed42",
        ),
        ExecutionPlatform.LINUX_ARM64: PixiDistribution(
            filename="pixi-aarch64-unknown-linux-musl.tar.gz",
            url=f"{_PIXI_RELEASE_BASE}/pixi-aarch64-unknown-linux-musl.tar.gz",
            sha256="sha256:b2b21272578600086e92f4e1d0e42cb7409c8e541688b9ea61aed7dd6a07a5ad",
        ),
    }
)

_PIXI_PLATFORM = MappingProxyType(
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
    json.loads(content, object_pairs_hook=_unique_json_object)
    return _PIXI_LIST_ADAPTER.validate_json(content)


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


def admit_pixi_records(
    records: Iterable[PixiListRecord],
    *,
    environment_name: str,
    platform: ExecutionPlatform,
    native_lock_sha256: Sha256Digest,
) -> PlatformLock:
    """Admit decoded transport records into the immutable BioNodulo contract."""

    decoded = tuple(records)
    if not decoded:
        raise ValueError("Pixi selected-platform output must not be empty")
    resolver_platform = _PIXI_PLATFORM[platform]
    artifacts: list[LockedArtifact] = []
    for record in decoded:
        if isinstance(record, PixiCondaListRecord):
            artifacts.append(_admit_conda(record, resolver_platform=resolver_platform))
        elif isinstance(record, PixiPypiListRecord):
            artifacts.append(_admit_pypi(record))
        else:
            raise TypeError(f"unsupported decoded Pixi record: {type(record).__name__}")
    artifacts.sort(key=lambda artifact: artifact.name)
    distribution = PIXI_DISTRIBUTIONS[platform]
    return PlatformLock(
        platform=platform,
        environment_name=environment_name,
        resolver_platform=resolver_platform,
        resolver=ResolverIdentity(
            name="pixi",
            version=PIXI_VERSION,
            config_digest=distribution.sha256,
        ),
        native_lock_sha256=native_lock_sha256,
        artifacts=tuple(artifacts),
    )


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(loader: _UniqueKeyLoader, node: yaml.MappingNode) -> dict[object, object]:
    loader.flatten_mapping(node)
    result: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=False)
        if key in result:
            raise ValueError(f"pixi.lock contains duplicate key: {key}")
        result[key] = loader.construct_object(value_node, deep=False)
    return result


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _validate_pixi_lock(
    content: bytes,
    *,
    environment_name: str,
    resolver_platform: str,
) -> tuple[tuple[str, str], ...]:
    if type(content) is not bytes:
        raise TypeError("pixi.lock content must be exact captured bytes")
    try:
        document = yaml.load(content.decode("utf-8"), Loader=_UniqueKeyLoader)
    except (UnicodeDecodeError, ValueError, yaml.YAMLError) as error:
        raise ValueError(f"pixi.lock must be unique-key UTF-8 YAML: {error}") from error
    if type(document) is not dict or type(document.get("version")) is not int or document["version"] != 7:
        raise ValueError("pixi.lock format must be exactly version 7")
    environments = document.get("environments")
    if type(environments) is not dict or environment_name not in environments:
        raise ValueError("pixi.lock must contain the exact selected environment_name")
    environment = environments[environment_name]
    packages = environment.get("packages") if type(environment) is dict else None
    if type(packages) is not dict or resolver_platform not in packages:
        raise ValueError(f"pixi.lock must contain selected platform {resolver_platform}")
    selected_packages = packages[resolver_platform]
    if type(selected_packages) is not list or not selected_packages:
        raise ValueError(f"pixi.lock selected platform {resolver_platform} must contain packages")
    references: list[tuple[str, str]] = []
    for reference in selected_packages:
        if type(reference) is not dict or len(reference) != 1:
            raise ValueError("pixi.lock selected platform package references must be single-key mappings")
        kind, url = next(iter(reference.items()))
        if kind not in ("conda", "pypi") or type(url) is not str:
            raise ValueError("pixi.lock selected platform package references must bind Conda or PyPI URLs")
        references.append((kind, url))
    return tuple(sorted(references))


def compile_pixi_platform_lock(
    pixi_list_content: bytes,
    pixi_lock_content: bytes,
    *,
    environment_name: str,
    platform: ExecutionPlatform,
) -> PlatformLock:
    """Compile captured Pixi list and native lock bytes into a PlatformLock."""

    resolver_platform = _PIXI_PLATFORM[platform]
    selected_references = _validate_pixi_lock(
        pixi_lock_content,
        environment_name=environment_name,
        resolver_platform=resolver_platform,
    )
    native_digest = "sha256:" + hashlib.sha256(pixi_lock_content).hexdigest()
    records = decode_pixi_list_json(pixi_list_content)
    admitted = admit_pixi_records(
        records,
        environment_name=environment_name,
        platform=platform,
        native_lock_sha256=native_digest,
    )
    listed_references = tuple(sorted((artifact.kind, artifact.url) for artifact in admitted.artifacts))
    if listed_references != selected_references:
        raise ValueError("Pixi list output does not match selected platform package references")
    return admitted


PixiRunner: TypeAlias = Callable[[tuple[str, ...], Path], bytes]


def _workspace_lock_content(workspace_root: Path) -> bytes:
    try:
        return (workspace_root / "pixi.lock").read_bytes()
    except OSError as error:
        raise ValueError("workspace pixi.lock must be readable") from error


def compile_pixi_platform_lock_with_runner(
    runner: PixiRunner,
    *,
    workspace_root: Path,
    pixi_lock_content: bytes,
    environment_name: str,
    platform: ExecutionPlatform,
) -> PlatformLock:
    """Run locked Pixi commands through an injected runner, then compile bytes."""

    _validate_pixi_lock(
        pixi_lock_content,
        environment_name=environment_name,
        resolver_platform=_PIXI_PLATFORM[platform],
    )
    if _workspace_lock_content(workspace_root) != pixi_lock_content:
        raise ValueError("supplied pixi.lock bytes must equal workspace pixi.lock")
    runner(
        ("pixi", "install", "--locked", "--environment", environment_name),
        workspace_root,
    )
    if _workspace_lock_content(workspace_root) != pixi_lock_content:
        raise ValueError("workspace pixi.lock changed during locked Pixi commands")
    list_content = runner(
        (
            "pixi",
            "list",
            "--locked",
            "--no-install",
            "--json",
            "--environment",
            environment_name,
            "--platform",
            _PIXI_PLATFORM[platform],
        ),
        workspace_root,
    )
    if _workspace_lock_content(workspace_root) != pixi_lock_content:
        raise ValueError("workspace pixi.lock changed during locked Pixi commands")
    return compile_pixi_platform_lock(
        list_content,
        pixi_lock_content,
        environment_name=environment_name,
        platform=platform,
    )
