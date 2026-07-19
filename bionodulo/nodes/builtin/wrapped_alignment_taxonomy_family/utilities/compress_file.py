"""Stable owner for ``compress_file``."""

from .adapter import _CompressFileContract


class CompressFileNode(_CompressFileContract):
    NODE_ID = "compress_file"
    UPSTREAM_SYMBOL = "CompressFileNode"
