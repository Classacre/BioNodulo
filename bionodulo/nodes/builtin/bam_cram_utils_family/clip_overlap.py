"""BamUtil 1.0.15 clipOverlap node."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import BamUtilCommandNode, GALAXY_ALIAS, output_dir, path_value


class BamUtilClipOverlapNode(BamUtilCommandNode):
    NODE_ID = "bamutil_clip_overlap"
    DISPLAY_NAME = "BamUtil clipOverlap"
    CATEGORY = "alignment"
    DESCRIPTION = "Clip overlapping paired-end reads in coordinate- or read-name-sorted alignments"
    SEARCH_ALIASES = [GALAXY_ALIAS, "bamutil", "clipOverlap", "clip overlapping read pairs"]
    RETURN_TYPES = ("BAM", "STATS_FILE")
    RETURN_NAMES = ("clipped_alignment", "overlap_stats")
    DOCUMENTATION_URL = (
        "https://genome.sph.umich.edu/wiki/BamUtil:_clipOverlap"
    )
    SOURCE_URL = (
        "https://github.com/statgen/bamUtil/blob/"
        f"{BamUtilCommandNode.GIT_COMMIT}/src/ClipOverlap.cpp"
    )
    UPSTREAM_SOURCE = "src/ClipOverlap.cpp"
    STDERR_OUTPUT_INDEX = 1

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input": ("BAM", {"description": "Coordinate- or read-name-sorted SAM/BAM"})},
            "optional": {
                "storeOrig": ("STRING", {"default": ""}),
                "stats": ("BOOLEAN", {"default": False}),
                "readName": ("BOOLEAN", {"default": False}),
                "noRNValidate": ("BOOLEAN", {"default": False}),
                "overlapsOnly": ("BOOLEAN", {"default": False}),
                "excludeFlags": ("INT", {"default": 3852, "min": 0}),
                "unmapped": ("BOOLEAN", {"default": False}),
                "poolSize": ("INT", {"default": 1000000, "min": 0}),
                "poolSkipOverlap": ("BOOLEAN", {"default": False}),
                "noeof": ("BOOLEAN", {"default": False}),
                "params": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir_: str | Path) -> list[Path]:
        node_out = Path(output_dir_) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "clipped.bam", node_out / "overlap_stats.txt"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if path_value(inputs.get("input")) is None:
            return "input must be a non-empty path-like value"
        tag = str(inputs.get("storeOrig", "") or "")
        if tag and len(tag) != 2:
            return "storeOrig must be exactly two characters"
        flags = inputs.get("excludeFlags")
        if flags not in (None, "") and (isinstance(flags, bool) or not isinstance(flags, int) or flags < 0):
            return "excludeFlags must be a non-negative integer"
        pool_size = inputs.get("poolSize", 1000000)
        if isinstance(pool_size, bool) or not isinstance(pool_size, int) or pool_size < 0:
            return "poolSize must be a non-negative integer"
        if inputs.get("noRNValidate") and not inputs.get("readName"):
            return "noRNValidate requires readName mode"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = output_dir(inputs)
        command = ["bam", "clipOverlap", "--in", str(inputs.get("input", ""))]
        cls.add_value(command, "--storeOrig", inputs.get("storeOrig"))
        for key, flag in (
            ("readName", "--readName"),
            ("noRNValidate", "--noRNValidate"),
            ("stats", "--stats"),
            ("overlapsOnly", "--overlapsOnly"),
        ):
            if inputs.get(key):
                command.append(flag)
        cls.add_value(command, "--excludeFlags", inputs.get("excludeFlags"))
        if inputs.get("unmapped"):
            command.append("--unmapped")
        cls.add_value(command, "--poolSize", inputs.get("poolSize"))
        if inputs.get("poolSkipOverlap"):
            command.append("--poolSkipOverlap")
        if inputs.get("noeof"):
            command.append("--noeof")
        if inputs.get("params"):
            command.append("--params")
        return [*command, "--noPhoneHome", "--out", str(out / "clipped.bam")]


__all__ = ["BamUtilClipOverlapNode"]
