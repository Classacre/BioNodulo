from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.command_node import CommandNode
from bionodulo.nodes.builtin.assembly_family.megahit import MEGAHITNode
from bionodulo.nodes.builtin.assembly_family.quast import QuastNode
from bionodulo.nodes.builtin.assembly_family.spades import SPAdesNode
from scripts.gen_node_index import build_index


PINNED = {
    SPAdesNode: {
        "node_id": "spades",
        "version": "4.2.0",
        "package": "spades",
        "executable": "spades.py",
        "url": "https://github.com/ablab/spades.git",
        "commit": "7fee3c1050a732faef8a0d93d70861015a96f44e",
        "documentation": "https://github.com/ablab/spades/tree/v4.2.0",
    },
    MEGAHITNode: {
        "node_id": "megahit",
        "version": "1.2.9",
        "package": "megahit",
        "executable": "megahit",
        "url": "https://github.com/voutcn/megahit.git",
        "commit": "d729cca1e201ca16749b67f750b0bc5465c9a990",
        "documentation": "https://github.com/voutcn/megahit/blob/v1.2.9/README.md",
    },
    QuastNode: {
        "node_id": "quast",
        "version": "5.3.0",
        "package": "quast",
        "executable": "quast",
        "url": "https://github.com/ablab/quast.git",
        "commit": "c3eb988a2fa8a815e1b0bfff55a58cb8d6ff0152",
        "documentation": "https://github.com/ablab/quast/tree/quast_5.3.0",
    },
}


class _FakeContext:
    def __init__(self, node_dir: Path, returncode: int = 0, create_outputs: bool = True) -> None:
        self.node_dir = node_dir
        self.returncode = returncode
        self.create_outputs = create_outputs
        self.calls: list[tuple[list[str], dict[str, Any]]] = []

    async def run_command(self, command: list[str], **kwargs: Any) -> dict[str, Any]:
        self.calls.append((command, kwargs))
        if self.returncode == 0 and self.create_outputs:
            if command[0] == "spades.py":
                output = Path(command[command.index("-o") + 1])
                output.mkdir(parents=True, exist_ok=True)
                for filename in ("scaffolds.fasta", "contigs.fasta"):
                    (output / filename).write_text(">synthetic\nACGT\n", encoding="ascii")
            elif command[0] == "megahit":
                output = Path(command[command.index("-o") + 1])
                output.mkdir(parents=True, exist_ok=True)
                (output / "final.contigs.fa").write_text(">synthetic\nACGT\n", encoding="ascii")
            elif command[0] == "quast":
                output = Path(command[command.index("--output-dir") + 1])
                output.mkdir(parents=True, exist_ok=True)
                (output / "report.html").write_text("<html>synthetic</html>\n", encoding="ascii")
        return {
            "returncode": self.returncode,
            "stdout": "",
            "stderr": "synthetic failure" if self.returncode else "",
        }


def test_assembly_ids_are_owned_by_focused_modules_and_legacy_aliases_resolve() -> None:
    live_index = build_index()
    expected = {
        "spades": "bionodulo.nodes.builtin.assembly_family.spades",
        "megahit": "bionodulo.nodes.builtin.assembly_family.megahit",
        "quast": "bionodulo.nodes.builtin.assembly_family.quast",
    }
    assert {node_id: live_index[node_id] for node_id in expected} == expected

    legacy = importlib.import_module("bionodulo.nodes.builtin.assembly")
    assert legacy.SPAdesNode is SPAdesNode
    assert legacy.MEGAHITNode is MEGAHITNode
    assert legacy.QuastNode is QuastNode
    for node in (SPAdesNode, MEGAHITNode, QuastNode):
        assert node.__module__.startswith("bionodulo.nodes.builtin.assembly_family.")

    legacy_ids = {
        obj.NODE_ID
        for _name, obj in inspect.getmembers(legacy, inspect.isclass)
        if issubclass(obj, BaseNode) and obj not in {BaseNode, CommandNode} and obj.__module__ == legacy.__name__
    }
    assert not {"spades", "megahit", "quast"} & legacy_ids


@pytest.mark.parametrize("node,expected", list(PINNED.items()))
def test_assembly_contracts_are_pinned_to_audited_releases(node: type[CommandNode], expected: dict[str, str]) -> None:
    assert node.NODE_ID == expected["node_id"]
    assert node.VERSION == expected["version"]
    assert node.BIOCONDA_VERSION == expected["version"]
    assert node.REQUIRED_CONDA_PACKAGES == [expected["package"]]
    assert node.REQUIRED_EXECUTABLES == [expected["executable"]]
    assert node.GIT_URL == expected["url"]
    assert node.GIT_COMMIT == expected["commit"]
    assert node.DOCUMENTATION_URL == expected["documentation"]
    assert node.SHELL is False


def test_assembly_input_ports_preserve_documented_defaults() -> None:
    spades_inputs = SPAdesNode.INPUT_TYPES()
    assert set(spades_inputs["required"]) == {"reads", "threads"}
    assert spades_inputs["required"]["threads"][1]["default"] == 16
    assert spades_inputs["optional"]["careful"][1]["default"] is False

    megahit_inputs = MEGAHITNode.INPUT_TYPES()
    assert set(megahit_inputs["required"]) == {"reads"}
    assert megahit_inputs["optional"]["min_contig_len"][1]["default"] == 200
    assert megahit_inputs["optional"]["k_list"][1]["default"] == MEGAHITNode.DEFAULT_K_LIST

    quast_inputs = QuastNode.INPUT_TYPES()
    assert set(quast_inputs["required"]) == {"assembly"}
    assert set(quast_inputs["optional"]) == {"threads", "reference", "gff"}


def test_spades_renders_single_end_argv_and_native_outputs(tmp_path: Path) -> None:
    output = tmp_path / "spades"
    assert SPAdesNode.render_command({"reads": "reads.fq.gz", "threads": 16, "output": output}) == [
        "spades.py",
        "-s",
        "reads.fq.gz",
        "-o",
        str(output),
        "-t",
        "16",
    ]
    assert SPAdesNode.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "spades" / "scaffolds.fasta",
        tmp_path / "spades" / "contigs.fasta",
    ]


def test_spades_renders_paired_end_and_optional_flags_in_order(tmp_path: Path) -> None:
    output = tmp_path / "spades"
    assert SPAdesNode.render_command(
        {
            "reads": ["R1.fq.gz", "R2.fq.gz"],
            "threads": 8,
            "memory": 32,
            "careful": True,
            "output": output,
        }
    ) == [
        "spades.py",
        "-1",
        "R1.fq.gz",
        "-2",
        "R2.fq.gz",
        "-o",
        str(output),
        "-t",
        "8",
        "-m",
        "32",
        "--careful",
    ]


@pytest.mark.parametrize(
    ("reads", "expected_inputs"),
    [
        ("reads.fq.gz", ["-r", "reads.fq.gz"]),
        (["R1.fq.gz", "R2.fq.gz"], ["-1", "R1.fq.gz", "-2", "R2.fq.gz"]),
    ],
)
def test_megahit_renders_single_or_paired_reads_with_nested_native_output(
    tmp_path: Path, reads: Any, expected_inputs: list[str]
) -> None:
    output = tmp_path / "megahit"
    assert MEGAHITNode.render_command({"reads": reads, "output": output}) == [
        "megahit",
        *expected_inputs,
        "-o",
        str(output / "megahit_out"),
        "--min-contig-len",
        "200",
        "--k-list",
        MEGAHITNode.DEFAULT_K_LIST,
    ]
    assert MEGAHITNode.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "megahit" / "megahit_out" / "final.contigs.fa"]


def test_megahit_renders_explicit_threads_and_documented_k_list(tmp_path: Path) -> None:
    command = MEGAHITNode.render_command(
        {
            "reads": ["R1.fq.gz", "R2.fq.gz"],
            "threads": 6,
            "min_contig_len": 500,
            "k_list": "21,49,77",
            "output": tmp_path / "megahit",
        }
    )
    assert command == [
        "megahit",
        "-1",
        "R1.fq.gz",
        "-2",
        "R2.fq.gz",
        "-o",
        str(tmp_path / "megahit" / "megahit_out"),
        "--min-contig-len",
        "500",
        "--k-list",
        "21,49,77",
        "--num-cpu-threads",
        "6",
    ]


def test_quast_renders_assemblies_reference_features_and_report_path(tmp_path: Path) -> None:
    output = tmp_path / "quast"
    command = QuastNode.render_command(
        {
            "assembly": ["contigs.fa", "scaffolds.fa"],
            "threads": 4,
            "reference": Path("reference.fa"),
            "gff": Path("genes.gff"),
            "output": output,
        }
    )
    assert command == [
        "quast",
        "contigs.fa",
        "scaffolds.fa",
        "--output-dir",
        str(output / "report_dir.out"),
        "--threads",
        "4",
        "--reference",
        "reference.fa",
        "--features",
        "genes.gff",
    ]
    assert QuastNode.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "quast" / "report_dir.out" / "report.html"]


@pytest.mark.parametrize(
    ("node", "inputs", "message"),
    [
        (SPAdesNode, {"reads": [], "threads": 4}, "exactly one or two"),
        (SPAdesNode, {"reads": ["R1", "R2", "R3"], "threads": 4}, "exactly one or two"),
        (SPAdesNode, {"reads": ["R1", ""], "threads": 4}, "non-empty"),
        (SPAdesNode, {"reads": "R1", "threads": 0}, "at least 1"),
        (MEGAHITNode, {"reads": ["R1", "R2", "R3"]}, "exactly one or two"),
        (MEGAHITNode, {"reads": "R1", "threads": True}, "integer"),
        (MEGAHITNode, {"reads": "R1", "k_list": ""}, "non-empty"),
        (MEGAHITNode, {"reads": "R1", "k_list": "twenty-nine"}, "only integers"),
        (MEGAHITNode, {"reads": "R1", "k_list": "14,29"}, "between 15 and 255"),
        (MEGAHITNode, {"reads": "R1", "k_list": "21,257"}, "between 15 and 255"),
        (MEGAHITNode, {"reads": "R1", "k_list": "20,29"}, "odd"),
        (MEGAHITNode, {"reads": "R1", "k_list": "21,51,81"}, "at most 28"),
        (QuastNode, {"assembly": [], "threads": 4}, "at least one"),
        (QuastNode, {"assembly": "contigs.fa", "threads": 0}, "at least 1"),
        (QuastNode, {"assembly": "contigs.fa", "reference": ["a.fa", "b.fa"]}, "exactly one"),
        (QuastNode, {"assembly": "contigs.fa", "gff": ["a.gff", "b.gff"]}, "exactly one"),
    ],
)
def test_invalid_assembly_values_fail_before_command_rendering(
    node: type[CommandNode], inputs: dict[str, Any], message: str
) -> None:
    validation = node.VALIDATE_INPUTS(inputs)
    assert validation is not True
    assert message in str(validation)
    with pytest.raises(ValueError, match=message):
        node.render_command(inputs)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("node", "inputs", "relative_outputs"),
    [
        (
            SPAdesNode,
            {"reads": ["R1.fq.gz", "R2.fq.gz"], "threads": 4},
            ["spades/scaffolds.fasta", "spades/contigs.fasta"],
        ),
        (
            MEGAHITNode,
            {"reads": "reads.fq.gz"},
            ["megahit/megahit_out/final.contigs.fa"],
        ),
        (
            QuastNode,
            {"assembly": "assembly.fa"},
            ["quast/report_dir.out/report.html"],
        ),
    ],
)
async def test_fake_execution_returns_native_planned_outputs(
    tmp_path: Path,
    node: type[CommandNode],
    inputs: dict[str, Any],
    relative_outputs: list[str],
) -> None:
    context = _FakeContext(tmp_path)
    result = await node().run(context=context, **inputs)
    assert result == tuple(str(tmp_path / relative) for relative in relative_outputs)
    assert len(context.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "node,inputs",
    [
        (SPAdesNode, {"reads": "reads.fq.gz", "threads": 4}),
        (MEGAHITNode, {"reads": "reads.fq.gz"}),
        (QuastNode, {"assembly": "assembly.fa"}),
    ],
)
async def test_nonzero_assembly_exit_is_reported_as_runtime_failure(
    tmp_path: Path, node: type[CommandNode], inputs: dict[str, Any]
) -> None:
    context = _FakeContext(tmp_path, returncode=7)
    with pytest.raises(RuntimeError, match=r"Command failed \(exit 7\)"):
        await node().run(context=context, **inputs)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "node,inputs",
    [
        (SPAdesNode, {"reads": "reads.fq.gz", "threads": 4}),
        (MEGAHITNode, {"reads": "reads.fq.gz"}),
        (QuastNode, {"assembly": "assembly.fa"}),
    ],
)
async def test_zero_exit_without_native_artifacts_fails_closed(
    tmp_path: Path, node: type[CommandNode], inputs: dict[str, Any]
) -> None:
    context = _FakeContext(tmp_path, create_outputs=False)
    with pytest.raises(RuntimeError, match="did not create expected output"):
        await node().run(context=context, **inputs)
