from __future__ import annotations

import copy
import inspect
from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin import wrapped_assembly_typing as facade


TOOLS_IUC_COMMIT = "8eb66da1f6f16fde92688ee6c500d2bcdc924a47"
CHEWBBACA_COMMIT = "4aa71967426065e30613cbe151c32614363eaf1e"

EXPECTED_OUTPUTS = {
    "abricate": ("report.tsv",),
    "abricate_list": ("databases.txt",),
    "abricate_summary": ("summary.tsv",),
    "bandage_image": ("out.jpg",),
    "bandage_info": ("out.tab",),
    "checkm2": ("output/quality_report.tsv", "output/protein_files", "output/diamond_output"),
    "checkm_analyze": (
        "output/bins/hmmer_analyze",
        "output/storage/bin_stats.analyze.tsv",
        "output/storage/checkm_hmm_info.pkl.gz",
    ),
    "checkm_lineage_set": ("marker.tsv",),
    "checkm_lineage_wf": ("results.tsv",),
    "checkm_plot": ("gc_plot",),
    "checkm_qa": ("output.tsv", "output/storage/bin_stats_ext.tsv"),
    "checkm_taxon_set": ("marker.tsv",),
    "checkm_taxonomy_wf": ("results.tsv",),
    "checkm_tetra": ("tetra_profile.tsv",),
    "checkm_tree": (
        "output/storage/phylo_hmm_info.pkl.gz",
        "output/storage/bin_stats.tree.tsv",
        "output/bins/hmmer_tree",
        "output/storage/tree/concatenated.fasta",
        "output/storage/tree/concatenated.tre",
    ),
    "checkm_tree_qa": ("output_f1.tsv",),
    "cherri_eval": ("cherri_eval/evaluation/evaluation_results_eval_rri.csv",),
    "cherri_train": ("model.tgz",),
    "chewbbaca_allelecall": ("output", "output"),
    "chewbbaca_allelecallevaluator": ("output.html",),
    "chewbbaca_createschema": ("output/schema_seed.zip",),
    "chewbbaca_downloadschema": ("schema_seed.zip",),
    "chewbbaca_extractcgmlst": ("output_collection",),
    "chewbbaca_joinprofiles": ("JoinedProfile.tsv",),
    "chewbbaca_nsstats": ("NSStats.txt",),
    "chewbbaca_prepexternalschema": ("PExternalschema_seed.zip",),
    "chira_collapse": ("collapsed.fasta",),
    "chira_extract": ("chimeras",),
    "chira_map": ("sorted.bed", "unmapped.fasta"),
    "chira_merge": ("segments.bed", "merged.bed"),
    "chira_quantify": ("loci.counts",),
    "das_tool": (
        "outputs_DASTool_summary.tsv",
        "outputs_DASTool_contig2bin.tsv",
        "outputs_DASTool.log",
        "outputs_DASTool_bins",
    ),
    "fasta_to_contig2bin": ("contigs2bin.tsv",),
    "gfa_to_fa": ("out.fa",),
    "kleborate": ("kleborate_concise_results.tsv", "kleborate_results.tsv"),
    "plasmidfinder": ("Hit_in_genome_seq.fsa", "Plasmid_seqs.fsa", "results_tab.tsv", "results.txt"),
    "raven": ("out.fasta", "out.gfa"),
    "shovill": ("out/shovill.log", "out/contigs.fa", "out/spades.gfa"),
    "snippy": ("out/snps.vcf", "out/snps.tab", "out.tgz"),
    "snippy_clean_full_aln": ("clean.full.aln",),
    "snippy_core": ("core.aln",),
    "staramr_search": (
        "mlst.tsv",
        "summary.tsv",
        "detailed_summary.tsv",
        "resfinder.tsv",
        "plasmidfinder.tsv",
        "settings.txt",
        "results.xlsx",
        "staramr_hits",
    ),
}

SOURCE_GROUPS = (
    (("gfa_to_fa",), TOOLS_IUC_COMMIT, "tools/gfa_to_fa", "0.1.2", "python wrapper gfa_to_fa==0.1.2"),
    (("raven",), TOOLS_IUC_COMMIT, "tools/raven", "1.8.3+galaxy0", "raven-assembler==1.8.3"),
    (("shovill",), TOOLS_IUC_COMMIT, "tools/shovill", "1.4.2+galaxy1", "shovill==1.4.2"),
    (
        ("snippy", "snippy_core", "snippy_clean_full_aln"),
        TOOLS_IUC_COMMIT,
        "tools/snippy",
        "4.6.0+galaxy0",
        "snippy==4.6.0; tar==1.32",
    ),
    (
        ("abricate", "abricate_list", "abricate_summary"),
        TOOLS_IUC_COMMIT,
        "tools/abricate",
        "1.4.0",
        "abricate==1.4.0",
    ),
    (
        ("kleborate",),
        TOOLS_IUC_COMMIT,
        "tools/kleborate",
        "2.3.2+galaxy1",
        "kleborate==2.3.2; kaptive==2.0.6",
    ),
    (
        ("plasmidfinder",),
        TOOLS_IUC_COMMIT,
        "tools/plasmidfinder",
        "2.1.6+galaxy2",
        "plasmidfinder==2.1.6",
    ),
    (
        ("staramr_search",),
        TOOLS_IUC_COMMIT,
        "tools/staramr",
        "0.12.3+galaxy0",
        "staramr==0.12.3; mlst==2.33.1",
    ),
    (
        (
            "checkm_lineage_wf",
            "checkm_tree",
            "checkm_tree_qa",
            "checkm_lineage_set",
            "checkm_taxon_set",
            "checkm_taxonomy_wf",
            "checkm_tetra",
            "checkm_plot",
            "checkm_analyze",
            "checkm_qa",
        ),
        TOOLS_IUC_COMMIT,
        "tools/checkm",
        "1.2.5+galaxy0",
        "checkm-genome==1.2.5",
    ),
    (("checkm2",), TOOLS_IUC_COMMIT, "tools/checkm2", "1.1.0+galaxy0", "checkm2==1.1.0"),
    (
        ("cherri_eval", "cherri_train"),
        TOOLS_IUC_COMMIT,
        "tools/cherri",
        {"cherri_eval": "0.7", "cherri_train": "0.7+galaxy0"},
        "cherri==0.7",
    ),
    (
        ("chira_collapse", "chira_map", "chira_merge", "chira_quantify", "chira_extract"),
        TOOLS_IUC_COMMIT,
        "tools/chira",
        {
            "chira_collapse": "1.4.3+galaxy1",
            "chira_map": "1.4.3+galaxy0",
            "chira_merge": "1.4.3+galaxy0",
            "chira_quantify": "1.4.3+galaxy0",
            "chira_extract": "1.4.3+galaxy1",
        },
        "chira==1.4.3",
    ),
    (
        (
            "chewbbaca_allelecall",
            "chewbbaca_allelecallevaluator",
            "chewbbaca_createschema",
            "chewbbaca_downloadschema",
            "chewbbaca_extractcgmlst",
            "chewbbaca_joinprofiles",
            "chewbbaca_nsstats",
            "chewbbaca_prepexternalschema",
        ),
        CHEWBBACA_COMMIT,
        "tools/chewbbaca",
        "3.3.10+galaxy1",
        "chewbbaca==3.3.10; blast==2.15.0; zip==3.0; fasttree==2.1.11",
    ),
    (
        ("das_tool", "fasta_to_contig2bin"),
        TOOLS_IUC_COMMIT,
        "tools/das_tool",
        "1.1.7+galaxy1",
        "das_tool==1.1.7",
    ),
    (
        ("bandage_info", "bandage_image"),
        TOOLS_IUC_COMMIT,
        "tools/bandage",
        {"bandage_info": "2022.09+galaxy2", "bandage_image": "2022.09+galaxy4"},
        "bandage_ng==2022.09",
    ),
)

SOURCE_CASES = [
    (
        node_id,
        commit,
        source_dir,
        versions[node_id] if isinstance(versions, dict) else versions,
        constraint,
    )
    for node_ids, commit, source_dir, versions, constraint in SOURCE_GROUPS
    for node_id in node_ids
]


def _node_classes() -> dict[str, type[BaseNode]]:
    return {
        candidate.NODE_ID: candidate
        for _name, candidate in inspect.getmembers(facade, inspect.isclass)
        if issubclass(candidate, BaseNode) and candidate is not BaseNode and candidate.NODE_ID
    }


def _sample_value(name: str, spec: Any) -> Any:
    type_spec = spec[0]
    config = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
    if "default" in config and config["default"] not in ("", []):
        return copy.deepcopy(config["default"])
    if isinstance(type_spec, list):
        return copy.deepcopy(type_spec[0])
    if config.get("multiple") or config.get("list") or config.get("is_list") or str(type_spec).endswith("_LIST"):
        return [f"/inputs/{name}.dat"]
    if type_spec == "BOOLEAN":
        return False
    if type_spec == "FLOAT":
        return 1.0
    if type_spec == "INT":
        return 1
    if type_spec in {
        "BAM",
        "BED",
        "CSV",
        "DIRECTORY",
        "FASTA",
        "FASTQ",
        "FILE",
        "GFA",
        "GFF",
        "JSON",
        "NEWICK",
        "PHYLOGENY_TREE",
        "STOCKHOLM",
        "TSV",
        "TXT",
        "VCF",
        "ZIP",
    }:
        return f"/inputs/{name}.dat"
    return "value"


def _sample_inputs(node_class: type[BaseNode]) -> dict[str, Any]:
    inputs = {
        name: _sample_value(name, spec)
        for name, spec in node_class.INPUT_TYPES().get("required", {}).items()
    }
    inputs["output"] = f"/work/{node_class.NODE_ID}"

    overrides = {
        "checkm_tree_qa": {"concatenated_tre": "/inputs/concatenated.tre"},
        "cherri_train": {
            "experiments": [
                {
                    "exp_name": "experiment_1",
                    "genome_fasta": "/inputs/genome.fa",
                    "chrom_len_file": "/inputs/chrom_lengths.tsv",
                    "rep_samples": ["/inputs/replicate.tsv"],
                }
            ]
        },
        "chewbbaca_downloadschema": {"species_id": "1"},
        "chewbbaca_nsstats": {"mode": "species"},
        "chira_extract": {
            "ref_type": "split",
            "ref_fasta1": "/inputs/reference_1.fa",
            "ref_fasta2": "/inputs/reference_2.fa",
        },
        "chira_map": {
            "ref_type": "split",
            "ref_fasta1": "/inputs/reference_1.fa",
            "ref_fasta2": "/inputs/reference_2.fa",
        },
        "snippy": {
            "reference_source_selector": "history",
            "ref_file": "/inputs/reference.fa",
            "fastq_input_selector": "paired",
            "fastq_input1": "/inputs/reads_1.fastq",
            "fastq_input2": "/inputs/reads_2.fastq",
        },
        "snippy_core": {
            "indirs": ["/inputs/sample_1.tar", "/inputs/sample_2.tar"],
            "reference_source_selector": "history",
            "ref_file": "/inputs/reference.fa",
        },
    }
    inputs.update(overrides.get(node_class.NODE_ID, {}))
    return inputs


def _command_text(command: Any) -> str:
    if isinstance(command, list):
        return " ".join(str(part) for part in command)
    return str(command)


def _planned_relatives(node_class: type[BaseNode], inputs: dict[str, Any], tmp_path: Path) -> tuple[str, ...]:
    planned = node_class.PLAN_OUTPUTS(inputs, tmp_path)
    paths = planned.values() if isinstance(planned, dict) else planned
    root = tmp_path / node_class.NODE_ID
    return tuple(str(Path(path).relative_to(root)) for path in paths)


def test_exactly_42_stable_ids_keep_legacy_facade_exports() -> None:
    classes = _node_classes()
    assert set(classes) == set(EXPECTED_OUTPUTS)
    assert len(classes) == 42

    for node_id, node_class in classes.items():
        assert getattr(facade, node_class.__name__) is node_class
        assert node_class.NODE_ID == node_id


@pytest.mark.parametrize("node_id", sorted(EXPECTED_OUTPUTS))
def test_each_contract_validates_renders_and_plans_declared_outputs(node_id: str, tmp_path: Path) -> None:
    node_class = _node_classes()[node_id]
    inputs = _sample_inputs(node_class)

    assert node_class.VALIDATE_INPUTS(inputs) is True
    command = _command_text(node_class.render_command(inputs))
    assert command
    assert any(executable in command for executable in node_class.REQUIRED_EXECUTABLES)
    assert _planned_relatives(node_class, inputs, tmp_path) == EXPECTED_OUTPUTS[node_id]


@pytest.mark.parametrize(
    ("node_id", "commit", "source_dir", "wrapper_version", "constraint"),
    SOURCE_CASES,
    ids=[case[0] for case in SOURCE_CASES],
)
def test_each_contract_is_pinned_to_an_exact_wrapper_authority(
    node_id: str,
    commit: str,
    source_dir: str,
    wrapper_version: str,
    constraint: str,
) -> None:
    node_class = _node_classes()[node_id]
    versions = getattr(node_class, "GALAXY_WRAPPER_VERSIONS", {})
    actual_version = versions.get(node_id, getattr(node_class, "GALAXY_WRAPPER_VERSION", None))

    assert node_class.GIT_COMMIT == commit
    assert node_class.GALAXY_WRAPPER_GIT_COMMIT == commit
    assert commit in node_class.SOURCE_URL
    assert node_class.SOURCE_URL.endswith(source_dir)
    assert node_class.GALAXY_WRAPPER_SOURCE_URL == node_class.SOURCE_URL
    assert actual_version == wrapper_version
    assert node_class.PACKAGE_CONSTRAINT == constraint
    assert node_class.DOCUMENTATION_URL
    assert node_class.EXIT_SEMANTICS


@pytest.mark.parametrize(
    ("node_id", "inputs", "error"),
    [
        ("abricate", {"file_input": "assembly.fa", "min_dna_id": 101}, "between 0 and 100"),
        ("bandage_image", {"input_file": "graph.gfa", "height": 0}, "at least 1"),
        ("checkm2", {"input": ["bin.fa"], "database_path": ""}, "database_path"),
        (
            "cherri_train",
            {"experiments": [{"chrom_len_file": "chrom.tsv", "rep_samples": ["rep.tsv"]}]},
            "genome_fasta",
        ),
        ("chewbbaca_createschema", {"input_file": ["assembly.fa"], "blast_score_ratio": 1.1}, "between 0 and 1"),
        ("chewbbaca_downloadschema", {"species_id": "zero"}, "species_id"),
        (
            "chira_map",
            {"query": "reads.fa", "ref_type": "split", "ref_fasta1": "ref1.fa", "aligner": "bwa"},
            "ref_fasta2",
        ),
        (
            "chira_extract",
            {"loci": "loci.tsv", "annot_choice": "no", "ref_type": "single"},
            "ref_fasta",
        ),
        ("plasmidfinder", {"input_file": "assembly.fa", "database": "/db", "threshold": 1.1}, "between 0 and 1"),
        ("raven", {"input_reads": "reads.fastq", "gap": 0}, "less than or equal to -1"),
        ("shovill", {"lib_type": "paired", "R1": "reads_1.fastq", "R2": ""}, "R2"),
        (
            "snippy",
            {
                "reference_source_selector": "history",
                "ref_file": "reference.fa",
                "fastq_input_selector": "paired",
                "fastq_input1": "reads_1.fastq",
            },
            "fastq_input2",
        ),
        (
            "snippy_core",
            {"indirs": ["sample.tar"], "reference_source_selector": "history", "ref_file": "reference.fa"},
            "at least two",
        ),
        (
            "staramr_search",
            {"genomes": ["assembly.fa"], "database": "/db", "exclude_genes_condition": "custom"},
            "exclude_genes_file",
        ),
    ],
)
def test_conditional_inputs_and_bounds_fail_closed(node_id: str, inputs: dict[str, Any], error: str) -> None:
    validation = _node_classes()[node_id].VALIDATE_INPUTS(inputs)
    assert validation is not True
    assert error in str(validation)


def test_representative_commands_preserve_documented_argument_order() -> None:
    classes = _node_classes()

    assert classes["abricate"].render_command(
        {
            "file_input": "assembly.fa",
            "db": "card",
            "min_dna_id": 90,
            "min_cov": 75,
            "no_header": True,
            "output": "/work/abricate",
        }
    ) == (
        "ln -sf assembly.fa assembly.fa && abricate assembly.fa --noheader --minid=90 "
        "--mincov=75 --db=card > /work/abricate/report.tsv"
    )

    assert classes["gfa_to_fa"].render_command(
        {"in_gfa": "graph.gfa", "script_path": "gfa_to_fa.py", "output": "/work/gfa_to_fa"}
    ) == "cat graph.gfa | python gfa_to_fa.py > /work/gfa_to_fa/out.fa"

    raven = classes["raven"].render_command(
        {
            "input_reads": "reads.fastq.gz",
            "input_format": "fastq.gz",
            "graphical_fragment_assembly": True,
            "use_micromizers": True,
            "output": "/work/raven",
        }
    )
    assert raven == (
        "ln -s reads.fastq.gz ./input.fq.gz && raven --kmer-len 15 --window-len 5 --frequency 0.001 "
        "--polishing-rounds 2 --match 3 --mismatch -5 --gap -4 --kMaxNumOverlaps 32 --identity 0 "
        "--min-unitig-size 9999 --use-micromizers --graphical-fragment-assembly /work/raven/out.gfa "
        "--disable-checkpoints -t ${GALAXY_SLOTS:-4} ./input.fq.gz > /work/raven/out.fasta"
    )

    assert classes["checkm_tetra"].render_command(
        {"seq_file": "bin.fa", "threads": 8, "output": "/work/checkm_tetra"}
    ) == ["checkm", "tetra", "bin.fa", "/work/checkm_tetra/tetra_profile.tsv", "--threads", "8"]

    assert classes["chira_map"].render_command(
        {
            "query": "collapsed.fa",
            "ref_type": "split",
            "ref_fasta1": "ref1.fa",
            "ref_fasta2": "ref2.fa",
            "aligner": "clan",
            "align_score": 12,
            "chimeric_overlap": 3,
            "threads": 6,
            "output": "/work/chira_map",
        }
    ) == (
        "mkdir -p /work/chira_map && cd /work/chira_map && chira_map.py -b -a clan -i collapsed.fa "
        "-s2 12 -co 3 -f1 ref1.fa -f2 ref2.fa -p ${GALAXY_SLOTS:-6} -o ./"
    )

    assert classes["chewbbaca_createschema"].render_command(
        {
            "input_file": ["a.fa", "b.fa"],
            "minimum_length": 201,
            "blast_score_ratio": 0.6,
            "translation_table": 11,
            "size_threshold": 0.2,
            "prodigal_mode": "single",
            "show_cds_invalid": True,
            "output": "/work/chewbbaca_createschema",
        }
    ) == (
        "mkdir -p /work/chewbbaca_createschema && cd /work/chewbbaca_createschema && mkdir input && "
        "ln -sf a.fa input/a.fa && ln -sf b.fa input/b.fa && chewBBACA.py CreateSchema --bsr 0.6 "
        "--l 201 --t 11 --st 0.2 --pm single -i input -o output && cd output/ && zip -r schema_seed.zip schema_seed"
    )

    assert classes["das_tool"].render_command(
        {
            "contigs": "contigs.fa",
            "bins": ["metabat.tsv", "maxbin.tsv"],
            "labels": ["metabat", "maxbin"],
            "search_engine": "diamond",
            "score_threshold": 0.5,
            "duplicate_penalty": 0.6,
            "megabin_penalty": 0.5,
            "max_iter_post_threshold": 10,
            "write_bins": "--write_bins",
            "threads": 4,
            "output": "/work/das_tool",
        }
    ) == [
        "DAS_Tool",
        "--contigs",
        "contigs.fa",
        "--outputbasename",
        "/work/das_tool/outputs",
        "--bins",
        "metabat.tsv,maxbin.tsv",
        "--labels",
        "metabat,maxbin",
        "--search_engine",
        "diamond",
        "--score_threshold",
        "0.5",
        "--duplicate_penalty",
        "0.6",
        "--megabin_penalty",
        "0.5",
        "--max_iter_post_threshold",
        "10",
        "--write_bins",
        "--threads",
        "4",
    ]
