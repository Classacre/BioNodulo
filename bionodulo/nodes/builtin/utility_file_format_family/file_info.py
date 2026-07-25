"""Stable owner for the ``file_info`` node."""

from .adapter import _FileInfoContract


class FileInfoNode(_FileInfoContract):
    NODE_ID = "file_info"
    UPSTREAM_SYMBOL = "FileInfoNode"
