"""Stable owner for the ``write_file`` node."""

from .adapter import _WriteFileContract


class WriteFileNode(_WriteFileContract):
    NODE_ID = "write_file"
    UPSTREAM_SYMBOL = "WriteFileNode"
