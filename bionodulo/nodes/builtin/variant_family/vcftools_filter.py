"""Stable owner for ``vcftools_filter``."""

from .legacy import _VcfToolsFilterContract


class VcfToolsFilterNode(_VcfToolsFilterContract):
    NODE_ID = "vcftools_filter"
