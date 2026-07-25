"""Float primitive node."""

from .adapter import FloatPrimitiveNode as _FloatPrimitiveContract


class FloatPrimitiveNode(_FloatPrimitiveContract):
    """Emit one bounded finite floating-point value."""

    NODE_ID = "float_primitive"
