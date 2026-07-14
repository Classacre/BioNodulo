"""deseq2 — r_bioinformatics node(s). One tool per file (extracted from r_bioinformatics.py)."""
from __future__ import annotations
import textwrap
from pathlib import Path
from typing import Any
from bionodulo.nodes.base import BaseNode


class DESeq2AliasNode(DESeq2Node):
    """Planner/workflow compatibility alias for DESeq2Node."""
    NODE_ID = 'deseq2'
    DISPLAY_NAME = 'DESeq2'
    DESCRIPTION = 'Run DESeq2 differential expression analysis for RNA-seq count matrices.'
    SEARCH_ALIASES = ['deseq2', 'differential expression', 'rna-seq', 'counts', 'bioconductor']
