"""Pixi identity checks and environment-lock compilation orchestration."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Annotated, TypeAlias

from pydantic import StringConstraints, field_validator

from bionodulo.nodes.contract.artifacts import _StrictFrozenModel
from bionodulo.nodes.contract.environments import (
    ExecutionPlatform,
    PlatformLock,
    ResolverIdentity,
    Sha256Digest,
)
from bionodulo.nodes.environment_compiler import pixi_identity, pixi_lock_v7


PIXI_VERSION = pixi_identity.PIXI_VERSION
PIXI_TAG_COMMIT = pixi_identity.PIXI_TAG_COMMIT
PixiDistribution = pixi_identity.PixiDistribution
PIXI_DISTRIBUTIONS = pixi_identity.PIXI_DISTRIBUTIONS
_MAX_WORKSPACE_STATE_BYTES = 512 * 1024 * 1024


class VerifiedPixiExecutable(_StrictFrozenModel):
    """Caller-verified executable provenance bound to one pinned release archive."""

    executable_path: Path
    version: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    distribution: PixiDistribution

    @field_validator("executable_path")
    @classmethod
    def _validate_executable_path(cls, value: Path) -> Path:
        if not value.is_absolute() or ".." in value.parts:
            raise ValueError("verified Pixi executable path must be absolute, not a PATH lookup name")
        if value.name != "pixi":
            raise ValueError("verified Pixi executable path must identify the pixi binary")
        return value


_PIXI_PLATFORM = pixi_lock_v7.PIXI_PLATFORM

# Compatibility re-exports retained until the public compiler API is narrowed.
PixiCondaListRecord = pixi_lock_v7.PixiCondaListRecord
PixiPypiListRecord = pixi_lock_v7.PixiPypiListRecord
PixiListRecord = pixi_lock_v7.PixiListRecord
decode_pixi_list_json = pixi_lock_v7.decode_pixi_list_json
_validate_pixi_lock = pixi_lock_v7._validate_pixi_lock

_VerifiedPixi = VerifiedPixiExecutable | pixi_identity._VerifiedPixiHandle


def _verified_pixi_for_platform(
    pixi: _VerifiedPixi | None,
    *,
    platform: ExecutionPlatform,
) -> _VerifiedPixi:
    if pixi is None:
        raise ValueError("capture requires an explicit verified Pixi executable identity")
    if isinstance(pixi, pixi_identity._VerifiedPixiHandle):
        _ = pixi.fd
        return pixi
    validated = VerifiedPixiExecutable.model_validate(pixi)
    if validated.version != PIXI_VERSION:
        raise ValueError(f"verified Pixi version must be exactly {PIXI_VERSION}")
    if validated.distribution != PIXI_DISTRIBUTIONS[platform]:
        raise ValueError("verified Pixi distribution does not match the target platform archive identity")
    return validated


def _resolver_identity(pixi: _VerifiedPixi) -> ResolverIdentity:
    if isinstance(pixi, pixi_identity._VerifiedPixiHandle):
        return pixi.resolver
    return ResolverIdentity(
        name="pixi",
        version=pixi.version,
        config_digest=pixi.distribution.sha256,
    )


def admit_pixi_records(
    records: Iterable[PixiListRecord],
    *,
    pixi: _VerifiedPixi | None = None,
    environment_name: str,
    platform: ExecutionPlatform,
    native_lock_sha256: Sha256Digest,
) -> PlatformLock:
    """Compatibility wrapper around lock-v7 record admission."""

    verified_pixi = _verified_pixi_for_platform(pixi, platform=platform)
    return pixi_lock_v7.admit_pixi_records(
        records,
        resolver=_resolver_identity(verified_pixi),
        environment_name=environment_name,
        target_platform=platform,
        native_lock_sha256=native_lock_sha256,
    )


def compile_pixi_platform_lock(
    pixi_list_content: bytes,
    pixi_lock_content: bytes,
    *,
    pixi: _VerifiedPixi | None = None,
    environment_name: str,
    platform: ExecutionPlatform,
) -> PlatformLock:
    """Compatibility wrapper for captured lock-v7 compilation."""

    verified_pixi = _verified_pixi_for_platform(pixi, platform=platform)
    return pixi_lock_v7._compile_captured_platform_lock(
        pixi_list_content=pixi_list_content,
        pixi_lock_content=pixi_lock_content,
        resolver=_resolver_identity(verified_pixi),
        environment_name=environment_name,
        target_platform=platform,
    )


PixiRunner: TypeAlias = Callable[[tuple[str, ...], Path], bytes]


def _workspace_lock_content(workspace_root: Path) -> bytes:
    try:
        return (workspace_root / "pixi.lock").read_bytes()
    except OSError as error:
        raise ValueError("workspace pixi.lock must be readable") from error


def _optional_workspace_file(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as error:
        raise ValueError(f"workspace control file must be readable: {path.name}") from error


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
    except OSError as error:
        raise ValueError("workspace .pixi state must be readable") from error
    return digest.hexdigest()


def _pixi_tree_state(workspace_root: Path) -> tuple[tuple[object, ...], ...]:
    pixi_root = workspace_root / ".pixi"
    if not pixi_root.exists() and not pixi_root.is_symlink():
        return ()
    state: list[tuple[object, ...]] = []
    total_bytes = 0
    try:
        paths = sorted(pixi_root.rglob("*"), key=lambda path: path.as_posix())
        for path in (pixi_root, *paths):
            relative = path.relative_to(workspace_root).as_posix()
            stat = path.lstat()
            if path.is_symlink():
                state.append((relative, "symlink", path.readlink().as_posix()))
            elif path.is_file():
                total_bytes += stat.st_size
                if total_bytes > _MAX_WORKSPACE_STATE_BYTES:
                    raise ValueError("workspace .pixi state exceeds bounded read-only verification size")
                state.append((relative, "file", stat.st_mode, stat.st_size, _hash_file(path)))
            elif path.is_dir():
                state.append((relative, "directory", stat.st_mode))
            else:
                state.append((relative, "other", stat.st_mode, stat.st_size))
    except OSError as error:
        raise ValueError("workspace .pixi state must be readable") from error
    return tuple(state)


def _read_only_workspace_state(workspace_root: Path) -> tuple[bytes | None, tuple[tuple[object, ...], ...]]:
    return _optional_workspace_file(workspace_root / "pixi.toml"), _pixi_tree_state(workspace_root)


def compile_pixi_platform_lock_with_runner(
    runner: PixiRunner,
    *,
    pixi: VerifiedPixiExecutable | None = None,
    workspace_root: Path,
    pixi_lock_content: bytes,
    environment_name: str,
    platform: ExecutionPlatform,
) -> PlatformLock:
    """Capture one frozen, no-install list from an explicitly verified Pixi binary."""

    verified_pixi = _verified_pixi_for_platform(pixi, platform=platform)
    assert isinstance(verified_pixi, VerifiedPixiExecutable)
    _validate_pixi_lock(
        pixi_lock_content,
        environment_name=environment_name,
        resolver_platform=_PIXI_PLATFORM[platform],
    )
    if _workspace_lock_content(workspace_root) != pixi_lock_content:
        raise ValueError("supplied pixi.lock bytes must equal workspace pixi.lock")
    workspace_state = _read_only_workspace_state(workspace_root)
    try:
        list_content = runner(
            (
                str(verified_pixi.executable_path),
                "list",
                "--frozen",
                "--no-install",
                "--json",
                "--environment",
                environment_name,
                "--platform",
                _PIXI_PLATFORM[platform],
                "--manifest-path",
                str(workspace_root / "pixi.toml"),
            ),
            workspace_root,
        )
    finally:
        if _workspace_lock_content(workspace_root) != pixi_lock_content:
            raise ValueError("workspace pixi.lock changed during locked Pixi commands")
        if _read_only_workspace_state(workspace_root) != workspace_state:
            raise ValueError("Pixi capture must be read-only and must not mutate pixi.toml or .pixi")
    return compile_pixi_platform_lock(
        list_content,
        pixi_lock_content,
        pixi=verified_pixi,
        environment_name=environment_name,
        platform=platform,
    )
