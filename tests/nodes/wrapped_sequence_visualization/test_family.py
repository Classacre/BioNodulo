"""Lean ownership, evidence, argv, and output checks for the focused wrapper family."""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin import wrapped_sequence_visualization as facade
from bionodulo.nodes.builtin import wrapped_sequence_visualization_family as family
from bionodulo.nodes.builtin.wrapped_sequence_visualization_family import adapter, contracts


CASES: dict[str, tuple[type[BaseNode], dict[str, Any], str, tuple[str, ...], tuple[str, ...]]] = {
    "barrnap": (
        family.BarrnapNode,
        {"fasta_file": "genome.fa"},
        "barrnap --quiet",
        ("rrna.gff3",),
        ("rrna_gff",),
    ),
    "fasta-stats": (
        family.FastaStatsNode,
        {"fasta": "genome.fa"},
        "python fasta-stats.py",
        ("stats.tsv",),
        ("stats_output",),
    ),
    "chopper": (
        family.ChopperNode,
        {"input": "reads.fastq"},
        "chopper --input",
        ("fq_filt.fastq",),
        ("fq_filt",),
    ),
    "chopin2": (
        family.Chopin2Node,
        {"dataset": "data.csv"},
        "chopin2 --dataset",
        ("summary.txt",),
        ("summary",),
    ),
    "cite_seq_count": (
        family.CiteSeqCountNode,
        {
            "input_type": "repeat",
            "input1": ["r1.fq.gz"],
            "input2": ["r2.fq.gz"],
            "tags": "tags.csv",
        },
        "CITE-seq-Count --threads",
        (
            "run_report.yaml",
            "read_count_features.tsv",
            "read_count_barcodes.tsv",
            "read_count_matrix.mtx",
            "umi_count_features.tsv",
            "umi_count_barcodes.tsv",
            "umi_count_matrix.mtx",
        ),
        (
            "report",
            "output_features",
            "output_barcodes",
            "output_matrix",
            "output_features_filtered",
            "output_barcodes_filtered",
            "output_matrix_filtered",
        ),
    ),
    "cialign": (
        family.CIAlignNode,
        {"input": "alignment.fa"},
        "CIAlign --infile",
        ("output_cleaned.fasta", "output_removed.txt"),
        ("output_cleaned", "output_removed"),
    ),
    "chromap": (
        family.ChromapNode,
        {"read_type": "single", "ref": "ref.fa", "single_reads": ["reads.fq"]},
        "chromap -i",
        ("mapping.bed", "summary.txt"),
        ("mapping_out", "summary_out"),
    ),
    "circexplorer2": (
        family.CIRCexplorer2Node,
        {"mode": "align", "gtf": "genes.gtf", "genome": "ref.fa", "fastq": ["reads.fq"]},
        "CIRCexplorer2 align",
        ("alignment.tgz",),
        ("alignment",),
    ),
    "circos": (
        family.CircosNode,
        {"reference_source": "preset"},
        "circos -conf",
        ("circos.png",),
        ("output_png",),
    ),
    "circos_resample": (
        family.CircosResampleNode,
        {"input": "track.tsv"},
        "resample -bin",
        ("resampled.tabular",),
        ("output",),
    ),
    "circos_gc_skew": (
        family.CircosGCSkewNode,
        {"reference_genome_source": "history", "history_item": "ref.fa"},
        "gc_skew.py",
        ("gc_skew.bw",),
        ("output",),
    ),
    "circos_wiggle_to_scatter": (
        family.CircosWiggleToScatterNode,
        {"input": "track.bw"},
        "scatter-from-wiggle.py",
        ("scatter.tabular",),
        ("output",),
    ),
    "circos_interval_to_text": (
        family.CircosIntervalToTextNode,
        {"ref_source": "bed", "input": "labels.bed"},
        "text-from-bed.py",
        ("text_labels.tabular",),
        ("output",),
    ),
    "circos_interval_to_tile": (
        family.CircosIntervalToTileNode,
        {"ref_source": "bed", "input": "tiles.bed"},
        "tiles-from-bed.py",
        ("tiles.tabular",),
        ("output",),
    ),
    "circos_aln_to_links": (
        family.CircosAlignmentsToLinksNode,
        {"input": "alignment.maf", "input_ext": "maf"},
        "alignments-to-links.py",
        ("links.tabular",),
        ("output",),
    ),
    "circos_binlinks": (
        family.CircosBinlinksNode,
        {"linksfile": "links.tsv"},
        "binlinks -bin_size",
        ("link_density.tabular",),
        ("outfile",),
    ),
    "circos_bundlelinks": (
        family.CircosBundlelinksNode,
        {"linksfile": "links.tsv"},
        "bundlelinks",
        ("bundled_links.tabular",),
        ("outfile",),
    ),
    "circos_wiggle_to_stacked": (
        family.CircosWiggleToStackedNode,
        {"input": ["one.bw", "two.bw"]},
        "stack-histogram.py",
        ("stacked_histogram.tabular",),
        ("output",),
    ),
    "circos_tableviewer": (
        family.CircosTableviewerNode,
        {"table": "table.tsv"},
        "parse-table -file",
        ("circos.png",),
        ("output_png",),
    ),
    "filtlong": (
        family.FiltlongNode,
        {"input_file": "reads.fastq"},
        "filtlong",
        ("output.fastq",),
        ("outfile",),
    ),
}


def _owned_node_classes(module: Any) -> list[type[BaseNode]]:
    return [
        value
        for value in vars(module).values()
        if inspect.isclass(value)
        and issubclass(value, BaseNode)
        and value is not BaseNode
        and value.__module__ == module.__name__
        and bool(value.__dict__.get("NODE_ID"))
    ]


def test_exactly_twenty_stable_ids_have_one_focused_owner_and_legacy_reexports() -> None:
    assert set(CASES) == set(contracts.NODE_EVIDENCE)
    assert len(CASES) == 20
    assert _owned_node_classes(adapter) == []

    for node_id, (node_class, *_rest) in CASES.items():
        owner = importlib.import_module(node_class.__module__)
        assert _owned_node_classes(owner) == [node_class]
        assert node_class.NODE_ID == node_id
        assert getattr(facade, node_class.__name__) is node_class


@pytest.mark.parametrize("node_id", sorted(CASES))
def test_every_owner_has_exact_pinned_wrapper_evidence(node_id: str) -> None:
    node_class = CASES[node_id][0]
    evidence = contracts.NODE_EVIDENCE[node_id]

    assert node_class.GIT_COMMIT == contracts.TOOLS_IUC_GIT_COMMIT
    assert node_class.GALAXY_WRAPPER_GIT_COMMIT == contracts.TOOLS_IUC_GIT_COMMIT
    assert node_class.GALAXY_WRAPPER_PATH == evidence.wrapper_path
    assert node_class.GALAXY_WRAPPER_VERSION == evidence.wrapper_version
    assert node_class.PACKAGE_CONSTRAINTS == evidence.package_constraints
    assert node_class.SOURCE_URL == evidence.source_url
    assert node_class.EXIT_SEMANTICS
    assert node_class.AUDIT_STATUS == "contract-checked-no-external-execution"


@pytest.mark.parametrize("node_id", sorted(CASES))
def test_representative_contract_validates_renders_and_maps_outputs(node_id: str, tmp_path: Path) -> None:
    node_class, raw_inputs, command_fragment, expected_files, expected_ports = CASES[node_id]
    inputs = {**raw_inputs, "output": f"/work/{node_id}"}

    assert node_class.VALIDATE_INPUTS(inputs) is True
    command = node_class.render_command(inputs)
    rendered = " ".join(command) if isinstance(command, list) else command
    assert command_fragment in rendered

    planned = node_class.PLAN_OUTPUTS(inputs, tmp_path)
    assert tuple(path.name for path in planned) == expected_files
    assert tuple(node_class.MAP_PLANNED_OUTPUTS(planned)) == expected_ports


@pytest.mark.parametrize(
    ("node_class", "inputs", "expected_ports"),
    [
        (family.BarrnapNode, {"fasta_file": "genome.fa", "outseq": True}, ("rrna_gff", "rrna_sequences")),
        (family.FastaStatsNode, {"fasta": "genome.fa", "gaps_option": True}, ("stats_output", "gaps_output")),
        (family.Chopin2Node, {"dataset": "data.csv", "enable_fs": True}, ("summary", "selection")),
        (
            family.CiteSeqCountNode,
            {
                "input_type": "repeat",
                "input1": ["r1.fq.gz"],
                "input2": ["r2.fq.gz"],
                "tags": "tags.csv",
                "dense": True,
            },
            (
                "report",
                "output_features",
                "output_barcodes",
                "output_matrix",
                "output_features_filtered",
                "output_barcodes_filtered",
                "output_matrix_filtered",
                "dense_output_matrix",
            ),
        ),
        (
            family.CIAlignNode,
            {"input": "alignment.fa", "plot_output": True},
            ("output_cleaned", "output_removed", "plot_output"),
        ),
        (
            family.CIRCexplorer2Node,
            {"mode": "parse", "fusion_file": "junctions.txt"},
            ("parse",),
        ),
        (
            family.CIRCexplorer2Node,
            {"mode": "annotate", "ref": "genes.txt", "genome": "ref.fa", "bed": "junctions.bed", "low_confidence": True},
            ("annotate", "annotate_low"),
        ),
        (
            family.CircosNode,
            {"reference_source": "preset", "output_png": False, "output_svg": True, "output_tar": False},
            ("output_svg",),
        ),
        (
            family.CircosNode,
            {"reference_source": "history", "genome_fasta": "ref.fa", "output_png": False, "output_svg": True},
            ("output_svg", "karyotype_txt"),
        ),
        (
            family.CircosTableviewerNode,
            {"table": "table.tsv", "output_png": False, "output_svg": True, "output_tar": False},
            ("output_svg",),
        ),
    ],
)
def test_conditional_outputs_keep_their_documented_port_names(
    node_class: type[BaseNode],
    inputs: dict[str, Any],
    expected_ports: tuple[str, ...],
    tmp_path: Path,
) -> None:
    assert node_class.VALIDATE_INPUTS(inputs) is True
    planned = node_class.PLAN_OUTPUTS(inputs, tmp_path)
    assert tuple(node_class.MAP_PLANNED_OUTPUTS(planned)) == expected_ports
