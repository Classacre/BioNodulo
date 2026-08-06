"""MultiQC 1.33 command contract.

The pinned CLI declares one or more existing files or directories as positional
inputs. The pinned result writer defines the report and parsed-data directory
names, and raises ``NoAnalysisFound`` with exit code 1 when nothing is parsed.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


def _path_values(value: Any) -> list[str] | None:
    if isinstance(value, (str, os.PathLike)):
        values = (value,)
    elif isinstance(value, (list, tuple)):
        values = value
    else:
        return None

    paths: list[str] = []
    for item in values:
        if not isinstance(item, (str, os.PathLike)):
            return None
        path = os.fsdecode(os.fspath(item))
        if not path.strip():
            return None
        paths.append(path)
    return paths


class MultiQCNode(CommandNode):
    """Aggregate recognized analysis files into HTML and parsed data outputs."""

    NODE_ID = "multiqc"
    DISPLAY_NAME = "MultiQC"
    CATEGORY = "qc"
    DESCRIPTION = "Aggregate recognized analysis outputs into a MultiQC report"
    SEARCH_ALIASES = ["multiqc", "aggregate qc", "report", "summary"]
    RETURN_TYPES = ("MULTIQC_REPORT", "DIRECTORY")
    RETURN_NAMES = ("report", "data_dir")
    REQUIRED_EXECUTABLES = ["multiqc"]
    REQUIRED_CONDA_PACKAGES = ["multiqc"]
    DOCUMENTATION_URL = "https://docs.seqera.io/multiqc/getting_started/running_multiqc/"
    VERSION = "1.33"
    GIT_URL = "https://github.com/MultiQC/MultiQC.git"
    GIT_COMMIT = "5953b5417ccb70bf4a2309562d43015fced8b585"
    UPSTREAM_TAG = "v1.33"
    SOURCE_REF = f"tag {UPSTREAM_TAG} at {GIT_COMMIT}"
    SOURCE_REVISION = GIT_COMMIT
    SOURCE_URL = f"https://github.com/MultiQC/MultiQC/tree/{GIT_COMMIT}"
    UPSTREAM_CLI_SOURCE = "multiqc/multiqc.py"
    UPSTREAM_OUTPUT_SOURCE = "multiqc/core/write_results.py"
    UPSTREAM_ERROR_SOURCE = "multiqc/core/exceptions.py"
    UPSTREAM_DOCS_SOURCE = "docs/markdown/getting_started/running_multiqc.md"
    SOURCE_PATHS = (UPSTREAM_CLI_SOURCE, UPSTREAM_OUTPUT_SOURCE, UPSTREAM_ERROR_SOURCE, UPSTREAM_DOCS_SOURCE)
    CITATION_DOIS = ["10.1093/bioinformatics/btw354"]
    CITATION_URLS = ["https://doi.org/10.1093/bioinformatics/btw354"]
    CITATION_TEXT = "MultiQC: summarize analysis results for multiple tools and samples in a single report."
    DEFAULT_FILENAME = "multiqc_report"
    AUDIT_STATUS = "contract-checked-no-external-execution"
    EXIT_SEMANTICS = (
        "MultiQC exits non-zero when no analysis is recognized or an input/output option fails; "
        "a zero exit is accepted only when the planned HTML report and parsed-data directory "
        "both exist. Existing names receive the same numeric suffix for both artifacts unless "
        "--force is selected."
    )
    SHELL = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                # MultiQC scans whatever it is pointed at, so a QC tool's report
                # DIRECTORY is its primary input -- fastqc -> multiqc is the
                # canonical use. Declaring FILE_LIST alone contradicted the
                # description below and made that link look invalid in the
                # editor, which users reasonably read as the tool being broken.
                "reports": (
                    "FILE_LIST|QC_REPORT_DIR|DIRECTORY|HTML_REPORT|KRAKEN_REPORT",
                    {"description": ("One or more files or directories containing recognizable analysis data")},
                ),
            },
            "optional": {
                "title": ("STRING", {"default": "", "label": "Report Title"}),
                "comment": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "label": "Comment",
                        "advanced": True,
                    },
                ),
                "force": (
                    "BOOLEAN",
                    {"default": False, "label": "Overwrite", "advanced": True},
                ),
                "filename": (
                    "STRING",
                    {
                        "default": cls.DEFAULT_FILENAME,
                        "label": "Output Filename",
                        "advanced": True,
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _filename_stem(cls, inputs: dict[str, Any]) -> str:
        filename = inputs.get("filename") or cls.DEFAULT_FILENAME
        if not isinstance(filename, str):
            return ""
        if filename.endswith(".html"):
            filename = filename[:-5]
        return filename

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation

        reports = _path_values(inputs.get("reports"))
        if not reports:
            return "reports must contain at least one non-empty path"
        for report in reports:
            if not Path(report).exists():
                return f"MultiQC search path does not exist: {report}"

        for name in ("title", "comment"):
            value = inputs.get(name)
            if value is not None and not isinstance(value, str):
                return f"{name} must be a string"

        filename = inputs.get("filename") or cls.DEFAULT_FILENAME
        if not isinstance(filename, str):
            return "filename must be a string"
        stem = cls._filename_stem(inputs)
        if stem == "stdout":
            return "filename cannot be stdout because this node returns a file"
        if not stem or stem in {".", ".."} or "\x00" in stem:
            return "filename must contain a usable file basename"
        if Path(stem).name != stem or "/" in stem or "\\" in stem:
            return "filename must not contain a directory path"
        return True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        stem = cls._filename_stem(inputs) or cls.DEFAULT_FILENAME
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        if not inputs.get("force"):
            report = node_out / f"{stem}.html"
            data_dir = node_out / f"{stem}_data"
            report_number = 1
            while report.exists() or data_dir.exists():
                report = node_out / f"{stem}_{report_number}.html"
                data_dir = node_out / f"{stem}_data_{report_number}"
                report_number += 1
            return [report, data_dir]
        return [node_out / f"{stem}.html", node_out / f"{stem}_data"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        reports = _path_values(inputs.get("reports")) or []
        output = str(inputs.get("output", inputs.get("output_dir", ".")))
        command = [
            "multiqc",
            *reports,
            "--outdir",
            output,
            "--filename",
            cls._filename_stem(inputs) or cls.DEFAULT_FILENAME,
        ]
        if inputs.get("title"):
            command.extend(["--title", str(inputs["title"])])
        if inputs.get("comment"):
            command.extend(["--comment", str(inputs["comment"])])
        if inputs.get("force"):
            command.append("--force")
        return command
