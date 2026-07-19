"""Workflow retry node."""

from .adapter import RetryNode as _RetryContract


class RetryNode(_RetryContract):
    """Describe bounded retry policy for a workflow value."""

    NODE_ID = "retry"
