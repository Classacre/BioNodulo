"""Workflow trigger-registration node."""

from .adapter import WorkflowTriggerNode as _WorkflowTriggerContract


class WorkflowTriggerNode(_WorkflowTriggerContract):
    """Register webhook, schedule, or file-watch workflow triggers."""

    NODE_ID = "workflow_trigger"
