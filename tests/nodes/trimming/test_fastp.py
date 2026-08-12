from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.builtin.trimming_family.fastp import FastpNode
from bionodulo.execution.executor import WorkflowExecutor
from scripts.gen_node_index import build_index


def _inputs(reads: Any, **updates: Any) -> dict[str, Any]:
    inputs: dict[str, Any] = {"reads": reads, "threads": 3}
    inputs.update(updates)
    return inputs


class _FakeContext:
    def __init__(self, node_dir: Path, returncode: int = 0) -> None:
        self.node_dir = node_dir
        self.returncode = returncode
        self.calls: list[tuple[list[str], dict[str, Any]]] = []

    async def run_command(self, command: list[str], **kwargs: Any) -> dict[str, Any]:
        self.calls.append((command, kwargs))
        if self.returncode == 0:
            for flag in ("--out1", "--out2", "--json", "--html"):
                if flag not in command:
                    continue
                path = Path(command[command.index(flag) + 1])
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"synthetic {flag}\n", encoding="utf-8")
        return {
            "returncode": self.returncode,
            "stdout": "",
            "stderr": "synthetic fastp failure" if self.returncode else "",
        }


def test_stable_fastp_id_is_owned_only_by_the_focused_operation_module() -> None:
    module_name = "bionodulo.nodes.builtin.trimming_family.fastp"
    assert build_index()["fastp"] == module_name


def test_fastp_contract_and_pinned_upstream_authority_are_exact() -> None:
    assert FastpNode.NODE_ID == "fastp"
    assert FastpNode.RETURN_TYPES == ("FASTQ_LIST", "HTML_REPORT", "JSON")
    assert FastpNode.RETURN_NAMES == ("trimmed_reads", "report", "json_report")
    assert FastpNode.REQUIRED_EXECUTABLES == ["fastp"]
    assert FastpNode.REQUIRED_CONDA_PACKAGES == ["fastp"]
    assert FastpNode.PACKAGE_CONSTRAINTS == ("fastp==0.24.0",)
    assert FastpNode.VERSION == "0.24.0"
    assert FastpNode.GIT_URL == "https://github.com/OpenGene/fastp.git"
    assert FastpNode.GIT_COMMIT == "4f273f1d8afac977a82460e1de174daa3e66f3f5"
    assert FastpNode.SOURCE_REF == "tag v0.24.0 at 4f273f1d8afac977a82460e1de174daa3e66f3f5"
    assert FastpNode.SOURCE_REVISION == FastpNode.GIT_COMMIT
    assert FastpNode.DOCUMENTATION_URL == ("https://github.com/OpenGene/fastp/tree/v0.24.0")
    assert FastpNode.SOURCE_URL == (
        "https://github.com/OpenGene/fastp/tree/4f273f1d8afac977a82460e1de174daa3e66f3f5"
    )
    assert FastpNode.UPSTREAM_README == "README.md"
    assert FastpNode.UPSTREAM_CLI_SOURCE == "src/main.cpp"
    assert FastpNode.UPSTREAM_VALIDATION_SOURCE == "src/options.cpp"
    assert FastpNode.UPSTREAM_ERROR_SOURCE == "src/util.h"
    assert FastpNode.UPSTREAM_SOURCE_PATHS == (
        "README.md",
        "src/main.cpp",
        "src/options.cpp",
        "src/util.h",
    )
    assert FastpNode.AUDIT_STATUS == "contract-checked-no-external-execution"
    assert "exits -1" in FastpNode.EXIT_SEMANTICS
    assert FastpNode.CITATION_DOIS == ["10.1002/imt2.107"]


def test_fastp_input_defaults_and_documented_ranges_are_exact() -> None:
    inputs = FastpNode.INPUT_TYPES()
    assert inputs["required"] == {
        "reads": (
            "FASTQ_LIST",
            {"description": ("One single-end FASTQ or an ordered paired-end collection [R1, R2]")},
        ),
        "threads": (
            "INT",
            {"default": 3, "min": 1, "max": 16, "display": "slider"},
        ),
    }
    assert inputs["optional"]["compression"][1]["default"] == 4
    assert inputs["optional"]["compression"][1]["min"] == 1
    assert inputs["optional"]["compression"][1]["max"] == 9
    assert inputs["optional"]["qualified_quality_phred"][1]["default"] == 15
    assert inputs["optional"]["qualified_quality_phred"][1]["min"] == 0
    assert inputs["optional"]["qualified_quality_phred"][1]["max"] == 93
    assert inputs["optional"]["length_required"][1]["default"] == 15
    assert inputs["optional"]["length_required"][1]["min"] == 1
    assert inputs["optional"]["cut_front"][1]["default"] is False
    assert inputs["optional"]["cut_tail"][1]["default"] is False
    assert inputs["hidden"] == {"output": ("STRING", {})}


@pytest.mark.parametrize(
    ("reads", "filenames"),
    [
        (["R1.fastq.gz"], ["trimmed_reads.fastq.gz", "report.html", "report.json"]),
        (
            ["R1.fastq.gz", "R2.fastq.gz"],
            [
                "trimmed_reads.fastq.gz",
                "trimmed_reads_2.fastq.gz",
                "report.html",
                "report.json",
            ],
        ),
    ],
)
def test_output_planning_matches_single_or_paired_mode(
    tmp_path: Path,
    reads: list[str],
    filenames: list[str],
) -> None:
    planned = FastpNode.PLAN_OUTPUTS(_inputs(reads), tmp_path)
    assert planned == [tmp_path / "fastp" / filename for filename in filenames]
    assert all(path.name.endswith(".gz") for path in planned[: len(reads)])


def test_single_end_default_argv_is_exact(tmp_path: Path) -> None:
    output = tmp_path / "fastp"
    assert FastpNode.render_command(_inputs("sample.fastq.gz", output=str(output))) == [
        "fastp",
        "--in1",
        "sample.fastq.gz",
        "--out1",
        str(output / "trimmed_reads.fastq.gz"),
        "--compression",
        "4",
        "--qualified_quality_phred",
        "15",
        "--length_required",
        "15",
        "--json",
        str(output / "report.json"),
        "--html",
        str(output / "report.html"),
        "--thread",
        "3",
    ]


def test_paired_end_option_argv_is_exact(tmp_path: Path) -> None:
    output = tmp_path / "fastp"
    assert FastpNode.render_command(
        _inputs(
            ["R1.fq.gz", "R2.fq.gz"],
            output=str(output),
            threads=8,
            compression=6,
            qualified_quality_phred=20,
            cut_front=True,
            cut_tail=True,
            length_required=30,
        )
    ) == [
        "fastp",
        "--in1",
        "R1.fq.gz",
        "--in2",
        "R2.fq.gz",
        "--out1",
        str(output / "trimmed_reads.fastq.gz"),
        "--out2",
        str(output / "trimmed_reads_2.fastq.gz"),
        "--compression",
        "6",
        "--cut_front",
        "--cut_tail",
        "--qualified_quality_phred",
        "20",
        "--length_required",
        "30",
        "--json",
        str(output / "report.json"),
        "--html",
        str(output / "report.html"),
        "--thread",
        "8",
    ]


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"reads": []}, "exactly one single-end FASTQ or two paired FASTQs"),
        ({"reads": ["R1", "R2", "R3"]}, "exactly one single-end FASTQ"),
        ({"reads": ["R1", ""]}, "read paths must be non-empty"),
        ({"threads": True}, "threads must be an integer"),
        ({"threads": 17}, "threads must be between 1 and 16"),
        ({"compression": 0}, "compression must be between 1 and 9"),
        ({"qualified_quality_phred": 94}, "must be between 0 and 93"),
        ({"length_required": 0}, "must be greater than zero"),
        ({"cut_front": "yes"}, "must be a boolean"),
    ],
)
def test_invalid_contract_values_fail_before_command_rendering(
    updates: dict[str, Any],
    message: str,
) -> None:
    inputs = _inputs(["R1.fastq.gz"])
    inputs.update(updates)
    validation = FastpNode.VALIDATE_INPUTS(inputs)
    assert validation is not True
    assert message in str(validation)
    with pytest.raises(ValueError, match=message):
        FastpNode.render_command(inputs)


@pytest.mark.asyncio
@pytest.mark.parametrize("reads", [["R1.fq.gz"], ["R1.fq.gz", "R2.fq.gz"]])
async def test_fake_execution_returns_grouped_fastqs_and_both_reports(
    tmp_path: Path,
    reads: list[str],
) -> None:
    context = _FakeContext(tmp_path)
    result = await FastpNode().run(reads=reads, threads=3, context=context)
    out = tmp_path / "fastp"
    expected_reads = [str(out / "trimmed_reads.fastq.gz")]
    if len(reads) == 2:
        expected_reads.append(str(out / "trimmed_reads_2.fastq.gz"))

    assert result == {
        "outputs": {
            "trimmed_reads": expected_reads,
            "report": str(out / "report.html"),
            "json_report": str(out / "report.json"),
        }
    }
    assert len(context.calls) == 1
    assert ("--out2" in context.calls[0][0]) is (len(reads) == 2)


@pytest.mark.asyncio
async def test_dry_run_preserves_the_grouped_paired_fastq_output_port(
    tmp_path: Path,
) -> None:
    class Registry:
        @staticmethod
        def get(node_type: str) -> type[FastpNode] | None:
            return FastpNode if node_type == "fastp" else None

    workflow = {
        "name": "fastp dry-run contract",
        "nodes": [
            {
                "id": "trim",
                "type": "fastp",
                "inputs": {
                    "reads": {"value": ["R1.fq.gz", "R2.fq.gz"]},
                    "threads": {"value": 3},
                },
                "outputs": {
                    "trimmed_reads": {},
                    "report": {},
                    "json_report": {},
                },
            }
        ],
        "edges": [],
    }
    executor = WorkflowExecutor(
        workspace_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        registry=Registry(),
    )

    preview = await executor.dry_run("fastp-preview", workflow)
    out = tmp_path / "runs" / "fastp-preview" / "trim" / "fastp"
    assert preview["nodes"][0]["planned_outputs"] == {
        "trimmed_reads": [
            str(out / "trimmed_reads.fastq.gz"),
            str(out / "trimmed_reads_2.fastq.gz"),
        ],
        "report": str(out / "report.html"),
        "json_report": str(out / "report.json"),
    }


@pytest.mark.asyncio
async def test_nonzero_fastp_exit_is_reported_as_a_runtime_failure(tmp_path: Path) -> None:
    context = _FakeContext(tmp_path, returncode=7)
    with pytest.raises(RuntimeError, match=r"Command failed \(exit 7\)"):
        await FastpNode().run(
            reads=["R1.fq.gz"],
            threads=3,
            context=context,
        )
