from __future__ import annotations

import importlib
import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.command_node import CommandNode
from bionodulo.nodes.builtin.qc_family.fastqc import FastQCNode
from bionodulo.nodes.builtin.qc_family.multiqc import MultiQCNode
from scripts.gen_node_index import build_index


class FakeExecutionContext:
    def __init__(
        self,
        node_dir: Path,
        writer: Callable[[list[str]], None] | None = None,
        *,
        returncode: int = 0,
    ) -> None:
        self.node_dir = node_dir
        self.writer = writer
        self.returncode = returncode
        self.commands: list[list[str]] = []

    async def run_command(self, command: list[str], **_kwargs: Any) -> dict[str, Any]:
        self.commands.append(command)
        if self.writer is not None:
            self.writer(command)
        return {
            "returncode": self.returncode,
            "stdout": "",
            "stderr": "synthetic failure" if self.returncode else "",
        }


def test_live_builtin_index_assigns_each_id_to_its_focused_module() -> None:
    expected = (
        ("fastqc", "bionodulo.nodes.builtin.qc_family.fastqc"),
        ("multiqc", "bionodulo.nodes.builtin.qc_family.multiqc"),
    )
    live_index = build_index()

    for node_id, module_name in expected:
        assert live_index[node_id] == module_name


def test_legacy_qc_module_no_longer_owns_the_migrated_ids() -> None:
    legacy = importlib.import_module("bionodulo.nodes.builtin.qc")
    owned_ids = {
        obj.NODE_ID
        for _name, obj in inspect.getmembers(legacy, inspect.isclass)
        if issubclass(obj, BaseNode) and obj not in {BaseNode, CommandNode} and obj.__module__ == legacy.__name__
    }

    assert {"fastqc", "multiqc", "qualimap", "qualimap_bamqc"}.isdisjoint(owned_ids)


def test_nodes_pin_exact_official_release_authorities() -> None:
    expected = (
        (
            FastQCNode,
            "0.12.1",
            "https://github.com/s-andrews/FastQC.git",
            "e7ef390bf10382f60786bdd0cf28abd4f8683ffd",
            "v0.12.1",
            "fastqc",
        ),
        (
            MultiQCNode,
            "1.33",
            "https://github.com/MultiQC/MultiQC.git",
            "5953b5417ccb70bf4a2309562d43015fced8b585",
            "v1.33",
            "multiqc",
        ),
    )

    for node, version, git_url, git_commit, tag, executable in expected:
        assert node.VERSION == version
        assert node.GIT_URL == git_url
        assert node.GIT_COMMIT == git_commit
        assert node.UPSTREAM_TAG == tag
        assert node.REQUIRED_EXECUTABLES == [executable]
        assert node.REQUIRED_CONDA_PACKAGES == [executable]
        assert node.SHELL is False


def test_fastqc_contract_pins_supported_inputs_and_directory_output() -> None:
    inputs = FastQCNode.INPUT_TYPES()

    assert inputs["required"] == {
        "reads": ("FASTQ_LIST", {"description": "One or more readable FASTQ files"}),
        "threads": (
            "INT",
            {"default": 1, "min": 1, "max": 64, "display": "slider"},
        ),
    }
    assert inputs["optional"]["extract"][1]["default"] is False
    assert inputs["optional"]["kmers"][1] == {
        "default": 7,
        "min": 2,
        "max": 10,
        "description": "K-mer length used by the Kmer Content module",
        "advanced": True,
    }
    assert inputs["optional"]["format"][1]["options"] == [
        "",
        "fastq",
        "sam",
        "bam",
        "sam_mapped",
        "bam_mapped",
    ]
    assert {inputs["optional"][name][0] for name in ("contaminants", "adapters", "limits")} == {"FILE"}
    assert FastQCNode.RETURN_TYPES == ("QC_REPORT_DIR",)
    assert FastQCNode.RETURN_NAMES == ("report_dir",)
    assert FastQCNode.UPSTREAM_CLI_SOURCE == "fastqc"
    assert FastQCNode.UPSTREAM_RUNNER_SOURCE.endswith("Analysis/OfflineRunner.java")
    assert FastQCNode.UPSTREAM_ARCHIVE_SOURCE.endswith("Report/HTMLReportArchive.java")


def test_fastqc_default_argv_and_planned_report_root_are_exact(tmp_path: Path) -> None:
    reads = ["sample_R1.fastq.gz", "sample_R2.fq.gz"]
    node_output = tmp_path / "fastqc"

    assert FastQCNode.render_command({"reads": reads, "threads": 1, "output": str(node_output)}) == [
        "fastqc",
        "--threads",
        "1",
        "--outdir",
        str(node_output / "report_dir.out"),
        *reads,
    ]
    assert FastQCNode.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "fastqc" / "report_dir.out"]
    assert (tmp_path / "fastqc" / "report_dir.out").is_dir()


def test_fastqc_optional_argv_is_ordered_and_exact(tmp_path: Path) -> None:
    contaminants = tmp_path / "contaminants.txt"
    adapters = tmp_path / "adapters.txt"
    limits = tmp_path / "limits.txt"
    for path in (contaminants, adapters, limits):
        path.write_text("fixture\n", encoding="utf-8")
    node_output = tmp_path / "run" / "fastqc"

    command = FastQCNode.render_command(
        {
            "reads": ("reads.fastq",),
            "threads": 4,
            "output": node_output,
            "nogroup": True,
            "kmers": 5,
            "extract": True,
            "format": "fastq",
            "contaminants": contaminants,
            "adapters": adapters,
            "limits": limits,
        }
    )

    assert command == [
        "fastqc",
        "--threads",
        "4",
        "--outdir",
        str(node_output / "report_dir.out"),
        "--nogroup",
        "--kmers",
        "5",
        "--extract",
        "--format",
        "fastq",
        "--contaminants",
        str(contaminants),
        "--adapters",
        str(adapters),
        "--limits",
        str(limits),
        "reads.fastq",
    ]


def test_fastqc_validation_rejects_documented_error_cases(tmp_path: Path) -> None:
    read = tmp_path / "reads.fastq"
    read.write_text("@r\nA\n+\nI\n", encoding="utf-8")
    cases: tuple[tuple[dict[str, Any], str], ...] = (
        ({"reads": []}, "at least one"),
        ({"reads": ["missing.fastq"]}, "does not exist"),
        ({"threads": True}, "threads must be an integer"),
        ({"threads": 0}, "threads must be between"),
        ({"kmers": 1}, "kmers must be between"),
        ({"kmers": True}, "kmers must be an integer"),
        ({"format": "bismark"}, "format must be"),
        ({"adapters": "missing-adapters.txt"}, "adapters file does not exist"),
    )
    for updates, message in cases:
        inputs: dict[str, Any] = {"reads": [read], "threads": 1}
        inputs.update(updates)
        assert message in str(FastQCNode.VALIDATE_INPUTS(inputs))

    first = tmp_path / "first" / "sample.fastq.gz"
    second = tmp_path / "second" / "sample.fastq.gz"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("fixture", encoding="utf-8")
    second.write_text("fixture", encoding="utf-8")

    assert (
        FastQCNode.VALIDATE_INPUTS({"reads": [first, second], "threads": 1})
        == "reads must have unique FastQC output basenames"
    )


@pytest.mark.asyncio
async def test_fastqc_fake_execution_requires_each_documented_artifact(tmp_path: Path) -> None:
    read = tmp_path / "sample.fastq.gz"
    read.write_text("@r\nA\n+\nI\n", encoding="utf-8")

    def write_fastqc_outputs(command: list[str]) -> None:
        report_dir = Path(command[command.index("--outdir") + 1])
        (report_dir / "sample_fastqc.html").write_text("html", encoding="utf-8")
        (report_dir / "sample_fastqc.zip").write_bytes(b"zip")

    context = FakeExecutionContext(tmp_path / "run", write_fastqc_outputs)

    result = await FastQCNode().run(reads=[read], threads=1, context=context)

    assert result == (str(tmp_path / "run" / "fastqc" / "report_dir.out"),)
    assert context.commands[0][-1] == str(read)
    missing_context = FakeExecutionContext(tmp_path / "missing-run")

    with pytest.raises(RuntimeError, match="did not create expected report artifact"):
        await FastQCNode().run(reads=[read], threads=1, context=missing_context)


def test_multiqc_contract_exposes_report_and_parsed_data_directory() -> None:
    inputs = MultiQCNode.INPUT_TYPES()

    assert inputs["required"] == {
        "reports": (
            "FILE_LIST",
            {"description": ("One or more files or directories containing recognizable analysis data")},
        )
    }
    assert inputs["optional"]["title"][1]["default"] == ""
    assert inputs["optional"]["comment"][1]["default"] == ""
    assert inputs["optional"]["force"][1]["default"] is False
    assert inputs["optional"]["filename"][1]["default"] == "multiqc_report"
    assert MultiQCNode.RETURN_TYPES == ("MULTIQC_REPORT", "DIRECTORY")
    assert MultiQCNode.RETURN_NAMES == ("report", "data_dir")
    assert MultiQCNode.UPSTREAM_CLI_SOURCE == "multiqc/multiqc.py"
    assert MultiQCNode.UPSTREAM_OUTPUT_SOURCE == "multiqc/core/write_results.py"
    assert MultiQCNode.UPSTREAM_ERROR_SOURCE == "multiqc/core/exceptions.py"
    assert MultiQCNode.CITATION_DOIS == ["10.1093/bioinformatics/btw354"]


def test_multiqc_passes_exact_search_paths_and_plans_upstream_defaults(tmp_path: Path) -> None:
    report_file = tmp_path / "sample_fastqc.zip"
    report_dir = tmp_path / "fastp"
    report_file.write_bytes(b"zip")
    report_dir.mkdir()
    node_output = tmp_path / "run" / "multiqc"

    assert MultiQCNode.render_command(
        {
            "reports": [report_file, report_dir],
            "output": node_output,
        }
    ) == [
        "multiqc",
        str(report_file),
        str(report_dir),
        "--outdir",
        str(node_output),
        "--filename",
        "multiqc_report",
    ]
    assert MultiQCNode.PLAN_OUTPUTS({}, tmp_path / "run") == [
        node_output / "multiqc_report.html",
        node_output / "multiqc_report_data",
    ]


def test_multiqc_custom_filename_and_optional_argv_are_exact(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    node_output = tmp_path / "run" / "multiqc"
    inputs = {
        "reports": reports,
        "output": node_output,
        "filename": "cohort.html",
        "title": "Cohort QC",
        "comment": "Synthetic fixture",
        "force": True,
    }

    assert MultiQCNode.render_command(inputs) == [
        "multiqc",
        str(reports),
        "--outdir",
        str(node_output),
        "--filename",
        "cohort",
        "--title",
        "Cohort QC",
        "--comment",
        "Synthetic fixture",
        "--force",
    ]
    assert MultiQCNode.PLAN_OUTPUTS(inputs, tmp_path / "run") == [
        node_output / "cohort.html",
        node_output / "cohort_data",
    ]

    (node_output / "cohort.html").write_text("old", encoding="utf-8")
    (node_output / "cohort_data").mkdir()
    assert MultiQCNode.PLAN_OUTPUTS({**inputs, "force": False}, tmp_path / "run") == [
        node_output / "cohort_1.html",
        node_output / "cohort_data_1",
    ]


def test_multiqc_validation_matches_cli_path_and_filename_constraints(
    tmp_path: Path,
) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    cases: tuple[tuple[dict[str, Any], str | None], ...] = (
        ({"reports": []}, "at least one"),
        ({"reports": ["missing"]}, "does not exist"),
        ({"filename": "stdout"}, "cannot be stdout"),
        ({"filename": "stdout.html"}, "cannot be stdout"),
        ({"filename": "nested/report"}, "must not contain a directory"),
        ({"filename": ""}, None),
        ({"title": 7}, "title must be a string"),
    )
    for updates, message in cases:
        inputs: dict[str, Any] = {"reports": [reports]}
        inputs.update(updates)
        result = MultiQCNode.VALIDATE_INPUTS(inputs)
        if message is None:
            assert result is True
        else:
            assert message in str(result)


@pytest.mark.asyncio
async def test_multiqc_fake_execution_returns_html_and_data_outputs(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()

    def write_multiqc_outputs(command: list[str]) -> None:
        output_dir = Path(command[command.index("--outdir") + 1])
        filename = command[command.index("--filename") + 1]
        (output_dir / f"{filename}.html").write_text("html", encoding="utf-8")
        (output_dir / f"{filename}_data").mkdir()

    context = FakeExecutionContext(tmp_path / "run", write_multiqc_outputs)

    result = await MultiQCNode().run(reports=[reports], context=context)

    assert result == (
        str(tmp_path / "run" / "multiqc" / "multiqc_report.html"),
        str(tmp_path / "run" / "multiqc" / "multiqc_report_data"),
    )


@pytest.mark.asyncio
async def test_nonzero_tool_exit_is_propagated(tmp_path: Path) -> None:
    read = tmp_path / "reads.fastq"
    read.write_text("@r\nA\n+\nI\n", encoding="utf-8")
    reports = tmp_path / "reports"
    reports.mkdir()
    cases: tuple[tuple[type[CommandNode], dict[str, Any]], ...] = (
        (FastQCNode, {"reads": [read], "threads": 1}),
        (MultiQCNode, {"reports": [reports]}),
    )

    for index, (node, required_inputs) in enumerate(cases):
        context = FakeExecutionContext(tmp_path / f"run-{index}", returncode=1)
        with pytest.raises(RuntimeError, match=r"Command failed \(exit 1\)"):
            await node().run(**required_inputs, context=context)
