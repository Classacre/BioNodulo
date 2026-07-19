"""RSeQC 5.0.3 ``RPKM_saturation.py`` node."""

from __future__ import annotations

from typing import Any

from .adapter import RSeQCCommandNode


class RSeQCRPKMSaturationNode(RSeQCCommandNode):
    """Assess expression-estimate saturation by repeated read resampling."""

    NODE_ID = "rseqc_rpkm_saturation"
    DISPLAY_NAME = "RSeQC RPKM Saturation"
    DESCRIPTION = "Assess whether per-gene RPKM estimates are saturated by sequencing depth."
    SEARCH_ALIASES = ["BioNodulo builtin", "RSeQC", "RPKM_saturation", "RPKM saturation", "expression saturation"]
    RETURN_TYPES = ("TSV", "TSV", "TEXT", "IMAGE")
    RETURN_NAMES = ("rpkm_values", "raw_counts", "r_script", "saturation_plot")
    REQUIRED_EXECUTABLES = ["RPKM_saturation.py", "Rscript"]
    REQUIRED_CONDA_PACKAGES = ["rseqc", "r-base"]
    OUTPUT_FILENAMES = (
        "output.eRPKM.xls",
        "output.rawCount.xls",
        "output.saturation.r",
        "output.saturation.pdf",
    )
    UPSTREAM_SCRIPT = "scripts/RPKM_saturation.py"
    UPSTREAM_SOURCE = UPSTREAM_SCRIPT
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#rpkm-saturation-py"

    REQUIRED_PATH_INPUTS = ("input", "refgene")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (("BAM", "SAM"), {"description": "SAM or BAM alignment file"}),
                "refgene": ("BED", {"description": "Reference gene model in BED format"}),
            },
            "optional": {
                "strand": ("STRING", {"default": "", "description": "RSeQC strand rule"}),
                "percentile_floor": ("INT", {"default": 5, "min": 0, "max": 100}),
                "percentile_ceiling": ("INT", {"default": 100, "min": 0, "max": 100}),
                "percentile_step": ("INT", {"default": 5, "min": 1, "max": 100}),
                "rpkm_cutoff": ("FLOAT", {"default": 0.01, "min": 0.0}),
                "mapq": ("INT", {"default": 30, "min": 0, "max": 255}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        stale = sorted(
            {key for key in ("strand_specific", "pair_type", "single_type", "rscript_output") if key in inputs}
        )
        if stale:
            return f"Legacy RSeQC controls are unsupported: {', '.join(stale)}"
        floor = inputs.get("percentile_floor", 5)
        ceiling = inputs.get("percentile_ceiling", 100)
        step = inputs.get("percentile_step", 5)
        for key, value in (("percentile_floor", floor), ("percentile_ceiling", ceiling), ("percentile_step", step)):
            validation = cls.validate_int(value, key, minimum=0, maximum=100)
            if validation is not True:
                return validation
        if int(step) == 0:
            return "Input 'percentile_step' must be greater than zero"
        if int(floor) > int(ceiling):
            return "percentile_floor must not exceed percentile_ceiling"
        if int(step) > int(ceiling):
            return "percentile_step must not exceed percentile_ceiling"
        validation = cls.validate_number(inputs.get("rpkm_cutoff", 0.01), "rpkm_cutoff", minimum=0.0)
        if validation is not True:
            return validation
        validation = cls.validate_int(inputs.get("mapq", 30), "mapq", minimum=0, maximum=255)
        if validation is not True:
            return validation
        return _validate_strand_rule(inputs.get("strand", ""), "strand")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(
            inputs,
            "RPKM_saturation.py",
            "-i",
            str(inputs["input"]),
            "-o",
            str(cls.output_prefix(inputs, "output")),
            "-r",
            str(inputs["refgene"]),
        )
        if inputs.get("strand"):
            command.extend(["-d", str(inputs["strand"])])
        command.extend(
            [
                "-l",
                str(inputs.get("percentile_floor", 5)),
                "-u",
                str(inputs.get("percentile_ceiling", 100)),
                "-s",
                str(inputs.get("percentile_step", 5)),
                "-c",
                str(inputs.get("rpkm_cutoff", 0.01)),
                "-q",
                str(inputs.get("mapq", 30)),
            ]
        )
        return command


def _validate_strand_rule(value: Any, key: str) -> bool | str:
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
