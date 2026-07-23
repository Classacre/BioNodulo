"""Stable owner for ``magicblast``."""

from .adapter import _MagicBlastContract


class MagicBlastNode(_MagicBlastContract):
    NODE_ID = "magicblast"
    UPSTREAM_SYMBOL = "MagicBlastNode"
