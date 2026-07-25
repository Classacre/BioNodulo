"""Focused registered node for ``ampvis2_mergereplicates``."""

from .io_adapter import Ampvis2MergeReplicatesNode as _NodeContract


class Ampvis2MergeReplicatesNode(_NodeContract):
    NODE_ID = "ampvis2_mergereplicates"
