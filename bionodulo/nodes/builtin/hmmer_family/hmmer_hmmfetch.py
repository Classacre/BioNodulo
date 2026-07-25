"""HMMER 3.4 ``hmmfetch`` contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import HMMER_SOURCE_ROOT, HMMER_VERSION, HMMERContractNode, output_dir, planned_output


class HMMERHmmfetchNode(HMMERContractNode):
    """Retrieve multiple named models from a profile HMM database."""

    NODE_ID = "hmmer_hmmfetch"
    VERSION = HMMER_VERSION
    DISPLAY_NAME = "HMMER hmmfetch"
    CATEGORY = "annotation"
    DESCRIPTION = "Retrieve the profile HMMs named in a key file from an HMM database."
    SEARCH_ALIASES = ["BioNodulo builtin", "hmmer", "hmmfetch", "retrieve HMM", "Pfam subset"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("selected_hmm_models",)
    REQUIRED_EXECUTABLES = ["hmmfetch"]
    REQUIRED_PATH_INPUTS = ("hmmfile", "keyfile")
    DOCUMENTATION_URL = f"{HMMER_SOURCE_ROOT}/documentation/man/hmmfetch.man.in"
    SOURCE_URL = f"{HMMER_SOURCE_ROOT}/src/hmmfetch.c"
    SOURCE_PATHS = ("documentation/man/hmmfetch.man.in", "src/hmmfetch.c")
    UPSTREAM_SOURCE = "documentation/man/hmmfetch.man.in; src/hmmfetch.c::main"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "hmmfile": ("FILE", {"description": "Profile HMM database"}),
                "keyfile": ("FILE", {"description": "One model name or accession per line"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        return [
            "hmmfetch",
            "-f",
            "-o",
            f"{output_dir(inputs)}/selected.hmm",
            str(inputs["hmmfile"]),
            str(inputs["keyfile"]),
        ]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_root: str | Path) -> list[Path]:
        return [planned_output(output_root, cls.NODE_ID, "selected.hmm")]
