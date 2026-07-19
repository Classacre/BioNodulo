"""RSeQC read-NVC node pinned to the 5.0.3 sdist."""

from __future__ import annotations

from typing import Any

from .adapter import RSeQCCommandNode


class RSeQCReadNVCNode(RSeQCCommandNode):
    """Calculate nucleotide composition by read cycle."""

    NODE_ID = "rseqc_read_nvc"
    DISPLAY_NAME = "RSeQC Read NVC"
    DESCRIPTION = "Calculate nucleotide-versus-cycle composition across aligned reads."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "RSeQC",
        "read_NVC.py",
        "read NVC",
        "nucleotide composition",
        "RNA-seq QC",
    ]
    RETURN_TYPES = ("TSV", "TEXT", "IMAGE")
    RETURN_NAMES = ("nvc_table", "r_script", "nvc_plot")
    OUTPUT_FILENAMES = ("output.NVC.xls", "output.NVC_plot.r", "output.NVC_plot.pdf")
    REQUIRED_PATH_INPUTS = ("input",)
    REQUIRED_EXECUTABLES = ["read_NVC.py", "Rscript"]
    REQUIRED_CONDA_PACKAGES = ["rseqc", "r-base"]
    UPSTREAM_SCRIPT = "scripts/read_NVC.py"
    UPSTREAM_SOURCE = "scripts/read_NVC.py"
    UPSTREAM_OUTPUT_SOURCE = "lib/qcmodule/SAM.py:readsNVC"
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#read-nvc-py"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (
                    ("BAM", "SAM"),
                    {"description": "Input BAM or SAM alignment file with fixed read length"},
                ),
            },
            "optional": {
                "nx": (
                    "BOOLEAN",
                    {"default": False, "description": "Include N and X in the NVC output"},
                ),
                "mapq": (
                    "INT",
                    {
                        "default": 30,
                        "min": 0,
                        "max": 255,
                        "description": "Minimum mapping quality for uniquely mapped reads",
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
        if "rscript_output" in inputs:
            return "Legacy input 'rscript_output' is unsupported; the source always creates its R script"
        if not isinstance(inputs.get("nx", False), bool):
            return "Input 'nx' must be a boolean"
        return cls.validate_int(inputs.get("mapq", 30), "mapq", minimum=0, maximum=255)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "read_NVC.py")
        command.extend(
            [
                "-i",
                cls.path_value(inputs["input"]),
                "-o",
                str(cls.output_prefix(inputs)),
            ]
        )
        if inputs.get("nx", False):
            command.append("-x")
        command.extend(["-q", str(inputs.get("mapq", 30))])
        return command
