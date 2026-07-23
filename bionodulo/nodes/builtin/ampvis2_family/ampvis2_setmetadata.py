"""Focused registered node for ``ampvis2_setmetadata``."""

from .io_adapter import Ampvis2SetMetadataNode as _NodeContract


class Ampvis2SetMetadataNode(_NodeContract):
    NODE_ID = "ampvis2_setmetadata"
