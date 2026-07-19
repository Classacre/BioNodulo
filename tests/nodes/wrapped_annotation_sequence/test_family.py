"""Lean ownership and contract checks for annotation/sequence wrappers."""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin import wrapped_annotation_sequence as facade
from bionodulo.nodes.builtin import wrapped_annotation_sequence_family as family
from bionodulo.nodes.builtin.wrapped_annotation_sequence_family import contracts


Case = tuple[type[BaseNode], dict[str, Any], str, tuple[str, ...], tuple[str, ...]]

CASES: dict[str, Case] = {
    "aegean_canongff3": (
        family.AegeanCanonGff3Node,
        {"gff3file": ["genes.gff3"]},
        "canon-gff3",
        ("canonical.gff3",),
        ("output",),
    ),
    "aegean_gaeval": (
        family.AegeanGaevalNode,
        {"alignmentgff3": "alignments.gff3", "genesgff3": "genes.gff3"},
        "gaeval",
        ("gaeval.tsv",),
        ("output",),
    ),
    "aegean_locuspocus": (
        family.AegeanLocusPocusNode,
        {"genesgff3": "genes.gff3"},
        "locuspocus",
        ("loci.gff3",),
        ("output",),
    ),
    "aegean_parseval": (
        family.AegeanParsevalNode,
        {"referencegff3": "reference.gff3", "predictiongff3": "prediction.gff3"},
        "parseval",
        ("parseval.txt",),
        ("output_txt",),
    ),
    "augustus": (
        family.AugustusNode,
        {"input_genome": "genome.fa", "model_mode": "builtin"},
        "augustus",
        ("augustus.gtf", "protein.fasta", "codingseq.fasta"),
        ("output", "protein_output", "codingseq_output"),
    ),
    "augustus_training": (
        family.AugustusTrainingNode,
        {"genome": "genome.fa", "maker_gff": "genes.gff"},
        "maker2zff",
        ("output_tar.augustus",),
        ("output_tar",),
    ),
    "arriba": (
        family.ArribaNode,
        {"input": "alignments.bam", "genome_assembly": "genome.fa", "annotation": "genes.gtf"},
        "arriba",
        ("fusions.tsv", "fusions.discarded.tsv", "fusions.vcf"),
        ("fusions_tsv", "discarded_fusions_tsv", "fusions_vcf"),
    ),
    "arriba_draw_fusions": (
        family.ArribaDrawFusionsNode,
        {
            "fusions": "fusions.tsv",
            "alignments": "alignments.bam",
            "alignments_index": "alignments.bam.bai",
            "annotation": "genes.gtf",
        },
        "draw_fusions.R",
        ("fusions.pdf",),
        ("fusions_pdf",),
    ),
    "arriba_get_filters": (
        family.ArribaGetFiltersNode,
        {"arriba_reference_name": "GRCh38"},
        "download_references.sh",
        ("blacklist.tsv.gz", "known_fusions.tsv.gz", "protein_domains.gff3", "cytobands.tsv"),
        ("blacklist", "known_fusions", "protein_domains", "cytobands"),
    ),
    "artic_guppyplex": (
        family.ArticGuppyplexNode,
        {"reads": "reads.fastq", "input_ext": "fastq"},
        "artic guppyplex",
        ("guppyplex_out.fastq",),
        ("output",),
    ),
    "artic_minion": (
        family.ArticMinionNode,
        {"read_file": "reads.fastq", "scheme_name": "SARS-CoV-2", "scheme_version": "V5.3.2"},
        "artic minion",
        (
            "sample.primertrimmed.rg.sorted.bam",
            "sample.alignreport.txt",
            "sample.merged.vcf.gz",
            "sample.fail.vcf.gz",
            "sample.pass.vcf.gz",
            "sample.consensus.fasta",
            "sample.coverage_mask.txt",
            "sample.minion.log.txt",
        ),
        (
            "alignment_trimmed",
            "alignment_report",
            "variants_merged_vcf",
            "variants_fail_vcf",
            "variants_pass_vcf",
            "consensus_fasta",
            "coverage_mask",
            "analysis_log",
        ),
    ),
    "busco": (
        family.BUSCONode,
        {"input": "assembly.fa", "mode": "genome", "threads": 4},
        "busco",
        ("short_summary.txt", "full_table.tsv", "missing_buscos.tsv", "summary.png"),
        ("short_summary", "full_table", "missing_buscos", "summary_image"),
    ),
    "htseq_count": (
        family.HTSeqCountNode,
        {"samfile": "alignments.bam", "gfffile": "genes.gtf"},
        "htseq-count",
        ("counts.tsv",),
        ("counts",),
    ),
    "roary": (
        family.RoaryNode,
        {"gffs": ["sample_a.gff", "sample_b.gff"]},
        "roary",
        ("summary_statistics.txt", "core_gene_alignment.aln", "gene_presence_absence.csv"),
        ("summary_statistics", "core_gene_alignment", "gene_presence_absence"),
    ),
    "seqkit_stats": (
        family.SeqKitStatsNode,
        {"input": "reads.fastq"},
        "seqkit stats",
        ("stats.tsv",),
        ("stats",),
    ),
    "seqkit_grep": (
        family.SeqKitGrepNode,
        {"input": "sequences.fa", "pattern_mode": "expression", "pattern": "ACGT", "output_ext": "fasta"},
        "seqkit grep",
        ("grep.fasta",),
        ("fasta_output",),
    ),
    "seqkit_head": (
        family.SeqKitHeadNode,
        {"input": "reads.fastq", "number": 10, "output_ext": "fastq"},
        "seqkit head",
        ("head.fastq",),
        ("head_output",),
    ),
    "seqkit_fx2tab": (
        family.SeqKitFx2tabNode,
        {"input": "reads.fastq"},
        "seqkit fx2tab",
        ("fx2tab.tsv",),
        ("tabular",),
    ),
    "seqkit_sort": (
        family.SeqKitSortNode,
        {"input": "reads.fastq", "output_ext": "fastq"},
        "seqkit sort",
        ("sorted.fastq",),
        ("sorted_sequences",),
    ),
    "seqkit_locate": (
        family.SeqKitLocateNode,
        {"input": "sequences.fa", "pattern_mode": "expression", "pattern": "ACGT"},
        "seqkit locate",
        ("locate.tsv",),
        ("tabular",),
    ),
    "seqkit_translate": (
        family.SeqKitTranslateNode,
        {"input": "sequences.fa", "output_ext": "fasta"},
        "seqkit translate",
        ("translated.fasta",),
        ("translated_fasta",),
    ),
    "seqkit_split2": (
        family.SeqKitSplit2Node,
        {"input_type": "single", "input_1": "reads.fa", "input_1_ext": "fasta", "by_part": 2},
        "seqkit split2",
        ("split_files",),
        ("split_files",),
    ),
    "amrfinderplus": (
        family.AMRFinderPlusNode,
        {"database": "amrfinder-db", "input_select": "nucleotide", "nucleotide_input": "contigs.fa"},
        "amrfinder",
        ("amrfinderplus_report.tsv", "amrfinderplus_nucleotide_output.fasta"),
        ("amrfinderplus_report", "nucleotide_output"),
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


def _command_text(command: Any) -> str:
    return " ".join(str(part) for part in command) if isinstance(command, list) else str(command)


def test_exactly_23_stable_ids_have_one_focused_owner_and_facade_reexport() -> None:
    assert set(CASES) == set(contracts.NODE_EVIDENCE)
    assert len(CASES) == 23

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
    assert node_class.GALAXY_WRAPPER_GIT_COMMIT == evidence.commit
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
    assert command_fragment in _command_text(node_class.render_command(inputs))
    planned = node_class.PLAN_OUTPUTS(inputs, tmp_path)
    assert tuple(path.name for path in planned) == expected_files
    assert tuple(node_class.MAP_PLANNED_OUTPUTS(planned)) == expected_ports


@pytest.mark.parametrize(
    ("node_class", "inputs", "expected_ports"),
    [
        (
            family.AegeanLocusPocusNode,
            {"genesgff3": "genes.gff3", "outputfiles": ["ilens", "genemap", "transmap"]},
            ("output", "output_ilens", "output_genemap", "output_transmap"),
        ),
        (
            family.AegeanParsevalNode,
            {"referencegff3": "reference.gff3", "predictiongff3": "prediction.gff3", "output_type": "html"},
            ("output_html",),
        ),
        (
            family.AugustusNode,
            {"input_genome": "genome.fa", "model_mode": "builtin", "output_format": "gff3", "outputs": ["protein"]},
            ("output", "protein_output"),
        ),
        (
            family.ArribaNode,
            {
                "input": "alignments.bam",
                "genome_assembly": "genome.fa",
                "annotation": "genes.gtf",
                "output_fusions_discarded": False,
                "output_fusions_vcf": False,
                "output_fusion_bams": True,
                "do_viz": "yes",
            },
            ("fusions_tsv", "fusion_bams", "fusions_pdf"),
        ),
        (
            family.RoaryNode,
            {
                "gffs": ["sample_a.gff", "sample_b.gff"],
                "outputs": list(family.RoaryNode.OUTPUT_FILE_ORDER),
            },
            family.RoaryNode.RETURN_NAMES,
        ),
        (
            family.SeqKitGrepNode,
            {"input": "reads.fastq", "pattern_mode": "expression", "pattern": "sample", "count": True},
            ("count",),
        ),
        (
            family.SeqKitGrepNode,
            {"input": "reads.fastq", "pattern_mode": "expression", "pattern": "sample", "output_ext": "fastq.gz"},
            ("fastq_output",),
        ),
        (
            family.SeqKitLocateNode,
            {"input": "sequences.fa", "pattern_mode": "expression", "pattern": "ACGT", "output_mode": "--bed"},
            ("bed",),
        ),
        (
            family.SeqKitLocateNode,
            {"input": "sequences.fa", "pattern_mode": "expression", "pattern": "ACGT", "output_mode": "--gtf"},
            ("gtf",),
        ),
        (
            family.SeqKitTranslateNode,
            {"input": "reads.fastq", "output_ext": "fastq.gz"},
            ("translated_fastq",),
        ),
        (
            family.SeqKitSplit2Node,
            {
                "input_type": "paired_collection",
                "input_1": "reads_1.fastq",
                "input_2": "reads_2.fastq",
                "input_1_ext": "fastq",
                "input_2_ext": "fastq",
            },
            ("paired_split_files",),
        ),
        (
            family.AMRFinderPlusNode,
            {
                "database": "amrfinder-db",
                "input_select": "nucl_prot",
                "nucleotide_input": "contigs.fa",
                "protein_input": "proteins.fa",
                "gff_annotation": "genes.gff",
                "organism": "Escherichia",
                "mutation_all": True,
                "nucleotide_flank5_size": 100,
            },
            (
                "amrfinderplus_report",
                "mutation_all_report",
                "protein_output",
                "nucleotide_output",
                "nucleotide_flank5_output",
            ),
        ),
    ],
)
def test_sparse_and_mode_specific_outputs_keep_their_declared_ports(
    node_class: type[BaseNode],
    inputs: dict[str, Any],
    expected_ports: tuple[str, ...],
    tmp_path: Path,
) -> None:
    planned = node_class.PLAN_OUTPUTS({**inputs, "output": f"/work/{node_class.NODE_ID}"}, tmp_path)
    assert tuple(node_class.MAP_PLANNED_OUTPUTS(planned)) == expected_ports


def test_named_output_mapping_rejects_unknown_artifacts(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown artifact"):
        family.ArribaNode.MAP_PLANNED_OUTPUTS([tmp_path / "unexpected.txt"])
