"""HMMER 3.4 ``nhmmscan`` contract."""

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
    stage_pressed_hmm_bundle,
    validate_pressed_hmm_bundle,
    validate_search_options,
)

_OUTPUT_FILENAMES = ("output.txt", "results.tblout", "dfam.tblout")
_DATABASE_INPUTS = ("hmmdb", "hmmdb_h3f", "hmmdb_h3i", "hmmdb_h3m", "hmmdb_h3p")


class HMMERNhmmscanNode(HMMERContractNode):
    """Search nucleotide sequences against a pressed nucleotide profile database."""

    NODE_ID = "hmmer_nhmmscan"
    VERSION = HMMER_VERSION
    DISPLAY_NAME = "HMMER nhmmscan"
    CATEGORY = "annotation"
    DESCRIPTION = "Search nucleotide sequences against a database prepared by hmmpress."
    SEARCH_ALIASES = ["BioNodulo builtin", "hmmer", "nhmmscan", "Dfam", "nucleotide profiles"]
    RETURN_TYPES = ("STATS_FILE", "TSV", "TEXT")
    RETURN_NAMES = ("output", "tblout", "dfamtblout")
    REQUIRED_EXECUTABLES = ["nhmmscan"]
    REQUIRED_PATH_INPUTS = (*_DATABASE_INPUTS, "seqfile")
    DOCUMENTATION_URL = f"{HMMER_SOURCE_ROOT}/documentation/man/nhmmscan.man.in"
    SOURCE_URL = f"{HMMER_SOURCE_ROOT}/src/nhmmscan.c"
    SOURCE_PATHS = ("documentation/man/nhmmscan.man.in", "src/nhmmscan.c")
    SIDECAR_DOCUMENTATION_URL = f"{HMMER_SOURCE_ROOT}/documentation/man/hmmpress.man.in"
    SIDECAR_SOURCE_PATHS = ("documentation/man/hmmpress.man.in",)
    UPSTREAM_SOURCE = "documentation/man/nhmmscan.man.in; documentation/man/hmmpress.man.in; src/nhmmscan.c::main"
    CITATION_DOIS = [HMMER_NUCLEOTIDE_CITATION_DOI]
    CITATION_URLS = [f"https://doi.org/{HMMER_NUCLEOTIDE_CITATION_DOI}"]
    CITATION_TEXT = "Accelerated profile HMM searches for large nucleotide sequence databases."
    SIDECAR_POLICY = (
        "nhmmscan opens <hmmdb>.h3f, .h3i, .h3m, and .h3p by sibling discovery. "
        "All four hmmpress products are explicit inputs and are staged with the database."
    )
    AUDIT_CAVEATS = (
        "The 3.4 nhmmscan manpage lists --aliscoresout, but the pinned src/nhmmscan.c "
        "option table and implementation do not accept or create it; the port is intentionally absent.",
        "The manpage states F2=0.001 and F3=1e-5, while src/nhmmscan.c executes with "
        "F2=0.003 and F3=3e-5; this contract follows the source.",
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        optional: dict[str, Any] = {
            **common_output_inputs(),
            **common_threshold_inputs(include_default=0.01, domains=False, model_cutoffs=True),
            **common_heuristic_inputs((0.02, 0.003, 3e-5)),
            "nonull2": ("BOOLEAN", {"default": False, "advanced": True}),
            "z": ("FLOAT", {"default": "", "min": 0, "advanced": True}),
            "w_beta": ("FLOAT", {"default": 1e-7, "min": 0, "max": 1, "advanced": True}),
            "w_length": ("INT", {"default": "", "min": 4, "advanced": True}),
            "strand": (
                "STRING",
                {"default": "both", "options": ["both", "watson", "crick"], "description": "Query strand selection"},
            ),
            "threads": (
                "INT",
                {"default": 0, "min": 0, "max": 128, "description": "Parallel CPU workers; upstream default is off"},
            ),
            "seed": ("INT", {"default": 42, "min": 0}),
        }
        return {
            "required": {
                "hmmdb": ("FILE", {"description": "Nucleotide profile HMM database"}),
                "hmmdb_h3f": ("FILE", {"description": "Exact <hmmdb>.h3f sibling from hmmpress"}),
                "hmmdb_h3i": ("FILE", {"description": "Exact <hmmdb>.h3i sibling from hmmpress"}),
                "hmmdb_h3m": ("FILE", {"description": "Exact <hmmdb>.h3m sibling from hmmpress"}),
                "hmmdb_h3p": ("FILE", {"description": "Exact <hmmdb>.h3p sibling from hmmpress"}),
                "seqfile": ("FASTA", {"description": "Nucleotide query sequences"}),
            },
            "optional": optional,
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_pressed_hmm_bundle(inputs)
        if validation is not True:
            return validation
        validation = validate_search_options(inputs, domains=False, model_cutoffs=True)
        if validation is not True:
            return validation
        w_beta = inputs.get("w_beta", 1e-7)
        if w_beta not in (None, "") and not 0 <= float(w_beta) <= 1:
            return "Input 'w_beta' must be between 0 and 1"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        command = ["nhmmscan"]
        add_output_flags(
            command,
            inputs,
            (("-o", "output.txt"), ("--tblout", "results.tblout"), ("--dfamtblout", "dfam.tblout")),
        )
        add_boolean_flags(command, inputs, (("acc", "--acc"), ("noali", "--noali"), ("notextw", "--notextw")))
        add_threshold_flags(command, inputs, include_default=0.01, domains=False, allow_model_cutoffs=True)
        add_heuristic_flags(command, inputs, defaults=(0.02, 0.003, 3e-5))
        add_boolean_flags(command, inputs, (("nonull2", "--nonull2"),))
        add_value(command, "-Z", inputs.get("z"))
        add_value(command, "--w_beta", inputs.get("w_beta", 1e-7))
        add_value(command, "--w_length", inputs.get("w_length"))
        strand = str(inputs.get("strand", "both"))
        if strand != "both":
            command.append(f"--{strand}")
        add_value(command, "--cpu", inputs.get("threads", 0))
        add_value(command, "--seed", inputs.get("seed", 42))
        command.extend([str(inputs["hmmdb"]), str(inputs["seqfile"])])
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_root: str | Path) -> list[Path]:
        return plan_outputs(output_root, cls.NODE_ID, _OUTPUT_FILENAMES)

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        stage_pressed_hmm_bundle(inputs, outputs[0].parent / "inputs")
