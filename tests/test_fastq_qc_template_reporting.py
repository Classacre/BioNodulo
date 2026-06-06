from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _load_template(name: str) -> dict[str, Any]:
    return json.loads((ROOT / "templates" / name).read_text(encoding="utf-8"))


def _node_types(workflow: dict[str, Any]) -> dict[str, str]:
    return {str(node["id"]): str(node["type"]) for node in workflow["nodes"]}


def _has_edge(workflow: dict[str, Any], source: str, source_output: str, target: str, target_input: str) -> bool:
    return any(
        edge.get("from") == {"node": source, "output": source_output}
        and edge.get("to") == {"node": target, "input": target_input}
        for edge in workflow["edges"]
    )


def test_fastq_qc_template_aggregates_fastp_and_fastqc_reports_in_multiqc() -> None:
    workflow = _load_template("fastq_qc_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["fastp_001"] == "fastp"
    assert node_types["fastqc_001"] == "fastqc"
    assert node_types["multiqc_001"] == "multiqc"

    assert _has_edge(workflow, "fastp_001", "report", "multiqc_001", "reports")
    assert _has_edge(workflow, "fastqc_001", "report_dir", "multiqc_001", "reports")
    assert _has_edge(workflow, "multiqc_001", "report", "validate_multiqc_001", "input")
