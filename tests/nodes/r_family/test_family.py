from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from bionodulo.environments.constants import (
    PACKAGE_MIN_VERSIONS,
    R_PACKAGE_TO_CONDA_PACKAGE,
)
from bionodulo.nodes.builtin.r_bioinformatics import DESeq2Node as FacadeDESeq2Node
from bionodulo.nodes.builtin.r_family.biostrings_stats import BiostringsStatsNode
from bionodulo.nodes.builtin.r_family.dataframe_builder import DataFrameBuilderNode
from bionodulo.nodes.builtin.r_family.deseq2 import DESeq2AliasNode, DESeq2Node
from bionodulo.nodes.builtin.r_family.pheatmap import PheatmapNode
from bionodulo.nodes.builtin.r_family.plot import RPlotNode
from bionodulo.nodes.builtin.r_family.script import RScriptNode
from bionodulo.nodes.registry import NodeRegistry


NODE_MODULES = {
    "deseq2_analysis": "bionodulo.nodes.builtin.r_family.deseq2",
    "deseq2": "bionodulo.nodes.builtin.r_family.deseq2",
    "r_pheatmap": "bionodulo.nodes.builtin.r_family.pheatmap",
    "r_biostrings_stats": "bionodulo.nodes.builtin.r_family.biostrings_stats",
    "r_dataframe_builder": "bionodulo.nodes.builtin.r_family.dataframe_builder",
    "r_plot": "bionodulo.nodes.builtin.r_family.plot",
    "r_script": "bionodulo.nodes.builtin.r_family.script",
}
ROOT = Path(__file__).resolve().parents[3]


def test_r_family_has_focused_ownership_without_changing_catalog_size() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    assert len(registry.object_info()) == 943
    assert {node_id: registry.get(node_id).__module__ for node_id in NODE_MODULES} == NODE_MODULES
    assert FacadeDESeq2Node is DESeq2Node
    assert registry.get("deseq2_analysis") is DESeq2Node
    assert registry.get("deseq2") is DESeq2AliasNode
    assert issubclass(DESeq2AliasNode, DESeq2Node)


def test_r_family_declares_one_solvable_exact_package_stack() -> None:
    assert PACKAGE_MIN_VERSIONS["r-base"] == "4.5.3"
    assert PACKAGE_MIN_VERSIONS["bioconductor-deseq2"] == "1.50.2"
    assert PACKAGE_MIN_VERSIONS["bioconductor-biostrings"] == "2.78.0"
    assert PACKAGE_MIN_VERSIONS["r-ggplot2"] == "4.0.3"
    assert PACKAGE_MIN_VERSIONS["r-pheatmap"] == "1.0.13"
    assert PACKAGE_MIN_VERSIONS["r-ashr"] == "2.2_63"
    assert R_PACKAGE_TO_CONDA_PACKAGE["ashr"] == "r-ashr"
    assert DESeq2Node.CONDA_PACKAGE_CONSTRAINTS == {
        "r-base": "4.5.3",
        "bioconductor-deseq2": "1.50.2",
        "r-ggplot2": "4.0.3",
        "r-ashr": "2.2_63",
    }
    assert DESeq2Node.SOURCE_AUTHORITIES == {
        "DESeq2": ("1.50.2", "d90821a3153a27b2a6b727df7188ea7a5b8929fd"),
        "ggplot2": ("4.0.3", "cc1444c10edb87650fbe0cb31d56f0da1a255634"),
        "ashr": ("2.2-63", "cba7ded0d9ca0d7843dfe7ca3eecabde1202aa20"),
    }
    assert BiostringsStatsNode.CONDA_PACKAGE_CONSTRAINTS == {
        "r-base": "4.5.3",
        "bioconductor-biostrings": "2.78.0",
    }
    assert PheatmapNode.CONDA_PACKAGE_CONSTRAINTS == {"r-base": "4.5.3", "r-pheatmap": "1.0.13"}
    assert RPlotNode.CONDA_PACKAGE_CONSTRAINTS == {"r-base": "4.5.3", "r-ggplot2": "4.0.3"}
    assert RScriptNode.CONDA_PACKAGE_CONSTRAINTS == {"r-base": "4.5.3"}
    assert BiostringsStatsNode.GIT_COMMIT == "eda5d667ad05a73336d8c83a71f670198433232f"
    assert PheatmapNode.GIT_COMMIT == "ffd0f8c4b5a3dc2628a3dfd9b5fd4321c2aa1569"
    assert RPlotNode.GIT_COMMIT == "cc1444c10edb87650fbe0cb31d56f0da1a255634"
    assert RScriptNode.GIT_COMMIT == "c5ddd2fcc67d751f51085e5a29f8158410fc0eaf"


def test_deseq2_prepares_native_outputs_and_documented_operations(tmp_path) -> None:
    inputs = {
        "count_matrix": "/data/counts.csv",
        "sample_info": "/data/samples.csv",
        "design_formula": "~ batch + condition",
        "contrast": "condition,treated,control",
        "min_counts": 10,
        "lfc_threshold": 0.5,
        "padj_threshold": 0.05,
        "output": str(tmp_path / "deseq2_analysis"),
    }
    outputs = DESeq2Node.PLAN_OUTPUTS(inputs, tmp_path)
    DESeq2Node.PREPARE_EXECUTION(inputs, outputs)

    assert [path.name for path in outputs] == [
        "deseq2_results.csv",
        "MA_plot.png",
        "normalized_counts.csv",
        "pca_scores.csv",
    ]
    assert DESeq2Node.render_command(inputs) == [
        "Rscript",
        "--vanilla",
        str(tmp_path / "deseq2_analysis" / "deseq2.R"),
    ]
    script = (tmp_path / "deseq2_analysis" / "deseq2.R").read_text(encoding="utf-8")
    for needle in (
        "DESeqDataSetFromMatrix",
        'as.formula("~ batch + condition")',
        'contrast_parts <- c("condition", "treated", "control")',
        "dds <- DESeq(dds, quiet = TRUE)",
        'type = "ashr"',
        "varianceStabilizingTransformation",
        "counts(dds, normalized = TRUE)",
        "ggplot2::ggsave",
    ):
        assert needle in script
    assert "readr" not in script
    assert "must exactly match count-matrix columns in the same order" in script


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"design_formula": "condition"}, "beginning with '~'"),
        ({"contrast": "condition,treated"}, "variable,numerator,denominator"),
        ({"padj_threshold": 1.5}, "at most 1"),
    ],
)
def test_deseq2_rejects_invalid_contract_values(updates, message) -> None:
    inputs = {
        "count_matrix": "counts.csv",
        "sample_info": "samples.csv",
        "design_formula": "~ condition",
        "contrast": "condition,treated,control",
        **updates,
    }
    assert message in str(DESeq2Node.VALIDATE_INPUTS(inputs))


def test_pheatmap_uses_native_filename_output_and_explicit_annotation(tmp_path) -> None:
    inputs = {
        "data_csv": "/data/matrix.csv",
        "annotation_csv": "/data/annotation.csv",
        "scale": "row",
        "cluster_rows": True,
        "cluster_cols": True,
        "show_rownames": False,
        "show_colnames": True,
        "fontsize": 10,
        "width": 900,
        "height": 700,
        "output": str(tmp_path / "r_pheatmap"),
    }
    outputs = PheatmapNode.PLAN_OUTPUTS(inputs, tmp_path)
    PheatmapNode.PREPARE_EXECUTION(inputs, outputs)
    script = (tmp_path / "r_pheatmap" / "pheatmap.R").read_text(encoding="utf-8")

    assert PheatmapNode.render_command(inputs)[0:2] == ["Rscript", "--vanilla"]
    assert 'annotation_data <- read.csv(' in script
    assert 'annotation_col = annotation_data' in script
    assert f'filename = "{outputs[0]}"' in script
    assert "width = 9.0" in script
    assert "height = 7.0" in script
    assert "readr" not in script
    assert "RColorBrewer" not in script


def test_biostrings_contract_translates_all_six_frames_without_false_start_codons(tmp_path) -> None:
    inputs = {
        "input_fasta": "/data/coding.fasta",
        "min_orf_length": 90,
        "genetic_code": "Bacterial",
        "output": str(tmp_path / "r_biostrings_stats"),
    }
    outputs = BiostringsStatsNode.PLAN_OUTPUTS(inputs, tmp_path)
    BiostringsStatsNode.PREPARE_EXECUTION(inputs, outputs)
    script = (tmp_path / "r_biostrings_stats" / "biostrings.R").read_text(encoding="utf-8")

    assert [path.name for path in outputs] == [
        "orf_table.csv",
        "reverse_complement.fasta",
        "six_frame_translation.fasta",
    ]
    assert 'getGeneticCode("11")' in script
    assert 'strand_sequences <- list("+" = forward_sequence, "-" = reverseComplement(forward_sequence))' in script
    assert "for (frame_offset in 0:2)" in script
    assert "no.init.codon = TRUE" in script
    assert 'strsplit(amino_text, "*", fixed = TRUE)' in script
    assert "readr" not in script


@pytest.mark.asyncio
async def test_dataframe_builder_writes_rectangular_csv_and_rejects_truncation(tmp_path) -> None:
    outputs = await DataFrameBuilderNode().run(
        x_column="sample",
        x_values='A,"B, replicate"',
        y_column="reads",
        y_values="10,20",
        group_column="lane",
        group_values="L1,L2",
        context=SimpleNamespace(node_dir=tmp_path),
    )
    with open(outputs[0], newline="", encoding="utf-8") as handle:
        assert list(csv.reader(handle)) == [
            ["sample", "reads", "lane"],
            ["A", "10", "L1"],
            ["B, replicate", "20", "L2"],
        ]
    invalid = DataFrameBuilderNode.VALIDATE_INPUTS({
        "x_column": "x",
        "x_values": "1,2,3",
        "y_column": "y",
        "y_values": "4,5",
    })
    assert "same number" in str(invalid)


def test_r_plot_uses_data_pronoun_and_pixel_dimensions(tmp_path) -> None:
    inputs = {
        "data_csv": "/data/stats.csv",
        "plot_type": "bar",
        "x_axis": "sample name",
        "y_axis": "read-count",
        "color_column": "lane",
        "title": 'Reads "by" sample',
        "width": 900,
        "height": 600,
        "output": str(tmp_path / "r_plot"),
    }
    outputs = RPlotNode.PLAN_OUTPUTS(inputs, tmp_path)
    RPlotNode.PREPARE_EXECUTION(inputs, outputs)
    script = (tmp_path / "r_plot" / "plot.R").read_text(encoding="utf-8")

    assert '.data[[x_name]]' in script
    assert '.data[[y_name]]' in script
    assert '.data[[color_name]]' in script
    assert "ggplot2::geom_col" in script
    assert 'units = "px"' in script
    assert "width = 900" in script
    assert "readr" not in script
    assert "custom_script" in str(RPlotNode.VALIDATE_INPUTS({
        "data_csv": "stats.csv",
        "plot_type": "custom",
        "x_axis": "x",
        "y_axis": "y",
    }))


def test_rscript_preserves_quoted_argument_boundaries() -> None:
    inputs = {
        "script": "/work/my analysis.R",
        "args": '--sample "tumor one" --threshold 0.05',
    }
    assert RScriptNode.render_command(inputs) == [
        "Rscript",
        "--vanilla",
        "/work/my analysis.R",
        "--sample",
        "tumor one",
        "--threshold",
        "0.05",
    ]
    assert "valid shell-style syntax" in str(RScriptNode.VALIDATE_INPUTS({
        "script": "analysis.R",
        "args": '"unterminated',
    }))


@pytest.mark.parametrize(
    ("template_name", "heatmap_id"),
    [
        ("deseq2_differential_expression.json", "heatmap_001"),
        ("r_visualization_pipeline.json", "pheatmap_001"),
    ],
)
def test_templates_stage_pheatmap_annotation_as_an_explicit_dependency(template_name, heatmap_id) -> None:
    workflow = json.loads((ROOT / "templates" / template_name).read_text(encoding="utf-8"))
    nodes = {node["id"]: node for node in workflow["nodes"]}

    assert nodes["heatmap_annotation_001"]["type"] == "input_file"
    assert "annotation_csv" not in nodes[heatmap_id]["params"]
    assert any(
        edge.get("from") == {"node": "heatmap_annotation_001", "output": "file"}
        and edge.get("to") == {"node": heatmap_id, "input": "annotation_csv"}
        for edge in workflow["edges"]
    )
