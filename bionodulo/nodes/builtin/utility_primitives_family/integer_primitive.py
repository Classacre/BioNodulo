"""Integer primitive node."""

from .adapter import IntegerPrimitiveNode as _IntegerPrimitiveContract


class IntegerPrimitiveNode(_IntegerPrimitiveContract):
    """Emit one bounded 32-bit integer value."""

    NODE_ID = "integer_primitive"
