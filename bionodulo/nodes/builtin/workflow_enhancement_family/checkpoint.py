"""Workflow checkpoint node."""

from .adapter import CheckpointNode as _CheckpointContract


class CheckpointNode(_CheckpointContract):
    """Persist a workflow checkpoint artifact."""

    NODE_ID = "checkpoint"
