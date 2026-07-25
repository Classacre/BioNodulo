"""Focused GATK Funcotator contract with explicit discoverable sidecars."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.builtin.variant_family.gatk_adapter import (
    GATKCommandNode,
    validate_gatk_variant_index,
    validate_reference_bundle,
)

from .evidence import attach_evidence
from .staging import stage_named_bundle


@attach_evidence
class FuncotateTableNode(GATKCommandNode):
    """Annotate a VCF with one pinned GATK Funcotator invocation."""

    NODE_ID = "funcotate_table"
    DISPLAY_NAME = "Funcotate Table"
    CATEGORY = "annotation"
    DESCRIPTION = "Oncotator-style functional annotation for cancer variants using GATK Funcotator."
    SEARCH_ALIASES = [
        "funcotator",
        "funcotate",
        "cancer variants",
        "oncotator",
        "somatic annotation",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("annotated",)
    UPSTREAM_SOURCE = "src/main/java/org/broadinstitute/hellbender/tools/funcotator/Funcotator.java"

    @classmethod
    def _output_filename(cls, output_format: str) -> str:
        return "annotated.vcf" if output_format.upper() == "VCF" else "annotated.maf"

    @staticmethod
    def _split_annotations(value: Any) -> list[str]:
        return [item.strip() for item in str(value or "").split(",") if item.strip()]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": ("VCF", {"description": "Input VCF to annotate"}),
                "vcf_index": (
                    "VCF_INDEX",
                    {"description": "Exact .tbi or .idx sidecar for the input VCF"},
                ),
                "reference": ("FASTA", {"description": "Reference FASTA used for the VCF"}),
                "reference_index": (
                    "FASTA_INDEX",
                    {"description": "Exact <reference>.fai sidecar"},
                ),
                "sequence_dictionary": (
                    "SEQUENCE_DICTIONARY",
                    {"description": "Exact extension-replaced <reference>.dict sidecar"},
                ),
                "data_sources": ("DIRECTORY", {"description": "Funcotator data sources directory"}),
                "ref_version": ("STRING", {"default": "hg38", "options": ["hg38", "hg19"]}),
            },
            "optional": {
                "output_format": ("STRING", {"default": "MAF", "options": ["MAF", "VCF"]}),
                "transcript_selection_mode": (
                    "STRING",
                    {
                        "default": "",
                        "options": ["", "CANONICAL", "BEST_EFFECT", "ALL"],
                        "advanced": True,
                    },
                ),
                "annotation_defaults": (
                    "STRING",
                    {"default": "", "description": "Comma-separated KEY:VALUE defaults", "advanced": True},
                ),
                "annotation_overrides": (
                    "STRING",
                    {"default": "", "description": "Comma-separated KEY:VALUE overrides", "advanced": True},
                ),
                "intervals": (
                    "FILE",
                    {"default": "", "description": "Optional intervals to annotate", "advanced": True},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for key in ("vcf", "vcf_index", "reference", "reference_index", "sequence_dictionary", "data_sources"):
            if not str(inputs.get(key, "")).strip():
                return f"{key} is required"

        validation = validate_gatk_variant_index(
            inputs,
            variant_key="vcf",
            index_key="vcf_index",
        )
        if validation is not True:
            return validation
        validation = validate_reference_bundle(inputs)
        if validation is not True:
            return validation

        output_format = str(inputs.get("output_format", "MAF")).upper()
        if output_format not in {"MAF", "VCF"}:
            return "output_format must be one of: MAF, VCF"
        if str(inputs.get("ref_version", "hg38")) not in {"hg38", "hg19"}:
            return "ref_version must be one of: hg38, hg19"
        selection_mode = str(inputs.get("transcript_selection_mode", ""))
        if selection_mode not in {"", "CANONICAL", "BEST_EFFECT", "ALL"}:
            return "transcript_selection_mode must be one of: CANONICAL, BEST_EFFECT, ALL"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        output_format = str(inputs.get("output_format", "MAF")).upper()
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = [
            "gatk",
            "Funcotator",
            "-R",
            str(inputs["reference"]),
            "-V",
            str(inputs["vcf"]),
            "-O",
            str(output / cls._output_filename(output_format)),
            "--output-file-format",
            output_format,
            "--data-sources-path",
            str(inputs["data_sources"]),
            "--ref-version",
            str(inputs.get("ref_version", "hg38")),
        ]
        if inputs.get("transcript_selection_mode"):
            command.extend(["--transcript-selection-mode", str(inputs["transcript_selection_mode"])])
        for annotation in cls._split_annotations(inputs.get("annotation_defaults")):
            command.extend(["--annotation-default", annotation])
        for annotation in cls._split_annotations(inputs.get("annotation_overrides")):
            command.extend(["--annotation-override", annotation])
        if inputs.get("intervals"):
            command.extend(["-L", str(inputs["intervals"])])
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / cls._output_filename(str(inputs.get("output_format", "MAF")))]

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        reference = Path(str(inputs["reference"]))
        vcf = Path(str(inputs["vcf"]))
        destination = outputs[0].parent / "inputs"
        stage_named_bundle(
            inputs,
            destination_dir=destination,
            names={
                "reference": reference.name,
                "reference_index": f"{reference.name}.fai",
                "sequence_dictionary": reference.with_suffix(".dict").name,
                "vcf": vcf.name,
                "vcf_index": Path(str(inputs["vcf_index"])).name,
            },
        )
