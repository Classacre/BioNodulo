"""Stable owner for ``checkm_qa``."""

from .adapter import _CheckMQAContract


class CheckMQANode(_CheckMQAContract):
    NODE_ID = "checkm_qa"
    UPSTREAM_SYMBOL = "CheckMQANode"
