"""Compact contract tests for the five focused metagenomics operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.builtin.checkm_family.checkm import CheckMNode
from bionodulo.nodes.builtin.metagenomics_family.bracken import BrackenNode
from bionodulo.nodes.builtin.metagenomics_family.kraken2 import Kraken2Node
from bionodulo.nodes.builtin.metagenomics_family.kraken2_build import FINAL_DATABASE_FILES, Kraken2BuildNode
from bionodulo.nodes.builtin.metagenomics_family.krona import KronaTaxonomyNode
from bionodulo.nodes.builtin.metagenomics_family.maxbin import MaxBinNode
from bionodulo.nodes.builtin.humann_family.humann import HUMAnNNode
from bionodulo.nodes.builtin.metaphlan_family.metaphlan import MetaPhlAnNode


ALL_NODES = (Kraken2Node, BrackenNode, MetaPhlAnNode, HUMAnNNode, KronaTaxonomyNode)

PINNED = {
    Kraken2Node: {
        "node_id": "kraken2",
        "version": "2.17.1",
        "tag": "v2.17.1",
        "commit": "5e2aa928d00b96d61f204d517437637863da1d8c",
        "package": "kraken2",
        "executable": "kraken2",
    },
    BrackenNode: {
        "node_id": "bracken",
        "version": "3.1",
        "tag": "v3.1",
        "commit": "cfeac04b6445c44c3825866683a6fdd18746cb58",
        "package": "bracken",
        "executable": "bracken",
    },
    MetaPhlAnNode: {
        "node_id": "metaphlan",
        "version": "4.2.4",
        "tag": "4.2.4",
        "commit": "b2293b0d319237c2312e628e5ab2a13095df7e3b",
        "package": "metaphlan",
        "executable": "metaphlan",
    },
    HUMAnNNode: {
        "node_id": "humann",
        "version": "3.9",
        "tag": "v3.9",
        "commit": "9c6dfef873837c0ed281e1093718769d1aea98c9",
        "package": "humann",
        "extra_packages": ("python",),
        "executable": "humann",
    },
    KronaTaxonomyNode: {
        "node_id": "krona",
        "version": "2.8.1",
        "tag": "v2.8.1",
        "commit": "106dedb36b6c80445c6bacbd53d745a2388de273",
        "package": "krona",
        "executable": "ktImportTaxonomy",
    },
}

RUN_INPUTS: dict[type[Any], dict[str, Any]] = {
    Kraken2Node: {"db": "/db/kraken2", "reads": ["reads.fastq.gz"]},
    BrackenNode: {"report": "sample.kreport", "db": "/db/bracken"},
    MetaPhlAnNode: {
        "reads": ["reads.fastq.gz"],
        "database": "/db/metaphlan",
        "index": "mpa_vJun23_CHOCOPhlAnSGB_202403",
    },
    HUMAnNNode: {
        "input": "reads.fastq.gz",
        "taxonomic_profile": "profile.tsv",
        "nucleotide_database": "/db/chocophlan",
        "protein_database": "/db/uniref90",
    },
    KronaTaxonomyNode: {"classification": "classification.kraken", "taxonomy": "/db/krona-taxonomy"},
}


class _FakeContext:
    def __init__(self, node_dir: Path, *, returncode: int = 0, create_outputs: bool = True) -> None:
        self.node_dir = node_dir
        self.returncode = returncode
        self.create_outputs = create_outputs
        self.calls: list[tuple[list[str], dict[str, Any]]] = []

    @staticmethod
    def _touch(path: str | Path) -> None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("synthetic\n", encoding="ascii")

    async def run_command(self, command: list[str], **kwargs: Any) -> dict[str, Any]:
        self.calls.append((command, kwargs))
        if self.returncode == 0 and self.create_outputs:
            executable = command[0]
            if executable == "kraken2":
                self._touch(command[command.index("--output") + 1])
                self._touch(command[command.index("--report") + 1])
            elif executable == "bracken":
                self._touch(command[command.index("-o") + 1])
                self._touch(command[command.index("-w") + 1])
            elif executable == "metaphlan":
                self._touch(command[command.index("-o") + 1])
                self._touch(command[command.index("--mapout") + 1])
            elif executable == "humann":
                output = Path(command[command.index("--output") + 1])
                output.mkdir(parents=True, exist_ok=True)
                for name in ("humann_genefamilies.tsv", "humann_pathabundance.tsv", "humann_pathcoverage.tsv"):
                    self._touch(output / name)
                self._touch(command[command.index("--o-log") + 1])
            elif executable == "ktImportTaxonomy":
                self._touch(command[command.index("-o") + 1])
        return {
            "returncode": self.returncode,
            "stdout": "",
            "stderr": "synthetic failure" if self.returncode else "",
        }


@pytest.mark.parametrize(("node", "expected"), list(PINNED.items()))
def test_source_and_package_contracts_are_exactly_pinned(
    node: type[Any],
    expected: dict[str, str],
) -> None:
    assert node.NODE_ID == expected["node_id"]
    assert node.VERSION == expected["version"]
    assert node.BIOCONDA_VERSION == expected["version"]
    assert node.BIOCONDA_CONSTRAINT == f"{expected['package']}={expected['version']}"
    assert node.UPSTREAM_TAG == expected["tag"]
    assert node.GIT_COMMIT == expected["commit"]
    # `extra_packages` covers a node that must pin a transitive dependency its
    # own conda package under-declares (humann/python -- see PACKAGE_MIN_VERSIONS).
    assert node.REQUIRED_CONDA_PACKAGES == [
        expected["package"],
        *expected.get("extra_packages", ()),
    ]
    assert node.REQUIRED_EXECUTABLES == [expected["executable"]]
    assert node.DOCUMENTATION_URL.startswith("https://github.com/")
    assert node.UPSTREAM_SOURCE
    assert node.EXIT_SEMANTICS
    assert node.SHELL is False


def test_stable_ids_are_grouped_with_their_tool_families() -> None:
    assert {node.NODE_ID for node in ALL_NODES} == {"kraken2", "bracken", "metaphlan", "humann", "krona"}
    assert HUMAnNNode.__module__ == "bionodulo.nodes.builtin.humann_family.humann"
    assert MetaPhlAnNode.__module__ == "bionodulo.nodes.builtin.metaphlan_family.metaphlan"
    assert all(
        node.__module__.startswith("bionodulo.nodes.builtin.metagenomics_family.")
        for node in (Kraken2Node, BrackenNode, KronaTaxonomyNode)
    )


def test_database_and_cross_tool_inputs_are_explicit_ports() -> None:
    assert Kraken2Node.INPUT_TYPES()["required"]["db"][0] == "DIRECTORY"
    assert BrackenNode.INPUT_TYPES()["required"]["db"][0] == "DIRECTORY"
    assert MetaPhlAnNode.INPUT_TYPES()["required"]["database"][0] == "DIRECTORY"
    assert MetaPhlAnNode.INPUT_TYPES()["required"]["index"][0] == "STRING"

    humann_required = HUMAnNNode.INPUT_TYPES()["required"]
    assert humann_required["taxonomic_profile"][0] == "METAPHLAN_PROFILE"
    assert humann_required["nucleotide_database"][0] == "DIRECTORY"
    assert humann_required["protein_database"][0] == "DIRECTORY"
    assert KronaTaxonomyNode.INPUT_TYPES()["required"]["taxonomy"][0] == "DIRECTORY"


def test_kraken2_default_and_paired_argv_are_native_and_redirect_free() -> None:
    inputs = {
        "db": "/db/kraken",
        "reads": ["R1.fastq.gz", "R2.fastq.gz"],
        "paired": True,
        "quick": True,
        "use_names": True,
        "memory_mapping": True,
        "output": "/work/kraken2",
    }
    assert Kraken2Node.render_command(inputs) == [
        "kraken2",
        "--db",
        "/db/kraken",
        "--threads",
        "1",
        "--quick",
        "--confidence",
        "0.0",
        "--minimum-base-quality",
        "0",
        "--minimum-hit-groups",
        "2",
        "--use-names",
        "--memory-mapping",
        "--paired",
        "--gzip-compressed",
        "--output",
        "/work/kraken2/classification.kraken",
        "--report",
        "/work/kraken2/report.kreport",
        "R1.fastq.gz",
        "R2.fastq.gz",
    ]


def test_kraken2_emits_the_required_compression_switch_for_gzip_reads() -> None:
    command = Kraken2Node.render_command(
        {
            "db": "/db/kraken",
            "reads": ["R1.fastq.gz", "R2.fastq.gz"],
            "paired": True,
            "output": "/work/kraken2",
        }
    )
    assert "--gzip-compressed" in command
    assert command.index("--gzip-compressed") < command.index("--output")


def test_kraken2_rejects_mixed_compression_without_an_explicit_mode() -> None:
    inputs = {
        "db": "/db/kraken",
        "reads": ["R1.fastq.gz", "R2.fastq"],
        "paired": True,
    }
    assert "mixes compressed and uncompressed" in str(Kraken2Node.VALIDATE_INPUTS(inputs))


def test_kraken2_checks_the_materialized_database_bundle(tmp_path: Path) -> None:
    database = tmp_path / "kraken-db"
    database.mkdir()
    inputs = {"db": str(database), "reads": ["reads.fastq"]}
    with pytest.raises(ValueError, match="hash.k2d"):
        Kraken2Node.PREPARE_EXECUTION(inputs, [tmp_path / "out"])

    for name in Kraken2Node.DATABASE_FILES:
        (database / name).write_bytes(b"synthetic")
    Kraken2Node.PREPARE_EXECUTION(inputs, [tmp_path / "out"])


def test_bracken_argv_uses_the_database_and_writes_both_native_reports() -> None:
    assert BrackenNode.render_command(
        {
            "report": "sample.kreport",
            "db": "/db/bracken",
            "read_length": 150,
            "level": "G",
            "threshold": 25,
            "output": "/work/bracken",
        }
    ) == [
        "bracken",
        "-d",
        "/db/bracken",
        "-i",
        "sample.kreport",
        "-o",
        "/work/bracken/abundance.tsv",
        "-w",
        "/work/bracken/bracken.kreport",
        "-r",
        "150",
        "-l",
        "G",
        "-t",
        "25",
    ]
    assert BrackenNode.UPSTREAM_REPORTED_VERSION == "3.0.1"


def test_bracken_checks_the_materialized_read_length_distribution_sidecar(tmp_path: Path) -> None:
    database = tmp_path / "bracken-db"
    database.mkdir()
    inputs = {
        "report": "sample.kreport",
        "db": str(database),
        "read_length": 150,
    }

    with pytest.raises(ValueError, match="database150mers.kmer_distrib"):
        BrackenNode.PREPARE_EXECUTION(inputs, [tmp_path / "out"])

    sidecar = database / "database150mers.kmer_distrib"
    sidecar.write_text("synthetic\n", encoding="ascii")
    BrackenNode.PREPARE_EXECUTION(inputs, [tmp_path / "out"])

    sidecar.unlink()
    (database / "database100mers.kmer_distrib").write_text("wrong length\n", encoding="ascii")
    with pytest.raises(ValueError, match="database150mers.kmer_distrib"):
        BrackenNode.PREPARE_EXECUTION(inputs, [tmp_path / "out"])


def test_metaphlan_argv_pins_database_release_outputs_and_offline_mode() -> None:
    assert MetaPhlAnNode.render_command(
        {
            "reads": ["R1.fastq.gz", "R2.fastq.gz"],
            "database": "/db/metaphlan",
            "index": "mpa_vJun23_CHOCOPhlAnSGB_202403",
            "threads": 8,
            "minimum_mapq": 10,
            "minimum_alignment_length": 75,
            "ignore_eukaryotes": True,
            "output": "/work/metaphlan",
        }
    ) == [
        "metaphlan",
        "R1.fastq.gz,R2.fastq.gz",
        "--input_type",
        "fastq",
        "--db_dir",
        "/db/metaphlan",
        "--index",
        "mpa_vJun23_CHOCOPhlAnSGB_202403",
        "--mapout",
        "/work/metaphlan/mapout.bz2",
        "--nproc",
        "8",
        "--read_min_len",
        "70",
        "--min_mapq_val",
        "10",
        "--min_alignment_len",
        "75",
        "-t",
        "rel_ab",
        "--tax_lev",
        "a",
        "--stat",
        "tavg_g",
        "--stat_q",
        "0.2",
        "--perc_nonzero",
        "0.33",
        "--ignore_eukaryotes",
        "-o",
        "/work/metaphlan/profile.metaphlan.tsv",
        "--offline",
    ]


def test_metaphlan_checks_the_materialized_index_bundle(tmp_path: Path) -> None:
    database = tmp_path / "metaphlan-db"
    database.mkdir()
    index = "mpa_vJun23_CHOCOPhlAnSGB_202403"
    inputs = {
        "reads": ["reads.fastq"],
        "database": str(database),
        "index": index,
    }
    with pytest.raises(ValueError, match=rf"{index}\.1\.bt2l"):
        MetaPhlAnNode.PREPARE_EXECUTION(inputs, [tmp_path / "out"])

    for suffix in MetaPhlAnNode.DATABASE_INDEX_SUFFIXES:
        (database / f"{index}{suffix}").write_bytes(b"synthetic")
    (database / f"{index}.pkl").write_bytes(b"synthetic")
    MetaPhlAnNode.PREPARE_EXECUTION(inputs, [tmp_path / "out"])


def test_humann_argv_requires_upstream_taxonomy_and_both_reference_databases() -> None:
    assert HUMAnNNode.render_command(
        {
            "input": "reads.fastq.gz",
            "taxonomic_profile": "profile.tsv",
            "nucleotide_database": "/db/chocophlan",
            "protein_database": "/db/uniref90",
            "input_format": "fastq.gz",
            "search_mode": "uniref90",
            "remove_temp_output": True,
            "remove_stratified_output": True,
            "output": "/work/humann",
        }
    ) == [
        "humann",
        "--input",
        "reads.fastq.gz",
        "--output",
        "/work/humann/output",
        "--threads",
        "1",
        "--taxonomic-profile",
        "profile.tsv",
        "--nucleotide-database",
        "/db/chocophlan",
        "--protein-database",
        "/db/uniref90",
        "--prescreen-threshold",
        "0.01",
        "--memory-use",
        "minimum",
        "--translated-alignment",
        "diamond",
        "--output-basename",
        "humann",
        "--output-format",
        "tsv",
        "--output-max-decimals",
        "10",
        "--o-log",
        "/work/humann/humann.log",
        "--input-format",
        "fastq.gz",
        "--search-mode",
        "uniref90",
        "--remove-temp-output",
        "--remove-stratified-output",
    ]


def test_humann_checks_materialized_chocophlan_and_diamond_database_members(tmp_path: Path) -> None:
    nucleotide_database = tmp_path / "chocophlan"
    protein_database = tmp_path / "uniref"
    nucleotide_database.mkdir()
    protein_database.mkdir()
    inputs = {
        "input": "reads.fastq.gz",
        "taxonomic_profile": "profile.tsv",
        "nucleotide_database": str(nucleotide_database),
        "protein_database": str(protein_database),
    }

    with pytest.raises(ValueError, match="ChocoPhlAn nucleotide database is empty"):
        HUMAnNNode.PREPARE_EXECUTION(inputs, [tmp_path / "out"])

    (nucleotide_database / "g__Example.s__Species.centroids.v201901_v31.ffn.gz").write_bytes(b"synthetic")
    with pytest.raises(ValueError, match="UniRef protein database is empty"):
        HUMAnNNode.PREPARE_EXECUTION(inputs, [tmp_path / "out"])

    (protein_database / "uniref90_201901b.udb").write_bytes(b"synthetic")
    with pytest.raises(ValueError, match=r"\*\.dmnd"):
        HUMAnNNode.PREPARE_EXECUTION(inputs, [tmp_path / "out"])

    (protein_database / "uniref90_201901b.dmnd").write_bytes(b"synthetic")
    HUMAnNNode.PREPARE_EXECUTION(inputs, [tmp_path / "out"])


def test_humann_rejects_wrong_release_and_nonsequence_chocophlan_members(tmp_path: Path) -> None:
    nucleotide_database = tmp_path / "chocophlan"
    protein_database = tmp_path / "uniref"
    nucleotide_database.mkdir()
    protein_database.mkdir()
    inputs = {
        "input": "reads.fastq.gz",
        "taxonomic_profile": "profile.tsv",
        "nucleotide_database": str(nucleotide_database),
        "protein_database": str(protein_database),
    }
    (nucleotide_database / "g__Example.s__Species.centroids.v201901_v31.1.bt2").write_bytes(b"index")
    (protein_database / "uniref90_201901b.dmnd").write_bytes(b"synthetic")

    with pytest.raises(ValueError, match="non-pangenome sequence member"):
        HUMAnNNode.PREPARE_EXECUTION(inputs, [tmp_path / "out"])

    (nucleotide_database / "g__Example.s__Species.centroids.v201901_v31.1.bt2").unlink()
    (nucleotide_database / "g__Example.s__Species.centroids.v202101_v31.ffn.gz").write_bytes(b"wrong")
    with pytest.raises(ValueError, match="v201901_v31"):
        HUMAnNNode.PREPARE_EXECUTION(inputs, [tmp_path / "out"])


@pytest.mark.parametrize(
    ("aligner", "database_member"),
    [
        ("usearch", "uniref90_201901b.udb"),
        ("rapsearch", "uniref90_201901b.info"),
    ],
)
def test_humann_selects_the_native_translated_database_format(
    tmp_path: Path,
    aligner: str,
    database_member: str,
) -> None:
    nucleotide_database = tmp_path / "chocophlan"
    protein_database = tmp_path / "uniref"
    nucleotide_database.mkdir()
    protein_database.mkdir()
    (nucleotide_database / "g__Example.s__Species.centroids.v201901_v31.ffn.gz").write_bytes(b"synthetic")
    (protein_database / database_member).write_bytes(b"synthetic")
    inputs = {
        "input": "reads.fastq.gz",
        "taxonomic_profile": "profile.tsv",
        "nucleotide_database": str(nucleotide_database),
        "protein_database": str(protein_database),
        "translated_alignment": aligner,
    }

    if aligner == "rapsearch":
        with pytest.raises(ValueError, match="basename and its .info sidecar"):
            HUMAnNNode.PREPARE_EXECUTION(inputs, [tmp_path / "out"])
        (protein_database / "uniref90_201901b").write_bytes(b"synthetic")

    HUMAnNNode.PREPARE_EXECUTION(inputs, [tmp_path / "out"])


def test_krona_argv_supplies_the_required_taxonomy_database() -> None:
    assert KronaTaxonomyNode.render_command(
        {
            "classification": "classification.kraken",
            "taxonomy": "/db/krona-taxonomy",
            "output": "/work/krona",
        }
    ) == [
        "ktImportTaxonomy",
        "-q",
        "2",
        "-t",
        "3",
        "-tax",
        "/db/krona-taxonomy",
        "-o",
        "/work/krona/krona.html",
        "classification.kraken",
    ]


def test_krona_checks_the_materialized_taxonomy_sidecar(tmp_path: Path) -> None:
    taxonomy = tmp_path / "krona-taxonomy"
    taxonomy.mkdir()
    inputs = {"classification": "classification.kraken", "taxonomy": str(taxonomy)}

    with pytest.raises(ValueError, match="taxonomy.tab"):
        KronaTaxonomyNode.PREPARE_EXECUTION(inputs, [tmp_path / "out"])

    taxonomy_tab = taxonomy / "taxonomy.tab"
    taxonomy_tab.touch()
    with pytest.raises(ValueError, match="non-empty"):
        KronaTaxonomyNode.PREPARE_EXECUTION(inputs, [tmp_path / "out"])

    taxonomy_tab.write_text("1\t0\t1\tno rank\troot\n", encoding="ascii")
    KronaTaxonomyNode.PREPARE_EXECUTION(inputs, [tmp_path / "out"])


def test_database_and_binning_nodes_have_exact_source_pins() -> None:
    assert Kraken2BuildNode.VERSION == "2.17.1"
    assert Kraken2BuildNode.GIT_COMMIT == "5e2aa928d00b96d61f204d517437637863da1d8c"
    assert MaxBinNode.VERSION == "2.2.7"
    assert MaxBinNode.SOURCE_SHA256 == "cb6429e857280c2b75823c8cd55058ed169c93bc707a46bde0c4383f2bffe09e"
    assert CheckMNode.VERSION == "1.2.5"
    assert CheckMNode.GIT_COMMIT == "acb42ba20b29661054933d0df44a78fd28fd0bcc"
    assert CheckMNode.__module__ == "bionodulo.nodes.builtin.checkm_family.checkm"
    assert all(
        node.__module__.startswith("bionodulo.nodes.builtin.metagenomics_family.")
        for node in (Kraken2BuildNode, MaxBinNode)
    )


def test_kraken2_build_uses_an_explicit_prior_database_and_final_sidecars(tmp_path: Path) -> None:
    prior = tmp_path / "prior"
    (prior / "taxonomy").mkdir(parents=True)
    (prior / "taxonomy" / "nodes.dmp").write_text("synthetic\n", encoding="ascii")
    outputs = Kraken2BuildNode.PLAN_OUTPUTS({"operation": "build"}, tmp_path / "run")
    inputs = {
        "operation": "build",
        "database": str(prior),
        "threads": 8,
        "kmer_len": 35,
        "minimizer_len": 31,
        "minimizer_spaces": 7,
        "load_factor": 0.7,
        "output": str(tmp_path / "run" / "kraken2_build"),
    }
    Kraken2BuildNode.PREPARE_EXECUTION(inputs, outputs)
    assert (outputs[0] / "taxonomy" / "nodes.dmp").is_file()
    assert Kraken2BuildNode.render_command(inputs) == [
        "kraken2-build",
        "--build",
        "--db",
        str(tmp_path / "run" / "kraken2_build" / "database"),
        "--threads",
        "8",
        "--kmer-len",
        "35",
        "--minimizer-len",
        "31",
        "--minimizer-spaces",
        "7",
        "--load-factor",
        "0.7",
    ]
    assert FINAL_DATABASE_FILES == ("hash.k2d", "opts.k2d", "taxo.k2d")


def test_maxbin_exposes_documented_prefix_artifacts_and_list_inputs(tmp_path: Path) -> None:
    outputs = MaxBinNode.PLAN_OUTPUTS({}, tmp_path)
    inputs = {
        "contigs": "contigs.fa",
        "reads": ["r1.fastq", "r2.fastq"],
        "abundance_files": [],
        "threads": 4,
        "prob_threshold": 0.8,
        "markerset": "40",
        "output": str(tmp_path / "maxbin"),
    }
    MaxBinNode.PREPARE_EXECUTION(inputs, outputs)
    assert MaxBinNode.render_command(inputs) == [
        "run_MaxBin.pl",
        "-contig",
        "contigs.fa",
        "-out",
        str(tmp_path / "maxbin" / "maxbin"),
        "-reads_list",
        str(tmp_path / "maxbin" / "reads.list"),
        "-thread",
        "4",
        "-prob_threshold",
        "0.8",
        "-markerset",
        "40",
    ]
    assert [path.name for path in outputs[1:]] == [
        "maxbin.summary",
        "maxbin.log",
        "maxbin.marker",
        "maxbin.noclass",
        "maxbin.tooshort",
        "maxbin.marker_of_each_gene.tar.gz",
    ]


def test_checkm_lineage_workflow_stages_reference_data_and_report() -> None:
    assert CheckMNode.render_command(
        {
            "bins": "/inputs/bins",
            "checkm_data": "/refs/checkm",
            "extension": "fa",
            "threads": 8,
            "pplacer_threads": 2,
            "reduced_tree": True,
            "output": "/work/checkm",
        }
    ) == [
        "env",
        "CHECKM_DATA_PATH=/refs/checkm",
        "checkm",
        "lineage_wf",
        "-x",
        "fa",
        "-t",
        "8",
        "--pplacer_threads",
        "2",
        "--aai_strain",
        "0.9",
        "--reduced_tree",
        "--tab_table",
        "-f",
        "/work/checkm/quality_report.tsv",
        "/inputs/bins",
        "/work/checkm/analysis",
    ]


@pytest.mark.parametrize(
    ("node", "inputs", "message"),
    [
        (Kraken2Node, {"db": "/db", "reads": ["R1", "R2", "R3"], "paired": True}, "positive even"),
        (Kraken2Node, {"db": "/db", "reads": ["R1"], "confidence": 1.1}, "at most 1"),
        (BrackenNode, {"report": "report", "db": "/db", "read_length": 0}, "at least 1"),
        (BrackenNode, {"report": "report", "db": "/db", "level": "species"}, "numbered sub-rank"),
        (
            MetaPhlAnNode,
            {"reads": ["reads.fastq"], "database": "/db", "index": "latest"},
            "network access",
        ),
        (
            MetaPhlAnNode,
            {"reads": ["reads,one.fastq"], "database": "/db", "index": "mpa_release"},
            "cannot contain commas",
        ),
        (
            HUMAnNNode,
            {"input": "reads.fastq", "nucleotide_database": "/nuc", "protein_database": "/protein"},
            "taxonomic_profile",
        ),
        (
            HUMAnNNode,
            {
                "input": "reads.fastq",
                "taxonomic_profile": "profile.tsv",
                "nucleotide_database": "/nuc",
                "protein_database": "/protein",
                "input_format": "sam",
            },
            "must be one of",
        ),
        (
            KronaTaxonomyNode,
            {"classification": "classification.kraken", "taxonomy": "/tax", "query_column": 3},
            "different columns",
        ),
    ],
)
def test_invalid_contract_values_fail_before_rendering(
    node: type[Any],
    inputs: dict[str, Any],
    message: str,
) -> None:
    validation = node.VALIDATE_INPUTS(inputs)
    assert validation is not True
    assert message in str(validation)
    with pytest.raises(ValueError, match=message):
        node.render_command(inputs)


@pytest.mark.parametrize(
    ("node", "inputs", "relative_outputs"),
    [
        (Kraken2Node, RUN_INPUTS[Kraken2Node], ["kraken2/classification.kraken", "kraken2/report.kreport"]),
        (BrackenNode, RUN_INPUTS[BrackenNode], ["bracken/abundance.tsv", "bracken/bracken.kreport"]),
        (
            MetaPhlAnNode,
            RUN_INPUTS[MetaPhlAnNode],
            ["metaphlan/profile.metaphlan.tsv", "metaphlan/mapout.bz2"],
        ),
        (
            HUMAnNNode,
            RUN_INPUTS[HUMAnNNode],
            [
                "humann/output",
                "humann/output/humann_genefamilies.tsv",
                "humann/output/humann_pathabundance.tsv",
                "humann/output/humann_pathcoverage.tsv",
                "humann/humann.log",
            ],
        ),
        (KronaTaxonomyNode, RUN_INPUTS[KronaTaxonomyNode], ["krona/krona.html"]),
    ],
)
def test_planned_outputs_use_stable_native_filenames(
    tmp_path: Path,
    node: type[Any],
    inputs: dict[str, Any],
    relative_outputs: list[str],
) -> None:
    assert node.PLAN_OUTPUTS(inputs, tmp_path) == [tmp_path / relative for relative in relative_outputs]


@pytest.mark.asyncio
@pytest.mark.parametrize("node", ALL_NODES)
async def test_synthetic_execution_returns_only_verified_native_outputs(
    tmp_path: Path,
    node: type[Any],
) -> None:
    context = _FakeContext(tmp_path)
    expected = tuple(str(path) for path in node.PLAN_OUTPUTS(RUN_INPUTS[node], tmp_path))
    result = await node().run(context=context, **RUN_INPUTS[node])
    assert result == expected
    assert len(context.calls) == 1
    assert isinstance(context.calls[0][0], list)


@pytest.mark.asyncio
@pytest.mark.parametrize("node", ALL_NODES)
async def test_nonzero_native_exit_status_is_propagated(
    tmp_path: Path,
    node: type[Any],
) -> None:
    with pytest.raises(RuntimeError, match="exit 64"):
        await node().run(context=_FakeContext(tmp_path, returncode=64), **RUN_INPUTS[node])


@pytest.mark.asyncio
async def test_zero_exit_without_outputs_still_fails_closed_for_bracken(tmp_path: Path) -> None:
    context = _FakeContext(tmp_path, create_outputs=False)
    with pytest.raises(RuntimeError, match="did not create expected output"):
        await BrackenNode().run(context=context, **RUN_INPUTS[BrackenNode])
