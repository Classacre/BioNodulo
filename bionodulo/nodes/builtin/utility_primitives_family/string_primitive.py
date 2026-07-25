"""String primitive node."""

from .adapter import StringPrimitiveNode as _StringPrimitiveContract


class StringPrimitiveNode(_StringPrimitiveContract):
    """Emit one string value."""

    NODE_ID = "string_primitive"
