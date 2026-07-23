"""Focused owner for ``bbtools_bbmap``."""

from .adapter import BBToolsBBMapNode as _NodeContract


class BBToolsBBMapNode(_NodeContract):
    NODE_ID = "bbtools_bbmap"
