from bionodulo.nodes.builtin.r_bioinformatics import DESeq2Node
from bionodulo.nodes.registry import NodeRegistry


def test_deseq2_alias_is_registered_by_builtin_loading() -> None:
    registry = NodeRegistry.create_isolated()

    registry.load_builtin_nodes()

    alias = registry.get("deseq2")
    assert alias is not None
    assert issubclass(alias, DESeq2Node)


def test_deseq2_alias_overrides_only_planner_metadata() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    alias = registry.get("deseq2")
    assert alias is not None

    assert alias.NODE_ID == "deseq2"
    assert alias.DISPLAY_NAME == "DESeq2"
    assert (
        alias.DESCRIPTION
        == "Run DESeq2 differential expression analysis for RNA-seq count matrices."
    )
    assert {
        "deseq2",
        "differential expression",
        "rna-seq",
        "counts",
        "bioconductor",
    }.issubset(alias.SEARCH_ALIASES)

    assert alias.CATEGORY == "rna_seq"
    assert alias.RETURN_NAMES == (
        "results_csv",
        "ma_plot",
        "normalized_counts_csv",
    )
    assert alias.REQUIRED_EXECUTABLES == ["Rscript"]
    assert alias.REQUIRED_R_PACKAGES == DESeq2Node.REQUIRED_R_PACKAGES
    assert alias.RETURN_TYPES == DESeq2Node.RETURN_TYPES
    assert alias.REQUIRED_CONDA_PACKAGES == DESeq2Node.REQUIRED_CONDA_PACKAGES
    assert alias.INPUT_TYPES() == DESeq2Node.INPUT_TYPES()
