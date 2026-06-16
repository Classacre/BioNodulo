"""
Real subprocess execution runner.

Executes external bioinformatics tools via async subprocess, capturing
stdout/stderr streams, writing log files, and forwarding log lines via
callback.
"""

from __future__ import annotations

import asyncio
import os
import signal
from pathlib import Path
from typing import Any, Callable


STREAM_CAPTURE_LIMIT = 1024 * 1024
LOG_BATCH_LINES = 50
# Grace period between SIGTERM and SIGKILL when terminating a cancelled or
# timed-out process group.
TERMINATE_GRACE_SECONDS = 5.0


class CommandCancelledError(Exception):
    """Raised when a subprocess is killed because its run was cancelled.

    Distinct from :class:`CommandExecutionError` so the executor can record the
    node as *cancelled* rather than *failed*.

    Attributes:
        cmd: The command string that was cancelled.
    """

    def __init__(self, cmd: str) -> None:
        self.cmd = cmd
        super().__init__(f"Command cancelled: {cmd}")


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


class _Cancelled(Exception):
    """Internal signal that a cancel_event fired while waiting on a process."""


async def _wait_process(
    process: "asyncio.subprocess.Process",
    timeout: float | None,
    cancel_event: asyncio.Event | None,
) -> int:
    """Wait for *process*, honouring *timeout* and *cancel_event*.

    Raises ``asyncio.TimeoutError`` on timeout and :class:`_Cancelled` when the
    cancel event fires before the process exits.
    """
    wait_task = asyncio.ensure_future(process.wait())
    waiters: list[asyncio.Future[Any]] = [wait_task]
    cancel_task: asyncio.Task[bool] | None = None
    if cancel_event is not None:
        cancel_task = asyncio.ensure_future(cancel_event.wait())
        waiters.append(cancel_task)

    try:
        done, _pending = await asyncio.wait(
            waiters, timeout=timeout, return_when=asyncio.FIRST_COMPLETED
        )
        if not done:
            raise asyncio.TimeoutError
        if cancel_task is not None and cancel_task in done and wait_task not in done:
            raise _Cancelled
        return wait_task.result()
    finally:
        # Detach awaiters we are no longer interested in. The caller terminates
        # the process explicitly on the timeout/cancel paths; cancelling these
        # futures just avoids "pending task destroyed" warnings.
        if cancel_task is not None and not cancel_task.done():
            cancel_task.cancel()
        if not wait_task.done():
            wait_task.cancel()


async def _terminate_process(process: "asyncio.subprocess.Process") -> None:
    """Terminate a process group: SIGTERM, grace period, then SIGKILL.

    Falls back to killing just the process when the platform lacks process
    groups or the group is already gone.
    """
    if process.returncode is not None:
        return

    def _signal_group(sig: int) -> None:
        try:
            if os.name != "nt" and process.pid is not None:
                os.killpg(os.getpgid(process.pid), sig)
            else:
                process.send_signal(sig)
        except (ProcessLookupError, PermissionError):
            pass

    try:
        _signal_group(signal.SIGTERM)
    except Exception:
        process.terminate()

    try:
        await asyncio.wait_for(process.wait(), timeout=TERMINATE_GRACE_SECONDS)
        return
    except asyncio.TimeoutError:
        pass

    try:
        _signal_group(signal.SIGKILL)
    except Exception:
        try:
            process.kill()
        except ProcessLookupError:
            pass
    try:
        await process.wait()
    except ProcessLookupError:
        pass


async def run_subprocess(
    cmd: str | list[str],
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
    stdout_path: str | Path | None = None,
    stderr_path: str | Path | None = None,
    emit: Callable[[str, dict[str, Any]], None] | None = None,
    node_id: str | None = None,
    timeout: float | None = None,
    cancel_event: asyncio.Event | None = None,
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
        cancel_event: When set mid-flight, the process group is terminated
            (SIGTERM then SIGKILL) and :class:`CommandCancelledError` is raised.

    Returns:
        Dictionary with ``returncode``, ``stdout_path``, ``stderr_path`` and a
        bounded in-memory tail of each stream.

    Raises:
        CommandCancelledError: If *cancel_event* fires before the process exits.
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
        # Start each process in its own process group (POSIX) / job-control
        # session so cancellation/timeout can terminate the whole tree of
        # children, not just the immediate shell.
        popen_kwargs: dict[str, Any] = {}
        if os.name == "nt":
            popen_kwargs["creationflags"] = getattr(
                __import__("subprocess"), "CREATE_NEW_PROCESS_GROUP", 0
            )
        else:
            popen_kwargs["start_new_session"] = True

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
                **popen_kwargs,
            )
        else:
            process = await asyncio.create_subprocess_exec(
                *(str(part) for part in cmd),
                cwd=str(cwd) if cwd else None,
                env=merged_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                **popen_kwargs,
            )

        stdout_task = asyncio.create_task(
            _drain_stream(process.stdout, stdout_path, "stdout")
        )
        stderr_task = asyncio.create_task(
            _drain_stream(process.stderr, stderr_path, "stderr")
        )

        try:
            returncode = await _wait_process(process, timeout, cancel_event)
        except asyncio.TimeoutError:
            _emit("error", f"[subprocess] Timeout after {timeout}s")
            await _terminate_process(process)
            await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
            raise
        except _Cancelled:
            _emit("error", "[subprocess] Cancelled; terminating process group")
            await _terminate_process(process)
            await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
            raise CommandCancelledError(cmd_str)
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
