"""HUMAnN 3.9 functional profiling."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import (
    MetagenomicsCommandNode,
    add_flag,
    path_value,
    validate_choice,
    validate_int,
    validate_number,
)


class HUMAnNNode(MetagenomicsCommandNode):
    """Profile gene families and pathways using explicit reference databases."""

    NODE_ID = "humann"
    DISPLAY_NAME = "HUMAnN"
    DESCRIPTION = "Profile microbial gene families and pathways from reads plus an explicit taxonomic profile."
    SEARCH_ALIASES = ["BioNodulo builtin", "HUMAnN 3", "gene families", "pathways", "functional profiling"]
    RETURN_TYPES = ("HUMANN_OUTPUT", "TSV", "TSV", "TSV", "TXT")
    RETURN_NAMES = ("output_dir", "genefamilies", "pathabundance", "pathcoverage", "log")
    REQUIRED_EXECUTABLES = ["humann"]
    REQUIRED_CONDA_PACKAGES = ["humann"]
    VERSION = "3.9"
    BIOCONDA_VERSION = VERSION
    BIOCONDA_CONSTRAINT = "humann=3.9"
    BIOCONDA_PACKAGE_URL = "https://anaconda.org/bioconda/humann/files?version=3.9"
    GIT_URL = "https://github.com/biobakery/humann.git"
    GIT_COMMIT = "9c6dfef873837c0ed281e1093718769d1aea98c9"
    UPSTREAM_TAG = "v3.9"
    UPSTREAM_SOURCE = "humann/humann.py; humann/config.py; readme.md"
    DOCUMENTATION_URL = "https://github.com/biobakery/humann/blob/9c6dfef873837c0ed281e1093718769d1aea98c9/readme.md"
    CITATION_DOIS = ["10.7554/eLife.65088", "10.1371/journal.pcbi.1002358"]
    CITATION_URLS = [
        "https://doi.org/10.7554/eLife.65088",
        "https://doi.org/10.1371/journal.pcbi.1002358",
    ]
    CITATION_TEXT = "bioBakery 3 and the HUMAnN metabolic reconstruction framework."
    REQUIRED_PATH_INPUTS = ("input", "taxonomic_profile", "nucleotide_database", "protein_database")
    INPUT_FORMATS = ("fastq", "fastq.gz", "fasta", "fasta.gz")
    MEMORY_MODES = ("minimum", "maximum")
    SEARCH_MODES = ("uniref50", "uniref90")
    TRANSLATED_ALIGNERS = ("diamond", "rapsearch", "usearch")
    EXIT_SEMANTICS = (
        "HUMAnN exits nonzero for unreadable inputs, unavailable dependencies, incompatible databases, "
        "or output failures; BioNodulo additionally verifies the native output directory, tables, and log."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (
                    "FILE",
                    {"description": "One FASTA/FASTQ file; upstream requires paired reads to be concatenated first"},
                ),
                "taxonomic_profile": (
                    "METAPHLAN_PROFILE",
                    {"description": "MetaPhlAn profile for the same sample, avoiding an implicit internal prescreen"},
                ),
                "nucleotide_database": ("DIRECTORY", {"description": "ChocoPhlAn nucleotide database directory"}),
                "protein_database": ("DIRECTORY", {"description": "UniRef translated-search database directory"}),
            },
            "optional": {
                "threads": ("INT", {"default": 1, "min": 1}),
                "input_format": ("STRING", {"options": list(cls.INPUT_FORMATS)}),
                "search_mode": ("STRING", {"options": list(cls.SEARCH_MODES)}),
                "memory_use": ("STRING", {"default": "minimum", "options": list(cls.MEMORY_MODES)}),
                "prescreen_threshold": ("FLOAT", {"default": 0.01, "min": 0.0, "max": 100.0}),
                "translated_alignment": (
                    "STRING",
                    {"default": "diamond", "options": list(cls.TRANSLATED_ALIGNERS)},
                ),
                "output_max_decimals": ("INT", {"default": 10, "min": 0}),
                "remove_temp_output": ("BOOLEAN", {"default": False}),
                "remove_stratified_output": ("BOOLEAN", {"default": False}),
                "remove_column_description_output": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def results_dir(cls, inputs: dict[str, Any]) -> Path:
        return cls.output_dir(inputs) / "output"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        results_dir = node_dir / "output"
        return [
            results_dir,
            results_dir / "humann_genefamilies.tsv",
            results_dir / "humann_pathabundance.tsv",
            results_dir / "humann_pathcoverage.tsv",
            node_dir / "humann.log",
        ]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if inputs.get("input_format") is not None:
            validation = validate_choice(inputs["input_format"], "input_format", cls.INPUT_FORMATS)
            if validation is not True:
                return validation
        if inputs.get("search_mode") is not None:
            validation = validate_choice(inputs["search_mode"], "search_mode", cls.SEARCH_MODES)
            if validation is not True:
                return validation
        for key, value, choices in (
            ("memory_use", inputs.get("memory_use", "minimum"), cls.MEMORY_MODES),
            ("translated_alignment", inputs.get("translated_alignment", "diamond"), cls.TRANSLATED_ALIGNERS),
        ):
            validation = validate_choice(value, key, choices)
            if validation is not True:
                return validation
        for key, default, minimum in (("threads", 1, 1), ("output_max_decimals", 10, 0)):
            validation = validate_int(inputs.get(key, default), key, minimum=minimum)
            if validation is not True:
                return validation
        return validate_number(
            inputs.get("prescreen_threshold", 0.01),
            "prescreen_threshold",
            minimum=0.0,
            maximum=100.0,
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        node_dir = cls.output_dir(inputs)
        command = cls.checked_command(
            inputs,
            "humann",
            "--input",
            path_value(inputs.get("input")),
            "--output",
            str(node_dir / "output"),
            "--threads",
            str(inputs.get("threads", 1)),
            "--taxonomic-profile",
            path_value(inputs.get("taxonomic_profile")),
            "--nucleotide-database",
            path_value(inputs.get("nucleotide_database")),
            "--protein-database",
            path_value(inputs.get("protein_database")),
            "--prescreen-threshold",
            str(inputs.get("prescreen_threshold", 0.01)),
            "--memory-use",
            str(inputs.get("memory_use", "minimum")),
            "--translated-alignment",
            str(inputs.get("translated_alignment", "diamond")),
            "--output-basename",
            "humann",
            "--output-format",
            "tsv",
            "--output-max-decimals",
            str(inputs.get("output_max_decimals", 10)),
            "--o-log",
            str(node_dir / "humann.log"),
        )
        if inputs.get("input_format") is not None:
            command.extend(["--input-format", str(inputs["input_format"])])
        if inputs.get("search_mode") is not None:
            command.extend(["--search-mode", str(inputs["search_mode"])])
        add_flag(command, "--remove-temp-output", inputs.get("remove_temp_output"))
        add_flag(command, "--remove-stratified-output", inputs.get("remove_stratified_output"))
        add_flag(
            command,
            "--remove-column-description-output",
            inputs.get("remove_column_description_output"),
        )
        return command
