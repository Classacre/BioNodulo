"""BEDTools shuffle node pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsShuffleNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_shufflebed"
    DISPLAY_NAME = "BEDTools Shuffle"
    DESCRIPTION = "Randomly redistribute intervals across a genome"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "shuffle", "shufflebed", "permutation"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("shuffled",)
    OUTPUT_FILENAMES = ("shuffled.bed",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/shuffle.html"
    UPSTREAM_SOURCE = "src/shuffleBed/shuffleBed.cpp"
    REQUIRED_PATH_INPUTS = ("inputA", "genome")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"inputA": ("BED", {}), "genome": ("TSV", {})},
            "optional": {
                "bedpe": ("BOOLEAN", {"default": False}),
                "seed": ("INT", {"default": ""}),
                "exclude": ("BED", {"default": ""}),
                "include": ("BED", {"default": ""}),
                "overlap": ("FLOAT", {"default": "", "min": 0, "max": 1}),
                "chrom": ("BOOLEAN", {"default": False}),
                "chromfirst": ("BOOLEAN", {"default": False}),
                "no_overlap": ("BOOLEAN", {"default": False}),
                "allow_beyond": ("BOOLEAN", {"default": False}),
                "maxtries": ("INT", {"default": 1000, "min": 1}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in ("exclude", "include"):
            if inputs.get(key) not in (None, ""):
                validation = cls.require_path(inputs, key)
                if validation is not True:
                    return validation
        validation = cls.validate_fraction(inputs.get("overlap"), "overlap", allow_zero=True)
        if validation is not True:
            return validation
        if inputs.get("overlap") not in (None, "") and not inputs.get("exclude"):
            return "overlap is only valid with an exclusion file"
        if inputs.get("include") and (inputs.get("chrom") or inputs.get("chromfirst")):
            return "include regions are incompatible with chrom/chromfirst placement"
        validation = cls.validate_int(inputs.get("maxtries", 1000), "maxtries", minimum=1)
        if validation is not True:
            return validation
        return cls.validate_int(inputs.get("seed"), "seed")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "bedtools", "shuffle", "-i", str(inputs["inputA"]), "-g", str(inputs["genome"]))
        if inputs.get("bedpe"):
            command.append("-bedpe")
        cls.optional_value(command, "-seed", inputs.get("seed"))
        if inputs.get("exclude"):
            command.extend(["-excl", str(inputs["exclude"])])
            cls.optional_value(command, "-f", inputs.get("overlap"))
        if inputs.get("include"):
            command.extend(["-incl", str(inputs["include"])])
        for key, flag in (
            ("chrom", "-chrom"), ("chromfirst", "-chromFirst"),
            ("no_overlap", "-noOverlapping"), ("allow_beyond", "-allowBeyondChromEnd"),
        ):
            if inputs.get(key):
                command.append(flag)
        command.extend(["-maxTries", str(inputs.get("maxtries", 1000))])
        return command
