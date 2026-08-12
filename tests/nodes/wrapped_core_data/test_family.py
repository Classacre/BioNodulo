"""Compact contracts for the focused wrapped core-data family."""

from __future__ import annotations

from pathlib import Path

import pytest

from bionodulo.nodes.builtin import wrapped_core_data_family as family
from bionodulo.nodes.builtin.wrapped_core_data_family.evidence import (
    NODE_EVIDENCE,
    TOOLS_IUC_COMMIT,
)


EXPECTED_IDS = {
    "addName",
    "add_input_name_as_column",
    "anndata2ri",
    "anndata_export",
    "anndata_import",
    "anndata_inspect",
    "anndata_manipulate",
    "annotatemyids",
    "argnorm",
    "autobigs-cli",
    "b2btools_single_sequence",
    "bam_to_scidx",
    "baredsc_1d",
    "baredsc_2d",
    "baredsc_combine_1d",
    "baredsc_combine_2d",
    "basil",
    "bax2bam",
    "bbgtobigwig",
    "berokka",
    "bp_genbank2gff3",
    "cd_hit",
    "celltypist",
    "cemitool",
    "charts",
    "clustering_from_distmat",
    "column_order_header_sort",
    "column_remove_by_header",
    "datamash_ops",
    "datamash_reverse",
    "datamash_transpose",
    "falco",
    "fasta_regex_finder",
    "mlst",
    "mlst_list",
    "modify_loom",
    "seqsero2",
}


def _nodes() -> list[type]:
    return [getattr(family, name) for name in family.__all__]


def test_stable_ids_have_one_focused_owner() -> None:
    nodes = _nodes()
    assert len(nodes) == 37
    assert {node.NODE_ID for node in nodes} == EXPECTED_IDS
    assert len({node.NODE_ID for node in nodes}) == len(nodes)


@pytest.mark.parametrize("node", _nodes(), ids=lambda node: node.NODE_ID)
def test_every_contract_is_pinned_to_the_exact_wrapper_and_packages(node: type) -> None:
    evidence = NODE_EVIDENCE[node.NODE_ID]
    assert node.VERSION == evidence.version
    assert node.WRAPPER_GIT_COMMIT == TOOLS_IUC_COMMIT
    assert node.WRAPPER_SOURCE == evidence.wrapper_path
    assert node.SOURCE_URL.endswith(evidence.wrapper_path)
    assert f"/{TOOLS_IUC_COMMIT}/" in node.SOURCE_URL
    assert node.PACKAGE_CONSTRAINTS == evidence.package_constraints
    assert node.DOCUMENTATION_URL
    assert node.EXIT_SEMANTICS
    assert node.AUDIT_STATUS == "contract-checked-no-external-execution"


def test_anndata_export_keeps_native_table_names_and_pinned_stack(tmp_path: Path) -> None:
    command = family.AnnDataExportNode.render_command(
        {"input": "single cell.h5ad", "output": "/work/anndata_export"}
    )
    assert "ad.read_h5ad('single cell.h5ad', backed='r')" in command
    assert "adata.write_csvs('.', sep=\"\\t\", skip_data=False)" in command
    assert family.AnnDataExportNode.PACKAGE_CONSTRAINTS == (
        "anndata=0.11.4",
        "scanpy=1.11.5",
        "loompy=3.0.8",
        "pandas=2.3.3",
    )
    assert family.AnnDataExportNode.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "anndata_export" / name
        for name in ("X.csv", "obs.csv", "obsm.csv", "var.csv", "varm.csv")
    ]


def test_clustering_uses_pinned_newick_flag_and_native_filename(tmp_path: Path) -> None:
    assert family.ClusteringFromDistmatNode.render_command(
        {
            "distmat": "sample distances.tsv",
            "output": "/work/clustering_from_distmat",
        }
    ) == (
        "mkdir -p /work/clustering_from_distmat && cd /work/clustering_from_distmat && "
        "python clustering_from_distmat.py 'sample distances.tsv' result --method average --newick && "
        "mv result.tree clustering_dendrogram.newick"
    )
    assert family.ClusteringFromDistmatNode.REQUIRED_CONDA_PACKAGES == ["python", "scipy", "pandas"]
    assert family.ClusteringFromDistmatNode.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "clustering_from_distmat" / "clustering_dendrogram.newick"
    ]


def test_datamash_operation_revisions_and_shell_contracts_are_exact() -> None:
    assert family.DatamashOpsNode.VERSION == "1.9+galaxy0"
    assert family.DatamashTransposeNode.VERSION == "1.9+galaxy1"
    assert family.DatamashReverseNode.VERSION == "1.9+galaxy0"
    assert family.DatamashOpsNode.render_command(
        {
            "in_file": "scores.csv",
            "input_ext": "csv",
            "grouping": "2",
            "operations": [{"op_name": "mean", "op_column": 3}],
            "output": "/work/datamash_ops",
        }
    ) == "datamash -t , --group 2 mean 3 < scores.csv > /work/datamash_ops/out_file.tsv"
    assert family.DatamashTransposeNode.PACKAGE_CONSTRAINTS == (
        "datamash=1.9",
        "coreutils=9.5",
    )


def test_typing_and_tabular_adapters_preserve_native_flags() -> None:
    assert family.MLSTNode.render_command(
        {
            "input_files": ["MRSA 0252.fna", "Acetobacter.fna"],
            "input_labels": ["MRSA 0252.fna", "Acetobacter.fna"],
            "output": "/work/mlst",
        }
    ) == (
        "ln -s 'MRSA 0252.fna' 'MRSA 0252.fna' && "
        "ln -s Acetobacter.fna Acetobacter.fna && "
        "mlst --nopath --threads ${GALAXY_SLOTS:-1} 'MRSA 0252.fna' Acetobacter.fna "
        "> /work/mlst/report.tsv"
    )
    assert family.ColumnRemoveByHeaderNode.VALIDATE_INPUTS(
        {"input_tabular": "table.tsv", "headers": ["sample", "batch"]}
    ) is True
    assert family.ColumnRemoveByHeaderNode.VALIDATE_INPUTS(
        {"input_tabular": "table.tsv", "headers": []}
    ) == "at least one header is required"


@pytest.mark.parametrize(
    ("node", "inputs", "expected_names"),
    [
        (family.FalcoNode, {}, ("fastqc_report.html", "fastqc_data.txt")),
        (family.MLSTListNode, {}, ("report.txt",)),
        (family.BerokkaNode, {}, ("trimmed.fasta", "results.tsv")),
    ],
)
def test_representative_planned_outputs_use_stable_filenames(
    node: type,
    inputs: dict[str, object],
    expected_names: tuple[str, ...],
    tmp_path: Path,
) -> None:
    assert tuple(path.name for path in node.PLAN_OUTPUTS(inputs, tmp_path)) == expected_names
