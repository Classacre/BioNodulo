"""FreeBayes 1.3.10 bamleftalign with an explicit FASTA index."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode
from bionodulo.nodes.builtin._reference_sidecars import validate_colocated_reference_index

from .adapter import stage_file
from .legacy_adapter import path_value, validate_int


class BamLeftAlignNode(CommandNode):
    """Left-align BAM indels while reading the alignment sequentially."""

    NODE_ID = "bamleftalign"
    DISPLAY_NAME = "BamLeftAlign"
    CATEGORY = "variant"
    DESCRIPTION = "Left-align and merge indels in a sequential BAM stream with FreeBayes bamleftalign."
    SEARCH_ALIASES = ["freebayes", "bamleftalign", "left align", "indel realignment"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("realigned_bam",)
    REQUIRED_EXECUTABLES = ["bamleftalign"]
    REQUIRED_CONDA_PACKAGES = ["freebayes"]
    PACKAGE_CONSTRAINTS = ("freebayes==1.3.10",)
    PACKAGE_CONSTRAINT = PACKAGE_CONSTRAINTS[0]
    VERSION = "1.3.10"
    GIT_URL = "https://github.com/freebayes/freebayes.git"
    GIT_COMMIT = "b0d8efd9fa7f6612c883ec5ff79e4d17a0c29993"
    DOCUMENTATION_URL = "https://github.com/freebayes/freebayes/tree/v1.3.10"
    CITATION_DOIS = ["10.1371/journal.pcbi.1002385"]
    CITATION_URLS = ["https://doi.org/10.1371/journal.pcbi.1002385"]
    UPSTREAM_SOURCE = "src/bamleftalign.cpp"
    SHELL = True
    OUTPUT_FILENAME = "realigned.bam"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bam": ("BAM", {"description": "BAM read sequentially from standard input"}),
                "reference": ("FASTA", {"description": "Reference FASTA used for realignment"}),
                "reference_index": ("FASTA_INDEX", {"description": "Exact <reference>.fai sibling"}),
            },
            "optional": {
                "iterations": (
                    "INT",
                    {
                        "default": 5,
                        "min": 1,
                        "description": "Maximum realignment iterations; Galaxy wrapper default is 5, binary default is 50",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / cls.OUTPUT_FILENAME]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if path_value(inputs.get("input_bam")) is None:
            return "input_bam must be a non-empty path"
        sidecar_validation = validate_colocated_reference_index(inputs)
        if sidecar_validation is not True:
            return sidecar_validation
        return validate_int(inputs.get("iterations", 5), "iterations", minimum=1)

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        staged_dir = outputs[0].parent / "reference"
        reference = staged_dir / "reference.fa"
        reference_index = Path(f"{reference}.fai")
        stage_file(Path(str(inputs["reference"])), reference)
        stage_file(Path(str(inputs["reference_index"])), reference_index)
        inputs["reference"] = str(reference)
        inputs["reference_index"] = str(reference_index)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", ".")))) / cls.OUTPUT_FILENAME
        return [
            "set",
            "-o",
            "pipefail",
            "&&",
            "cat",
            str(inputs.get("input_bam", "")),
            "|",
            "bamleftalign",
            "--fasta-reference",
            str(inputs.get("reference", "")),
            "--compressed",
            "--max-iterations",
            str(inputs.get("iterations", 5)),
            ">",
            str(output),
        ]
