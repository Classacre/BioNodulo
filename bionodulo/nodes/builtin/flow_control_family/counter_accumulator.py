"""Stable owner for the ``counter_accumulator`` node."""

from .adapter import _CounterAccumulatorContract


class CounterAccumulatorNode(_CounterAccumulatorContract):
    """Update one explicitly keyed loop accumulator."""

    NODE_ID = "counter_accumulator"
    UPSTREAM_SYMBOL = "CounterAccumulatorNode"
