"""RSeQC ``RNA_fragment_size.py`` node pinned to the 5.0.3 sdist."""

from __future__ import annotations

from typing import Any

from .adapter import RSeQCCommandNode


class RSeQCRNAFragmentSizeNode(RSeQCCommandNode):
    """Report per-transcript RNA fragment-size statistics."""

    NODE_ID = "rseqc_rna_fragment_size"
    DISPLAY_NAME = "RSeQC RNA Fragment Size"
    DESCRIPTION = "Calculate fragment-size statistics per gene or transcript from an indexed BAM."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "RSeQC",
        "RNA_fragment_size.py",
        "RNA fragment size",
        "fragment length",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("fragment_sizes",)
    REQUIRED_EXECUTABLES = ["RNA_fragment_size.py"]
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#rna-fragment-size-py"
    UPSTREAM_SCRIPT = "scripts/RNA_fragment_size.py"
    UPSTREAM_SOURCE = UPSTREAM_SCRIPT
    UPSTREAM_OUTPUT_SOURCE = "scripts/RNA_fragment_size.py:main (stdout)"
    OUTPUT_FILENAMES = ("fragment_sizes.tsv",)
    STDOUT_OUTPUT_INDEX = 0
    REQUIRED_PATH_INPUTS = ("input", "bam_index", "refgene")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "Coordinate-indexed BAM input"}),
                "bam_index": (
                    "BAI",
                    {"description": "Exact sibling index at <input BAM>.bai"},
                ),
                "refgene": (
                    "BED",
                    {"description": "Standard 12-column BED gene model"},
                ),
            },
            "optional": {
                "mapq": (
                    "INT",
                    {
                        "default": 30,
                        "min": 0,
                        "max": 255,
                        "description": "Minimum mapping quality",
                    },
                ),
                "frag_num": (
                    "INT",
                    {
                        "default": 3,
                        "min": 1,
                        "description": "Minimum fragments required for non-zero statistics",
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
        validation = cls.validate_bam_index(inputs, bam_key="input", index_key="bam_index")
        if validation is not True:
            return validation
        validation = cls.validate_int(inputs.get("mapq", 30), "mapq", minimum=0, maximum=255)
        if validation is not True:
            return validation
        return cls.validate_int(inputs.get("frag_num", 3), "frag_num", minimum=1)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "RNA_fragment_size.py")
        command.extend(
            [
                "-i",
                cls.path_value(inputs.get("input")),
                "-r",
                cls.path_value(inputs.get("refgene")),
                "-q",
                str(inputs.get("mapq", 30)),
                "-n",
                str(inputs.get("frag_num", 3)),
            ]
        )
        return command
