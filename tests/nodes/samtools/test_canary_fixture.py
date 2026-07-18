from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.nodes.registry import NodeRegistry
from bionodulo.workflow.validation import validate_workflow


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "samtools_first_wave"
TINY_SAM = FIXTURE_DIR / "tiny.sam"
WORKFLOW = FIXTURE_DIR / "workflow.json"
RUNBOOK = REPO_ROOT / "docs" / "testing" / "samtools-first-wave-canary.md"
TINY_SAM_SHA256 = "0b621dee8e14e8ebf5e52772c3c6695b47c312e5190b52591644ce872ee422c7"
WORKFLOW_SHA256 = "86407589c10492da463a8fd2ae9cfcadb6e53c3f83d5c797f44c9eda8b63739a"

NODE_ORDER = [
    "view_001",
    "collate_001",
    "fixmate_001",
    "sort_001",
    "markdup_001",
    "index_001",
    "flagstat_001",
]

EDGE_TUPLES = [
    ("view_001", "bam", "collate_001", "bam"),
    ("collate_001", "name_collated_bam", "fixmate_001", "bam"),
    ("fixmate_001", "fixmate_bam", "sort_001", "alignment"),
    ("sort_001", "sorted_bam", "markdup_001", "bam"),
    ("markdup_001", "marked_bam", "index_001", "bam"),
    ("index_001", "indexed_bam", "flagstat_001", "bam"),
]


def test_canary_fixture_bytes_match_documented_sha256() -> None:
    assert hashlib.sha256(TINY_SAM.read_bytes()).hexdigest() == TINY_SAM_SHA256
    assert hashlib.sha256(WORKFLOW.read_bytes()).hexdigest() == WORKFLOW_SHA256
    runbook = RUNBOOK.read_text(encoding="utf-8")
    block_start = "The fixture and workflow hashes in this checkout are:\n\n```text\n"
    _, marker, remainder = runbook.partition(block_start)
    assert marker, "runbook fixture hash block is missing"
    hash_block, marker, _ = remainder.partition("\n```")
    assert marker, "runbook fixture hash block is not closed"
    documented_hashes = dict(line.split() for line in hash_block.splitlines())
    assert documented_hashes == {
        "tiny.sam": TINY_SAM_SHA256,
        "workflow.json": WORKFLOW_SHA256,
    }


def test_canary_fixture_git_attributes_pin_lf_bytes() -> None:
    result = subprocess.run(
        [
            "git",
            "check-attr",
            "text",
            "eol",
            "--",
            "tests/fixtures/samtools_first_wave/tiny.sam",
            "tests/fixtures/samtools_first_wave/workflow.json",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.splitlines() == [
        "tests/fixtures/samtools_first_wave/tiny.sam: text: set",
        "tests/fixtures/samtools_first_wave/tiny.sam: eol: lf",
        "tests/fixtures/samtools_first_wave/workflow.json: text: set",
        "tests/fixtures/samtools_first_wave/workflow.json: eol: lf",
    ]


def test_tiny_sam_is_an_interleaved_two_pair_duplicate_case() -> None:
    lines = TINY_SAM.read_text(encoding="ascii").splitlines()

    assert lines[:2] == [
        "@HD\tVN:1.6\tSO:unsorted",
        "@SQ\tSN:chr1\tLN:1000",
    ]
    assert [line.split("\t") for line in lines[2:]] == [
        [
            "pair_high",
            "99",
            "chr1",
            "101",
            "60",
            "10M",
            "=",
            "151",
            "60",
            "ACGTACGTAC",
            "IIIIIIIIII",
        ],
        [
            "pair_low",
            "99",
            "chr1",
            "101",
            "60",
            "10M",
            "=",
            "151",
            "60",
            "ACGTACGTAC",
            "5555555555",
        ],
        [
            "pair_high",
            "147",
            "chr1",
            "151",
            "60",
            "10M",
            "=",
            "101",
            "-60",
            "GTACGTACGT",
            "IIIIIIIIII",
        ],
        [
            "pair_low",
            "147",
            "chr1",
            "151",
            "60",
            "10M",
            "=",
            "101",
            "-60",
            "GTACGTACGT",
            "5555555555",
        ],
    ]
    assert all("/" not in line.split("\t", 1)[0] for line in lines[2:])


@pytest.mark.asyncio
async def test_canary_workflow_validates_and_dry_runs_exact_seven_node_chain(
    tmp_path: Path,
) -> None:
    workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    registry = NodeRegistry.create_isolated()

    assert workflow["version"] == "2.0"
    assert workflow["app"] == "bionodulo"
    assert workflow["parameters"] == [
        {"name": "tiny_sam", "type": "SAM", "required": True}
    ]
    assert [node["id"] for node in workflow["nodes"]] == NODE_ORDER
    assert [node["type"] for node in workflow["nodes"]] == [
        "samtools_view",
        "samtools_collate",
        "samtools_fixmate",
        "samtools_sort",
        "samtools_markdup",
        "samtools_index",
        "samtools_flagstat",
    ]
    assert [
        (
            edge["from"]["node"],
            edge["from"]["output"],
            edge["to"]["node"],
            edge["to"]["input"],
        )
        for edge in workflow["edges"]
    ] == EDGE_TUPLES
    assert workflow["outputs"] == {
        "indexed_bam": "index_001",
        "bai": "index_001",
        "flagstat": "flagstat_001",
        "duplicate_stats": "markdup_001",
    }

    validation = validate_workflow(workflow, registry)
    assert validation.valid, validation.errors
    assert validation.sorted_node_order == NODE_ORDER

    workspace = tmp_path / "workspace"
    executor = WorkflowExecutor(
        workspace_dir=workspace,
        cache_dir=tmp_path / "cache",
        registry=registry,
    )
    preview = await executor.dry_run(
        "samtools-first-wave-canary",
        workflow,
        force=True,
        options={"parameters": {"tiny_sam": str(TINY_SAM.resolve())}},
    )

    assert preview["status"] == "dry_run"
    assert preview["will_execute"] is False
    assert preview["execution_order"] == NODE_ORDER
    assert preview["workflow_parameters"] == {"tiny_sam": str(TINY_SAM.resolve())}
    assert all(isinstance(node["command"], list) for node in preview["nodes"])
    assert all(
        isinstance(token, str)
        for node in preview["nodes"]
        for token in node["command"]
    )
    assert all(node["shell"] is False for node in preview["nodes"])

    plans = {node["node_id"]: node for node in preview["nodes"]}
    assert "-m" in plans["fixmate_001"]["command"]
    index_outputs = plans["index_001"]["planned_outputs"]
    assert Path(index_outputs["indexed_bam"]).name == "indexed_bam.bam"
    assert Path(index_outputs["bai"]).name == "indexed_bam.bam.bai"
    assert plans["flagstat_001"]["inputs"]["bam"] == index_outputs["indexed_bam"]
