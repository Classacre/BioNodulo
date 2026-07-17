"""Isolated orchestration for verified, locked Pixi list capture."""

from __future__ import annotations

import os
import selectors
import signal
import stat
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TypeAlias

from bionodulo.nodes.contract.environments import ExecutionPlatform, PlatformLock
from bionodulo.nodes.environment_compiler import pixi_identity, pixi_lock_v7, pixi_manifest


_MAX_PIXI_TOML_BYTES = 1024 * 1024
_MAX_CAPTURE_ERROR_BYTES = 4096
_PIXI_CAPTURE_TIMEOUT_SECONDS = 120.0
_CAPTURE_CHUNK_BYTES = 64 * 1024
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


def _kill_and_reap(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()
    if process.stdout is not None:
        process.stdout.close()
    if process.stderr is not None:
        process.stderr.close()


def _capture_pixi_list(command: tuple[str, ...], cwd: Path, executable_fd: int) -> bytes:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        pass_fds=(executable_fd,),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    if process.stdout is None or process.stderr is None:  # pragma: no cover - PIPE contract
        _kill_and_reap(process)
        raise RuntimeError("Pixi capture pipes were not created")
    stdout_pipe = process.stdout
    stderr_pipe = process.stderr
    captured_stdout = bytearray()
    captured_stderr = bytearray()
    selector = selectors.DefaultSelector()
    selector.register(stdout_pipe, selectors.EVENT_READ, data="stdout")
    selector.register(stderr_pipe, selectors.EVENT_READ, data="stderr")
    deadline = time.monotonic() + _PIXI_CAPTURE_TIMEOUT_SECONDS
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ValueError(f"locked Pixi list capture timed out after {_PIXI_CAPTURE_TIMEOUT_SECONDS:g} seconds")
            for key, _ in selector.select(min(remaining, 0.1)):
                if key.data == "stdout":
                    target = captured_stdout
                    maximum = pixi_lock_v7._MAX_PIXI_LIST_BYTES
                    pipe = stdout_pipe
                else:
                    target = captured_stderr
                    maximum = _MAX_CAPTURE_ERROR_BYTES
                    pipe = stderr_pipe
                read_size = min(_CAPTURE_CHUNK_BYTES, maximum - len(target) + 1)
                chunk = os.read(key.fd, read_size)
                if not chunk:
                    selector.unregister(pipe)
                    pipe.close()
                    continue
                target.extend(chunk)
                if len(target) > maximum:
                    label = "Pixi list JSON" if key.data == "stdout" else "Pixi capture stderr"
                    raise ValueError(f"{label} exceeds {maximum} bytes")
        returncode = process.wait()
        if returncode != 0:
            stderr = bytes(captured_stderr)
            detail = stderr.decode("utf-8", errors="replace").strip()
            suffix = f": {detail}" if detail else ""
            error = subprocess.CalledProcessError(
                returncode,
                command,
                output=bytes(captured_stdout),
                stderr=stderr,
            )
            raise ValueError(f"locked Pixi list capture failed with exit code {returncode}{suffix}") from error
        return bytes(captured_stdout)
    except BaseException:
        _kill_and_reap(process)
        raise
    finally:
        selector.close()
        if not stdout_pipe.closed:
            stdout_pipe.close()
        if not stderr_pipe.closed:
            stderr_pipe.close()


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
    requested_specs = pixi_manifest._derive_requested_specs(
        pixi_toml_content,
        environment_name=environment_name,
        target_platform=target_platform,
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
            requested_specs=requested_specs,
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
