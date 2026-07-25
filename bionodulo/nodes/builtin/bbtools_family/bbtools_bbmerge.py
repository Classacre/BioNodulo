"""Focused owner for ``bbtools_bbmerge``."""

from .adapter import BBToolsBBMergeNode as _NodeContract


class BBToolsBBMergeNode(_NodeContract):
    NODE_ID = "bbtools_bbmerge"
