"""Stable owner for ``kaiju_merge_outputs``."""

from .adapter import _KaijuMergeOutputsContract


class KaijuMergeOutputsNode(_KaijuMergeOutputsContract):
    NODE_ID = "kaiju_merge_outputs"
    UPSTREAM_SYMBOL = "KaijuMergeOutputsNode"
