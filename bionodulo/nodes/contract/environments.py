"""Declarative, non-executing environment contracts."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from enum import StrEnum
from typing import Annotated, Literal, Self, TypeAlias
from urllib.parse import unquote, urlsplit

from pydantic import Field, StringConstraints, ValidationInfo, field_validator, model_validator

from bionodulo.nodes.contract._package_identity import (
    parse_pypi_wheel_tags,
    parse_python_runtime_release,
    validate_pypi_package_name,
    validate_pypi_wheel_identity,
)
from bionodulo.nodes.contract.artifacts import ArtifactId, _StrictFrozenModel


_PACKAGE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_EXACT_CONSTRAINT_RE = re.compile(r"^==(?P<version>[0-9][0-9A-Za-z._+-]{0,127})$")
_RANGE_CONSTRAINT_RE = re.compile(
    r"^(?P<lower_op>>=|>)(?P<lower>[0-9]+(?:\.[0-9]+)*),"
    r"(?P<upper_op><=|<)(?P<upper>[0-9]+(?:\.[0-9]+)*)$"
)
_RESOLVER_PLATFORM_RE = re.compile(r"^[a-z0-9][a-z0-9._/-]{0,63}$")
_EXACT_VERSION_RE = re.compile(
    r"^[0-9]+(?:\.[0-9]+)*(?:"
    r"[A-Za-z][0-9A-Za-z]*(?:[._+-][0-9A-Za-z]+)*"
    r"|\.(?:alpha|beta|dev|p|patch|post|pre|preview|r|rc|rev)[0-9A-Za-z]*"
    r"(?:[._+-][0-9A-Za-z]+)*"
    r"|[-+_][0-9A-Za-z]+(?:[._+-][0-9A-Za-z]+)*"
    r")?$",
    re.IGNORECASE,
)
_BUILD_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._+-]{0,255}$")
_FILENAME_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._+-]{0,511}$")
_HOST_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)
_MODULE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
_R_PACKAGE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9.]{0,127}$")
_PACKAGE_REQUEST_RE = re.compile(r"^(?P<name>[a-z0-9][a-z0-9._-]{0,127})(?P<constraint>==|>=|>).+$")
_OCI_REFERENCE_RE = re.compile(
    r"^(?P<registry>[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?(?::[0-9]{1,5})?)/"
    r"(?P<path>[a-z0-9]+(?:[._-][a-z0-9]+)*(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)*)"
    r"@sha256:[0-9a-f]{64}$"
)


def _canonical_digest(value: _StrictFrozenModel) -> str:
    payload = json.dumps(
        value.model_dump(mode="json"),
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _numeric_version(value: str) -> tuple[int, ...]:
    components = tuple(int(part) for part in value.split("."))
    while len(components) > 1 and components[-1] == 0:
        components = components[:-1]
    return components


def _format_numeric_version(value: tuple[int, ...]) -> str:
    return ".".join(str(component) for component in value)


def _version_satisfies(version: str, constraint: str) -> bool:
    exact = _EXACT_CONSTRAINT_RE.fullmatch(constraint)
    if exact is not None:
        return version == exact.group("version")
    bounds = _RANGE_CONSTRAINT_RE.fullmatch(constraint)
    if bounds is None or re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", version) is None:
        return False
    locked = _numeric_version(version)
    lower = _numeric_version(bounds.group("lower"))
    upper = _numeric_version(bounds.group("upper"))
    width = max(len(locked), len(lower), len(upper))
    locked += (0,) * (width - len(locked))
    lower += (0,) * (width - len(lower))
    upper += (0,) * (width - len(upper))
    lower_ok = locked >= lower if bounds.group("lower_op") == ">=" else locked > lower
    upper_ok = locked <= upper if bounds.group("upper_op") == "<=" else locked < upper
    return lower_ok and upper_ok


def _validate_constraint(value: str) -> str:
    if _EXACT_CONSTRAINT_RE.fullmatch(value) is not None:
        return value
    match = _RANGE_CONSTRAINT_RE.fullmatch(value)
    if match is None:
        raise ValueError("constraint must be an exact ==version pin or a numeric lower,upper range")
    lower = _numeric_version(match.group("lower"))
    upper = _numeric_version(match.group("upper"))
    width = max(len(lower), len(upper))
    if lower + (0,) * (width - len(lower)) >= upper + (0,) * (width - len(upper)):
        raise ValueError("constraint range must have a lower bound below its upper bound")
    return (
        f"{match.group('lower_op')}{_format_numeric_version(lower)},"
        f"{match.group('upper_op')}{_format_numeric_version(upper)}"
    )


CanonicalPackageName = Annotated[str, StringConstraints(min_length=1, max_length=128)]
VersionConstraint = Annotated[str, StringConstraints(min_length=1, max_length=256)]
Sha256Digest = Annotated[
    str,
    StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$", min_length=71, max_length=71),
]
ExactVersion = Annotated[str, StringConstraints(min_length=1, max_length=128)]
ProbeArgument = Annotated[str, StringConstraints(max_length=4096)]
VersionLinePrefix = Annotated[str, StringConstraints(min_length=1, max_length=256)]


def _validate_exact_version(value: str) -> str:
    if _EXACT_VERSION_RE.fullmatch(value) is None or value.lower() == "latest":
        raise ValueError("version must be an exact upstream version")
    return value


def _validate_https_url(value: str, *, require_path: bool) -> str:
    try:
        value.encode("ascii")
    except UnicodeEncodeError as error:
        raise ValueError("URL must use canonical ASCII spelling") from error
    if "%" in value or "\\" in value or any(ord(character) <= 32 or ord(character) == 127 for character in value):
        raise ValueError("URL must use canonical ASCII spelling without escapes")
    if not value.startswith("https://"):
        raise ValueError("URL must start with literal lowercase https://")
    if "?" in value or "#" in value:
        raise ValueError("URL must not contain query or fragment delimiters")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise ValueError("URL is malformed") from error
    if parsed.scheme != "https" or not parsed.netloc or parsed.hostname is None:
        raise ValueError("URL must use HTTPS with an explicit hostname")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URL must not contain user information")
    raw_host = parsed.netloc.rsplit(":", 1)[0] if port is not None else parsed.netloc
    if raw_host != parsed.hostname or _HOST_RE.fullmatch(raw_host) is None:
        raise ValueError("URL hostname must be canonical lowercase DNS")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("URL port must be between 1 and 65535")
    if port == 443:
        raise ValueError("URL must omit the default HTTPS port")
    canonical_netloc = parsed.hostname
    if port is not None:
        raw_port = parsed.netloc.rsplit(":", 1)[1]
        if raw_port != str(port):
            raise ValueError("URL port must use canonical decimal spelling")
        canonical_netloc = f"{canonical_netloc}:{port}"
    if parsed.netloc != canonical_netloc:
        raise ValueError("URL netloc must use canonical spelling")
    if not parsed.path:
        raise ValueError("URL must declare an explicit canonical path; use / for root")
    if require_path and parsed.path == "/":
        raise ValueError("URL must have an immutable resource path")
    segments = parsed.path.split("/")
    if "" in segments[1:-1] or any(segment in (".", "..") for segment in segments):
        raise ValueError("URL path must be canonical and traversal-free")
    if any(ord(character) < 32 or ord(character) == 127 for character in parsed.path):
        raise ValueError("URL path must not contain control characters")
    if value != f"https://{canonical_netloc}{parsed.path}":
        raise ValueError("URL must use its single canonical raw spelling")
    return value


def _validate_locator(value: str) -> str:
    if "\x00" in value or "\\" in value or "/" not in value or value.startswith("/") or value.endswith("/"):
        raise ValueError("locator must be an environment-root-relative POSIX path, not a PATH lookup name")
    segments = value.split("/")
    if not segments or any(segment in ("", ".", "..") for segment in segments):
        raise ValueError("locator must be a canonical traversal-free POSIX path")
    if any(any(ord(character) < 32 or ord(character) == 127 for character in segment) for segment in segments):
        raise ValueError("locator must not contain control characters")
    return value


def _validate_oci_reference(value: str) -> str:
    match = _OCI_REFERENCE_RE.fullmatch(value)
    if match is None:
        raise ValueError("image must be an explicit registry reference with @sha256 digest")
    registry = match.group("registry")
    registry_host = registry.rsplit(":", 1)[0] if ":" in registry else registry
    if registry_host != "localhost":
        try:
            address = ipaddress.ip_address(registry_host)
        except ValueError:
            if _HOST_RE.fullmatch(registry_host) is None:
                raise ValueError("image registry must be explicit canonical DNS, localhost, or IPv4")
        else:
            if not isinstance(address, ipaddress.IPv4Address) or str(address) != registry_host:
                raise ValueError("image registry IPv4 address must use canonical dotted-decimal spelling")
    if ":" in registry:
        raw_port = registry.rsplit(":", 1)[1]
        port = int(raw_port)
        if not 1 <= port <= 65535 or raw_port != str(port):
            raise ValueError("registry port must use canonical decimal spelling between 1 and 65535")
    return value


def _parse_package_request(value: str) -> PackageRequirement:
    match = _PACKAGE_REQUEST_RE.fullmatch(value)
    if match is None:
        raise ValueError("package string must contain an explicit exact or bounded constraint")
    constraint_start = match.start("constraint")
    return PackageRequirement(name=value[:constraint_start], constraint=value[constraint_start:])


def _parse_package_collection(value: object, info: ValidationInfo) -> object:
    if type(value) is tuple or (info.mode == "json" and type(value) is list):
        parsed = [_parse_package_request(item) if type(item) is str else item for item in value]
        return tuple(parsed)
    return value


def _validate_unique_ordered_strings(values: tuple[str, ...], *, label: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{label} must be unique")
    if values != tuple(sorted(values)):
        raise ValueError(f"{label} must be canonically ordered")


def _validate_package_declarations(
    packages: tuple[PackageRequirement, ...],
    urls: tuple[str, ...],
    *,
    url_label: str,
) -> None:
    _validate_unique_ordered_strings(
        tuple(package.name for package in packages),
        label="package names",
    )
    _validate_unique_ordered_strings(urls, label=url_label)


def _validate_probe_namespace(
    executable_probes: tuple[ExecutableProbe, ...],
    language_probes: tuple[ImportProbe | RPackageProbe, ...],
) -> None:
    probe_ids = tuple(probe.probe_id for probe in (*executable_probes, *language_probes))
    if len(set(probe_ids)) != len(probe_ids):
        raise ValueError("probe IDs must be unique within an environment")


class ExecutionPlatform(StrEnum):
    LINUX_AMD64 = "linux/amd64"
    LINUX_ARM64 = "linux/arm64"


_RESOLVER_PLATFORM_BY_EXECUTION = {
    ExecutionPlatform.LINUX_AMD64: "linux-64",
    ExecutionPlatform.LINUX_ARM64: "linux-aarch64",
}


def _wheel_tag_matches_platform(tag_platform: str, platform: ExecutionPlatform) -> bool:
    if tag_platform == "any":
        return True
    if not tag_platform.startswith(("linux_", "manylinux", "musllinux")):
        return False
    if platform is ExecutionPlatform.LINUX_AMD64:
        return tag_platform.endswith("_x86_64")
    return tag_platform.endswith(("_aarch64", "_arm64"))


def _wheel_tag_matches_python(
    interpreter: str,
    abi: str,
    runtime_version: tuple[int, int],
) -> bool:
    if interpreter.startswith("py"):
        digits = interpreter[2:]
        if digits == str(runtime_version[0]):
            return True
    elif interpreter.startswith("cp"):
        digits = interpreter[2:]
    else:
        return False
    if not digits.isdigit() or len(digits) < 2:
        return False
    tagged_version = (int(digits[0]), int(digits[1:]))
    if abi == "abi3":
        return tagged_version[0] == runtime_version[0] and tagged_version <= runtime_version
    return tagged_version == runtime_version


class PackageRequirement(_StrictFrozenModel):
    """A deliberately small exact-or-bounded package request."""

    name: CanonicalPackageName
    constraint: VersionConstraint

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        if _PACKAGE_NAME_RE.fullmatch(value) is None:
            raise ValueError("package name must be canonical lowercase ASCII")
        return value

    @field_validator("constraint")
    @classmethod
    def _validate_version_constraint(cls, value: str) -> str:
        return _validate_constraint(value)

    def as_string(self) -> str:
        return self.name + self.constraint


class VersionRequest(_StrictFrozenModel):
    constraint: VersionConstraint

    @field_validator("constraint")
    @classmethod
    def _validate_version_constraint(cls, value: str) -> str:
        return _validate_constraint(value)


class ResolverIdentity(_StrictFrozenModel):
    name: CanonicalPackageName
    version: ExactVersion
    config_digest: Sha256Digest

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        if _PACKAGE_NAME_RE.fullmatch(value) is None:
            raise ValueError("resolver name must be canonical lowercase ASCII")
        return value

    @field_validator("version")
    @classmethod
    def _validate_version(cls, value: str) -> str:
        return _validate_exact_version(value)


class _LockedArtifactBase(_StrictFrozenModel):
    name: CanonicalPackageName
    version: ExactVersion
    filename: Annotated[str, StringConstraints(min_length=1, max_length=512)]
    url: Annotated[str, StringConstraints(min_length=1, max_length=2048)]
    sha256: Sha256Digest
    size_bytes: Annotated[int, Field(strict=True, ge=1, le=2**50)] | None = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        if _PACKAGE_NAME_RE.fullmatch(value) is None:
            raise ValueError("locked artifact name must be canonical lowercase ASCII")
        return value

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        return _validate_https_url(value, require_path=True)

    @model_validator(mode="after")
    def _validate_url_identity(self) -> Self:
        filename = unquote(urlsplit(self.url).path).rsplit("/", 1)[-1]
        if filename != self.filename:
            raise ValueError("artifact URL basename must equal its explicit filename")
        return self


class CondaLockedArtifact(_LockedArtifactBase):
    kind: Literal["conda"] = "conda"
    build: Annotated[str, StringConstraints(min_length=1, max_length=256)]

    @field_validator("version")
    @classmethod
    def _validate_version(cls, value: str) -> str:
        return _validate_exact_version(value)

    @field_validator("filename")
    @classmethod
    def _validate_filename(cls, value: str) -> str:
        if _FILENAME_RE.fullmatch(value) is None:
            raise ValueError("Conda filename must be a canonical ASCII basename")
        return value

    @field_validator("build")
    @classmethod
    def _validate_build(cls, value: str) -> str:
        if _BUILD_RE.fullmatch(value) is None:
            raise ValueError("build must be an exact canonical build identifier")
        return value

    @model_validator(mode="after")
    def _validate_conda_binary_identity(self) -> Self:
        if self.filename.endswith(".tar.bz2"):
            suffix = ".tar.bz2"
        elif self.filename.endswith(".conda"):
            suffix = ".conda"
        else:
            raise ValueError("conda artifact must be a .conda or .tar.bz2 binary")
        expected = f"{self.name}-{self.version}-{self.build}{suffix}"
        if self.filename != expected:
            raise ValueError("conda artifact filename must match its name, version, and build")
        return self


class PypiLockedArtifact(_LockedArtifactBase):
    kind: Literal["pypi"] = "pypi"

    @field_validator("name")
    @classmethod
    def _validate_normalized_name(cls, value: str) -> str:
        validate_pypi_package_name(value)
        return value

    @model_validator(mode="after")
    def _validate_wheel_identity(self) -> Self:
        validate_pypi_wheel_identity(
            name=self.name,
            version=self.version,
            filename=self.filename,
        )
        return self


LockedArtifact: TypeAlias = Annotated[
    CondaLockedArtifact | PypiLockedArtifact,
    Field(discriminator="kind"),
]


class PlatformLock(_StrictFrozenModel):
    platform: ExecutionPlatform
    environment_name: ArtifactId
    resolver_platform: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    resolver: ResolverIdentity
    native_lock_sha256: Sha256Digest
    artifacts: Annotated[tuple[LockedArtifact, ...], Field(min_length=1, max_length=4096)]

    @field_validator("resolver_platform")
    @classmethod
    def _validate_resolver_platform(cls, value: str) -> str:
        if _RESOLVER_PLATFORM_RE.fullmatch(value) is None:
            raise ValueError("resolver platform must be canonical lowercase ASCII")
        return value

    @model_validator(mode="after")
    def _validate_artifacts(self) -> Self:
        expected_resolver_platform = _RESOLVER_PLATFORM_BY_EXECUTION[self.platform]
        if self.resolver_platform != expected_resolver_platform:
            raise ValueError(
                f"resolver platform must be {expected_resolver_platform} for execution platform {self.platform.value}"
            )
        names = tuple(artifact.name for artifact in self.artifacts)
        if len(set(names)) != len(names):
            raise ValueError("locked artifact names must be unique")
        if names != tuple(sorted(names)):
            raise ValueError("locked artifacts must be canonically ordered by name")
        for label, identities in (
            ("urls", tuple(artifact.url for artifact in self.artifacts)),
            ("filenames", tuple(artifact.filename for artifact in self.artifacts)),
            ("sha256 identities", tuple(artifact.sha256 for artifact in self.artifacts)),
        ):
            if len(set(identities)) != len(identities):
                raise ValueError(f"locked artifact {label} must be unique")
        for artifact in self.artifacts:
            if isinstance(artifact, CondaLockedArtifact):
                url_subdir = urlsplit(artifact.url).path.rsplit("/", 2)[-2]
                if url_subdir not in (expected_resolver_platform, "noarch"):
                    raise ValueError(
                        f"Conda artifact URL subdir {url_subdir} does not match selected platform "
                        f"{expected_resolver_platform}"
                    )
        wheels = tuple(artifact for artifact in self.artifacts if isinstance(artifact, PypiLockedArtifact))
        if wheels:
            python = next(
                (
                    artifact
                    for artifact in self.artifacts
                    if isinstance(artifact, CondaLockedArtifact) and artifact.name == "python"
                ),
                None,
            )
            if python is None:
                raise ValueError("PyPI wheel admission requires a locked Python runtime artifact")
            runtime_release = parse_python_runtime_release(python.version)
            if len(runtime_release) < 2:
                raise ValueError("locked Python runtime must declare major and minor versions")
            runtime_version = (runtime_release[0], runtime_release[1])
            for wheel in wheels:
                tags = parse_pypi_wheel_tags(wheel.filename)
                if not any(
                    _wheel_tag_matches_platform(tag_platform, self.platform)
                    and _wheel_tag_matches_python(interpreter, abi, runtime_version)
                    for interpreter, abi, tag_platform in tags
                ):
                    raise ValueError(
                        f"PyPI wheel {wheel.filename} is incompatible with execution platform "
                        f"{self.platform.value} and locked Python {python.version}"
                    )
        return self

    def lock_digest(self) -> str:
        return _canonical_digest(self)


def _validate_runtime_artifacts(
    locks: tuple[PlatformLock, ...],
    *,
    runtime_name: str,
    request: VersionRequest,
) -> None:
    for lock in locks:
        runtime = next((artifact for artifact in lock.artifacts if artifact.name == runtime_name), None)
        if runtime is None or not _version_satisfies(runtime.version, request.constraint):
            raise ValueError(
                f"lock for {lock.platform.value} must contain exactly one {runtime_name} runtime artifact "
                f"satisfying {request.constraint}"
            )


class ExecutableProbe(_StrictFrozenModel):
    probe_id: ArtifactId
    locator: Annotated[str, StringConstraints(min_length=1, max_length=1024)]
    version_arguments: Annotated[tuple[ProbeArgument, ...], Field(min_length=1, max_length=16)]
    version_line_prefix: VersionLinePrefix
    expected_version: ExactVersion
    fingerprint: Sha256Digest | None = None

    @field_validator("locator")
    @classmethod
    def _validate_executable_locator(cls, value: str) -> str:
        return _validate_locator(value)

    @field_validator("version_arguments")
    @classmethod
    def _validate_version_arguments(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(
            "\x00" in argument or any(ord(character) < 32 or ord(character) == 127 for character in argument)
            for argument in value
        ):
            raise ValueError("probe arguments must not contain control characters")
        return value

    @field_validator("version_line_prefix")
    @classmethod
    def _validate_version_line_prefix(cls, value: str) -> str:
        try:
            value.encode("ascii")
        except UnicodeEncodeError as error:
            raise ValueError("version line prefix must use literal ASCII") from error
        if any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise ValueError("version line prefix must not contain control characters")
        return value

    @field_validator("expected_version")
    @classmethod
    def _validate_expected_version(cls, value: str) -> str:
        return _validate_exact_version(value)


class ImportProbe(_StrictFrozenModel):
    probe_id: ArtifactId
    module: Annotated[str, StringConstraints(min_length=1, max_length=256)]
    expected_version: ExactVersion

    @field_validator("module")
    @classmethod
    def _validate_module(cls, value: str) -> str:
        if _MODULE_RE.fullmatch(value) is None:
            raise ValueError("module must be an absolute dotted import name")
        return value

    @field_validator("expected_version")
    @classmethod
    def _validate_version(cls, value: str) -> str:
        return _validate_exact_version(value)


class RPackageProbe(_StrictFrozenModel):
    probe_id: ArtifactId
    package: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    expected_version: ExactVersion

    @field_validator("package")
    @classmethod
    def _validate_package(cls, value: str) -> str:
        if _R_PACKAGE_RE.fullmatch(value) is None:
            raise ValueError("R package must be a canonical package name")
        return value

    @field_validator("expected_version")
    @classmethod
    def _validate_version(cls, value: str) -> str:
        return _validate_exact_version(value)


class ContainerImageLock(_StrictFrozenModel):
    platform: ExecutionPlatform
    resolver_platform: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    index_image: Annotated[str, StringConstraints(min_length=1, max_length=512)]
    image: Annotated[str, StringConstraints(min_length=1, max_length=512)]

    @field_validator("resolver_platform")
    @classmethod
    def _validate_resolver_platform(cls, value: str) -> str:
        if _RESOLVER_PLATFORM_RE.fullmatch(value) is None:
            raise ValueError("resolver platform must be canonical lowercase ASCII")
        return value

    @field_validator("index_image", "image")
    @classmethod
    def _validate_image(cls, value: str) -> str:
        return _validate_oci_reference(value)

    @model_validator(mode="after")
    def _validate_platform_identity(self) -> Self:
        expected = _RESOLVER_PLATFORM_BY_EXECUTION[self.platform]
        if self.resolver_platform != expected:
            raise ValueError(f"resolver platform must be {expected} for execution platform {self.platform.value}")
        return self

    def lock_digest(self) -> str:
        return _canonical_digest(self)


class _EnvironmentBase(_StrictFrozenModel):
    environment_id: ArtifactId
    platforms: Annotated[tuple[ExecutionPlatform, ...], Field(min_length=1, max_length=2)]
    executable_probes: Annotated[tuple[ExecutableProbe, ...], Field(max_length=256)] = ()

    @model_validator(mode="after")
    def _validate_common_declaration(self) -> Self:
        platform_values = tuple(platform.value for platform in self.platforms)
        _validate_unique_ordered_strings(platform_values, label="platforms")
        _validate_unique_ordered_strings(
            tuple(probe.probe_id for probe in self.executable_probes),
            label="executable probe IDs",
        )
        return self

    def environment_digest(self) -> str:
        return _canonical_digest(self)


class _LockedPackageEnvironment(_EnvironmentBase):
    packages: Annotated[tuple[PackageRequirement, ...], Field(max_length=4096)] = ()
    locks: Annotated[tuple[PlatformLock, ...], Field(max_length=2)] = ()

    @field_validator("packages", mode="before")
    @classmethod
    def _parse_packages(cls, value: object, info: ValidationInfo) -> object:
        return _parse_package_collection(value, info)

    @model_validator(mode="after")
    def _validate_platform_locks(self) -> Self:
        lock_platforms = tuple(lock.platform.value for lock in self.locks)
        _validate_unique_ordered_strings(lock_platforms, label="lock platforms")
        if len({lock.environment_name for lock in self.locks}) > 1:
            raise ValueError("all PlatformLocks in one environment must share the same environment_name")
        declared = set(self.platforms)
        if any(lock.platform not in declared for lock in self.locks):
            raise ValueError("locks may cover only declared platforms")
        for lock in self.locks:
            inventory = {artifact.name: artifact for artifact in lock.artifacts}
            for request in self.packages:
                locked = inventory.get(request.name)
                if locked is None or not _version_satisfies(
                    locked.version,
                    request.constraint,
                ):
                    raise ValueError(
                        f"lock for {lock.platform.value} does not satisfy package request {request.as_string()}"
                    )
        return self

    @property
    def is_fully_locked(self) -> bool:
        return bool(self.locks) and {lock.platform for lock in self.locks} == set(self.platforms)


class PixiEnvironment(_LockedPackageEnvironment):
    kind: Literal["pixi"] = "pixi"
    channels: Annotated[tuple[str, ...], Field(max_length=64)] = ()
    import_probes: Annotated[tuple[ImportProbe, ...], Field(max_length=256)] = ()

    @field_validator("channels")
    @classmethod
    def _validate_channels(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for url in value:
            _validate_https_url(url, require_path=False)
        return value

    @model_validator(mode="after")
    def _validate_pixi_declaration(self) -> Self:
        _validate_package_declarations(self.packages, self.channels, url_label="channels")
        _validate_unique_ordered_strings(
            tuple(probe.probe_id for probe in self.import_probes),
            label="import probe IDs",
        )
        _validate_probe_namespace(self.executable_probes, self.import_probes)
        return self


class PythonEnvironment(_LockedPackageEnvironment):
    kind: Literal["python"] = "python"
    python_version: VersionRequest
    indexes: Annotated[tuple[str, ...], Field(max_length=64)] = ()
    import_probes: Annotated[tuple[ImportProbe, ...], Field(max_length=256)] = ()

    @field_validator("python_version", mode="before")
    @classmethod
    def _parse_python_version(cls, value: object) -> object:
        if type(value) is str:
            return VersionRequest(constraint=value)
        return value

    @field_validator("indexes")
    @classmethod
    def _validate_indexes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for url in value:
            _validate_https_url(url, require_path=False)
        return value

    @model_validator(mode="after")
    def _validate_python_declaration(self) -> Self:
        _validate_package_declarations(self.packages, self.indexes, url_label="indexes")
        _validate_unique_ordered_strings(
            tuple(probe.probe_id for probe in self.import_probes),
            label="import probe IDs",
        )
        _validate_probe_namespace(self.executable_probes, self.import_probes)
        _validate_runtime_artifacts(self.locks, runtime_name="python", request=self.python_version)
        return self


class REnvironment(_LockedPackageEnvironment):
    kind: Literal["r"] = "r"
    r_version: VersionRequest
    repositories: Annotated[tuple[str, ...], Field(max_length=64)] = ()
    package_probes: Annotated[tuple[RPackageProbe, ...], Field(max_length=256)] = ()

    @field_validator("r_version", mode="before")
    @classmethod
    def _parse_r_version(cls, value: object) -> object:
        if type(value) is str:
            return VersionRequest(constraint=value)
        return value

    @field_validator("repositories")
    @classmethod
    def _validate_repositories(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for url in value:
            _validate_https_url(url, require_path=False)
        return value

    @model_validator(mode="after")
    def _validate_r_declaration(self) -> Self:
        _validate_package_declarations(
            self.packages,
            self.repositories,
            url_label="repositories",
        )
        _validate_unique_ordered_strings(
            tuple(probe.probe_id for probe in self.package_probes),
            label="R package probe IDs",
        )
        _validate_probe_namespace(self.executable_probes, self.package_probes)
        _validate_runtime_artifacts(self.locks, runtime_name="r-base", request=self.r_version)
        return self


class ContainerEnvironment(_EnvironmentBase):
    kind: Literal["container"] = "container"
    image: Annotated[str, StringConstraints(min_length=1, max_length=512)]
    image_locks: Annotated[tuple[ContainerImageLock, ...], Field(max_length=2)] = ()

    @field_validator("image")
    @classmethod
    def _validate_image(cls, value: str) -> str:
        return _validate_oci_reference(value)

    @model_validator(mode="after")
    def _validate_image_locks(self) -> Self:
        lock_platforms = tuple(lock.platform.value for lock in self.image_locks)
        _validate_unique_ordered_strings(lock_platforms, label="image lock platforms")
        declared = set(self.platforms)
        if any(lock.platform not in declared for lock in self.image_locks):
            raise ValueError("image locks may cover only declared platforms")
        if any(lock.index_image != self.image for lock in self.image_locks):
            raise ValueError("image lock index_image must exactly equal the declared image index")
        repository = self.image.rsplit("@", 1)[0]
        if any(lock.image.rsplit("@", 1)[0] != repository for lock in self.image_locks):
            raise ValueError("image locks must use the declared image repository")
        return self

    @property
    def is_fully_locked(self) -> bool:
        return bool(self.image_locks) and {lock.platform for lock in self.image_locks} == set(self.platforms)


EnvironmentSpec: TypeAlias = Annotated[
    PixiEnvironment | PythonEnvironment | REnvironment | ContainerEnvironment,
    Field(discriminator="kind"),
]
