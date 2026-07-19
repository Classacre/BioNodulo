"""Focused BCFtools annotate owner."""

from .evidence import attach_evidence
from .legacy import BcftoolsAnnotateNode as _LegacyBcftoolsAnnotateNode


@attach_evidence
class BcftoolsAnnotateNode(_LegacyBcftoolsAnnotateNode):
    NODE_ID = "bcftools_annotate"
