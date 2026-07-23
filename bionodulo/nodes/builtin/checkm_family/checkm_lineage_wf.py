"""Focused owner for ``checkm_lineage_wf``."""

from .adapter import _CheckMLineageWFContract


class CheckMLineageWFNode(_CheckMLineageWFContract):
    NODE_ID = "checkm_lineage_wf"
    UPSTREAM_SYMBOL = "CheckMLineageWFNode"
