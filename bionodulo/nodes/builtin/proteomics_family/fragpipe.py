"""FragPipe 24.0 headless workflow contract."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .adapter import ProteomicsCommandNode, path_list, path_value, require_file, stage_file, validate_int


class FragPipeWorkflowNode(ProteomicsCommandNode):
    """Run a user-supplied FragPipe workflow with explicit staged inputs."""

    NODE_ID = "fragpipe"
    DISPLAY_NAME = "FragPipe Workflow"
    DESCRIPTION = "Run a FragPipe 24.0 headless workflow with an explicit manifest and database."
    SEARCH_ALIASES = ["BioNodulo builtin", "FragPipe", "MSFragger", "headless proteomics workflow"]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("results_dir",)
    REQUIRED_EXECUTABLES = ["fragpipe"]
    REQUIRED_CONDA_PACKAGES = ["fragpipe"]
    REQUIRED_PATH_INPUTS = ("workflow_file", "manifest_file", "fasta_db")
    REQUIRED_PATH_LIST_INPUTS = ("raw_files",)
    VERSION = "24.0"
    GIT_URL = "https://github.com/Nesvilab/FragPipe.git"
    GIT_COMMIT = "c2f256cb6a6a28a89a8b4d4da2e0e8eaee1ef3a5"
    DOCUMENTATION_URL = "https://fragpipe.nesvilab.org/docs/tutorial_fragpipe_headless.html"
    UPSTREAM_SOURCE = "FragPipe 24.0 release start scripts and headless CLI documentation"
    WRAPPER_AUTHORITY = (
        "Bioconda fragpipe 24.0 recipe and license wrapper at "
        "0f45cb6931cc383705d156ad4e7e8c7e5015b505"
    )
    CITATION_DOIS = ["10.1074/mcp.TIR120.002048"]
    CITATION_URLS = ["https://doi.org/10.1074/mcp.TIR120.002048"]
    CITATION_TEXT = "FragPipe computational platform for comprehensive proteomics analysis."
    RUN_IN_NODE_OUTPUT_DIR = True
    EXPERIMENTAL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "raw_files": (
                    "FILE_LIST",
                    {"multiple": True, "description": "Spectrum files named .mzML, .mzXML, or .raw"},
                ),
                "workflow_file": ("FILE", {"description": "FragPipe .workflow file"}),
                "manifest_file": (
                    "TSV",
                    {"description": "Four-column FragPipe manifest matching raw-file basenames"},
                ),
                "fasta_db": ("FASTA", {"description": "Protein database referenced by the workflow"}),
                "msfragger_key": ("STRING", {"description": "MSFragger license key"}),
                "ionquant_key": ("STRING", {"description": "IonQuant license key"}),
            },
            "optional": {
                "threads": (
                    "INT",
                    {"default": None, "min": 0, "description": "Optional FragPipe thread limit; zero means auto"},
                ),
                "memory_gb": (
                    "INT",
                    {"default": None, "min": 0, "description": "Optional FragPipe RAM limit in GB; zero means auto"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        raw_files = path_list(inputs.get("raw_files"))
        if len({Path(path).name for path in raw_files}) != len(raw_files):
            return "Input 'raw_files' must have unique basenames"
        if any(Path(path).suffix.lower() not in {".mzml", ".mzxml", ".raw"} for path in raw_files):
            return "Input 'raw_files' must use .mzML, .mzXML, or .raw filenames"
        for key in ("msfragger_key", "ionquant_key"):
            if not str(inputs.get(key, "")).strip():
                return f"Input '{key}' must be non-empty"
        if inputs.get("threads") is not None:
            validation = validate_int(inputs["threads"], "threads", minimum=0)
            if validation is not True:
                return validation
        if inputs.get("memory_gb") is not None:
            return validate_int(inputs["memory_gb"], "memory_gb", minimum=0)
        return True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        return [node_dir / "results"]

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        cls.require_valid_inputs(inputs)
        node_dir = outputs[0].parent
        outputs[0].mkdir(parents=True, exist_ok=True)
        scans_dir = node_dir / "scans"
        staged = {
            Path(path).name: stage_file(path, "raw_files", scans_dir)
            for path in path_list(inputs["raw_files"])
        }
        fasta = stage_file(inputs["fasta_db"], "fasta_db", node_dir, name="database.fasta")

        manifest_path = require_file(inputs["manifest_file"], "manifest_file")
        with manifest_path.open(newline="", encoding="utf-8") as handle:
            rows = [row for row in csv.reader(handle, delimiter="\t") if row]
        if not rows or any(len(row) != 4 for row in rows):
            raise ValueError("FragPipe manifest must contain four tab-separated columns per row")
        data_types = {
            value.lower(): value
            for value in ("DDA", "DIA", "DDA+", "DIA-Quant", "DIA-Lib", "GPF-DIA")
        }
        for row in rows:
            normalized = row[3].strip().lower()
            if normalized not in data_types:
                raise ValueError(
                    "FragPipe manifest data type must be DDA, DIA, DDA+, DIA-Quant, DIA-Lib, or GPF-DIA"
                )
            row[3] = data_types[normalized]
        manifest_names = [Path(row[0]).name for row in rows]
        if len(set(manifest_names)) != len(manifest_names):
            raise ValueError("FragPipe manifest contains duplicate spectrum basenames")
        if set(manifest_names) != set(staged):
            raise ValueError("FragPipe manifest spectrum names must exactly match raw_files basenames")
        prepared_manifest = node_dir / "fragpipe.manifest"
        with prepared_manifest.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
            for row in rows:
                writer.writerow([str(staged[Path(row[0]).name].absolute()), *row[1:]])

        workflow_path = require_file(inputs["workflow_file"], "workflow_file")
        workflow_lines = workflow_path.read_text(encoding="utf-8").splitlines()
        database_line = f"database.db-path={fasta.absolute()}"
        replaced = False
        for index, line in enumerate(workflow_lines):
            if line.startswith("database.db-path="):
                workflow_lines[index] = database_line
                replaced = True
                break
        if not replaced:
            workflow_lines.append(database_line)
        prepared_workflow = node_dir / "fragpipe.workflow"
        prepared_workflow.write_text("\n".join(workflow_lines) + "\n", encoding="utf-8")
        inputs["_fragpipe_manifest"] = str(prepared_manifest)
        inputs["_fragpipe_workflow"] = str(prepared_workflow)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        output = Path(path_value(inputs.get("output", ".")))
        command = [
            "fragpipe",
            "--msfragger_key",
            str(inputs["msfragger_key"]),
            "--ionquant_key",
            str(inputs["ionquant_key"]),
            "--headless",
        ]
        if inputs.get("threads") is not None:
            command.extend(["--threads", str(inputs["threads"])])
        if inputs.get("memory_gb") is not None:
            command.extend(["--ram", str(inputs["memory_gb"])])
        command.extend(
            [
                "--workflow",
                str(inputs.get("_fragpipe_workflow", output / "fragpipe.workflow")),
                "--manifest",
                str(inputs.get("_fragpipe_manifest", output / "fragpipe.manifest")),
                "--workdir",
                str(output / "results"),
            ]
        )
        return command
