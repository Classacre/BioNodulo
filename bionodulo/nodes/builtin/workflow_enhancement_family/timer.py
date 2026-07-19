"""Workflow timer node."""

from .adapter import TimerNode as _TimerContract


class TimerNode(_TimerContract):
    """Record one workflow timestamp and pass data through."""

    NODE_ID = "timer"
