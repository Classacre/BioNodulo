"""Focused owner for ``compose_text_param``."""

from bionodulo.nodes.builtin._alignment_taxonomy_utilities_adapter import _ComposeTextParamContract


class ComposeTextParamNode(_ComposeTextParamContract):
    NODE_ID = "compose_text_param"
    UPSTREAM_SYMBOL = "ComposeTextParamNode"
