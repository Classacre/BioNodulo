"""Focused owner for ``bbtools_tadpole``."""

from .adapter import BBToolsTadpoleNode as _NodeContract


class BBToolsTadpoleNode(_NodeContract):
    NODE_ID = "bbtools_tadpole"
