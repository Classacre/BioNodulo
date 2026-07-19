from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.builtin.rasusa import RasusaNode


def test_rasusa_is_source_pinned_and_has_truthful_conditional_ports() -> None:
    assert RasusaNode.VERSION == "4.1.0"
    assert RasusaNode.GIT_COMMIT == "59e28930210f1a7dccffb236273c2bddb7b4fedd"
    assert RasusaNode.PACKAGE_CONSTRAINTS == ("rasusa==4.1.0", "samtools==1.23.1")
    assert RasusaNode.RETURN_TYPES == ("FILE_LIST", "FILE", "BAM", "BAI")
    assert RasusaNode.RETURN_NAMES == (
        "paired_reads",
        "single_reads",
        "subsampled_bam",
        "subsampled_bam_index",
    )


def test_rasusa_single_and_paired_read_commands_map_outputs_explicitly(tmp_path: Path) -> None:
    single = {
        "input_selector": "single",
        "reads": "reads.fastq.gz",
        "subsample_type": "coverage",
        "genome_size": 4.6,
        "genome_size_unit": "m",
        "coverage": 30,
        "seed": 7,
        "output": tmp_path / "single",
    }
    assert RasusaNode.VALIDATE_INPUTS(single) is True
    assert RasusaNode.render_command(single) == [
        "rasusa",
        "reads",
        "--seed",
        "7",
        "--output",
        str(tmp_path / "single" / "single.fastq.gz"),
        "--genome-size",
        "4.6m",
        "--coverage",
        "30",
        "--compress-type",
        "g",
        "reads.fastq.gz",
    ]
    single_planned = RasusaNode.PLAN_OUTPUTS(single, tmp_path)
    assert RasusaNode.MAP_PLANNED_OUTPUTS(single_planned) == {"single_reads": single_planned[0]}

    paired = {
        "input_selector": "paired_collection",
        "reads": {"forward": "R1.fq", "reverse": "R2.fq"},
        "subsample_type": "num_reads",
        "num": 10000,
        "output_ext": "fastq",
        "output": tmp_path / "paired",
    }
    assert RasusaNode.VALIDATE_INPUTS(paired) is True
    planned = RasusaNode.PLAN_OUTPUTS(paired, tmp_path)
    assert RasusaNode.MAP_PLANNED_OUTPUTS(planned) == {"paired_reads": planned}
    command = RasusaNode.render_command(paired)
    assert command[-2:] == ["R1.fq", "R2.fq"]
    assert command.count("--output") == 2


def test_rasusa_preserves_inferred_fasta_format_and_compression(tmp_path: Path) -> None:
    inputs = {
        "input_selector": "single",
        "reads": "reads.fa.xz",
        "subsample_type": "num_reads",
        "num": 10,
        "output": tmp_path / "rasusa",
    }
    assert RasusaNode.VALIDATE_INPUTS(inputs) is True
    assert RasusaNode.PLAN_OUTPUTS(inputs, tmp_path) == [tmp_path / "rasusa" / "single.fasta.xz"]
    command = RasusaNode.render_command(inputs)
    assert ["--output", str(tmp_path / "rasusa" / "single.fasta.xz")] == command[2:4]
    assert ["--compress-type", "x", "reads.fa.xz"] == command[-3:]


def test_aligned_fetch_requires_exact_bai_and_emits_sorted_bam_bai(tmp_path: Path) -> None:
    bam = tmp_path / "source" / "aligned.bam"
    bam.parent.mkdir()
    bam.write_bytes(b"bam")
    bai = Path(f"{bam}.bai")
    bai.write_bytes(b"bai")
    inputs: dict[str, Any] = {
        "input_selector": "aligned",
        "aligned_input": bam,
        "aligned_input_index": bai,
        "coverage": 50,
        "seed": 13,
        "strategy": "fetch",
        "step_size": 200,
        "batch_size": 20000,
        "threads": 3,
    }
    assert RasusaNode.VALIDATE_INPUTS(inputs) is True
    outputs = RasusaNode.PLAN_OUTPUTS(inputs, tmp_path / "run")
    RasusaNode.PREPARE_EXECUTION(inputs, outputs)
    staged_bam = tmp_path / "run" / "rasusa" / "input" / "alignment.bam"
    assert inputs["aligned_input"] == str(staged_bam)
    assert inputs["aligned_input_index"] == f"{staged_bam}.bai"
    command = RasusaNode.render_command({**inputs, "output": outputs[0].parent})
    assert command[:6] == ["set", "-o", "pipefail", "&&", "rasusa", "aln"]
    assert ["--step-size", "200", "--batch-size", "20000"] == command[
        command.index("--step-size") : command.index("--batch-size") + 2
    ]
    assert command[-5:] == [
        "samtools",
        "index",
        "-o",
        str(outputs[1]),
        str(outputs[0]),
    ]
    assert RasusaNode.MAP_PLANNED_OUTPUTS(outputs) == {
        "subsampled_bam": outputs[0],
        "subsampled_bam_index": outputs[1],
    }


def test_aligned_stream_uses_only_stream_specific_parameter(tmp_path: Path) -> None:
    command = RasusaNode.render_command(
        {
            "input_selector": "aligned",
            "aligned_input": "aligned.bam",
            "coverage": 20,
            "strategy": "stream",
            "swap_distance": 8,
            "output": tmp_path / "rasusa",
        }
    )
    assert ["--swap-distance", "8"] == command[
        command.index("--swap-distance") : command.index("--swap-distance") + 2
    ]
    assert "--step-size" not in command
    assert "--batch-size" not in command


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        ({"input_selector": "paired", "reads": ["R1.fq"], "subsample_type": "num_reads", "num": 1}, "exactly 2"),
        ({"input_selector": "single", "reads": "r.fq", "subsample_type": "coverage", "coverage": 10}, "genome_size"),
        ({"input_selector": "single", "reads": "r.fq", "subsample_type": "frac_reads", "frac": 0}, "frac"),
        ({"input_selector": "aligned", "aligned_input": "a.bam", "coverage": 4.5}, "integer"),
        (
            {"input_selector": "aligned", "aligned_input": "/data/a.bam", "coverage": 5, "strategy": "fetch"},
            "aligned_input_index",
        ),
        (
            {
                "input_selector": "single",
                "reads": "reads.fa.gz",
                "subsample_type": "num_reads",
                "num": 1,
                "output_ext": "fastq.gz",
            },
            "truthful FASTQ",
        ),
        (
            {
                "input_selector": "single",
                "reads": "reads.fastq.gz",
                "subsample_type": "num_reads",
                "num": 1,
                "output_ext": "fastq.gz",
                "compress_type": "u",
            },
            "match output_ext",
        ),
        (
            {
                "input_selector": "paired",
                "reads": ["R1.fastq.gz", "R2.fastq.bz2"],
                "subsample_type": "num_reads",
                "num": 1,
            },
            "different compression",
        ),
    ],
)
def test_rasusa_invalid_contracts_fail_closed(inputs: dict[str, Any], message: str) -> None:
    validation = RasusaNode.VALIDATE_INPUTS(inputs)
    assert validation is not True
    assert message in str(validation)


@pytest.mark.asyncio
async def test_rasusa_fake_aligned_execution_returns_explicit_mapping(tmp_path: Path) -> None:
    inputs = {
        "input_selector": "aligned",
        "aligned_input": "aligned.bam",
        "coverage": 10,
        "strategy": "stream",
    }

    class Context:
        node_dir = tmp_path / "run"

        async def run_command(self, _command: str, **_kwargs: Any) -> dict[str, Any]:
            for path in RasusaNode.PLAN_OUTPUTS(inputs, self.node_dir):
                path.write_bytes(b"synthetic")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    result = await RasusaNode().run(context=Context(), **inputs)
    assert result == {
        "outputs": {
            "subsampled_bam": str(tmp_path / "run" / "rasusa" / "subsampled.bam"),
            "subsampled_bam_index": str(tmp_path / "run" / "rasusa" / "subsampled.bam.bai"),
        }
    }
