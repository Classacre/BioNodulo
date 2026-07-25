"""HMMER 3.4 ``alimask`` contract."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .common import (
    HMMER_SOURCE_ROOT,
    HMMER_VERSION,
    HMMERContractNode,
    add_value,
    output_dir,
    planned_output,
    string_list,
)

_RANGE_RE = re.compile(r"^(?P<start>[1-9][0-9]*)-(?P<end>[1-9][0-9]*)$")


class HMMERAlimaskNode(HMMERContractNode):
    """Apply model- or alignment-coordinate masks to one MSA."""

    NODE_ID = "hmmer_alimask"
    VERSION = HMMER_VERSION
    DISPLAY_NAME = "HMMER alimask"
    CATEGORY = "annotation"
    DESCRIPTION = "Add a model- or alignment-coordinate mask to one multiple sequence alignment."
    SEARCH_ALIASES = ["BioNodulo builtin", "hmmer", "alimask", "alignment mask", "model range"]
    RETURN_TYPES = ("ALIGNMENT",)
    RETURN_NAMES = ("masked_alignment",)
    REQUIRED_EXECUTABLES = ["alimask"]
    DOCUMENTATION_URL = f"{HMMER_SOURCE_ROOT}/documentation/man/alimask.man.in"
    SOURCE_URL = f"{HMMER_SOURCE_ROOT}/src/alimask.c"
    SOURCE_PATHS = ("documentation/man/alimask.man.in", "src/alimask.c")
    UPSTREAM_SOURCE = "documentation/man/alimask.man.in; src/alimask.c::main"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "msafile": ("ALIGNMENT", {"description": "Single multiple sequence alignment to mask"}),
                "range_type": (
                    "STRING",
                    {
                        "default": "model",
                        "options": ["model", "ali"],
                        "description": "Interpret ranges as model or alignment coordinates",
                    },
                ),
                "ranges": (
                    "STRING",
                    {"is_list": True, "description": "Inclusive start-end ranges, for example 12-40"},
                ),
            },
            "optional": {
                "input_format": (
                    "STRING",
                    {"default": "--amino", "options": ["--amino", "--dna", "--rna"]},
                ),
                "model_construction": (
                    "STRING",
                    {"default": "fast", "options": ["fast", "hand"]},
                ),
                "symfrac": (
                    "FLOAT",
                    {
                        "default": 0.5,
                        "min": 0,
                        "max": 1,
                        "displayOptions": {"show": {"model_construction": ["fast"]}},
                    },
                ),
                "fragthresh": ("FLOAT", {"default": 0.5, "min": 0, "max": 1}),
                "relative_weighting": (
                    "STRING",
                    {
                        "default": "--wpb",
                        "options": ["--wpb", "--wgsc", "--wblosum", "--wnone", "--wgiven"],
                    },
                ),
                "wid": (
                    "FLOAT",
                    {
                        "default": 0.62,
                        "min": 0,
                        "max": 1,
                        "displayOptions": {"show": {"relative_weighting": ["--wblosum"]}},
                    },
                ),
                "seed": ("INT", {"default": 42, "min": 0}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        ranges = [part for value in string_list(inputs.get("ranges")) for part in value.split(",")]
        if not ranges:
            return "Input 'ranges' must contain at least one start-end range"
        for value in ranges:
            match = _RANGE_RE.fullmatch(value)
            if match is None or int(match.group("start")) > int(match.group("end")):
                return f"Input 'ranges' contains an invalid inclusive range: {value}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        ranges = [part for value in string_list(inputs["ranges"]) for part in value.split(",")]
        range_flag = "--alirange" if inputs.get("range_type", "model") == "ali" else "--modelrange"
        command = ["alimask", range_flag, ",".join(ranges)]
        command.append(str(inputs.get("input_format", "--amino")))
        construction = str(inputs.get("model_construction", "fast"))
        command.append(f"--{construction}")
        if construction == "fast":
            add_value(command, "--symfrac", inputs.get("symfrac", 0.5))
        add_value(command, "--fragthresh", inputs.get("fragthresh", 0.5))
        weighting = str(inputs.get("relative_weighting", "--wpb"))
        command.append(weighting)
        if weighting == "--wblosum":
            add_value(command, "--wid", inputs.get("wid", 0.62))
        add_value(command, "--seed", inputs.get("seed", 42))
        command.extend([str(inputs["msafile"]), f"{output_dir(inputs)}/masked.sto"])
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_root: str | Path) -> list[Path]:
        return [planned_output(output_root, cls.NODE_ID, "masked.sto")]
