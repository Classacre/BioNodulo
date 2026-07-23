"""Stable owner for ``humann_unpack_pathways``."""

from .adapter import _HUMAnNUnpackPathwaysContract


class HUMAnNUnpackPathwaysNode(_HUMAnNUnpackPathwaysContract):
    NODE_ID = "humann_unpack_pathways"
    UPSTREAM_SYMBOL = "HUMAnNUnpackPathwaysNode"
