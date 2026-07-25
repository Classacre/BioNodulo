"""HMMER 3.4 ``hmmsearch`` contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import (
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


class HMMERHmmsearchNode(HMMERContractNode):
    """Search protein sequences with one or more profile HMMs."""

    NODE_ID = "hmmer_hmmsearch"
    VERSION = HMMER_VERSION
    DISPLAY_NAME = "HMMER hmmsearch"
    CATEGORY = "annotation"
    DESCRIPTION = "Search a protein sequence database with one or more profile HMMs."
    SEARCH_ALIASES = ["BioNodulo builtin", "hmmer", "hmmsearch", "profile HMM search"]
    RETURN_TYPES = ("STATS_FILE", "TSV", "TSV", "TSV")
    RETURN_NAMES = ("output", "tblout", "domtblout", "pfamtblout")
    REQUIRED_EXECUTABLES = ["hmmsearch"]
    REQUIRED_PATH_INPUTS = ("hmmfile", "seqdb")
    DOCUMENTATION_URL = f"{HMMER_SOURCE_ROOT}/documentation/man/hmmsearch.man.in"
    SOURCE_URL = f"{HMMER_SOURCE_ROOT}/src/hmmsearch.c"
    SOURCE_PATHS = ("documentation/man/hmmsearch.man.in", "src/hmmsearch.c")
    UPSTREAM_SOURCE = "documentation/man/hmmsearch.man.in; src/hmmsearch.c::main"
    AUDIT_CAVEATS = (
        "The 3.4 hmmsearch manpage omits --pfamtblout, but the pinned src/hmmsearch.c "
        "option table and output implementation support it; the contract follows the executable source.",
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        optional: dict[str, Any] = {
            **common_output_inputs(),
            **common_threshold_inputs(include_default=0.01, domains=True, model_cutoffs=True),
            **common_heuristic_inputs((0.02, 0.001, 1e-5)),
            "nonull2": ("BOOLEAN", {"default": False, "advanced": True}),
            "z": ("FLOAT", {"default": "", "min": 0, "advanced": True}),
            "domz": ("FLOAT", {"default": "", "min": 0, "advanced": True}),
            "threads": ("INT", {"default": 2, "min": 0, "max": 128, "description": "Parallel CPU workers"}),
            "seed": ("INT", {"default": 42, "min": 0}),
        }
        return {
            "required": {
                "hmmfile": ("FILE", {"description": "One or more protein profile HMMs"}),
                "seqdb": ("FASTA", {"description": "Target protein sequence database"}),
            },
            "optional": optional,
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if str(inputs.get("hmmfile", "")) == "-" and str(inputs.get("seqdb", "")) == "-":
            return "hmmsearch cannot read both hmmfile and seqdb from stdin"
        return validate_search_options(inputs, domains=True, model_cutoffs=True)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        command = ["hmmsearch"]
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
        add_threshold_flags(command, inputs, include_default=0.01, domains=True, allow_model_cutoffs=True)
        add_heuristic_flags(command, inputs, defaults=(0.02, 0.001, 1e-5))
        add_boolean_flags(command, inputs, (("nonull2", "--nonull2"),))
        add_value(command, "-Z", inputs.get("z"))
        add_value(command, "--domZ", inputs.get("domz"))
        add_value(command, "--cpu", inputs.get("threads", 2))
        add_value(command, "--seed", inputs.get("seed", 42))
        command.extend([str(inputs["hmmfile"]), str(inputs["seqdb"])])
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_root: str | Path) -> list[Path]:
        return plan_outputs(output_root, cls.NODE_ID, _OUTPUT_FILENAMES)
