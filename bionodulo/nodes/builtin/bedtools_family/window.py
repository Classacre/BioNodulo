"""BEDTools window node pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsWindowNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_windowbed"
    DISPLAY_NAME = "BEDTools Window"
    DESCRIPTION = "Report B records within a symmetric or asymmetric window around A"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "window", "windowbed", "nearby intervals"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("window_matches",)
    OUTPUT_FILENAMES = ("window.out",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/window.html"
    UPSTREAM_SOURCE = "src/windowBed/windowBed.cpp"
    REQUIRED_PATH_INPUTS = ("inputA", "inputB")
    REPORTS = ("default", "u", "c", "v")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"inputA": ("FILE", {}), "inputB": ("BED", {})},
            "optional": {
                "addition_mode": ("STRING", {"default": "window", "options": ["window", "lr"]}),
                "window": ("INT", {"default": 1000, "min": 0}),
                "left": ("INT", {"default": 1000, "min": 0}),
                "right": ("INT", {"default": 1000, "min": 0}),
                "strand_window": ("BOOLEAN", {"default": False}),
                "strand": ("STRING", {"default": "", "options": ["", "same", "opposite"]}),
                "report": ("STRING", {"default": "default", "options": list(cls.REPORTS)}),
                "bed": ("BOOLEAN", {"default": False}),
                "header": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        stale = [key for key in ("original", "number", "nooverlaps", "w") if key in inputs]
        if stale:
            return f"Legacy window controls are stale ({', '.join(stale)}); use report and window"
        for key, choices, default in (
            ("addition_mode", ("window", "lr"), "window"),
            ("strand", ("", "same", "opposite"), ""),
            ("report", cls.REPORTS, "default"),
        ):
            validation = cls.validate_choice(inputs.get(key, default), choices, key)
            if validation is not True:
                return validation
        mode = str(inputs.get("addition_mode", "window"))
        size_keys = ("left", "right") if mode == "lr" else ("window",)
        for key in size_keys:
            validation = cls.validate_int(inputs.get(key, 1000), key, minimum=0)
            if validation is not True:
                return validation
        if mode == "lr":
            if inputs.get("window") not in (None, "", 1000):
                return "window is ignored in asymmetric lr mode"
        else:
            if inputs.get("left") not in (None, "", 1000) or inputs.get("right") not in (None, "", 1000):
                return "left and right are ignored in symmetric window mode"
            if inputs.get("strand_window"):
                return "strand_window only has an effect in asymmetric lr mode"
        is_bam = str(inputs.get("inputA", "")).lower().endswith(".bam")
        if inputs.get("bed") and not is_bam:
            return "bed conversion is only valid for BAM inputA"
        if is_bam and inputs.get("header"):
            return "header is ignored by BEDTools when inputA is BAM"
        if is_bam and inputs.get("report", "default") == "c" and not inputs.get("bed"):
            return "report=c requires bed=True when inputA is BAM"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        is_bam = str(inputs["inputA"]).lower().endswith(".bam")
        command = cls.checked_command(inputs, "bedtools", "window", "-abam" if is_bam else "-a", str(inputs["inputA"]), "-b", str(inputs["inputB"]))
        if is_bam and inputs.get("bed"):
            command.append("-bed")
        if inputs.get("addition_mode", "window") == "lr":
            command.extend(["-l", str(inputs.get("left", 1000)), "-r", str(inputs.get("right", 1000))])
            if inputs.get("strand_window"):
                command.append("-sw")
        else:
            command.extend(["-w", str(inputs.get("window", 1000))])
        strand = cls.strand_flag(inputs.get("strand"), same="-sm", opposite="-Sm")
        if strand:
            command.append(strand)
        report = str(inputs.get("report", "default"))
        if report != "default":
            command.append(f"-{report}")
        if inputs.get("header"):
            command.append("-header")
        return command
