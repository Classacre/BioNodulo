from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.command_node import CommandNode
from bionodulo.nodes.builtin.alignment_family.adapter import BWA_INDEX_SUFFIXES
from bionodulo.nodes.builtin.alignment_family.bamleftalign import BamLeftAlignNode
from bionodulo.nodes.builtin.alignment_family.bowtie2 import Bowtie2Node
from bionodulo.nodes.builtin.alignment_family.bowtie2_adapter import BOWTIE2_SMALL_SUFFIXES
from bionodulo.nodes.builtin.alignment_family.bwa import BWANode
from bionodulo.nodes.builtin.alignment_family.bwa_mem2 import BWAMem2Node
from bionodulo.nodes.builtin.alignment_family.bwa_mem2_adapter import BWA_MEM2_SUFFIXES
from bionodulo.nodes.builtin.alignment_family.bwa_mem2_idx import BWAMem2IndexNode
from scripts.gen_node_index import build_index


def _bwa_bundle(directory: Path) -> Path:
    directory.mkdir(parents=True)
    prefix = directory / "reference.fa"
    prefix.write_text(">chr1\nACGT\n", encoding="ascii")
    for suffix in BWA_INDEX_SUFFIXES:
        Path(f"{prefix}{suffix}").write_bytes(suffix.encode("ascii"))
    return prefix


def _bwa_mem2_bundle(directory: Path) -> Path:
    directory.mkdir(parents=True)
    prefix = directory / "reference"
    for suffix in BWA_MEM2_SUFFIXES:
        Path(f"{prefix}{suffix}").write_bytes(suffix.encode("ascii"))
    return prefix


def _bowtie2_bundle(directory: Path) -> Path:
    directory.mkdir(parents=True)
    prefix = directory / "reference"
    for suffix in BOWTIE2_SMALL_SUFFIXES:
        Path(f"{prefix}{suffix}").write_bytes(suffix.encode("ascii"))
    return prefix


def test_focused_owners_are_unambiguous() -> None:
    expected = {
        "bamleftalign": BamLeftAlignNode,
        "bowtie2": Bowtie2Node,
        "bwa": BWANode,
        "bwa_mem2": BWAMem2Node,
        "bwa_mem2_idx": BWAMem2IndexNode,
    }
    live_index = build_index()
    assert {node_id: live_index[node_id] for node_id in expected} == {
        node_id: node.__module__ for node_id, node in expected.items()
    }


@pytest.mark.parametrize(
    ("node", "version", "commit", "source"),
    [
        (BamLeftAlignNode, "1.3.10", "b0d8efd9fa7f6612c883ec5ff79e4d17a0c29993", "src/bamleftalign.cpp"),
        (Bowtie2Node, "2.5.5", "0c6a1c75e047ad8bf70c178fa3cb1528fba6adc2", "bt2_search.cpp"),
        (BWANode, "0.7.19", "b92993c1161e73167181558856567ef2f367e3f0", "bwtaln.c; bwase.c; bwape.c"),
        (BWAMem2Node, "2.3", "7aa5ff6c3330490e5629ab9b7327683d2dce02d6", "src/fastmap.cpp"),
        (BWAMem2IndexNode, "2.3", "7aa5ff6c3330490e5629ab9b7327683d2dce02d6", "src/bwtindex.cpp"),
    ],
)
def test_alignment_contracts_are_source_pinned(node: type[CommandNode], version: str, commit: str, source: str) -> None:
    assert node.VERSION == version
    assert node.GIT_COMMIT == commit
    assert node.UPSTREAM_SOURCE == source
    assert node.PACKAGE_CONSTRAINTS
    if node in {BWANode, BWAMem2Node, BWAMem2IndexNode}:
        assert node.GIT_TAG == f"v{version}"
        assert all(commit in url for url in node.SOURCE_URLS)
        assert node.AUDIT_STATUS == "contract-checked-no-external-execution"


def test_bwa_reference_sockets_are_explicit_unions() -> None:
    assert BWANode.INPUT_TYPES()["required"]["ref_file"][0] == ("FASTA", "INDEX_DIR")
    assert BWAMem2Node.INPUT_TYPES()["required"]["ref_file"][0] == (
        "FASTA",
        "BWA_MEM2_INDEX",
        "INDEX_DIR",
    )
    assert BWAMem2IndexNode.RETURN_TYPES == ("BWA_MEM2_INDEX",)


def test_bwa_validates_cached_bundle_and_emits_coordinate_bam_bai(tmp_path: Path) -> None:
    prefix = _bwa_bundle(tmp_path / "index")
    inputs = {
        "ref_file": prefix.parent,
        "reference_source_selector": "cached",
        "input_type_selector": "paired",
        "fastq_input1": "R1.fastq.gz",
        "fastq_input2": "R2.fastq.gz",
        "threads": 4,
        "output": tmp_path / "out",
    }
    assert BWANode.VALIDATE_INPUTS(inputs) is True
    assert BWANode.PLAN_OUTPUTS(inputs, tmp_path) == [
        tmp_path / "bwa" / "aligned.bam",
        tmp_path / "bwa" / "aligned.bam.bai",
    ]
    command = BWANode.render_command(inputs)
    assert command[:5] == ["set", "-o", "pipefail", "&&", "bwa"]
    assert ["bwa", "index"] not in [command[index : index + 2] for index in range(len(command) - 1)]
    aln_commands = [
        command[index : index + 6] for index in range(len(command) - 5) if command[index : index + 2] == ["bwa", "aln"]
    ]
    assert [aln_command[-2:] for aln_command in aln_commands] == [
        [str(prefix), "R1.fastq.gz"],
        [str(prefix), "R2.fastq.gz"],
    ]
    assert command[-5:] == [
        "samtools",
        "index",
        "-o",
        str(tmp_path / "out" / "aligned.bam.bai"),
        str(tmp_path / "out" / "aligned.bam"),
    ]


def test_bwa_accepts_a_native_prefix_without_a_copied_reference_fasta(tmp_path: Path) -> None:
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    prefix = index_dir / "custom-prefix"
    for suffix in BWA_INDEX_SUFFIXES:
        Path(f"{prefix}{suffix}").write_bytes(suffix.encode("ascii"))
    inputs = {
        "ref_file": index_dir,
        "reference_source_selector": "cached",
        "input_type_selector": "single",
        "fastq_input1": "reads.fastq.gz",
        "threads": 1,
        "output": tmp_path / "out",
    }
    assert BWANode.VALIDATE_INPUTS(inputs) is True
    command = BWANode.render_command(inputs)
    aln_start = command.index("bwa")
    assert [str(prefix), "reads.fastq.gz", ">"] == command[aln_start + 4 : aln_start + 7]


def test_bwa_accepts_upstream_thread_counts_above_wrapper_ui_conventions(tmp_path: Path) -> None:
    prefix = _bwa_bundle(tmp_path / "index")
    inputs = {
        "ref_file": prefix.parent,
        "reference_source_selector": "cached",
        "input_type_selector": "single",
        "fastq_input1": "reads.fastq.gz",
        "threads": 128,
        "output": tmp_path / "out",
    }

    assert BWANode.INPUT_TYPES()["required"]["threads"][1] == {"default": 1, "min": 1}
    assert BWANode.VALIDATE_INPUTS(inputs) is True
    command = BWANode.render_command(inputs)
    assert command[command.index("-t") : command.index("-t") + 2] == ["-t", "128"]


def test_bwa_mem2_history_is_a_fasta_not_an_index_directory(tmp_path: Path) -> None:
    reference = tmp_path / "source.fa"
    reference.write_text(">chr1\nACGT\n", encoding="ascii")
    outputs = BWAMem2Node.PLAN_OUTPUTS({"output_sort": "coordinate"}, tmp_path / "run")
    inputs: dict[str, Any] = {
        "ref_file": reference,
        "reference_source_selector": "history",
        "ref_file_type": "fasta",
        "fastq_input_selector": "single",
        "fastq_input1": "reads.fastq.gz",
        "threads": 2,
        "output_sort": "coordinate",
    }
    assert BWAMem2Node.VALIDATE_INPUTS(inputs) is True
    BWAMem2Node.PREPARE_EXECUTION(inputs, outputs)
    staged = tmp_path / "run" / "bwa_mem2" / "reference_index" / "reference.fa"
    assert inputs["ref_file"] == str(staged)
    command = BWAMem2Node.render_command({**inputs, "output": outputs[0].parent})
    assert command[4:10] == [
        "bwa-mem2",
        "index",
        "-p",
        str(staged.parent / "reference"),
        str(staged),
        "&&",
    ]
    assert outputs[-1].name == "aligned.bam.bai"
    assert BWAMem2Node.PLAN_OUTPUTS({"output_sort": "name"}, tmp_path / "name") == [
        tmp_path / "name" / "bwa_mem2" / "aligned.bam"
    ]

    index_prefix = _bwa_mem2_bundle(tmp_path / "native-index")
    indexed = {
        **inputs,
        "ref_file": index_prefix.parent,
        "ref_file_type": "bwa_mem2_index",
    }
    assert BWAMem2Node.VALIDATE_INPUTS(indexed) is True
    indexed_command = BWAMem2Node.render_command({**indexed, "output": outputs[0].parent})
    assert indexed_command[4:8] == ["bwa-mem2", "mem", "-t", "2"]
    assert ["bwa-mem2", "index"] not in [
        indexed_command[offset : offset + 2] for offset in range(len(indexed_command) - 1)
    ]
    assert str(index_prefix) in indexed_command


def test_bwa_mem2_source_options_and_validation_match_v23(tmp_path: Path) -> None:
    prefix = _bwa_mem2_bundle(tmp_path / "index")
    inputs = {
        "ref_file": prefix.parent,
        "reference_source_selector": "history",
        "ref_file_type": "bwa_mem2_index",
        "fastq_input_selector": "single",
        "fastq_input1": "reads.fastq.gz",
        "threads": 128,
        "analysis_type_selector": "pbref",
        "iset_stats": "300,30,420,180",
        "read_group": "@RG\\tID:sample\\tSM:sample",
        "mark_shorter_splits": True,
        "min_score": -1,
        "output_sort": "unsorted",
        "output": tmp_path / "out",
    }

    assert BWAMem2Node.CITATION_DOIS == ["10.1109/IPDPS.2019.00041"]
    assert BWAMem2Node.INPUT_TYPES()["required"]["threads"][1] == {"default": 1, "min": 1}
    assert BWAMem2Node.VALIDATE_INPUTS(inputs) is True
    command = BWAMem2Node.render_command(inputs)
    for expected in (
        ["-t", "128"],
        ["-x", "pbref"],
        ["-I", "300,30,420,180"],
        ["-T", "-1"],
    ):
        start = command.index(expected[0])
        assert command[start : start + 2] == expected
    assert "-M" in command
    assert BWAMem2Node.VALIDATE_INPUTS({**inputs, "read_group": "SM:sample"}) == ("read_group must start with @RG")


@pytest.mark.asyncio
async def test_bwa_mem2_index_fake_execution_requires_complete_native_bundle(tmp_path: Path) -> None:
    reference = tmp_path / "reference.fa"
    reference.write_text(">chr1\nACGT\n", encoding="ascii")

    class Context:
        node_dir = tmp_path / "run"

        async def run_command(self, command: list[str], **_kwargs: Any) -> dict[str, Any]:
            prefix = Path(command[command.index("-p") + 1])
            for suffix in BWA_MEM2_SUFFIXES:
                Path(f"{prefix}{suffix}").write_bytes(suffix.encode("ascii"))
            return {"returncode": 0, "stdout": "", "stderr": ""}

    result = await BWAMem2IndexNode().run(reference=reference, context=Context())
    assert result == (str(tmp_path / "run" / "bwa_mem2_idx" / "index"),)


def test_bowtie2_paired_artifacts_use_percent_templates_and_explicit_mapping(tmp_path: Path) -> None:
    prefix = _bowtie2_bundle(tmp_path / "index")
    inputs = {
        "ref_file": prefix.parent,
        "reference_source_selector": "indexed",
        "library_type": "paired_collection",
        "input_1": {"forward": "R1.fastq.gz", "reverse": "R2.fastq.gz"},
        "reads_compression": "gz",
        "unaligned_file": True,
        "aligned_file": True,
        "save_mapping_stats": True,
        "sam_output_format": "bam",
        "threads": 3,
        "output": tmp_path / "out",
    }
    assert Bowtie2Node.VALIDATE_INPUTS(inputs) is True
    planned = Bowtie2Node.PLAN_OUTPUTS(inputs, tmp_path)
    assert Bowtie2Node.MAP_PLANNED_OUTPUTS(planned) == {
        "alignments": tmp_path / "bowtie2" / "alignments.bam",
        "alignment_index": tmp_path / "bowtie2" / "alignments.bam.bai",
        "mapping_stats": tmp_path / "bowtie2" / "mapping_stats.txt",
        "unaligned_reads": [
            tmp_path / "bowtie2" / "unaligned_reads.1.fastq.gz",
            tmp_path / "bowtie2" / "unaligned_reads.2.fastq.gz",
        ],
        "aligned_reads": [
            tmp_path / "bowtie2" / "aligned_reads.1.fastq.gz",
            tmp_path / "bowtie2" / "aligned_reads.2.fastq.gz",
        ],
    }
    command = Bowtie2Node.render_command(inputs)
    assert ["--un-conc-gz", str(tmp_path / "out" / "unaligned_reads.%.fastq.gz")] == command[
        command.index("--un-conc-gz") : command.index("--un-conc-gz") + 2
    ]
    assert ["--al-conc-gz", str(tmp_path / "out" / "aligned_reads.%.fastq.gz")] == command[
        command.index("--al-conc-gz") : command.index("--al-conc-gz") + 2
    ]


def test_bowtie2_names_reordered_output_truthfully_and_accepts_legacy_value(tmp_path: Path) -> None:
    prefix = _bowtie2_bundle(tmp_path / "index")
    base_inputs = {
        "ref_file": prefix.parent,
        "reference_source_selector": "indexed",
        "input_1": "reads.fastq",
        "threads": 1,
        "output": tmp_path / "out",
    }
    options = Bowtie2Node.INPUT_TYPES()["optional"]["sam_output_format"][1]["options"]
    assert options == ["bam", "sam", "input_order_bam"]

    current = {**base_inputs, "sam_output_format": "input_order_bam"}
    legacy = {**base_inputs, "sam_output_format": "qname_input_sorted_bam"}
    assert Bowtie2Node.VALIDATE_INPUTS(current) is True
    assert Bowtie2Node.VALIDATE_INPUTS(legacy) is True
    assert Bowtie2Node.render_command(current) == Bowtie2Node.render_command(legacy)
    assert "--reorder" in Bowtie2Node.render_command(current)

    assert "rg_id is required" in str(Bowtie2Node.VALIDATE_INPUTS({**base_inputs, "rg_sample": "sample"}))


def test_bamleftalign_requires_and_stages_exact_fasta_fai(tmp_path: Path) -> None:
    bam = tmp_path / "input.bam"
    reference = tmp_path / "reference.fa"
    reference_index = tmp_path / "reference.fa.fai"
    bam.write_bytes(b"bam")
    reference.write_text(">chr1\nACGT\n", encoding="ascii")
    reference_index.write_text("chr1\t4\t6\t4\t5\n", encoding="ascii")
    inputs: dict[str, Any] = {
        "input_bam": bam,
        "reference": reference,
        "reference_index": reference_index,
        "iterations": 5,
    }
    assert BamLeftAlignNode.VALIDATE_INPUTS(inputs) is True
    outputs = BamLeftAlignNode.PLAN_OUTPUTS(inputs, tmp_path / "run")
    BamLeftAlignNode.PREPARE_EXECUTION(inputs, outputs)
    staged_reference = tmp_path / "run" / "bamleftalign" / "reference" / "reference.fa"
    assert inputs["reference"] == str(staged_reference)
    assert inputs["reference_index"] == f"{staged_reference}.fai"
    assert BamLeftAlignNode.render_command({**inputs, "output": outputs[0].parent})[-5:] == [
        "--compressed",
        "--max-iterations",
        "5",
        ">",
        str(outputs[0]),
    ]
