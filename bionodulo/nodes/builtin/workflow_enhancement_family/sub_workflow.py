"""Nested sub-workflow node."""

from .adapter import SubWorkflowNode as _SubWorkflowContract


class SubWorkflowNode(_SubWorkflowContract):
    """Prepare or execute a nested workflow."""

    NODE_ID = "sub_workflow"
