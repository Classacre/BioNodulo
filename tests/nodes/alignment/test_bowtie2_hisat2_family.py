from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.builtin.alignment_family.bowtie2_adapter import (
    BOWTIE2_LARGE_SUFFIXES,
    BOWTIE2_SMALL_SUFFIXES,
    BOWTIE2_SUFFIX_FAMILIES,
)
from bionodulo.nodes.builtin.alignment_family.bowtie2_align import Bowtie2AlignNode
from bionodulo.nodes.builtin.alignment_family.bowtie2_build import Bowtie2BuildNode
from bionodulo.nodes.builtin.alignment_family.bowtie2_inspect import Bowtie2IndexNode
from bionodulo.nodes.builtin.alignment_family.fm_index_bundle import (
    find_index_bundle,
    planned_or_complete_prefix,
)
from bionodulo.nodes.builtin.alignment_family.hisat2_adapter import (
    HISAT2_LARGE_SUFFIXES,
    HISAT2_SMALL_SUFFIXES,
    HISAT2_SUFFIX_FAMILIES,
)
from bionodulo.nodes.builtin.alignment_family.hisat2_align import HISAT2AlignNode
from bionodulo.nodes.builtin.alignment_family.hisat2_build import HISAT2BuildNode
from scripts.gen_node_index import build_index


BOWTIE2_COMMIT = "0c6a1c75e047ad8bf70c178fa3cb1528fba6adc2"
HISAT2_COMMIT = "99583d7536b9ee017ac07de8834017a3bf99a2fe"


def _bundle(directory: Path, suffixes: tuple[str, ...], name: str = "index") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    prefix = directory / name
    for suffix in suffixes:
        Path(f"{prefix}{suffix}").write_bytes(suffix.encode("ascii"))
    return prefix


def _read(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("@r1\nACGT\n+\nIIII\n", encoding="ascii")
    return path


@pytest.mark.parametrize(
    ("module_name", "class_name", "node_id", "version", "commit", "executable", "wrapper", "source"),
    [
        (
            "bowtie2_build",
            "Bowtie2BuildNode",
            "bowtie2_build",
            "2.5.5",
            BOWTIE2_COMMIT,
            "bowtie2-build",
            "bowtie2-build",
            "bt2_build.cpp",
        ),
        (
            "bowtie2_align",
            "Bowtie2AlignNode",
            "bowtie2_align",
            "2.5.5",
            BOWTIE2_COMMIT,
            "bowtie2",
            "bowtie2",
            "bt2_search.cpp",
        ),
        (
            "bowtie2_inspect",
            "Bowtie2IndexNode",
            "bowtie2_inspect",
            "2.5.5",
            BOWTIE2_COMMIT,
            "bowtie2-inspect",
            "bowtie2-inspect",
            "bt2_inspect.cpp",
        ),
        (
            "hisat2_build",
            "HISAT2BuildNode",
            "hisat2_build",
            "2.2.2",
            HISAT2_COMMIT,
            "hisat2-build",
            "hisat2-build",
            "hisat2_build.cpp",
        ),
        (
            "hisat2_align",
            "HISAT2AlignNode",
            "hisat2_align",
            "2.2.2",
            HISAT2_COMMIT,
            "hisat2",
            "hisat2",
            "hisat2.cpp",
        ),
    ],
)
def test_operations_are_source_pinned_in_focused_modules(
    module_name: str,
    class_name: str,
    node_id: str,
    version: str,
    commit: str,
    executable: str,
    wrapper: str,
    source: str,
) -> None:
    module = importlib.import_module(f"bionodulo.nodes.builtin.alignment_family.{module_name}")
    node = getattr(module, class_name)

    assert node.NODE_ID == node_id
    assert node.__module__ == module.__name__
    assert node.VERSION == version
    assert node.GIT_COMMIT == commit
    assert node.REQUIRED_EXECUTABLES == [executable]
    assert node.REQUIRED_CONDA_PACKAGES == [node_id.split("_")[0]]
    assert node.UPSTREAM_WRAPPER == wrapper
    assert node.UPSTREAM_SOURCE == source
    assert node.SHELL is False


def test_discovery_and_legacy_imports_resolve_to_focused_classes() -> None:
    live_index = build_index()
    legacy = importlib.import_module("bionodulo.nodes.builtin.alignment")

    assert live_index["bowtie2_build"] == "bionodulo.nodes.builtin.alignment_family.bowtie2_build"
    assert live_index["bowtie2_align"] == "bionodulo.nodes.builtin.alignment_family.bowtie2_align"
    assert live_index["bowtie2_inspect"] == "bionodulo.nodes.builtin.alignment_family.bowtie2_inspect"
    assert live_index["hisat2_build"] == "bionodulo.nodes.builtin.alignment_family.hisat2_build"
    assert live_index["hisat2_align"] == "bionodulo.nodes.builtin.alignment_family.hisat2_align"
    assert legacy.Bowtie2BuildNode is Bowtie2BuildNode
    assert legacy.Bowtie2AlignNode is Bowtie2AlignNode
    assert legacy.Bowtie2IndexNode is Bowtie2IndexNode
    assert legacy.HISAT2BuildNode is HISAT2BuildNode
    assert legacy.HISAT2AlignNode is HISAT2AlignNode


@pytest.mark.parametrize(
    ("node", "expected_prefix"),
    [
        (Bowtie2BuildNode, ["bowtie2-build", "--threads"]),
        (HISAT2BuildNode, ["hisat2-build", "-p"]),
    ],
)
def test_build_contract_uses_upstream_thread_default_and_planned_prefix(
    tmp_path: Path,
    node: type[Bowtie2BuildNode] | type[HISAT2BuildNode],
    expected_prefix: list[str],
) -> None:
    reference = _read(tmp_path / "reference.fa")
    output = tmp_path / "run"

    assert node.INPUT_TYPES()["required"]["threads"][1] == {"default": 1, "min": 1, "max": 64}
    assert node.PLAN_OUTPUTS({}, output) == [output / node.NODE_ID / "index"]
    assert node.render_command({"reference": reference, "threads": 1, "output": output / node.NODE_ID}) == [
        *expected_prefix,
        "1",
        str(reference),
        str(output / node.NODE_ID / "index" / "index"),
    ]
    assert node.VALIDATE_INPUTS({"reference": reference, "threads": 1}) is True
    assert node.VALIDATE_INPUTS({"reference": reference, "threads": True}) == "threads must be an integer"


@pytest.mark.parametrize(
    ("node", "suffixes"),
    [
        (Bowtie2BuildNode, BOWTIE2_SMALL_SUFFIXES),
        (HISAT2BuildNode, HISAT2_SMALL_SUFFIXES),
    ],
)
@pytest.mark.asyncio
async def test_build_fake_execution_returns_only_a_complete_bundle(
    tmp_path: Path,
    node: type[Bowtie2BuildNode] | type[HISAT2BuildNode],
    suffixes: tuple[str, ...],
) -> None:
    reference = _read(tmp_path / "reference.fa")

    class Context:
        node_dir = tmp_path / "run"
        command: list[str] | None = None

        async def run_command(self, command: list[str], **_kwargs: Any) -> dict[str, Any]:
            self.command = command
            prefix = Path(command[-1])
            prefix.parent.mkdir(parents=True, exist_ok=True)
            for suffix in suffixes:
                Path(f"{prefix}{suffix}").write_bytes(suffix.encode("ascii"))
            return {"returncode": 0, "stdout": "", "stderr": ""}

    context = Context()
    result = await node().run(reference=reference, threads=1, context=context)

    assert result == (str(tmp_path / "run" / node.NODE_ID / "index"),)
    assert context.command is not None
    assert context.command[-1] == str(tmp_path / "run" / node.NODE_ID / "index" / "index")


@pytest.mark.parametrize(
    "node",
    [Bowtie2BuildNode, HISAT2BuildNode],
)
@pytest.mark.asyncio
async def test_build_fails_closed_when_zero_exit_created_no_index_members(
    tmp_path: Path,
    node: type[Bowtie2BuildNode] | type[HISAT2BuildNode],
) -> None:
    reference = _read(tmp_path / "reference.fa")

    class Context:
        node_dir = tmp_path / "run"

        async def run_command(self, _command: list[str], **_kwargs: Any) -> dict[str, Any]:
            return {"returncode": 0, "stdout": "", "stderr": ""}

    with pytest.raises(FileNotFoundError, match="no complete sibling prefix"):
        await node().run(reference=reference, threads=1, context=Context())


@pytest.mark.parametrize(
    ("label", "families", "suffixes"),
    [
        ("Bowtie2", BOWTIE2_SUFFIX_FAMILIES, BOWTIE2_SMALL_SUFFIXES),
        ("Bowtie2", BOWTIE2_SUFFIX_FAMILIES, BOWTIE2_LARGE_SUFFIXES),
        ("HISAT2", HISAT2_SUFFIX_FAMILIES, HISAT2_SMALL_SUFFIXES),
        ("HISAT2", HISAT2_SUFFIX_FAMILIES, HISAT2_LARGE_SUFFIXES),
    ],
)
def test_bundle_resolution_accepts_each_documented_index_format(
    tmp_path: Path,
    label: str,
    families: tuple[tuple[str, ...], ...],
    suffixes: tuple[str, ...],
) -> None:
    prefix = _bundle(tmp_path / "bundle", suffixes, "reference")

    assert find_index_bundle(tmp_path / "bundle", label=label, suffix_families=families).prefix == prefix
    assert planned_or_complete_prefix(tmp_path / "bundle", label=label, suffix_families=families) == prefix


@pytest.mark.parametrize(
    ("label", "families", "suffixes"),
    [
        ("Bowtie2", BOWTIE2_SUFFIX_FAMILIES, BOWTIE2_SMALL_SUFFIXES),
        ("HISAT2", HISAT2_SUFFIX_FAMILIES, HISAT2_SMALL_SUFFIXES),
    ],
)
def test_bundle_resolution_rejects_partial_and_ambiguous_directories(
    tmp_path: Path,
    label: str,
    families: tuple[tuple[str, ...], ...],
    suffixes: tuple[str, ...],
) -> None:
    partial = _bundle(tmp_path / "partial", suffixes)
    Path(f"{partial}{suffixes[-1]}").unlink()
    with pytest.raises(FileNotFoundError, match="no complete sibling prefix"):
        find_index_bundle(partial.parent, label=label, suffix_families=families)
    with pytest.raises(FileNotFoundError, match="no complete sibling prefix"):
        planned_or_complete_prefix(partial.parent, label=label, suffix_families=families)

    ambiguous = tmp_path / "ambiguous"
    _bundle(ambiguous, suffixes, "one")
    _bundle(ambiguous, suffixes, "two")
    with pytest.raises(ValueError, match="multiple complete prefixes"):
        find_index_bundle(ambiguous, label=label, suffix_families=families)


@pytest.mark.parametrize(
    ("node", "label", "families"),
    [
        (Bowtie2AlignNode, "Bowtie2", BOWTIE2_SUFFIX_FAMILIES),
        (HISAT2AlignNode, "HISAT2", HISAT2_SUFFIX_FAMILIES),
    ],
)
def test_align_contract_uses_upstream_defaults_and_dry_run_prefix(
    tmp_path: Path,
    node: type[Bowtie2AlignNode] | type[HISAT2AlignNode],
    label: str,
    families: tuple[tuple[str, ...], ...],
) -> None:
    inputs = node.INPUT_TYPES()
    planned = tmp_path / "future-index"

    assert "reads" in inputs["required"]
    assert "r1" not in inputs["optional"]
    assert "r2" not in inputs["optional"]
    assert inputs["required"]["threads"][1] == {"default": 1, "min": 1, "max": 64}
    assert inputs["optional"]["rg_id"][1]["default"] == ""
    assert inputs["optional"]["rg_sample"][1]["default"] == ""
    assert planned_or_complete_prefix(planned, label=label, suffix_families=families) == planned / "index"

    command = node.render_command(
        {"reads": ["reads.fastq"], "index": planned, "threads": 1, "output": tmp_path / "out"}
    )
    assert command[command.index("-x") + 1] == str(planned / "index")
    assert command[-2:] == ["-S", str(tmp_path / "out" / "alignment.sam")]


def test_bowtie2_renders_exact_single_and_paired_argv(tmp_path: Path) -> None:
    index_dir = _bundle(tmp_path / "index bundle", BOWTIE2_SMALL_SUFFIXES).parent
    output = tmp_path / "output"

    assert Bowtie2AlignNode.render_command(
        {"reads": ["single.fastq"], "index": index_dir, "threads": 1, "output": output}
    ) == [
        "bowtie2",
        "-p",
        "1",
        "-x",
        str(index_dir / "index"),
        "-U",
        "single.fastq",
        "-S",
        str(output / "alignment.sam"),
    ]
    assert Bowtie2AlignNode.render_command(
        {
            "reads": ["r1.fastq.gz", "r2.fastq.gz"],
            "index": index_dir,
            "threads": 8,
            "rg_id": "sample-1",
            "rg_sample": "tumor",
            "very_sensitive": True,
            "no_mixed": True,
            "output": output,
        }
    ) == [
        "bowtie2",
        "-p",
        "8",
        "-x",
        str(index_dir / "index"),
        "--rg-id",
        "sample-1",
        "--rg",
        "SM:tumor",
        "--very-sensitive",
        "--no-mixed",
        "-1",
        "r1.fastq.gz",
        "-2",
        "r2.fastq.gz",
        "-S",
        str(output / "alignment.sam"),
    ]


def test_hisat2_renders_exact_single_and_paired_argv(tmp_path: Path) -> None:
    index_dir = _bundle(tmp_path / "index bundle", HISAT2_SMALL_SUFFIXES).parent
    output = tmp_path / "output"

    assert HISAT2AlignNode.INPUT_TYPES()["optional"]["dta"][1]["default"] is False
    assert HISAT2AlignNode.render_command(
        {"reads": ["single.fastq"], "index": index_dir, "threads": 1, "output": output}
    ) == [
        "hisat2",
        "-p",
        "1",
        "-x",
        str(index_dir / "index"),
        "-U",
        "single.fastq",
        "-S",
        str(output / "alignment.sam"),
    ]
    assert HISAT2AlignNode.render_command(
        {
            "reads": ["r1.fastq.gz", "r2.fastq.gz"],
            "index": index_dir,
            "threads": 8,
            "rg_id": "sample-1",
            "rg_sample": "tumor",
            "dta": True,
            "no_softclip": True,
            "output": output,
        }
    ) == [
        "hisat2",
        "-p",
        "8",
        "-x",
        str(index_dir / "index"),
        "--rg-id",
        "sample-1",
        "--rg",
        "SM:tumor",
        "--dta",
        "--no-softclip",
        "-1",
        "r1.fastq.gz",
        "-2",
        "r2.fastq.gz",
        "-S",
        str(output / "alignment.sam"),
    ]


def test_bowtie2_inspect_uses_validated_prefix_and_stdout_capture(tmp_path: Path) -> None:
    index_dir = _bundle(tmp_path / "index bundle", BOWTIE2_LARGE_SUFFIXES, "genome").parent
    planned = tmp_path / "planned-index"

    assert Bowtie2IndexNode.STDOUT_OUTPUT_INDEX == 0
    assert Bowtie2IndexNode.RETURN_TYPES == ("FASTA",)
    assert Bowtie2IndexNode.RETURN_NAMES == ("reference",)
    assert Bowtie2IndexNode.PLAN_OUTPUTS({}, tmp_path / "run") == [
        tmp_path / "run" / "bowtie2_inspect" / "reference.fasta"
    ]
    assert Bowtie2IndexNode.render_command({"index": index_dir}) == [
        "bowtie2-inspect",
        str(index_dir / "genome"),
    ]
    assert Bowtie2IndexNode.render_command({"index": planned}) == [
        "bowtie2-inspect",
        str(planned / "index"),
    ]
    assert Bowtie2IndexNode.VALIDATE_INPUTS({"index": index_dir}) is True


@pytest.mark.asyncio
async def test_bowtie2_inspect_fake_execution_captures_fasta_without_shell(tmp_path: Path) -> None:
    index_dir = _bundle(tmp_path / "index", BOWTIE2_SMALL_SUFFIXES).parent

    class Context:
        node_dir = tmp_path / "run"
        command: list[str] | None = None
        kwargs: dict[str, Any] | None = None

        async def run_command(self, command: list[str], **kwargs: Any) -> dict[str, Any]:
            self.command = command
            self.kwargs = kwargs
            stdout_path = Path(kwargs["stdout_path"])
            stdout_path.write_text(">chr1\nACGT\n", encoding="ascii")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    context = Context()
    result = await Bowtie2IndexNode().run(index=index_dir, context=context)

    expected = tmp_path / "run" / "bowtie2_inspect" / "reference.fasta"
    assert result == (str(expected),)
    assert expected.read_text(encoding="ascii") == ">chr1\nACGT\n"
    assert context.command == ["bowtie2-inspect", str(index_dir / "index")]
    assert context.kwargs == {"env": None, "cwd": tmp_path / "run", "stdout_path": expected}


@pytest.mark.parametrize(
    ("node", "suffixes"),
    [
        (Bowtie2AlignNode, BOWTIE2_SMALL_SUFFIXES),
        (HISAT2AlignNode, HISAT2_SMALL_SUFFIXES),
    ],
)
def test_align_validation_rejects_invalid_layout_threads_and_read_groups(
    tmp_path: Path,
    node: type[Bowtie2AlignNode] | type[HISAT2AlignNode],
    suffixes: tuple[str, ...],
) -> None:
    index_dir = _bundle(tmp_path / "index", suffixes).parent
    read = _read(tmp_path / "reads.fastq")
    base: dict[str, Any] = {"reads": [read], "index": index_dir, "threads": 1}

    assert "one single-end FASTQ" in str(node.VALIDATE_INPUTS({**base, "reads": []}))
    assert "one single-end FASTQ" in str(node.VALIDATE_INPUTS({**base, "reads": [read, read, read]}))
    assert node.VALIDATE_INPUTS({**base, "threads": True}) == "threads must be an integer"
    assert node.VALIDATE_INPUTS({**base, "threads": 0}) == "threads must be between 1 and 64"
    assert "requires rg_id" in str(node.VALIDATE_INPUTS({**base, "rg_sample": "sample"}))
    assert "tabs or newlines" in str(node.VALIDATE_INPUTS({**base, "rg_id": "bad\tid"}))

    if node is Bowtie2AlignNode:
        assert node.VALIDATE_INPUTS({**base, "no_mixed": True}) == ("no_mixed is only valid for paired-end reads")


@pytest.mark.asyncio
async def test_bowtie2_fake_execution_uses_native_sam_output(tmp_path: Path) -> None:
    index_dir = _bundle(tmp_path / "index", BOWTIE2_SMALL_SUFFIXES).parent
    read = _read(tmp_path / "reads.fastq")

    class Context:
        node_dir = tmp_path / "run"
        command: list[str] | None = None

        async def run_command(self, command: list[str], **_kwargs: Any) -> dict[str, Any]:
            self.command = command
            output = Path(command[command.index("-S") + 1])
            output.write_text("@HD\tVN:1.6\n", encoding="ascii")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    context = Context()
    result = await Bowtie2AlignNode().run(reads=[read], index=index_dir, threads=1, context=context)

    assert result == (str(tmp_path / "run" / "bowtie2_align" / "alignment.sam"),)
    assert context.command is not None
    assert ">" not in context.command
    assert context.command[-2] == "-S"


@pytest.mark.asyncio
async def test_hisat2_fake_execution_stages_space_safe_inputs(tmp_path: Path) -> None:
    source_prefix = _bundle(tmp_path / "index bundle", HISAT2_SMALL_SUFFIXES, "genome prefix")
    read1 = _read(tmp_path / "source reads" / "read one.fastq.gz")
    read2 = _read(tmp_path / "source reads" / "read two.fastq.gz")

    class Context:
        node_dir = tmp_path / "run with spaces"
        command: list[str] | None = None
        staged_reads_match = False
        staged_index_matches = False

        async def run_command(self, command: list[str], **_kwargs: Any) -> dict[str, Any]:
            self.command = command
            index_prefix = Path(command[command.index("-x") + 1])
            staged_r1 = Path(command[command.index("-1") + 1])
            staged_r2 = Path(command[command.index("-2") + 1])
            output = Path(command[command.index("-S") + 1])

            assert all(" " not in str(path) for path in (index_prefix, staged_r1, staged_r2, output))
            self.staged_reads_match = os.path.samefile(staged_r1, read1) and os.path.samefile(staged_r2, read2)
            self.staged_index_matches = os.path.samefile(
                Path(f"{index_prefix}{HISAT2_SMALL_SUFFIXES[0]}"),
                Path(f"{source_prefix}{HISAT2_SMALL_SUFFIXES[0]}"),
            )
            output.write_text("@HD\tVN:1.6\n", encoding="ascii")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    context = Context()
    result = await HISAT2AlignNode().run(
        reads=[read1, read2],
        index=source_prefix.parent,
        threads=2,
        context=context,
    )

    assert result == (str(tmp_path / "run with spaces" / "hisat2_align" / "alignment.sam"),)
    assert context.command is not None
    assert context.staged_reads_match is True
    assert context.staged_index_matches is True
