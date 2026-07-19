"""Stable owner for ``survivor_merge``."""

from .legacy import _SURVIVORMergeContract


class SURVIVORMergeNode(_SURVIVORMergeContract):
    NODE_ID = "survivor_merge"
