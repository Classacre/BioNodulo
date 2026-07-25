"""Focused owner for ``comebin``."""

from .adapter import COMEBinNode as _NodeContract


class COMEBinNode(_NodeContract):
    NODE_ID = "comebin"
    UPSTREAM_SYMBOL = "COMEBinNode"
