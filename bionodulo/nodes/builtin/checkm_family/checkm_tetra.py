"""Focused owner for ``checkm_tetra``."""

from .adapter import _CheckMTetraContract


class CheckMTetraNode(_CheckMTetraContract):
    NODE_ID = "checkm_tetra"
    UPSTREAM_SYMBOL = "CheckMTetraNode"
