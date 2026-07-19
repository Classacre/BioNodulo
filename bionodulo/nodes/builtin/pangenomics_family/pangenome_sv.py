"""Stable owner for ``pangenome_sv``."""

from .legacy import _PangenomeSVContract


class PangenomeSVNode(_PangenomeSVContract):
    NODE_ID = "pangenome_sv"
