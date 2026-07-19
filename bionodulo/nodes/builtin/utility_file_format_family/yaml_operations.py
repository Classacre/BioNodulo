"""Stable owner for the ``yaml_operations`` node."""

from .adapter import _YMLOperationsContract


class YMLOperationsNode(_YMLOperationsContract):
    NODE_ID = "yaml_operations"
    UPSTREAM_SYMBOL = "YMLOperationsNode"
