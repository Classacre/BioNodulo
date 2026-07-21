"""FastQC 0.12.1 command contract.

The ``fastqc`` launcher defines the CLI flags and validation. ``OfflineRunner``
defines input-derived report names and process exit behavior, while
``HTMLReportArchive`` defines the HTML, ZIP, and optional extracted outputs.
All three sources are pinned by ``GIT_COMMIT`` below.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


_FORMAT_OPTIONS = ("", "fastq", "sam", "bam", "sam_mapped", "bam_mapped")
_INPUT_SUFFIXES = (
    ".gz",
    ".bz2",
    ".txt",
    ".fastq",
    ".fq",
    ".csfastq",
    ".sam",
    ".bam",
    ".ubam",
)


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


def _report_stem(read_path: str) -> str:
    name = Path(read_path).name
    for suffix in _INPUT_SUFFIXES:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return f"{name}_fastqc"


class FastQCNode(CommandNode):
    """Generate one HTML/ZIP quality report pair for each input read file."""

    NODE_ID = "fastqc"
    DISPLAY_NAME = "FastQC"
    CATEGORY = "qc"
    DESCRIPTION = "Generate FastQC HTML and ZIP quality reports for sequencing reads"
    SEARCH_ALIASES = ["fastqc", "quality control", "qc", "reads qc"]
    RETURN_TYPES = ("QC_REPORT_DIR",)
    RETURN_NAMES = ("report_dir",)
    REQUIRED_EXECUTABLES = ["fastqc"]
    REQUIRED_CONDA_PACKAGES = ["fastqc"]
    DOCUMENTATION_URL = "https://www.bioinformatics.babraham.ac.uk/projects/fastqc/"
    VERSION = "0.12.1"
    GIT_URL = "https://github.com/s-andrews/FastQC.git"
    GIT_COMMIT = "e7ef390bf10382f60786bdd0cf28abd4f8683ffd"
    UPSTREAM_TAG = "v0.12.1"
    UPSTREAM_CLI_SOURCE = "fastqc"
    UPSTREAM_RUNNER_SOURCE = "uk/ac/babraham/FastQC/Analysis/OfflineRunner.java"
    UPSTREAM_ARCHIVE_SOURCE = "uk/ac/babraham/FastQC/Report/HTMLReportArchive.java"
    SOURCE_PATHS = (UPSTREAM_CLI_SOURCE, UPSTREAM_RUNNER_SOURCE, UPSTREAM_ARCHIVE_SOURCE)
    AUDIT_STATUS = "contract-checked-no-external-execution"
    EXIT_SEMANTICS = (
        "FastQC exits non-zero for invalid options or unreadable inputs; a zero exit is accepted "
        "only when every input has its HTML and ZIP report, plus the extracted directory when "
        "--extract is requested."
    )
    CITATION_URLS = [DOCUMENTATION_URL]
    CITATION_TEXT = "Andrews S. FastQC: A Quality Control Tool for High Throughput Sequence Data (2010)."
    OUTPUT_DIRECTORY = "report_dir.out"
    SHELL = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": (
                    "FASTQ_LIST",
                    {"description": "One or more readable FASTQ files"},
                ),
                "threads": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "description": "Number of input files processed concurrently; upstream requires a positive integer",
                        "display": "slider",
                    },
                ),
            },
            "optional": {
                "nogroup": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Show every base instead of grouping long reads",
                        "advanced": True,
                    },
                ),
                "kmers": (
                    "INT",
                    {
                        "default": 7,
                        "min": 2,
                        "max": 10,
                        "description": "K-mer length used by the Kmer Content module",
                        "advanced": True,
                    },
                ),
                "extract": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Extract each FastQC ZIP archive",
                        "advanced": True,
                    },
                ),
                "format": (
                    "STRING",
                    {
                        "default": "",
                        "options": list(_FORMAT_OPTIONS),
                        "description": "Force an input format instead of auto-detection",
                        "advanced": True,
                    },
                ),
                "contaminants": (
                    "FILE",
                    {
                        "default": "",
                        "description": "Named contaminant sequences (name, tab, sequence)",
                        "advanced": True,
                    },
                ),
                "adapters": (
                    "FILE",
                    {
                        "default": "",
                        "description": "Named adapter sequences (name, tab, sequence)",
                        "advanced": True,
                    },
                ),
                "limits": (
                    "FILE",
                    {
                        "default": "",
                        "description": "FastQC warning and error limits configuration",
                        "advanced": True,
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation

        reads = _path_values(inputs.get("reads"))
        if not reads:
            return "reads must contain at least one non-empty path"
        for read in reads:
            path = Path(read)
            if not path.is_file() or not os.access(path, os.R_OK):
                return f"Read file does not exist or is not readable: {read}"

        report_stems = [_report_stem(read) for read in reads]
        if len(report_stems) != len(set(report_stems)):
            return "reads must have unique FastQC output basenames"

        threads = inputs.get("threads")
        if isinstance(threads, bool) or not isinstance(threads, int):
            return "threads must be an integer"
        if threads < 1:
            return "threads must be at least 1"

        kmers = inputs.get("kmers")
        if kmers is not None:
            if isinstance(kmers, bool) or not isinstance(kmers, int):
                return "kmers must be an integer"
            if not 2 <= kmers <= 10:
                return "kmers must be between 2 and 10"

        input_format = inputs.get("format", "")
        if not isinstance(input_format, str) or input_format not in _FORMAT_OPTIONS:
            return "format must be auto, fastq, sam, bam, sam_mapped, or bam_mapped"

        for name in ("contaminants", "adapters", "limits"):
            value = inputs.get(name)
            if value in (None, ""):
                continue
            paths = _path_values(value)
            if paths is None or len(paths) != 1:
                return f"{name} must be a single file path"
            path = Path(paths[0])
            if not path.is_file() or not os.access(path, os.R_OK):
                return f"{name} file does not exist or is not readable: {paths[0]}"
        return True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        report_dir = Path(output_dir) / cls.NODE_ID / cls.OUTPUT_DIRECTORY
        # FastQC requires --outdir to exist before the process starts.
        report_dir.mkdir(parents=True, exist_ok=True)
        return [report_dir]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = [
            "fastqc",
            "--threads",
            str(inputs.get("threads", 1)),
            "--outdir",
            str(output / cls.OUTPUT_DIRECTORY),
        ]
        if inputs.get("nogroup"):
            command.append("--nogroup")
        if inputs.get("kmers") is not None:
            command.extend(["--kmers", str(inputs["kmers"])])
        if inputs.get("extract"):
            command.append("--extract")
        if inputs.get("format"):
            command.extend(["--format", str(inputs["format"])])
        for name, flag in (
            ("contaminants", "--contaminants"),
            ("adapters", "--adapters"),
            ("limits", "--limits"),
        ):
            if inputs.get(name):
                command.extend([flag, os.fsdecode(os.fspath(inputs[name]))])
        command.extend(_path_values(inputs.get("reads")) or [])
        return command

    async def run(self, **kwargs: Any) -> tuple[Any, ...] | dict[str, Any]:
        """Reject FastQC's successful exit when expected reports are absent."""

        reads = _path_values(kwargs.get("reads")) or []
        result = await super().run(**kwargs)
        if not isinstance(result, tuple) or not result:
            return result

        report_dir = Path(str(result[0]))
        expected: list[Path] = []
        for read in reads:
            stem = _report_stem(read)
            expected.extend((report_dir / f"{stem}.html", report_dir / f"{stem}.zip"))
            if kwargs.get("extract"):
                expected.append(report_dir / stem)
        missing = [path for path in expected if not path.exists()]
        if missing:
            missing_text = ", ".join(str(path) for path in missing)
            raise RuntimeError(f"FastQC completed but did not create expected report artifact(s): {missing_text}")
        return result
