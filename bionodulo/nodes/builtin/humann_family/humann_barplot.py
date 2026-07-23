"""Stable owner for ``humann_barplot``."""

from .adapter import _HUMAnNBarplotContract


class HUMAnNBarplotNode(_HUMAnNBarplotContract):
    NODE_ID = "humann_barplot"
    UPSTREAM_SYMBOL = "HUMAnNBarplotNode"
