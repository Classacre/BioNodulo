"""HMMER 3.4 ``hmmbuild`` contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import HMMER_SOURCE_ROOT, HMMER_VERSION, HMMERContractNode, add_value, output_dir, planned_output

_OPTIONAL_NUMBERS = {
    "ere",
    "eset",
    "maxinsertlen",
    "w_beta",
    "w_length",
}


class HMMERHmmbuildNode(HMMERContractNode):
    """Build profile HMMs from one or more multiple sequence alignments."""

    NODE_ID = "hmmer_hmmbuild"
    VERSION = HMMER_VERSION
    DISPLAY_NAME = "HMMER hmmbuild"
    CATEGORY = "annotation"
    DESCRIPTION = "Build profile HMMs from multiple sequence alignments."
    SEARCH_ALIASES = ["BioNodulo builtin", "hmmer", "hmmbuild", "profile HMM"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("hmm_profile",)
    REQUIRED_EXECUTABLES = ["hmmbuild"]
    REQUIRED_PATH_INPUTS = ("msafile",)
    DOCUMENTATION_URL = f"{HMMER_SOURCE_ROOT}/documentation/man/hmmbuild.man.in"
    SOURCE_URL = f"{HMMER_SOURCE_ROOT}/src/hmmbuild.c"
    SOURCE_PATHS = ("documentation/man/hmmbuild.man.in", "src/hmmbuild.c")
    UPSTREAM_SOURCE = "documentation/man/hmmbuild.man.in; src/hmmbuild.c::main"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "msafile": ("ALIGNMENT", {"description": "Multiple sequence alignment input"}),
            },
            "optional": {
                "hmmname": ("STRING", {"default": ""}),
                "input_format_select": (
                    "STRING",
                    {"default": "--amino", "options": ["--amino", "--dna", "--rna"]},
                ),
                "model_construction": (
                    "STRING",
                    {"default": "fast", "options": ["fast", "hand"]},
                ),
                "symfrac": (
                    "FLOAT",
                    {
                        "default": 0.5,
                        "min": 0,
                        "max": 1,
                        "displayOptions": {"show": {"model_construction": ["fast"]}},
                    },
                ),
                "fragthresh": ("FLOAT", {"default": 0.5, "min": 0, "max": 1}),
                "relative_weighting": (
                    "STRING",
                    {
                        "default": "--wpb",
                        "options": ["--wpb", "--wgsc", "--wblosum", "--wnone", "--wgiven"],
                    },
                ),
                "wid": (
                    "FLOAT",
                    {
                        "default": 0.62,
                        "min": 0,
                        "max": 1,
                        "displayOptions": {"show": {"relative_weighting": ["--wblosum"]}},
                    },
                ),
                "effective_weighting": (
                    "STRING",
                    {"default": "", "options": ["", "eent", "eclust", "enone", "eset"]},
                ),
                "eset": (
                    "FLOAT",
                    {
                        "default": "",
                        "min": 0,
                        "advanced": True,
                        "displayOptions": {"show": {"effective_weighting": ["eset"]}},
                    },
                ),
                "ere": (
                    "FLOAT",
                    {
                        "default": "",
                        "min": 0,
                        "advanced": True,
                        "displayOptions": {"show": {"effective_weighting": ["eent"]}},
                    },
                ),
                "esigma": (
                    "FLOAT",
                    {
                        "default": 45.0,
                        "min": 0,
                        "advanced": True,
                        "displayOptions": {"show": {"effective_weighting": ["eent"]}},
                    },
                ),
                "eid": (
                    "FLOAT",
                    {
                        "default": 0.62,
                        "min": 0,
                        "max": 1,
                        "advanced": True,
                        "displayOptions": {"show": {"effective_weighting": ["eclust"]}},
                    },
                ),
                "prior": (
                    "STRING",
                    {"default": "", "options": ["", "--pnone", "--plaplace"], "advanced": True},
                ),
                "single_sequence_scoring": (
                    "STRING",
                    {"default": "false", "options": ["false", "singlemx"], "advanced": True},
                ),
                "popen": (
                    "FLOAT",
                    {
                        "default": 0.02,
                        "min": 0,
                        "max": 0.5,
                        "advanced": True,
                        "displayOptions": {"show": {"single_sequence_scoring": ["singlemx"]}},
                    },
                ),
                "pextend": (
                    "FLOAT",
                    {
                        "default": 0.4,
                        "min": 0,
                        "max": 1,
                        "advanced": True,
                        "displayOptions": {"show": {"single_sequence_scoring": ["singlemx"]}},
                    },
                ),
                "eml": ("INT", {"default": 200, "min": 1, "advanced": True}),
                "emn": ("INT", {"default": 200, "min": 1, "advanced": True}),
                "evl": ("INT", {"default": 200, "min": 1, "advanced": True}),
                "evn": ("INT", {"default": 200, "min": 1, "advanced": True}),
                "efl": ("INT", {"default": 100, "min": 1, "advanced": True}),
                "efn": ("INT", {"default": 200, "min": 1, "advanced": True}),
                "eft": ("FLOAT", {"default": 0.04, "min": 0, "max": 1, "advanced": True}),
                "threads": (
                    "INT",
                    {"default": 1, "min": 1, "max": 128, "description": "Parallel CPU workers"},
                ),
                "seed": ("INT", {"default": 42, "min": 0}),
                "w_beta": ("FLOAT", {"default": "", "advanced": True}),
                "w_length": ("INT", {"default": "", "advanced": True}),
                "maxinsertlen": ("INT", {"default": "", "min": 5, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        normalized = dict(inputs)
        for name in _OPTIONAL_NUMBERS:
            if normalized.get(name) == "":
                normalized.pop(name)
        validation = super().VALIDATE_INPUTS(normalized)
        if validation is not True:
            return validation
        effective = str(inputs.get("effective_weighting", ""))
        if effective == "eset" and inputs.get("eset") in (None, ""):
            return "Input 'eset' is required when effective_weighting is eset"
        if effective != "eset" and inputs.get("eset") not in (None, ""):
            return "Input 'eset' is only valid when effective_weighting is eset"
        if inputs.get("ere") not in (None, "") and float(inputs["ere"]) <= 0:
            return "Input 'ere' must be greater than 0"
        if float(inputs.get("esigma", 45.0)) <= 0:
            return "Input 'esigma' must be greater than 0"
        if str(inputs.get("single_sequence_scoring", "false")) == "singlemx":
            if not 0 <= float(inputs.get("popen", 0.02)) < 0.5:
                return "Input 'popen' must be at least 0 and less than 0.5"
            if not 0 <= float(inputs.get("pextend", 0.4)) < 1:
                return "Input 'pextend' must be at least 0 and less than 1"
        if not 0 < float(inputs.get("eft", 0.04)) < 1:
            return "Input 'eft' must be greater than 0 and less than 1"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        command = ["hmmbuild"]
        add_value(command, "-n", inputs.get("hmmname"))
        command.append(str(inputs.get("input_format_select", "--amino")))
        construction = str(inputs.get("model_construction", "fast"))
        command.append(f"--{construction}")
        if construction == "fast":
            add_value(command, "--symfrac", inputs.get("symfrac", 0.5))
        add_value(command, "--fragthresh", inputs.get("fragthresh", 0.5))

        weighting = str(inputs.get("relative_weighting", "--wpb"))
        command.append(weighting)
        if weighting == "--wblosum":
            add_value(command, "--wid", inputs.get("wid", 0.62))

        effective = str(inputs.get("effective_weighting", ""))
        if effective == "eset":
            add_value(command, "--eset", inputs.get("eset"))
        elif effective:
            command.append(f"--{effective}")
            if effective == "eent":
                add_value(command, "--ere", inputs.get("ere"))
                add_value(command, "--esigma", inputs.get("esigma", 45.0))
            elif effective == "eclust":
                add_value(command, "--eid", inputs.get("eid", 0.62))

        prior = str(inputs.get("prior", ""))
        if prior:
            command.append(prior)
        if str(inputs.get("single_sequence_scoring", "false")) == "singlemx":
            command.append("--singlemx")
            add_value(command, "--popen", inputs.get("popen", 0.02))
            add_value(command, "--pextend", inputs.get("pextend", 0.4))

        for name, flag, default in (
            ("eml", "--EmL", 200),
            ("emn", "--EmN", 200),
            ("evl", "--EvL", 200),
            ("evn", "--EvN", 200),
            ("efl", "--EfL", 100),
            ("efn", "--EfN", 200),
            ("eft", "--Eft", 0.04),
        ):
            add_value(command, flag, inputs.get(name, default))
        add_value(command, "--cpu", inputs.get("threads", 1))
        add_value(command, "--seed", inputs.get("seed", 42))
        add_value(command, "--w_beta", inputs.get("w_beta"))
        add_value(command, "--w_length", inputs.get("w_length"))
        add_value(command, "--maxinsertlen", inputs.get("maxinsertlen"))
        command.extend([f"{output_dir(inputs)}/profile.hmm", str(inputs["msafile"])])
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_root: str | Path) -> list[Path]:
        return [planned_output(output_root, cls.NODE_ID, "profile.hmm")]
