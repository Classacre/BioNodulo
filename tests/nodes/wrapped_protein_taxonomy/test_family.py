from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.registry import NodeRegistry


EXPECTED_OUTPUTS = {
    "beacon2_analyses": ("analyses_query_findings.json",),
    "beacon2_biosamples": ("biosamples_query_findings.json",),
    "beacon2_bracket": ("bracket_query_findings.json",),
    "beacon2_cnv": ("cnv_query_findings.json",),
    "beacon2_cohorts": ("cohorts_query_findings.json",),
    "beacon2_datasets": ("datasets_query_findings.json",),
    "beacon2_gene": ("gene_query_findings.json",),
    "beacon2_individuals": ("individuals_query_findings.json",),
    "beacon2_range": ("ranged_query_findings.json",),
    "beacon2_runs": ("runs_query_findings.json",),
    "beacon2_sequence": ("sequenced_query_findings.json",),
    "bg_diamond": ("blast_tabular.tsv",),
    "bg_diamond_makedb": ("database.dmnd",),
    "bg_diamond_view": ("blast_tabular.tsv",),
    "centrifuge": ("centrifuge_output.tsv", "centrifuge_report.tsv"),
    "diamond_align": ("matches.tsv",),
    "diamond_makedb": ("database.dmnd",),
    "hmmer_alimask": ("masked.sto",),
    "hmmer_hmmalign": ("alignment.sto",),
    "hmmer_hmmbuild": ("profile.hmm",),
    "hmmer_hmmconvert": ("converted.hmm3",),
    "hmmer_hmmemit": ("emitted.fasta",),
    "hmmer_hmmfetch": ("selected.hmm",),
    "hmmer_hmmscan": ("output.txt", "results.tblout", "domains.domtblout", "pfam.tblout"),
    "hmmer_hmmsearch": ("output.txt", "results.tblout", "domains.domtblout", "pfam.tblout"),
    "hmmer_jackhmmer": ("output.txt", "results.tblout", "domains.domtblout"),
    "hmmer_nhmmer": ("output.txt", "results.tblout", "dfam.tblout", "alignment_scores.txt"),
    "hmmer_nhmmscan": ("output.txt", "results.tblout", "dfam.tblout"),
    "hmmer_phmmer": ("output.txt", "results.tblout", "domains.domtblout", "pfam.tblout"),
    "kaiju": ("kaiju_taxonomy.tsv",),
    "kaiju2krona": ("kaiju_krona.tsv",),
    "kaiju2table": ("kaiju_summary.tsv",),
    "kaiju_add_taxon_names": ("kaiju_taxon_names.tsv",),
    "kaiju_merge_outputs": ("kaiju_merged_outputs.tsv",),
    "kraken": ("classification.kraken",),
    "kraken_filter": ("filtered_output.kraken",),
    "kraken_mpa_report": ("output_report.tsv",),
    "kraken_report": ("kraken_report.tsv",),
    "kraken_translate": ("translated.tsv",),
    "mmseqs2_easy_cluster": ("result_rep_seq.fasta", "result_all_seqs.fasta", "result_cluster.tsv"),
    "mmseqs2_easy_linclust_clustering": (
        "result_rep_seq.fasta",
        "result_all_seqs.fasta",
        "result_cluster.tsv",
    ),
    "mmseqs2_easy_linsearch": ("search_results.tsv",),
    "mmseqs2_easy_rbh": ("search_results.tsv",),
    "mmseqs2_easy_search": ("search_results",),
    "mmseqs2_easy_taxonomy": ("result_lca.tsv", "result_report.txt"),
    "mmseqs2_taxonomy_assignment": ("taxo_result.tsv", "taxo_result.txt", "taxo_result.html"),
}

def _node_classes() -> dict[str, type[BaseNode]]:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    classes = {node_id: registry.get(node_id) for node_id in EXPECTED_OUTPUTS}
    assert all(node_class is not None for node_class in classes.values())
    return classes


def _sample_value(name: str, spec: Any) -> Any:
    type_spec = spec[0]
    config = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
    if "default" in config and config["default"] not in ("", []):
        return copy.deepcopy(config["default"])
    if isinstance(type_spec, list):
        return copy.deepcopy(type_spec[0])
    if config.get("multiple") or config.get("list") or config.get("is_list"):
        return [f"/inputs/{name}.dat"]
    if type_spec == "BOOLEAN":
        return False
    if type_spec == "FLOAT":
        return 1.0
    if type_spec == "INT":
        return 1
    if type_spec in {
        "DIRECTORY",
        "DMND",
        "FASTA",
        "FASTQ",
        "FILE",
        "HMM",
        "JSON",
        "STOCKHOLM",
        "TSV",
        "TXT",
    }:
        return f"/inputs/{name}.dat"
    return "value"


def _sample_inputs(node_class: type[BaseNode]) -> dict[str, Any]:
    inputs = {name: _sample_value(name, spec) for name, spec in node_class.INPUT_TYPES().get("required", {}).items()}
    inputs["output"] = f"/work/{node_class.NODE_ID}"

    if node_class.NODE_ID == "centrifuge":
        inputs["unpaired_reads"] = ["/inputs/reads.fastq"]
    elif node_class.NODE_ID == "hmmer_alimask":
        inputs["ranges"] = ["1-10"]
    elif node_class.NODE_ID in {"hmmer_hmmscan", "hmmer_nhmmscan"}:
        inputs.update(
            hmmdb="/inputs/profiles.hmm",
            hmmdb_h3f="/inputs/profiles.hmm.h3f",
            hmmdb_h3i="/inputs/profiles.hmm.h3i",
            hmmdb_h3m="/inputs/profiles.hmm.h3m",
            hmmdb_h3p="/inputs/profiles.hmm.h3p",
        )
    elif node_class.NODE_ID in {"mmseqs2_easy_linsearch", "mmseqs2_easy_rbh"}:
        inputs.update(target_source="history", target_fasta="/inputs/target.fasta")
    elif node_class.NODE_ID in {"mmseqs2_easy_taxonomy", "mmseqs2_taxonomy_assignment"}:
        inputs["target_database"] = "/inputs/mmseqs-taxonomy"
    return inputs


def _command_text(command: Any) -> str:
    if isinstance(command, list):
        return " ".join(str(part) for part in command)
    return str(command)


def _planned_names(planned: Any) -> tuple[str, ...]:
    paths = planned.values() if isinstance(planned, dict) else planned
    return tuple(path.name for path in paths)


def test_exactly_46_stable_ids_are_registered() -> None:
    classes = _node_classes()
    assert set(classes) == set(EXPECTED_OUTPUTS)
    assert len(classes) == 46

    for node_id, node_class in classes.items():
        assert node_class.NODE_ID == node_id


@pytest.mark.parametrize("node_id", sorted(EXPECTED_OUTPUTS))
def test_each_contract_validates_renders_and_plans_declared_outputs(node_id: str, tmp_path: Path) -> None:
    node_class = _node_classes()[node_id]
    inputs = _sample_inputs(node_class)

    assert node_class.VALIDATE_INPUTS(inputs) is True
    command = _command_text(node_class.render_command(inputs))
    assert command
    assert any(executable in command for executable in node_class.REQUIRED_EXECUTABLES)
    assert _planned_names(node_class.PLAN_OUTPUTS(inputs, tmp_path)) == EXPECTED_OUTPUTS[node_id]


@pytest.mark.parametrize(
    ("prefixes", "commit", "constraint"),
    [
        (("diamond_", "bg_diamond"), "4c026eae71032c8e71fd1b647086296562892e4a", "diamond==2.2.2"),
        (("hmmer_",), "9acd8b6758a0ca5d21db6d167e0277484341929b", "hmmer==3.4"),
        (("mmseqs2_",), "b804fbe384e6f6c9fe96322ec0e92d48bccd0a42", "mmseqs2==17-b804f"),
        (("kaiju",), "55a0a14f454f86f09df6d424e39847d9ddc4ab7e", "kaiju==1.10.1"),
        (("kraken",), "e343539a12c3ad5afd38b3e30a7ed6db58c8d2c9", "kraken==1.1.1"),
        (("centrifuge",), "77115a711a17ad3d59d3c6f36346012b23fc461a", "centrifuge==1.0.4_beta"),
        (("beacon2_",), "8eb66da1f6f16fde92688ee6c500d2bcdc924a47", "beacon2-import==2.2.4"),
    ],
)
def test_tool_sources_and_package_versions_are_pinned(
    prefixes: tuple[str, ...],
    commit: str,
    constraint: str,
) -> None:
    selected = [
        node_class
        for node_id, node_class in _node_classes().items()
        if any(node_id.startswith(prefix) for prefix in prefixes)
    ]
    assert selected
    for node_class in selected:
        assert node_class.GIT_COMMIT == commit
        assert commit in node_class.SOURCE_URL
        assert node_class.PACKAGE_CONSTRAINT == constraint


def test_exact_tools_iuc_wrapper_commit_is_attached_to_galaxy_contracts() -> None:
    expected_commit = "8eb66da1f6f16fde92688ee6c500d2bcdc924a47"
    galaxy_ids = {
        node_id
        for node_id in EXPECTED_OUTPUTS
        if node_id.startswith(("beacon2_", "bg_diamond", "kaiju", "kraken", "mmseqs2_"))
    }
    for node_id in galaxy_ids:
        node_class = _node_classes()[node_id]
        assert node_class.GALAXY_WRAPPER_GIT_COMMIT == expected_commit
        assert expected_commit in node_class.GALAXY_WRAPPER_SOURCE_URL


@pytest.mark.parametrize(
    ("node_id", "inputs", "error"),
    [
        ("diamond_align", {"query": "q.fa", "database": "db.dmnd", "method": "tblastn"}, "method"),
        ("hmmer_nhmmscan", {"seqfile": "q.fa"}, "hmmdb"),
        (
            "hmmer_nhmmscan",
            {"hmmdb": "profiles.hmm", "seqfile": "q.fa"},
            "hmmdb_h3f",
        ),
        (
            "mmseqs2_easy_linsearch",
            {"query_fasta": "q.fa", "target_source": "history"},
            "target_fasta",
        ),
        (
            "mmseqs2_easy_rbh",
            {"query_fasta": "q.fa", "target_source": "cached"},
            "target_database",
        ),
        ("mmseqs2_easy_taxonomy", {"query_fasta": "q.fa", "database_type": "amino_acid_tax"}, "target_database"),
        ("kaiju", {"input_type": "single", "reference_database": "/db/kaiju"}, "reads"),
        (
            "kaiju",
            {"input_type": "paired", "reads": "single.fastq", "reference_database": "/db/kaiju"},
            "reads_1 and reads_2",
        ),
        ("centrifuge", {"db": "/db/centrifuge"}, "At least one"),
        ("kraken", {"input_type": "unsupported", "db": "/db/kraken", "input_sequences": "q.fa"}, "input_type"),
        ("beacon2_gene", {"collection": "genomicVariations", "geneId": "BRCA1"}, "database"),
    ],
)
def test_conditional_inputs_and_modes_fail_closed(node_id: str, inputs: dict[str, Any], error: str) -> None:
    validation = _node_classes()[node_id].VALIDATE_INPUTS(inputs)
    assert validation is not True
    assert error in str(validation)


def test_representative_commands_preserve_documented_argument_order() -> None:
    classes = _node_classes()

    diamond = classes["diamond_align"].render_command(
        {
            "query": "reads.fna",
            "database": "proteins.dmnd",
            "method": "blastx",
            "query_gencode": 11,
            "query_strand": "minus",
            "min_orf": 20,
            "output": "/work/diamond",
        }
    )
    assert diamond[:6] == ["diamond", "blastx", "--threads", "12", "--db", "proteins.dmnd"]
    assert diamond[-6:] == ["--query-gencode", "11", "--strand", "minus", "--min-orf", "20"]

    hmmer = _command_text(
        classes["hmmer_hmmsearch"].render_command(
            {"hmmfile": "profiles.hmm", "seqdb": "proteins.fa", "output": "/work/hmmer"}
        )
    )
    assert hmmer.startswith("hmmsearch -o /work/hmmer/output.txt --tblout /work/hmmer/results.tblout")
    assert hmmer.endswith("--cpu 2 --seed 42 profiles.hmm proteins.fa")

    linsearch = classes["mmseqs2_easy_linsearch"].render_command(
        {
            "query_fasta": "query.fa",
            "target_source": "cached",
            "target_database": "/db/mmseqs",
            "output": "/work/linsearch",
        }
    )
    assert "mmseqs easy-linsearch query.fa /db/mmseqs/database" in linsearch

    kaiju = classes["kaiju"].render_command(
        {
            "input_type": "paired",
            "reads_1": "R1.fastq",
            "reads_2": "R2.fastq",
            "reference_database": "/db/kaiju",
            "output": "/work/kaiju",
        }
    )
    assert kaiju[kaiju.index("-i") : kaiju.index("-i") + 4] == ["-i", "R1.fastq", "-j", "R2.fastq"]

    kraken = _command_text(
        classes["kraken_report"].render_command(
            {"kraken_output": "classification.kraken", "db": "/db/kraken", "output": "/work/kraken"}
        )
    )
    assert kraken == "kraken-report --db /db/kraken classification.kraken > /work/kraken/kraken_report.tsv"

    beacon = classes["beacon2_gene"].render_command(
        {
            "database": "beacon",
            "collection": "genomicVariations",
            "geneId": "BRCA1",
            "output": "/work/beacon",
        }
    )
    assert "beacon2-search" in beacon
    assert "--geneId BRCA1" in beacon
    assert beacon.endswith("> /work/beacon/gene_query_findings.json")


def test_beacon_records_the_missing_separate_upstream_package_commit() -> None:
    beacon = _node_classes()["beacon2_analyses"]
    assert beacon.UPSTREAM_PACKAGE_GIT_COMMIT == ""
    assert "no separate upstream package commit" in beacon.UPSTREAM_PACKAGE_PIN_STATUS
