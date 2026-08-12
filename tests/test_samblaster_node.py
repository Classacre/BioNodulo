from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.builtin.alignment_family.samblaster import SamblasterNode


def test_samblaster_is_source_pinned_and_uses_samtools_not_sambamba() -> None:
    assert SamblasterNode.VERSION == "0.1.26"
    assert SamblasterNode.GIT_COMMIT == "b642639117eafedc760d8b84c0d2c4872b0da084"
    assert SamblasterNode.PACKAGE_CONSTRAINTS == ("samblaster==0.1.26", "samtools==1.23.1")
    assert SamblasterNode.REQUIRED_EXECUTABLES == ["samblaster", "samtools"]
    assert SamblasterNode.REQUIRED_CONDA_PACKAGES == ["samblaster", "samtools"]
    assert "sambamba" not in SamblasterNode.REQUIRED_EXECUTABLES
    assert SamblasterNode.UPSTREAM_SOURCE_SHA256 == (
        "e1b85dba49dc1a0b4d75854aea433a918dd16a55f16b80fc5e232aed8e449bba"
    )


def test_samblaster_renders_queryname_grouping_and_indexed_bam_outputs(tmp_path: Path) -> None:
    inputs = {
        "input": "aligned.bam",
        "output_bam": True,
        "discordantFile": True,
        "splitterFile": True,
        "unmappedFile": True,
        "acceptDupMarks": True,
        "excludeDups": True,
        "addMateTags": True,
        "compatibility_mode": True,
        "maxSplitCount": 3,
        "maxUnmappedBases": 60,
        "minIndelSize": 75,
        "minNonOverlap": 25,
        "minClipSize": 30,
        "threads": 6,
        "output": tmp_path / "samblaster",
    }
    command = SamblasterNode.render_command(inputs)
    assert command[:16] == [
        "set",
        "-o",
        "pipefail",
        "&&",
        "samtools",
        "sort",
        "-n",
        "--no-PG",
        "-@",
        "6",
        "-O",
        "sam",
        "-o",
        str(tmp_path / "samblaster" / "queryname_grouped.sam"),
        "aligned.bam",
        "&&",
    ]
    assert "sambamba" not in command
    assert command.count("samblaster") == 1
    assert command.count("samtools") == 7
    assert ["--unmappedFile", str(tmp_path / "samblaster" / "unmapped_reads.fastx")] == command[
        command.index("--unmappedFile") : command.index("--unmappedFile") + 2
    ]
    assert command.count("samtools") == command.count("index") + command.count("sort")


def test_samblaster_conditional_output_mapping_pairs_every_bam_with_bai(tmp_path: Path) -> None:
    inputs = {
        "output_bam": True,
        "discordantFile": True,
        "splitterFile": True,
        "unmappedFile": True,
    }
    planned = SamblasterNode.PLAN_OUTPUTS(inputs, tmp_path)
    assert [path.name for path in planned] == [
        "output.bam",
        "output.bam.bai",
        "discordant.bam",
        "discordant.bam.bai",
        "splitter.bam",
        "splitter.bam.bai",
        "unmapped_reads.fastx",
    ]
    assert SamblasterNode.MAP_PLANNED_OUTPUTS(planned) == {
        "alignments": planned[0],
        "alignments_index": planned[1],
        "discordant_alignments": planned[2],
        "discordant_alignments_index": planned[3],
        "split_alignments": planned[4],
        "split_alignments_index": planned[5],
        "unmapped_reads": planned[6],
    }
    assert SamblasterNode.RETURN_TYPES[-1] == "FILE"


def test_samblaster_can_suppress_primary_output_without_positional_mislabeling(tmp_path: Path) -> None:
    inputs = {"input": "aligned.sam", "output_bam": False, "splitterFile": True, "threads": 2}
    command = SamblasterNode.render_command({**inputs, "output": tmp_path / "samblaster"})
    assert ["--output", "/dev/null"] == command[command.index("--output") : command.index("--output") + 2]
    assert "output.bam" not in " ".join(command)
    planned = SamblasterNode.PLAN_OUTPUTS(inputs, tmp_path)
    assert planned == [tmp_path / "samblaster" / "splitter.bam", tmp_path / "samblaster" / "splitter.bam.bai"]
    assert SamblasterNode.MAP_PLANNED_OUTPUTS(planned) == {
        "split_alignments": planned[0],
        "split_alignments_index": planned[1],
    }


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        ({"input": ""}, "non-empty"),
        (
            {
                "input": "a.bam",
                "output_bam": False,
                "discordantFile": False,
                "splitterFile": False,
                "unmappedFile": False,
            },
            "at least one output",
        ),
        ({"input": "a.bam", "splitterFile": True, "maxSplitCount": 1}, "maxSplitCount"),
        ({"input": "a.bam", "unmappedFile": True, "minClipSize": 0}, "minClipSize"),
        ({"input": "a.bam", "threads": True}, "threads"),
    ],
)
def test_samblaster_invalid_contracts_fail_closed(inputs: dict[str, Any], message: str) -> None:
    validation = SamblasterNode.VALIDATE_INPUTS(inputs)
    assert validation is not True
    assert message in str(validation)


@pytest.mark.asyncio
async def test_samblaster_fake_execution_returns_named_conditional_outputs(tmp_path: Path) -> None:
    inputs = {"input": "aligned.bam", "output_bam": False, "splitterFile": True, "unmappedFile": True}

    class Context:
        node_dir = tmp_path / "run"

        async def run_command(self, _command: str, **_kwargs: Any) -> dict[str, Any]:
            for path in SamblasterNode.PLAN_OUTPUTS(inputs, self.node_dir):
                path.write_bytes(b"synthetic")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    result = await SamblasterNode().run(context=Context(), **inputs)
    assert result == {
        "outputs": {
            "split_alignments": str(tmp_path / "run" / "samblaster" / "splitter.bam"),
            "split_alignments_index": str(tmp_path / "run" / "samblaster" / "splitter.bam.bai"),
            "unmapped_reads": str(tmp_path / "run" / "samblaster" / "unmapped_reads.fastx"),
        }
    }
