"""Focused compatibility ID for GATK Funcotator."""

from .evidence import attach_evidence
from .funcotate_table import FuncotateTableNode


@attach_evidence
class FuncotatorNode(FuncotateTableNode):
    NODE_ID = "funcotator"
    DISPLAY_NAME = "Funcotator"
    DESCRIPTION = "Annotate cancer variants with GATK Funcotator."
    SEARCH_ALIASES = [
        "funcotator",
        "funcotate",
        "gatk funcotator",
        "cancer variants",
        "somatic annotation",
        "oncotator",
    ]
