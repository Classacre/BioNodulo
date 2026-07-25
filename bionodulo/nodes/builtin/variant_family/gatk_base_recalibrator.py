"""GATK 4.6.2.0 BaseRecalibrator node."""

from __future__ import annotations

from typing import Any

from .gatk_adapter import (
    GATKCommandNode,
    path_values,
    validate_gatk_bam_index,
    validate_reference_bundle,
    validate_variant_index_pairs,
)


class GatkBaseRecalibratorNode(GATKCommandNode):
    """Build a BQSR recalibration table from one indexed BAM."""

    NODE_ID = "gatk_base_recalibrator"
    DISPLAY_NAME = "GATK BaseRecalibrator"
    DESCRIPTION = "Generate a BQSR recalibration table using known polymorphic sites"
    SEARCH_ALIASES = ["gatk", "bqsr", "base recalibration", "known sites"]
    RETURN_TYPES = ("TABLE",)
    RETURN_NAMES = ("recal_table",)
    OUTPUT_FILENAMES = ("recalibration.table",)
    DOCUMENTATION_URL = "https://gatk.broadinstitute.org/hc/en-us/articles/360036898312-BaseRecalibrator"
    UPSTREAM_SOURCE = (
        "src/main/java/org/broadinstitute/hellbender/tools/walkers/bqsr/BaseRecalibrator.java"
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Coordinate-sorted BAM with read groups"}),
                "bam_index": (
                    "BAI",
                    {"description": "Exact colocated <stem>.bai or <bam>.bai index"},
                ),
                "reference": (
                    "FASTA",
                    {"description": "Reference FASTA with colocated FAI and sequence dictionary"},
                ),
                "reference_index": (
                    "FASTA_INDEX",
                    {"description": "Exact <reference>.fai sidecar"},
                ),
                "sequence_dictionary": (
                    "SEQUENCE_DICTIONARY",
                    {"description": "Exact extension-replaced <reference>.dict sidecar"},
                ),
                "known_sites": (
                    ("VCF", "VCF_GZ"),
                    {
                        "multiple": True,
                        "description": "One or more known-polymorphism VCF resources",
                    },
                ),
                "known_sites_indexes": (
                    "VCF_INDEX",
                    {
                        "multiple": True,
                        "description": "One exact TBI or Tribble IDX per known-sites VCF",
                    },
                ),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_gatk_bam_index(inputs)
        if validation is not True:
            return validation
        validation = validate_reference_bundle(inputs)
        if validation is not True:
            return validation
        return validate_variant_index_pairs(
            inputs,
            variants_key="known_sites",
            indexes_key="known_sites_indexes",
            split_commas=True,
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "BaseRecalibrator")
        command.extend(["-R", str(inputs["reference"]), "-I", str(inputs["bam"])])
        known_sites = path_values(inputs["known_sites"], key="known_sites", split_commas=True)
        if isinstance(known_sites, str):
            raise ValueError(known_sites)
        for known_site in known_sites:
            command.extend(["--known-sites", known_site])
        command.extend(["-O", str(cls.output_path(inputs))])
        return command
