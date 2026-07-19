"""Medaka 2.0.1 consensus polishing with an explicit local model artifact."""

from __future__ import annotations

from typing import Any

from .adapter import LongReadCommandNode, option_value, path_value, validate_int


class MedakaConsensusNode(LongReadCommandNode):
    """Polish a draft assembly while disabling automatic model selection."""

    NODE_ID = "medaka_consensus"
    DISPLAY_NAME = "Medaka Consensus"
    DESCRIPTION = "Polish an Oxford Nanopore draft assembly with an explicit Medaka model"
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "Medaka",
        "consensus",
        "assembly polishing",
        "Oxford Nanopore",
        "ONT",
    ]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("polished_assembly",)
    OUTPUT_FILENAMES = ("consensus.fasta",)
    REQUIRED_PATH_INPUTS = ("reads", "draft", "model")
    REQUIRED_EXECUTABLES = ["medaka_consensus"]
    REQUIRED_CONDA_PACKAGES = ["medaka"]
    PACKAGE_CONSTRAINT = "medaka = 2.0.1"
    VERSION = "2.0.1"
    GIT_URL = "https://github.com/nanoporetech/medaka.git"
    GIT_COMMIT = "03b58482ca38088790edfa4b196f8bf619f83c05"
    SOURCE_TAG = "v2.0.1"
    DOCUMENTATION_URL = "https://github.com/nanoporetech/medaka/tree/v2.0.1"
    UPSTREAM_SOURCE = "scripts/medaka_consensus; medaka/medaka.py; medaka/models.py"
    EXIT_SEMANTICS = (
        "The medaka_consensus shell wrapper uses set -euo pipefail and exits non-zero "
        "for missing required inputs or failed alignment, inference, or stitching."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": (
                    ("FASTQ", "FASTA", "BAM"),
                    {"description": "Basecalled reads accepted by medaka_consensus -i"},
                ),
                "draft": ("FASTA", {"description": "Draft assembly to polish"}),
                "model": (
                    "FILE",
                    {
                        "description": (
                            "Staged Medaka .hdf or .tar.gz model; explicit -m prevents "
                            "automatic model selection and download"
                        )
                    },
                ),
            },
            "optional": {
                "threads": ("INT", {"default": 1, "min": 1}),
                "batch_size": ("INT", {"default": 100, "min": 1}),
                "no_fillgaps": ("BOOLEAN", {"default": False}),
                "fill_char": ("STRING", {"default": ""}),
                "min_mapq": ("INT", {"default": None, "min": 0}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        model = path_value(inputs.get("model"))
        if "/" not in model and not model.endswith((".hdf", ".tar.gz")):
            return "Input 'model' must be a staged local Medaka model file, not a model identifier"
        for key, default in (("threads", 1), ("batch_size", 100)):
            validation = validate_int(option_value(inputs, key, default), key, minimum=1)
            if validation is not True:
                return validation
        if inputs.get("min_mapq") is not None:
            validation = validate_int(inputs["min_mapq"], "min_mapq", minimum=0)
            if validation is not True:
                return validation
        fill_char = str(option_value(inputs, "fill_char", ""))
        if len(fill_char) > 1:
            return "Input 'fill_char' must contain at most one character"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get("output", inputs.get("output_dir", ".")))
        command = cls.checked_command(
            inputs,
            "medaka_consensus",
            "-i",
            path_value(inputs["reads"]),
            "-d",
            path_value(inputs["draft"]),
            "-o",
            output,
            "-m",
            path_value(inputs["model"]),
            "-t",
            str(option_value(inputs, "threads", 1)),
            "-b",
            str(option_value(inputs, "batch_size", 100)),
            "-f",
        )
        if option_value(inputs, "no_fillgaps", False):
            command.append("-g")
        if inputs.get("fill_char"):
            command.extend(["-r", str(inputs["fill_char"])])
        if inputs.get("min_mapq") is not None:
            command.extend(["-M", str(inputs["min_mapq"])])
        return command


class MedakaNode(MedakaConsensusNode):
    """Compatibility alias preserving the original stable Medaka node ID."""

    NODE_ID = "medaka"
    DISPLAY_NAME = "Medaka"
    DESCRIPTION = "Polish an Oxford Nanopore draft assembly with Medaka"
    SEARCH_ALIASES = [*MedakaConsensusNode.SEARCH_ALIASES, "medaka consensus"]
