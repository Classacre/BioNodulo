"""BamUtil 1.0.15 diff node."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import BamUtilCommandNode, GALAXY_ALIAS, output_dir, path_value


def output_extension(inputs: dict[str, Any]) -> str:
    return Path(str(inputs.get("output_as", "diff.txt"))).suffix.lstrip(".") or "txt"


def path_stem(value: Any, fallback: str) -> str:
    stem = Path(str(value or "")).stem
    return stem or fallback


class BamUtilDiffNode(BamUtilCommandNode):
    NODE_ID = "bamutil_diff"
    DISPLAY_NAME = "BamUtil diff"
    CATEGORY = "alignment"
    DESCRIPTION = "Compare two coordinate-sorted SAM/BAM files and report differing records"
    SEARCH_ALIASES = [GALAXY_ALIAS, "bamutil", "diff", "compare SAM BAM files"]
    RETURN_TYPES = ("FILE", "FILE", "FILE")
    RETURN_NAMES = ("diff", "only_in_first", "only_in_second")
    DOCUMENTATION_URL = (
        "https://genome.sph.umich.edu/wiki/BamUtil:_diff"
    )
    SOURCE_URL = (
        "https://github.com/statgen/bamUtil/blob/"
        f"{BamUtilCommandNode.GIT_COMMIT}/src/Diff.cpp"
    )
    UPSTREAM_SOURCE = "src/Diff.cpp"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"in1": ("BAM", {}), "in2": ("BAM", {})},
            "optional": {
                "posDiff": ("INT", {"default": 100000, "min": 0}),
                "onlyDiffs": ("BOOLEAN", {"default": False}),
                "fields_choice": ("STRING", {"default": "default", "options": ["default", "all", "select"]}),
                "flag": ("BOOLEAN", {"default": False}),
                "mapQual": ("BOOLEAN", {"default": False}),
                "mate": ("BOOLEAN", {"default": False}),
                "isize": ("BOOLEAN", {"default": False}),
                "seq": ("BOOLEAN", {"default": False}),
                "baseQual": ("BOOLEAN", {"default": False}),
                "noCigar": ("BOOLEAN", {"default": False}),
                "noPos": ("BOOLEAN", {"default": False}),
                "tagchoice": ("STRING", {"default": "none", "options": ["none", "everyTag", "specify"]}),
                "tags": ("STRING", {"default": ""}),
                "recPoolSize": ("INT", {"default": 1000000}),
                "noeof": ("BOOLEAN", {"default": False}),
                "params": ("BOOLEAN", {"default": False}),
                "output_as": ("STRING", {"default": "diff.txt", "options": ["diff.txt", "diff.bam", "diff.sam"]}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir_: str | Path) -> list[Path]:
        node_out = Path(output_dir_) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        output_as = str(inputs.get("output_as", "diff.txt"))
        first = node_out / output_as
        ext = output_extension(inputs)
        if ext == "txt":
            return [first]
        stem = Path(output_as).stem or "diff"
        return [
            first,
            node_out / f"{stem}_only1_{path_stem(inputs.get('in1'), 'in1')}.{ext}",
            node_out / f"{stem}_only2_{path_stem(inputs.get('in2'), 'in2')}.{ext}",
        ]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in ("in1", "in2"):
            if path_value(inputs.get(key)) is None:
                return f"{key} must be a non-empty path-like value"
        if str(inputs.get("fields_choice", "default")) not in {"default", "all", "select"}:
            return "fields_choice must be one of: default, all, select"
        if str(inputs.get("tagchoice", "none")) not in {"none", "everyTag", "specify"}:
            return "tagchoice must be one of: none, everyTag, specify"
        if str(inputs.get("tagchoice", "none")) == "specify" and not str(inputs.get("tags", "")).strip():
            return "tags is required when tagchoice is specify"
        position = inputs.get("posDiff", 100000)
        if isinstance(position, bool) or not isinstance(position, int) or position < 0:
            return "posDiff must be a non-negative integer"
        pool_size = inputs.get("recPoolSize", 1000000)
        if isinstance(pool_size, bool) or not isinstance(pool_size, int) or pool_size == 0 or pool_size < -1:
            return "recPoolSize must be -1 or a positive integer"
        if str(inputs.get("output_as", "diff.txt")) not in {"diff.txt", "diff.bam", "diff.sam"}:
            return "output_as must be one of: diff.txt, diff.bam, diff.sam"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ["bam", "diff", "--in1", str(inputs.get("in1", "")), "--in2", str(inputs.get("in2", ""))]
        fields_choice = str(inputs.get("fields_choice", "default"))
        if fields_choice == "all":
            command.append("--all")
        elif fields_choice == "select":
            for key, flag in (
                ("flag", "--flag"),
                ("mapQual", "--mapQual"),
                ("mate", "--mate"),
                ("isize", "--isize"),
                ("seq", "--seq"),
                ("baseQual", "--baseQual"),
                ("noCigar", "--noCigar"),
                ("noPos", "--noPos"),
            ):
                if inputs.get(key):
                    command.append(flag)
            tagchoice = str(inputs.get("tagchoice", "none"))
            if tagchoice == "everyTag":
                # BamUtil 1.0.15 documents --everyTag but registers --everyTags.
                command.append("--everyTags")
            elif tagchoice == "specify":
                cls.add_value(command, "--tags", inputs.get("tags"))
        if inputs.get("onlyDiffs"):
            command.append("--onlyDiffs")
        command.extend(
            [
                "--recPoolSize",
                str(inputs.get("recPoolSize", 1000000)),
                "--posDiff",
                str(inputs.get("posDiff", 100000)),
            ]
        )
        if inputs.get("noeof"):
            command.append("--noeof")
        if inputs.get("params"):
            command.append("--params")
        return [*command, "--noPhoneHome", "--out", str(output_dir(inputs) / str(inputs.get("output_as", "diff.txt")))]


__all__ = ["BamUtilDiffNode"]
