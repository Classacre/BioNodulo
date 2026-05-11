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
    """Run an external command asynchronously with full stream capture.

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
        Dictionary with ``returncode``, ``stdout_path``, ``stderr_path``.

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

    if isinstance(cmd, str):
        proc_cmd = cmd
        shell = True
    else:
        proc_cmd = cmd
        shell = False

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

    _emit("info", f"[subprocess] Starting: {cmd if isinstance(cmd, str) else ' '.join(cmd)}")

    stdout_fh = open(stdout_path, "w", encoding="utf-8") if stdout_path else None
    stderr_fh = open(stderr_path, "w", encoding="utf-8") if stderr_path else None

    try:
        if shell:
            process = await asyncio.create_subprocess_shell(
                proc_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=merged_env,
            )
        else:
            process = await asyncio.create_subprocess_exec(
                *proc_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=merged_env,
            )

        async def _read_stream(
            stream: asyncio.StreamReader | None,
            fh: Any,
            level: str,
        ) -> None:
            if stream is None:
                return
            while True:
                try:
                    line = await stream.readline()
                except Exception:
                    break
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip("\n")
                if fh:
                    fh.write(text + "\n")
                    fh.flush()
                _emit(level, text)

        await asyncio.wait_for(
            asyncio.gather(
                _read_stream(process.stdout, stdout_fh, "stdout"),
                _read_stream(process.stderr, stderr_fh, "stderr"),
            ),
            timeout=timeout,
        )

        returncode = await process.wait()

    except asyncio.TimeoutError:
        try:
            process.kill()
            await process.wait()
        except Exception:
            pass
        _emit("error", f"[subprocess] Timeout after {timeout}s")
        raise
    finally:
        if stdout_fh:
            stdout_fh.close()
        if stderr_fh:
            stderr_fh.close()

    _emit("info", f"[subprocess] Finished with exit code {returncode}")

    result = {
        "returncode": returncode,
        "stdout_path": str(stdout_path) if stdout_path else None,
        "stderr_path": str(stderr_path) if stderr_path else None,
    }

    if returncode != 0:
        raise CommandExecutionError(
            cmd=cmd if isinstance(cmd, str) else " ".join(cmd),
            returncode=returncode,
            stdout_path=stdout_path or Path("/dev/null"),
            stderr_path=stderr_path or Path("/dev/null"),
        )

    return result
