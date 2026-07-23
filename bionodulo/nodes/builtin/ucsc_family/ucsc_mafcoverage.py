"""Focused registered owner for ``ucsc_mafcoverage``."""

from .maf_extra_adapter import UcscMafCoverageNode as _NodeContract


class UcscMafCoverageNode(_NodeContract):
    NODE_ID = "ucsc_mafcoverage"
