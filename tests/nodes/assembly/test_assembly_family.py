from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

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


PUBLIC_OUTPUTS = {
    SPAdesNode: (
        ("assembly", "ASSEMBLY", "scaffolds.fasta"),
        ("contigs", "CONTIGS", "contigs.fasta"),
        ("assembly_graph", "GFA", "assembly_graph_with_scaffolds.gfa"),
        ("assembly_graph_fastg", "FILE", "assembly_graph.fastg"),
        ("contig_paths", "FILE", "contigs.paths"),
        ("scaffold_paths", "FILE", "scaffolds.paths"),
    ),
    MEGAHITNode: (("contigs", "CONTIGS", "final.contigs.fa"),),
    QuastNode: (
        ("report", "HTML_REPORT", "report.html"),
        ("report_txt", "FILE", "report.txt"),
        ("report_tsv", "TSV", "report.tsv"),
        ("report_tex", "FILE", "report.tex"),
        ("transposed_report_txt", "FILE", "transposed_report.txt"),
        ("transposed_report_tsv", "TSV", "transposed_report.tsv"),
        ("transposed_report_tex", "FILE", "transposed_report.tex"),
        ("icarus_report", "HTML_REPORT", "icarus.html"),
    ),
}


def _materialize_runtime_inputs(tmp_path: Path, inputs: dict[str, Any]) -> dict[str, Any]:
    materialized = dict(inputs)

    def create(value: Any) -> str:
        path = tmp_path / str(value)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(">synthetic\nACGT\n", encoding="ascii")
        return str(path)

    for name in ("reads", "assembly", "reference", "gff"):
        value = materialized.get(name)
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            materialized[name] = [create(item) for item in value]
        else:
            materialized[name] = create(value)
    return materialized


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
                for filename in SPAdesNode.OUTPUT_FILENAMES:
                    (output / filename).write_text(">synthetic\nACGT\n", encoding="ascii")
            elif command[0] == "megahit":
                output = Path(command[command.index("-o") + 1])
                output.mkdir(parents=True, exist_ok=True)
                (output / "final.contigs.fa").write_text(">synthetic\nACGT\n", encoding="ascii")
            elif command[0] == "quast":
                output = Path(command[command.index("--output-dir") + 1])
                output.mkdir(parents=True, exist_ok=True)
                for filename in QuastNode.OUTPUT_FILENAMES:
                    (output / filename).write_text("synthetic\n", encoding="ascii")
        return {
            "returncode": self.returncode,
            "stdout": "",
            "stderr": "synthetic failure" if self.returncode else "",
        }


def test_assembly_ids_are_owned_by_focused_modules() -> None:
    live_index = build_index()
    expected = {
        "spades": "bionodulo.nodes.builtin.assembly_family.spades",
        "megahit": "bionodulo.nodes.builtin.assembly_family.megahit",
        "quast": "bionodulo.nodes.builtin.assembly_family.quast",
    }
    assert {node_id: live_index[node_id] for node_id in expected} == expected

    for node in (SPAdesNode, MEGAHITNode, QuastNode):
        assert node.__module__.startswith("bionodulo.nodes.builtin.assembly_family.")


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
    assert node.CONDA_PACKAGE_CONSTRAINTS == {expected["package"]: expected["version"]}
    assert node.PACKAGE_CONSTRAINTS == (f"{expected['package']}=={expected['version']}",)
    assert "non-zero" in node.EXIT_SEMANTICS
    assert node.SHELL is False


@pytest.mark.parametrize("node", [SPAdesNode, MEGAHITNode, QuastNode])
def test_assembly_public_outputs_match_pinned_source_filenames(node: type[CommandNode], tmp_path: Path) -> None:
    outputs = PUBLIC_OUTPUTS[node]
    assert node.RETURN_NAMES == tuple(name for name, _kind, _filename in outputs)
    assert node.RETURN_TYPES == tuple(kind for _name, kind, _filename in outputs)
    assert [path.name for path in node.PLAN_OUTPUTS({}, tmp_path)] == [filename for _name, _kind, filename in outputs]


def test_assembly_input_ports_preserve_documented_defaults() -> None:
    spades_inputs = SPAdesNode.INPUT_TYPES()
    assert set(spades_inputs["required"]) == {"reads", "threads"}
    assert spades_inputs["required"]["threads"][1]["default"] == 16
    assert spades_inputs["optional"]["careful"][1]["default"] is False

    megahit_inputs = MEGAHITNode.INPUT_TYPES()
    assert set(megahit_inputs["required"]) == {"reads"}
    assert megahit_inputs["optional"]["min_contig_len"][1]["default"] == 200
    assert megahit_inputs["optional"]["min_contig_len"][1]["min"] == 0
    assert megahit_inputs["optional"]["threads"][1]["min"] == 0
    assert megahit_inputs["optional"]["k_list"][1]["default"] == MEGAHITNode.DEFAULT_K_LIST

    quast_inputs = QuastNode.INPUT_TYPES()
    assert set(quast_inputs["required"]) == {"assembly"}
    assert set(quast_inputs["optional"]) == {"threads", "reference", "gff"}


def test_spades_renders_single_end_argv_and_native_outputs(tmp_path: Path) -> None:
    output = tmp_path / "spades"
    reads = tmp_path / "reads.fq.gz"
    reads.write_text("@read\nACGT\n+\n!!!!\n", encoding="ascii")
    assert SPAdesNode.render_command({"reads": reads, "threads": 16, "output": output}) == [
        "spades.py",
        "--s",
        "1",
        str(reads),
        "-o",
        str(output),
        "-t",
        "16",
    ]
    assert SPAdesNode.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "spades" / "scaffolds.fasta",
        tmp_path / "spades" / "contigs.fasta",
        tmp_path / "spades" / "assembly_graph_with_scaffolds.gfa",
        tmp_path / "spades" / "assembly_graph.fastg",
        tmp_path / "spades" / "contigs.paths",
        tmp_path / "spades" / "scaffolds.paths",
    ]


def test_spades_renders_paired_end_and_optional_flags_in_order(tmp_path: Path) -> None:
    output = tmp_path / "spades"
    r1 = tmp_path / "R1.fq.gz"
    r2 = tmp_path / "R2.fq.gz"
    r1.write_text("@read/1\nACGT\n+\n!!!!\n", encoding="ascii")
    r2.write_text("@read/2\nTGCA\n+\n!!!!\n", encoding="ascii")
    assert SPAdesNode.render_command(
        {
            "reads": [r1, r2],
            "threads": 8,
            "memory": 32,
            "careful": True,
            "output": output,
        }
    ) == [
        "spades.py",
        "-1",
        str(r1),
        "-2",
        str(r2),
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
    materialized = _materialize_runtime_inputs(tmp_path, {"reads": reads})["reads"]
    expected_materialized_inputs = [
        str(tmp_path / value) if value not in {"-r", "-1", "-2"} else value for value in expected_inputs
    ]
    assert MEGAHITNode.render_command({"reads": materialized, "output": output}) == [
        "megahit",
        *expected_materialized_inputs,
        "-o",
        str(output / "megahit_out"),
        "--min-contig-len",
        "200",
        "--k-list",
        MEGAHITNode.DEFAULT_K_LIST,
    ]
    assert MEGAHITNode.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "megahit" / "megahit_out" / "final.contigs.fa"]


def test_megahit_renders_explicit_threads_and_documented_k_list(tmp_path: Path) -> None:
    r1 = tmp_path / "R1.fq.gz"
    r2 = tmp_path / "R2.fq.gz"
    r1.write_text("@read/1\nACGT\n+\n!!!!\n", encoding="ascii")
    r2.write_text("@read/2\nTGCA\n+\n!!!!\n", encoding="ascii")
    command = MEGAHITNode.render_command(
        {
            "reads": [r1, r2],
            "threads": 6,
            "min_contig_len": 500,
            "k_list": "21,49,77",
            "output": tmp_path / "megahit",
        }
    )
    assert command == [
        "megahit",
        "-1",
        str(r1),
        "-2",
        str(r2),
        "-o",
        str(tmp_path / "megahit" / "megahit_out"),
        "--min-contig-len",
        "500",
        "--k-list",
        "21,49,77",
        "--num-cpu-threads",
        "6",
    ]


def test_megahit_preserves_source_supported_zero_auto_values(tmp_path: Path) -> None:
    reads = tmp_path / "reads.fq"
    reads.write_text("@read\nACGT\n+\n!!!!\n", encoding="ascii")
    command = MEGAHITNode.render_command(
        {"reads": reads, "threads": 0, "min_contig_len": 0, "output": tmp_path / "megahit"}
    )
    assert command[command.index("--min-contig-len") + 1] == "0"
    assert command[command.index("--num-cpu-threads") + 1] == "0"


def test_quast_renders_assemblies_reference_features_and_report_path(tmp_path: Path) -> None:
    output = tmp_path / "quast"
    contigs = tmp_path / "contigs.fa"
    scaffolds = tmp_path / "scaffolds.fa"
    reference = tmp_path / "reference.fa"
    genes = tmp_path / "genes.gff"
    for path in (contigs, scaffolds, reference, genes):
        path.write_text(">synthetic\nACGT\n", encoding="ascii")
    command = QuastNode.render_command(
        {
            "assembly": [contigs, scaffolds],
            "threads": 4,
            "reference": reference,
            "gff": genes,
            "output": output,
        }
    )
    assert command == [
        "quast",
        str(contigs),
        str(scaffolds),
        "--output-dir",
        str(output / "report_dir.out"),
        "--threads",
        "4",
        "--reference",
        str(reference),
        "--features",
        str(genes),
    ]
    assert QuastNode.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "quast" / "report_dir.out" / filename for filename in QuastNode.OUTPUT_FILENAMES
    ]


@pytest.mark.parametrize(
    ("node", "inputs", "message"),
    [
        (SPAdesNode, {"reads": [], "threads": 4}, "exactly one or two"),
        (SPAdesNode, {"reads": ["R1", "R2", "R3"], "threads": 4}, "exactly one or two"),
        (SPAdesNode, {"reads": ["R1", ""], "threads": 4}, "non-empty"),
        (SPAdesNode, {"reads": "R1", "threads": 0}, "at least 1"),
        (MEGAHITNode, {"reads": ["R1", "R2", "R3"]}, "exactly one or two"),
        (MEGAHITNode, {"reads": "R1", "threads": True}, "integer"),
        (MEGAHITNode, {"reads": "R1", "threads": -1}, "at least 0"),
        (MEGAHITNode, {"reads": "R1", "min_contig_len": -1}, "at least 0"),
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
        (SPAdesNode, {"reads": "missing.fastq", "threads": 4}, "not a materialized file"),
        (MEGAHITNode, {"reads": "missing.fastq"}, "not a materialized file"),
        (QuastNode, {"assembly": "missing.fasta"}, "not a materialized file"),
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


@pytest.mark.parametrize("name", ["reference", "gff"])
def test_quast_requires_each_supplied_optional_file_to_be_materialized(tmp_path: Path, name: str) -> None:
    assembly = tmp_path / "assembly.fasta"
    assembly.write_text(">synthetic\nACGT\n", encoding="ascii")
    missing = tmp_path / f"missing.{name}"
    validation = QuastNode.VALIDATE_INPUTS({"assembly": assembly, name: missing})
    assert validation == f"{name} path is not a materialized file: {missing}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("node", "inputs", "relative_outputs"),
    [
        (
            SPAdesNode,
            {"reads": ["R1.fq.gz", "R2.fq.gz"], "threads": 4},
            [
                "spades/scaffolds.fasta",
                "spades/contigs.fasta",
                "spades/assembly_graph_with_scaffolds.gfa",
                "spades/assembly_graph.fastg",
                "spades/contigs.paths",
                "spades/scaffolds.paths",
            ],
        ),
        (
            MEGAHITNode,
            {"reads": "reads.fq.gz"},
            ["megahit/megahit_out/final.contigs.fa"],
        ),
        (
            QuastNode,
            {"assembly": "assembly.fa"},
            [f"quast/report_dir.out/{filename}" for filename in QuastNode.OUTPUT_FILENAMES],
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
    result = await node().run(context=context, **_materialize_runtime_inputs(tmp_path, inputs))
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
        await node().run(context=context, **_materialize_runtime_inputs(tmp_path, inputs))


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
        await node().run(context=context, **_materialize_runtime_inputs(tmp_path, inputs))
