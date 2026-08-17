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
    assert DoradoBasecallerNode.SOURCE_REF == (
        "tag v0.9.6 at 0949eb8de80dce9a198c08c0e37e31ed1eb627fc"
    )
    assert DoradoBasecallerNode.SOURCE_REVISION == DoradoBasecallerNode.GIT_COMMIT
    assert DoradoBasecallerNode.AUDIT_STATUS == "contract-checked-no-external-execution"
    assert DoradoBasecallerNode.PACKAGE_CONSTRAINT.startswith("official Dorado 0.9.6 binary")
    assert DoradoBasecallerNode.REQUIRED_CONDA_PACKAGES == []
    assert DoradoBasecallerNode.LINUX_X64_BINARY_URL.endswith("dorado-0.9.6-linux-x64.tar.gz")
    assert ModkitPileupNode.GIT_COMMIT == "cd85862f71d3bfc289f12adc1052a2e574c95e0f"
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
    assert basecaller["optional"]["modified_bases_models"][0] == "DIRECTORY"
    assert basecaller["optional"]["modified_bases_models"][1]["multiple"] is True
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
    assert DoradoDemuxNode.RETURN_NAMES == ("demux_dir", "barcode_summary", "selected_bam")
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
            "min_gc": 0.0,
            "max_gc": 1.0,
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
            "1.0",
            "--mingc",
            "0.0",
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


def test_chopper_rejects_gc_bounds_in_inverse_mode_because_upstream_ignores_them() -> None:
    validation = ChopperFilterNode.VALIDATE_INPUTS(
        {"reads": "reads.fastq", "inverse": True, "min_gc": 0.2}
    )
    assert validation is not True
    assert "cannot be combined with inverse mode" in str(validation)


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
    for malformed in ("gpu", "metal", "cuda:", "cuda:garbage", "cuda:0,0", "cuda:01"):
        assert (
            DoradoBasecallerNode.VALIDATE_INPUTS(
                {
                    "pod5_dir": "/data/pod5",
                    "model": "/models/sup",
                    "reference": "reference.mmi",
                    "device": malformed,
                }
            )
            == "Input 'device' must be auto, cpu, cuda:all, cuda:auto, or cuda:<ids>"
        )
    assert (
        DoradoBasecallerNode.VALIDATE_INPUTS(
            {
                "pod5_dir": "/data/pod5",
                "model": "/models/sup",
                "reference": "reference.mmi",
                "device": "cuda:auto",
            }
        )
        is True
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


def test_dorado_demux_classification_argv_forces_bam_and_native_summary() -> None:
    command = DoradoDemuxNode.render_command(
        {
            "reads": "calls.bam",
            "kit_name": "SQK-NBD114-24",
            "sample_sheet": "samples.csv",
            "barcode_arrangement": "arrangement.toml",
            "barcode_sequences": "barcodes.fasta",
            "selected_barcode": "SQK-NBD114-24_barcode01",
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
    input_types = DoradoDemuxNode.INPUT_TYPES()
    assert "selected_barcode" in input_types["required"]
    assert "emit_fastq" not in input_types["optional"]
    assert "emit_fastq" in input_types["hidden"]
    assert DoradoDemuxNode.render_command(
        {
            "reads": "/data/basecalled.bam",
            "no_classify": True,
            "selected_barcode": "SQK-NBD114-24_barcode01",
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
    assert DoradoDemuxNode.VALIDATE_INPUTS({"reads": "calls.bam"}) == ("Required input 'selected_barcode' is missing")
    assert (
        DoradoDemuxNode.VALIDATE_INPUTS(
            {
                "reads": "calls.bam",
                "selected_barcode": "KIT_barcode01",
                "kit_name": "KIT",
                "no_classify": True,
            }
        )
        == "Specify exactly one of 'kit_name' or 'no_classify'"
    )
    assert (
        DoradoDemuxNode.VALIDATE_INPUTS(
            {
                "reads": "calls.bam",
                "selected_barcode": "KIT_barcode01",
                "kit_name": "KIT",
                "sort_bam": True,
            }
        )
        == "Input 'sort_bam' requires 'no_trim' or 'no_classify'"
    )
    assert "drops barcode metadata" in str(
        DoradoDemuxNode.VALIDATE_INPUTS(
            {
                "reads": "calls.bam",
                "selected_barcode": "barcode01",
                "no_classify": True,
                "emit_fastq": True,
            }
        )
    )
    assert "selected_barcode" in str(
        DoradoDemuxNode.VALIDATE_INPUTS({"reads": "calls.bam", "no_classify": True, "selected_barcode": "../barcode01"})
    )


@pytest.mark.asyncio
async def test_dorado_demux_binds_one_source_native_barcode_bam_without_copying(
    tmp_path: Path,
) -> None:
    commands: list[list[str]] = []
    stale_dir = tmp_path / "dorado_demux" / "demux"
    stale_dir.mkdir(parents=True)
    (stale_dir / "stale.bam").write_bytes(b"stale")

    class NativeOutputContext:
        node_dir = tmp_path

        async def run_command(self, command: list[str], **kwargs: object) -> dict[str, object]:
            commands.append(command)
            native_dir = Path(command[command.index("--output-dir") + 1])
            native_dir.mkdir(parents=True, exist_ok=True)
            (native_dir / "run-123_SQK-NBD114-24_barcode01.bam").write_bytes(b"BAM\x01selected")
            (native_dir / "run-123_SQK-NBD114-24_barcode02.bam").write_bytes(b"BAM\x01other")
            (native_dir / "barcoding_summary.txt").write_text(
                "read_id\tbarcode_arrangement\nread-1\tSQK-NBD114-24_barcode01\n",
                encoding="utf-8",
            )
            return {"returncode": 0, "stdout": "", "stderr": ""}

    result = await DoradoDemuxNode().run(
        context=NativeOutputContext(),
        output_dir=tmp_path,
        reads="calls.bam",
        no_classify=True,
        selected_barcode="SQK-NBD114-24_barcode01",
        threads=4,
    )

    demux_dir = tmp_path / "dorado_demux" / "demux"
    native_bam = demux_dir / "run-123_SQK-NBD114-24_barcode01.bam"
    summary = demux_dir / "barcoding_summary.txt"
    selected = demux_dir / "selected_barcode.bam"
    assert commands and "--emit-fastq" not in commands[0]
    assert not (demux_dir / "stale.bam").exists()
    assert selected.read_bytes() == b"BAM\x01selected"
    assert selected.samefile(native_bam)
    assert result == (str(demux_dir), str(summary), str(selected))


@pytest.mark.asyncio
async def test_dorado_demux_copies_selected_bam_when_hard_links_are_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NativeOutputContext:
        node_dir = tmp_path

        async def run_command(self, command: list[str], **kwargs: object) -> dict[str, object]:
            native_dir = Path(command[command.index("--output-dir") + 1])
            native_dir.mkdir(parents=True, exist_ok=True)
            (native_dir / "run-123_barcode01.bam").write_bytes(b"BAM\x01selected")
            (native_dir / "barcoding_summary.txt").write_text("read_id\tbarcode\nread-1\tbarcode01\n")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    def reject_hard_link(*args: object, **kwargs: object) -> None:
        raise OSError("hard links unavailable")

    monkeypatch.setattr("bionodulo.nodes.builtin.long_read_family.dorado_demux.os.link", reject_hard_link)
    _, _, selected = await DoradoDemuxNode().run(
        context=NativeOutputContext(),
        output_dir=tmp_path,
        reads="calls.bam",
        no_classify=True,
        selected_barcode="barcode01",
    )

    native = tmp_path / "dorado_demux" / "demux" / "run-123_barcode01.bam"
    assert Path(selected).read_bytes() == native.read_bytes()
    assert not Path(selected).samefile(native)


@pytest.mark.asyncio
async def test_dorado_demux_fails_closed_when_selected_barcode_is_absent(tmp_path: Path) -> None:
    class NativeOutputContext:
        node_dir = tmp_path

        async def run_command(self, command: list[str], **kwargs: object) -> dict[str, object]:
            native_dir = Path(command[command.index("--output-dir") + 1])
            native_dir.mkdir(parents=True, exist_ok=True)
            (native_dir / "barcoding_summary.txt").write_text("read_id\n", encoding="utf-8")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    with pytest.raises(RuntimeError, match="exactly one BAM.*found 0"):
        await DoradoDemuxNode().run(
            context=NativeOutputContext(),
            output_dir=tmp_path,
            reads="calls.bam",
            no_classify=True,
            selected_barcode="SQK-NBD114-24_barcode01",
        )
    assert not (tmp_path / "dorado_demux" / "demux").exists()


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
        "--high-depth",
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


def test_modkit_rejects_percentile_when_filtering_is_disabled() -> None:
    inputs = {
        "bam": "/data/calls.sorted.bam",
        "bam_index": "/data/calls.sorted.bam.bai",
        "no_filtering": True,
        "filter_percentile": 0.2,
    }
    assert ModkitPileupNode.VALIDATE_INPUTS(inputs) == (
        "Input 'filter_percentile' cannot be combined with 'no_filtering'; "
        "the pinned Modkit parser treats them as mutually exclusive"
    )


def test_modkit_prepares_bam_and_reference_sibling_pairs(tmp_path: Path) -> None:
    bam = tmp_path / "source" / "calls.sorted.bam"
    bam_index = Path(f"{bam}.bai")
    reference = tmp_path / "source" / "reference.fa"
    reference_index = Path(f"{reference}.fai")
    for path in (bam, bam_index, reference, reference_index):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(path.name, encoding="utf-8")

    inputs = {
        "bam": str(bam),
        "bam_index": str(bam_index),
        "reference": str(reference),
        "reference_index": str(reference_index),
        "cpg": True,
    }
    output = tmp_path / "run" / "modkit_pileup" / "bedmethyl.bed"
    ModkitPileupNode.PREPARE_EXECUTION(inputs, [output])

    assert inputs["bam"] == str(tmp_path / "run" / "modkit_pileup" / "inputs" / "bam" / bam.name)
    assert inputs["bam_index"] == f"{inputs['bam']}.bai"
    assert inputs["reference"] == str(
        tmp_path / "run" / "modkit_pileup" / "inputs" / "reference" / reference.name
    )
    assert inputs["reference_index"] == f"{inputs['reference']}.fai"
    assert Path(inputs["bam"]).read_text(encoding="utf-8") == bam.name
    assert Path(inputs["bam_index"]).read_text(encoding="utf-8") == bam_index.name


def test_nanoplot_renders_one_source_with_documented_defaults_and_flags() -> None:
    assert NanoPlotQCNode.VERSION == "1.44.1"
    # python-kaleido is pinned below 1.0: nanoplotter imports
    # `kaleido.scopes.plotly`, which kaleido 1.x removed, so an unpinned solve
    # makes NanoPlot die at import.
    assert NanoPlotQCNode.CONDA_PACKAGE_CONSTRAINTS == {
        "nanoplot": "1.44.1",
        "python-kaleido": "0.2.1",
    }
    assert NanoPlotQCNode.SOURCE_SHA256 == ("c9d6b3c807d46fb3eb293bc826a94b699d17f50fb7fd0dcc3f17f56b0cee8e57")
    assert NanoPlotQCNode.SOURCE_AUTHORITIES["argv_parser"] == "nanoplot/utils.py:get_args"
    assert NanoPlotQCNode.AUDIT_STATUS == "contract-checked-no-binary-execution"
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
        demux_dir / "selected_barcode.bam",
    ]
