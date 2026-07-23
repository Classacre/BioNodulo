"""Focused owner for ``clustalw``."""

from .classic_adapter import ClustalWNode as _NodeContract


class ClustalWNode(_NodeContract):
    NODE_ID = "clustalw"
