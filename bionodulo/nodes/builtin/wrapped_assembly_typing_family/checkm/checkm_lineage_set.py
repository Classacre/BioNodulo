"""Stable owner for ``checkm_lineage_set``."""

from .adapter import _CheckMLineageSetContract


class CheckMLineageSetNode(_CheckMLineageSetContract):
    NODE_ID = "checkm_lineage_set"
    UPSTREAM_SYMBOL = "CheckMLineageSetNode"
