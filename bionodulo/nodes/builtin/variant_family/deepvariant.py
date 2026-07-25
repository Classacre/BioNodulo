"""Stable owner for ``deepvariant``."""

from .legacy import _DeepVariantContract


class DeepVariantNode(_DeepVariantContract):
    NODE_ID = "deepvariant"
