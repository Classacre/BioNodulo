"""Focused owner for ``chewbbaca_allelecall``."""

from .adapter import _ChewBBACAAlleleCallContract


class ChewBBACAAlleleCallNode(_ChewBBACAAlleleCallContract):
    NODE_ID = "chewbbaca_allelecall"
    UPSTREAM_SYMBOL = "ChewBBACAAlleleCallNode"
