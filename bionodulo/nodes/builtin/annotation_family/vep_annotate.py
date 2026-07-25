"""Focused compatibility ID for the audited VEP 113.4 contract."""

from .evidence import attach_evidence
from .vep import VEPNode


@attach_evidence
class VEPAnnotateNode(VEPNode):
    NODE_ID = "vep_annotate"
    DISPLAY_NAME = "VEP Annotate"
