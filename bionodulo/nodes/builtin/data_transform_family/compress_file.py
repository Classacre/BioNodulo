"""Focused owner for ``compress_file``."""

from bionodulo.nodes.builtin._alignment_taxonomy_utilities_adapter import _CompressFileContract


class CompressFileNode(_CompressFileContract):
    NODE_ID = "compress_file"
    UPSTREAM_SYMBOL = "CompressFileNode"
