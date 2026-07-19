"""MUMmer4 4.0.1 nucleotide alignment with ``nucmer``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import (
    Mummer4CommandNode,
    add_flag,
    path_list,
    path_value,
    validate_choice,
    validate_int,
    validate_number,
)


class Mummer4NucmerNode(Mummer4CommandNode):
    """Align one reference FASTA against one or more query FASTAs."""

    NODE_ID = "mummer4_nucmer"
    DISPLAY_NAME = "MUMmer4 Nucmer"
    DESCRIPTION = "Generate native delta or SAM nucleotide alignments with nucmer."
    SEARCH_ALIASES = ["BioNodulo builtin", "MUMmer4", "nucmer", "genome alignment", "delta"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("alignment",)
    REQUIRED_EXECUTABLES = ["nucmer"]
    REQUIRED_PATH_INPUTS = ("reference_sequence",)
    REQUIRED_PATH_LIST_INPUTS = ("query_sequence",)
    UPSTREAM_SOURCE = "src/umd/nucmer_cmdline.yaggo; src/umd/nucmer_main.cc"
    MATCH_MODES = ("mumreference", "mum", "maxmatch")
    OUTPUT_FORMATS = ("delta", "sam_short", "sam_long")
    STRANDS = ("both", "forward", "reverse")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reference_sequence": ("FASTA", {"description": "Reference multi-FASTA"}),
                "query_sequence": (
                    "FASTA_LIST",
                    {"multiple": True, "description": "One or more query multi-FASTA files"},
                ),
            },
            "optional": {
                "output_format": ("STRING", {"default": "delta", "options": list(cls.OUTPUT_FORMATS)}),
                "match_mode": ("STRING", {"default": "mumreference", "options": list(cls.MATCH_MODES)}),
                "breaklen": ("INT", {"default": 200, "min": 0}),
                "mincluster": ("INT", {"default": 65, "min": 0}),
                "diagdiff": ("INT", {"default": 5, "min": 0}),
                "diagfactor": ("FLOAT", {"default": 0.12, "min": 0}),
                "noextend": ("BOOLEAN", {"default": False}),
                "strand": ("STRING", {"default": "both", "options": list(cls.STRANDS)}),
                "maxgap": ("INT", {"default": 90, "min": 0}),
                "minmatch": ("INT", {"default": 20, "min": 1}),
                "minalign": ("INT", {"default": 0, "min": 0}),
                "nooptimize": ("BOOLEAN", {"default": False}),
                "nosimplify": ("BOOLEAN", {"default": False}),
                "threads": ("INT", {"default": 2, "min": 1, "max": 128}),
                "banded": ("BOOLEAN", {"default": False, "advanced": True}),
                "large": ("BOOLEAN", {"default": False, "advanced": True}),
                "genome": ("BOOLEAN", {"default": False, "advanced": True}),
                "max_chunk": ("INT", {"default": None, "min": 1, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def output_filename(cls, inputs: dict[str, Any]) -> str:
        return "alignment.delta" if inputs.get("output_format", "delta") == "delta" else "alignment.sam"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        return [node_dir / cls.output_filename(inputs)]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key, value, choices in (
            ("output_format", inputs.get("output_format", "delta"), cls.OUTPUT_FORMATS),
            ("match_mode", inputs.get("match_mode", "mumreference"), cls.MATCH_MODES),
            ("strand", inputs.get("strand", "both"), cls.STRANDS),
        ):
            validation = validate_choice(value, key, choices)
            if validation is not True:
                return validation
        for key, default, minimum in (
            ("breaklen", 200, 0),
            ("mincluster", 65, 0),
            ("diagdiff", 5, 0),
            ("maxgap", 90, 0),
            ("minmatch", 20, 1),
            ("minalign", 0, 0),
            ("threads", 2, 1),
        ):
            validation = validate_int(inputs.get(key, default), key, minimum=minimum)
            if validation is not True:
                return validation
        validation = validate_number(inputs.get("diagfactor", 0.12), "diagfactor", minimum=0)
        if validation is not True:
            return validation
        if inputs.get("max_chunk") is not None:
            return validate_int(inputs["max_chunk"], "max_chunk", minimum=1)
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = cls.checked_command(inputs, "nucmer")
        mode = str(inputs.get("match_mode", "mumreference"))
        if mode != "mumreference":
            command.append(f"--{mode}")
        output_format = str(inputs.get("output_format", "delta"))
        command.extend([f"--{output_format.replace('_', '-')}", str(output / cls.output_filename(inputs))])
        command.extend(
            [
                "--breaklen",
                str(inputs.get("breaklen", 200)),
                "--mincluster",
                str(inputs.get("mincluster", 65)),
                "--diagdiff",
                str(inputs.get("diagdiff", 5)),
                "--diagfactor",
                str(inputs.get("diagfactor", 0.12)),
            ]
        )
        add_flag(command, "--noextend", inputs.get("noextend"))
        strand = str(inputs.get("strand", "both"))
        if strand != "both":
            command.append(f"--{strand}")
        command.extend(
            [
                "--maxgap",
                str(inputs.get("maxgap", 90)),
                "--minmatch",
                str(inputs.get("minmatch", 20)),
                "--minalign",
                str(inputs.get("minalign", 0)),
            ]
        )
        add_flag(command, "--nooptimize", inputs.get("nooptimize"))
        add_flag(command, "--nosimplify", inputs.get("nosimplify"))
        command.extend(["--threads", str(inputs.get("threads", 2))])
        add_flag(command, "--banded", inputs.get("banded"))
        add_flag(command, "--large", inputs.get("large"))
        add_flag(command, "--genome", inputs.get("genome"))
        if inputs.get("max_chunk") is not None:
            command.extend(["--max-chunk", str(inputs["max_chunk"])])
        command.append(path_value(inputs.get("reference_sequence")))
        command.extend(path_list(inputs.get("query_sequence")))
        return command
