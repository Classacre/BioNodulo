"""RSeQC 5.0.3 ``FPKM_count.py`` node."""

from __future__ import annotations

from typing import Any

from .adapter import RSeQCCommandNode


class RSeQCFPKMCountNode(RSeQCCommandNode):
    """Calculate per-transcript fragment counts, FPM, and FPKM values."""

    NODE_ID = "rseqc_fpkm_count"
    DISPLAY_NAME = "RSeQC FPKM Count"
    DESCRIPTION = "Calculate raw fragment count, FPM, and FPKM for a BED12 gene model."
    SEARCH_ALIASES = ["BioNodulo builtin", "RSeQC", "FPKM_count", "FPKM", "gene expression"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("fpkm_counts",)
    REQUIRED_EXECUTABLES = ["FPKM_count.py"]
    OUTPUT_FILENAMES = ("output.FPKM.xls",)
    UPSTREAM_SCRIPT = "scripts/FPKM_count.py"
    UPSTREAM_SOURCE = UPSTREAM_SCRIPT
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#fpkm-count-py"

    REQUIRED_PATH_INPUTS = ("input", "bam_index", "refgene")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "BAM alignment file"}),
                "bam_index": ("BAI", {"description": "Exact sibling input BAM index (<bam>.bai)"}),
                "refgene": ("BED", {"description": "Reference gene model in BED12 format"}),
            },
            "optional": {
                "strand": (
                    "STRING",
                    {
                        "default": "",
                        "description": "RSeQC strand rule (two or four comma-separated mappings)",
                    },
                ),
                "skip_multi_hits": ("BOOLEAN", {"default": False}),
                "only_exonic": ("BOOLEAN", {"default": False}),
                "mapq": ("INT", {"default": 30, "min": 0, "max": 255}),
                "single_read": (
                    "FLOAT",
                    {"default": 1, "min": 0.0, "max": 1.0, "description": "Weight for one-end-mapped pairs"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        stale = sorted({key for key in ("strand_specific", "pair_type", "single_type") if key in inputs})
        if stale:
            return f"Legacy RSeQC strand controls are unsupported: {', '.join(stale)}; use strand"
        validation = cls.validate_bam_index(inputs)
        if validation is not True:
            return validation
        validation = cls.validate_int(inputs.get("mapq", 30), "mapq", minimum=0, maximum=255)
        if validation is not True:
            return validation
        validation = cls.validate_number(inputs.get("single_read", 1), "single_read", minimum=0.0, maximum=1.0)
        if validation is not True:
            return validation
        return _validate_strand_rule(inputs.get("strand", ""), "strand")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(
            inputs,
            "FPKM_count.py",
            "-i",
            str(inputs["input"]),
            "-o",
            str(cls.output_prefix(inputs, "output")),
            "-r",
            str(inputs["refgene"]),
        )
        if inputs.get("strand"):
            command.extend(["-d", str(inputs["strand"])])
        if inputs.get("skip_multi_hits"):
            command.append("-u")
        if inputs.get("only_exonic"):
            command.append("-e")
        command.extend(["-q", str(inputs.get("mapq", 30)), "-s", str(inputs.get("single_read", 1))])
        return command


def _validate_strand_rule(value: Any, key: str) -> bool | str:
    """Reject malformed rules before RSeQC's dictionary lookup fails later."""
    if value in (None, ""):
        return True
    parts = str(value).split(",")
    if len(parts) == 2:
        if {part[0] for part in parts if len(part) == 2} != {"+", "-"} or any(
            len(part) != 2 or part[1] not in "+-" for part in parts
        ):
            return f"Input '{key}' must map both single-end strands"
    elif len(parts) == 4:
        if {part[:2] for part in parts if len(part) == 3} != {"1+", "1-", "2+", "2-"} or any(
            len(part) != 3 or part[2] not in "+-" for part in parts
        ):
            return f"Input '{key}' must map all four paired-end read/strand combinations"
    else:
        return f"Input '{key}' must contain two or four RSeQC strand mappings"
    return True
