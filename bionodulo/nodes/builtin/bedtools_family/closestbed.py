"""Compatibility BEDTools closest ID pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsClosestBedNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_closestbed"
    COMPATIBILITY_ALIAS_OF = "bedtools_closest"
    DISPLAY_NAME = "BEDTools ClosestBed"
    DESCRIPTION = "Find closest records in sorted B files for every sorted A record"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "closest", "closestbed", "nearest interval"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("closest",)
    OUTPUT_FILENAMES = ("closest.bed",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/closest.html"
    UPSTREAM_SOURCE = "src/utils/Contexts/ContextClosest.cpp"
    REQUIRED_PATH_INPUTS = ("inputA",)
    REQUIRED_PATH_LIST_INPUTS = ("inputB",)
    TIES = ("all", "first", "last")
    DISTANCE_MODES = ("", "ref", "a", "b")
    MDB_MODES = ("each", "all")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"inputA": ("BED", {}), "inputB": ("BED_LIST", {})},
            "optional": {
                "ties": ("STRING", {"default": "all", "options": list(cls.TIES)}),
                "strand": ("STRING", {"default": "", "options": ["", "same", "opposite"]}),
                "distance": ("BOOLEAN", {"default": False}),
                "distance_mode": ("STRING", {"default": "", "options": list(cls.DISTANCE_MODES)}),
                "ignore_upstream": ("BOOLEAN", {"default": False}),
                "ignore_downstream": ("BOOLEAN", {"default": False}),
                "first_upstream": ("BOOLEAN", {"default": False}),
                "first_downstream": ("BOOLEAN", {"default": False}),
                "ignore_overlaps": ("BOOLEAN", {"default": False}),
                "mdb": ("STRING", {"default": "each", "options": list(cls.MDB_MODES)}),
                "k": ("INT", {"default": "", "min": 1}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key, choices, default in (
            ("ties", cls.TIES, "all"),
            ("strand", ("", "same", "opposite"), ""),
            ("distance_mode", cls.DISTANCE_MODES, ""),
            ("mdb", cls.MDB_MODES, "each"),
        ):
            validation = cls.validate_choice(inputs.get(key, default), choices, key)
            if validation is not True:
                return validation
        mode = str(inputs.get("distance_mode", ""))
        directional = any(inputs.get(key) for key in ("ignore_upstream", "ignore_downstream", "first_upstream", "first_downstream"))
        if inputs.get("distance") and mode:
            return "distance and signed distance_mode are mutually exclusive"
        if directional and not mode:
            return "directional closest controls require signed distance_mode"
        if inputs.get("ignore_upstream") and inputs.get("ignore_downstream"):
            return "ignore_upstream and ignore_downstream are mutually exclusive"
        if inputs.get("first_upstream") and inputs.get("first_downstream"):
            return "first_upstream and first_downstream are mutually exclusive"
        if inputs.get("ignore_upstream") and inputs.get("first_upstream"):
            return "cannot select and ignore upstream records together"
        if inputs.get("ignore_downstream") and inputs.get("first_downstream"):
            return "cannot select and ignore downstream records together"
        return cls.validate_int(inputs.get("k"), "k", minimum=1)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "bedtools", "closest")
        strand = cls.strand_flag(inputs.get("strand"))
        if strand:
            command.append(strand)
        if inputs.get("distance"):
            command.append("-d")
        elif inputs.get("distance_mode"):
            command.extend(["-D", str(inputs["distance_mode"])])
            for key, flag in (("ignore_upstream", "-iu"), ("ignore_downstream", "-id"), ("first_upstream", "-fu"), ("first_downstream", "-fd")):
                if inputs.get(key):
                    command.append(flag)
        if inputs.get("ignore_overlaps"):
            command.append("-io")
        command.extend(["-mdb", str(inputs.get("mdb", "each")), "-t", str(inputs.get("ties", "all"))])
        cls.optional_value(command, "-k", inputs.get("k"))
        command.extend(["-a", str(inputs["inputA"]), "-b", *cls.path_list(inputs["inputB"])])
        return command
