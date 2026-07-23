"""Focused owner for ``freyja_variants``."""

from .adapter import FreyjaVariantsNode as _NodeContract


class FreyjaVariantsNode(_NodeContract):
    NODE_ID = "freyja_variants"
    UPSTREAM_SYMBOL = "FreyjaVariantsNode"
