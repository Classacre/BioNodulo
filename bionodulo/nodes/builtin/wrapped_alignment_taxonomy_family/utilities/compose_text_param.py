"""Stable owner for ``compose_text_param``."""

from .adapter import _ComposeTextParamContract


class ComposeTextParamNode(_ComposeTextParamContract):
    NODE_ID = "compose_text_param"
    UPSTREAM_SYMBOL = "ComposeTextParamNode"
