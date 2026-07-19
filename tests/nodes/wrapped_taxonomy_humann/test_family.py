from __future__ import annotations

import copy
import importlib
import inspect
from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin import wrapped_taxonomy_humann as facade
from bionodulo.nodes.builtin.wrapped_taxonomy_humann_family.contracts import (
    NODE_EVIDENCE,
    TOOLS_IUC_GIT_COMMIT,
)


EXPECTED_OUTPUTS = {
    "biom_add_metadata": ("output.biom",),
    "biom_convert": ("output.biom",),
    "biom_from_uc": ("output.biom",),
    "biom_normalize_table": ("output.biom",),
    "biom_subset_table": ("output.biom",),
    "biom_summarize_table": ("output.txt",),
    "bmtagger": ("out_single.fastq",),
    "est_abundance": ("report.tsv",),
    "humann_barplot": ("output.pdf",),
    "humann_join_tables": ("joined_tables.tsv",),
    "humann_reduce_table": ("reduced_table.tsv",),
    "humann_regroup_table": ("regrouped_table.tsv",),
    "humann_rename_table": ("renamed_table.tsv",),
    "humann_renorm_table": ("renormalized_table.tsv",),
    "humann_split_stratified_table": (
        "split_stratified/input_stratified.dat",
        "split_stratified/input_unstratified.dat",
    ),
    "humann_split_table": ("split_tables",),
    "humann_unpack_pathways": ("unpacked_pathways.tsv",),
    "hybpiper": ("hybpiper_archive.tar",),
    "krakentools_alpha_diversity": ("alpha_diversity.txt",),
    "krakentools_beta_diversity": ("beta_diversity.tsv",),
    "krakentools_combine_kreports": ("combined_kreport.tsv",),
    "krakentools_extract_kraken_reads": (
        "output_1.fasta.gz",
        "output_2.fasta.gz",
        "paired_reads",
    ),
    "krakentools_kreport2krona": ("krona_text.tsv",),
    "krakentools_kreport2mpa": ("metaphlan_profile.tsv",),
    "magicblast": ("output.bam",),
    "mothur_taxonomy_to_krona": ("krona_taxonomy.tsv",),
    "recentrifuge": (
        "output.rcf.html",
        "logfile.txt",
        "output.rcf.data.csv",
        "output.rcf.stat.csv",
    ),
    "taxonkit_name2taxid": ("names2taxid.tsv",),
    "taxonkit_profile2cami": ("cami_profile.tsv",),
    "taxonomy_krona_chart": ("krona.html",),
    "taxpasta": ("tabular_output.tsv",),
    "tracy_align": ("out.txt", "out.align.fa"),
    "tracy_assemble": ("out.cons.fa", "out.align.fa"),
    "tracy_basecall": ("basecalls.fasta",),
    "tracy_decompose": ("out.align1", "out.align2", "out.align3"),
}

ADAPTER_MODULES = (
    "bionodulo.nodes.builtin.wrapped_taxonomy_humann_family.contracts",
    "bionodulo.nodes.builtin.wrapped_taxonomy_humann_family.classification.adapter",
    "bionodulo.nodes.builtin.wrapped_taxonomy_humann_family.biom.adapter",
    "bionodulo.nodes.builtin.wrapped_taxonomy_humann_family.krakentools.adapter",
    "bionodulo.nodes.builtin.wrapped_taxonomy_humann_family.tracy.adapter",
    "bionodulo.nodes.builtin.wrapped_taxonomy_humann_family.humann.adapter",
    "bionodulo.nodes.builtin.wrapped_taxonomy_humann_family.hybpiper.adapter",
)


def _node_classes() -> dict[str, type[BaseNode]]:
    return {
        candidate.NODE_ID: candidate
        for _name, candidate in inspect.getmembers(facade, inspect.isclass)
        if issubclass(candidate, BaseNode) and candidate is not BaseNode and candidate.NODE_ID
    }


def _owned_node_classes(module: Any) -> list[type[BaseNode]]:
    return [
        candidate
        for _name, candidate in inspect.getmembers(module, inspect.isclass)
        if issubclass(candidate, BaseNode)
        and candidate is not BaseNode
        and candidate.__module__ == module.__name__
        and candidate.NODE_ID
    ]


def _sample_value(name: str, spec: Any) -> Any:
    type_spec = spec[0]
    config = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
    if "default" in config and config["default"] not in ("", []):
        return copy.deepcopy(config["default"])
    if config.get("options"):
        return copy.deepcopy(config["options"][0])
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
        "bmtagger": {"host_source": "cached", "reference": "/db/host"},
        "hybpiper": {
            "hybpiper_job": "assemble",
            "paired_forward": "/inputs/reads_1.fastq",
            "paired_reverse": "/inputs/reads_2.fastq",
            "sample_name": "sample",
        },
        "krakentools_extract_kraken_reads": {"taxid": "9606"},
        "magicblast": {"db_opts_selector": "histdb", "histdb": "/db/reference"},
        "taxonkit_name2taxid": {
            "data_source": "history",
            "taxdump": "/inputs/taxdump.tar.gz",
        },
        "tracy_assemble": {"tracefiles": ["/inputs/read_1.ab1", "/inputs/read_2.ab1"]},
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


def test_exactly_35_stable_ids_have_focused_owners() -> None:
    classes = _node_classes()
    assert set(classes) == set(EXPECTED_OUTPUTS) == set(NODE_EVIDENCE)
    assert len(classes) == 35

    for module_name in ADAPTER_MODULES:
        assert _owned_node_classes(importlib.import_module(module_name)) == []

    for node_id, node_class in classes.items():
        owner = importlib.import_module(node_class.__module__)
        assert _owned_node_classes(owner) == [node_class]
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


@pytest.mark.parametrize("node_id", sorted(NODE_EVIDENCE))
def test_each_contract_is_pinned_to_the_exact_wrapper_and_packages(node_id: str) -> None:
    node_class = _node_classes()[node_id]
    evidence = NODE_EVIDENCE[node_id]

    assert node_class.GIT_COMMIT == TOOLS_IUC_GIT_COMMIT == evidence.commit
    assert node_class.GALAXY_WRAPPER_GIT_COMMIT == evidence.commit
    assert node_class.GALAXY_WRAPPER_PATH == evidence.wrapper_path
    assert node_class.GALAXY_WRAPPER_VERSION == evidence.wrapper_version
    assert node_class.PACKAGE_CONSTRAINTS == evidence.package_constraints
    assert node_class.SOURCE_URL == evidence.source_url
    assert node_class.GALAXY_WRAPPER_SOURCE_URL == evidence.source_url
    assert node_class.DOCUMENTATION_URL
    assert node_class.EXIT_SEMANTICS
    assert node_class.AUDIT_STATUS == "contract-checked-no-external-execution"


@pytest.mark.parametrize(
    ("node_id", "inputs", "error"),
    [
        ("est_abundance", {"input": "report.tsv", "kmer_distr": "/db/bracken", "threshold": -1}, ">= 0"),
        ("magicblast", {"query": "reads.fastq", "db_opts_selector": "histdb"}, "histdb"),
        (
            "bmtagger",
            {
                "reads": "reads_1.fastq",
                "sequence_type": "paired",
                "reads_reverse": "",
                "host_source": "cached",
                "reference": "/db/host",
            },
            "reads_reverse",
        ),
        ("biom_convert", {"input_fp": "table.tsv", "output_type": "biom", "biom_type": "bad"}, "biom_type"),
        (
            "krakentools_extract_kraken_reads",
            {"library_type": "single", "input_1": "reads.fastq", "results": "kraken.tsv", "taxid": "human"},
            "numeric tax IDs",
        ),
        (
            "recentrifuge",
            {"input_file": ["report.tsv"], "filetype": "bad", "database_name": "/db/taxonomy"},
            "filetype",
        ),
        (
            "taxpasta",
            {"action": "bad", "profiler": "kraken2", "infile": ["report.tsv"], "taxonomy": "/db/taxonomy"},
            "action",
        ),
        (
            "taxonkit_name2taxid",
            {"input": "names.tsv", "name_field": 1, "data_source": "history"},
            "taxdump",
        ),
        ("tracy_basecall", {"tracefile": "sample.ab1", "format": "xml"}, "format"),
        ("humann_regroup_table", {"input": "genes.tsv", "grouping_type": "custom"}, "grouping file"),
        ("humann_barplot", {"input": "pathways.tsv", "focal_feature": "PWY", "format": "bmp"}, "format"),
        (
            "hybpiper",
            {"targetfile_dna": "targets.fa", "hybpiper_job": "assemble", "paired_forward": "reads_1.fastq"},
            "paired forward and reverse",
        ),
    ],
)
def test_conditional_inputs_and_modes_fail_closed(node_id: str, inputs: dict[str, Any], error: str) -> None:
    validation = _node_classes()[node_id].VALIDATE_INPUTS(inputs)
    assert validation is not True
    assert error in str(validation)


def test_representative_commands_preserve_documented_argument_order() -> None:
    classes = _node_classes()

    assert classes["magicblast"].render_command(
        {
            "query": "reads.fastq.gz",
            "query_type": "fastq.gz",
            "db_opts_selector": "histdb",
            "histdb": "/db/ref",
            "outfmt": "tabular",
            "report_unaligned": "no",
            "no_discordant": True,
            "threads": 6,
            "output": "/work/magicblast",
        }
    ) == (
        "magicblast -num_threads ${GALAXY_SLOTS:-6} -query <(gunzip -c reads.fastq.gz) -infmt fastq "
        "-db /db/ref/blastdb -word_size 18 -gapopen 0 -gapextend 0 -penalty -4 -max_intron_length 500000 "
        "-validate_seqs true -limit_lookup true -max_db_word_count 30 -lookup_stride 0 -score 0 -splice true "
        "-reftype genome -no_unaligned -no_discordant -out /work/magicblast/output.tabular -outfmt tabular"
    )

    assert classes["biom_convert"].render_command(
        {
            "input_fp": "table.tsv",
            "input_type": "tsv",
            "output_type": "biom",
            "biom_type": "json",
            "table_type": "OTU table",
            "output": "/work/biom_convert",
        }
    ) == (
        "sed '1s/^\\([^#].*\\)/#\\1/' table.tsv > input && biom convert --input-fp input "
        "--output-fp /work/biom_convert/output.biom --table-type 'OTU table' --to-json"
    )

    assert classes["krakentools_combine_kreports"].render_command(
        {
            "reports": ["a.tsv", "b.tsv"],
            "element_identifiers": ["A", "B"],
            "display_headers": True,
            "only_combined": False,
            "output": "/work/kraken",
        }
    ) == (
        "ln -s a.tsv A && ln -s b.tsv B && combine_kreports.py --reports A B "
        "--output /work/kraken/combined_kreport.tsv --display-headers"
    )

    assert classes["tracy_align"].render_command(
        {
            "reference": "ref.fa",
            "tracefile": "sample.ab1",
            "kmer": 17,
            "support": 4,
            "gapopen": -9,
            "gapext": -3,
            "match": 4,
            "mismatch": -6,
            "optional_outputs": ["json"],
            "output": "/work/tracy_align",
        }
    ) == (
        "tracy align --reference ref.fa --pratio 0.33 --kmer 17 --support 4 --maxindel 1000 --trim 0 "
        "--trimLeft 50 --trimRight 50 --linelimit 60 --gapopen -9 --gapext -3 --match 4 --mismatch -6 "
        "--output /work/tracy_align sample.ab1"
    )

    assert classes["humann_regroup_table"].render_command(
        {
            "input": "genes.tsv",
            "grouping_type": "standard",
            "groups": "uniref90_rxn",
            "function": "mean",
            "precision": 4,
            "ungrouped": False,
            "protected": False,
            "output": "/work/humann_regroup",
        }
    ) == (
        "humann_regroup_table --input genes.tsv --output /work/humann_regroup/regrouped_table.tsv "
        "--function mean --groups uniref90_rxn --precision 4 --ungrouped N --protected N"
    )

    assert classes["hybpiper"].render_command(
        {
            "targetfile_dna": "targets.fa",
            "hybpiper_job": "assemble",
            "paired_forward": "R1.fq.gz",
            "paired_reverse": "R2.fq.gz",
            "sample_name": "S1",
            "threads": 8,
            "output": "/work/hybpiper",
        }
    ) == (
        "ln -s targets.fa ./target_file.fasta && hybpiper assemble --readfiles R1.fq.gz R2.fq.gz "
        "--targetfile_dna target_file.fasta --diamond --cpu 8 --prefix S1 && "
        "tar -cvf /work/hybpiper/hybpiper_archive.tar --directory=S1 ."
    )


def test_wrapper_declared_environment_conflicts_remain_explicit() -> None:
    magicblast = _node_classes()["magicblast"]
    assert "samtools==1.18" in magicblast.PACKAGE_CONSTRAINTS
    assert _node_classes()["taxonkit_name2taxid"].PACKAGE_CONSTRAINTS == ("taxonkit==0.20.0",)
