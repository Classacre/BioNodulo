"""HMMER 3.4 ``jackhmmer`` contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import (
    HMMER_PROTEIN_MATRICES,
    HMMER_SOURCE_ROOT,
    HMMER_VERSION,
    HMMERContractNode,
    add_boolean_flags,
    add_heuristic_flags,
    add_output_flags,
    add_threshold_flags,
    add_value,
    common_heuristic_inputs,
    common_output_inputs,
    common_threshold_inputs,
    plan_outputs,
    validate_search_options,
)

_OUTPUT_FILENAMES = ("output.txt", "results.tblout", "domains.domtblout")


class HMMERJackhmmerNode(HMMERContractNode):
    """Iteratively search protein queries against a protein sequence database."""

    NODE_ID = "hmmer_jackhmmer"
    VERSION = HMMER_VERSION
    DISPLAY_NAME = "HMMER jackhmmer"
    CATEGORY = "annotation"
    DESCRIPTION = "Iteratively search protein sequences against a protein sequence database."
    SEARCH_ALIASES = ["BioNodulo builtin", "hmmer", "jackhmmer", "iterative protein search"]
    RETURN_TYPES = ("STATS_FILE", "TSV", "TSV")
    RETURN_NAMES = ("output", "tblout", "domtblout")
    REQUIRED_EXECUTABLES = ["jackhmmer"]
    REQUIRED_PATH_INPUTS = ("seqfile", "seqdb")
    DOCUMENTATION_URL = f"{HMMER_SOURCE_ROOT}/documentation/man/jackhmmer.man.in"
    SOURCE_URL = f"{HMMER_SOURCE_ROOT}/src/jackhmmer.c"
    SOURCE_PATHS = ("documentation/man/jackhmmer.man.in", "src/jackhmmer.c")
    UPSTREAM_SOURCE = "documentation/man/jackhmmer.man.in; src/jackhmmer.c::main"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        optional: dict[str, Any] = {
            "iterations": ("INT", {"default": 5, "min": 1, "description": "Maximum iterations (-N)"}),
            **common_output_inputs(),
            "popen": ("FLOAT", {"default": 0.02, "min": 0, "description": "Gap-open probability"}),
            "pextend": ("FLOAT", {"default": 0.4, "min": 0, "description": "Gap-extension probability"}),
            "matrix": (
                "STRING",
                {"default": "BLOSUM62", "options": list(HMMER_PROTEIN_MATRICES)},
            ),
            "matrix_file": (
                "FILE",
                {"default": "", "description": "Square substitution matrix; overrides matrix", "advanced": True},
            ),
            **common_threshold_inputs(include_default=0.001, domains=True, model_cutoffs=False),
            **common_heuristic_inputs((0.02, 0.001, 1e-5)),
            "fragthresh": ("FLOAT", {"default": 0.5, "min": 0, "max": 1}),
            "relative_weighting": (
                "STRING",
                {"default": "--wpb", "options": ["--wpb", "--wgsc", "--wblosum", "--wnone"]},
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
                {"default": "eent", "options": ["eent", "eclust", "enone", "eset"]},
            ),
            "eset": (
                "FLOAT",
                {"default": "", "min": 0, "displayOptions": {"show": {"effective_weighting": ["eset"]}}},
            ),
            "ere": (
                "FLOAT",
                {"default": 0.59, "min": 0, "displayOptions": {"show": {"effective_weighting": ["eent"]}}},
            ),
            "esigma": (
                "FLOAT",
                {"default": 45.0, "min": 0, "displayOptions": {"show": {"effective_weighting": ["eent"]}}},
            ),
            "eid": (
                "FLOAT",
                {
                    "default": 0.62,
                    "min": 0,
                    "max": 1,
                    "displayOptions": {"show": {"effective_weighting": ["eclust"]}},
                },
            ),
            "prior": ("STRING", {"default": "", "options": ["", "--pnone", "--plaplace"]}),
            "eml": ("INT", {"default": 200, "min": 1, "advanced": True}),
            "emn": ("INT", {"default": 200, "min": 1, "advanced": True}),
            "evl": ("INT", {"default": 200, "min": 1, "advanced": True}),
            "evn": ("INT", {"default": 200, "min": 1, "advanced": True}),
            "efl": ("INT", {"default": 100, "min": 1, "advanced": True}),
            "efn": ("INT", {"default": 200, "min": 1, "advanced": True}),
            "eft": ("FLOAT", {"default": 0.04, "min": 0, "max": 1, "advanced": True}),
            "nonull2": ("BOOLEAN", {"default": False, "advanced": True}),
            "z": ("FLOAT", {"default": "", "min": 0, "advanced": True}),
            "domz": ("FLOAT", {"default": "", "min": 0, "advanced": True}),
            "threads": ("INT", {"default": 2, "min": 0, "max": 128, "description": "Parallel CPU workers"}),
            "seed": ("INT", {"default": 42, "min": 0}),
        }
        return {
            "required": {
                "seqfile": ("FASTA", {"description": "Protein query sequence FASTA"}),
                "seqdb": ("FASTA", {"description": "Rewindable, uncompressed protein target FASTA"}),
            },
            "optional": optional,
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_search_options(inputs, domains=True, model_cutoffs=False)
        if validation is not True:
            return validation
        if str(inputs.get("seqdb", "")) == "-":
            return "jackhmmer cannot read seqdb from stdin"
        if str(inputs.get("seqdb", "")).lower().endswith((".gz", ".gzip")):
            return "jackhmmer requires a rewindable, uncompressed seqdb"
        if not 0 <= float(inputs.get("popen", 0.02)) < 0.5:
            return "Input 'popen' must be at least 0 and less than 0.5"
        if not 0 <= float(inputs.get("pextend", 0.4)) < 1:
            return "Input 'pextend' must be at least 0 and less than 1"
        effective = str(inputs.get("effective_weighting", "eent"))
        if effective == "eset" and inputs.get("eset") in (None, ""):
            return "Input 'eset' is required when effective_weighting is eset"
        if effective != "eset" and inputs.get("eset") not in (None, ""):
            return "Input 'eset' is only valid when effective_weighting is eset"
        if effective == "eset" and float(inputs["eset"]) <= 0:
            return "Input 'eset' must be greater than 0"
        if effective == "eent" and float(inputs.get("ere", 0.59)) <= 0:
            return "Input 'ere' must be greater than 0"
        if effective == "eent" and float(inputs.get("esigma", 45.0)) <= 0:
            return "Input 'esigma' must be greater than 0"
        if not 0 < float(inputs.get("eft", 0.04)) < 1:
            return "Input 'eft' must be greater than 0 and less than 1"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        command = ["jackhmmer", "-N", str(inputs.get("iterations", 5))]
        add_output_flags(
            command,
            inputs,
            (("-o", "output.txt"), ("--tblout", "results.tblout"), ("--domtblout", "domains.domtblout")),
        )
        add_boolean_flags(command, inputs, (("acc", "--acc"), ("noali", "--noali"), ("notextw", "--notextw")))
        add_value(command, "--popen", inputs.get("popen", 0.02))
        add_value(command, "--pextend", inputs.get("pextend", 0.4))
        if inputs.get("matrix_file"):
            add_value(command, "--mxfile", inputs["matrix_file"])
        else:
            add_value(command, "--mx", inputs.get("matrix", "BLOSUM62"))
        add_threshold_flags(command, inputs, include_default=0.001, domains=True, allow_model_cutoffs=False)
        add_heuristic_flags(command, inputs, defaults=(0.02, 0.001, 1e-5))
        add_value(command, "--fragthresh", inputs.get("fragthresh", 0.5))

        weighting = str(inputs.get("relative_weighting", "--wpb"))
        command.append(weighting)
        if weighting == "--wblosum":
            add_value(command, "--wid", inputs.get("wid", 0.62))

        effective = str(inputs.get("effective_weighting", "eent"))
        if effective == "eset":
            add_value(command, "--eset", inputs["eset"])
        else:
            command.append(f"--{effective}")
            if effective == "eent":
                add_value(command, "--ere", inputs.get("ere", 0.59))
                add_value(command, "--esigma", inputs.get("esigma", 45.0))
            elif effective == "eclust":
                add_value(command, "--eid", inputs.get("eid", 0.62))

        if inputs.get("prior"):
            command.append(str(inputs["prior"]))
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
        add_boolean_flags(command, inputs, (("nonull2", "--nonull2"),))
        add_value(command, "-Z", inputs.get("z"))
        add_value(command, "--domZ", inputs.get("domz"))
        add_value(command, "--cpu", inputs.get("threads", 2))
        add_value(command, "--seed", inputs.get("seed", 42))
        command.extend([str(inputs["seqfile"]), str(inputs["seqdb"])])
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_root: str | Path) -> list[Path]:
        return plan_outputs(output_root, cls.NODE_ID, _OUTPUT_FILENAMES)
