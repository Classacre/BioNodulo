"""NanoPlot 1.44.1 long-read QC with mutually exclusive source inputs."""

from __future__ import annotations

from typing import Any

from .adapter import (
    LongReadCommandNode,
    option_value,
    path_list,
    validate_int,
)


class NanoPlotQCNode(LongReadCommandNode):
    """Generate NanoPlot's native HTML report and NanoStats text file."""

    NODE_ID = "nanoplot"
    DISPLAY_NAME = "NanoPlot QC"
    DESCRIPTION = "Generate NanoPlot quality-control plots and long-read summary statistics"
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "NanoPlot",
        "long-read QC",
        "Nanopore QC",
        "read statistics",
    ]
    RETURN_TYPES = ("HTML_REPORT", "STATS_FILE")
    RETURN_NAMES = ("qc_report", "qc_stats")
    OUTPUT_FILENAMES = ("NanoPlot-report.html", "NanoStats.txt")
    REQUIRED_EXECUTABLES = ["NanoPlot"]
    REQUIRED_CONDA_PACKAGES = ["nanoplot"]
    CONDA_PACKAGE_CONSTRAINTS = {"nanoplot": "1.44.1"}
    PACKAGE_CONSTRAINT = "nanoplot = 1.44.1"
    VERSION = "1.44.1"
    SOURCE_URL = (
        "https://files.pythonhosted.org/packages/0d/b4/"
        "4b1aa17b9a4f2c750ddde6a53132e1ecdc23dbcb0db823032dca8e17489c/"
        "NanoPlot-1.44.1.tar.gz"
    )
    SOURCE_SHA256 = "c9d6b3c807d46fb3eb293bc826a94b699d17f50fb7fd0dcc3f17f56b0cee8e57"
    DOCUMENTATION_URL = "https://github.com/wdecoster/NanoPlot"
    UPSTREAM_SOURCE = "nanoplot/utils.py; nanoplot/NanoPlot.py"
    SOURCE_AUTHORITIES = {
        "pypi_sdist": (SOURCE_URL, SOURCE_SHA256),
        "argv_parser": "nanoplot/utils.py:get_args",
        "native_outputs": "nanoplot/NanoPlot.py:make_stats,make_report",
    }
    AUDIT_STATUS = "contract-checked-no-binary-execution"
    CITATION_DOIS = ["10.1093/bioinformatics/bty149"]
    CITATION_URLS = ["https://doi.org/10.1093/bioinformatics/bty149"]
    CITATION_TEXT = "NanoPack: visualizing and processing long-read sequencing data."
    EXIT_SEMANTICS = (
        "Argument errors and empty post-filter datasets exit non-zero; uncaught "
        "data or plotting exceptions are logged, reported, and re-raised."
    )
    INPUT_FLAGS = {
        "fastq": "--fastq",
        "fasta": "--fasta",
        "summary": "--summary",
        "bam": "--bam",
        "ubam": "--ubam",
        "cram": "--cram",
    }
    PLOT_FORMATS = ("png", "jpg", "jpeg", "webp", "svg", "pdf", "eps", "json")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {},
            "optional": {
                "fastq": ("FASTQ_LIST", {"default": [], "multiple": True}),
                "fasta": ("FASTA_LIST", {"default": [], "multiple": True}),
                "summary": ("FILE_LIST", {"default": [], "multiple": True}),
                "bam": ("BAM_LIST", {"default": [], "multiple": True}),
                "ubam": ("BAM_LIST", {"default": [], "multiple": True}),
                "cram": ("FILE_LIST", {"default": [], "multiple": True}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 256}),
                "plot_format": (
                    "STRING",
                    {"default": "png", "options": list(cls.PLOT_FORMATS)},
                ),
                "max_length": ("INT", {"default": None, "min": 0}),
                "min_length": ("INT", {"default": None, "min": 0}),
                "loglength": ("BOOLEAN", {"default": False}),
                "show_n50": ("BOOLEAN", {"default": False}),
                "tsv_stats": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _selected_input(cls, inputs: dict[str, Any]) -> tuple[str, list[str]] | None:
        selected = [(key, paths) for key in cls.INPUT_FLAGS if (paths := path_list(inputs.get(key)))]
        return selected[0] if len(selected) == 1 else None

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        selected_count = sum(bool(path_list(inputs.get(key))) for key in cls.INPUT_FLAGS)
        if selected_count != 1:
            return "Exactly one NanoPlot input source must be provided"
        validation = validate_int(option_value(inputs, "threads", 4), "threads", minimum=1)
        if validation is not True:
            return validation
        plot_format = str(option_value(inputs, "plot_format", "png"))
        if plot_format not in cls.PLOT_FORMATS:
            return f"Input 'plot_format' must be one of: {', '.join(cls.PLOT_FORMATS)}"
        for key in ("max_length", "min_length"):
            if inputs.get(key) is not None:
                validation = validate_int(inputs[key], key, minimum=0)
                if validation is not True:
                    return validation
        max_length = inputs.get("max_length")
        min_length = inputs.get("min_length")
        if max_length is not None and min_length is not None and min_length > max_length:
            return "Input 'min_length' must not exceed 'max_length'"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get("output", inputs.get("output_dir", ".")))
        command = cls.checked_command(
            inputs,
            "NanoPlot",
            "--outdir",
            output,
            "--threads",
            str(option_value(inputs, "threads", 4)),
            "--format",
            str(option_value(inputs, "plot_format", "png")),
        )
        max_length = inputs.get("max_length")
        if max_length is not None:
            command.extend(["--maxlength", str(max_length)])
        min_length = inputs.get("min_length")
        if min_length is not None:
            command.extend(["--minlength", str(min_length)])
        if option_value(inputs, "loglength", False):
            command.append("--loglength")
        if option_value(inputs, "show_n50", False):
            command.append("--N50")
        if option_value(inputs, "tsv_stats", False):
            command.append("--tsv_stats")
        selected = cls._selected_input(inputs)
        assert selected is not None
        key, paths = selected
        command.append(cls.INPUT_FLAGS[key])
        command.extend(paths)
        return command
