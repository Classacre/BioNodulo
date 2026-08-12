from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any

import pytest

from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin.alignment_family.adapter import (
    BWA_INDEX_SUFFIXES,
    find_index_prefix,
)
from bionodulo.nodes.builtin.alignment_family.index import BWAIndexNode
from bionodulo.nodes.builtin.alignment_family.index_dir import BWAIndexDirNode
from bionodulo.nodes.builtin.alignment_family.mem import BWAMemNode
from bionodulo.nodes.registry import NodeRegistry
from scripts.gen_node_index import build_index


PINNED_COMMIT = "b92993c1161e73167181558856567ef2f367e3f0"


def _bundle(directory: Path, name: str = "reference.fa", *, alt: bool = False) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    prefix = directory / name
    prefix.write_text(">chr1\nACGT\n", encoding="ascii")
    for suffix in BWA_INDEX_SUFFIXES:
        Path(f"{prefix}{suffix}").write_bytes(suffix.encode("ascii"))
    if alt:
        Path(f"{prefix}.alt").write_text("chr1\n", encoding="ascii")
    return prefix


def _native_bundle(directory: Path, name: str = "native-prefix") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    prefix = directory / name
    for suffix in BWA_INDEX_SUFFIXES:
        Path(f"{prefix}{suffix}").write_bytes(suffix.encode("ascii"))
    return prefix


@pytest.mark.parametrize(
    ("module_name", "class_name", "node_id", "source"),
    [
        ("index", "BWAIndexNode", "bwa_index", "bwtindex.c"),
        ("mem", "BWAMemNode", "bwa_mem", "fastmap.c"),
    ],
)
def test_documented_bwa_operations_are_source_pinned(
    module_name: str,
    class_name: str,
    node_id: str,
    source: str,
) -> None:
    module = importlib.import_module(f"bionodulo.nodes.builtin.alignment_family.{module_name}")
    node = getattr(module, class_name)

    assert node.NODE_ID == node_id
    assert node.__module__ == module.__name__
    assert node.VERSION == "0.7.19"
    assert node.GIT_URL == "https://github.com/lh3/bwa.git"
    assert node.GIT_COMMIT == PINNED_COMMIT
    assert node.REQUIRED_EXECUTABLES == ["bwa"]
    assert node.REQUIRED_CONDA_PACKAGES == ["bwa"]
    assert node.SHELL is False
    assert node.UPSTREAM_MANPAGE == "bwa.1"
    assert node.UPSTREAM_SOURCE == source
    assert node.GIT_TAG == "v0.7.19"
    assert node.PACKAGE_CONSTRAINTS == ("bwa==0.7.19",)
    assert all(PINNED_COMMIT in url for url in node.SOURCE_URLS)


def test_live_discovery_assigns_each_stable_id_to_its_focused_module() -> None:
    live_index = build_index()

    assert live_index["bwa_index"] == "bionodulo.nodes.builtin.alignment_family.index"
    assert live_index["bwa_mem"] == "bionodulo.nodes.builtin.alignment_family.mem"
    assert live_index["bwa_index_dir"] == ("bionodulo.nodes.builtin.alignment_family.index_dir")


def test_index_contract_uses_auto_by_default_and_exact_documented_algorithms(
    tmp_path: Path,
) -> None:
    outputs = BWAIndexNode.PLAN_OUTPUTS({}, tmp_path)
    reference = outputs[0] / "reference.fa"

    assert outputs == [tmp_path / "bwa_index" / "index"]
    assert BWAIndexNode.RETURN_TYPES == ("INDEX_DIR",)
    assert BWAIndexNode.RETURN_NAMES == ("indexed_reference",)
    assert BWAIndexNode.INPUT_TYPES()["optional"]["algorithm"][1] == {
        "default": "auto",
        "options": ["auto", "is", "bwtsw", "rb2"],
        "description": "BWT construction algorithm; auto lets BWA choose by reference size",
    }
    assert BWAIndexNode.render_command({"reference": reference, "algorithm": "auto"}) == [
        "bwa",
        "index",
        "-p",
        str(reference),
        str(reference),
    ]
    assert BWAIndexNode.render_command({"reference": reference, "algorithm": "is"}) == [
        "bwa",
        "index",
        "-a",
        "is",
        "-p",
        str(reference),
        str(reference),
    ]


@pytest.mark.parametrize("algorithm", ["auto", "is", "bwtsw", "rb2"])
def test_index_accepts_only_upstream_algorithms(algorithm: str) -> None:
    assert BWAIndexNode.VALIDATE_INPUTS({"reference": "reference.fa", "algorithm": algorithm}) is True
    assert (
        BWAIndexNode.VALIDATE_INPUTS({"reference": "reference.fa", "algorithm": "div"})
        == "algorithm must be one of: auto, is, bwtsw, rb2"
    )


def test_index_preparation_stages_the_reference_at_the_output_prefix(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source genome.fa"
    source.write_text(">chr1\nACGT\n", encoding="ascii")
    outputs = BWAIndexNode.PLAN_OUTPUTS({}, tmp_path / "run")
    inputs: dict[str, Any] = {"reference": source, "algorithm": "auto"}

    BWAIndexNode.PREPARE_EXECUTION(inputs, outputs)

    staged = outputs[0] / "reference.fa"
    assert inputs["reference"] == str(staged)
    assert staged.read_bytes() == source.read_bytes()
    assert os.path.samefile(source, staged)


@pytest.mark.asyncio
async def test_index_fake_execution_requires_and_returns_the_complete_bundle(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.fa"
    source.write_text(">chr1\nACGT\n", encoding="ascii")

    class Context:
        node_dir = tmp_path / "run"
        command: list[str] | None = None

        async def run_command(self, command: list[str], **_kwargs: Any) -> dict[str, Any]:
            self.command = command
            prefix = Path(command[command.index("-p") + 1])
            for suffix in BWA_INDEX_SUFFIXES:
                Path(f"{prefix}{suffix}").write_bytes(suffix.encode("ascii"))
            return {"returncode": 0, "stdout": "", "stderr": ""}

    context = Context()
    result = await BWAIndexNode().run(
        reference=source,
        algorithm="auto",
        context=context,
    )

    assert result == (str(tmp_path / "run" / "bwa_index" / "index"),)
    assert context.command == [
        "bwa",
        "index",
        "-p",
        str(tmp_path / "run" / "bwa_index" / "index" / "reference.fa"),
        str(tmp_path / "run" / "bwa_index" / "index" / "reference.fa"),
    ]
    assert find_index_prefix(result[0]).name == "reference.fa"


@pytest.mark.asyncio
async def test_index_fails_closed_when_a_zero_exit_did_not_create_sidecars(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.fa"
    source.write_text(">chr1\nACGT\n", encoding="ascii")

    class Context:
        node_dir = tmp_path / "run"

        async def run_command(self, _command: list[str], **_kwargs: Any) -> dict[str, Any]:
            return {"returncode": 0, "stdout": "", "stderr": ""}

    with pytest.raises(FileNotFoundError, match="no complete colocated prefix"):
        await BWAIndexNode().run(reference=source, context=Context())


@pytest.mark.parametrize("missing_suffix", BWA_INDEX_SUFFIXES)
def test_bundle_validation_rejects_every_missing_required_sidecar(
    tmp_path: Path,
    missing_suffix: str,
) -> None:
    prefix = _bundle(tmp_path / "index")
    Path(f"{prefix}{missing_suffix}").unlink()

    with pytest.raises(FileNotFoundError, match="no complete colocated prefix"):
        find_index_prefix(prefix.parent)


def test_bundle_validation_rejects_ambiguous_prefixes(tmp_path: Path) -> None:
    directory = tmp_path / "index"
    _bundle(directory, "one.fa")
    _bundle(directory, "two.fa")

    with pytest.raises(ValueError, match="multiple complete prefixes"):
        find_index_prefix(directory)


def test_bundle_validation_rejects_zero_byte_native_members(tmp_path: Path) -> None:
    prefix = _bundle(tmp_path / "index")
    Path(f"{prefix}.sa").write_bytes(b"")

    with pytest.raises(FileNotFoundError, match="no complete colocated prefix"):
        find_index_prefix(prefix.parent)


def test_bundle_validation_models_bwa_64_prefix_inference(tmp_path: Path) -> None:
    directory = tmp_path / "index"
    directory.mkdir()
    reference = directory / "reference.fa"
    reference.write_text(">chr1\nACGT\n", encoding="ascii")
    prefix = Path(f"{reference}.64")
    for suffix in BWA_INDEX_SUFFIXES:
        Path(f"{prefix}{suffix}").write_bytes(suffix.encode("ascii"))

    assert find_index_prefix(directory) == prefix


def test_mem_renders_exact_single_and_paired_argv_without_a_shell(tmp_path: Path) -> None:
    index_dir = tmp_path / "index bundle"
    prefix = _bundle(index_dir)
    output = tmp_path / "output dir"

    assert BWAMemNode.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "bwa_mem" / "alignment.sam"]
    assert BWAMemNode.render_command(
        {
            "reads": ["single reads.fastq.gz"],
            "reference": index_dir,
            "threads": 1,
            "output": output,
        }
    ) == [
        "bwa",
        "mem",
        "-t",
        "1",
        "-T",
        "30",
        "-o",
        str(output / "alignment.sam"),
        str(prefix),
        "single reads.fastq.gz",
    ]
    assert BWAMemNode.render_command(
        {
            "reads": ["r1.fq.gz", "r2.fq.gz"],
            "reference": index_dir,
            "threads": 8,
            "read_group": "@RG\\tID:sample-1\\tSM:tumor\\tPL:ILLUMINA",
            "min_score": 42,
            "mark_shorter_splits": True,
            "output": output,
        }
    ) == [
        "bwa",
        "mem",
        "-t",
        "8",
        "-R",
        "@RG\\tID:sample-1\\tSM:tumor\\tPL:ILLUMINA",
        "-T",
        "42",
        "-M",
        "-o",
        str(output / "alignment.sam"),
        str(prefix),
        "r1.fq.gz",
        "r2.fq.gz",
    ]


@pytest.mark.asyncio
async def test_mem_dry_run_uses_the_upstream_planned_index_prefix(
    tmp_path: Path,
) -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    workflow = {
        "name": "BWA dry-run contract",
        "nodes": [
            {
                "id": "index",
                "type": "bwa_index",
                "params": {"reference": "/inputs/reference.fa"},
            },
            {
                "id": "mem",
                "type": "bwa_mem",
                "params": {
                    "reads": ["/inputs/R1.fastq.gz", "/inputs/R2.fastq.gz"],
                    "threads": 2,
                },
            },
        ],
        "edges": [
            {
                "id": "index-to-mem",
                "from": {"node": "index", "output": "indexed_reference"},
                "to": {"node": "mem", "input": "reference"},
            }
        ],
    }

    executor = WorkflowExecutor(
        workspace_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        registry=registry,
    )
    preview = await executor.dry_run("bwa-preview", workflow)

    mem_plan = next(node for node in preview["nodes"] if node["node_id"] == "mem")
    planned_prefix = tmp_path / "runs" / "bwa-preview" / "index" / "bwa_index" / "index" / "reference.fa"
    assert mem_plan["command"][-3:] == [
        str(planned_prefix),
        "/inputs/R1.fastq.gz",
        "/inputs/R2.fastq.gz",
    ]


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"reads": []}, "reads must contain one single-end FASTQ"),
        ({"reads": ["1.fq", "2.fq", "3.fq"]}, "reads must contain one single-end FASTQ"),
        ({"threads": True}, "threads must be an integer"),
        ({"threads": 0}, "threads must be at least 1"),
        ({"read_group": "ID:x"}, "read_group must start with @RG"),
        (
            {"read_group": "@RG\tID:x"},
            "read_group must use escaped \\t separators",
        ),
        (
            {"read_group": "@RG\\tSM:x"},
            "read_group must contain an ID field",
        ),
        ({"mark_shorter_splits": "yes"}, "must be a boolean"),
    ],
)
def test_mem_rejects_invalid_layout_and_exposed_options(
    tmp_path: Path,
    updates: dict[str, Any],
    message: str,
) -> None:
    inputs: dict[str, Any] = {
        "reads": ["reads.fq.gz"],
        "reference": _bundle(tmp_path / "index").parent,
        "threads": 1,
    }
    inputs.update(updates)

    assert message in str(BWAMemNode.VALIDATE_INPUTS(inputs))


def test_mem_accepts_native_bundle_without_fasta_and_unbounded_upstream_ints(tmp_path: Path) -> None:
    prefix = _native_bundle(tmp_path / "native")
    inputs = {
        "reads": ["reads.fq.gz"],
        "reference": prefix.parent,
        "threads": 128,
        "min_score": -1,
        "output": tmp_path / "out",
    }

    assert BWAMemNode.INPUT_TYPES()["required"]["threads"][1] == {"default": 1, "min": 1}
    assert BWAMemNode.VALIDATE_INPUTS(inputs) is True
    command = BWAMemNode.render_command(inputs)
    assert command[0:4] == ["bwa", "mem", "-t", "128"]
    assert command[command.index("-T") : command.index("-T") + 2] == ["-T", "-1"]
    assert str(prefix) in command


@pytest.mark.asyncio
async def test_mem_fake_execution_uses_native_output_option(tmp_path: Path) -> None:
    index_dir = _bundle(tmp_path / "index").parent

    class Context:
        node_dir = tmp_path / "run"
        command: list[str] | None = None
        kwargs: dict[str, Any] | None = None

        async def run_command(
            self,
            command: list[str],
            **kwargs: Any,
        ) -> dict[str, Any]:
            self.command = command
            self.kwargs = kwargs
            output = Path(command[command.index("-o") + 1])
            output.write_text("@HD\tVN:1.6\n", encoding="ascii")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    context = Context()
    result = await BWAMemNode().run(
        reads=["r1.fq.gz", "r2.fq.gz"],
        reference=index_dir,
        threads=2,
        context=context,
    )

    assert result == (str(tmp_path / "run" / "bwa_mem" / "alignment.sam"),)
    assert context.command is not None
    assert ">" not in context.command
    assert context.command[0:4] == ["bwa", "mem", "-t", "2"]
    assert context.kwargs == {
        "env": None,
        "cwd": tmp_path / "run",
    }


def test_index_dir_is_a_non_tool_import_adapter() -> None:
    assert issubclass(BWAIndexDirNode, BaseNode)
    assert BWAIndexDirNode.REQUIRES_EXTERNAL_TOOLS is False
    assert BWAIndexDirNode.REQUIRED_EXECUTABLES == []
    assert BWAIndexDirNode.REQUIRED_CONDA_PACKAGES == []
    assert BWAIndexDirNode.GIT_COMMIT == PINNED_COMMIT
    assert "import adapter" in BWAIndexDirNode.__doc__


@pytest.mark.asyncio
async def test_index_dir_adapter_canonicalizes_complete_bundle_and_optional_alt(
    tmp_path: Path,
) -> None:
    source_prefix = _bundle(tmp_path / "source", "custom-prefix", alt=True)

    result = await BWAIndexDirNode().run(
        index_dir=source_prefix.parent,
        output_dir=tmp_path / "run",
    )

    target_dir = tmp_path / "run" / "bwa_index_dir" / "index"
    target_prefix = target_dir / "reference.fa"
    assert result == (str(target_dir),)
    assert find_index_prefix(target_dir) == target_prefix
    assert target_prefix.read_bytes() == source_prefix.read_bytes()
    assert Path(f"{target_prefix}.alt").read_text(encoding="ascii") == "chr1\n"


@pytest.mark.asyncio
async def test_index_dir_adapter_accepts_native_sidecars_without_source_fasta(tmp_path: Path) -> None:
    source_prefix = _native_bundle(tmp_path / "source")

    result = await BWAIndexDirNode().run(
        index_dir=source_prefix.parent,
        output_dir=tmp_path / "run",
    )

    target_dir = tmp_path / "run" / "bwa_index_dir" / "index"
    target_prefix = target_dir / "reference.fa"
    assert result == (str(target_dir),)
    assert not target_prefix.exists()
    assert find_index_prefix(target_dir, require_reference=False) == target_prefix


@pytest.mark.asyncio
async def test_index_dir_adapter_rejects_partial_directory(tmp_path: Path) -> None:
    partial = tmp_path / "partial"
    partial.mkdir()
    (partial / "reference.fa.bwt").write_bytes(b"bwt")

    with pytest.raises(ValueError, match="no complete sibling prefix"):
        await BWAIndexDirNode().run(index_dir=partial, output_dir=tmp_path / "run")
