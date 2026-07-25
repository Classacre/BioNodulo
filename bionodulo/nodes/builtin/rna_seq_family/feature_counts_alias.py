"""Stable feature_counts compatibility ID for featureCounts 2.1.1."""

from .featurecounts import FeatureCountsNode


class FeatureCountsAliasNode(FeatureCountsNode):
    NODE_ID = "feature_counts"
    COMPATIBILITY_ALIAS_OF = "featurecounts"
    DISPLAY_NAME = "Feature Counts"
    DESCRIPTION = "Count reads per genomic feature with the focused featureCounts 2.1.1 contract."
    SEARCH_ALIASES = [
        "feature_counts",
        "featurecounts",
        "feature counts",
        "gene counts",
        "subread",
        "rna-seq counts",
    ]


__all__ = ["FeatureCountsAliasNode"]
