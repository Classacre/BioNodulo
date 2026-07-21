"""Prokka 1.15.6 prokaryotic genome annotation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import (
    AnnotationCommandNode,
    path_value,
    validate_choice,
    validate_filename,
    validate_int,
)


class ProkkaNode(AnnotationCommandNode):
    """Create Prokka's documented annotation bundle from one assembly FASTA."""

    NODE_ID = "prokka"
    DISPLAY_NAME = "Prokka"
    DESCRIPTION = "Rapid prokaryotic genome annotation with Prokka 1.15.6."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "Prokka",
        "prokaryotic annotation",
        "bacteria",
        "archaea",
        "genome annotation",
        "Prokka GFF3",
    ]
    RETURN_TYPES = (
        "GFF",
        "FILE",
        "FASTA",
        "FASTA",
        "FASTA",
        "FILE",
        "FASTA",
        "FILE",
        "FILE",
        "FILE",
        "STATS_FILE",
        "TSV",
    )
    RETURN_NAMES = (
        "gff",
        "genbank",
        "proteins",
        "contigs",
        "transcripts",
        "sequin",
        "submission_fasta",
        "feature_table",
        "discrepancy_report",
        "log",
        "statistics",
        "features",
    )
    REQUIRED_EXECUTABLES = ["prokka"]
    REQUIRED_CONDA_PACKAGES = ["prokka"]
    CONDA_PACKAGE_CONSTRAINTS = {"prokka": "1.15.6"}
    VERSION = "1.15.6"
    GIT_URL = "https://github.com/tseemann/prokka.git"
    GIT_COMMIT = "d7b72388989e1fba42c8c68482a36a70dbd3bac4"
    DOCUMENTATION_URL = "https://github.com/tseemann/prokka/tree/v1.15.6"
    SOURCE_URL = "https://github.com/tseemann/prokka/blob/v1.15.6/bin/prokka"
    UPSTREAM_SOURCE = "bin/prokka"
    CITATION_DOIS = ["10.1093/bioinformatics/btu153"]
    CITATION_URLS = ["https://doi.org/10.1093/bioinformatics/btu153"]
    CITATION_TEXT = "Prokka: rapid prokaryotic genome annotation."
    REQUIRED_PATH_INPUTS = ("assembly",)
    KINGDOMS = ("Bacteria", "Archaea", "Viruses", "Mitochondria")
    EXIT_SEMANTICS = (
        "Prokka exits 1 for usage or option-parsing failures and 2 for invalid inputs, "
        "missing databases, or failed child commands; BioNodulo additionally requires "
        "every documented output artifact."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "assembly": ("ASSEMBLY", {"description": "Readable, non-empty contig FASTA"}),
            },
            "optional": {
                "threads": ("INT", {"default": 8, "min": 0}),
                "prefix": ("STRING", {"default": "genome"}),
                "kingdom": ("STRING", {"default": "Bacteria", "options": list(cls.KINGDOMS)}),
                "genus": ("STRING", {"default": ""}),
                "species": ("STRING", {"default": ""}),
                "strain": ("STRING", {"default": ""}),
                "gcode": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 25,
                        "description": "0 selects Prokka's kingdom-specific default",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_int(inputs.get("threads", 8), "threads", minimum=0)
        if validation is not True:
            return validation
        validation = validate_filename(inputs.get("prefix", "genome"), "prefix")
        if validation is not True:
            return validation
        validation = validate_choice(inputs.get("kingdom", "Bacteria"), "kingdom", cls.KINGDOMS)
        if validation is not True:
            return validation
        validation = validate_int(inputs.get("gcode", 0), "gcode", minimum=0, maximum=25)
        if validation is not True:
            return validation

        assembly = Path(path_value(inputs.get("assembly")))
        try:
            if not assembly.is_file():
                return "Input 'assembly' must be a materialized regular file"
            if assembly.stat().st_size == 0:
                return "Input 'assembly' must be non-empty"
            with assembly.open("rb"):
                pass
        except OSError as exc:
            return f"Input 'assembly' must be readable: {exc}"
        return True

    @classmethod
    def _output_filenames(cls, prefix: str) -> tuple[str, ...]:
        return tuple(
            f"{prefix}.{extension}"
            for extension in (
                "gff",
                "gbk",
                "faa",
                "fna",
                "ffn",
                "sqn",
                "fsa",
                "tbl",
                "err",
                "log",
                "txt",
                "tsv",
            )
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        prefix = str(inputs.get("prefix", "genome"))
        validation = validate_filename(prefix, "prefix")
        if validation is not True:
            raise ValueError(str(validation))
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        return [node_dir / filename for filename in cls._output_filenames(prefix)]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        command = [
            "prokka",
            "--outdir",
            path_value(inputs.get("output", inputs.get("output_dir", "."))),
            "--prefix",
            str(inputs.get("prefix", "genome")),
            "--cpus",
            str(inputs.get("threads", 8)),
            "--kingdom",
            str(inputs.get("kingdom", "Bacteria")),
            "--force",
        ]
        for key, flag in (("genus", "--genus"), ("species", "--species"), ("strain", "--strain")):
            value = inputs.get(key)
            if value not in (None, ""):
                command.extend([flag, str(value)])
        gcode = inputs.get("gcode", 0)
        if gcode:
            command.extend(["--gcode", str(gcode)])
        command.append(path_value(inputs["assembly"]))
        return command
