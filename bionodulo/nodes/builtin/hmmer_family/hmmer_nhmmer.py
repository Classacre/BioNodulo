"""HMMER 3.4 ``nhmmer`` contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import (
    HMMER_NUCLEOTIDE_CITATION_DOI,
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

_OUTPUT_FILENAMES = ("output.txt", "results.tblout", "dfam.tblout", "alignment_scores.txt")


class HMMERNhmmerNode(HMMERContractNode):
    """Search a nucleotide model, alignment, or sequence against nucleotide targets."""

    NODE_ID = "hmmer_nhmmer"
    VERSION = HMMER_VERSION
    DISPLAY_NAME = "HMMER nhmmer"
    CATEGORY = "annotation"
    DESCRIPTION = "Search a DNA model, alignment, or sequence against a nucleotide sequence database."
    SEARCH_ALIASES = ["BioNodulo builtin", "hmmer", "nhmmer", "nucleotide homology search"]
    RETURN_TYPES = ("STATS_FILE", "TSV", "TEXT", "TEXT")
    RETURN_NAMES = ("output", "tblout", "dfamtblout", "aliscoresout")
    REQUIRED_EXECUTABLES = ["nhmmer"]
    REQUIRED_PATH_INPUTS = ("hmmfile", "seqfile")
    DOCUMENTATION_URL = f"{HMMER_SOURCE_ROOT}/documentation/man/nhmmer.man.in"
    SOURCE_URL = f"{HMMER_SOURCE_ROOT}/src/nhmmer.c"
    SOURCE_PATHS = ("documentation/man/nhmmer.man.in", "src/nhmmer.c")
    UPSTREAM_SOURCE = "documentation/man/nhmmer.man.in; src/nhmmer.c::main"
    CITATION_DOIS = [HMMER_NUCLEOTIDE_CITATION_DOI]
    CITATION_URLS = [f"https://doi.org/{HMMER_NUCLEOTIDE_CITATION_DOI}"]
    CITATION_TEXT = "Accelerated profile HMM searches for large nucleotide sequence databases."
    AUDIT_CAVEATS = (
        "The 3.4 manpage still states --popen 0.02 and --pextend 0.4, while the pinned "
        "src/nhmmer.c option table executes with 0.03125 and 0.75; this contract follows the source.",
        "The manpage states F2=0.001 and F3=1e-5, while src/nhmmer.c executes with "
        "F2=0.003 and F3=3e-5; this contract follows the source.",
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        optional: dict[str, Any] = {
            **common_output_inputs(),
            "singlemx": (
                "BOOLEAN",
                {"default": False, "description": "Use single-sequence matrix scoring for a one-sequence MSA"},
            ),
            "popen": ("FLOAT", {"default": 0.03125, "min": 0, "description": "Gap-open probability"}),
            "pextend": ("FLOAT", {"default": 0.75, "min": 0, "description": "Gap-extension probability"}),
            "matrix_file": (
                "FILE",
                {"default": "", "description": "Square nucleotide substitution matrix", "advanced": True},
            ),
            **common_threshold_inputs(include_default=0.01, domains=False, model_cutoffs=True),
            **common_heuristic_inputs((0.02, 0.003, 3e-5)),
            "input_format_select": (
                "STRING",
                {"default": "", "options": ["", "--dna", "--rna"], "description": "Optional query alphabet assertion"},
            ),
            "nonull2": ("BOOLEAN", {"default": False, "advanced": True}),
            "z": ("FLOAT", {"default": "", "min": 0, "description": "Database size in megabases", "advanced": True}),
            "w_beta": ("FLOAT", {"default": 1e-7, "min": 0, "max": 1, "advanced": True}),
            "w_length": ("INT", {"default": "", "min": 4, "advanced": True}),
            "strand": (
                "STRING",
                {"default": "both", "options": ["both", "watson", "crick"], "description": "Target strand selection"},
            ),
            "threads": ("INT", {"default": 2, "min": 0, "max": 128, "description": "Parallel CPU workers"}),
            "seed": ("INT", {"default": 42, "min": 0}),
        }
        return {
            "required": {
                "hmmfile": (
                    "FILE",
                    {"description": "Nucleotide query HMM, multiple alignment, or sequence file"},
                ),
                "seqfile": ("FASTA", {"description": "Target nucleotide sequence database"}),
            },
            "optional": optional,
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_search_options(inputs, domains=False, model_cutoffs=True)
        if validation is not True:
            return validation
        if str(inputs.get("hmmfile", "")) == "-" and str(inputs.get("seqfile", "")) == "-":
            return "nhmmer cannot read both query and target from stdin"
        if not 0 <= float(inputs.get("popen", 0.03125)) < 0.5:
            return "Input 'popen' must be at least 0 and less than 0.5"
        if not 0 <= float(inputs.get("pextend", 0.75)) < 1:
            return "Input 'pextend' must be at least 0 and less than 1"
        w_beta = inputs.get("w_beta", 1e-7)
        if w_beta not in (None, "") and not 0 <= float(w_beta) <= 1:
            return "Input 'w_beta' must be between 0 and 1"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        command = ["nhmmer"]
        add_output_flags(
            command,
            inputs,
            (
                ("-o", "output.txt"),
                ("--tblout", "results.tblout"),
                ("--dfamtblout", "dfam.tblout"),
                ("--aliscoresout", "alignment_scores.txt"),
            ),
        )
        add_boolean_flags(command, inputs, (("acc", "--acc"), ("noali", "--noali"), ("notextw", "--notextw")))
        add_boolean_flags(command, inputs, (("singlemx", "--singlemx"),))
        add_value(command, "--popen", inputs.get("popen", 0.03125))
        add_value(command, "--pextend", inputs.get("pextend", 0.75))
        add_value(command, "--mxfile", inputs.get("matrix_file"))
        add_threshold_flags(command, inputs, include_default=0.01, domains=False, allow_model_cutoffs=True)
        add_heuristic_flags(command, inputs, defaults=(0.02, 0.003, 3e-5))
        if inputs.get("input_format_select"):
            command.append(str(inputs["input_format_select"]))
        add_boolean_flags(command, inputs, (("nonull2", "--nonull2"),))
        add_value(command, "-Z", inputs.get("z"))
        add_value(command, "--w_beta", inputs.get("w_beta", 1e-7))
        add_value(command, "--w_length", inputs.get("w_length"))
        strand = str(inputs.get("strand", "both"))
        if strand != "both":
            command.append(f"--{strand}")
        add_value(command, "--cpu", inputs.get("threads", 2))
        add_value(command, "--seed", inputs.get("seed", 42))
        command.extend([str(inputs["hmmfile"]), str(inputs["seqfile"])])
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_root: str | Path) -> list[Path]:
        return plan_outputs(output_root, cls.NODE_ID, _OUTPUT_FILENAMES)
