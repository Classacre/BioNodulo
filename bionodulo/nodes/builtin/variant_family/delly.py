"""DELLY 1.2.6 structural-variant calling with native BCF output."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import (
    IndexedBamReferenceNode,
    option_value,
    validate_choice,
    validate_integer,
)


class DellyNode(IndexedBamReferenceNode):
    """Call short- or long-read structural variants with DELLY."""

    NODE_ID = "delly"
    DISPLAY_NAME = "DELLY SV Caller"
    DESCRIPTION = "Paired-end, split-read, or long-read structural-variant caller"
    SEARCH_ALIASES = [
        "delly",
        "structural variant",
        "sv caller",
        "somatic sv",
        "long-read sv",
    ]
    RETURN_TYPES = ("BCF", "VCF_INDEX")
    RETURN_NAMES = ("sv_calls", "sv_calls_index")
    OUTPUT_FILENAMES = ("sv_calls.bcf", "sv_calls.bcf.csi")
    REQUIRED_EXECUTABLES = ["delly"]
    REQUIRED_CONDA_PACKAGES = ["delly"]
    DOCUMENTATION_URL = "https://github.com/dellytools/delly"
    VERSION = "1.2.6"
    GIT_URL = "https://github.com/dellytools/delly.git"
    GIT_COMMIT = "e6246dbb18b7f6df2b7b381d542cdeaea6be8c82"
    SOURCE_URL = f"https://github.com/dellytools/delly/tree/{GIT_COMMIT}"
    PACKAGE_CONSTRAINTS = ("delly==1.2.6",)
    PACKAGE_CONSTRAINT = "delly==1.2.6"
    EXIT_SEMANTICS = "Input validation or a non-zero DELLY or conversion command fails the node."
    AUDIT_STATUS = "contract-checked-no-external-execution"
    CITATION_DOIS = ["10.1093/bioinformatics/bts378"]
    CITATION_URLS = ["https://doi.org/10.1093/bioinformatics/bts378"]
    CITATION_TEXT = "DELLY: structural variant discovery by integrated paired-end and split-read analysis."
    UPSTREAM_SOURCE = "src/delly.h"
    UPSTREAM_LONG_READ_SOURCE = "src/tegua.h"
    UPSTREAM_OUTPUT_SOURCE = "src/modvcf.h"
    MODES = ("call", "lr")
    TECHNOLOGIES = ("ont", "pb")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Coordinate-sorted input BAM"}),
                "bam_index": (
                    "BAI",
                    {"description": "Exact <bam>.bai index for the input BAM"},
                ),
                "reference": (
                    "FASTA",
                    {"description": "Reference FASTA with a colocated FAI"},
                ),
                "reference_index": (
                    "FASTA_INDEX",
                    {"description": "Exact <reference>.fai index"},
                ),
                "mode": (
                    "STRING",
                    {"default": "call", "options": list(cls.MODES)},
                ),
            },
            "optional": {
                "exclude_regions": (
                    "BED",
                    {"description": "Regions excluded from discovery", "advanced": True},
                ),
                "map_qual": (
                    "INT",
                    {"default": 1, "min": 0, "label": "Min MapQ", "advanced": True},
                ),
                "technology": (
                    "STRING",
                    {
                        "default": "ont",
                        "options": list(cls.TECHNOLOGIES),
                        "description": "Long-read sequencing technology used by delly lr",
                        "advanced": True,
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _render_delly_command(
        cls,
        inputs: dict[str, Any],
        output_bcf: Path,
    ) -> list[str]:
        mode = str(option_value(inputs, "mode", "call"))
        command = [
            "delly",
            mode,
            "-g",
            str(inputs["reference"]),
            "-o",
            str(output_bcf),
        ]
        if inputs.get("exclude_regions"):
            command.extend(["-x", str(inputs["exclude_regions"])])
        command.extend(["-q", str(option_value(inputs, "map_qual", 1))])
        if mode == "lr":
            command.extend(["-y", str(option_value(inputs, "technology", "ont"))])
        command.append(str(inputs["bam"]))
        return command

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        return cls._render_delly_command(inputs, output / "sv_calls.bcf")

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_choice(inputs, "mode", "call", cls.MODES)
        if validation is not True:
            return validation
        validation = validate_integer(inputs, "map_qual", 1, minimum=0)
        if validation is not True:
            return validation
        return validate_choice(inputs, "technology", "ont", cls.TECHNOLOGIES)
