"""Focused owner for ``abyss_pe``."""

from .adapter import ABySSPENode as _NodeContract


class ABySSPENode(_NodeContract):
    NODE_ID = "abyss_pe"
    UPSTREAM_SYMBOL = "ABySSPENode"
