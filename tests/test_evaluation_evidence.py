"""Regressions for false scientific-proof claims in the study scaffold."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/evaluation/adjudicate.py"
spec = importlib.util.spec_from_file_location("study_adjudicator", SCRIPT)
adjudicator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adjudicator)

@pytest.fixture
def study_tasks(tmp_path):
    """Small, local study inputs: CI checks out this repository only."""
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    for number in range(1, 7):
        task = {
            "task_id": f"T{number}",
            "analysis_type": "qc",
            "task_class": "planted_failure",
            "participant_brief": "Quality check the reads with FastQC",
            "agent_materials": {"fixtures": {"reads": "synthetic.fastq"}},
            "ground_truth": {
                "param_requirements": [
                    {"node_type": "fastqc", "param": "threads", "expected": 8}
                ]
            },
            "planted_failure": {
                "dimension": "threads",
                "class": "synthetic-parameter-mismatch",
                "signature": {"kind": "param_value", "node_type": "fastqc", "param": "threads"},
            },
        }
        if number == 3:
            task.update(
                analysis_type="rna_seq_de",
                task_class="runtime_failure_control",
                participant_brief="Align reads, convert to BAM and index with samtools_index",
                endpoint_eligible=False,
                ground_truth={"required_edge_states": [
                    {"to_type": "samtools_index", "to_input": "bam", "dimension": "sort_order", "expected": "coordinate"}
                ]},
                planted_failure={"dimension": "sort_order", "class": "synthetic-unsorted-bam",
                                 "signature": {"kind": "edge_state", "to_type": "samtools_index",
                                               "to_input": "bam", "dimension": "sort_order"}},
            )
        elif number == 5:
            task.update(task_class="clean_control", planted_failure=None,
                        ground_truth={"admissible_node_types": ["input_fastq", "fastqc"]})
        elif number == 6:
            task.update(task_class="ambiguous", planted_failure=None,
                        ground_truth={"detection_node_types": ["rseqc_infer_experiment"]})
        (tasks / f"T{number}.json").write_text(json.dumps(task), encoding="utf-8")
    submissions = tasks / "submissions"
    submissions.mkdir()
    planted = {"version": "2.0", "app": "bionodulo", "name": "Synthetic planted parameter",
               "nodes": [{"id": "qc", "type": "fastqc", "params": {"threads": 4}}],
               "edges": [], "outputs": {}}
    (submissions / "T1-planted.json").write_text(json.dumps(planted), encoding="utf-8")
    return tasks


@pytest.mark.parametrize("other_state", ["unsorted", None])
def test_one_valid_edge_cannot_hide_an_invalid_or_unknown_feed(other_state):
    nodes = {"c": {"type": "samtools_index"}}
    edges = [{"id": source, "source": source, "source_output": "bam",
              "target": "c", "target_input": "bam"} for source in ("good", "bad")]
    states = SimpleNamespace(node_states={
        "good": {"bam": {"sort_order": "coordinate"}},
        "bad": {"bam": {"sort_order": other_state}}})
    checks = adjudicator.check_edge_states([{
        "to_type": "samtools_index", "to_input": "bam",
        "dimension": "sort_order", "expected": "coordinate"}], nodes, edges, states)
    assert checks[0]["ok"] is False


def test_one_fed_consumer_cannot_hide_another_missing_input():
    checks = adjudicator.check_edge_states([{
        "to_type": "samtools_index", "to_input": "bam", "dimension": "sort_order",
        "expected": "coordinate"}], {"c1": {"type": "samtools_index"}, "c2": {"type": "samtools_index"}},
        [{"id": "e", "source": "s", "source_output": "bam", "target": "c1", "target_input": "bam"}],
        SimpleNamespace(node_states={"s": {"bam": {"sort_order": "coordinate"}}}))
    assert checks[0]["ok"] is False


def test_cli_cannot_turn_static_artifact_into_observed_silent_error(tmp_path, study_tasks):
    result = subprocess.run([sys.executable, str(SCRIPT), "--task", str(study_tasks / "T1.json"),
        "--submission", str(study_tasks / "submissions/T1-planted.json"),
        "--out", str(tmp_path / "verdict.json")], check=True, capture_output=True, text=True)
    verdict = json.loads(result.stdout)
    assert verdict["static_hazard_present"] is True
    assert verdict["silent_error"] is None
    assert verdict["endpoint_status"] == "unobserved"
    assert json.loads((tmp_path / "verdict.json").read_text()) == verdict


def test_all_baseline_outputs_preserve_unobserved_endpoint(tmp_path, study_tasks):
    subprocess.run([sys.executable, str(ROOT / "scripts/evaluation/agent_arm.py"),
                    "--tasks-dir", str(study_tasks), "--out", str(tmp_path)],
                   check=True, capture_output=True, text=True)
    outputs = json.loads((tmp_path / "agent-arm-results.json").read_text())
    assert len(outputs) == 6
    assert all(arm["silent_error"] is None for task in outputs for arm in task["agents"].values())
    t3 = json.loads((study_tasks / "T3.json").read_text())
    assert t3["endpoint_eligible"] is False
    assert t3["planted_failure"]["signature"]["to_type"] == "samtools_index"


def test_detection_node_is_not_proof_of_human_examination(study_tasks):
    task = json.loads((study_tasks / "T6.json").read_text())
    result = adjudicator.check_ambiguous_task(task, {"detect": {"type": "rseqc_infer_experiment"}})
    assert result["ambiguity_handling"] == "graph_hint_present_unverified"
