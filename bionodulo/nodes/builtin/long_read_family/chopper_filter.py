"""Chopper 0.9.2 FASTQ filtering with uncompressed stdout capture."""

from __future__ import annotations

from typing import Any

from .adapter import (
    LongReadCommandNode,
    option_value,
    path_value,
    validate_int,
    validate_number,
)


class ChopperFilterNode(LongReadCommandNode):
    """Filter and trim one FASTQ file while retaining Chopper's stdout format."""

    NODE_ID = "chopper_filter"
    DISPLAY_NAME = "Chopper Filter"
    DESCRIPTION = "Filter and trim one long-read FASTQ file with Chopper"
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "Chopper",
        "long-read filtering",
        "FASTQ trimming",
        "NanoFilt replacement",
    ]
    RETURN_TYPES = ("FASTQ",)
    RETURN_NAMES = ("filtered_reads",)
    OUTPUT_FILENAMES = ("filtered_reads.fastq",)
    STDOUT_OUTPUT_INDEX = 0
    REQUIRED_PATH_INPUTS = ("reads",)
    REQUIRED_EXECUTABLES = ["chopper"]
    REQUIRED_CONDA_PACKAGES = ["chopper"]
    PACKAGE_CONSTRAINT = "chopper = 0.9.2"
    VERSION = "0.9.2"
    GIT_URL = "https://github.com/wdecoster/chopper.git"
    GIT_COMMIT = "ca85a03f6c4a8836ab5f163592e24a30b9d3a3c4"
    SOURCE_TAG = "v0.9.2"
    DOCUMENTATION_URL = "https://github.com/wdecoster/chopper/tree/v0.9.2"
    UPSTREAM_SOURCE = "src/main.rs; src/utils.rs"
    CITATION_DOIS = ["10.1093/bioinformatics/btad311"]
    CITATION_URLS = ["https://doi.org/10.1093/bioinformatics/btad311"]
    CITATION_TEXT = "NanoPack2: population-scale evaluation of long-read sequencing data."
    EXIT_SEMANTICS = (
        "Invalid input files and decompression errors return non-zero; malformed "
        "FASTQ records or thread-pool construction errors panic and return non-zero."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": (
                    "FASTQ",
                    {"description": "One FASTQ input; gzip, bzip2, and xz are auto-detected"},
                ),
            },
            "optional": {
                "min_quality": ("FLOAT", {"default": 0.0, "min": 0.0}),
                "max_quality": ("FLOAT", {"default": 1000.0, "min": 0.0}),
                "min_length": ("INT", {"default": 1, "min": 0}),
                "max_length": ("INT", {"default": None, "min": 0}),
                "headcrop": ("INT", {"default": 0, "min": 0}),
                "tailcrop": ("INT", {"default": 0, "min": 0}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 256}),
                "contaminant_reference": (
                    "FASTA",
                    {"default": "", "description": "FASTA used by Chopper's contaminant filter"},
                ),
                "inverse": ("BOOLEAN", {"default": False}),
                "min_gc": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0}),
                "max_gc": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key, default in (("min_quality", 0.0), ("max_quality", 1000.0)):
            validation = validate_number(option_value(inputs, key, default), key, minimum=0)
            if validation is not True:
                return validation
        for key, default, minimum in (
            ("min_length", 1, 0),
            ("headcrop", 0, 0),
            ("tailcrop", 0, 0),
            ("threads", 4, 1),
        ):
            validation = validate_int(option_value(inputs, key, default), key, minimum=minimum)
            if validation is not True:
                return validation
        if inputs.get("max_length") is not None:
            validation = validate_int(inputs["max_length"], "max_length", minimum=0)
            if validation is not True:
                return validation
        for key, default in (("min_gc", 0.0), ("max_gc", 1.0)):
            validation = validate_number(
                option_value(inputs, key, default),
                key,
                minimum=0,
                maximum=1,
            )
            if validation is not True:
                return validation
        if float(option_value(inputs, "min_quality", 0.0)) > float(option_value(inputs, "max_quality", 1000.0)):
            return "Input 'min_quality' must not exceed 'max_quality'"
        if float(option_value(inputs, "min_gc", 0.0)) > float(option_value(inputs, "max_gc", 1.0)):
            return "Input 'min_gc' must not exceed 'max_gc'"
        contaminant = inputs.get("contaminant_reference")
        if contaminant not in (None, "") and not path_value(contaminant):
            return "Input 'contaminant_reference' must be a non-empty path-like value"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "chopper")
        command.extend(
            [
                "--quality",
                str(option_value(inputs, "min_quality", 0.0)),
                "--maxqual",
                str(option_value(inputs, "max_quality", 1000.0)),
                "--minlength",
                str(option_value(inputs, "min_length", 1)),
            ]
        )
        max_length = inputs.get("max_length")
        if max_length is not None:
            command.extend(["--maxlength", str(max_length)])
        headcrop = option_value(inputs, "headcrop", 0)
        if headcrop:
            command.extend(["--headcrop", str(headcrop)])
        tailcrop = option_value(inputs, "tailcrop", 0)
        if tailcrop:
            command.extend(["--tailcrop", str(tailcrop)])
        command.extend(["--threads", str(option_value(inputs, "threads", 4))])
        if inputs.get("contaminant_reference"):
            command.extend(["--contam", path_value(inputs["contaminant_reference"])])
        if option_value(inputs, "inverse", False):
            command.append("--inverse")
        command.extend(
            [
                "--input",
                path_value(inputs["reads"]),
                "--maxgc",
                str(option_value(inputs, "max_gc", 1.0)),
                "--mingc",
                str(option_value(inputs, "min_gc", 0.0)),
            ]
        )
        return command
