"""Contract and mocked-execution coverage for the ViennaRNA structure family."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.builtin.rna_structure_family.adapter import RNAStructureCommandNode
from bionodulo.nodes.registry import NodeRegistry
from scripts.gen_node_index import build_index


OUTPUT = "/work/node"
FAMILY_IDS = ("rnafold_mfe", "rnafold_partition", "rnaplfold_accessibility", "rnaeval_energy")
QUERY = "GGGCUAUUAGCUCAGCUGGGAGAGCGCCUGCUUAGCACUGCA"
STRUCTURE = ".((((((..((((.....)))).(((((....))))).....))))))"
CENTROID = ".((((((..((((.....)))).(((((....))))).....)))))"

FOLD_MFE_STDOUT = f">query\n{QUERY}\n{STRUCTURE} ( -23.10)\n"

FOLD_PARTITION_STDOUT = (
    f">query\n{QUERY}\n"
    f"{STRUCTURE} ( -23.10)\n"
    f"{CENTROID} ( -22.60 = -25.80 + 3.20)\n"
    " frequency of mfe structure in ensemble 0.3245; ensemble diversity 21.42\n"
)

LUNP_SAMPLE = """#unpaired probabilities
# i   1       2
1 0.98 0.95
2 0.91 0.88
3 0.05 0.04
"""


class FakeContext:
    """Run the rendered argv while emulating the pinned tool's artifacts."""

    def __init__(self, base: Path, *, fold_stdout: str = "", lunp: bool = False) -> None:
        self.node_dir = base
        self.fold_stdout = fold_stdout
        self.lunp = lunp
        self.commands: list[list[str]] = []

    async def run_command(self, command: list[str], **kwargs: Any) -> dict[str, Any]:
        self.commands.append(list(command))
        cwd = Path(str(kwargs["cwd"]))
        stdout_path = kwargs.get("stdout_path")
        if self.fold_stdout and stdout_path is not None:
            Path(stdout_path).write_text(self.fold_stdout, encoding="utf-8")
        if self.lunp:
            (cwd / "rnaplfold_0001_lunp").write_text(LUNP_SAMPLE, encoding="utf-8")
        return {"returncode": 0, "stdout": "", "stderr": ""}


@pytest.fixture(scope="module")
def registry() -> NodeRegistry:
    result = NodeRegistry.create_isolated()
    result.load_builtin_nodes()
    return result


@pytest.mark.parametrize("node_id", FAMILY_IDS)
def test_family_contract_metadata(registry: NodeRegistry, node_id: str) -> None:
    node_class = registry.get(node_id)
    assert node_class is not None
    assert issubclass(node_class, RNAStructureCommandNode)
    assert node_class.CATEGORY == "rna_structure"
    assert "vienna-rna" in node_class.REQUIRED_CONDA_PACKAGES
    assert node_class.CITATION_DOIS == ["10.1186/1748-7182-6-26"]
    assert node_class.DOCUMENTATION_URL.startswith("https://www.tbi.univie.ac.at/RNA")
    assert node_class.EXPERIMENTAL is False
    assert node_class.SHELL is False
    assert node_class.RUN_IN_NODE_OUTPUT_DIR is True
    assert len(node_class.RETURN_TYPES) == len(node_class.RETURN_NAMES)


@pytest.mark.parametrize(
    ("node_id", "inputs", "expected"),
    [
        ("rnafold_mfe", {}, "Provide exactly one of 'fasta' or 'sequence'"),
        ("rnafold_mfe", {"fasta": "a.fa", "sequence": "AUGCUA"}, "Provide exactly one of 'fasta' or 'sequence'"),
        ("rnafold_mfe", {"sequence": ""}, "Provide exactly one of 'fasta' or 'sequence'"),
        ("rnafold_mfe", {"sequence": "AUGCXA"}, "is neither an existing FASTA file nor a valid RNA/DNA sequence"),
        ("rnafold_partition", {"sequence": "A" * 50001}, "exceeds the 50000 nt per-sequence limit"),
        ("rnafold_mfe", {"sequence": "AUGCUA", "temperature": 200.0}, "Input 'temperature' must be at most 100"),
        ("rnafold_mfe", {"sequence": "AUGCUA", "threads": 0}, "Input 'threads' must be at least 1"),
        ("rnafold_mfe", {"sequence": "AUGCUA", "no_lp": "yes"}, "Input 'no_lp' must be a boolean"),
        ("rnaplfold_accessibility", {"sequence": "AUGCUA", "max_span": 200}, "Input 'max_span' must not exceed 'window_size'"),
        (
            "rnaeval_energy",
            {"sequence": "AUGCUA", "structure": "(((("},
            "Input 'structure' length must equal 'sequence' length",
        ),
        (
            "rnaeval_energy",
            {"sequence": "AUGCUA", "structure": "(((xxx"},
            "Input 'structure' contains non dot-bracket characters",
        ),
    ],
)
def test_family_validation_rejects_bad_inputs(
    registry: NodeRegistry,
    node_id: str,
    inputs: dict[str, object],
    expected: str,
) -> None:
    node_class = registry.get(node_id)
    assert node_class is not None
    validation = node_class.VALIDATE_INPUTS(dict(inputs))
    assert validation is not True
    assert expected in str(validation)


def test_family_valid_inputs_pass(registry: NodeRegistry, tmp_path: Path) -> None:
    fasta = tmp_path / "seq.fa"
    fasta.write_text(f">x\n{QUERY}\n", encoding="utf-8")
    assert registry.get("rnafold_mfe").VALIDATE_INPUTS({"fasta": str(fasta)}) is True  # type: ignore[union-attr]
    assert registry.get("rnafold_partition").VALIDATE_INPUTS({"sequence": QUERY}) is True  # type: ignore[union-attr]
    assert registry.get("rnaplfold_accessibility").VALIDATE_INPUTS({"sequence": QUERY}) is True  # type: ignore[union-attr]


def test_rnafold_mfe_renders_verified_argv(registry: NodeRegistry, tmp_path: Path) -> None:
    node_class = registry.get("rnafold_mfe")
    assert node_class is not None
    fasta = tmp_path / "input.fasta"
    fasta.write_text(f">query\n{QUERY}\n", encoding="utf-8")
    assert node_class.render_command({"fasta": str(fasta), "output": OUTPUT}) == [
        "RNAfold",
        "--noPS",
        "-T",
        "37.0",
        "-i",
        str(fasta),
    ]
    assert node_class.render_command(
        {
            "sequence": QUERY,
            "temperature": 25.5,
            "no_lp": True,
            "max_bp_span": 150,
            "threads": 4,
            "output": OUTPUT,
        }
    ) == [
        "RNAfold",
        "--noPS",
        "--noLP",
        "--maxBPspan",
        "150",
        "--jobs",
        "4",
        "-T",
        "25.5",
        "-i",
        str(Path(OUTPUT) / "rnafold_mfe" / "input.fasta"),
    ]


def test_rnafold_partition_renders_verified_argv(registry: NodeRegistry, tmp_path: Path) -> None:
    node_class = registry.get("rnafold_partition")
    assert node_class is not None
    fasta = tmp_path / "input.fa"
    fasta.write_text(f">query\n{QUERY}\n", encoding="utf-8")
    assert node_class.render_command({"fasta": str(fasta), "output": OUTPUT}) == [
        "RNAfold",
        "--noPS",
        "-p",
        "-T",
        "37.0",
        "-i",
        str(fasta),
    ]


def test_rnaplfold_renders_verified_argv(registry: NodeRegistry) -> None:
    node_class = registry.get("rnaplfold_accessibility")
    assert node_class is not None
    assert node_class.render_command({"sequence": QUERY, "output": OUTPUT}) == [
        "RNAplfold",
        "-W",
        "120",
        "-L",
        "80",
        "-u",
        "25",
        "--auto-id",
        "--id-prefix=rnaplfold",
        str(Path(OUTPUT) / "rnaplfold_accessibility" / "input.fasta"),
    ]


def test_rnaeval_renders_verified_argv(registry: NodeRegistry) -> None:
    node_class = registry.get("rnaeval_energy")
    assert node_class is not None
    assert node_class.render_command({"sequence": QUERY, "structure": "." * len(QUERY), "output": OUTPUT}) == [
        "RNAeval",
        "-T",
        "37.0",
        "-i",
        str(Path(OUTPUT) / "rnaeval_energy" / "input.txt"),
    ]


@pytest.mark.asyncio
async def test_rnafold_mfe_run_parses_stdout_into_artifacts(tmp_path: Path, registry: NodeRegistry) -> None:
    node_class = registry.get("rnafold_mfe")
    assert node_class is not None
    context = FakeContext(tmp_path, fold_stdout=FOLD_MFE_STDOUT)
    result = await node_class().run(context=context, output_dir=tmp_path, sequence=QUERY)
    node_out = tmp_path / "rnafold_mfe"
    assert result == (
        str(node_out / "fold_stdout.txt"),
        str(node_out / "structure.dbn"),
        str(node_out / "energies.json"),
        str(node_out / "per_record.tsv"),
    )
    per_record = (node_out / "per_record.tsv").read_text(encoding="utf-8").splitlines()
    assert per_record[0] == "id\tmfe"
    assert per_record[1].startswith("query\t-23.1")
    dbn = (node_out / "structure.dbn").read_text(encoding="utf-8").splitlines()
    assert dbn[0] == ">query"
    assert dbn[1] == QUERY
    assert set(dbn[2]) <= set(".()")
    payload = json.loads((node_out / "energies.json").read_text(encoding="utf-8"))
    assert payload["mode"] == "mfe"
    assert payload["record_count"] == 1
    assert payload["records"][0]["mfe_kcal_mol"] == pytest.approx(-23.10)
    assert payload["records"][0]["structure"] == dbn[2]
    assert (node_out / "input.fasta").read_text(encoding="utf-8").startswith(">rnafold_mfe\n")
    assert context.commands[0][:2] == ["RNAfold", "--noPS"]


@pytest.mark.asyncio
async def test_rnafold_partition_run_captures_ensemble_statistics(tmp_path: Path, registry: NodeRegistry) -> None:
    node_class = registry.get("rnafold_partition")
    assert node_class is not None
    context = FakeContext(tmp_path, fold_stdout=FOLD_PARTITION_STDOUT)
    result = await node_class().run(context=context, output_dir=tmp_path, sequence=QUERY)
    node_out = tmp_path / "rnafold_partition"
    assert result[2] == str(node_out / "ensemble.json")
    payload = json.loads((node_out / "ensemble.json").read_text(encoding="utf-8"))
    record = payload["records"][0]
    assert record["mfe"]["energy_kcal_mol"] == pytest.approx(-23.10)
    assert record["centroid"]["energy_kcal_mol"] == pytest.approx(-22.60)
    assert record["centroid"]["distance"] == pytest.approx(-25.80)
    assert record["centroid"]["correction"] == pytest.approx(3.20)
    assert record["frequency_of_mfe"] == pytest.approx(0.3245)
    assert record["ensemble_diversity"] == pytest.approx(21.42)
    dbn = (node_out / "structure.dbn").read_text(encoding="utf-8").splitlines()
    assert dbn[2] == STRUCTURE
    assert dbn[3] == CENTROID
    assert context.commands[0][2] == "-p"


@pytest.mark.asyncio
async def test_rnaplfold_run_renames_tool_output_and_summarizes(tmp_path: Path, registry: NodeRegistry) -> None:
    node_class = registry.get("rnaplfold_accessibility")
    assert node_class is not None
    context = FakeContext(tmp_path, lunp=True)
    result = await node_class().run(
        context=context,
        output_dir=tmp_path,
        sequence=QUERY,
        window_size=20,
        max_span=15,
    )
    node_out = tmp_path / "rnaplfold_accessibility"
    assert result == (str(node_out / "accessibility.lunp"), str(node_out / "accessibility.json"))
    assert not (node_out / "rnaplfold_0001_lunp").exists()
    payload = json.loads((node_out / "accessibility.json").read_text(encoding="utf-8"))
    assert payload["window_size"] == 20
    assert payload["max_span"] == 15
    assert payload["position_count"] == 3
    assert payload["per_position"][0] == {
        "position": 1,
        "p_unpaired": pytest.approx(0.98),
        "mean_p_unpaired": pytest.approx(0.965),
    }
    assert context.commands[0][:7] == ["RNAplfold", "-W", "20", "-L", "15", "-u", "25"]


@pytest.mark.asyncio
async def test_rnaeval_run_writes_energy_json(tmp_path: Path, registry: NodeRegistry) -> None:
    node_class = registry.get("rnaeval_energy")
    assert node_class is not None
    context = FakeContext(tmp_path, fold_stdout=f"{QUERY}\n{'.' * len(QUERY)} ( -18.70)\n")
    result = await node_class().run(context=context, output_dir=tmp_path, sequence=QUERY, structure="." * len(QUERY))
    node_out = tmp_path / "rnaeval_energy"
    assert result == (str(node_out / "eval_stdout.txt"), str(node_out / "energy.json"))
    payload = json.loads((node_out / "energy.json").read_text(encoding="utf-8"))
    assert payload["energy_kcal_mol"] == pytest.approx(-18.70)
    assert payload["length"] == len(QUERY)
    staged = (node_out / "input.txt").read_text(encoding="utf-8").splitlines()
    assert staged == [QUERY, "." * len(QUERY)]


@pytest.mark.asyncio
async def test_rnaplfold_rejects_multi_record_fasta(tmp_path: Path, registry: NodeRegistry) -> None:
    node_class = registry.get("rnaplfold_accessibility")
    assert node_class is not None
    fasta = tmp_path / "two.fa"
    fasta.write_text(">a\nGGGCUAUUAGCUCAGCUGGG\n>b\nGGGCUAUUAGCUCAGCUGGG\n", encoding="utf-8")
    with pytest.raises(ValueError, match="exactly one sequence"):
        await node_class().run(context=FakeContext(tmp_path), output_dir=tmp_path, fasta=str(fasta))


@pytest.mark.asyncio
async def test_rnafold_mfe_fails_without_structure_line(tmp_path: Path, registry: NodeRegistry) -> None:
    node_class = registry.get("rnafold_mfe")
    assert node_class is not None
    context = FakeContext(tmp_path, fold_stdout=">query\nGGGCUA\n")
    with pytest.raises(ValueError, match="no structure line"):
        await node_class().run(context=context, output_dir=tmp_path, sequence="GGGCUA")


def test_rna_structure_ids_are_owned_by_focused_modules() -> None:
    index = build_index()
    family = {node_id: module for node_id, module in index.items() if node_id in FAMILY_IDS}
    assert set(family) == set(FAMILY_IDS)
    assert all(module.startswith("bionodulo.nodes.builtin.rna_structure_family.") for module in family.values())
