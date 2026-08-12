"""Focused Minimap2 2.30 and STAR 2.7.11b contract tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.builtin.alignment_family.minimap2_align import Minimap2AlignNode
from bionodulo.nodes.builtin.alignment_family.minimap2_index import Minimap2IndexNode
from bionodulo.nodes.builtin.alignment_family.star_adapter import STAR_INDEX_MARKERS
from bionodulo.nodes.builtin.alignment_family.star_align import STARAlignNode
from bionodulo.nodes.builtin.alignment_family.star_index import STARIndexNode
from scripts.gen_node_index import build_index


def _star_index(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    for name in STAR_INDEX_MARKERS:
        (path / name).write_text(name, encoding="ascii")
    return path


def test_minimap2_and_star_ids_have_focused_source_pinned_owners() -> None:
    index = build_index()
    expected = {
        "minimap2_index": Minimap2IndexNode,
        "minimap2_align": Minimap2AlignNode,
        "star_index": STARIndexNode,
        "star_align": STARAlignNode,
    }
    for node_id, node_class in expected.items():
        assert index[node_id] == node_class.__module__
        assert node_class.GIT_COMMIT
        assert node_class.DOCUMENTATION_URL.startswith("https://github.com/")


def test_minimap2_index_models_the_native_mmi_file(tmp_path: Path) -> None:
    inputs = {"reference": "reference.fa", "preset": "map-ont", "output": "/work/minimap2_index"}
    assert Minimap2IndexNode.VALIDATE_INPUTS(inputs) is True
    assert Minimap2IndexNode.RETURN_TYPES == ("FILE",)
    assert Minimap2IndexNode.render_command(inputs) == [
        "minimap2",
        "-x",
        "map-ont",
        "-d",
        "/work/minimap2_index/reference.mmi",
        "reference.fa",
    ]
    assert Minimap2IndexNode.PLAN_OUTPUTS(inputs, tmp_path) == [
        tmp_path / "minimap2_index" / "reference.mmi"
    ]


def test_minimap2_align_uses_native_argv_and_sam_stdout(tmp_path: Path) -> None:
    inputs = {
        "reads": "reads.fastq.gz",
        "reference": "reference.mmi",
        "preset": "map-hifi",
        "threads": 4,
    }
    assert Minimap2AlignNode.VALIDATE_INPUTS(inputs) is True
    assert Minimap2AlignNode.render_command(inputs) == [
        "minimap2",
        "-a",
        "-x",
        "map-hifi",
        "-t",
        "4",
        "reference.mmi",
        "reads.fastq.gz",
    ]
    assert Minimap2AlignNode.PLAN_OUTPUTS(inputs, tmp_path) == [
        tmp_path / "minimap2_align" / "alignment.sam"
    ]
    assert Minimap2AlignNode.STDOUT_OUTPUT_INDEX == 0
    assert Minimap2AlignNode.SHELL is False


@pytest.mark.asyncio
async def test_minimap2_fake_execution_captures_stdout(tmp_path: Path) -> None:
    class Context:
        node_dir = tmp_path / "run"
        command: list[str] | None = None
        kwargs: dict[str, Any] | None = None

        async def run_command(self, command: list[str], **kwargs: Any) -> dict[str, Any]:
            self.command = command
            self.kwargs = kwargs
            Path(kwargs["stdout_path"]).write_text("@HD\tVN:1.6\n", encoding="ascii")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    context = Context()
    result = await Minimap2AlignNode().run(
        reads="reads.fastq",
        reference="reference.fa",
        preset="sr",
        threads=2,
        context=context,
    )
    expected = tmp_path / "run" / "minimap2_align" / "alignment.sam"
    assert result == (str(expected),)
    assert context.command == ["minimap2", "-a", "-x", "sr", "-t", "2", "reference.fa", "reads.fastq"]
    assert context.kwargs == {"env": None, "cwd": tmp_path / "run", "stdout_path": expected}


def test_star_index_renders_into_the_planned_directory(tmp_path: Path) -> None:
    inputs = {
        "reference": "reference.fa",
        "gtf": "genes.gtf",
        "threads": 8,
        "genome_sa_index_nbases": 12,
        "sjdb_overhang": 149,
        "output": "/work/star_index",
    }
    assert STARIndexNode.VALIDATE_INPUTS(inputs) is True
    assert STARIndexNode.render_command(inputs) == [
        "STAR",
        "--runMode",
        "genomeGenerate",
        "--genomeDir",
        "/work/star_index/index",
        "--genomeFastaFiles",
        "reference.fa",
        "--sjdbGTFfile",
        "genes.gtf",
        "--runThreadN",
        "8",
        "--genomeSAindexNbases",
        "12",
        "--sjdbOverhang",
        "149",
    ]
    assert STARIndexNode.PLAN_OUTPUTS(inputs, tmp_path) == [tmp_path / "star_index" / "index"]


@pytest.mark.asyncio
async def test_star_index_fake_execution_requires_complete_bundle(tmp_path: Path) -> None:
    reference = tmp_path / "reference.fa"
    gtf = tmp_path / "genes.gtf"
    reference.write_text(">chr1\nACGT\n", encoding="ascii")
    gtf.write_text("chr1\ttest\tgene\t1\t4\t.\t+\t.\tgene_id \"g\";\n", encoding="ascii")

    class Context:
        node_dir = tmp_path / "run"

        async def run_command(self, command: list[str], **kwargs: Any) -> dict[str, Any]:
            index_dir = Path(command[command.index("--genomeDir") + 1])
            _star_index(index_dir)
            return {"returncode": 0, "stdout": "", "stderr": ""}

    result = await STARIndexNode().run(reference=reference, gtf=gtf, threads=1, context=Context())
    assert result == (str(tmp_path / "run" / "star_index" / "index"),)


def test_star_align_renders_paired_compressed_reads_and_actual_bam_name(tmp_path: Path) -> None:
    index_dir = _star_index(tmp_path / "index")
    inputs = {
        "reads": ["r1.fastq.gz", "r2.fastq.gz"],
        "index": index_dir,
        "threads": 6,
        "two_pass": True,
        "chim_segment_min": 12,
        "output": "/work/star_align",
    }
    assert STARAlignNode.VALIDATE_INPUTS(inputs) is True
    assert STARAlignNode.render_command(inputs) == [
        "STAR",
        "--genomeDir",
        str(index_dir),
        "--readFilesIn",
        "r1.fastq.gz",
        "r2.fastq.gz",
        "--readFilesCommand",
        "zcat",
        "--outFileNamePrefix",
        "/work/star_align/",
        "--outSAMtype",
        "BAM",
        "SortedByCoordinate",
        "--runThreadN",
        "6",
        "--twopassMode",
        "Basic",
        "--chimSegmentMin",
        "12",
    ]
    assert STARAlignNode.PLAN_OUTPUTS(inputs, tmp_path) == [
        tmp_path / "star_align" / "Aligned.sortedByCoord.out.bam"
    ]


@pytest.mark.asyncio
async def test_star_align_fake_execution_returns_native_bam(tmp_path: Path) -> None:
    index_dir = _star_index(tmp_path / "index")

    class Context:
        node_dir = tmp_path / "run"

        async def run_command(self, command: list[str], **kwargs: Any) -> dict[str, Any]:
            prefix = Path(command[command.index("--outFileNamePrefix") + 1])
            (prefix / "Aligned.sortedByCoord.out.bam").write_bytes(b"BAM")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    result = await STARAlignNode().run(
        reads=["reads.fastq"],
        index=index_dir,
        threads=1,
        two_pass=False,
        context=Context(),
    )
    assert result == (str(tmp_path / "run" / "star_align" / "Aligned.sortedByCoord.out.bam"),)


@pytest.mark.parametrize(
    ("node_class", "inputs", "message"),
    [
        (Minimap2AlignNode, {"reads": "r.fq", "reference": "r.fa", "threads": 0}, "threads must be between"),
        (Minimap2IndexNode, {"reference": "r.fa", "preset": "unknown"}, "preset must be one of"),
        (
            STARAlignNode,
            {"reads": ["r1.fastq.gz", "r2.fastq"], "index": "index", "threads": 1},
            "same compression format",
        ),
        (
            STARIndexNode,
            {"reference": "r.fa", "gtf": "g.gtf", "threads": 1, "sjdb_overhang": 0},
            "sjdb_overhang must be a positive integer",
        ),
    ],
)
def test_minimap2_and_star_contracts_fail_closed(
    node_class: type,
    inputs: dict[str, object],
    message: str,
) -> None:
    assert message in str(node_class.VALIDATE_INPUTS(inputs))
