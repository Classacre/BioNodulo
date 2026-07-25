"""Pinned Pixi release metadata and host executable identity verification."""

from __future__ import annotations

import hashlib
import errno
import os
import stat
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from bionodulo.nodes.contract.artifacts import _StrictFrozenModel
from bionodulo.nodes.contract.environments import ExecutionPlatform, ResolverIdentity, Sha256Digest


PIXI_VERSION = "0.68.1"
PIXI_TAG_COMMIT = "a2453cacd4a02bc99ee84b5e6015ec83bbb2d397"
_PIXI_RELEASE_BASE = f"https://github.com/prefix-dev/pixi/releases/download/v{PIXI_VERSION}"
_MAX_PIXI_BINARY_BYTES = 256 * 1024 * 1024


class PixiDistribution(_StrictFrozenModel):
    filename: str
    url: str
    archive_sha256: Sha256Digest
    binary_sha256: Sha256Digest

    @property
    def sha256(self) -> str:
        """Compatibility alias for the pinned release archive digest."""

        return self.archive_sha256


PIXI_DISTRIBUTIONS: Mapping[ExecutionPlatform, PixiDistribution] = MappingProxyType(
    {
        ExecutionPlatform.LINUX_AMD64: PixiDistribution(
            filename="pixi-x86_64-unknown-linux-musl.tar.gz",
            url=f"{_PIXI_RELEASE_BASE}/pixi-x86_64-unknown-linux-musl.tar.gz",
            archive_sha256="sha256:f61a9546898cc1caad1956d1b5bba0408de5a24854b648631c0b49555520ed42",
            binary_sha256="sha256:01d29d4b78ab07badf57edda0b3d200bc705d5afb6da9960ebabe7010cd836e4",
        ),
        ExecutionPlatform.LINUX_ARM64: PixiDistribution(
            filename="pixi-aarch64-unknown-linux-musl.tar.gz",
            url=f"{_PIXI_RELEASE_BASE}/pixi-aarch64-unknown-linux-musl.tar.gz",
            archive_sha256="sha256:b2b21272578600086e92f4e1d0e42cb7409c8e541688b9ea61aed7dd6a07a5ad",
            binary_sha256="sha256:a86916c9cf8c84fe8e1a8fbac117dc8bc85a0bf9cfc63e7382d6d45e5101f179",
        ),
    }
)


class _VerifiedPixiHandle:
    def __init__(self, *, fd: int, host_platform: ExecutionPlatform, distribution: PixiDistribution) -> None:
        self._fd = fd
        self.host_platform = host_platform
        self.distribution = distribution

    @property
    def fd(self) -> int:
        if self._fd < 0:
            raise ValueError("verified Pixi executable handle is closed")
        return self._fd

    @property
    def executable(self) -> str:
        return f"/proc/self/fd/{self.fd}"

    @property
    def resolver(self) -> ResolverIdentity:
        return ResolverIdentity(
            name="pixi",
            version=PIXI_VERSION,
            config_digest=self.distribution.archive_sha256,
        )

    def close(self) -> None:
        if self._fd >= 0:
            os.close(self._fd)
            self._fd = -1

    def __enter__(self) -> _VerifiedPixiHandle:
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()


def _stat_identity(value: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _open_verified_pixi(
    executable_path: Path,
    *,
    host_platform: ExecutionPlatform,
    distributions: Mapping[ExecutionPlatform, PixiDistribution] = PIXI_DISTRIBUTIONS,
) -> _VerifiedPixiHandle:
    if not executable_path.is_absolute() or ".." in executable_path.parts:
        raise ValueError("Pixi executable path must be absolute, not a PATH lookup name")
    if executable_path.name != "pixi":
        raise ValueError("Pixi executable path must identify the pixi binary")
    distribution = distributions[host_platform]
    try:
        fd = os.open(
            executable_path,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK,
        )
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise ValueError("Pixi executable must not be a symlink") from error
        raise ValueError("Pixi executable must be readable") from error
    try:
        opened_stat = os.fstat(fd)
        if not stat.S_ISREG(opened_stat.st_mode):
            raise ValueError("Pixi executable must be a regular file")
        if opened_stat.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH) == 0:
            raise ValueError("Pixi executable must have an executable permission bit")
        if not 1 <= opened_stat.st_size <= _MAX_PIXI_BINARY_BYTES:
            raise ValueError(f"Pixi executable size must be between 1 and {_MAX_PIXI_BINARY_BYTES} bytes")
        digest = hashlib.sha256()
        while chunk := os.read(fd, 1024 * 1024):
            digest.update(chunk)
        actual = "sha256:" + digest.hexdigest()
        if actual != distribution.binary_sha256:
            raise ValueError(f"Pixi executable SHA-256 is {actual}, expected {distribution.binary_sha256}")
        if _stat_identity(os.fstat(fd)) != _stat_identity(opened_stat):
            raise ValueError("Pixi executable metadata changed while its SHA-256 was computed")
        os.lseek(fd, 0, os.SEEK_SET)
        return _VerifiedPixiHandle(
            fd=fd,
            host_platform=host_platform,
            distribution=distribution,
        )
    except BaseException:
        os.close(fd)
        raise
