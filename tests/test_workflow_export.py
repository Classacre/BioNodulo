from __future__ import annotations

import builtins

import pytest

from bionodulo.converter.cwl_converter import export_to_cwl
from bionodulo.converter.galaxy_converter import export_to_galaxy
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


def test_export_workflow_rejects_unavailable_converter_instead_of_placeholder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = builtins.__import__

    def import_with_missing_converter(
        name: str,
        globals: dict[str, object] | None = None,
        locals: dict[str, object] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "bionodulo.converter.snakemake_converter":
            raise ImportError("simulated missing converter")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", import_with_missing_converter)

    with pytest.raises(
        RuntimeError,
        match="Cannot export snakemake workflow because the converter module is unavailable",
    ):
        export_workflow(_workflow("fastqc"), "snakemake", name="qc")


def test_snakemake_export_rejects_unsupported_node_types_instead_of_placeholder_commands() -> None:
    with pytest.raises(ValueError, match="Cannot export unsupported node type 'custom_python' to SnakeMake"):
        export_to_snakemake(_workflow("custom_python"))


def test_nextflow_export_rejects_unsupported_node_types_instead_of_placeholder_commands() -> None:
    with pytest.raises(ValueError, match="Cannot export unsupported node type 'custom_python' to NextFlow"):
        export_to_nextflow(_workflow("custom_python"))


def test_cwl_export_rejects_unsupported_node_types_instead_of_placeholder_commands() -> None:
    with pytest.raises(ValueError, match="Cannot export unsupported node type 'custom_python' to CWL"):
        export_to_cwl(_workflow("custom_python"))


def test_galaxy_export_rejects_unsupported_node_types_instead_of_placeholder_tools() -> None:
    with pytest.raises(ValueError, match="Cannot export unsupported node type 'custom_python' to Galaxy"):
        export_to_galaxy(_workflow("custom_python"))
