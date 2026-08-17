"""Typed error taxonomy for node execution failures.

Retry policies and the run-event log dispatch on these types (``code``) so the
engine no longer string-matches exception text. Generic errors raised by
third-party nodes keep working: they simply carry no taxonomy code and the
executor falls back to legacy text matching.
"""

from __future__ import annotations

OOM_STDERR_PATTERNS = (
    "cannot allocate memory",
    "out of memory",
    "std::bad_alloc",
    "memoryerror",
    "cuda out of memory",
    "killed",
)
OOM_EXIT_CODES = frozenset({137, -9})


def looks_like_oom(returncode: int, stderr: str) -> bool:
    """Heuristic OOM detection: SIGKILL-style exit codes or known stderr text."""
    if returncode in OOM_EXIT_CODES:
        return True
    lowered = (stderr or "").lower()
    return any(pattern in lowered for pattern in OOM_STDERR_PATTERNS)


class NodeError(Exception):
    """Base class for typed node execution failures."""

    code = "node_error"

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class NodeCancelledError(NodeError):
    """A node was aborted because its run was cancelled."""

    code = "node_cancelled"


class NodeTimeoutError(NodeError, TimeoutError):
    """A node exceeded its execution time budget.

    Also subclasses :class:`TimeoutError` (== ``asyncio.TimeoutError`` on
    Python 3.11+) so existing ``except asyncio.TimeoutError`` handlers keep
    working.
    """

    code = "node_timeout"

    def __init__(self, timeout_seconds: float | None = None, message: str | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        label = f"{timeout_seconds}s" if timeout_seconds is not None else "the time budget"
        super().__init__(message or f"Node timed out after {label}")


class NodeMemoryError(NodeError):
    """A node failed from out-of-memory conditions (OOM kill or allocator)."""

    code = "node_memory"

    def __init__(self, evidence: str = "", message: str | None = None) -> None:
        self.evidence = evidence
        # Explicit base call: subclasses mix this with CommandExecutionError,
        # where a cooperative super() would re-enter the sibling __init__.
        NodeError.__init__(self, message or "Node failed with an out-of-memory condition")


class NodeExitCodeError(NodeError):
    """A node's process exited with a non-zero exit code."""

    code = "node_exit_code"

    def __init__(
        self,
        exit_code: int = 0,
        stderr_tail: str = "",
        message: str | None = None,
    ) -> None:
        self.exit_code = exit_code
        self.stderr_tail = stderr_tail
        NodeError.__init__(self, message or f"Node process exited with code {exit_code}")
