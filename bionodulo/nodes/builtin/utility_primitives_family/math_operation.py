"""Arithmetic utility node."""

from .adapter import MathNode as _MathContract


class MathNode(_MathContract):
    """Apply one finite arithmetic operation to two operands."""

    NODE_ID = "math"
