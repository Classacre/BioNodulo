from types import SimpleNamespace

import pytest

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
        "pca_scores_csv",
    )
    assert alias.REQUIRED_EXECUTABLES == ["Rscript"]
    assert alias.REQUIRED_R_PACKAGES == DESeq2Node.REQUIRED_R_PACKAGES
    assert alias.RETURN_TYPES == DESeq2Node.RETURN_TYPES
    assert alias.REQUIRED_CONDA_PACKAGES == DESeq2Node.REQUIRED_CONDA_PACKAGES
    assert alias.INPUT_TYPES() == DESeq2Node.INPUT_TYPES()


def test_deseq2_analysis_plans_pca_scores_output() -> None:
    outputs = DESeq2Node.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/deseq2_analysis/results_csv.out",
        "/tmp/run/deseq2_analysis/ma_plot.out",
        "/tmp/run/deseq2_analysis/normalized_counts_csv.out",
        "/tmp/run/deseq2_analysis/pca_scores_csv.out",
    ]


@pytest.mark.asyncio
async def test_deseq2_analysis_writes_named_gene_columns_for_downstream_tables(tmp_path) -> None:
    async def run_command(cmd, cwd=None):
        return {"returncode": 0}

    context = SimpleNamespace(
        node_dir=tmp_path,
        run_command=run_command,
        register_preview=lambda path, label=None: None,
    )

    await DESeq2Node().run(
        count_matrix="counts.csv",
        sample_info="samples.csv",
        context=context,
    )

    script = (tmp_path / "deseq2_analysis" / "deseq2.R").read_text(encoding="utf-8")
    assert "res_df <- data.frame(gene = rownames(res), as.data.frame(res), check.names = FALSE)" in script
    assert 'write.csv(res_df, "' in script
    assert "row.names = FALSE" in script
    assert (
        "norm_counts <- data.frame(gene = rownames(norm_counts), "
        "as.data.frame(norm_counts), check.names = FALSE)"
    ) in script
    assert 'write.csv(norm_counts, "' in script


@pytest.mark.asyncio
async def test_deseq2_analysis_writes_pca_scores_script_and_output(tmp_path) -> None:
    commands: list[tuple[list[str], str]] = []
    previews: list[tuple[str, str]] = []

    async def run_command(cmd, cwd=None):
        commands.append((list(cmd), str(cwd)))
        return {"returncode": 0}

    context = SimpleNamespace(
        node_dir=tmp_path,
        run_command=run_command,
        register_preview=lambda path, label=None: previews.append((str(path), str(label))),
    )

    outputs = await DESeq2Node().run(
        count_matrix="counts.csv",
        sample_info="samples.csv",
        context=context,
    )

    script = (tmp_path / "deseq2_analysis" / "deseq2.R").read_text(encoding="utf-8")
    assert 'write.csv(pca_scores, "' in script
    assert "pca_scores.csv" in script
    assert "varianceStabilizingTransformation" in script
    assert "prcomp(t(assay(vst_counts)))" in script
    assert "cbind(pca_scores, as.data.frame(colData[pca_scores$sample, , drop = FALSE]))" in script
    assert outputs[3].endswith("/deseq2_analysis/pca_scores.csv")
    assert commands[0][0][0] == "Rscript"
    assert previews == [(str(tmp_path / "deseq2_analysis" / "MA_plot.png"), "DESeq2 MA Plot")]
