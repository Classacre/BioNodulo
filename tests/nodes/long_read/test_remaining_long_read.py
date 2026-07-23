"""Focused contracts for the remaining Dorado and Medaka long-read nodes."""

from __future__ import annotations

from pathlib import Path

import pytest

from bionodulo.nodes.builtin import long_read as legacy
from bionodulo.nodes.builtin.long_read_family import (
    DoradoCorrectNode,
    DoradoDuplexNode,
    MedakaConsensusNode,
    MedakaNode,
)


def test_pinned_authorities_outputs_and_legacy_reexports() -> None:
    assert DoradoCorrectNode.GIT_COMMIT == "0949eb8de80dce9a198c08c0e37e31ed1eb627fc"
    assert DoradoDuplexNode.GIT_COMMIT == "0949eb8de80dce9a198c08c0e37e31ed1eb627fc"
    assert DoradoCorrectNode.SOURCE_REVISION == DoradoCorrectNode.GIT_COMMIT
    assert DoradoDuplexNode.SOURCE_REVISION == DoradoDuplexNode.GIT_COMMIT
    assert DoradoCorrectNode.AUDIT_STATUS == "contract-checked-no-external-execution"
    assert DoradoDuplexNode.AUDIT_STATUS == "contract-checked-no-external-execution"
    assert DoradoCorrectNode.REQUIRED_CONDA_PACKAGES == []
    assert DoradoCorrectNode.RETURN_TYPES == ("FASTA",)
    assert DoradoDuplexNode.RETURN_NAMES == ("duplex_bam", "duplex_bam_index")
    assert DoradoDuplexNode.INPUT_TYPES()["optional"]["modified_bases_models"][0] == "DIRECTORY"

    assert MedakaConsensusNode.GIT_COMMIT == "03b58482ca38088790edfa4b196f8bf619f83c05"
    assert MedakaConsensusNode.PACKAGE_CONSTRAINT == "medaka = 2.0.1"
    assert MedakaConsensusNode.REQUIRED_CONDA_PACKAGES == ["medaka"]

    assert legacy.DoradoCorrectNode is DoradoCorrectNode
    assert legacy.DoradoDuplexNode is DoradoDuplexNode
    assert legacy.MedakaConsensusNode is MedakaConsensusNode
    assert legacy.MedakaNode is MedakaNode


def test_dorado_correct_renders_fasta_correction_without_model_downloads() -> None:
    command = DoradoCorrectNode.render_command(
        {
            "reads": "reads.fastq.gz",
            "model": "/models/herro-v1",
            "threads": 12,
            "infer_threads": 2,
            "device": "cuda:0,1",
            "batch_size": 64,
            "index_size": "4G",
            "from_paf": "overlaps.paf",
            "resume_from": "corrected.fasta.fai",
        }
    )

    assert command == [
        "dorado",
        "correct",
        "reads.fastq.gz",
        "--model-path",
        "/models/herro-v1",
        "--threads",
        "12",
        "--infer-threads",
        "2",
        "--device",
        "cuda:0,1",
        "--batch-size",
        "64",
        "--index-size",
        "4G",
        "--from-paf",
        "overlaps.paf",
        "--resume-from",
        "corrected.fasta.fai",
    ]
    assert DoradoCorrectNode.STDOUT_OUTPUT_INDEX == 0
    assert DoradoCorrectNode.OUTPUT_FILENAMES == ("corrected_reads.fasta",)
    assert ">" not in command


def test_dorado_correct_validation_matches_normal_correction_mode() -> None:
    assert DoradoCorrectNode.VALIDATE_INPUTS({"reads": "reads.fastq", "model": ""}) == (
        "Input 'model' must be a non-empty path-like value"
    )
    assert (
        DoradoCorrectNode.VALIDATE_INPUTS({"reads": "reads.fastq", "model": "/models/herro", "threads": -1})
        == "Input 'threads' must be at least 0"
    )
    assert (
        DoradoCorrectNode.VALIDATE_INPUTS({"reads": "reads.fastq", "model": "/models/herro", "device": "gpu"})
        == "Input 'device' must be auto, cpu, cuda:all, cuda:auto, or cuda:<ids>"
    )
    assert "device" in str(
        DoradoCorrectNode.VALIDATE_INPUTS({"reads": "reads.fastq", "model": "/models/herro", "device": "metal"})
    )
    assert (
        DoradoCorrectNode.VALIDATE_INPUTS({"reads": "reads.fastq", "model": "/models/herro", "index_size": "lots"})
        == "Input 'index_size' must be an integer optionally followed by a size suffix"
    )


@pytest.mark.asyncio
async def test_dorado_correct_captures_source_native_fasta_stdout(tmp_path: Path) -> None:
    commands: list[list[str]] = []

    class Context:
        node_dir = tmp_path

        async def run_command(self, command: list[str], **kwargs: object) -> dict[str, object]:
            commands.append(command)
            stdout_path = Path(kwargs["stdout_path"])
            stdout_path.parent.mkdir(parents=True, exist_ok=True)
            stdout_path.write_bytes(b">read-1\nACGT\n")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    result = await DoradoCorrectNode().run(
        context=Context(),
        output_dir=tmp_path,
        reads="reads.fastq",
        model="/models/herro-v1",
        device="cpu",
    )

    expected = tmp_path / "dorado_correct" / "corrected_reads.fasta"
    assert commands and "--model-path" in commands[0]
    assert expected.read_bytes() == b">read-1\nACGT\n"
    assert result == (str(expected),)


def test_dorado_duplex_renders_explicit_simplex_stereo_and_sidecar_mode() -> None:
    command = DoradoDuplexNode.render_command(
        {
            "pod5_dir": "/data/pod5",
            "model": "/models/simplex",
            "stereo_model": "/models/stereo",
            "modified_bases_models": ["/models/5mC", "/models/6mA"],
            "pairs": "pairs.csv",
            "read_ids": "read_ids.txt",
            "reference": "reference.mmi",
            "bed_file": "targets.bed",
            "device": "cpu",
            "recursive": True,
            "min_qscore": 9,
            "threads": 8,
            "batch_size": 0,
            "chunk_size": 12000,
            "overlap": 600,
            "output": "/tmp/run/dorado_duplex",
        }
    )

    assert command == [
        "dorado",
        "duplex",
        "/models/simplex",
        "/data/pod5",
        "--stereo-model",
        "/models/stereo",
        "--device",
        "cpu",
        "--min-qscore",
        "9",
        "--threads",
        "8",
        "--batchsize",
        "0",
        "--chunksize",
        "12000",
        "--overlap",
        "600",
        "--modified-bases-models",
        "/models/5mC,/models/6mA",
        "--pairs",
        "pairs.csv",
        "--read-ids",
        "read_ids.txt",
        "--reference",
        "reference.mmi",
        "--bed-file",
        "targets.bed",
        "--recursive",
        "--output-dir",
        "/tmp/run/dorado_duplex/native_output",
    ]


def test_dorado_duplex_rejects_download_selectors_and_invalid_combinations() -> None:
    base = {
        "pod5_dir": "/data/pod5",
        "model": "/models/simplex",
        "stereo_model": "/models/stereo",
    }
    assert DoradoDuplexNode.VALIDATE_INPUTS({**base, "model": "sup@latest"}) == (
        "Input 'model' must be a staged local simplex model directory, not an automatic selector"
    )
    assert DoradoDuplexNode.VALIDATE_INPUTS({**base, "bed_file": "targets.bed"}) == (
        "Input 'bed_file' requires 'reference'"
    )
    assert DoradoDuplexNode.VALIDATE_INPUTS({**base, "chunk_size": 500, "overlap": 500}) == (
        "Input 'overlap' must be smaller than 'chunk_size'"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("with_reference", [False, True])
async def test_dorado_duplex_stabilizes_native_bam_and_conditional_index(
    tmp_path: Path,
    with_reference: bool,
) -> None:
    class Context:
        node_dir = tmp_path

        async def run_command(self, command: list[str], **kwargs: object) -> dict[str, object]:
            native_dir = Path(command[command.index("--output-dir") + 1])
            native_dir.mkdir(parents=True, exist_ok=True)
            native_bam = native_dir / "calls_2025-04-16_T00-00-00.bam"
            native_bam.write_bytes(b"BAM\x01\xff\x00duplex")
            if "--reference" in command:
                Path(f"{native_bam}.bai").write_bytes(b"BAI\x01\xff\x00duplex")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    kwargs: dict[str, object] = {
        "context": Context(),
        "output_dir": tmp_path,
        "pod5_dir": "/data/pod5",
        "model": "/models/simplex",
        "stereo_model": "/models/stereo",
        "device": "cpu",
    }
    if with_reference:
        kwargs["reference"] = "reference.mmi"

    result = await DoradoDuplexNode().run(**kwargs)

    expected_bam = tmp_path / "dorado_duplex" / "duplex_bam.bam"
    assert expected_bam.read_bytes() == b"BAM\x01\xff\x00duplex"
    if with_reference:
        expected_index = tmp_path / "dorado_duplex" / "duplex_bam.bam.bai"
        assert expected_index.read_bytes() == b"BAI\x01\xff\x00duplex"
        assert result == (str(expected_bam), str(expected_index))
    else:
        assert result == (str(expected_bam),)


def test_medaka_consensus_uses_explicit_model_and_source_native_output() -> None:
    command = MedakaConsensusNode.render_command(
        {
            "reads": "reads.fastq.gz",
            "draft": "draft.fasta",
            "model": "models/r1041_model.hdf",
            "threads": 8,
            "batch_size": 64,
            "no_fillgaps": True,
            "fill_char": "N",
            "min_mapq": 20,
            "output": "/tmp/run/medaka_consensus",
        }
    )

    assert command == [
        "medaka_consensus",
        "-i",
        "reads.fastq.gz",
        "-d",
        "draft.fasta",
        "-o",
        "/tmp/run/medaka_consensus",
        "-m",
        "models/r1041_model.hdf",
        "-t",
        "8",
        "-b",
        "64",
        "-f",
        "-g",
        "-r",
        "N",
        "-M",
        "20",
    ]
    assert "bam" not in MedakaConsensusNode.INPUT_TYPES()["optional"]
    assert MedakaConsensusNode.OUTPUT_FILENAMES == ("consensus.fasta",)


def test_medaka_rejects_model_identifiers_that_can_trigger_downloads() -> None:
    assert (
        MedakaConsensusNode.VALIDATE_INPUTS(
            {
                "reads": "reads.fastq",
                "draft": "draft.fasta",
                "model": "r1041_e82_400bps_sup_v5.0.0",
            }
        )
        == "Input 'model' must be a staged local Medaka model file, not a model identifier"
    )


def test_medaka_alias_preserves_the_focused_contract(tmp_path: Path) -> None:
    assert issubclass(MedakaNode, MedakaConsensusNode)
    assert MedakaNode.NODE_ID == "medaka"
    assert MedakaNode.INPUT_TYPES() == MedakaConsensusNode.INPUT_TYPES()
    assert MedakaNode.render_command.__func__ is MedakaConsensusNode.render_command.__func__
    assert MedakaNode.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "medaka" / "consensus.fasta"]


@pytest.mark.asyncio
async def test_medaka_consensus_checks_the_documented_consensus_fasta(tmp_path: Path) -> None:
    class Context:
        node_dir = tmp_path

        async def run_command(self, command: list[str], **kwargs: object) -> dict[str, object]:
            output = Path(command[command.index("-o") + 1])
            output.mkdir(parents=True, exist_ok=True)
            (output / "consensus.fasta").write_text(">draft\nACGT\n", encoding="ascii")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    result = await MedakaConsensusNode().run(
        context=Context(),
        output_dir=tmp_path,
        reads="reads.fastq",
        draft="draft.fasta",
        model="model.hdf",
    )

    expected = tmp_path / "medaka_consensus" / "consensus.fasta"
    assert expected.read_text(encoding="ascii") == ">draft\nACGT\n"
    assert result == (str(expected),)
