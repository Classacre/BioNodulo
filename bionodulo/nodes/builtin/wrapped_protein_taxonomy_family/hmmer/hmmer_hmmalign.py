"""HMMER 3.4 ``hmmalign`` contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import HMMER_SOURCE_ROOT, HMMER_VERSION, HMMERContractNode, add_value, output_dir, planned_output


class HMMERHmmalignNode(HMMERContractNode):
    """Align sequences to one profile HMM."""

    NODE_ID = "hmmer_hmmalign"
    VERSION = HMMER_VERSION
    DISPLAY_NAME = "HMMER hmmalign"
    CATEGORY = "alignment"
    DESCRIPTION = "Align sequences to one profile HMM and emit a Stockholm alignment."
    SEARCH_ALIASES = ["BioNodulo builtin", "hmmer", "hmmalign", "profile HMM alignment"]
    RETURN_TYPES = ("ALIGNMENT",)
    RETURN_NAMES = ("alignment",)
    REQUIRED_EXECUTABLES = ["hmmalign"]
    REQUIRED_PATH_INPUTS = ("hmmfile", "seq")
    DOCUMENTATION_URL = f"{HMMER_SOURCE_ROOT}/documentation/man/hmmalign.man.in"
    SOURCE_URL = f"{HMMER_SOURCE_ROOT}/src/hmmalign.c"
    SOURCE_PATHS = ("documentation/man/hmmalign.man.in", "src/hmmalign.c")
    UPSTREAM_SOURCE = "documentation/man/hmmalign.man.in; src/hmmalign.c::main"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "seq": ("FASTA", {"description": "Sequences to align against the profile"}),
                "hmmfile": ("HMM", {"description": "A file containing one profile HMM"}),
                "input_format_select": (
                    "STRING",
                    {
                        "default": "--amino",
                        "options": ["--amino", "--dna", "--rna"],
                        "description": "Assert the alphabet of both inputs",
                    },
                ),
            },
            "optional": {
                "trim": ("BOOLEAN", {"default": False}),
                "mapali": (
                    "ALIGNMENT",
                    {
                        "default": "",
                        "description": "Original model-building alignment to merge through the stored map",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        command = ["hmmalign", "-o", f"{output_dir(inputs)}/alignment.sto"]
        if inputs.get("trim", False):
            command.append("--trim")
        command.append(str(inputs.get("input_format_select", "--amino")))
        add_value(command, "--mapali", inputs.get("mapali"))
        command.extend(["--outformat", "stockholm", str(inputs["hmmfile"]), str(inputs["seq"])])
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_root: str | Path) -> list[Path]:
        return [planned_output(output_root, cls.NODE_ID, "alignment.sto")]
