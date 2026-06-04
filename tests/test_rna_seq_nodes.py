from pathlib import Path

from bionodulo.nodes.builtin.rna_seq import FeatureCountsNode
from bionodulo.nodes.registry import NodeRegistry


def test_feature_counts_alias_is_registered_by_builtin_loading() -> None:
    registry = NodeRegistry.create_isolated()

    registry.load_builtin_nodes()

    alias = registry.get("feature_counts")
    assert alias is not None
    assert issubclass(alias, FeatureCountsNode)


def test_feature_counts_alias_overrides_only_planner_metadata() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    alias = registry.get("feature_counts")
    assert alias is not None

    assert alias.NODE_ID == "feature_counts"
    assert alias.DISPLAY_NAME == "Feature Counts"
    assert alias.DESCRIPTION == "Count reads per gene with featureCounts for RNA-seq workflows."
    assert {
        "feature_counts",
        "featurecounts",
        "feature counts",
        "gene counts",
        "subread",
        "rna-seq counts",
    }.issubset(alias.SEARCH_ALIASES)

    assert alias.RETURN_TYPES == FeatureCountsNode.RETURN_TYPES
    assert alias.RETURN_NAMES == FeatureCountsNode.RETURN_NAMES
    assert alias.REQUIRED_EXECUTABLES == FeatureCountsNode.REQUIRED_EXECUTABLES
    assert alias.REQUIRED_CONDA_PACKAGES == FeatureCountsNode.REQUIRED_CONDA_PACKAGES
    assert alias.DOCUMENTATION_URL == FeatureCountsNode.DOCUMENTATION_URL
    assert alias.VERSION == FeatureCountsNode.VERSION
    assert alias.INPUT_TYPES() == FeatureCountsNode.INPUT_TYPES()


def test_feature_counts_alias_renders_and_plans_with_alias_output_path() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    alias = registry.get("feature_counts")
    assert alias is not None

    output = "/tmp/run/feature_counts"
    cmd = alias.render_command(
        {
            "bam": "sample.bam",
            "gtf": "genes.gtf",
            "threads": 4,
            "output": output,
        }
    )
    planned_outputs = alias.PLAN_OUTPUTS({}, "/tmp/run")

    assert cmd == [
        "featureCounts",
        "-a",
        "genes.gtf",
        "-o",
        f"{output}/counts.counts.tsv",
        "-T",
        "4",
        "-p",
        "--countReadPairs",
        "sample.bam",
    ]
    assert planned_outputs == [Path("/tmp/run/feature_counts/counts.counts.tsv")]
