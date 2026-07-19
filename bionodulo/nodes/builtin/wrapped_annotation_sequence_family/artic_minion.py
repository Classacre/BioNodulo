"""Stable owner for ``artic_minion``."""

from .legacy import _ArticMinionContract


class ArticMinionNode(_ArticMinionContract):
    NODE_ID = "artic_minion"
