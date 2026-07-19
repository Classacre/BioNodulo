"""Workflow result-comparison node."""

from .adapter import CompareResultsNode as _CompareResultsContract


class CompareResultsNode(_CompareResultsContract):
    """Compare two results with an explicit comparison method."""

    NODE_ID = "compare_results"
