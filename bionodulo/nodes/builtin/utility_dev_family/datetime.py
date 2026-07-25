"""Stable owner for the ``datetime`` node."""

from .adapter import _DateTimeContract


class DateTimeNode(_DateTimeContract):
    NODE_ID = "datetime"
    UPSTREAM_SYMBOL = "DateTimeNode"
