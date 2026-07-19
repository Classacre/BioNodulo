from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.builtin.crispr_family.adapter import (
    CAS_OFFINDER_COMMIT,
    CRISPRESSO2_COMMIT,
    GUIDE_DESIGN_BASELINE_COMMIT,
    GUIDE_DESIGN_SOURCE_BLOB,
    MAGECK_COMMIT,
)
from bionodulo.nodes.builtin.crispr_family.cas_offinder import CasOffinderNode
from bionodulo.nodes.builtin.crispr_family.crispresso2 import CRISPRESSO2Node
from bionodulo.nodes.builtin.crispr_family.guide_rna_design import GuideRNADesignNode
from bionodulo.nodes.builtin.crispr_family.mageck_count import MAGeCKCountNode
from bionodulo.nodes.builtin.crispr_family.mageck_test import MAGeCKTestNode


EXTERNAL_NODES = (CasOffinderNode, CRISPRESSO2Node, MAGeCKCountNode, MAGeCKTestNode)


def test_crispr_family_has_five_stable_source_pinned_ids() -> None:
    assert {node.NODE_ID for node in (*EXTERNAL_NODES, GuideRNADesignNode)} == {
        "cas_offinder",
        "crispresso2",
        "guide_rna_design",
        "mageck_count",
        "mageck_test",
    }
    assert CasOffinderNode.GIT_COMMIT == CAS_OFFINDER_COMMIT
    assert CRISPRESSO2Node.GIT_COMMIT == CRISPRESSO2_COMMIT
    assert MAGeCKCountNode.GIT_COMMIT == MAGECK_COMMIT
    assert MAGeCKTestNode.GIT_COMMIT == MAGECK_COMMIT
    for node in EXTERNAL_NODES:
        assert node.UPSTREAM_SOURCE
        assert node.EXIT_SEMANTICS
        assert node.SHELL is False


def test_external_package_contracts_are_exact() -> None:
    assert CasOffinderNode.CONDA_PACKAGE_CONSTRAINTS == {"cas-offinder": "2.4.1"}
    assert CRISPRESSO2Node.CONDA_PACKAGE_CONSTRAINTS == {"crispresso2": "2.3.4"}
    assert MAGeCKCountNode.CONDA_PACKAGE_CONSTRAINTS == {"mageck": "0.5.9.5"}
    assert MAGeCKTestNode.CONDA_PACKAGE_CONSTRAINTS == {"mageck": "0.5.9.5"}
    assert CasOffinderNode.REQUIRED_EXECUTABLES == ["cas-offinder"]
    assert CRISPRESSO2Node.REQUIRED_EXECUTABLES == ["CRISPResso"]
    assert MAGeCKCountNode.REQUIRED_EXECUTABLES == ["mageck"]


def test_internal_guide_design_is_not_misrepresented_as_an_external_tool() -> None:
    assert GuideRNADesignNode.REQUIRES_EXTERNAL_TOOLS is False
    assert GuideRNADesignNode.REQUIRED_EXECUTABLES == []
    assert GuideRNADesignNode.REQUIRED_CONDA_PACKAGES == []
    assert GuideRNADesignNode.GIT_COMMIT == GUIDE_DESIGN_BASELINE_COMMIT
    assert GuideRNADesignNode.SOURCE_GIT_BLOB == GUIDE_DESIGN_SOURCE_BLOB
    assert GuideRNADesignNode.PACKAGE_CONSTRAINT.startswith("none")


def test_crispresso2_renders_native_argv_and_plans_sanitized_outputs(tmp_path: Path) -> None:
    inputs = {
        "r1": "edited R1.fastq.gz",
        "r2": "edited R2.fastq.gz",
        "amplicon_seq": "ACGTACGTACGT",
        "name": "edited locus/sample",
        "guide_seq": "GATTACAGATTACAGATTAC",
        "quant_window_center": -3,
        "quant_window_size": 5,
        "output": "/work/crispresso2",
    }
    assert CRISPRESSO2Node.render_command(inputs) == [
        "CRISPResso",
        "-r1",
        "edited R1.fastq.gz",
        "-a",
        "ACGTACGTACGT",
        "-o",
        "/work/crispresso2",
        "--name",
        "edited locus/sample",
        "-r2",
        "edited R2.fastq.gz",
        "-g",
        "GATTACAGATTACAGATTAC",
        "-wc",
        "-3",
        "-w",
        "5",
    ]
    assert CRISPRESSO2Node.PLAN_OUTPUTS(inputs, tmp_path) == [
        tmp_path / "crispresso2" / "CRISPResso_on_edited_locus_sample.html",
        tmp_path / "crispresso2" / "CRISPResso_on_edited_locus_sample",
    ]


def test_crispresso2_preserves_zero_window_and_rejects_bad_sequences() -> None:
    inputs = {
        "r1": "r1.fastq.gz",
        "amplicon_seq": "ACGTACGT",
        "name": "sample",
        "quant_window_center": 0,
        "quant_window_size": 0,
    }
    command = CRISPRESSO2Node.render_command(inputs)
    assert command[-4:] == ["-wc", "0", "-w", "0"]
    assert "unsupported DNA symbols" in str(CRISPRESSO2Node.VALIDATE_INPUTS({**inputs, "amplicon_seq": "ACGTU"}))
    assert "at least 0" in str(CRISPRESSO2Node.VALIDATE_INPUTS({**inputs, "quant_window_size": "1,-1"}))


def test_cas_offinder_prepares_exact_native_input_and_device_argv(tmp_path: Path) -> None:
    inputs: dict[str, Any] = {
        "guide_seq": "GGCCGACCTGTCGCTGACGC",
        "genome_fasta": "/data/genomes/hg38",
        "mismatches": 5,
        "pam_sequence": "NRG",
        "device": "G0,1",
        "output": str(tmp_path / "cas_offinder"),
    }
    outputs = CasOffinderNode.PLAN_OUTPUTS(inputs, tmp_path)
    CasOffinderNode.PREPARE_EXECUTION(inputs, outputs)
    input_file = outputs[0].parent / "cas_offinder_input.txt"

    assert input_file.read_text(encoding="ascii") == (
        "/data/genomes/hg38\n"
        "NNNNNNNNNNNNNNNNNNNNNRG\n"
        "GGCCGACCTGTCGCTGACGCNRG 5\n"
    )
    assert CasOffinderNode.render_command(inputs) == [
        "cas-offinder",
        str(input_file),
        "G0,1",
        str(outputs[0]),
    ]
    assert outputs == [tmp_path / "cas_offinder" / "offtarget_sites.txt"]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"guide_seq": "ACGTU"}, "unsupported DNA symbols"),
        ({"mismatches": -1}, "at least 0"),
        ({"device": "GPU"}, "optional device IDs"),
    ],
)
def test_cas_offinder_rejects_non_native_contracts(overrides: dict[str, Any], message: str) -> None:
    inputs = {
        "guide_seq": "ACGTACGT",
        "genome_fasta": "genome.fa",
        "mismatches": 3,
        "pam_sequence": "NGG",
        "device": "C",
        **overrides,
    }
    assert message in str(CasOffinderNode.VALIDATE_INPUTS(inputs))


def test_mageck_count_renders_fastq_samples_and_native_outputs(tmp_path: Path) -> None:
    inputs = {
        "library_file": "library.tsv",
        "fastq_files": ["control_r1.fastq.gz,control_r2.fastq.gz", "treated.fastq.gz"],
        "output_prefix": "screen",
        "sample_labels": "control,treated",
        "day0_label": "control",
        "output": "/work/mageck_count",
    }
    assert MAGeCKCountNode.render_command(inputs) == [
        "mageck",
        "count",
        "-l",
        "library.tsv",
        "-n",
        "/work/mageck_count/screen",
        "--fastq",
        "control_r1.fastq.gz,control_r2.fastq.gz",
        "treated.fastq.gz",
        "--sample-label",
        "control,treated",
        "--day0-label",
        "control",
    ]
    assert MAGeCKCountNode.PLAN_OUTPUTS(inputs, tmp_path) == [
        tmp_path / "mageck_count" / "screen.count.txt",
        tmp_path / "mageck_count" / "screen.count_normalized.txt",
    ]
    assert MAGeCKCountNode.DEFAULT_NORMALIZATION == "median"
    assert "exactly one" in str(MAGeCKCountNode.VALIDATE_INPUTS({**inputs, "sample_labels": "control"}))


def test_mageck_test_renders_source_order_and_native_outputs(tmp_path: Path) -> None:
    inputs = {
        "count_table": "screen.count.txt",
        "treatment_labels": "treated_a,treated_b",
        "control_labels": "control_a,control_b",
        "output_prefix": "screen_test",
        "norm_method": "median",
        "adjust_method": "fdr",
        "sort_criteria": "neg",
        "output": "/work/mageck_test",
    }
    assert MAGeCKTestNode.render_command(inputs) == [
        "mageck",
        "test",
        "-k",
        "screen.count.txt",
        "-t",
        "treated_a,treated_b",
        "-c",
        "control_a,control_b",
        "-n",
        "/work/mageck_test/screen_test",
        "--norm-method",
        "median",
        "--adjust-method",
        "fdr",
        "--sort-criteria",
        "neg",
    ]
    assert MAGeCKTestNode.PLAN_OUTPUTS(inputs, tmp_path) == [
        tmp_path / "mageck_test" / "screen_test.gene_summary.txt",
        tmp_path / "mageck_test" / "screen_test.sgrna_summary.txt",
    ]
    assert "norm_method" in str(MAGeCKTestNode.VALIDATE_INPUTS({**inputs, "norm_method": "quantile"}))


def test_guide_design_validation_and_output_planning(tmp_path: Path) -> None:
    inputs = {"target": "chr1", "pam": "NGG", "genome": "genome.fa"}
    assert GuideRNADesignNode.PLAN_OUTPUTS(inputs, tmp_path) == [
        tmp_path / "guide_rna_design" / "guides.tsv",
        tmp_path / "guide_rna_design" / "off_targets.tsv",
    ]
    assert GuideRNADesignNode.VALIDATE_INPUTS({**inputs, "guide_length": 0}) == (
        "guide_length must be greater than zero"
    )
    assert GuideRNADesignNode.VALIDATE_INPUTS({**inputs, "pam": "NGR"}) == (
        "pam may only contain A, C, G, T, or N"
    )


@pytest.mark.asyncio
async def test_guide_design_runs_internal_baseline_on_synthetic_fasta(tmp_path: Path) -> None:
    genome = tmp_path / "mini.fa"
    genome.write_text(
        ">chr1\n"
        "TTTTACGTACGTACGTACGTACGTNGGCCCCACGTACGTACGTACGTACGTAGGTTTT\n"
        ">chr2\n"
        "AAAACGTACGTACGTACGTACGTAGGAAAAACGTACGTACGTACGTACGTGGGAAAA\n",
        encoding="ascii",
    )

    guides_path, off_targets_path = await GuideRNADesignNode().run(
        target="chr1:5-27",
        pam="NGG",
        genome=genome,
        guide_length=20,
        max_guides=5,
        mismatches=1,
        output_dir=tmp_path / "run",
    )

    with Path(guides_path).open(newline="", encoding="utf-8") as handle:
        guides = list(csv.DictReader(handle, delimiter="\t"))
    with Path(off_targets_path).open(newline="", encoding="utf-8") as handle:
        off_targets = list(csv.DictReader(handle, delimiter="\t"))
    assert guides[0]["sequence"] == "ACGTACGTACGTACGTACGT"
    assert guides[0]["start"] == "5"
    assert guides[0]["off_target_count"] == str(len(off_targets))
    assert {row["contig"] for row in off_targets} == {"chr1", "chr2"}


class _FailingContext:
    def __init__(self, node_dir: Path) -> None:
        self.node_dir = node_dir

    async def run_command(self, command: list[str], **kwargs: Any) -> dict[str, Any]:
        return {"returncode": 23, "stdout": "", "stderr": "synthetic tool failure"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("node", "inputs"),
    [
        (
            CasOffinderNode(),
            {"guide_seq": "ACGT", "genome_fasta": "genome.fa", "mismatches": 1},
        ),
        (
            CRISPRESSO2Node(),
            {"r1": "reads.fastq", "amplicon_seq": "ACGT", "name": "sample"},
        ),
        (
            MAGeCKCountNode(),
            {"library_file": "library.tsv", "fastq_files": ["reads.fastq"], "output_prefix": "count"},
        ),
        (
            MAGeCKTestNode(),
            {
                "count_table": "count.txt",
                "treatment_labels": "treated",
                "control_labels": "control",
                "output_prefix": "test",
            },
        ),
    ],
)
async def test_external_nodes_fail_closed_on_nonzero_exit(
    node: Any,
    inputs: dict[str, Any],
    tmp_path: Path,
) -> None:
    with pytest.raises(RuntimeError, match=r"exit 23.*synthetic tool failure"):
        await node.run(context=_FailingContext(tmp_path), **inputs)
