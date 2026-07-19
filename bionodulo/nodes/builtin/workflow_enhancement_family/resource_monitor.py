"""Workflow resource-monitor node."""

from .adapter import ResourceMonitorNode as _ResourceMonitorContract


class ResourceMonitorNode(_ResourceMonitorContract):
    """Gate execution on measured CPU, memory, and disk resources."""

    NODE_ID = "resource_monitor"
