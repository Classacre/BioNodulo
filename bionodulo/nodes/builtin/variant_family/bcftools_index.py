"""Stable owner for ``bcftools_index``."""

from .legacy import _BcftoolsIndexContract


class BcftoolsIndexNode(_BcftoolsIndexContract):
    NODE_ID = "bcftools_index"
