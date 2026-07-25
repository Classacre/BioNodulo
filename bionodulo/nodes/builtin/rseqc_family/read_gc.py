"""RSeQC read-GC node pinned to the 5.0.3 sdist."""

from __future__ import annotations

from typing import Any

from .adapter import RSeQCCommandNode


class RSeQCReadGCNode(RSeQCCommandNode):
    """Calculate GC-content distribution for aligned reads."""

    NODE_ID = "rseqc_read_gc"
    DISPLAY_NAME = "RSeQC Read GC"
    DESCRIPTION = "Calculate the GC-content distribution of reads in a BAM or SAM alignment."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "RSeQC",
        "read_GC.py",
        "read GC",
        "GC content",
        "GC bias",
        "RNA-seq QC",
    ]
    RETURN_TYPES = ("TSV", "TEXT", "IMAGE")
    RETURN_NAMES = ("gc_counts", "r_script", "gc_plot")
    OUTPUT_FILENAMES = ("output.GC.xls", "output.GC_plot.r", "output.GC_plot.pdf")
    REQUIRED_PATH_INPUTS = ("input",)
    REQUIRED_EXECUTABLES = ["read_GC.py", "Rscript"]
    REQUIRED_CONDA_PACKAGES = ["rseqc", "r-base"]
    UPSTREAM_SCRIPT = "scripts/read_GC.py"
    UPSTREAM_SOURCE = "scripts/read_GC.py"
    UPSTREAM_OUTPUT_SOURCE = "lib/qcmodule/SAM.py:readGC"
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#read-gc-py"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (
                    ("BAM", "SAM"),
                    {"description": "Input BAM or SAM alignment file"},
                ),
            },
            "optional": {
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
        return cls.validate_int(inputs.get("mapq", 30), "mapq", minimum=0, maximum=255)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "read_GC.py")
        command.extend(
            [
                "-i",
                cls.path_value(inputs["input"]),
                "-o",
                str(cls.output_prefix(inputs)),
                "-q",
                str(inputs.get("mapq", 30)),
            ]
        )
        return command
