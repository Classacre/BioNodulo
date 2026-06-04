from __future__ import annotations

import builtins
import csv
import json
import subprocess
import sys
from pathlib import Path

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


def _frontend_connected_workflow() -> dict:
    return {
        "id": "frontend-export-test",
        "name": "Frontend Export Test",
        "nodes": [
            {
                "id": "qc",
                "type": "fastqc",
                "widgets": {},
                "outputs": {
                    "html": {"path": "results/qc/fastqc.html"},
                },
                "meta": {},
            },
            {
                "id": "summary",
                "type": "multiqc",
                "widgets": {},
                "inputs": {"reports": {"type": "FILE"}},
                "outputs": {
                    "html": {"path": "results/summary/multiqc.html"},
                },
                "meta": {},
            },
        ],
        "edges": [
            {
                "id": "edge-qc-summary",
                "from": {"node": "qc", "output": "html"},
                "to": {"node": "summary", "input": "reports"},
            }
        ],
    }


def _frontend_node_info_output_workflow() -> dict:
    workflow = _frontend_connected_workflow()
    for node in workflow["nodes"]:
        node.pop("outputs", None)
        node["node_info"] = {
            "return_names": ["html"],
            "return_types": ["FILE"],
        }
    return workflow


def _normalize_data_workflow() -> dict:
    return {
        "id": "normalize-export-test",
        "name": "Normalize Export Test",
        "nodes": [
            {
                "id": "norm",
                "type": "normalize_data",
                "inputs": {"table": {"type": "FILE"}},
                "widgets": {
                    "method": "min_max",
                    "id_columns": "gene",
                    "axis": "columns",
                    "output_type": "TSV",
                },
                "outputs": {"normalized_table": {"path": "results/norm/normalized.tsv"}},
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


def test_cwl_export_supports_normalize_data_with_builtin_node_runner() -> None:
    exported = export_to_cwl(_normalize_data_workflow())
    workflow = json.loads(exported["workflow.cwl"])
    tool = json.loads(exported["tools/norm.cwl"])

    assert workflow["inputs"] == {"norm_table": "File"}
    assert workflow["steps"]["norm"]["in"] == {"table": "norm_table"}
    assert tool["baseCommand"] == ["python3", "-m", "bionodulo.converter.cwl_node_runner"]
    assert tool["arguments"] == [
        "--node-type",
        "normalize_data",
        "--output-dir",
        ".",
        "--input",
        "table",
        "$(inputs.table.path)",
        "--input",
        "method",
        "$(inputs.method)",
        "--input",
        "id_columns",
        "$(inputs.id_columns)",
        "--input",
        "axis",
        "$(inputs.axis)",
        "--input",
        "pseudocount",
        "$(inputs.pseudocount)",
        "--input",
        "min_max_range",
        "$(inputs.min_max_range)",
        "--input",
        "output_type",
        "$(inputs.output_type)",
    ]
    assert tool["inputs"]["method"]["default"] == "min_max"
    assert tool["inputs"]["pseudocount"]["default"] == 1.0
    assert tool["outputs"] == {
        "normalized_table": {
            "type": "File",
            "outputBinding": {"glob": "normalized_table_output"},
        }
    }


def test_cwl_exported_normalize_data_command_executes(tmp_path: Path) -> None:
    exported = export_to_cwl(_normalize_data_workflow())
    tool = json.loads(exported["tools/norm.cwl"])
    table = tmp_path / "counts.tsv"
    with table.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["gene", "s1", "s2"], delimiter="\t")
        writer.writeheader()
        writer.writerows([
            {"gene": "A", "s1": "10", "s2": "20"},
            {"gene": "B", "s1": "5", "s2": "5"},
        ])

    defaults = {name: spec.get("default") for name, spec in tool["inputs"].items()}
    replacements = {
        "$(inputs.table.path)": str(table),
        **{f"$(inputs.{name})": str(value) for name, value in defaults.items() if value is not None},
    }
    command = [*tool["baseCommand"], *(replacements.get(argument, argument) for argument in tool["arguments"])]
    completed = subprocess.run(command, cwd=tmp_path, check=False, capture_output=True, text=True)

    assert completed.returncode == 0, completed.stderr
    with (tmp_path / "normalized_table_output").open(newline="", encoding="utf-8") as fh:
        assert list(csv.DictReader(fh, delimiter="\t")) == [
            {"gene": "A", "s1": "0", "s2": "1"},
            {"gene": "B", "s1": "0", "s2": "0"},
        ]


def test_cwl_node_runner_executes_normalize_data_node(tmp_path: Path) -> None:
    table = tmp_path / "counts.tsv"
    with table.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["gene", "s1", "s2"], delimiter="\t")
        writer.writeheader()
        writer.writerows([
            {"gene": "A", "s1": "10", "s2": "20"},
            {"gene": "B", "s1": "5", "s2": "5"},
        ])

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "bionodulo.converter.cwl_node_runner",
            "--node-type",
            "normalize_data",
            "--output-dir",
            ".",
            "--input",
            "table",
            str(table),
            "--input",
            "method",
            "min_max",
            "--input",
            "id_columns",
            "gene",
            "--input",
            "axis",
            "columns",
            "--input",
            "output_type",
            "TSV",
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    with (tmp_path / "normalized_table_output").open(newline="", encoding="utf-8") as fh:
        assert list(csv.DictReader(fh, delimiter="\t")) == [
            {"gene": "A", "s1": "0", "s2": "1"},
            {"gene": "B", "s1": "0", "s2": "0"},
        ]


def test_cwl_node_runner_rejects_unmapped_builtin_nodes(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "bionodulo.converter.cwl_node_runner",
            "--node-type",
            "fastqc",
            "--output-dir",
            ".",
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert "Cannot execute unsupported CWL runner node type: fastqc" in completed.stderr


def test_galaxy_export_rejects_unsupported_node_types_instead_of_placeholder_tools() -> None:
    with pytest.raises(ValueError, match="Cannot export unsupported node type 'custom_python' to Galaxy"):
        export_to_galaxy(_workflow("custom_python"))


def test_snakemake_export_preserves_frontend_shaped_edges() -> None:
    exported = export_to_snakemake(_frontend_connected_workflow())

    assert (
        'rule summary:\n'
        '    input:\n'
        '        "results/qc/fastqc.html",\n'
        '    output:'
    ) in exported


def test_nextflow_export_preserves_frontend_shaped_edges() -> None:
    exported = export_to_nextflow(_frontend_connected_workflow())

    assert "process summary {\n" in exported
    assert "    input:\n        path input_0 from qc" in exported
    assert "    summary(ch_qc)" in exported


def test_cwl_export_preserves_frontend_shaped_edges() -> None:
    exported = export_to_cwl(_frontend_connected_workflow())
    workflow = json.loads(exported["workflow.cwl"])

    assert workflow["steps"]["summary"]["in"] == {"reports": "qc/html"}


def test_galaxy_export_preserves_frontend_shaped_edges() -> None:
    exported = json.loads(export_to_galaxy(_frontend_connected_workflow()))
    summary_step = next(step for step in exported["steps"].values() if step["label"] == "summary")

    assert summary_step["input_connections"] == {
        "reports": {
            "id": 1,
            "output_name": "html",
        }
    }


def test_snakemake_export_derives_outputs_from_frontend_node_info() -> None:
    exported = export_to_snakemake(_frontend_node_info_output_workflow())

    assert '"results/summary/html_output",' in exported
    assert (
        'rule summary:\n'
        '    input:\n'
        '        "results/qc/html_output",\n'
        '    output:\n'
        '        html="results/summary/html_output",'
    ) in exported


def test_nextflow_export_derives_outputs_from_frontend_node_info() -> None:
    exported = export_to_nextflow(_frontend_node_info_output_workflow())

    assert "process summary {\n" in exported
    assert '    output:\n        path "html_output"' in exported


def test_cwl_export_derives_outputs_from_frontend_node_info() -> None:
    exported = export_to_cwl(_frontend_node_info_output_workflow())
    workflow = json.loads(exported["workflow.cwl"])
    summary_tool = json.loads(exported["tools/summary.cwl"])

    assert workflow["steps"]["summary"]["out"] == ["html"]
    assert workflow["outputs"]["summary_html"]["outputSource"] == "summary/html"
    assert summary_tool["outputs"] == {
        "html": {
            "type": "File",
            "outputBinding": {"glob": "html_output"},
        }
    }


def test_galaxy_export_derives_outputs_from_frontend_node_info() -> None:
    exported = json.loads(export_to_galaxy(_frontend_node_info_output_workflow()))
    summary_step = next(step for step in exported["steps"].values() if step["label"] == "summary")

    assert summary_step["outputs"] == [
        {
            "name": "html",
            "type": "data",
            "output_name": "html",
        }
    ]
