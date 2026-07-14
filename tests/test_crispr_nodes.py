from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace

import pytest

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE, PACKAGE_MIN_VERSIONS
from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def _context(tmp_path: Path, name: str) -> SimpleNamespace:
    node_dir = tmp_path / name
    node_dir.mkdir()
    return SimpleNamespace(node_dir=node_dir)


def test_crispresso2_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["crispresso2"]
    assert node_info["display_name"] == "CRISPRESSO2"
    assert node_info["category"] == "crispr"
    assert node_info["description"].startswith("Analyze CRISPR editing")
    assert node_info["output"] == ["HTML_REPORT", "DIRECTORY"]
    assert node_info["output_name"] == ["report", "results_dir"]
    assert node_info["required_executables"] == ["CRISPResso"]
    assert node_info["required_conda_packages"] == ["crispresso2"]
    assert "crispresso" in node_info["search_aliases"]
    assert "crispr" in node_info["search_aliases"]
    assert "editing analysis" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"r1", "amplicon_seq", "name"}
    assert set(inputs["optional"]) == {"r2", "guide_seq", "quant_window_center", "quant_window_size"}


def test_crispresso2_renders_paired_end_command_with_quantification_options() -> None:
    node_class = _node_class("crispresso2")

    cmd = node_class.render_command({
        "r1": "sample_R1.fastq.gz",
        "r2": "sample_R2.fastq.gz",
        "amplicon_seq": "ACGTACGTACGT",
        "name": "edited_locus",
        "guide_seq": "GATTACAGATTACAGATTAC",
        "quant_window_center": -3,
        "quant_window_size": 5,
        "output": "/tmp/run/crispresso2",
    })

    assert cmd == [
        "CRISPResso",
        "-r1",
        "sample_R1.fastq.gz",
        "-a",
        "ACGTACGTACGT",
        "-o",
        "/tmp/run/crispresso2",
        "--name",
        "edited_locus",
        "-r2",
        "sample_R2.fastq.gz",
        "-g",
        "GATTACAGATTACAGATTAC",
        "-wc",
        "-3",
        "-w",
        "5",
    ]


def test_crispresso2_omits_empty_optional_flags() -> None:
    node_class = _node_class("crispresso2")

    cmd = node_class.render_command({
        "r1": "sample_R1.fastq.gz",
        "amplicon_seq": "ACGTACGTACGT",
        "name": "crispresso_run",
        "r2": "",
        "guide_seq": "",
        "quant_window_center": 0,
        "quant_window_size": 0,
        "output": "/tmp/run/crispresso2",
    })

    assert "-r2" not in cmd
    assert "-g" not in cmd
    assert "-qc" not in cmd
    assert "-w" not in cmd
    assert cmd == [
        "CRISPResso",
        "-r1",
        "sample_R1.fastq.gz",
        "-a",
        "ACGTACGTACGT",
        "-o",
        "/tmp/run/crispresso2",
        "--name",
        "crispresso_run",
    ]


def test_crispresso2_plans_outputs() -> None:
    node_class = _node_class("crispresso2")

    outputs = node_class.PLAN_OUTPUTS({"name": "edited_locus"}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/crispresso2/CRISPResso_on_edited_locus.html",
        "/tmp/run/crispresso2/CRISPResso_on_edited_locus",
    ]


def test_crispresso2_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["CRISPResso"] == "crispresso2"
    assert PACKAGE_MIN_VERSIONS["crispresso2"] == ">=2.3.2"


def test_mageck_count_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["mageck_count"]
    assert node_info["display_name"] == "MAGeCK Count"
    assert node_info["category"] == "crispr"
    assert node_info["description"].startswith("Count sgRNA reads")
    assert node_info["output"] == ["TSV", "TSV"]
    assert node_info["output_name"] == ["count_table", "normalized_counts"]
    assert node_info["required_executables"] == ["mageck"]
    assert node_info["required_conda_packages"] == ["mageck"]
    assert "crispr screen" in node_info["search_aliases"]
    assert "sgrna" in node_info["search_aliases"]
    assert "pooled screen" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"library_file", "fastq_files", "output_prefix"}
    assert set(inputs["optional"]) == {"sample_labels", "day0_label"}
    assert _node_class("mageck_count").INPUT_TYPES()["required"]["fastq_files"][0] == "FASTQ_LIST"


def test_mageck_count_renders_fastq_count_command_with_labels() -> None:
    node_class = _node_class("mageck_count")

    cmd = node_class.render_command({
        "library_file": "library.tsv",
        "fastq_files": ["control.fastq.gz", "treated.fastq.gz"],
        "output_prefix": "screen",
        "sample_labels": "control,treated",
        "day0_label": "control",
        "output": "/tmp/run/mageck_count",
    })

    assert cmd == [
        "mageck",
        "count",
        "-l",
        "library.tsv",
        "-n",
        "/tmp/run/mageck_count/screen",
        "--fastq",
        "control.fastq.gz",
        "treated.fastq.gz",
        "--sample-label",
        "control,treated",
        "--day0-label",
        "control",
    ]


def test_mageck_count_omits_empty_optional_flags_and_accepts_single_fastq() -> None:
    node_class = _node_class("mageck_count")

    cmd = node_class.render_command({
        "library_file": "library.tsv",
        "fastq_files": "control.fastq.gz",
        "output_prefix": "screen",
        "sample_labels": "",
        "day0_label": "",
        "output": "/tmp/run/mageck_count",
    })

    assert "--sample-label" not in cmd
    assert "--day0-label" not in cmd
    assert cmd == [
        "mageck",
        "count",
        "-l",
        "library.tsv",
        "-n",
        "/tmp/run/mageck_count/screen",
        "--fastq",
        "control.fastq.gz",
    ]


def test_mageck_count_plans_outputs() -> None:
    node_class = _node_class("mageck_count")

    outputs = node_class.PLAN_OUTPUTS({"output_prefix": "screen"}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/mageck_count/screen.count.txt",
        "/tmp/run/mageck_count/screen.count_normalized.txt",
    ]


def test_mageck_test_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["mageck_test"]
    assert node_info["display_name"] == "MAGeCK Test"
    assert node_info["category"] == "crispr"
    assert node_info["description"].startswith("Identify essential genes")
    assert node_info["output"] == ["TSV", "TSV"]
    assert node_info["output_name"] == ["gene_summary", "sgrna_summary"]
    assert node_info["required_executables"] == ["mageck"]
    assert node_info["required_conda_packages"] == ["mageck"]
    assert "essential genes" in node_info["search_aliases"]
    assert "gene ranking" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"count_table", "treatment_labels", "control_labels", "output_prefix"}
    assert set(inputs["optional"]) == {"norm_method", "adjust_method", "sort_criteria"}


def test_mageck_test_renders_ranking_command_with_analysis_options() -> None:
    node_class = _node_class("mageck_test")

    cmd = node_class.render_command({
        "count_table": "screen.count.txt",
        "treatment_labels": "treated_a,treated_b",
        "control_labels": "control_a,control_b",
        "output_prefix": "screen_test",
        "norm_method": "median",
        "adjust_method": "fdr",
        "sort_criteria": "neg",
        "output": "/tmp/run/mageck_test",
    })

    assert cmd == [
        "mageck",
        "test",
        "-k",
        "screen.count.txt",
        "-t",
        "treated_a,treated_b",
        "-c",
        "control_a,control_b",
        "-n",
        "/tmp/run/mageck_test/screen_test",
        "--norm-method",
        "median",
        "--adjust-method",
        "fdr",
        "--sort-criteria",
        "neg",
    ]


def test_mageck_test_omits_empty_optional_flags() -> None:
    node_class = _node_class("mageck_test")

    cmd = node_class.render_command({
        "count_table": "screen.count.txt",
        "treatment_labels": "treated",
        "control_labels": "control",
        "output_prefix": "screen_test",
        "norm_method": "",
        "adjust_method": "",
        "sort_criteria": "",
        "output": "/tmp/run/mageck_test",
    })

    assert "--norm-method" not in cmd
    assert "--adjust-method" not in cmd
    assert "--sort-criteria" not in cmd
    assert cmd == [
        "mageck",
        "test",
        "-k",
        "screen.count.txt",
        "-t",
        "treated",
        "-c",
        "control",
        "-n",
        "/tmp/run/mageck_test/screen_test",
    ]


def test_mageck_test_plans_outputs() -> None:
    node_class = _node_class("mageck_test")

    outputs = node_class.PLAN_OUTPUTS({"output_prefix": "screen_test"}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/mageck_test/screen_test.gene_summary.txt",
        "/tmp/run/mageck_test/screen_test.sgrna_summary.txt",
    ]


def test_mageck_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["mageck"] == "mageck"
    assert PACKAGE_MIN_VERSIONS["mageck"] == ">=0.5.9"


def test_cas_offinder_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["cas_offinder"]
    assert node_info["display_name"] == "Cas-OFFinder"
    assert node_info["category"] == "crispr"
    assert node_info["description"].startswith("Fast off-target detection")
    assert node_info["output"] == ["TSV"]
    assert node_info["output_name"] == ["offtarget_sites"]
    assert node_info["required_executables"] == ["cas-offinder"]
    assert node_info["required_conda_packages"] == ["cas-offinder"]
    assert "off target" in node_info["search_aliases"]
    assert "guide rna" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"guide_seq", "genome_fasta", "mismatches"}
    assert set(inputs["optional"]) == {"pam_sequence", "device"}


def test_cas_offinder_writes_input_file_and_renders_cpu_command(tmp_path: Path) -> None:
    node_class = _node_class("cas_offinder")
    output_dir = tmp_path / "cas_offinder"

    cmd = node_class.render_command({
        "guide_seq": "GGCCGACCTGTCGCTGACGC",
        "genome_fasta": "/data/genomes/hg38",
        "mismatches": 3,
        "pam_sequence": "NNN",
        "device": "C",
        "output": str(output_dir),
    })

    input_file = output_dir / "cas_offinder_input.txt"
    assert input_file.read_text(encoding="utf-8") == (
        "/data/genomes/hg38\n"
        "NNNNNNNNNNNNNNNNNNNNNNN\n"
        "GGCCGACCTGTCGCTGACGCNNN 3\n"
    )
    assert cmd == [
        "cas-offinder",
        str(input_file),
        "C",
        str(output_dir / "offtarget_sites.txt"),
    ]


def test_cas_offinder_plans_outputs() -> None:
    node_class = _node_class("cas_offinder")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/cas_offinder/offtarget_sites.txt",
    ]


def test_cas_offinder_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["cas-offinder"] == "cas-offinder"
    assert PACKAGE_MIN_VERSIONS["cas-offinder"] == ">=2.4.1"


def test_guide_rna_design_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["guide_rna_design"]
    assert node_info["display_name"] == "Guide RNA Design"
    assert node_info["category"] == "crispr"
    assert node_info["description"].startswith("Design guide RNAs")
    assert node_info["output"] == ["TSV", "TSV"]
    assert node_info["output_name"] == ["guides", "off_targets"]
    assert node_info["required_executables"] == []
    assert node_info["required_conda_packages"] == ["biopython"]
    assert "guide rna" in node_info["search_aliases"]
    assert "cas9" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"target", "pam", "genome"}
    assert set(inputs["optional"]) == {"guide_length", "max_guides", "mismatches"}
    assert inputs["required"]["genome"][0] == "FASTA"


def test_guide_rna_design_plans_outputs() -> None:
    node_class = _node_class("guide_rna_design")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/guide_rna_design/guides.tsv",
        "/tmp/run/guide_rna_design/off_targets.tsv",
    ]


def test_guide_rna_design_validates_pam_and_guide_length() -> None:
    node_class = _node_class("guide_rna_design")

    assert node_class.VALIDATE_INPUTS({
        "target": "chr1",
        "pam": "NGG",
        "genome": "genome.fa",
        "guide_length": 0,
    }) == "guide_length must be greater than zero"
    assert node_class.VALIDATE_INPUTS({
        "target": "chr1",
        "pam": "NGR",
        "genome": "genome.fa",
    }) == "pam may only contain A, C, G, T, or N"


@pytest.mark.asyncio
async def test_guide_rna_design_finds_guides_and_candidate_off_targets(tmp_path: Path) -> None:
    genome = tmp_path / "mini.fa"
    genome.write_text(
        ">chr1\n"
        "TTTTACGTACGTACGTACGTACGTNGGCCCCACGTACGTACGTACGTACGTAGGTTTT\n"
        ">chr2\n"
        "AAAACGTACGTACGTACGTACGTAGGAAAAACGTACGTACGTACGTACGTGGGAAAA\n",
        encoding="utf-8",
    )

    result = await _node_class("guide_rna_design")().run(
        target="chr1:5-27",
        pam="NGG",
        genome=str(genome),
        guide_length=20,
        max_guides=5,
        mismatches=1,
        context=_context(tmp_path, "guide-design"),
    )

    guides_path = Path(result[0])
    off_targets_path = Path(result[1])
    assert guides_path.name == "guides.tsv"
    assert off_targets_path.name == "off_targets.tsv"

    with guides_path.open(newline="", encoding="utf-8") as fh:
        guides = list(csv.DictReader(fh, delimiter="\t"))
    assert guides == [
        {
            "guide_id": "guide_1",
            "sequence": "ACGTACGTACGTACGTACGT",
            "pam": "NGG",
            "contig": "chr1",
            "start": "5",
            "end": "27",
            "strand": "+",
            "gc_content": "50.00",
            "target": "chr1:5-27",
            "off_target_count": "3",
        },
    ]

    with off_targets_path.open(newline="", encoding="utf-8") as fh:
        off_targets = list(csv.DictReader(fh, delimiter="\t"))
    assert off_targets == [
        {
            "guide_id": "guide_1",
            "sequence": "ACGTACGTACGTACGTACGT",
            "contig": "chr1",
            "start": "32",
            "end": "54",
            "strand": "+",
            "pam": "AGG",
            "mismatches": "0",
        },
        {
            "guide_id": "guide_1",
            "sequence": "ACGTACGTACGTACGTACGT",
            "contig": "chr2",
            "start": "4",
            "end": "26",
            "strand": "+",
            "pam": "AGG",
            "mismatches": "0",
        },
        {
            "guide_id": "guide_1",
            "sequence": "ACGTACGTACGTACGTACGT",
            "contig": "chr2",
            "start": "31",
            "end": "53",
            "strand": "+",
            "pam": "GGG",
            "mismatches": "0",
        },
    ]
