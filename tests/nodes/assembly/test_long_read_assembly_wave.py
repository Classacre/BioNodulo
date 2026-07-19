from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.builtin.assembly_family.canu import CanuNode
from bionodulo.nodes.builtin.assembly_family.flye import FlyeNode
from bionodulo.nodes.builtin.assembly_family.unicycler import UnicyclerNode
from scripts.gen_node_index import build_index


def test_long_read_assembly_ids_have_focused_source_pinned_owners() -> None:
    expected = {
        "canu": (CanuNode, "2.3", "d2ec645cf89a7fc862dcfdf2dea5a547eba15376"),
        "flye": (FlyeNode, "2.9.6", "886b8c17412cdf3a2868a28237bca6c5ad1da156"),
        "unicycler": (UnicyclerNode, "0.5.1", "d153f67d6f626176c100724600104ade4f6d7a2e"),
    }
    live_index = build_index()
    facade = importlib.import_module("bionodulo.nodes.builtin.assembly")
    for node_id, (node, version, commit) in expected.items():
        assert live_index[node_id] == node.__module__
        assert getattr(facade, node.__name__) is node
        assert node.VERSION == version
        assert node.GIT_COMMIT == commit
        assert node.PACKAGE_CONSTRAINTS
        assert node.SHELL is False


def test_canu_renders_multiple_reads_and_native_prefix_outputs(tmp_path: Path) -> None:
    inputs = {
        "reads": ["hifi-1.fastq.gz", "hifi-2.fastq.gz"],
        "genome_size": "5m",
        "prefix": "sample",
        "read_type": "pacbio-hifi",
        "threads": 12,
        "output": tmp_path / "canu",
    }
    assert CanuNode.VALIDATE_INPUTS(inputs) is True
    assert CanuNode.render_command(inputs) == [
        "canu",
        "-p",
        "sample",
        "-d",
        str(tmp_path / "canu"),
        "genomeSize=5m",
        "-pacbio-hifi",
        "hifi-1.fastq.gz",
        "hifi-2.fastq.gz",
        "useGrid=false",
        "maxThreads=12",
    ]
    assert CanuNode.PLAN_OUTPUTS(inputs, tmp_path) == [
        tmp_path / "canu" / "sample.contigs.fasta",
        tmp_path / "canu" / "sample.unassembled.fasta",
        tmp_path / "canu" / "sample.report",
    ]
    assert all("unitig" not in path.name for path in CanuNode.PLAN_OUTPUTS(inputs, tmp_path))


@pytest.mark.parametrize("read_type", FlyeNode.READ_TYPES)
def test_flye_accepts_each_documented_read_mode(read_type: str) -> None:
    assert FlyeNode.VALIDATE_INPUTS({"reads": "reads.fastq.gz", "read_type": read_type}) is True


def test_flye_preserves_zero_polishing_iterations_and_native_outputs(tmp_path: Path) -> None:
    inputs = {
        "reads": ["ont-a.fastq.gz", "ont-b.fastq.gz"],
        "read_type": "nano-hq",
        "threads": 8,
        "iterations": 0,
        "output": tmp_path / "flye",
    }
    assert FlyeNode.render_command(inputs) == [
        "flye",
        "--nano-hq",
        "ont-a.fastq.gz",
        "ont-b.fastq.gz",
        "--out-dir",
        str(tmp_path / "flye"),
        "--threads",
        "8",
        "--iterations",
        "0",
    ]
    assert FlyeNode.PLAN_OUTPUTS(inputs, tmp_path) == [
        tmp_path / "flye" / "assembly.fasta",
        tmp_path / "flye" / "assembly_graph.gfa",
        tmp_path / "flye" / "assembly_graph.gv",
        tmp_path / "flye" / "assembly_info.txt",
        tmp_path / "flye" / "flye.log",
    ]


def test_unicycler_emits_only_flags_for_supplied_read_classes(tmp_path: Path) -> None:
    hybrid = {
        "reads": ["R1.fastq.gz", "R2.fastq.gz"],
        "unpaired": "singletons.fastq.gz",
        "long_reads": "ont.fastq.gz",
        "threads": 6,
        "mode": "conservative",
        "min_fasta_length": 250,
        "output": tmp_path / "unicycler",
    }
    assert UnicyclerNode.VALIDATE_INPUTS(hybrid) is True
    assert UnicyclerNode.render_command(hybrid) == [
        "unicycler",
        "-1",
        "R1.fastq.gz",
        "-2",
        "R2.fastq.gz",
        "-s",
        "singletons.fastq.gz",
        "-l",
        "ont.fastq.gz",
        "-o",
        str(tmp_path / "unicycler"),
        "-t",
        "6",
        "--mode",
        "conservative",
        "--min_fasta_length",
        "250",
        "--keep",
        "0",
    ]
    long_only = UnicyclerNode.render_command({"long_reads": "ont.fastq.gz", "output": tmp_path / "long"})
    assert "-1" not in long_only and "-2" not in long_only and "-s" not in long_only
    assert ["-l", "ont.fastq.gz"] == long_only[1:3]
    assert UnicyclerNode.PLAN_OUTPUTS(hybrid, tmp_path) == [
        tmp_path / "unicycler" / "assembly.fasta",
        tmp_path / "unicycler" / "assembly.gfa",
        tmp_path / "unicycler" / "unicycler.log",
    ]


@pytest.mark.parametrize(
    ("node", "inputs", "message"),
    [
        (CanuNode, {"reads": "reads.fq", "genome_size": "5m", "prefix": "../escape"}, "prefix"),
        (CanuNode, {"reads": "reads.fq", "genome_size": "5m", "prefix": "sample name"}, "whitespace"),
        (FlyeNode, {"reads": "reads.fq", "read_type": "ont"}, "read_type"),
        (FlyeNode, {"reads": "reads.fq", "read_type": "nano-hq", "iterations": 11}, "iterations"),
        (UnicyclerNode, {}, "at least one"),
        (UnicyclerNode, {"reads": ["R1.fq"]}, "exactly two"),
        (UnicyclerNode, {"r1": "R1.fq", "r2": "R2.fq", "reads": ["A", "B"]}, "either reads"),
    ],
)
def test_invalid_long_read_assembly_contracts_fail_closed(
    node: type, inputs: dict[str, Any], message: str
) -> None:
    validation = node.VALIDATE_INPUTS(inputs)
    assert validation is not True
    assert message in str(validation)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("node", "inputs", "filenames"),
    [
        (CanuNode, {"reads": "reads.fq", "genome_size": "5m"}, CanuNode.PLAN_OUTPUTS({}, Path("."))),
        (FlyeNode, {"reads": "reads.fq", "read_type": "nano-hq"}, [Path(name) for name in FlyeNode.OUTPUT_FILENAMES]),
        (UnicyclerNode, {"long_reads": "reads.fq"}, [Path(name) for name in UnicyclerNode.OUTPUT_FILENAMES]),
    ],
)
async def test_fake_execution_requires_every_native_assembly_artifact(
    tmp_path: Path, node: type, inputs: dict[str, Any], filenames: list[Path]
) -> None:
    class Context:
        node_dir = tmp_path / "run"

        async def run_command(self, _command: list[str], **_kwargs: Any) -> dict[str, Any]:
            planned = node.PLAN_OUTPUTS(inputs, self.node_dir)
            for path in planned:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("synthetic\n", encoding="ascii")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    result = await node().run(context=Context(), **inputs)
    assert result == tuple(str(path) for path in node.PLAN_OUTPUTS(inputs, tmp_path / "run"))
    assert filenames
