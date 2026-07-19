"""Compatibility coverage for the stable feature_counts ID."""

from bionodulo.nodes.builtin.rna_seq import FeatureCountsAliasNode, FeatureCountsNode
from bionodulo.nodes.registry import NodeRegistry


def test_feature_counts_alias_reuses_the_focused_contract() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    alias = registry.get("feature_counts")

    assert alias is FeatureCountsAliasNode
    assert issubclass(alias, FeatureCountsNode)
    assert alias.COMPATIBILITY_ALIAS_OF == "featurecounts"
    assert alias.__module__.endswith("rna_seq_family.feature_counts_alias")
    assert alias.VERSION == "2.1.1"
    assert alias.SOURCE_SHA256 == FeatureCountsNode.SOURCE_SHA256
    assert alias.RETURN_TYPES == FeatureCountsNode.RETURN_TYPES
    assert alias.INPUT_TYPES() == FeatureCountsNode.INPUT_TYPES()
