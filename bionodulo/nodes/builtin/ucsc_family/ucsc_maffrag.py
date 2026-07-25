"""Focused registered owner for ``ucsc_maffrag``."""

from .maf_adapter import UcscMafFragNode as _NodeContract


class UcscMafFragNode(_NodeContract):
    NODE_ID = "ucsc_maffrag"
