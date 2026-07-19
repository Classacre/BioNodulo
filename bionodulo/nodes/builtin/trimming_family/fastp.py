"""Pinned fastp 0.24.0 single-end and paired-end preprocessing contract.

The focused wrapper exposes the ordinary filtered FASTQ outputs plus fastp's
always-generated HTML and JSON reports.  The JSON report is a first-class port
because MultiQC parses it directly.  Optional modes that change output arity
(``unpaired``, ``failed``, ``overlapped``, ``merge``, ``stdout``, and split
outputs) are intentionally outside this node contract instead of being
represented by speculative ports.  fastp has no sidecar files; the ``.gz``
suffix selects gzip output and this wrapper passes the upstream compression
default explicitly.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


def _read_paths(value: Any) -> list[str]:
    """Normalize one FASTQ path or an ordered one/two-path collection."""

    if isinstance(value, (str, os.PathLike)):
        values = [value]
    elif isinstance(value, (list, tuple)):
        values = list(value)
    else:
        raise TypeError("reads must be a FASTQ path or an ordered FASTQ collection")

    paths: list[str] = []
    for item in values:
        try:
            path = os.fsdecode(os.fspath(item))
        except TypeError as exc:
            raise TypeError("each read must be a path-like value") from exc
        if not path.strip():
            raise ValueError("read paths must be non-empty")
        paths.append(path)
    return paths


class FastpNode(CommandNode):
    """Trim and filter one FASTQ or an ordered R1/R2 pair with fastp."""

    NODE_ID = "fastp"
    DISPLAY_NAME = "fastp Trim"
    CATEGORY = "trimming"
    DESCRIPTION = "Trim adapters and filter single-end or paired-end FASTQ reads with fastp"
    SEARCH_ALIASES = ["fastp", "trim", "adapter", "quality filter", "fastq qc"]
    RETURN_TYPES = ("FASTQ_LIST", "HTML_REPORT", "JSON")
    RETURN_NAMES = ("trimmed_reads", "report", "json_report")
    REQUIRED_EXECUTABLES = ["fastp"]
    REQUIRED_CONDA_PACKAGES = ["fastp"]
    PACKAGE_CONSTRAINTS = ("fastp==0.24.0",)
    PACKAGE_CONSTRAINT = PACKAGE_CONSTRAINTS[0]
    DOCUMENTATION_URL = "https://github.com/OpenGene/fastp/tree/v0.24.0"
    VERSION = "0.24.0"
    GIT_URL = "https://github.com/OpenGene/fastp.git"
    GIT_COMMIT = "4f273f1d8afac977a82460e1de174daa3e66f3f5"
    SOURCE_URL = f"https://github.com/OpenGene/fastp/tree/{GIT_COMMIT}"
    CITATION_DOIS = ["10.1002/imt2.107"]
    CITATION_URLS = ["https://doi.org/10.1002/imt2.107"]
    CITATION_TEXT = "Ultrafast one-pass FASTQ data preprocessing, quality control, and deduplication using fastp."
    UPSTREAM_README = "README.md"
    UPSTREAM_CLI_SOURCE = "src/main.cpp"
    UPSTREAM_VALIDATION_SOURCE = "src/options.cpp"
    UPSTREAM_ERROR_SOURCE = "src/util.h"
    UPSTREAM_SOURCE_PATHS = (
        UPSTREAM_README,
        UPSTREAM_CLI_SOURCE,
        UPSTREAM_VALIDATION_SOURCE,
        UPSTREAM_ERROR_SOURCE,
    )
    AUDIT_STATUS = "contract-checked-no-external-execution"
    EXIT_SEMANTICS = (
        "fastp returns 0 on success; validation and I/O failures call error_exit, "
        "which exits -1 (reported as 255 by POSIX shells)."
    )

    READ1_FILENAME = "trimmed_reads.fastq.gz"
    READ2_FILENAME = "trimmed_reads_2.fastq.gz"
    HTML_FILENAME = "report.html"
    JSON_FILENAME = "report.json"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": (
                    "FASTQ_LIST",
                    {"description": ("One single-end FASTQ or an ordered paired-end collection [R1, R2]")},
                ),
                "threads": (
                    "INT",
                    {"default": 3, "min": 1, "max": 16, "display": "slider"},
                ),
            },
            "optional": {
                "compression": (
                    "INT",
                    {
                        "default": 4,
                        "min": 1,
                        "max": 9,
                        "description": "Gzip compression level (fastp default: 4)",
                        "advanced": True,
                    },
                ),
                "qualified_quality_phred": (
                    "INT",
                    {
                        "default": 15,
                        "min": 0,
                        "max": 93,
                        "description": ("Minimum Phred score for a base to be qualified (fastp default: 15)"),
                    },
                ),
                "cut_front": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Enable 5-prime sliding-window quality cutting",
                    },
                ),
                "cut_tail": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Enable 3-prime sliding-window quality cutting",
                    },
                ),
                "length_required": (
                    "INT",
                    {
                        "default": 15,
                        "min": 1,
                        "description": ("Discard reads shorter than this length (fastp default: 15)"),
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

        try:
            reads = _read_paths(inputs.get("reads"))
        except (TypeError, ValueError) as exc:
            return str(exc)
        if len(reads) not in (1, 2):
            return "reads must contain exactly one single-end FASTQ or two paired FASTQs"

        ranges = {
            "threads": (1, 16, 3),
            "compression": (1, 9, 4),
            "qualified_quality_phred": (0, 93, 15),
        }
        for name, (minimum, maximum, default) in ranges.items():
            value = inputs.get(name, default)
            if isinstance(value, bool) or not isinstance(value, int):
                return f"{name} must be an integer"
            if not minimum <= value <= maximum:
                return f"{name} must be between {minimum} and {maximum}"

        length_required = inputs.get("length_required", 15)
        if isinstance(length_required, bool) or not isinstance(length_required, int):
            return "length_required must be an integer"
        if length_required <= 0:
            return "length_required must be greater than zero"
        return True

    @classmethod
    def _output_paths(
        cls,
        inputs: dict[str, Any],
        output_dir: str | Path,
    ) -> tuple[list[Path], Path, Path]:
        reads = _read_paths(inputs.get("reads"))
        if len(reads) not in (1, 2):
            raise ValueError("reads must contain exactly one single-end FASTQ or two paired FASTQs")
        node_out = Path(output_dir) / cls.NODE_ID
        trimmed = [node_out / cls.READ1_FILENAME]
        if len(reads) == 2:
            trimmed.append(node_out / cls.READ2_FILENAME)
        return trimmed, node_out / cls.HTML_FILENAME, node_out / cls.JSON_FILENAME

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        trimmed, html_report, json_report = cls._output_paths(inputs, output_dir)
        html_report.parent.mkdir(parents=True, exist_ok=True)
        return [*trimmed, html_report, json_report]

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Any]:
        """Group physical artifacts into the node's three public output ports."""

        if len(planned_paths) not in (3, 4):
            raise ValueError("fastp must plan one or two FASTQs plus HTML and JSON")
        return {
            "trimmed_reads": list(planned_paths[:-2]),
            "report": planned_paths[-2],
            "json_report": planned_paths[-1],
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        reads = _read_paths(inputs.get("reads"))
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = ["fastp", "--in1", reads[0]]
        if len(reads) == 2:
            command.extend(["--in2", reads[1]])
        command.extend(["--out1", str(output / cls.READ1_FILENAME)])
        if len(reads) == 2:
            command.extend(["--out2", str(output / cls.READ2_FILENAME)])
        command.extend(["--compression", str(inputs.get("compression", 4))])
        if inputs.get("cut_front", False):
            command.append("--cut_front")
        if inputs.get("cut_tail", False):
            command.append("--cut_tail")
        command.extend(
            [
                "--qualified_quality_phred",
                str(inputs.get("qualified_quality_phred", 15)),
                "--length_required",
                str(inputs.get("length_required", 15)),
                "--json",
                str(output / cls.JSON_FILENAME),
                "--html",
                str(output / cls.HTML_FILENAME),
                "--thread",
                str(inputs.get("threads", 3)),
            ]
        )
        return command

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        """Execute fastp and group its one/two FASTQs under one stable port."""

        output_dir = kwargs.get("output_dir")
        context = kwargs.get("context")
        if output_dir is None and context is not None:
            output_dir = getattr(context, "node_dir", ".")
        if output_dir is None:
            output_dir = "."

        execution_inputs = dict(kwargs)
        execution_inputs["output_dir"] = output_dir
        await super().run(**execution_inputs)

        trimmed, html_report, json_report = self.__class__._output_paths(kwargs, output_dir)
        return {
            "outputs": {
                "trimmed_reads": [str(path) for path in trimmed],
                "report": str(html_report),
                "json_report": str(json_report),
            }
        }
