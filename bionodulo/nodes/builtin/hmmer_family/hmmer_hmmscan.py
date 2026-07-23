"""HMMER 3.4 ``hmmscan`` contract."""

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
    stage_pressed_hmm_bundle,
    validate_pressed_hmm_bundle,
    validate_search_options,
)

_OUTPUT_FILENAMES = ("output.txt", "results.tblout", "domains.domtblout", "pfam.tblout")
_DATABASE_INPUTS = ("hmmdb", "hmmdb_h3f", "hmmdb_h3i", "hmmdb_h3m", "hmmdb_h3p")


class HMMERHmmscanNode(HMMERContractNode):
    """Search protein sequences against a pressed profile HMM database."""

    NODE_ID = "hmmer_hmmscan"
    VERSION = HMMER_VERSION
    DISPLAY_NAME = "HMMER hmmscan"
    CATEGORY = "annotation"
    DESCRIPTION = "Search protein sequences against a database prepared by hmmpress."
    SEARCH_ALIASES = ["BioNodulo builtin", "hmmer", "hmmscan", "Pfam", "profile annotation"]
    RETURN_TYPES = ("STATS_FILE", "TSV", "TSV", "TSV")
    RETURN_NAMES = ("output", "tblout", "domtblout", "pfamtblout")
    REQUIRED_EXECUTABLES = ["hmmscan"]
    REQUIRED_PATH_INPUTS = (*_DATABASE_INPUTS, "seqfile")
    DOCUMENTATION_URL = f"{HMMER_SOURCE_ROOT}/documentation/man/hmmscan.man.in"
    SOURCE_URL = f"{HMMER_SOURCE_ROOT}/src/hmmscan.c"
    SOURCE_PATHS = ("documentation/man/hmmscan.man.in", "src/hmmscan.c")
    SIDECAR_DOCUMENTATION_URL = f"{HMMER_SOURCE_ROOT}/documentation/man/hmmpress.man.in"
    SIDECAR_SOURCE_PATHS = ("documentation/man/hmmpress.man.in",)
    UPSTREAM_SOURCE = "documentation/man/hmmscan.man.in; documentation/man/hmmpress.man.in; src/hmmscan.c::main"
    SIDECAR_POLICY = (
        "hmmscan opens <hmmdb>.h3f, .h3i, .h3m, and .h3p by sibling discovery. "
        "All four hmmpress products are explicit inputs and are staged with the database."
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
            "threads": (
                "INT",
                {"default": 0, "min": 0, "max": 128, "description": "Parallel CPU workers; upstream default is off"},
            ),
            "seed": ("INT", {"default": 42, "min": 0}),
        }
        return {
            "required": {
                "hmmdb": ("FILE", {"description": "Protein profile HMM database"}),
                "hmmdb_h3f": ("FILE", {"description": "Exact <hmmdb>.h3f sibling from hmmpress"}),
                "hmmdb_h3i": ("FILE", {"description": "Exact <hmmdb>.h3i sibling from hmmpress"}),
                "hmmdb_h3m": ("FILE", {"description": "Exact <hmmdb>.h3m sibling from hmmpress"}),
                "hmmdb_h3p": ("FILE", {"description": "Exact <hmmdb>.h3p sibling from hmmpress"}),
                "seqfile": ("FASTA", {"description": "Protein query sequences"}),
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
        return validate_search_options(inputs, domains=True, model_cutoffs=True)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        command = ["hmmscan"]
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
