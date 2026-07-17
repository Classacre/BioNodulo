"""Isolated orchestration for verified, locked Pixi list capture."""

from __future__ import annotations

import stat
import subprocess
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TypeAlias

from bionodulo.nodes.contract.environments import ExecutionPlatform, PlatformLock
from bionodulo.nodes.environment_compiler import pixi_identity, pixi_lock_v7


_MAX_PIXI_TOML_BYTES = 1024 * 1024
_MAX_CAPTURE_ERROR_BYTES = 4096
_PixiCapture: TypeAlias = Callable[[tuple[str, ...], Path, int], bytes]


def _verify_staged_inputs(
    stage: Path,
    *,
    pixi_toml_content: bytes,
    pixi_lock_content: bytes,
) -> None:
    expected = {
        "pixi.toml": pixi_toml_content,
        "pixi.lock": pixi_lock_content,
    }
    if {path.name for path in stage.iterdir()} != set(expected):
        raise ValueError("isolated Pixi stage must contain only pixi.toml and pixi.lock")
    for filename, content in expected.items():
        path = stage / filename
        metadata = path.lstat()
        if not stat.S_ISREG(metadata.st_mode) or path.is_symlink():
            raise ValueError(f"staged {filename} must remain a regular file")
        if path.read_bytes() != content:
            raise ValueError(f"staged {filename} changed during locked Pixi capture")


def _capture_pixi_list(command: tuple[str, ...], cwd: Path, executable_fd: int) -> bytes:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            pass_fds=(executable_fd,),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as error:
        stderr = error.stderr if type(error.stderr) is bytes else b""
        detail = stderr[:_MAX_CAPTURE_ERROR_BYTES].decode("utf-8", errors="replace").strip()
        suffix = f": {detail}" if detail else ""
        raise ValueError(f"locked Pixi list capture failed with exit code {error.returncode}{suffix}") from error
    if len(completed.stdout) > pixi_lock_v7._MAX_PIXI_LIST_BYTES:
        raise ValueError(f"Pixi list JSON exceeds {pixi_lock_v7._MAX_PIXI_LIST_BYTES} bytes")
    return completed.stdout


def _compile_with_capture_for_test(
    *,
    pixi_toml_content: bytes,
    pixi_lock_content: bytes,
    capture: _PixiCapture,
    verified_pixi: pixi_identity._VerifiedPixiHandle,
    target_platform: ExecutionPlatform,
    environment_name: str,
) -> PlatformLock:
    if type(pixi_toml_content) is not bytes:
        raise TypeError("pixi.toml content must be exact bytes")
    if not pixi_toml_content or len(pixi_toml_content) > _MAX_PIXI_TOML_BYTES:
        raise ValueError(f"pixi.toml size must be between 1 and {_MAX_PIXI_TOML_BYTES} bytes")
    pixi_lock_v7._validate_pixi_lock(
        pixi_lock_content,
        environment_name=environment_name,
        resolver_platform=pixi_lock_v7.PIXI_PLATFORM[target_platform],
    )
    with TemporaryDirectory(prefix="bionodulo-pixi-") as temporary_directory:
        stage = Path(temporary_directory)
        (stage / "pixi.toml").write_bytes(pixi_toml_content)
        (stage / "pixi.lock").write_bytes(pixi_lock_content)
        command = (
            verified_pixi.executable,
            "list",
            "--locked",
            "--no-install",
            "--json",
            "--environment",
            environment_name,
            "--platform",
            pixi_lock_v7.PIXI_PLATFORM[target_platform],
            "--manifest-path",
            str(stage / "pixi.toml"),
        )
        try:
            pixi_list_content = capture(command, stage, verified_pixi.fd)
        finally:
            _verify_staged_inputs(
                stage,
                pixi_toml_content=pixi_toml_content,
                pixi_lock_content=pixi_lock_content,
            )
        return pixi_lock_v7._compile_captured_platform_lock(
            pixi_list_content=pixi_list_content,
            pixi_lock_content=pixi_lock_content,
            resolver=verified_pixi.resolver,
            environment_name=environment_name,
            target_platform=target_platform,
        )


def compile_pixi_platform_lock(
    pixi_toml_content: bytes,
    pixi_lock_content: bytes,
    *,
    pixi_executable: Path,
    host_platform: ExecutionPlatform,
    target_platform: ExecutionPlatform,
    environment_name: str,
) -> PlatformLock:
    """Compile one target lock through a verified host Pixi binary."""

    with pixi_identity._open_verified_pixi(
        pixi_executable,
        host_platform=host_platform,
    ) as verified_pixi:
        return _compile_with_capture_for_test(
            pixi_toml_content=pixi_toml_content,
            pixi_lock_content=pixi_lock_content,
            capture=_capture_pixi_list,
            verified_pixi=verified_pixi,
            target_platform=target_platform,
            environment_name=environment_name,
        )
