"""Stable owner for ``cnvkit_call``."""

from .legacy import _CNVkitCallContract


class CNVkitCallNode(_CNVkitCallContract):
    NODE_ID = "cnvkit_call"
