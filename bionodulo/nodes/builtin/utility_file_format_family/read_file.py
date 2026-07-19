"""Stable owner for the ``read_file`` node."""

from .adapter import _ReadFileContract


class ReadFileNode(_ReadFileContract):
    NODE_ID = "read_file"
    UPSTREAM_SYMBOL = "ReadFileNode"
