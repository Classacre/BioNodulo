"""BEDTools closest node pinned to 2.31.1."""

from __future__ import annotations

import os
from typing import Any

from .adapter import BEDToolsCommandNode


class BEDToolsClosestNode(BEDToolsCommandNode):
    """Find the closest presorted annotation interval for each query interval."""

    NODE_ID = "bedtools_closest"
    DISPLAY_NAME = "BEDTools Closest"
    DESCRIPTION = "Append the closest feature and optional distance to each chromosome/start-sorted query interval"
    SEARCH_ALIASES = ["bedtools", "closest", "nearest gene", "nearest feature", "bed annotation"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("closest",)
    OUTPUT_FILENAMES = ("closest.tsv",)
    STDOUT_OUTPUT_INDEX = 0
    CONDA_PACKAGE_CONSTRAINTS = {"bedtools": "2.31.1"}
    PACKAGE_CONSTRAINTS = ("bedtools==2.31.1",)
    PACKAGE_CONSTRAINT = PACKAGE_CONSTRAINTS[0]
    DOCUMENTATION_URL = (
        "https://github.com/arq5x/bedtools2/blob/"
        "705ccfdf2c9a77d71560c8adcece0663c2f5e18e/docs/content/tools/closest.rst"
    )
    SOURCE_URL = DOCUMENTATION_URL
    SOURCE_SHA256 = "9882b5a8d106c6c6a14d09257961c79fdb78c542cedb86f27efdd0c34c33557b"
    UPSTREAM_SOURCE = (
        "docs/content/tools/closest.rst; src/utils/Contexts/ContextClosest.cpp; "
        "src/closestFile/closestFile.cpp; src/utils/RecordOutputMgr/RecordOutputMgr.cpp"
    )
    EXIT_SEMANTICS = (
        "closest enables BEDTools sorted-input checks internally and exits 1 for out-of-order records or "
        "inconsistent chromosome ordering; every other non-zero exit is fatal. Standard output is captured "
        "as the planned TSV artifact, which must exist after a zero exit."
    )

    TIE_MODES = ("all", "first", "last")
    STRAND_MODES = ("ignore", "same", "opposite")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "variants": (
                    "FILE",
                    {
                        "description": (
                            "BED, GFF, or VCF query intervals presorted by chromosome and start in the same chromosome "
                            "order as annotations"
                        )
                    },
                ),
                "annotations": (
                    "FILE",
                    {
                        "description": (
                            "BED, GFF, or VCF annotation intervals presorted by chromosome and start in the same "
                            "chromosome order as variants"
                        )
                    },
                ),
            },
            "optional": {
                "mode": ("STRING", {"default": "all", "options": list(cls.TIE_MODES)}),
                "distance": ("BOOLEAN", {"default": False}),
                "strand": ("STRING", {"default": "ignore", "options": list(cls.STRAND_MODES)}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in ("variants", "annotations"):
            try:
                value = os.fsdecode(os.fspath(inputs.get(key)))
            except TypeError:
                return f"Input '{key}' must be a non-empty path-like value"
            if not value.strip():
                return f"Input '{key}' must be a non-empty path-like value"
        mode = str(inputs.get("mode", "all"))
        if mode not in cls.TIE_MODES:
            return f"Unsupported BEDTools closest tie mode: {mode}"
        strand = str(inputs.get("strand", "ignore"))
        if strand not in cls.STRAND_MODES:
            return f"Unsupported BEDTools closest strand mode: {strand}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        command = [
            "bedtools",
            "closest",
            "-a",
            str(inputs.get("variants", "")),
            "-b",
            str(inputs.get("annotations", "")),
        ]
        if inputs.get("distance"):
            command.append("-d")
        strand = str(inputs.get("strand", "ignore"))
        if strand == "same":
            command.append("-s")
        elif strand == "opposite":
            command.append("-S")
        command.extend(["-t", str(inputs.get("mode", "all"))])
        return command
