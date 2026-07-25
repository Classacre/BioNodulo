"""Stable owner for the ``type_cast`` node."""

from .adapter import _TypeCastContract


class TypeCastNode(_TypeCastContract):
    NODE_ID = "type_cast"
    UPSTREAM_SYMBOL = "TypeCastNode"
