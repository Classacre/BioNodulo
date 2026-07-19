"""Focused argv, output, and failure contracts for SRA Toolkit 3.4.1."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bionodulo.environments.constants import (
    EXECUTABLE_TO_CONDA_PACKAGE,
    PACKAGE_MIN_VERSIONS,
)
from bionodulo.nodes.builtin import ncbi as legacy
from bionodulo.nodes.builtin.ncbi_family import SRADownloadNode, SRAFetchNode


def test_sra_authority_environment_and_generic_outputs() -> None:
    assert SRADownloadNode.VERSION == "3.4.1"
    assert SRADownloadNode.GIT_COMMIT == "ded4303eb477047590b219f6a2e8397b12d58cc0"
    assert SRADownloadNode.PACKAGE_CONSTRAINT == "sra-tools = 3.4.1"
    assert SRADownloadNode.CONDA_PACKAGE_CONSTRAINTS == {"sra-tools": "3.4.1"}
    assert PACKAGE_MIN_VERSIONS["sra-tools"] == "3.4.1"
    assert EXECUTABLE_TO_CONDA_PACKAGE["prefetch"] == "sra-tools"
    assert EXECUTABLE_TO_CONDA_PACKAGE["fasterq-dump"] == "sra-tools"
    assert SRADownloadNode.REQUIRED_EXECUTABLES == ["prefetch", "fasterq-dump"]
    assert SRADownloadNode.RETURN_TYPES == ("FILE_LIST", "JSON")
    assert SRADownloadNode.RETURN_NAMES == ("files", "download_report")
    assert SRADownloadNode.INPUT_TYPES()["optional"]["threads"][1]["default"] == 6
    assert SRADownloadNode.INPUT_TYPES()["optional"]["split_files"][1]["default"] is False
    assert legacy.SRADownloadNode is SRADownloadNode
    assert legacy.SRAFetchNode is SRAFetchNode


def test_sra_commands_use_accession_directory_and_source_native_flags(tmp_path: Path) -> None:
    assert SRADownloadNode.render_prefetch_command("SRR123", tmp_path) == [
        "prefetch",
        "SRR123",
        "--output-directory",
        str(tmp_path),
    ]
    assert SRADownloadNode.render_fasterq_command(
        accession="SRR123",
        output_dir=tmp_path,
        output_format="fastq",
        split_files=False,
        skip_technical=True,
        threads=6,
    ) == [
        "fasterq-dump",
        str(tmp_path / "SRR123"),
        "--outdir",
        str(tmp_path),
        "--threads",
        "6",
    ]
    assert SRADownloadNode.render_fasterq_command(
        accession="SRR123",
        output_dir=tmp_path,
        output_format="fasta",
        split_files=True,
        skip_technical=False,
        threads=8,
    ) == [
        "fasterq-dump",
        str(tmp_path / "SRR123"),
        "--outdir",
        str(tmp_path),
        "--threads",
        "8",
        "--fasta",
        "--split-files",
        "--include-technical",
    ]


@pytest.mark.asyncio
async def test_sra_runs_fasterq_once_per_accession_and_collects_files(tmp_path: Path) -> None:
    commands: list[list[str]] = []

    class Context:
        node_dir = tmp_path

        async def run_command(self, command: list[str], **kwargs: object) -> dict[str, object]:
            commands.append(command)
            if command[0] == "prefetch":
                Path(command[command.index("--output-directory") + 1]).mkdir(parents=True, exist_ok=True)
            else:
                accession = Path(command[1]).name
                output_dir = Path(command[command.index("--outdir") + 1])
                (output_dir / f"{accession}_1.fastq").write_text("@r1\nAC\n+\nII\n", encoding="utf-8")
                (output_dir / f"{accession}_2.fastq").write_text("@r2\nGT\n+\nII\n", encoding="utf-8")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    result = await SRADownloadNode().run(
        context=Context(),
        accessions="SRR100,ERR200",
    )

    assert [command[0] for command in commands] == [
        "prefetch",
        "fasterq-dump",
        "prefetch",
        "fasterq-dump",
    ]
    assert [Path(command[1]).name for command in commands if command[0] == "fasterq-dump"] == [
        "SRR100",
        "ERR200",
    ]
    assert all("--skip-technical" not in command for command in commands)
    assert all("--gzip" not in command for command in commands)
    assert [Path(path).name for path in result["outputs"]["files"]] == [
        "SRR100_1.fastq",
        "SRR100_2.fastq",
        "ERR200_1.fastq",
        "ERR200_2.fastq",
    ]
    report = json.loads(Path(result["outputs"]["download_report"]).read_text(encoding="utf-8"))
    assert report["completed_accessions"] == ["SRR100", "ERR200"]


@pytest.mark.asyncio
async def test_sra_fails_closed_and_writes_report(tmp_path: Path) -> None:
    commands: list[list[str]] = []

    class Context:
        node_dir = tmp_path

        async def run_command(self, command: list[str], **kwargs: object) -> dict[str, object]:
            commands.append(command)
            return {"returncode": 3, "stdout": "", "stderr": "download denied"}

    with pytest.raises(RuntimeError, match="SRR100: download denied"):
        await SRADownloadNode().run(
            context=Context(),
            accessions="SRR100,SRR200",
        )

    assert len(commands) == 1
    report_path = tmp_path / "sra_download" / "download_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["runs"] == [
        {
            "accession": "SRR100",
            "status": "prefetch_failed",
            "files": [],
            "error": "download denied",
        }
    ]


@pytest.mark.asyncio
async def test_sra_continue_on_error_returns_explicit_partial_results(tmp_path: Path) -> None:
    class Context:
        node_dir = tmp_path

        async def run_command(self, command: list[str], **kwargs: object) -> dict[str, object]:
            if command[0] == "prefetch" and command[1] == "SRR100":
                return {"returncode": 2, "stdout": "", "stderr": "not found"}
            if command[0] == "prefetch":
                Path(command[command.index("--output-directory") + 1]).mkdir(parents=True, exist_ok=True)
            else:
                output_dir = Path(command[command.index("--outdir") + 1])
                (output_dir / "SRR200.fastq").write_text("@r\nAC\n+\nII\n", encoding="utf-8")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    result = await SRADownloadNode().run(
        context=Context(),
        accessions="SRR100,SRR200",
        continue_on_error=True,
    )

    assert [Path(path).name for path in result["outputs"]["files"]] == ["SRR200.fastq"]
    report = json.loads(Path(result["outputs"]["download_report"]).read_text(encoding="utf-8"))
    assert [run["status"] for run in report["runs"]] == ["prefetch_failed", "completed"]
    assert report["continue_on_error"] is True
