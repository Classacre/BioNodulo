"""Contract tests for the lineardesign_optimize wrapper (no network, mocked subprocess)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.nodes.builtin.codon_design_family.lineardesign_optimize import (
    DEFAULT_COMMIT,
    LinearDesignOptimizeNode,
    build_command,
    parse_lineardesign_stdout,
)

PROTEIN = "MNDTEAI"
CDS_WITH_STOP = "ATGAATGATACGGAAGCCATCTAA"
CDS_NO_STOP = "ATGAATGATACGGAAGCCATC"
README_STDOUT = (
    "mRNA sequence:  AUGAACGAUACGGAGGCGAUC\n"
    "mRNA structure: ......(((.((....)))))\n"
    "mRNA folding free energy: -1.10 kcal/mol; mRNA CAI: 0.695\n"
)
MULTI_STDOUT = (
    ">seq1\n"
    "mRNA sequence:  AUGCCAAACACCCUGGCAUGCCCC\n"
    "mRNA structure: ((((((.......)))))).....\n"
    "mRNA folding free energy: -6.00 kcal/mol; mRNA CAI: 0.910\n"
    ">seq2\n"
    "mRNA sequence:  AUGCUGGAUCAGGUGAACAAGCUGAAGUACCCAGAGGUGAGCCUGACCUGA\n"
    "mRNA structure: .....((.((((((..((...(((.......)))..))..))))))))...\n"
    "mRNA folding free energy: -13.50 kcal/mol; mRNA CAI: 0.979\n"
)


def context_at(base: Path) -> SimpleNamespace:
    return SimpleNamespace(node_dir=base)


class FakeCompleted:
    def __init__(self, stdout: str, returncode: int = 0, stderr: str = "") -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


def fake_checkout(tmp_path: Path) -> Path:
    checkout = tmp_path / "ld"
    checkout.mkdir()
    (checkout / "lineardesign").write_text("#!/bin/sh\n", encoding="utf-8")
    return checkout


def test_build_command_mirrors_readme_usage() -> None:
    binary = Path("/opt/LinearDesign/lineardesign")
    assert build_command(binary, 3.0) == [str(binary), "--lambda", "3.0"]
    assert build_command(binary, 0.3)[2] == "0.3"
    assert DEFAULT_COMMIT == "f0126ca89a8b853088b4bccfd2cc8c378d3678be"


def test_parse_lineardesign_stdout_single_and_multi_record() -> None:
    single = parse_lineardesign_stdout(README_STDOUT)
    assert single == [
        {
            "id": "seq1",
            "cds": "ATGAACGATACGGAGGCGATC",
            "structure": "......(((.((....)))))",
            "mfe_kcal_mol": -1.10,
            "cai": 0.695,
        }
    ]
    multi = parse_lineardesign_stdout(MULTI_STDOUT)
    assert [record["id"] for record in multi] == ["seq1", "seq2"]
    assert multi[1]["cds"].startswith("ATGCTGGAT")
    assert multi[1]["mfe_kcal_mol"] == -13.50
    with pytest.raises(ValueError, match="no designed mRNA sequence"):
        parse_lineardesign_stdout("unexpected output\n")


def test_validate_inputs_contract() -> None:
    ok = LinearDesignOptimizeNode.VALIDATE_INPUTS({"cds": CDS_WITH_STOP})
    assert ok is True
    assert (
        LinearDesignOptimizeNode.VALIDATE_INPUTS({"cds": ""})
        == "Input 'cds' must be a non-empty sequence or file path"
    )
    assert "divisible by 3" in str(LinearDesignOptimizeNode.VALIDATE_INPUTS({"cds": "ATGGGCA"}))
    assert "invalid characters" in str(LinearDesignOptimizeNode.VALIDATE_INPUTS({"cds": "ATGGGCTAX"}))
    assert "lambda_param' must be at most" in str(
        LinearDesignOptimizeNode.VALIDATE_INPUTS({"cds": CDS_WITH_STOP, "lambda_param": 99999.0})
    )
    assert "gc_target' must be at most 1" in str(
        LinearDesignOptimizeNode.VALIDATE_INPUTS({"cds": CDS_WITH_STOP, "gc_target": 1.5})
    )
    assert "commit' must be" in str(LinearDesignOptimizeNode.VALIDATE_INPUTS({"cds": CDS_WITH_STOP, "commit": ""}))


@pytest.mark.asyncio
async def test_run_executes_binary_with_protein_stdin_and_parses_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout = fake_checkout(tmp_path)
    monkeypatch.setenv("BIONODULO_LINEARDESIGN_DIR", str(checkout))
    calls: list[dict[str, Any]] = []

    def fake_run(command: list[str], **kwargs: Any) -> FakeCompleted:
        calls.append({"command": command, "kwargs": kwargs})
        return FakeCompleted(README_STDOUT)

    monkeypatch.setattr("bionodulo.nodes.builtin.codon_design_family.lineardesign_optimize.subprocess.run", fake_run)
    result = await LinearDesignOptimizeNode().run(
        context=context_at(tmp_path / "run"), cds=CDS_WITH_STOP, lambda_param=0.5
    )
    assert len(calls) == 1
    assert calls[0]["command"] == [str(checkout / "lineardesign"), "--lambda", "0.5"]
    assert calls[0]["kwargs"]["input"] == f">protein\n{PROTEIN}\n"
    assert calls[0]["kwargs"]["cwd"] == str(checkout)
    fasta = Path(result[0]).read_text(encoding="utf-8").splitlines()
    assert fasta == [">seq1", "ATGAACGATACGGAGGCGATC"]
    report = json.loads(Path(result[1]).read_text(encoding="utf-8"))
    assert report["lambda"] == 0.5
    assert report["protein_length"] == 7
    assert report["records"][0]["mfe_kcal_mol"] == pytest.approx(-1.10)
    assert report["records"][0]["cai"] == pytest.approx(0.695)
    assert report["records"][0]["gc"] == pytest.approx(11 / 21)
    assert report["commit"] == DEFAULT_COMMIT
    assert README_STDOUT in report["raw_stdout"]
    assert "redistribution" in report["license_constraint"]
    staged = (tmp_path / "run" / "protein.fasta").read_text(encoding="utf-8")
    assert staged == f">protein\n{PROTEIN}\n"


@pytest.mark.asyncio
async def test_run_rejects_internal_stop_and_non_cds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BIONODULO_LINEARDESIGN_DIR", str(fake_checkout(tmp_path)))
    with pytest.raises(ValueError, match="internal stop codon at protein position 2"):
        await LinearDesignOptimizeNode().run(
            context=context_at(tmp_path), cds="ATGTAAAATCTC" + "TAA"
        )
    with pytest.raises(ValueError, match="divisible by 3"):
        await LinearDesignOptimizeNode().run(context=context_at(tmp_path), cds="ATGGGCA")
    with pytest.raises(ValueError, match="invalid characters"):
        await LinearDesignOptimizeNode().run(context=context_at(tmp_path), cds="ATGX" * 4)


@pytest.mark.asyncio
async def test_run_requires_linux_worker_when_binary_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("BIONODULO_LINEARDESIGN_DIR", str(empty))
    monkeypatch.setattr(sys, "platform", "win32")
    with pytest.raises(RuntimeError, match="Linux worker required"):
        await LinearDesignOptimizeNode().run(context=context_at(tmp_path), cds=CDS_WITH_STOP)
    monkeypatch.setattr(sys, "platform", "linux")
    with pytest.raises(RuntimeError, match="build it with 'make'"):
        await LinearDesignOptimizeNode().run(context=context_at(tmp_path), cds=CDS_WITH_STOP)


@pytest.mark.asyncio
async def test_run_clones_and_pins_commit_when_no_env_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: Any) -> FakeCompleted:
        commands.append(list(command))
        if "clone" in command:
            target = Path(command[-1])
            target.mkdir(parents=True, exist_ok=True)
            (target / "lineardesign").write_text("#!/bin/sh\n", encoding="utf-8")
        return FakeCompleted(README_STDOUT)

    monkeypatch.delenv("BIONODULO_LINEARDESIGN_DIR", raising=False)
    monkeypatch.setattr("bionodulo.nodes.builtin.codon_design_family.lineardesign_optimize.subprocess.run", fake_run)
    node_dir = tmp_path / "run"
    result = await LinearDesignOptimizeNode().run(context=context_at(node_dir), cds=CDS_NO_STOP, commit="abc1234")
    checkout = node_dir / "lineardesign_optimize" / "LinearDesign"
    assert commands[0] == ["git", "clone", "--depth", "1",
                           "https://github.com/LinearDesignSoftware/LinearDesign", str(checkout)]
    assert commands[1] == ["git", "-C", str(checkout), "fetch", "--depth", "1", "origin", "abc1234"]
    assert commands[2] == ["git", "-C", str(checkout), "checkout", "--detach", "abc1234"]
    assert commands[3] == [str(checkout / "lineardesign"), "--lambda", "1.0"]
    assert Path(result[0]).is_file()

    commands.clear()
    monkeypatch.setenv("BIONODULO_LINEARDESIGN_DIR", str(checkout))
    await LinearDesignOptimizeNode().run(context=context_at(tmp_path / "run2"), cds=CDS_NO_STOP, commit="main")
    assert len(commands) == 1 and "git" not in commands[0]
