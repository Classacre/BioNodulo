"""HMMER 3.4 ``phmmer`` contract."""

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

_OUTPUT_FILENAMES = ("output.txt", "results.tblout", "domains.domtblout", "pfam.tblout")


class HMMERPhmmerNode(HMMERContractNode):
    """Search protein queries against a protein sequence database."""

    NODE_ID = "hmmer_phmmer"
    VERSION = HMMER_VERSION
    DISPLAY_NAME = "HMMER phmmer"
    CATEGORY = "annotation"
    DESCRIPTION = "Search protein sequences against a protein sequence database."
    SEARCH_ALIASES = ["BioNodulo builtin", "hmmer", "phmmer", "protein homology search"]
    RETURN_TYPES = ("STATS_FILE", "TSV", "TSV", "TSV")
    RETURN_NAMES = ("output", "tblout", "domtblout", "pfamtblout")
    REQUIRED_EXECUTABLES = ["phmmer"]
    REQUIRED_PATH_INPUTS = ("seqfile", "seqdb")
    DOCUMENTATION_URL = f"{HMMER_SOURCE_ROOT}/documentation/man/phmmer.man.in"
    SOURCE_URL = f"{HMMER_SOURCE_ROOT}/src/phmmer.c"
    SOURCE_PATHS = ("documentation/man/phmmer.man.in", "src/phmmer.c")
    UPSTREAM_SOURCE = "documentation/man/phmmer.man.in; src/phmmer.c::main"
    AUDIT_CAVEATS = (
        "The 3.4 phmmer manpage omits --pfamtblout, but the pinned src/phmmer.c "
        "option table and output implementation support it; the contract follows the executable source.",
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        optional: dict[str, Any] = {
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
            **common_threshold_inputs(include_default=0.01, domains=True, model_cutoffs=False),
            **common_heuristic_inputs((0.02, 0.001, 1e-5)),
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
                "seqdb": ("FASTA", {"description": "Protein target sequence FASTA"}),
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
        if str(inputs.get("seqfile", "")) == "-" and str(inputs.get("seqdb", "")) == "-":
            return "phmmer cannot read both seqfile and seqdb from stdin"
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
        command = ["phmmer"]
        add_output_flags(
            command,
            inputs,
            (
                ("-o", "output.txt"),
                ("--tblout", "results.tblout"),
                ("--domtblout", "domains.domtblout"),
                ("--pfamtblout", "pfam.tblout"),
            ),
        )
        add_boolean_flags(command, inputs, (("acc", "--acc"), ("noali", "--noali"), ("notextw", "--notextw")))
        add_value(command, "--popen", inputs.get("popen", 0.02))
        add_value(command, "--pextend", inputs.get("pextend", 0.4))
        if inputs.get("matrix_file"):
            add_value(command, "--mxfile", inputs["matrix_file"])
        else:
            add_value(command, "--mx", inputs.get("matrix", "BLOSUM62"))
        add_threshold_flags(command, inputs, include_default=0.01, domains=True, allow_model_cutoffs=False)
        add_heuristic_flags(command, inputs, defaults=(0.02, 0.001, 1e-5))
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
