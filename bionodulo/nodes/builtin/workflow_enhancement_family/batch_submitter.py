"""Workflow batch-submitter node."""

from .adapter import BatchSubmitterNode as _BatchSubmitterContract


class BatchSubmitterNode(_BatchSubmitterContract):
    """Prepare and submit a bounded workflow batch."""

    NODE_ID = "batch_submitter"
