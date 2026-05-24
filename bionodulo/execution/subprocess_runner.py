"""
Real subprocess execution runner.

Executes external bioinformatics tools via async subprocess, capturing
stdout/stderr streams, writing log files, and forwarding log lines via
callback.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Callable


STREAM_CAPTURE_LIMIT = 1024 * 1024
LOG_BATCH_LINES = 50


class CommandExecutionError(Exception):
    """Raised when a subprocess command exits with a non-zero code.

    Attributes:
        cmd: The command string that failed.
        returncode: The exit code returned by the process.
        stdout_path: Path to the captured stdout log file.
        stderr_path: Path to the captured stderr log file.
    """

    def __init__(
        self,
        cmd: str,
        returncode: int,
        stdout_path: str | Path,
        stderr_path: str | Path,
    ) -> None:
        self.cmd = cmd
        self.returncode = returncode
        self.stdout_path = Path(stdout_path)
        self.stderr_path = Path(stderr_path)
        super().__init__(
            f"Command failed with exit code {returncode}: {cmd}\n"
            f"  stdout: {self.stdout_path}\n"
            f"  stderr: {self.stderr_path}"
        )


async def run_subprocess(
    cmd: str | list[str],
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
    stdout_path: str | Path | None = None,
    stderr_path: str | Path | None = None,
    emit: Callable[[str, dict[str, Any]], None] | None = None,
    node_id: str | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Run an external command asynchronously with streaming log capture.

    Args:
        cmd: Shell command string or argument list.
        cwd: Working directory for the subprocess.
        env: Additional environment variables (merged with current env).
        stdout_path: Path to write captured stdout. If *None*, stdout is
            discarded after streaming.
        stderr_path: Path to write captured stderr. If *None*, stderr is
            discarded after streaming.
        emit: Optional callback for real-time log events.
        node_id: Node identifier included in emitted log events.
        timeout: Maximum seconds to wait for the process.

    Returns:
        Dictionary with ``returncode``, ``stdout_path``, ``stderr_path`` and a
        bounded in-memory tail of each stream.

    Raises:
        CommandExecutionError: If the process exits with a non-zero code.
        asyncio.TimeoutError: If the process exceeds *timeout* seconds.
    """
    cwd = Path(cwd) if cwd else None
    stdout_path = Path(stdout_path) if stdout_path else None
    stderr_path = Path(stderr_path) if stderr_path else None

    if stdout_path:
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
    if stderr_path:
        stderr_path.parent.mkdir(parents=True, exist_ok=True)

    merged_env = None
    if env:
        merged_env = {**dict(os.environ), **env}

    cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)

    def _emit(level: str, message: str) -> None:
        if emit:
            emit(
                "log",
                {
                    "node_id": node_id or "subprocess",
                    "level": level,
                    "message": message,
                },
            )

    _emit("info", f"[subprocess] Starting: {cmd_str}")

    async def _drain_stream(
        stream: asyncio.StreamReader | None,
        path: Path | None,
        level: str,
    ) -> tuple[str, bool]:
        if stream is None:
            return "", False

        captured = bytearray()
        truncated = False
        batch: list[str] = []

        def _capture(text: str) -> None:
            nonlocal truncated
            encoded = text.encode("utf-8", errors="replace")
            captured.extend(encoded)
            overflow = len(captured) - STREAM_CAPTURE_LIMIT
            if overflow > 0:
                del captured[:overflow]
                truncated = True

        def _queue_log(text: str) -> None:
            for line in text.splitlines():
                batch.append(line)
                if len(batch) >= LOG_BATCH_LINES:
                    _emit(level, "\n".join(batch))
                    batch.clear()

        handle = path.open("w", encoding="utf-8", errors="replace") if path else None
        try:
            while True:
                raw = await stream.readline()
                if not raw:
                    break
                text = raw.decode("utf-8", errors="replace")
                _capture(text)
                _queue_log(text)
                if handle:
                    handle.write(text)
                    if len(batch) == 0:
                        handle.flush()
            if batch:
                _emit(level, "\n".join(batch))
            if handle:
                handle.flush()
        finally:
            if handle:
                handle.close()

        return captured.decode("utf-8", errors="replace"), truncated

    try:
        if isinstance(cmd, str):
            shell_kwargs: dict[str, Any] = {}
            if os.name != "nt":
                shell_kwargs["executable"] = "/bin/bash"
            process = await asyncio.create_subprocess_shell(
                cmd,
                cwd=str(cwd) if cwd else None,
                env=merged_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                **shell_kwargs,
            )
        else:
            process = await asyncio.create_subprocess_exec(
                *(str(part) for part in cmd),
                cwd=str(cwd) if cwd else None,
                env=merged_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

        stdout_task = asyncio.create_task(
            _drain_stream(process.stdout, stdout_path, "stdout")
        )
        stderr_task = asyncio.create_task(
            _drain_stream(process.stderr, stderr_path, "stderr")
        )
        try:
            returncode = await asyncio.wait_for(process.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            _emit("error", f"[subprocess] Timeout after {timeout}s")
            process.kill()
            await process.wait()
            await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
            raise
        stdout_result, stderr_result = await asyncio.gather(stdout_task, stderr_task)
    except asyncio.TimeoutError:
        raise

    _emit("info", f"[subprocess] Finished with exit code {returncode}")

    result = {
        "returncode": returncode,
        "stdout": stdout_result[0],
        "stderr": stderr_result[0],
        "stdout_truncated": stdout_result[1],
        "stderr_truncated": stderr_result[1],
        "stdout_path": str(stdout_path) if stdout_path else None,
        "stderr_path": str(stderr_path) if stderr_path else None,
    }

    if returncode != 0:
        raise CommandExecutionError(
            cmd=cmd_str,
            returncode=returncode,
            stdout_path=stdout_path or Path("/dev/null"),
            stderr_path=stderr_path or Path("/dev/null"),
        )

    return result
