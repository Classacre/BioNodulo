"""Stable owner for ``bctools_remove_spurious_events``."""

from .adapter import _BctoolsRemoveSpuriousEventsContract


class BctoolsRemoveSpuriousEventsNode(_BctoolsRemoveSpuriousEventsContract):
    NODE_ID = "bctools_remove_spurious_events"
    UPSTREAM_SYMBOL = "BctoolsRemoveSpuriousEventsNode"
