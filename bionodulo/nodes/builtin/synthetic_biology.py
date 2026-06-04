"""Synthetic biology and BioCAD workflow nodes."""
from __future__ import annotations

import re
import textwrap
from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


def _safe_output_stem(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        text = fallback
    stem = Path(text).stem
    stem = re.sub(r"\.(gz|bz2|xz|zip)$", "", stem)
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._-")
    return stem or fallback


class SBOLDesignImportNode(CommandNode):
    """Import, normalize, and summarize SBOL designs with pySBOL3."""

    NODE_ID = "sbol_design_import"
    DISPLAY_NAME = "SBOL Design Import"
    CATEGORY = "synthetic_biology"
    DESCRIPTION = "Import and summarize Synthetic Biology Open Language designs with pySBOL3."
    SEARCH_ALIASES = ["sbol", "pysbol3", "synthetic biology", "biocad", "genetic design", "sbol3"]
    RETURN_TYPES = ("SBOL", "JSON")
    RETURN_NAMES = ("normalized_sbol", "summary")
    REQUIRED_EXECUTABLES = ["python"]
    REQUIRED_CONDA_PACKAGES = ["pysbol3"]
    DOCUMENTATION_URL = "https://pysbol3.readthedocs.io/"
    VERSION = "1.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get("output", ".")))
        out_dir.mkdir(parents=True, exist_ok=True)
        script_file = out_dir / "sbol_design_import.py"
        stem = _safe_output_stem(inputs.get("output_name"), _safe_output_stem(inputs.get("sbol_file"), "design"))
        output_format = str(inputs.get("output_format", "rdfxml") or "rdfxml")
        extension = ".nt" if output_format == "ntriples" else ".xml"
        normalized_path = out_dir / f"{stem}{extension}"
        summary_path = out_dir / f"{stem}.summary.json"
        namespace = str(inputs.get("namespace", "") or "").strip()
        validate = bool(inputs.get("validate", True))

        namespace_line = f"sbol3.set_namespace({namespace!r})" if namespace else ""
        validation_line = "report = doc.validate()" if validate else "report = None"
        validation_summary = (
            "\"validation_errors\": [str(result) for result in getattr(report, 'errors', [])],\n"
            "    \"validation_warnings\": [str(result) for result in getattr(report, 'warnings', [])],"
            if validate
            else "\"validation_errors\": [],\n    \"validation_warnings\": [],"
        )
        script = textwrap.dedent(f"""\
            from __future__ import annotations

            import json
            from pathlib import Path

            import sbol3

            {namespace_line}
            doc = sbol3.Document()
            doc.read({str(inputs.get("sbol_file", ""))!r})
            {validation_line}
            doc.write({str(normalized_path)!r}, file_format={output_format!r})

            def identity(obj):
                return str(getattr(obj, "identity", obj))

            components = [obj for obj in doc.objects if isinstance(obj, sbol3.Component)]
            sequences = [obj for obj in doc.objects if isinstance(obj, sbol3.Sequence)]
            interactions = []
            for component in components:
                interactions.extend(getattr(component, "interactions", []) or [])

            summary = {{
                "input_file": {str(inputs.get("sbol_file", ""))!r},
                "normalized_sbol": {str(normalized_path)!r},
                "object_count": len(doc.objects),
                "components": [identity(obj) for obj in components],
                "sequences": [identity(obj) for obj in sequences],
                "interactions": [identity(obj) for obj in interactions],
                "output_format": {output_format!r},
                {validation_summary}
            }}
            summary_path = Path({str(summary_path)!r})
            summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
        """)
        script_file.write_text(script, encoding="utf-8")
        return ["python", str(script_file)]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        stem = _safe_output_stem(inputs.get("output_name"), _safe_output_stem(inputs.get("sbol_file"), "design"))
        output_format = str(inputs.get("output_format", "rdfxml") or "rdfxml")
        extension = ".nt" if output_format == "ntriples" else ".xml"
        return [
            node_out / f"{stem}{extension}",
            node_out / f"{stem}.summary.json",
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "sbol_file": ("FILE", {"description": "SBOL file to import (.xml, .rdf, .nt, .ttl)"}),
            },
            "optional": {
                "namespace": ("STRING", {"default": "", "description": "Default SBOL namespace for generated identities"}),
                "validate": ("BOOLEAN", {"default": True, "description": "Validate the design after import"}),
                "output_format": ("STRING", {"default": "rdfxml", "options": ["rdfxml", "ntriples"]}),
                "output_name": ("STRING", {"default": "", "description": "Optional output filename stem"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class COPASISimulationNode(CommandNode):
    """Run COPASI batch simulations from configured COPASI, SED-ML, or COMBINE models."""

    NODE_ID = "copasi_simulation"
    DISPLAY_NAME = "COPASI Simulation"
    CATEGORY = "synthetic_biology"
    DESCRIPTION = "Run COPASI batch simulations using executable model tasks and capture reports."
    SEARCH_ALIASES = [
        "copasi",
        "CopasiSE",
        "synthetic biology",
        "biocad",
        "kinetic model",
        "sbml",
        "sed-ml",
        "combine archive",
    ]
    RETURN_TYPES = ("TSV", "CPS", "LOG", "JSON")
    RETURN_NAMES = ("report", "updated_model", "log", "metadata")
    REQUIRED_EXECUTABLES = ["CopasiSE", "python"]
    REQUIRED_CONDA_PACKAGES: list[str] = []
    DOCUMENTATION_URL = "https://copasi.org/Support/User_Manual/Model_Creation/Commandline_Version_and_Commandline_Options/"
    VERSION = "1.0"
    EXPERIMENTAL = True
    SHELL = True

    METADATA_SCRIPT = textwrap.dedent("""\
        from __future__ import annotations
        import json
        import sys
        from pathlib import Path

        (
            metadata_path,
            model_file,
            report_file,
            updated_model,
            log_file,
            executable,
            scheduled_task,
            sedml_task,
            validate_only,
            save_model,
            verbose,
            max_time,
        ) = sys.argv[1:13]

        def file_info(path_text):
            path = Path(path_text)
            return {
                "path": path_text,
                "exists": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() else 0,
            }

        metadata = {
            "model_file": model_file,
            "report": file_info(report_file),
            "updated_model": file_info(updated_model),
            "log": file_info(log_file),
            "copasi_executable": executable,
            "scheduled_task": scheduled_task,
            "sedml_task": sedml_task,
            "validate_only": validate_only.lower() == "true",
            "save_model": save_model.lower() == "true",
            "verbose": verbose.lower() == "true",
            "max_time": int(max_time),
        }
        Path(metadata_path).write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
    """)

    @classmethod
    def _planned_paths(cls, inputs: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path, Path, Path]:
        node_out = Path(output_dir)
        node_out.mkdir(parents=True, exist_ok=True)
        stem = _safe_output_stem(inputs.get("output_name"), _safe_output_stem(inputs.get("model_file"), "copasi"))
        return (
            node_out / f"{stem}.report.tsv",
            node_out / f"{stem}.updated.cps",
            node_out / f"{stem}.log",
            node_out / f"{stem}.metadata.json",
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get("output", ".")))
        out_dir.mkdir(parents=True, exist_ok=True)
        report_path, updated_model_path, log_path, metadata_path = cls._planned_paths(inputs, out_dir)

        model_file = str(inputs.get("model_file", ""))
        executable = str(inputs.get("copasi_executable", "") or "CopasiSE")
        scheduled_task = str(inputs.get("scheduled_task", "") or "").strip()
        sedml_task = str(inputs.get("sedml_task", "") or "").strip()
        save_model = bool(inputs.get("save_model", True))
        validate_only = bool(inputs.get("validate_only", False))
        verbose = bool(inputs.get("verbose", False))
        max_time = int(inputs.get("max_time", 0) or 0)

        if scheduled_task and sedml_task:
            raise ValueError("COPASI supports only one task override; set either scheduled_task or sedml_task, not both")
        if max_time < 0:
            raise ValueError("max_time must be greater than or equal to 0")

        cmd = [executable, "--nologo"]
        if verbose:
            cmd.append("--verbose")
        if validate_only:
            cmd.append("--validate")
        cmd.append(model_file)
        if save_model:
            cmd.extend(["-s", str(updated_model_path)])
        cmd.extend(["--report-file", str(report_path)])
        if scheduled_task:
            cmd.extend(["--scheduled-task", scheduled_task])
        if sedml_task:
            cmd.extend(["--sedmlTask", sedml_task])
        if max_time > 0:
            cmd.extend(["--maxTime", str(max_time)])

        cmd.extend([
            ">",
            str(log_path),
            "2>&1",
            "&&",
            "python",
            "-c",
            cls.METADATA_SCRIPT,
            str(metadata_path),
            model_file,
            str(report_path),
            str(updated_model_path),
            str(log_path),
            executable,
            scheduled_task,
            sedml_task,
            str(validate_only).lower(),
            str(save_model).lower(),
            str(verbose).lower(),
            str(max_time),
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        return list(cls._planned_paths(inputs, node_out))

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "model_file": ("FILE", {"description": "COPASI, SBML, SED-ML, or COMBINE archive model file"}),
            },
            "optional": {
                "copasi_executable": (
                    "STRING",
                    {"default": "CopasiSE", "description": "CopasiSE executable name or full path"},
                ),
                "scheduled_task": ("STRING", {"default": "", "description": "COPASI task name to run instead of the executable task"}),
                "sedml_task": ("STRING", {"default": "", "description": "SED-ML task id for SED-ML or COMBINE archive inputs"}),
                "save_model": ("BOOLEAN", {"default": True, "description": "Save the updated model after execution"}),
                "validate_only": ("BOOLEAN", {"default": False, "description": "Validate the model file before processing"}),
                "verbose": ("BOOLEAN", {"default": False, "description": "Enable COPASI verbose output"}),
                "max_time": ("INT", {"default": 0, "min": 0, "description": "Maximum CopasiSE runtime in seconds; 0 disables"}),
                "output_name": ("STRING", {"default": "", "description": "Optional output filename stem"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class iBioSimModelNode(CommandNode):
    """Execute iBioSim COMBINE/OMEX archives through the BioSimulators CLI."""

    NODE_ID = "ibiosim_model"
    DISPLAY_NAME = "iBioSim Model"
    CATEGORY = "synthetic_biology"
    DESCRIPTION = "Execute iBioSim COMBINE/OMEX archives containing SED-ML simulation experiments."
    SEARCH_ALIASES = [
        "ibiosim",
        "biosimulators",
        "synthetic biology",
        "biocad",
        "combine archive",
        "omex",
        "sed-ml",
        "sbml",
        "model simulation",
    ]
    RETURN_TYPES = ("DIRECTORY", "TSV", "JSON", "LOG")
    RETURN_NAMES = ("results_dir", "result_index", "metadata", "log")
    REQUIRED_EXECUTABLES = ["ibiosim", "python"]
    REQUIRED_CONDA_PACKAGES: list[str] = []
    DOCUMENTATION_URL = "https://docs.biosimulators.org/Biosimulators_iBioSim/"
    VERSION = "1.0"
    EXPERIMENTAL = True
    SHELL = True

    INDEX_SCRIPT = textwrap.dedent("""\
        from __future__ import annotations
        import csv
        import json
        import sys
        from pathlib import Path

        (
            results_dir,
            index_path,
            metadata_path,
            log_path,
            archive_file,
            execution_mode,
            executable,
            docker_image,
            quiet,
            debug,
        ) = sys.argv[1:11]

        root = Path(results_dir)
        rows = []
        if root.exists():
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    rows.append({
                        "relative_path": str(path.relative_to(root)),
                        "path": str(path),
                        "size_bytes": path.stat().st_size,
                    })

        index_file = Path(index_path)
        index_file.parent.mkdir(parents=True, exist_ok=True)
        with index_file.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["relative_path", "path", "size_bytes"], delimiter="\\t")
            writer.writeheader()
            writer.writerows(rows)

        log_file = Path(log_path)
        metadata = {
            "archive_file": archive_file,
            "results_dir": results_dir,
            "result_count": len(rows),
            "result_index": index_path,
            "log": {
                "path": log_path,
                "exists": log_file.exists(),
                "size_bytes": log_file.stat().st_size if log_file.exists() else 0,
            },
            "execution_mode": execution_mode,
            "ibiosim_executable": executable,
            "docker_image": docker_image,
            "quiet": quiet.lower() == "true",
            "debug": debug.lower() == "true",
        }
        Path(metadata_path).write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
    """)

    @classmethod
    def _planned_paths(cls, inputs: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path, Path, Path]:
        node_out = Path(output_dir)
        node_out.mkdir(parents=True, exist_ok=True)
        stem = _safe_output_stem(inputs.get("output_name"), _safe_output_stem(inputs.get("archive_file"), "ibiosim"))
        results_dir = node_out / stem
        return (
            results_dir,
            node_out / f"{stem}.result_index.tsv",
            node_out / f"{stem}.metadata.json",
            node_out / f"{stem}.log",
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get("output", ".")))
        out_dir.mkdir(parents=True, exist_ok=True)
        results_dir, index_path, metadata_path, log_path = cls._planned_paths(inputs, out_dir)
        results_dir.mkdir(parents=True, exist_ok=True)

        archive_file = str(inputs.get("archive_file", ""))
        execution_mode = str(inputs.get("execution_mode", "cli") or "cli").strip().lower()
        executable = str(inputs.get("ibiosim_executable", "") or "ibiosim")
        docker_image = str(inputs.get("docker_image", "") or "ghcr.io/biosimulators/ibiosim:latest")
        quiet = bool(inputs.get("quiet", False))
        debug = bool(inputs.get("debug", False))

        if execution_mode not in {"cli", "docker"}:
            raise ValueError("execution_mode must be one of: cli, docker")

        if execution_mode == "cli":
            cmd = [executable]
            if debug:
                cmd.append("-d")
            if quiet:
                cmd.append("-q")
            cmd.extend(["-i", archive_file, "-o", str(results_dir)])
        else:
            archive_path = Path(archive_file)
            archive_dir = archive_path.parent
            docker_archive = f"/tmp/ibiosim-input/{archive_path.name}"
            cmd = [
                "docker",
                "run",
                "--rm",
                "--mount",
                f"type=bind,source={archive_dir},target=/tmp/ibiosim-input,readonly",
                "--mount",
                f"type=bind,source={results_dir},target=/tmp/ibiosim-output",
                docker_image,
            ]
            if debug:
                cmd.append("-d")
            if quiet:
                cmd.append("-q")
            cmd.extend(["-i", docker_archive, "-o", "/tmp/ibiosim-output"])

        cmd.extend([
            ">",
            str(log_path),
            "2>&1",
            "&&",
            "python",
            "-c",
            cls.INDEX_SCRIPT,
            str(results_dir),
            str(index_path),
            str(metadata_path),
            str(log_path),
            archive_file,
            execution_mode,
            executable,
            docker_image,
            str(quiet).lower(),
            str(debug).lower(),
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        return list(cls._planned_paths(inputs, node_out))

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "archive_file": ("FILE", {"description": "COMBINE/OMEX archive containing SED-ML simulation experiments"}),
            },
            "optional": {
                "execution_mode": ("STRING", {"default": "cli", "options": ["cli", "docker"]}),
                "ibiosim_executable": (
                    "STRING",
                    {"default": "ibiosim", "description": "BioSimulators-iBioSim CLI executable name or full path"},
                ),
                "docker_image": (
                    "STRING",
                    {"default": "ghcr.io/biosimulators/ibiosim:latest", "description": "Docker image for docker execution mode"},
                ),
                "quiet": ("BOOLEAN", {"default": False, "description": "Suppress iBioSim console output"}),
                "debug": ("BOOLEAN", {"default": False, "description": "Enable iBioSim debug mode"}),
                "output_name": ("STRING", {"default": "", "description": "Optional output directory and filename stem"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
