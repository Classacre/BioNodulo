"""Workflow pause/resume node."""

from .adapter import PauseResumeNode as _PauseResumeContract


class PauseResumeNode(_PauseResumeContract):
    """Persist a human-review decision gate."""

    NODE_ID = "pause_resume"
