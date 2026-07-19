"""HMMER 3.4 ``hmmemit`` contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import HMMER_SOURCE_ROOT, HMMER_VERSION, HMMERContractNode, add_value, output_dir, planned_output


class HMMERHmmemitNode(HMMERContractNode):
    """Emit sampled or consensus sequences from profile HMMs."""

    NODE_ID = "hmmer_hmmemit"
    VERSION = HMMER_VERSION
    DISPLAY_NAME = "HMMER hmmemit"
    CATEGORY = "annotation"
    DESCRIPTION = "Emit sampled sequences, alignments, or consensus sequences from profile HMMs."
    SEARCH_ALIASES = ["BioNodulo builtin", "hmmer", "hmmemit", "consensus sequence"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("emitted_sequences",)
    REQUIRED_EXECUTABLES = ["hmmemit"]
    REQUIRED_PATH_INPUTS = ("hmmfile",)
    DOCUMENTATION_URL = f"{HMMER_SOURCE_ROOT}/documentation/man/hmmemit.man.in"
    SOURCE_URL = f"{HMMER_SOURCE_ROOT}/src/hmmemit.c"
    SOURCE_PATHS = ("documentation/man/hmmemit.man.in", "src/hmmemit.c")
    UPSTREAM_SOURCE = "documentation/man/hmmemit.man.in; src/hmmemit.c::main"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "hmmfile": ("FILE", {"description": "Profile HMM file"}),
                "output_mode": (
                    "STRING",
                    {
                        "default": "fasta",
                        "options": ["fasta", "aln", "mrcs", "mrcsf", "sample"],
                        "description": "Core sample, alignment, simple/fancier consensus, or search-profile sample",
                    },
                ),
            },
            "optional": {
                "n_fasta": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "displayOptions": {"show": {"output_mode": ["fasta"]}},
                    },
                ),
                "n_alignment": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "displayOptions": {"show": {"output_mode": ["aln"]}},
                    },
                ),
                "n_sample": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "displayOptions": {"show": {"output_mode": ["sample"]}},
                    },
                ),
                "minl": (
                    "FLOAT",
                    {
                        "default": 0.0,
                        "min": 0,
                        "max": 1,
                        "displayOptions": {"show": {"output_mode": ["mrcsf"]}},
                    },
                ),
                "minu": (
                    "FLOAT",
                    {
                        "default": 0.0,
                        "min": 0,
                        "max": 1,
                        "displayOptions": {"show": {"output_mode": ["mrcsf"]}},
                    },
                ),
                "length": (
                    "INT",
                    {
                        "default": 400,
                        "min": 1,
                        "displayOptions": {"show": {"output_mode": ["sample"]}},
                    },
                ),
                "emission_profile": (
                    "STRING",
                    {
                        "default": "--local",
                        "options": ["--local", "--unilocal", "--glocal", "--uniglocal"],
                        "displayOptions": {"show": {"output_mode": ["sample"]}},
                    },
                ),
                "seed": ("INT", {"default": 0, "min": 0}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        return "emitted.sto" if inputs.get("output_mode", "fasta") == "aln" else "emitted.fasta"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        command = ["hmmemit", "-o", f"{output_dir(inputs)}/{cls._output_name(inputs)}"]
        output_mode = str(inputs.get("output_mode", "fasta"))
        if output_mode == "aln":
            add_value(command, "-N", inputs.get("n_alignment", 1))
            command.append("-a")
        elif output_mode == "mrcs":
            command.append("-c")
        elif output_mode == "mrcsf":
            add_value(command, "--minl", inputs.get("minl", 0.0))
            add_value(command, "--minu", inputs.get("minu", 0.0))
            command.append("-C")
        elif output_mode == "sample":
            add_value(command, "-N", inputs.get("n_sample", 1))
            command.append("-p")
            add_value(command, "-L", inputs.get("length", 400))
            command.append(str(inputs.get("emission_profile", "--local")))
        else:
            add_value(command, "-N", inputs.get("n_fasta", 1))
        add_value(command, "--seed", inputs.get("seed", 0))
        command.append(str(inputs["hmmfile"]))
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_root: str | Path) -> list[Path]:
        return [planned_output(output_root, cls.NODE_ID, cls._output_name(inputs))]
