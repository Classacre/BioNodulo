from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from bionodulo.execution.errors import (
    NodeCancelledError,
    NodeError,
    NodeExitCodeError,
    NodeMemoryError,
    NodeTimeoutError,
    looks_like_oom,
)
from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.execution.subprocess_runner import (
    CommandCancelledError,
    CommandExecutionError,
    CommandOOMError,
    run_subprocess,
)


@pytest.mark.asyncio
async def test_subprocess_timeout_raises_typed_node_timeout_error(tmp_path: Path) -> None:
    with pytest.raises(NodeTimeoutError) as exc_info:
        await run_subprocess(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            stdout_path=tmp_path / "out.log",
            stderr_path=tmp_path / "err.log",
            timeout=0.2,
        )

    assert exc_info.value.timeout_seconds == 0.2
    assert isinstance(exc_info.value, asyncio.TimeoutError)


@pytest.mark.asyncio
async def test_subprocess_nonzero_exit_raises_typed_exit_code_error_with_tail(tmp_path: Path) -> None:
    with pytest.raises(NodeExitCodeError) as exc_info:
        await run_subprocess(
            [
                sys.executable,
                "-c",
                "import sys; print('boom-detail', file=sys.stderr); sys.exit(3)",
            ],
            stdout_path=tmp_path / "out.log",
            stderr_path=tmp_path / "err.log",
        )

    assert exc_info.value.exit_code == 3
    assert "boom-detail" in exc_info.value.stderr_tail
    # Legacy import path and handlers keep working.
    assert isinstance(exc_info.value, CommandExecutionError)
    assert exc_info.value.returncode == 3
    assert exc_info.value.stderr_path.exists()


@pytest.mark.asyncio
async def test_subprocess_oom_exit_raises_typed_memory_error(tmp_path: Path) -> None:
    with pytest.raises(NodeMemoryError) as exc_info:
        await run_subprocess(
            [
                sys.executable,
                "-c",
                "import sys; print('std::bad_alloc', file=sys.stderr); sys.exit(137)",
            ],
            stdout_path=tmp_path / "out.log",
            stderr_path=tmp_path / "err.log",
        )

    assert isinstance(exc_info.value, CommandOOMError)
    assert exc_info.value.exit_code == 137
    assert "bad_alloc" in exc_info.value.evidence
    # Still a CommandExecutionError for existing handlers.
    assert isinstance(exc_info.value, CommandExecutionError)


@pytest.mark.asyncio
async def test_subprocess_oom_stderr_pattern_without_137_code(tmp_path: Path) -> None:
    with pytest.raises(NodeMemoryError):
        await run_subprocess(
            [
                sys.executable,
                "-c",
                "import sys; print('python: out of memory', file=sys.stderr); sys.exit(1)",
            ],
            stdout_path=tmp_path / "out.log",
            stderr_path=tmp_path / "err.log",
        )


def test_looks_like_oom_matches_exit_codes_and_patterns() -> None:
    assert looks_like_oom(137, "")
    assert looks_like_oom(-9, "")
    assert looks_like_oom(1, "Fatal Python error: Cannot allocate memory")
    assert looks_like_oom(2, "process OOM-killed (Killed)")
    assert not looks_like_oom(3, "file not found")
    assert not looks_like_oom(0, "")


@pytest.mark.asyncio
async def test_subprocess_cancel_raises_node_cancelled_taxonomy(tmp_path: Path) -> None:
    cancel_event = asyncio.Event()

    async def _cancel_soon() -> None:
        await asyncio.sleep(0.2)
        cancel_event.set()

    canceller = asyncio.create_task(_cancel_soon())
    try:
        with pytest.raises(CommandCancelledError) as exc_info:
            await run_subprocess(
                [sys.executable, "-c", "import time; time.sleep(10)"],
                stdout_path=tmp_path / "out.log",
                stderr_path=tmp_path / "err.log",
                cancel_event=cancel_event,
            )
    finally:
        await canceller

    assert isinstance(exc_info.value, NodeCancelledError)
    assert isinstance(exc_info.value, NodeError)


def test_taxonomy_codes_are_stable() -> None:
    assert NodeError("x").code == "node_error"
    assert NodeTimeoutError(5).code == "node_timeout"
    assert NodeMemoryError("evidence").code == "node_memory"
    assert NodeExitCodeError(exit_code=2).code == "node_exit_code"
    assert NodeCancelledError().code == "node_cancelled"


def test_retry_policy_dispatches_on_exception_type_first() -> None:
    oom = CommandOOMError("cmd", 137, "/o", "/e", "std::bad_alloc")
    timeout = NodeTimeoutError(30)
    exit_code = CommandExecutionError("cmd", 3, "/o", "/e", "tail")
    cancelled = CommandCancelledError("cmd")

    assert WorkflowExecutor._retry_matches_exception({"retry_on": "memory"}, oom)
    assert not WorkflowExecutor._retry_matches_exception({"retry_on": "timeout"}, oom)
    assert not WorkflowExecutor._retry_matches_exception({"retry_on": "exit_code"}, oom)

    assert WorkflowExecutor._retry_matches_exception({"retry_on": "timeout"}, timeout)
    assert not WorkflowExecutor._retry_matches_exception({"retry_on": "memory"}, timeout)

    assert WorkflowExecutor._retry_matches_exception({"retry_on": "exit_code"}, exit_code)
    assert not WorkflowExecutor._retry_matches_exception({"retry_on": "memory"}, exit_code)

    assert WorkflowExecutor._retry_matches_exception({"retry_on": "all"}, oom)
    assert WorkflowExecutor._retry_matches_exception({"retry_on": "all"}, cancelled)
    assert not WorkflowExecutor._retry_matches_exception({"retry_on": "timeout"}, cancelled)
    assert not WorkflowExecutor._retry_matches_exception(None, oom)


def test_retry_policy_text_matching_still_covers_generic_exceptions() -> None:
    policy = {"retry_on": "timeout"}
    assert WorkflowExecutor._retry_matches_exception(policy, RuntimeError("Operation timed out"))
    assert WorkflowExecutor._retry_matches_exception(policy, TimeoutError("deadline exceeded"))

    memory_policy = {"retry_on": "memory"}
    assert WorkflowExecutor._retry_matches_exception(memory_policy, RuntimeError("OOM during sort"))

    exit_policy = {"retry_on": "exit_code"}
    assert WorkflowExecutor._retry_matches_exception(exit_policy, RuntimeError("exit code 2"))
    assert not WorkflowExecutor._retry_matches_exception(exit_policy, RuntimeError("unrelated"))


def test_legacy_command_error_constructor_still_works_positionally(tmp_path: Path) -> None:
    exc = CommandExecutionError("bwrap", 1, tmp_path / "stdout.log", tmp_path / "stderr.log")

    assert isinstance(exc, NodeExitCodeError)
    assert exc.exit_code == 1
    assert exc.stderr_tail == ""
    assert str(exc).startswith("Command failed with exit code 1: bwrap")


def test_error_code_helper_covers_typed_and_plain_exceptions() -> None:
    executor = WorkflowExecutor()
    for exc in (
        NodeTimeoutError(9),
        NodeMemoryError("evidence"),
        NodeExitCodeError(exit_code=7, stderr_tail="tail"),
        RuntimeError("plain"),
    ):
        assert executor._error_code(exc) == getattr(exc, "code", "")
