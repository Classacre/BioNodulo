"""Boolean primitive node."""

from .adapter import BooleanPrimitiveNode as _BooleanPrimitiveContract


class BooleanPrimitiveNode(_BooleanPrimitiveContract):
    """Emit one normalized boolean value."""

    NODE_ID = "boolean_primitive"
