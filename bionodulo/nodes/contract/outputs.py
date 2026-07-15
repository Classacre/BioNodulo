import ctypes
import errno
import fnmatch
import json
import math
import os
import re
import stat
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Annotated, Any, BinaryIO, Final, Literal, Self, TypeAlias, cast

from pydantic import Field, field_validator, model_validator

from bionodulo.nodes.contract.artifacts import (
    ArtifactContainer,
    ArtifactId,
    Cardinality,
    _StrictFrozenModel,
)


MAX_OUTPUT_SPECS: Final = 1_024
MAX_GLOB_MATCHES: Final = 10_000
MAX_GLOB_SCAN_ENTRIES: Final = 100_000
MAX_DIRECTORY_ENTRIES: Final = 100_000
MAX_STDOUT_BYTES: Final = 16 * 1024 * 1024
MAX_CONTENT_VALIDATOR_BYTES: Final = 16 * 1024 * 1024

_DEFAULT_STDOUT_BYTES: Final = 1024 * 1024
_DEFAULT_CONTENT_BYTES: Final = 1024 * 1024
_DEFAULT_DIRECTORY_ENTRIES: Final = 10_000
_MAX_RELATIVE_PATH_BYTES: Final = 4_096
_MAX_PATH_COMPONENTS: Final = 256
_MAX_DIRECTORY_DEPTH: Final = 256
_AT_EMPTY_PATH: Final = 0x1000
_EXTENSION_RE = re.compile(r"^\.[A-Za-z0-9][A-Za-z0-9_+-]*(?:\.[A-Za-z0-9][A-Za-z0-9_+-]*)*$")
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")

_GlobBound = Annotated[int, Field(ge=0, le=MAX_GLOB_MATCHES)]
_DirectoryBound = Annotated[int, Field(ge=0, le=MAX_DIRECTORY_ENTRIES)]
_StdoutBound = Annotated[int, Field(ge=1, le=MAX_STDOUT_BYTES)]
_ContentBound = Annotated[int, Field(ge=1, le=MAX_CONTENT_VALIDATOR_BYTES)]
_NonnegativeInt = Annotated[int, Field(ge=0)]
_ConditionValue: TypeAlias = str | int | float | bool | None


class OutputCollectionError(ValueError):
    """Raised when a declared output cannot be collected safely."""


class OutputRootError(OutputCollectionError):
    """Raised when the trusted output root is invalid."""


class OutputIdentityError(OutputCollectionError):
    """Raised when a collected object is no longer the same object."""


class MissingOutputError(FileNotFoundError):
    """Raised when a required declared output is absent."""


def _validate_relative_path(value: str, *, pattern: bool) -> str:
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError("must be valid UTF-8") from error
    if not value or "\x00" in value:
        raise ValueError("must be a nonempty relative path without NUL bytes")
    if value.startswith("/") or "\\" in value or _WINDOWS_DRIVE_RE.match(value):
        raise ValueError("must be a platform-independent relative POSIX path")

    components = value.split("/")
    if len(encoded) > _MAX_RELATIVE_PATH_BYTES or len(components) > _MAX_PATH_COMPONENTS:
        raise ValueError("relative path exceeds safe length bounds")
    if any(component in ("", ".", "..") for component in components):
        raise ValueError("must not contain empty, dot, or traversal components")
    if pattern:
        for component in components:
            if "**" in component:
                raise ValueError("recursive glob patterns are not allowed")
            if component.count("[") != component.count("]"):
                raise ValueError("glob pattern has unbalanced brackets")
    return value


class ExactCollector(_StrictFrozenModel):
    kind: Literal["exact"] = "exact"
    relative_path: str

    @field_validator("relative_path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        return _validate_relative_path(value, pattern=False)


class GlobCollector(_StrictFrozenModel):
    kind: Literal["glob"] = "glob"
    pattern: str
    minimum: _GlobBound
    maximum: _GlobBound
    container: ArtifactContainer = ArtifactContainer.FILE
    maximum_directory_entries: _DirectoryBound = _DEFAULT_DIRECTORY_ENTRIES

    @field_validator("pattern")
    @classmethod
    def _validate_pattern(cls, value: str) -> str:
        return _validate_relative_path(value, pattern=True)

    @model_validator(mode="after")
    def _validate_bounds(self) -> Self:
        if self.maximum < self.minimum:
            raise ValueError("glob maximum must be greater than or equal to minimum")
        return self


class StdoutCollector(_StrictFrozenModel):
    kind: Literal["stdout"] = "stdout"
    relative_path: str
    maximum_bytes: _StdoutBound = _DEFAULT_STDOUT_BYTES

    @field_validator("relative_path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        return _validate_relative_path(value, pattern=False)


class DirectoryCollector(_StrictFrozenModel):
    kind: Literal["directory"] = "directory"
    relative_path: str
    maximum_entries: _DirectoryBound = _DEFAULT_DIRECTORY_ENTRIES

    @field_validator("relative_path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        return _validate_relative_path(value, pattern=False)


NonConditionalOutputCollector = Annotated[
    ExactCollector | GlobCollector | StdoutCollector | DirectoryCollector,
    Field(discriminator="kind"),
]


class ConditionalCollector(_StrictFrozenModel):
    kind: Literal["conditional"] = "conditional"
    condition_key: ArtifactId
    expected_value: _ConditionValue
    collector: NonConditionalOutputCollector

    @field_validator("expected_value")
    @classmethod
    def _validate_expected_value(cls, value: _ConditionValue) -> _ConditionValue:
        if type(value) is float and not math.isfinite(value):
            raise ValueError("conditional expected value must be finite")
        return value


OutputCollector = Annotated[
    ExactCollector | GlobCollector | StdoutCollector | DirectoryCollector | ConditionalCollector,
    Field(discriminator="kind"),
]


class Utf8TextValidator(_StrictFrozenModel):
    kind: Literal["utf8_text"] = "utf8_text"
    maximum_bytes: _ContentBound = _DEFAULT_CONTENT_BYTES


class JsonValidator(_StrictFrozenModel):
    kind: Literal["json"] = "json"
    maximum_bytes: _ContentBound = _DEFAULT_CONTENT_BYTES


ContentValidator = Annotated[
    Utf8TextValidator | JsonValidator,
    Field(discriminator="kind"),
]


def _collector_container(collector: OutputCollector) -> ArtifactContainer:
    concrete = collector.collector if isinstance(collector, ConditionalCollector) else collector
    if isinstance(concrete, DirectoryCollector):
        return ArtifactContainer.DIRECTORY
    if isinstance(concrete, GlobCollector):
        return concrete.container
    return ArtifactContainer.FILE


class OutputSpec(_StrictFrozenModel):
    port_id: ArtifactId
    artifact_type: ArtifactId
    cardinality: Cardinality = Cardinality.ONE
    collector: OutputCollector
    require_nonempty: bool = False
    allowed_extensions: tuple[str, ...] = ()
    validators: tuple[ContentValidator, ...] = ()

    @model_validator(mode="after")
    def _validate_spec(self) -> Self:
        if isinstance(self.collector, ConditionalCollector):
            if self.cardinality not in (Cardinality.OPTIONAL_ONE, Cardinality.MANY):
                raise ValueError("conditional outputs must use an optional cardinality")

        container = _collector_container(self.collector)
        if container is ArtifactContainer.DIRECTORY:
            if self.allowed_extensions:
                raise ValueError("only file outputs can restrict extensions")
            if self.validators:
                raise ValueError("only file outputs can use content validators")

        seen_extensions: set[str] = set()
        for extension in self.allowed_extensions:
            if _EXTENSION_RE.fullmatch(extension) is None:
                raise ValueError(f"invalid output extension: {extension!r}")
            if extension in seen_extensions:
                raise ValueError(f"duplicate output extension: {extension}")
            seen_extensions.add(extension)

        concrete = self.collector.collector if isinstance(self.collector, ConditionalCollector) else self.collector
        if isinstance(concrete, GlobCollector):
            if self.cardinality in (Cardinality.ONE, Cardinality.OPTIONAL_ONE) and concrete.minimum > 1:
                raise ValueError("glob minimum is incompatible with scalar cardinality")
            if self.cardinality in (Cardinality.ONE, Cardinality.NONEMPTY_MANY) and concrete.maximum < 1:
                raise ValueError("glob maximum is incompatible with required cardinality")
        return self


class ObjectIdentity(_StrictFrozenModel):
    device: _NonnegativeInt
    inode: _NonnegativeInt
    mode: _NonnegativeInt
    size: _NonnegativeInt
    modified_time_ns: _NonnegativeInt
    changed_time_ns: _NonnegativeInt


class CollectedTreeEntry(_StrictFrozenModel):
    relative_path: str
    container: ArtifactContainer
    identity: ObjectIdentity

    @field_validator("relative_path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        return _validate_relative_path(value, pattern=False)


class CollectedArtifact(_StrictFrozenModel):
    relative_path: str
    container: ArtifactContainer
    identity: ObjectIdentity
    root_identity: ObjectIdentity
    entries: tuple[CollectedTreeEntry, ...] = ()

    @field_validator("relative_path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        return _validate_relative_path(value, pattern=False)

    @model_validator(mode="after")
    def _validate_entries(self) -> Self:
        if self.container is ArtifactContainer.FILE and self.entries:
            raise ValueError("file artifacts cannot contain directory entries")
        paths = tuple(entry.relative_path for entry in self.entries)
        if paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
            raise ValueError("directory entries must be unique and canonically ordered")
        prefix = f"{self.relative_path}/"
        if any(not path.startswith(prefix) for path in paths):
            raise ValueError("directory entries must be descendants of the artifact")
        return self

    def verify_identity(self, root: str | os.PathLike[str]) -> None:
        type(self).model_validate(self)
        root_fd = _open_root(root)
        captured: _CapturedObject | None = None
        try:
            if not _same_root_identity(_identity_from_stat(os.fstat(root_fd)), self.root_identity):
                raise OutputIdentityError("collected output root changed")
            try:
                captured = _open_existing_artifact(
                    root_fd,
                    self.relative_path,
                    self.container,
                    port_id="collected",
                    directory_limit=max(1, len(self.entries) + 1),
                )
            except (OSError, OutputCollectionError) as error:
                raise OutputIdentityError(f"output path '{self.relative_path}' changed") from error
            if captured is None or captured.identity != self.identity or captured.entries != self.entries:
                raise OutputIdentityError(f"output path '{self.relative_path}' changed")
        finally:
            if captured is not None:
                os.close(captured.fd)
            os.close(root_fd)

    @contextmanager
    def open_verified(self, root: str | os.PathLike[str]) -> Iterator[BinaryIO]:
        type(self).model_validate(self)
        if self.container is not ArtifactContainer.FILE:
            raise OutputIdentityError(f"output path '{self.relative_path}' is not a regular file")
        root_fd = _open_root(root)
        captured: _CapturedObject | None = None
        opened: BinaryIO | None = None
        primary_error = False
        try:
            if not _same_root_identity(_identity_from_stat(os.fstat(root_fd)), self.root_identity):
                raise OutputIdentityError("collected output root changed")
            try:
                captured = _open_existing_artifact(
                    root_fd,
                    self.relative_path,
                    ArtifactContainer.FILE,
                    port_id="collected",
                    directory_limit=0,
                )
            except (OSError, OutputCollectionError) as error:
                raise OutputIdentityError(f"output path '{self.relative_path}' changed") from error
            if captured is None or captured.identity != self.identity:
                raise OutputIdentityError(f"output path '{self.relative_path}' changed")
            opened = cast(BinaryIO, os.fdopen(captured.fd, "rb", closefd=True))
            captured = None
            yield opened
            try:
                final_identity = _identity_from_stat(os.fstat(opened.fileno()))
            except (OSError, ValueError) as error:
                raise OutputIdentityError(f"output path '{self.relative_path}' changed") from error
            if final_identity != self.identity:
                raise OutputIdentityError(f"output path '{self.relative_path}' changed")
        except BaseException:
            primary_error = True
            raise
        finally:
            cleanup_error: BaseException | None = None
            if opened is not None:
                try:
                    opened.close()
                except BaseException as error:
                    cleanup_error = error
            if captured is not None:
                try:
                    os.close(captured.fd)
                except BaseException as error:
                    cleanup_error = cleanup_error or error
            try:
                os.close(root_fd)
            except BaseException as error:
                cleanup_error = cleanup_error or error
            if cleanup_error is not None and not primary_error:
                raise cleanup_error

    def read_bytes_verified(
        self,
        root: str | os.PathLike[str],
        *,
        maximum_bytes: int = MAX_CONTENT_VALIDATOR_BYTES,
    ) -> bytes:
        if type(maximum_bytes) is not int or not 1 <= maximum_bytes <= MAX_CONTENT_VALIDATOR_BYTES:
            raise ValueError(f"maximum_bytes must be an integer from 1 to {MAX_CONTENT_VALIDATOR_BYTES}")
        with self.open_verified(root) as opened:
            data = opened.read(maximum_bytes + 1)
        if len(data) > maximum_bytes:
            raise OutputIdentityError(
                f"output path '{self.relative_path}' exceeds read maximum of {maximum_bytes} bytes"
            )
        return data


class CollectedOutput(_StrictFrozenModel):
    port_id: ArtifactId
    artifact_type: ArtifactId
    cardinality: Cardinality
    artifacts: tuple[CollectedArtifact, ...]

    @model_validator(mode="after")
    def _validate_cardinality(self) -> Self:
        count = len(self.artifacts)
        if self.cardinality is Cardinality.ONE and count != 1:
            raise ValueError("one output must contain exactly one artifact")
        if self.cardinality is Cardinality.OPTIONAL_ONE and count > 1:
            raise ValueError("optional-one output must contain at most one artifact")
        if self.cardinality is Cardinality.NONEMPTY_MANY and count < 1:
            raise ValueError("nonempty-many output must contain at least one artifact")
        return self

    @property
    def value(self) -> CollectedArtifact | tuple[CollectedArtifact, ...] | None:
        if self.cardinality in (Cardinality.MANY, Cardinality.NONEMPTY_MANY):
            return self.artifacts
        return self.artifacts[0] if self.artifacts else None


class CollectedOutputs(_StrictFrozenModel, Mapping[str, object]):
    outputs: tuple[CollectedOutput, ...]

    @model_validator(mode="after")
    def _validate_ports(self) -> Self:
        seen: set[str] = set()
        for output in self.outputs:
            if output.port_id in seen:
                raise ValueError(f"duplicate collected output port ID: {output.port_id}")
            seen.add(output.port_id)
        return self

    def __getitem__(self, port_id: str) -> object:
        for output in self.outputs:
            if output.port_id == port_id:
                return output.value
        raise KeyError(port_id)

    def __iter__(self) -> Iterator[str]:
        return (output.port_id for output in self.outputs)

    def __len__(self) -> int:
        return len(self.outputs)

    def to_manifest(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


@dataclass(frozen=True, slots=True)
class _CapturedObject:
    relative_path: str
    container: ArtifactContainer
    identity: ObjectIdentity
    entries: tuple[CollectedTreeEntry, ...]
    fd: int
    created: bool = False


def _require_descriptor_primitives() -> None:
    required_flags = ("O_CLOEXEC", "O_DIRECTORY", "O_EXCL", "O_NOFOLLOW", "O_NONBLOCK")
    if any(not hasattr(os, flag) for flag in required_flags):
        raise OutputRootError("platform lacks required no-follow descriptor support")
    if os.open not in os.supports_dir_fd or os.stat not in os.supports_dir_fd or os.scandir not in os.supports_fd:
        raise OutputRootError("platform lacks required descriptor-relative operations")


def _open_root(root: str | os.PathLike[str]) -> int:
    _require_descriptor_primitives()
    try:
        root_path = os.fspath(root)
    except TypeError as error:
        raise OutputRootError("output root must be an existing absolute non-symlink directory") from error
    if type(root_path) is not str or "\x00" in root_path or not root_path.startswith("/"):
        raise OutputRootError("output root must be an existing absolute non-symlink directory")
    if root_path != "/":
        root_path = root_path.rstrip("/")
    components = () if root_path == "/" else tuple(root_path.split("/")[1:])
    if any(component in ("", ".", "..") for component in components):
        raise OutputRootError("output root must be an existing absolute non-symlink directory")
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        root_fd = os.open("/", flags)
    except OSError as error:
        raise OutputRootError("output root must be an existing absolute non-symlink directory") from error
    try:
        for component in components:
            next_fd = os.open(component, flags, dir_fd=root_fd)
            os.close(root_fd)
            root_fd = next_fd
        if not stat.S_ISDIR(os.fstat(root_fd).st_mode):
            raise OutputRootError("output root must be an existing absolute non-symlink directory")
    except (OSError, UnicodeError, TypeError, ValueError) as error:
        os.close(root_fd)
        if isinstance(error, OutputRootError):
            raise
        raise OutputRootError("output root must be an existing absolute non-symlink directory") from error
    return root_fd


def _identity_from_stat(value: os.stat_result) -> ObjectIdentity:
    return ObjectIdentity(
        device=value.st_dev,
        inode=value.st_ino,
        mode=value.st_mode,
        size=value.st_size,
        modified_time_ns=value.st_mtime_ns,
        changed_time_ns=value.st_ctime_ns,
    )


def _same_root_identity(left: ObjectIdentity, right: ObjectIdentity) -> bool:
    return left == right


def _kind_name(mode: int) -> str:
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISFIFO(mode):
        return "fifo"
    if stat.S_ISSOCK(mode):
        return "socket"
    if stat.S_ISBLK(mode):
        return "block device"
    if stat.S_ISCHR(mode):
        return "character device"
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISREG(mode):
        return "regular file"
    return "special file"


def _stat_entry(parent_fd: int, name: str) -> os.stat_result | None:
    try:
        return os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None


def _path_error(port_id: str, relative_path: str, detail: str) -> OutputCollectionError:
    return OutputCollectionError(f"output port '{port_id}' path '{relative_path}': {detail}")


def _raise_open_error(
    error: OSError,
    *,
    parent_fd: int,
    name: str,
    port_id: str,
    relative_path: str,
) -> None:
    existing = _stat_entry(parent_fd, name)
    if existing is not None:
        kind = _kind_name(existing.st_mode)
        raise _path_error(port_id, relative_path, f"unsafe or wrong object kind: {kind}") from error
    if error.errno in (errno.ENOENT, errno.ENOTDIR):
        raise FileNotFoundError(relative_path) from error
    raise _path_error(port_id, relative_path, "could not be opened safely") from error


def _open_parent(
    root_fd: int,
    relative_path: str,
    *,
    port_id: str,
) -> tuple[int, str] | None:
    components = relative_path.split("/")
    current_fd = os.dup(root_fd)
    try:
        for index, component in enumerate(components[:-1]):
            flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
            try:
                next_fd = os.open(component, flags, dir_fd=current_fd)
            except FileNotFoundError:
                return None
            except OSError as error:
                prefix = "/".join(components[: index + 1])
                _raise_open_error(
                    error,
                    parent_fd=current_fd,
                    name=component,
                    port_id=port_id,
                    relative_path=relative_path,
                )
                raise AssertionError(f"unreachable while opening {prefix}")
            os.close(current_fd)
            current_fd = next_fd
        result = (current_fd, components[-1])
        current_fd = -1
        return result
    finally:
        if current_fd >= 0:
            os.close(current_fd)


def _open_child(
    parent_fd: int,
    name: str,
    *,
    port_id: str,
    relative_path: str,
) -> tuple[int, os.stat_result] | None:
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        child_fd = os.open(name, flags, dir_fd=parent_fd)
    except FileNotFoundError:
        return None
    except OSError as error:
        _raise_open_error(
            error,
            parent_fd=parent_fd,
            name=name,
            port_id=port_id,
            relative_path=relative_path,
        )
        raise AssertionError("unreachable")
    try:
        child_stat = os.fstat(child_fd)
    except BaseException:
        os.close(child_fd)
        raise
    return child_fd, child_stat


def _directory_names(
    directory_fd: int,
    *,
    limit: int,
    configured_limit: int,
    port_id: str,
    relative_path: str,
) -> tuple[str, ...]:
    names: list[str] = []
    with os.scandir(directory_fd) as entries:
        for entry in entries:
            name = entry.name
            try:
                name.encode("utf-8")
            except UnicodeEncodeError as error:
                raise _path_error(port_id, relative_path, "contains a non-UTF-8 entry name") from error
            names.append(name)
            if len(names) > limit:
                raise _path_error(
                    port_id,
                    relative_path,
                    f"directory exceeds maximum of {configured_limit} entries",
                )
    return tuple(sorted(names))


def _scan_directory_tree(
    directory_fd: int,
    relative_path: str,
    *,
    maximum_entries: int,
    port_id: str,
) -> tuple[CollectedTreeEntry, ...]:
    collected: list[CollectedTreeEntry] = []

    def visit(current_fd: int, prefix: str, depth: int) -> None:
        try:
            identity_before = _identity_from_stat(os.fstat(current_fd))
        except OSError as error:
            raise _path_error(port_id, prefix, "directory changed before collection") from error
        remaining = maximum_entries - len(collected)
        names = _directory_names(
            current_fd,
            limit=remaining,
            configured_limit=maximum_entries,
            port_id=port_id,
            relative_path=relative_path,
        )
        for name in names:
            child_path = f"{prefix}/{name}"
            try:
                _validate_relative_path(child_path, pattern=False)
            except ValueError as error:
                raise _path_error(port_id, child_path, "directory entry path exceeds safe bounds") from error
            opened = _open_child(
                current_fd,
                name,
                port_id=port_id,
                relative_path=child_path,
            )
            if opened is None:
                raise _path_error(port_id, child_path, "changed during collection")
            child_fd, child_stat = opened
            try:
                if stat.S_ISREG(child_stat.st_mode):
                    container = ArtifactContainer.FILE
                elif stat.S_ISDIR(child_stat.st_mode):
                    container = ArtifactContainer.DIRECTORY
                else:
                    kind = _kind_name(child_stat.st_mode)
                    raise _path_error(port_id, child_path, f"unsafe object kind: {kind}")
                collected.append(
                    CollectedTreeEntry(
                        relative_path=child_path,
                        container=container,
                        identity=_identity_from_stat(child_stat),
                    )
                )
                if len(collected) > maximum_entries:
                    raise _path_error(
                        port_id,
                        relative_path,
                        f"directory exceeds maximum of {maximum_entries} entries",
                    )
                if container is ArtifactContainer.DIRECTORY:
                    if depth >= _MAX_DIRECTORY_DEPTH:
                        raise _path_error(port_id, child_path, "directory tree exceeds safe depth")
                    visit(child_fd, child_path, depth + 1)
            finally:
                os.close(child_fd)
        try:
            identity_after = _identity_from_stat(os.fstat(current_fd))
        except OSError as error:
            raise _path_error(port_id, prefix, "directory changed during collection") from error
        if identity_after != identity_before:
            raise _path_error(port_id, prefix, "directory changed during collection")

    visit(directory_fd, relative_path, 0)
    return tuple(sorted(collected, key=lambda entry: entry.relative_path))


def _open_existing_artifact(
    root_fd: int,
    relative_path: str,
    container: ArtifactContainer,
    *,
    port_id: str,
    directory_limit: int,
) -> _CapturedObject | None:
    parent = _open_parent(root_fd, relative_path, port_id=port_id)
    if parent is None:
        return None
    parent_fd, name = parent
    try:
        opened = _open_child(
            parent_fd,
            name,
            port_id=port_id,
            relative_path=relative_path,
        )
    finally:
        os.close(parent_fd)
    if opened is None:
        return None
    artifact_fd, artifact_stat = opened
    try:
        if container is ArtifactContainer.FILE:
            if not stat.S_ISREG(artifact_stat.st_mode):
                kind = _kind_name(artifact_stat.st_mode)
                raise _path_error(
                    port_id,
                    relative_path,
                    f"expected a regular file, found {kind}",
                )
            entries: tuple[CollectedTreeEntry, ...] = ()
        else:
            if not stat.S_ISDIR(artifact_stat.st_mode):
                kind = _kind_name(artifact_stat.st_mode)
                raise _path_error(
                    port_id,
                    relative_path,
                    f"expected a directory, found {kind}",
                )
            entries = _scan_directory_tree(
                artifact_fd,
                relative_path,
                maximum_entries=directory_limit,
                port_id=port_id,
            )
        return _CapturedObject(
            relative_path=relative_path,
            container=container,
            identity=_identity_from_stat(artifact_stat),
            entries=entries,
            fd=artifact_fd,
        )
    except BaseException:
        os.close(artifact_fd)
        raise


def _glob_names(
    directory_fd: int,
    component: str,
    *,
    scan_state: list[int],
    match_limit: int | None,
    configured_maximum: int,
    port_id: str,
    pattern: str,
) -> tuple[str, ...]:
    if not any(character in component for character in "*?["):
        return (component,)
    matched: list[str] = []
    with os.scandir(directory_fd) as entries:
        for entry in entries:
            scan_state[0] += 1
            if scan_state[0] > MAX_GLOB_SCAN_ENTRIES:
                raise _path_error(
                    port_id,
                    pattern,
                    f"glob scan exceeds maximum of {MAX_GLOB_SCAN_ENTRIES} entries",
                )
            name = entry.name
            try:
                name.encode("utf-8")
            except UnicodeEncodeError as error:
                raise _path_error(port_id, pattern, "glob encountered a non-UTF-8 entry name") from error
            if fnmatch.fnmatchcase(name, component):
                matched.append(name)
                if match_limit is not None and len(matched) > match_limit:
                    raise _path_error(
                        port_id,
                        pattern,
                        f"glob exceeds maximum of {configured_maximum} matches",
                    )
    return tuple(sorted(matched))


def _collect_glob(
    root_fd: int,
    collector: GlobCollector,
    *,
    port_id: str,
) -> list[_CapturedObject]:
    components = collector.pattern.split("/")
    captured: list[_CapturedObject] = []
    scan_state = [0]

    def visit(directory_fd: int, index: int, prefix: tuple[str, ...]) -> None:
        component = components[index]
        is_leaf = index == len(components) - 1
        names = _glob_names(
            directory_fd,
            component,
            scan_state=scan_state,
            match_limit=collector.maximum - len(captured) if is_leaf else None,
            configured_maximum=collector.maximum,
            port_id=port_id,
            pattern=collector.pattern,
        )
        component_has_magic = any(character in component for character in "*?[")
        for name in names:
            candidate_parts = (*prefix, name)
            candidate = "/".join(candidate_parts)
            if is_leaf:
                artifact = _open_existing_artifact(
                    directory_fd,
                    name,
                    collector.container,
                    port_id=port_id,
                    directory_limit=collector.maximum_directory_entries,
                )
                if artifact is None:
                    continue
                try:
                    captured.append(
                        _CapturedObject(
                            relative_path=candidate,
                            container=artifact.container,
                            identity=artifact.identity,
                            entries=tuple(
                                entry.model_copy(
                                    update={
                                        "relative_path": f"{'/'.join(prefix)}/{entry.relative_path}"
                                        if prefix
                                        else entry.relative_path
                                    }
                                )
                                for entry in artifact.entries
                            ),
                            fd=artifact.fd,
                        )
                    )
                except BaseException:
                    os.close(artifact.fd)
                    raise
                if len(captured) > collector.maximum:
                    raise _path_error(
                        port_id,
                        collector.pattern,
                        f"glob exceeds maximum of {collector.maximum} matches",
                    )
                continue

            opened = _open_child(
                directory_fd,
                name,
                port_id=port_id,
                relative_path=candidate,
            )
            if opened is None:
                continue
            child_fd, child_stat = opened
            try:
                if stat.S_ISLNK(child_stat.st_mode):
                    raise _path_error(port_id, candidate, "unsafe object kind: symlink")
                if not stat.S_ISDIR(child_stat.st_mode):
                    if component_has_magic and stat.S_ISREG(child_stat.st_mode):
                        continue
                    kind = _kind_name(child_stat.st_mode)
                    raise _path_error(port_id, candidate, f"expected a directory, found {kind}")
                visit(child_fd, index + 1, candidate_parts)
            finally:
                os.close(child_fd)

    try:
        visit(root_fd, 0, ())
    except BaseException:
        for artifact in captured:
            os.close(artifact.fd)
        raise
    return sorted(captured, key=lambda artifact: artifact.relative_path)


def _create_stdout_artifact(
    root_fd: int,
    collector: StdoutCollector,
    payload: bytes,
    *,
    port_id: str,
) -> _CapturedObject:
    parent = _open_parent(root_fd, collector.relative_path, port_id=port_id)
    if parent is None:
        raise _path_error(port_id, collector.relative_path, "parent directory is missing")
    parent_fd, _ = parent
    artifact_fd = -1
    try:
        if not hasattr(os, "O_TMPFILE"):
            raise _path_error(
                port_id,
                collector.relative_path,
                "platform does not support safe anonymous stdout staging",
            )
        flags = os.O_RDWR | os.O_CLOEXEC | os.O_TMPFILE
        try:
            artifact_fd = os.open(".", flags, 0o600, dir_fd=parent_fd)
        except OSError as error:
            raise _path_error(
                port_id,
                collector.relative_path,
                "filesystem does not support safe anonymous stdout staging",
            ) from error

        position = 0
        while position < len(payload):
            written = os.write(artifact_fd, payload[position:])
            if written <= 0:
                raise _path_error(port_id, collector.relative_path, "stdout write did not make progress")
            position += written
        identity = _identity_from_stat(os.fstat(artifact_fd))
        return _CapturedObject(
            relative_path=collector.relative_path,
            container=ArtifactContainer.FILE,
            identity=identity,
            entries=(),
            fd=artifact_fd,
            created=True,
        )
    except BaseException:
        if artifact_fd >= 0:
            os.close(artifact_fd)
        raise
    finally:
        os.close(parent_fd)


def _link_anonymous_file(source_fd: int, parent_fd: int, name: str) -> None:
    try:
        library = ctypes.CDLL(None, use_errno=True)
        linkat = library.linkat
    except (AttributeError, OSError) as error:
        raise OSError(errno.ENOSYS, "linkat is unavailable") from error
    linkat.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
    )
    linkat.restype = ctypes.c_int
    ctypes.set_errno(0)
    result = linkat(
        source_fd,
        b"",
        parent_fd,
        os.fsencode(name),
        _AT_EMPTY_PATH,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number))


def _publish_stdout_artifact(
    root_fd: int,
    artifact: _CapturedObject,
    *,
    port_id: str,
) -> _CapturedObject:
    parent = _open_parent(root_fd, artifact.relative_path, port_id=port_id)
    if parent is None:
        raise _path_error(port_id, artifact.relative_path, "parent directory is missing")
    parent_fd, name = parent
    try:
        try:
            _link_anonymous_file(artifact.fd, parent_fd, name)
        except OSError as error:
            if error.errno == errno.EEXIST:
                detail = "target already exists"
            elif error.errno in (
                errno.EINVAL,
                errno.ENOSYS,
                errno.EOPNOTSUPP,
                errno.EPERM,
            ):
                detail = "platform does not support safe stdout publication"
            else:
                detail = "target could not be published safely"
            raise _path_error(port_id, artifact.relative_path, detail) from error
    finally:
        os.close(parent_fd)

    published_identity = _identity_from_stat(os.fstat(artifact.fd))
    verified = _open_existing_artifact(
        root_fd,
        artifact.relative_path,
        ArtifactContainer.FILE,
        port_id=port_id,
        directory_limit=0,
    )
    if verified is None:
        raise _path_error(port_id, artifact.relative_path, "published target changed")
    try:
        if verified.identity != published_identity:
            raise _path_error(port_id, artifact.relative_path, "published target changed")
    finally:
        os.close(verified.fd)
    return _CapturedObject(
        relative_path=artifact.relative_path,
        container=artifact.container,
        identity=published_identity,
        entries=artifact.entries,
        fd=artifact.fd,
    )


def _read_bounded(fd: int, maximum_bytes: int) -> bytes:
    os.lseek(fd, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    remaining = maximum_bytes + 1
    while remaining:
        chunk = os.read(fd, min(65_536, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def _parse_finite_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite JSON number: {value}")
    return parsed


def _validate_content(
    spec: OutputSpec,
    artifact: _CapturedObject,
    validator: ContentValidator,
) -> None:
    before = _identity_from_stat(os.fstat(artifact.fd))
    if before != artifact.identity:
        raise _path_error(spec.port_id, artifact.relative_path, "changed before content validation")
    data = _read_bounded(artifact.fd, validator.maximum_bytes)
    after = _identity_from_stat(os.fstat(artifact.fd))
    if after != artifact.identity:
        raise _path_error(spec.port_id, artifact.relative_path, "changed during content validation")
    if len(data) > validator.maximum_bytes:
        raise _path_error(
            spec.port_id,
            artifact.relative_path,
            f"content exceeds validator maximum of {validator.maximum_bytes} bytes",
        )
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise _path_error(spec.port_id, artifact.relative_path, "content is not valid UTF-8") from error
    if isinstance(validator, JsonValidator):
        try:
            json.loads(
                text,
                parse_constant=_reject_json_constant,
                parse_float=_parse_finite_json_float,
            )
        except (ValueError, RecursionError, MemoryError) as error:
            raise _path_error(spec.port_id, artifact.relative_path, "content is not valid bounded JSON") from error


def _validate_artifacts(spec: OutputSpec, artifacts: Sequence[_CapturedObject]) -> None:
    for artifact in artifacts:
        if spec.require_nonempty:
            if artifact.container is ArtifactContainer.FILE and artifact.identity.size == 0:
                raise _path_error(spec.port_id, artifact.relative_path, "file is empty")
            if artifact.container is ArtifactContainer.DIRECTORY and not artifact.entries:
                raise _path_error(spec.port_id, artifact.relative_path, "directory is empty")
        if artifact.container is ArtifactContainer.FILE and spec.allowed_extensions:
            if not any(artifact.relative_path.endswith(extension) for extension in spec.allowed_extensions):
                raise _path_error(spec.port_id, artifact.relative_path, "file extension is not allowed")
        for validator in spec.validators:
            if artifact.container is not ArtifactContainer.FILE:
                raise _path_error(spec.port_id, artifact.relative_path, "content validators require a file")
            _validate_content(spec, artifact, validator)


def _validate_count(
    spec: OutputSpec,
    artifacts: Sequence[_CapturedObject],
    *,
    collector_active: bool,
) -> None:
    count = len(artifacts)
    if spec.cardinality is Cardinality.ONE and count != 1:
        if count == 0 and not isinstance(spec.collector, GlobCollector):
            path = _collector_relative_path(spec.collector)
            raise MissingOutputError(f"output port '{spec.port_id}' path '{path}': missing required output")
        raise _path_error(spec.port_id, _collector_label(spec.collector), "cardinality requires exactly one artifact")
    if spec.cardinality is Cardinality.OPTIONAL_ONE and count > 1:
        raise _path_error(spec.port_id, _collector_label(spec.collector), "cardinality permits at most one artifact")
    if spec.cardinality is Cardinality.NONEMPTY_MANY and count == 0:
        if not isinstance(spec.collector, GlobCollector):
            path = _collector_relative_path(spec.collector)
            raise MissingOutputError(f"output port '{spec.port_id}' path '{path}': missing required output")
        raise _path_error(spec.port_id, _collector_label(spec.collector), "cardinality requires at least one artifact")

    concrete = spec.collector.collector if isinstance(spec.collector, ConditionalCollector) else spec.collector
    if collector_active and isinstance(concrete, GlobCollector) and count < concrete.minimum:
        raise _path_error(
            spec.port_id,
            concrete.pattern,
            f"glob found {count} artifacts below minimum of {concrete.minimum}",
        )


def _collector_label(collector: OutputCollector) -> str:
    concrete = collector.collector if isinstance(collector, ConditionalCollector) else collector
    if isinstance(concrete, GlobCollector):
        return concrete.pattern
    return concrete.relative_path


def _collector_relative_path(collector: OutputCollector) -> str:
    return _collector_label(collector)


def _path_matches_glob_pattern(relative_path: str, pattern: str) -> bool:
    path_components = relative_path.split("/")
    pattern_components = pattern.split("/")
    return len(path_components) == len(pattern_components) and all(
        fnmatch.fnmatchcase(path_component, pattern_component)
        for path_component, pattern_component in zip(
            path_components,
            pattern_components,
            strict=True,
        )
    )


def _stdout_overlaps_collector(
    stdout: StdoutCollector,
    collector: NonConditionalOutputCollector,
) -> bool:
    if isinstance(collector, ExactCollector):
        return stdout.relative_path == collector.relative_path
    if isinstance(collector, DirectoryCollector):
        return stdout.relative_path.startswith(f"{collector.relative_path}/")
    if isinstance(collector, GlobCollector):
        if collector.container is ArtifactContainer.FILE:
            return _path_matches_glob_pattern(stdout.relative_path, collector.pattern)
        components = stdout.relative_path.split("/")
        return any(
            _path_matches_glob_pattern("/".join(components[:index]), collector.pattern)
            for index in range(1, len(components))
        )
    return False


def _collect_concrete(
    root_fd: int,
    collector: NonConditionalOutputCollector,
    *,
    port_id: str,
    stdout_payload: bytes | None,
) -> list[_CapturedObject]:
    if isinstance(collector, ExactCollector):
        artifact = _open_existing_artifact(
            root_fd,
            collector.relative_path,
            ArtifactContainer.FILE,
            port_id=port_id,
            directory_limit=0,
        )
        return [] if artifact is None else [artifact]
    if isinstance(collector, DirectoryCollector):
        artifact = _open_existing_artifact(
            root_fd,
            collector.relative_path,
            ArtifactContainer.DIRECTORY,
            port_id=port_id,
            directory_limit=collector.maximum_entries,
        )
        return [] if artifact is None else [artifact]
    if isinstance(collector, GlobCollector):
        return _collect_glob(root_fd, collector, port_id=port_id)
    if stdout_payload is None:
        return []
    return [
        _create_stdout_artifact(
            root_fd,
            collector,
            stdout_payload,
            port_id=port_id,
        )
    ]


def _validated_specs(specs: Sequence[OutputSpec]) -> tuple[OutputSpec, ...]:
    validated: list[OutputSpec] = []
    for spec in specs:
        validated.append(OutputSpec.model_validate(spec))
        if len(validated) > MAX_OUTPUT_SPECS:
            raise OutputCollectionError(f"declared outputs exceed maximum of {MAX_OUTPUT_SPECS} specs")
    seen: set[str] = set()
    for spec in validated:
        if spec.port_id in seen:
            raise OutputCollectionError(f"duplicate output port ID: {spec.port_id}")
        seen.add(spec.port_id)
    return tuple(validated)


def _active_collectors(
    specs: Sequence[OutputSpec],
    conditions: Mapping[str, object] | None,
) -> tuple[NonConditionalOutputCollector | None, ...]:
    active: list[NonConditionalOutputCollector | None] = []
    values = {} if conditions is None else conditions
    for spec in specs:
        collector = spec.collector
        if not isinstance(collector, ConditionalCollector):
            active.append(collector)
            continue
        if collector.condition_key not in values:
            raise _path_error(
                spec.port_id,
                _collector_label(collector),
                f"condition key '{collector.condition_key}' is missing",
            )
        actual = values[collector.condition_key]
        enabled = type(actual) is type(collector.expected_value) and actual == collector.expected_value
        active.append(collector.collector if enabled else None)
    return tuple(active)


def _prepare_stdout(
    specs: Sequence[OutputSpec],
    active: Sequence[NonConditionalOutputCollector | None],
    stdout: str | bytes | None,
    stdout_truncated: bool | None,
) -> bytes | None:
    stdout_specs = [
        (spec, collector)
        for spec, collector in zip(specs, active, strict=True)
        if isinstance(collector, StdoutCollector)
    ]
    if not stdout_specs:
        return None
    if len(stdout_specs) > 1:
        conflicts = "; ".join(
            f"port '{spec.port_id}' path '{collector.relative_path}'" for spec, collector in stdout_specs
        )
        raise OutputCollectionError(f"multiple active stdout collectors conflict: {conflicts}")
    for stdout_spec, stdout_collector in stdout_specs:
        for other_spec, other_collector in zip(specs, active, strict=True):
            if other_spec.port_id == stdout_spec.port_id or other_collector is None:
                continue
            if _stdout_overlaps_collector(stdout_collector, other_collector):
                label_kind = "pattern" if isinstance(other_collector, GlobCollector) else "path"
                raise OutputCollectionError(
                    f"stdout output port '{stdout_spec.port_id}' path "
                    f"'{stdout_collector.relative_path}' overlaps output port "
                    f"'{other_spec.port_id}' {label_kind} "
                    f"'{_collector_label(other_collector)}'"
                )
    first_spec = stdout_specs[0][0]
    if stdout_truncated is True:
        raise _path_error(
            first_spec.port_id,
            _collector_label(first_spec.collector),
            "captured stdout is truncated",
        )
    if stdout is None:
        return None
    if type(stdout_truncated) is not bool:
        raise _path_error(
            first_spec.port_id,
            _collector_label(first_spec.collector),
            "explicit stdout truncation metadata is required",
        )
    if type(stdout) is str:
        try:
            payload = stdout.encode("utf-8")
        except UnicodeEncodeError as error:
            raise _path_error(
                first_spec.port_id,
                _collector_label(first_spec.collector),
                "captured stdout is not valid UTF-8 text",
            ) from error
    elif type(stdout) is bytes:
        payload = stdout
    else:
        raise _path_error(
            first_spec.port_id,
            _collector_label(first_spec.collector),
            "captured stdout must be text or bytes",
        )
    for spec, collector in stdout_specs:
        if len(payload) > collector.maximum_bytes:
            raise _path_error(
                spec.port_id,
                collector.relative_path,
                f"captured stdout exceeds maximum of {collector.maximum_bytes} bytes",
            )
    return payload


def collect_outputs(
    specs: Sequence[OutputSpec],
    root: str | os.PathLike[str],
    stdout: str | bytes | None = None,
    *,
    stdout_truncated: bool | None = None,
    conditions: Mapping[str, object] | None = None,
) -> CollectedOutputs:
    """Collect every declared artifact, then validate and shape the exact result."""

    validated_specs = _validated_specs(specs)
    active = _active_collectors(validated_specs, conditions)
    stdout_payload = _prepare_stdout(
        validated_specs,
        active,
        stdout,
        stdout_truncated,
    )
    root_fd = _open_root(root)
    all_captured: list[list[_CapturedObject]] = []
    try:
        for spec, collector in zip(validated_specs, active, strict=True):
            artifacts = (
                []
                if collector is None
                else _collect_concrete(
                    root_fd,
                    collector,
                    port_id=spec.port_id,
                    stdout_payload=stdout_payload,
                )
            )
            all_captured.append(artifacts)

        for spec, collector, artifacts in zip(
            validated_specs,
            active,
            all_captured,
            strict=True,
        ):
            _validate_count(spec, artifacts, collector_active=collector is not None)
            _validate_artifacts(spec, artifacts)

        for index, (spec, artifacts) in enumerate(zip(validated_specs, all_captured, strict=True)):
            all_captured[index] = [
                _publish_stdout_artifact(root_fd, artifact, port_id=spec.port_id) if artifact.created else artifact
                for artifact in artifacts
            ]

        root_identity = _identity_from_stat(os.fstat(root_fd))
        collected_outputs: list[CollectedOutput] = []
        for spec, artifacts in zip(validated_specs, all_captured, strict=True):
            collected_outputs.append(
                CollectedOutput(
                    port_id=spec.port_id,
                    artifact_type=spec.artifact_type,
                    cardinality=spec.cardinality,
                    artifacts=tuple(
                        CollectedArtifact(
                            relative_path=artifact.relative_path,
                            container=artifact.container,
                            identity=artifact.identity,
                            root_identity=root_identity,
                            entries=artifact.entries,
                        )
                        for artifact in artifacts
                    ),
                )
            )
        return CollectedOutputs(outputs=tuple(collected_outputs))
    except BaseException:
        for artifacts in all_captured:
            for artifact in artifacts:
                try:
                    os.close(artifact.fd)
                except OSError:
                    pass
        all_captured.clear()
        raise
    finally:
        for artifacts in all_captured:
            for artifact in artifacts:
                try:
                    os.close(artifact.fd)
                except OSError:
                    pass
        os.close(root_fd)


__all__ = [
    "CollectedArtifact",
    "CollectedOutput",
    "CollectedOutputs",
    "CollectedTreeEntry",
    "ConditionalCollector",
    "ContentValidator",
    "DirectoryCollector",
    "ExactCollector",
    "GlobCollector",
    "JsonValidator",
    "MAX_CONTENT_VALIDATOR_BYTES",
    "MAX_DIRECTORY_ENTRIES",
    "MAX_GLOB_MATCHES",
    "MAX_STDOUT_BYTES",
    "MissingOutputError",
    "ObjectIdentity",
    "OutputCollectionError",
    "OutputCollector",
    "OutputIdentityError",
    "OutputRootError",
    "OutputSpec",
    "StdoutCollector",
    "Utf8TextValidator",
    "collect_outputs",
]
