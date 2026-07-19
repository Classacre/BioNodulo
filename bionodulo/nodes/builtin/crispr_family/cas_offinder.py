"""Cas-OFFinder 2.4.1 native input-file search contract."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .adapter import (
    CAS_OFFINDER_COMMIT,
    CrisprCommandNode,
    path_value,
    validate_int,
    validate_iupac_sequence,
)


class CasOffinderNode(CrisprCommandNode):
    """Search a FASTA, 2bit file, or sequence directory for guide off-targets."""

    NODE_ID = "cas_offinder"
    DISPLAY_NAME = "Cas-OFFinder"
    DESCRIPTION = "Fast off-target detection for CRISPR guides against an explicit genome sequence source."
    SEARCH_ALIASES = ["BioNodulo builtin", "Cas-OFFinder", "off target", "guide rna", "CRISPR safety"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("offtarget_sites",)
    REQUIRED_EXECUTABLES = ["cas-offinder"]
    REQUIRED_CONDA_PACKAGES = ["cas-offinder"]
    CONDA_PACKAGE_CONSTRAINTS = {"cas-offinder": "2.4.1"}
    VERSION = "2.4.1"
    GIT_URL = "https://github.com/snugel/cas-offinder.git"
    GIT_COMMIT = CAS_OFFINDER_COMMIT
    DOCUMENTATION_URL = "https://github.com/snugel/cas-offinder/tree/2.4.1"
    CITATION_DOIS = ["10.1093/bioinformatics/btu048"]
    CITATION_URLS = ["https://doi.org/10.1093/bioinformatics/btu048"]
    CITATION_TEXT = "Cas-OFFinder: a fast and versatile algorithm that searches for potential off-target sites."
    OUTPUT_FILENAMES = ("offtarget_sites.txt",)
    REQUIRED_PATH_INPUTS = ("genome_fasta",)
    UPSTREAM_SOURCE = "README.md: usage, native input format, output columns; main.cpp: exit behavior"
    INPUT_FILENAME = "cas_offinder_input.txt"
    DEVICE_RE = re.compile(r"^[CGA](?:\d+(?:(?:,|:)\d+)*)?$")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "guide_seq": ("STRING", {"description": "Guide sequence without the PAM"}),
                "genome_fasta": (
                    "FASTA",
                    {"description": "FASTA/2bit file or directory passed as Cas-OFFinder input line 1"},
                ),
                "mismatches": ("INT", {"default": 3, "min": 0}),
            },
            "optional": {
                "pam_sequence": ("STRING", {"default": "NNG", "description": "IUPAC PAM pattern"}),
                "device": (
                    "STRING",
                    {"default": "C", "description": "C, G, or A with optional device IDs/ranges"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_iupac_sequence(inputs.get("guide_seq", ""), "guide_seq")
        if validation is not True:
            return validation
        validation = validate_iupac_sequence(inputs.get("pam_sequence", "NNG"), "pam_sequence")
        if validation is not True:
            return validation
        validation = validate_int(inputs.get("mismatches", 3), "mismatches", minimum=0)
        if validation is not True:
            return validation
        device = str(inputs.get("device", "C"))
        if not cls.DEVICE_RE.fullmatch(device):
            return "Input 'device' must be C, G, or A with optional device IDs/ranges"
        return True

    @classmethod
    def _write_native_input(cls, inputs: dict[str, Any], input_file: Path) -> None:
        guide = str(inputs["guide_seq"]).upper()
        pam = str(inputs.get("pam_sequence", "NNG")).upper()
        pattern = f"{'N' * len(guide)}{pam}"
        input_file.parent.mkdir(parents=True, exist_ok=True)
        input_file.write_text(
            f"{path_value(inputs['genome_fasta'])}\n{pattern}\n{guide}{pam} {inputs.get('mismatches', 3)}\n",
            encoding="ascii",
        )

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        if len(outputs) != 1:
            raise ValueError("cas_offinder requires exactly one planned output")
        input_file = outputs[0].parent / cls.INPUT_FILENAME
        cls._write_native_input(inputs, input_file)
        inputs["_cas_offinder_input"] = str(input_file)
        inputs["_cas_offinder_output"] = str(outputs[0])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "cas-offinder")
        output_dir = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        input_file = Path(str(inputs.get("_cas_offinder_input", output_dir / cls.INPUT_FILENAME)))
        output_file = Path(str(inputs.get("_cas_offinder_output", output_dir / cls.OUTPUT_FILENAMES[0])))
        cls._write_native_input(inputs, input_file)
        command.extend([str(input_file), str(inputs.get("device", "C")), str(output_file)])
        return command
