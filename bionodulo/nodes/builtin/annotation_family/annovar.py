"""Focused ANNOVAR contract using its documented direct VCF workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .evidence import attach_evidence
from .legacy import ANNOVARNode as _LegacyANNOVARNode


@attach_evidence
class ANNOVARNode(_LegacyANNOVARNode):
    NODE_ID = "annovar"
    RETURN_TYPES = ("VCF", "TABULAR")
    RETURN_NAMES = ("annotated_vcf", "multianno_table")
    REQUIRED_EXECUTABLES = ["table_annovar.pl"]
    REQUIRED_CONDA_PACKAGES: list[str] = []
    INSTALLATION_REQUIRED = "User-supplied licensed ANNOVAR 2020-06-08 distribution"
    SHELL = False

    DEFAULT_PROTOCOL = "refGene,cytoBand,gnomad40_genome,clinvar_20220320"
    DEFAULT_OPERATION = "g,r,f,f"

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
