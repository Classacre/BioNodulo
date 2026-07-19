"""Focused metadata, argv, validation, and output contracts for long-read tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from bionodulo.nodes.builtin.long_read_family import (
    ChopperFilterNode,
    DoradoBasecallerNode,
    DoradoDemuxNode,
    ModkitPileupNode,
    NanoPlotQCNode,
)


FAMILY = (
    ChopperFilterNode,
    DoradoBasecallerNode,
    DoradoDemuxNode,
    ModkitPileupNode,
    NanoPlotQCNode,
)


def test_pinned_source_authorities_and_direct_argv_metadata() -> None:
    assert ChopperFilterNode.GIT_COMMIT == "ca85a03f6c4a8836ab5f163592e24a30b9d3a3c4"
    assert ChopperFilterNode.PACKAGE_CONSTRAINT == "chopper = 0.9.2"
    assert DoradoBasecallerNode.GIT_COMMIT == "0949eb8de80dce9a198c08c0e37e31ed1eb627fc"
    assert DoradoBasecallerNode.PACKAGE_CONSTRAINT.startswith("official Dorado 0.9.6 binary")
    assert DoradoBasecallerNode.REQUIRED_CONDA_PACKAGES == []
    assert DoradoBasecallerNode.LINUX_X64_BINARY_URL.endswith("dorado-0.9.6-linux-x64.tar.gz")
    assert ModkitPileupNode.GIT_COMMIT == "d13b97db2d221afc4a1db3616a7eccdc6858a313"
    assert ModkitPileupNode.REQUIRED_CONDA_PACKAGES == ["ont-modkit"]
    assert NanoPlotQCNode.SOURCE_SHA256 == ("c9d6b3c807d46fb3eb293bc826a94b699d17f50fb7fd0dcc3f17f56b0cee8e57")
    assert {node.NODE_ID for node in FAMILY} == {
        "chopper_filter",
        "dorado_basecaller",
        "dorado_demux",
        "modkit_pileup",
        "nanoplot",
    }
    assert all(node.SHELL is False for node in FAMILY)


def test_source_native_ports_expose_models_indexes_and_mutually_exclusive_inputs() -> None:
    basecaller = DoradoBasecallerNode.INPUT_TYPES()
    assert set(basecaller["required"]) == {"pod5_dir", "model", "reference"}
    assert basecaller["required"]["model"][0] == "DIRECTORY"
    assert basecaller["optional"]["modified_bases_models"][0] == "FILE_LIST"
    assert "modified_bases" not in basecaller["optional"]
    assert DoradoBasecallerNode.RETURN_NAMES == (
        "basecalled_bam",
        "basecalled_bam_index",
    )

    modkit = ModkitPileupNode.INPUT_TYPES()
    assert set(modkit["required"]) == {"bam", "bam_index"}
    assert {"reference", "reference_index", "cpg", "combine_strands"}.issubset(modkit["optional"])

    assert ChopperFilterNode.INPUT_TYPES()["required"]["reads"][0] == "FASTQ"
    assert DoradoDemuxNode.NATIVE_SUMMARY_FILENAME == "barcoding_summary.txt"
    assert {
        "fastq",
        "fasta",
        "summary",
        "bam",
        "ubam",
        "cram",
    }.issubset(NanoPlotQCNode.INPUT_TYPES()["optional"])


def test_chopper_renders_complete_filter_argv_without_shell_or_fake_gzip() -> None:
    command = ChopperFilterNode.render_command(
        {
            "reads": "reads.fastq.gz",
            "min_quality": 10.5,
            "max_quality": 40.0,
            "min_length": 1000,
            "max_length": 50000,
            "headcrop": 5,
            "tailcrop": 7,
            "threads": 8,
            "contaminant_reference": "lambda.fa",
            "inverse": True,
            "min_gc": 0.2,
            "max_gc": 0.8,
        }
    )

    assert command == [
        "chopper",
        "--quality",
        "10.5",
        "--maxqual",
        "40.0",
        "--minlength",
        "1000",
        "--maxlength",
        "50000",
        "--headcrop",
        "5",
        "--tailcrop",
        "7",
        "--threads",
        "8",
        "--contam",
        "lambda.fa",
        "--inverse",
        "--input",
        "reads.fastq.gz",
        "--maxgc",
        "0.8",
        "--mingc",
        "0.2",
    ]
    assert ChopperFilterNode.STDOUT_OUTPUT_INDEX == 0
    assert ChopperFilterNode.OUTPUT_FILENAMES == ("filtered_reads.fastq",)


def test_chopper_uses_upstream_defaults_and_validates_ranges() -> None:
    assert ChopperFilterNode.render_command({"reads": "reads.fastq"}) == [
        "chopper",
        "--quality",
        "0.0",
        "--maxqual",
        "1000.0",
        "--minlength",
        "1",
        "--threads",
        "4",
        "--input",
        "reads.fastq",
        "--maxgc",
        "1.0",
        "--mingc",
        "0.0",
    ]
    assert (
        ChopperFilterNode.VALIDATE_INPUTS({"reads": "reads.fastq", "min_gc": 0.8, "max_gc": 0.2})
        == "Input 'min_gc' must not exceed 'max_gc'"
    )


def test_dorado_basecaller_uses_explicit_models_and_native_file_output() -> None:
    command = DoradoBasecallerNode.render_command(
        {
            "pod5_dir": "/data/pod5",
            "model": "/models/simplex",
            "modified_bases_models": ["/models/5mC", "/models/6mA"],
            "kit_name": "SQK-NBD114-24",
            "trim": "none",
            "min_qscore": 9,
            "reference": "reference.mmi",
            "device": "cpu",
            "recursive": True,
            "output": "/tmp/run/dorado_basecaller",
        }
    )

    assert command == [
        "dorado",
        "basecaller",
        "/models/simplex",
        "/data/pod5",
        "--device",
        "cpu",
        "--recursive",
        "--min-qscore",
        "9",
        "--reference",
        "reference.mmi",
        "--modified-bases-models",
        "/models/5mC,/models/6mA",
        "--kit-name",
        "SQK-NBD114-24",
        "--trim",
        "none",
        "--output-dir",
        "/tmp/run/dorado_basecaller/native_output",
    ]
    assert DoradoBasecallerNode.STDOUT_OUTPUT_INDEX is None
    assert ">" not in command


def test_dorado_basecaller_rejects_implicit_model_downloads_and_bad_devices() -> None:
    assert (
        DoradoBasecallerNode.VALIDATE_INPUTS(
            {
                "pod5_dir": "/data/pod5",
                "model": "sup@latest",
                "reference": "reference.mmi",
            }
        )
        == "Input 'model' must be a staged local model directory, not an automatic selector"
    )
    assert (
        DoradoBasecallerNode.VALIDATE_INPUTS(
            {
                "pod5_dir": "/data/pod5",
                "model": "/models/sup",
                "reference": "reference.mmi",
                "device": "gpu",
            }
        )
        == "Input 'device' must be auto, cpu, metal, cuda:all, or cuda:<ids>"
    )
    for malformed in ("cuda:", "cuda:garbage", "cuda:0,0", "cuda:01"):
        assert (
            DoradoBasecallerNode.VALIDATE_INPUTS(
                {
                    "pod5_dir": "/data/pod5",
                    "model": "/models/sup",
                    "reference": "reference.mmi",
                    "device": malformed,
                }
            )
            == "Input 'device' must be auto, cpu, metal, cuda:all, or cuda:<ids>"
        )


@pytest.mark.asyncio
async def test_dorado_basecaller_stabilizes_native_binary_output_without_decoding(
    tmp_path: Path,
) -> None:
    commands: list[list[str]] = []

    class NativeOutputContext:
        node_dir = tmp_path

        async def run_command(self, command: list[str], **kwargs: object) -> dict[str, object]:
            commands.append(command)
            native_dir = Path(command[command.index("--output-dir") + 1])
            native_dir.mkdir(parents=True, exist_ok=True)
            native_bam = native_dir / "calls_2025-04-16_T00-00-00.bam"
            native_bam.write_bytes(b"BAM\x01\xff\x00binary")
            Path(f"{native_bam}.bai").write_bytes(b"BAI\x01\xff\x00binary")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    result = await DoradoBasecallerNode().run(
        context=NativeOutputContext(),
        output_dir=tmp_path,
        pod5_dir="/data/pod5",
        model="/models/simplex",
        reference="reference.mmi",
        device="cpu",
    )

    expected_bam = tmp_path / "dorado_basecaller" / "basecalled_bam.bam"
    expected_index = tmp_path / "dorado_basecaller" / "basecalled_bam.bam.bai"
    assert commands and "--output-dir" in commands[0]
    assert expected_bam.read_bytes() == b"BAM\x01\xff\x00binary"
    assert expected_index.read_bytes() == b"BAI\x01\xff\x00binary"
    assert result == (str(expected_bam), str(expected_index))


def test_dorado_demux_classification_argv_forces_native_summary() -> None:
    command = DoradoDemuxNode.render_command(
        {
            "reads": "calls.bam",
            "kit_name": "SQK-NBD114-24",
            "sample_sheet": "samples.csv",
            "barcode_arrangement": "arrangement.toml",
            "barcode_sequences": "barcodes.fasta",
            "emit_fastq": True,
            "barcode_both_ends": True,
            "no_trim": True,
            "sort_bam": True,
            "recursive": True,
            "threads": 6,
            "max_reads": 1000,
            "read_ids": "read_ids.txt",
            "output": "/tmp/run/dorado_demux",
        }
    )

    assert command == [
        "dorado",
        "demux",
        "--output-dir",
        "/tmp/run/dorado_demux/demux",
        "--kit-name",
        "SQK-NBD114-24",
        "--sample-sheet",
        "samples.csv",
        "--barcode-arrangement",
        "arrangement.toml",
        "--barcode-sequences",
        "barcodes.fasta",
        "--emit-fastq",
        "--emit-summary",
        "--barcode-both-ends",
        "--no-trim",
        "--sort-bam",
        "--recursive",
        "--threads",
        "6",
        "--max-reads",
        "1000",
        "--read-ids",
        "read_ids.txt",
        "calls.bam",
    ]


def test_dorado_demux_no_classify_and_validation_match_source_xor() -> None:
    assert DoradoDemuxNode.render_command(
        {
            "reads": "/data/basecalled.bam",
            "no_classify": True,
            "output": "/tmp/run/dorado_demux",
        }
    ) == [
        "dorado",
        "demux",
        "--output-dir",
        "/tmp/run/dorado_demux/demux",
        "--no-classify",
        "--emit-summary",
        "/data/basecalled.bam",
    ]
    assert DoradoDemuxNode.VALIDATE_INPUTS({"reads": "calls.bam"}) == (
        "Specify exactly one of 'kit_name' or 'no_classify'"
    )
    assert (
        DoradoDemuxNode.VALIDATE_INPUTS({"reads": "calls.bam", "kit_name": "KIT", "no_classify": True})
        == "Specify exactly one of 'kit_name' or 'no_classify'"
    )
    assert (
        DoradoDemuxNode.VALIDATE_INPUTS({"reads": "calls.bam", "kit_name": "KIT", "sort_bam": True})
        == "Input 'sort_bam' requires 'no_trim' or 'no_classify'"
    )


def test_modkit_pileup_renders_indexed_cpg_bedmethyl_argv() -> None:
    command = ModkitPileupNode.render_command(
        {
            "bam": "/data/calls.sorted.bam",
            "bam_index": "/data/calls.sorted.bam.bai",
            "reference": "/refs/reference.fa",
            "reference_index": "/refs/reference.fa.fai",
            "threads": 8,
            "max_depth": 16000,
            "filter_percentile": 0.2,
            "region": "chr1:1-1000",
            "cpg": True,
            "combine_strands": True,
            "with_header": True,
            "output": "/tmp/run/modkit_pileup",
        }
    )

    assert command == [
        "modkit",
        "pileup",
        "/data/calls.sorted.bam",
        "/tmp/run/modkit_pileup/bedmethyl.bed",
        "--threads",
        "8",
        "--max-depth",
        "16000",
        "--filter-percentile",
        "0.2",
        "--region",
        "chr1:1-1000",
        "--ref",
        "/refs/reference.fa",
        "--cpg",
        "--combine-strands",
        "--header",
    ]


def test_modkit_requires_exact_bam_and_reference_sidecars() -> None:
    base = {
        "bam": "/data/calls.sorted.bam",
        "bam_index": "/data/calls.sorted.bam.bai",
    }
    assert ModkitPileupNode.VALIDATE_INPUTS({**base, "combine_strands": True}) == (
        "Inputs 'reference' and 'reference_index' are required for CpG strand handling"
    )
    assert ModkitPileupNode.VALIDATE_INPUTS({**base, "bam_index": "/data/calls.bai"}) == (
        "Input 'bam_index' must be the exact colocated index for input 'bam'; expected '/data/calls.sorted.bam.bai'"
    )
    assert ModkitPileupNode.VALIDATE_INPUTS(
        {
            **base,
            "reference": "/refs/reference.fa",
            "reference_index": "/refs/reference.fai",
            "cpg": True,
        }
    ) == (
        "Input 'reference_index' must be the exact colocated index for input 'reference'; "
        "expected '/refs/reference.fa.fai'"
    )


def test_nanoplot_renders_one_source_with_documented_defaults_and_flags() -> None:
    command = NanoPlotQCNode.render_command(
        {
            "fastq": ["reads_1.fastq.gz", "reads_2.fastq.gz"],
            "threads": 8,
            "plot_format": "pdf",
            "max_length": 50000,
            "min_length": 1000,
            "loglength": True,
            "show_n50": True,
            "tsv_stats": True,
            "output": "/tmp/run/nanoplot",
        }
    )

    assert command == [
        "NanoPlot",
        "--outdir",
        "/tmp/run/nanoplot",
        "--threads",
        "8",
        "--format",
        "pdf",
        "--maxlength",
        "50000",
        "--minlength",
        "1000",
        "--loglength",
        "--N50",
        "--tsv_stats",
        "--fastq",
        "reads_1.fastq.gz",
        "reads_2.fastq.gz",
    ]


def test_nanoplot_requires_exactly_one_source_and_valid_length_bounds() -> None:
    assert NanoPlotQCNode.VALIDATE_INPUTS({}) == ("Exactly one NanoPlot input source must be provided")
    assert (
        NanoPlotQCNode.VALIDATE_INPUTS({"fastq": "reads.fastq", "bam": "calls.bam"})
        == "Exactly one NanoPlot input source must be provided"
    )
    assert (
        NanoPlotQCNode.VALIDATE_INPUTS({"fastq": "reads.fastq", "min_length": 1000, "max_length": 500})
        == "Input 'min_length' must not exceed 'max_length'"
    )


@pytest.mark.parametrize(
    ("node_class", "inputs", "expected"),
    [
        (ChopperFilterNode, {}, ("filtered_reads.fastq",)),
        (
            DoradoBasecallerNode,
            {},
            ("basecalled_bam.bam", "basecalled_bam.bam.bai"),
        ),
        (ModkitPileupNode, {}, ("bedmethyl.bed",)),
        (NanoPlotQCNode, {}, ("NanoPlot-report.html", "NanoStats.txt")),
    ],
)
def test_fixed_output_plans_use_source_native_names(
    tmp_path: Path,
    node_class: type,
    inputs: dict[str, object],
    expected: tuple[str, ...],
) -> None:
    assert node_class.PLAN_OUTPUTS(inputs, tmp_path) == [
        tmp_path / node_class.NODE_ID / filename for filename in expected
    ]


def test_dorado_demux_plans_native_summary_inside_dynamic_output_directory(
    tmp_path: Path,
) -> None:
    demux_dir = tmp_path / "dorado_demux" / "demux"
    assert DoradoDemuxNode.PLAN_OUTPUTS({}, tmp_path) == [
        demux_dir,
        demux_dir / "barcoding_summary.txt",
    ]
