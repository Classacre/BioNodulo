"""Focused ANNOVAR contract using its documented direct VCF workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode

from .evidence import attach_evidence


@attach_evidence
class ANNOVARNode(CommandNode):
    """Annotate variants with the licensed ANNOVAR distribution."""

    NODE_ID = "annovar"
    DISPLAY_NAME = "ANNOVAR"
    CATEGORY = "annotation"
    DESCRIPTION = (
        "Comprehensive variant annotation: gene-based, region-based, "
        "filter-based. Clinical interpretation."
    )
    SEARCH_ALIASES = ["annovar", "variant annotation", "clinical", "clinvar", "gnomad"]
    RETURN_TYPES = ("VCF", "TABULAR")
    RETURN_NAMES = ("annotated_vcf", "multianno_table")
    REQUIRED_EXECUTABLES = ["table_annovar.pl"]
    REQUIRED_CONDA_PACKAGES: list[str] = []
    DOCUMENTATION_URL = "https://annovar.openbioinformatics.org/"
    INSTALLATION_REQUIRED = "User-supplied licensed ANNOVAR 2020-06-08 distribution"
    SHELL = False
    EXPERIMENTAL = True

    DEFAULT_PROTOCOL = "refGene,cytoBand,gnomad40_genome,clinvar_20220320"
    DEFAULT_OPERATION = "g,r,f,f"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": ("VCF_GZ", {"description": "Input VCF"}),
                "humandb_dir": ("DIRECTORY", {"description": "ANNOVAR humandb"}),
                "buildver": ("STRING", {"default": "hg38", "options": ["hg38", "hg19"]}),
                "protocol": ("STRING", {"default": cls.DEFAULT_PROTOCOL}),
                "operation": (
                    "STRING",
                    {"default": cls.DEFAULT_OPERATION, "description": "g=gene,r=region,f=filter"},
                ),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for key in ("vcf", "humandb_dir"):
            if not str(inputs.get(key, "")).strip():
                return f"{key} is required"
        buildver = str(inputs.get("buildver", "hg38"))
        if buildver not in {"hg19", "hg38"}:
            return "buildver must be one of: hg19, hg38"
        protocols = [
            item.strip()
            for item in str(inputs.get("protocol", cls.DEFAULT_PROTOCOL)).split(",")
            if item.strip()
        ]
        operations = [
            item.strip()
            for item in str(inputs.get("operation", cls.DEFAULT_OPERATION)).split(",")
            if item.strip()
        ]
        if not protocols or len(protocols) != len(operations):
            return "protocol and operation must contain the same non-zero number of entries"
        if any(operation not in {"g", "r", "f"} for operation in operations):
            return "operation entries must be one of: g, r, f"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        out_dir = Path(str(inputs.get("output", ".")))
        buildver = str(inputs.get("buildver", "hg38"))
        prefix = out_dir / "annovar"
        return [
            "table_annovar.pl",
            str(inputs["vcf"]),
            str(inputs["humandb_dir"]),
            "-buildver",
            buildver,
            "-out",
            str(prefix),
            "-remove",
            "-protocol",
            str(inputs.get("protocol", cls.DEFAULT_PROTOCOL)),
            "-operation",
            str(inputs.get("operation", cls.DEFAULT_OPERATION)),
            "-nastring",
            ".",
            "-vcfinput",
            "-polish",
        ]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        buildver = str(inputs.get("buildver", "hg38"))
        return [
            node_out / f"annovar.{buildver}_multianno.vcf",
            node_out / f"annovar.{buildver}_multianno.txt",
        ]
