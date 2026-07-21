from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE, PACKAGE_MIN_VERSIONS
from bionodulo.nodes.builtin.phylogeny_family.iqtree import IQTREENode
from bionodulo.nodes.builtin.phylogeny_family.mafft import MAFFTNode
from bionodulo.nodes.registry import NodeRegistry


def test_focused_phylogeny_nodes_are_source_pinned_and_discoverable() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    assert registry.get("mafft") is MAFFTNode
    assert MAFFTNode.VERSION == "7.525"
    assert MAFFTNode.SOURCE_SHA256 == "2876f4adc1a2de4ed206bc40896763bf208bf1a02bda52f8bfdd91cf52d73e4a"
    assert MAFFTNode.CONDA_PACKAGE_CONSTRAINTS == {"mafft": "7.525"}
    assert MAFFTNode.SOURCE_AUTHORITIES["argv_parser"] == "core/mafft.tmpl"
    assert MAFFTNode.AUDIT_STATUS == "contract-checked-no-binary-execution"
    assert registry.get("iqtree") is IQTREENode
    assert IQTREENode.VERSION == "2.3.4"
    assert IQTREENode.GIT_COMMIT == "33b2ab64cfa3a42364a175752ede881bfe5daf05"
    assert IQTREENode.GIT_TAG == "v2.3.4"
    assert IQTREENode.CONDA_PACKAGE_CONSTRAINTS == {"iqtree": "2.3.4"}
    assert IQTREENode.PACKAGE_CONSTRAINTS == ("iqtree=2.3.4",)
    assert IQTREENode.SOURCE_AUTHORITIES["argv_and_bounds"] == "utils/tools.cpp:parseArg"
    assert IQTREENode.AUDIT_STATUS == "contract-checked-no-binary-execution"
    assert EXECUTABLE_TO_CONDA_PACKAGE["mafft"] == "mafft"
    assert PACKAGE_MIN_VERSIONS["mafft"] == "7.525"
    assert EXECUTABLE_TO_CONDA_PACKAGE["iqtree2"] == "iqtree"
    assert PACKAGE_MIN_VERSIONS["iqtree"] == "2.3.4"


def test_mafft_renders_documented_strategies_and_captures_stdout(tmp_path: Path) -> None:
    assert MAFFTNode.render_command(
        {"input": "sequences.fa", "threads": 8, "strategy": "linsi"}
    ) == [
        "mafft",
        "--thread",
        "8",
        "--localpair",
        "--maxiterate",
        "1000",
        "sequences.fa",
    ]
    assert MAFFTNode.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "mafft" / "alignment.fasta"]
    assert MAFFTNode.STDOUT_OUTPUT_INDEX == 0
    assert "threads=0" in MAFFTNode.DETERMINISM_SEMANTICS
    assert "captured stdout" in MAFFTNode.EXIT_SEMANTICS
    assert MAFFTNode.VALIDATE_INPUTS({"input": "sequences.fa", "threads": -1}) is True
    assert MAFFTNode.VALIDATE_INPUTS({"input": "sequences.fa", "threads": 0}) is True


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        ({"input": "", "threads": 4}, "non-empty path"),
        ({"input": "sequences.fa", "threads": -2}, "at least -1"),
        ({"input": "sequences.fa", "strategy": "--unsafe"}, "strategy"),
    ],
)
def test_mafft_rejects_inputs_outside_the_source_contract(inputs: dict[str, Any], message: str) -> None:
    assert message in str(MAFFTNode.VALIDATE_INPUTS(inputs))


def test_iqtree_renders_official_cli_and_native_treefile(tmp_path: Path) -> None:
    alignment = tmp_path / "alignment.fasta"
    alignment.write_text(">a\nAAAA\n>b\nAAAT\n", encoding="utf-8")
    inputs = {
        "alignment": str(alignment),
        "threads": 6,
        "model": "MFP",
        "ufboot_replicates": 2000,
        "alrt_replicates": 1000,
        "seed": 17,
        "output": "/work/iqtree",
    }
    assert IQTREENode.render_command(inputs) == [
        "iqtree2",
        "-s",
        str(alignment),
        "--prefix",
        "/work/iqtree/tree",
        "-m",
        "MFP",
        "-T",
        "AUTO",
        "--threads-max",
        "6",
        "--ufboot",
        "2000",
        "--alrt",
        "1000",
        "--seed",
        "17",
    ]
    assert IQTREENode.PLAN_OUTPUTS(inputs, tmp_path) == [tmp_path / "iqtree" / "tree.treefile"]
    assert IQTREENode.REQUIRED_EXECUTABLES == ["iqtree2"]


def test_iqtree_source_defaults_disable_optional_support_tests(tmp_path: Path) -> None:
    alignment = tmp_path / "alignment.fasta"
    alignment.write_text(">a\nAAAA\n>b\nAAAT\n", encoding="utf-8")
    inputs = {"alignment": alignment, "output": str(tmp_path / "out")}

    assert IQTREENode.INPUT_TYPES()["optional"]["threads"][1]["default"] == 1
    assert IQTREENode.INPUT_TYPES()["optional"]["ufboot_replicates"][1]["default"] is None
    assert IQTREENode.INPUT_TYPES()["optional"]["alrt_replicates"][1]["default"] is None
    command = IQTREENode.render_command(inputs)
    assert command == [
        "iqtree2",
        "-s",
        str(alignment),
        "--prefix",
        str(tmp_path / "out" / "tree"),
        "-m",
        "MFP",
        "-T",
        "AUTO",
        "--threads-max",
        "1",
    ]


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        ({"alignment": "a.fa", "ufboot_replicates": 999}, "at least 1000"),
        ({"alignment": "a.fa", "alrt_replicates": 500}, "0 or at least 1000"),
        ({"alignment": "a.fa", "model": ""}, "model"),
    ],
)
def test_iqtree_rejects_invalid_source_values(inputs: dict[str, Any], message: str) -> None:
    assert message in str(IQTREENode.VALIDATE_INPUTS(inputs))


def test_iqtree_rejects_unmaterialized_alignment(tmp_path: Path) -> None:
    missing = tmp_path / "missing.fasta"
    assert IQTREENode.VALIDATE_INPUTS({"alignment": missing}) == (
        f"Input 'alignment' is not a materialized file: {missing}"
    )


@pytest.mark.asyncio
async def test_iqtree_rejects_zero_exit_with_invalid_treefile(tmp_path: Path) -> None:
    alignment = tmp_path / "alignment.fasta"
    alignment.write_text(">a\nAAAA\n>b\nAAAT\n", encoding="utf-8")

    class Context:
        node_dir = tmp_path

        async def run_command(self, _command: list[str] | str, **_kwargs: object) -> dict[str, object]:
            tree = tmp_path / "iqtree" / "tree.treefile"
            tree.parent.mkdir(parents=True, exist_ok=True)
            tree.write_text("(a:0.1,b:0.2)\n", encoding="utf-8")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    with pytest.raises(RuntimeError, match="not terminated Newick"):
        await IQTREENode().run(alignment=alignment, context=Context(), output_dir=tmp_path)
