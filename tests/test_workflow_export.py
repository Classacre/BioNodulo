from __future__ import annotations

import pytest

from bionodulo.converter.nextflow_converter import export_to_nextflow
from bionodulo.converter.snakemake_converter import export_to_snakemake
from bionodulo.workflow.export import export_workflow


def _workflow(node_type: str) -> dict:
    return {
        "id": "export-test",
        "name": "Export Test",
        "nodes": [
            {
                "id": "qc",
                "type": node_type,
                "widgets": {},
                "outputs": {
                    "html": {"path": "results/qc/fastqc.html"},
                },
                "meta": {},
            }
        ],
        "edges": [],
    }


def test_export_workflow_delegates_to_pipeline_converters() -> None:
    snakemake = export_workflow(_workflow("fastqc"), "snakemake", name="qc")
    nextflow = export_workflow(_workflow("fastqc"), "nextflow", name="qc")
    cwl = export_workflow(_workflow("fastqc"), "cwl", name="qc")
    galaxy = export_workflow(_workflow("fastqc"), "galaxy", name="qc")

    assert "rule qc:" in snakemake
    assert "fastqc -o" in snakemake
    assert "process qc {" in nextflow
    assert "fastqc -o" in nextflow
    assert "workflow.cwl" in cwl
    assert "\"a_galaxy_workflow\": \"true\"" in galaxy


def test_snakemake_export_rejects_unsupported_node_types_instead_of_placeholder_commands() -> None:
    with pytest.raises(ValueError, match="Cannot export unsupported node type 'custom_python' to SnakeMake"):
        export_to_snakemake(_workflow("custom_python"))


def test_nextflow_export_rejects_unsupported_node_types_instead_of_placeholder_commands() -> None:
    with pytest.raises(ValueError, match="Cannot export unsupported node type 'custom_python' to NextFlow"):
        export_to_nextflow(_workflow("custom_python"))
