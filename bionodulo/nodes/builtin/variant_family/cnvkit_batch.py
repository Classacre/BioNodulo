"""Stable owner for ``cnvkit_batch``."""

from .legacy import _CNVkitBatchContract


class CNVkitBatchNode(_CNVkitBatchContract):
    NODE_ID = "cnvkit_batch"
