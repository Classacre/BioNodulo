"""RSeQC ``read_hexamer.py`` node pinned to the 5.0.3 sdist."""

from __future__ import annotations

from typing import Any

from .adapter import RSeQCCommandNode


class RSeQCReadHexamerNode(RSeQCCommandNode):
    """Calculate six-mer frequencies from one or more sequence files."""

    NODE_ID = "rseqc_read_hexamer"
    DISPLAY_NAME = "RSeQC Read Hexamer"
    DESCRIPTION = "Calculate hexamer frequencies for FASTA or FASTQ reads and optional references."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "RSeQC",
        "read_hexamer.py",
        "read hexamer",
        "hexamer frequency",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("hexamer_frequencies",)
    REQUIRED_EXECUTABLES = ["read_hexamer.py"]
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#read-hexamer-py"
    UPSTREAM_SCRIPT = "scripts/read_hexamer.py"
    UPSTREAM_SOURCE = UPSTREAM_SCRIPT
    UPSTREAM_OUTPUT_SOURCE = "scripts/read_hexamer.py:main (stdout)"
    OUTPUT_FILENAMES = ("read_hexamer.tsv",)
    STDOUT_OUTPUT_INDEX = 0
    REQUIRED_PATH_LIST_INPUTS = ("inputs",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputs": (
                    ("FASTA", "FASTQ"),
                    {
                        "multiple": True,
                        "description": "One or more uncompressed FASTA or FASTQ files",
                    },
                ),
            },
            "optional": {
                "refgenome": (
                    "FASTA",
                    {"description": "Optional reference genome FASTA"},
                ),
                "refgene": (
                    "FASTA",
                    {"description": "Optional reference mRNA FASTA"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        paths = cls.path_list(inputs.get("inputs"))
        for path in paths:
            if "," in path:
                return "Input 'inputs' paths must not contain commas"
            if path.lower().endswith((".gz", ".gzip", ".bz2", ".xz")):
                return (
                    "Input 'inputs' must contain uncompressed FASTA/FASTQ files; "
                    f"compressed path is not supported by read_hexamer.py: {path}"
                )
        for key in ("refgenome", "refgene"):
            value = inputs.get(key)
            if value not in (None, ""):
                validation = cls.require_path(inputs, key)
                if validation is not True:
                    return validation
                if cls.path_value(value).lower().endswith((".gz", ".gzip", ".bz2", ".xz")):
                    return f"Input '{key}' must be an uncompressed FASTA"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        paths = cls.path_list(inputs.get("inputs"))
        command = ["read_hexamer.py", "-i", ",".join(paths)]
        refgenome = cls.path_value(inputs.get("refgenome"))
        if refgenome:
            command.extend(["-r", refgenome])
        refgene = cls.path_value(inputs.get("refgene"))
        if refgene:
            command.extend(["-g", refgene])
        return command
