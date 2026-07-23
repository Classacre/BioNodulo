"""Stable owner for ``beacon2_cnv``."""

from .adapter import _Beacon2CNVContract


class Beacon2CNVNode(_Beacon2CNVContract):
    NODE_ID = "beacon2_cnv"
    UPSTREAM_SYMBOL = "Beacon2CNVNode"
