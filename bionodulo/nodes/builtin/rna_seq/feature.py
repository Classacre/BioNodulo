"""feature — rna_seq node(s). One tool per file (extracted from rna_seq.py)."""
from __future__ import annotations
from typing import Any, Optional
from bionodulo.nodes.command_node import CommandNode


class FeatureCountsAliasNode(FeatureCountsNode):
    """Planner/workflow compatibility alias for featureCounts."""
    NODE_ID = 'feature_counts'
    DISPLAY_NAME = 'Feature Counts'
    DESCRIPTION = 'Count reads per gene with featureCounts for RNA-seq workflows.'
    SEARCH_ALIASES = ['feature_counts', 'featurecounts', 'feature counts', 'gene counts', 'subread', 'rna-seq counts']
