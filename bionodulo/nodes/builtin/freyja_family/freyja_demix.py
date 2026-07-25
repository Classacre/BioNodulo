"""Focused owner for ``freyja_demix``."""

from .adapter import FreyjaDemixNode as _NodeContract


class FreyjaDemixNode(_NodeContract):
    NODE_ID = "freyja_demix"
    UPSTREAM_SYMBOL = "FreyjaDemixNode"
