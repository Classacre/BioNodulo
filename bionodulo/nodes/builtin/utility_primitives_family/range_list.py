"""Integer range-list utility node."""

from .adapter import RangeListNode as _RangeListContract


class RangeListNode(_RangeListContract):
    """Emit a bounded integer range as JSON."""

    NODE_ID = "range_list"
