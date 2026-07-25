"""HMMER 3.4 ``hmmconvert`` contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import HMMER_SOURCE_ROOT, HMMER_VERSION, HMMERContractNode, planned_output

_HMMER3_FORMATS = ["", "3/a", "3/b", "3/c", "3/d", "3/e", "3/f"]


class HMMERHmmconvertNode(HMMERContractNode):
    """Convert profile HMM files between documented HMMER formats."""

    NODE_ID = "hmmer_hmmconvert"
    VERSION = HMMER_VERSION
    DISPLAY_NAME = "HMMER hmmconvert"
    CATEGORY = "annotation"
    DESCRIPTION = "Convert HMMER profile files to HMMER3 ASCII or HMMER2 ASCII."
    SEARCH_ALIASES = ["BioNodulo builtin", "hmmer", "hmmconvert", "HMMER2", "HMMER3"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("converted_profile",)
    REQUIRED_EXECUTABLES = ["hmmconvert"]
    REQUIRED_PATH_INPUTS = ("hmmfile",)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = f"{HMMER_SOURCE_ROOT}/documentation/man/hmmconvert.man.in"
    SOURCE_URL = f"{HMMER_SOURCE_ROOT}/src/hmmconvert.c"
    SOURCE_PATHS = ("documentation/man/hmmconvert.man.in", "src/hmmconvert.c")
    UPSTREAM_SOURCE = "documentation/man/hmmconvert.man.in; src/hmmconvert.c::main"
    AUDIT_CAVEATS = [
        "HMMER's documented -b binary output is intentionally not exposed until stdout artifact capture is binary-safe."
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "hmmfile": ("FILE", {"description": "HMMER2 or HMMER3 profile file"}),
                "format": (
                    "STRING",
                    {
                        "default": "-a",
                        "options": ["-a", "-2"],
                        "description": "HMMER3 ASCII or HMMER2 ASCII output",
                    },
                ),
            },
            "optional": {
                "outfmt": (
                    "STRING",
                    {
                        "default": "",
                        "options": _HMMER3_FORMATS,
                        "description": "Optional historical HMMER3 ASCII format revision",
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
        if inputs.get("format", "-a") == "-2" and inputs.get("outfmt"):
            return "Input 'outfmt' is incompatible with HMMER2 output"
        return True

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        output_format = str(inputs.get("format", "-a"))
        if output_format == "-2":
            return "converted.hmm2"
        return "converted.hmm3"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        command = ["hmmconvert", str(inputs.get("format", "-a"))]
        if inputs.get("outfmt"):
            command.extend(["--outfmt", str(inputs["outfmt"])])
        command.append(str(inputs["hmmfile"]))
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_root: str | Path) -> list[Path]:
        return [planned_output(output_root, cls.NODE_ID, cls._output_name(inputs))]
