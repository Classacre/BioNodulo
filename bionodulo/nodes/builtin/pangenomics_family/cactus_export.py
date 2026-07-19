"""Stable owner for the Tools-IUC ``cactus_export`` contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .evidence import PangenomicsCommandContract


class CactusExportNode(PangenomicsCommandContract):
    """Export Cactus HAL alignments to Galaxy-supported downstream formats."""

    NODE_ID = "cactus_export"
    OUTPUT_NAME_BY_BASENAME = {
        "alignment.maf": "out_maf",
        "alignment.pg": "out_vg",
        "assemblyhub.tar": "out_ah",
    }
    DISPLAY_NAME = "Cactus Export"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Convert Cactus HAL whole-genome alignments to MAF, VG, or UCSC Assembly Hub archives."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "Cactus Export",
        "cactus_export",
        "HAL export",
        "hal2maf",
        "hal2vg",
        "hal2assemblyHub",
        "MAF alignment",
        "UCSC Assembly Hub",
    ]
    RETURN_TYPES = ("MAF", "VG", "TAR")
    RETURN_NAMES = ("out_maf", "out_vg", "out_ah")
    REQUIRED_EXECUTABLES = ["hal2maf", "hal2vg", "hal2assemblyHub.py", "tar"]
    REQUIRED_CONDA_PACKAGES = ["cactus", "tar"]
    DOCUMENTATION_URL = "https://github.com/ComparativeGenomicsToolkit/cactus#using-the-output"
    CITATION_DOIS = ["10.1038/s41586-020-2871-y"]
    CITATION_URLS = ["https://doi.org/10.1038/s41586-020-2871-y"]
    CITATION_TEXT = "Progressive Cactus is a multiple-genome aligner for the thousand-genome era."
    VERSION = "2.7.1+galaxy0"
    SHELL = True

    FORMATS = ["maf_selector", "vg_selector", "ah_selector"]

    @classmethod
    def _format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("format", "maf_selector") or "maf_selector")

    @classmethod
    def _positive_int(cls, inputs: dict[str, Any], key: str, default: int) -> int | str:
        value = inputs.get(key, default)
        if value in (None, ""):
            value = default
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if parsed <= 0:
            return f"{key} must be greater than zero"
        return parsed

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("hal_file", "")).strip():
            return "hal_file is required"
        export_format = cls._format(inputs)
        if export_format not in cls.FORMATS:
            return f"format must be one of: {', '.join(cls.FORMATS)}"
        if export_format in {"maf_selector", "vg_selector"} and not str(inputs.get("ref_level", "")).strip():
            return "ref_level is required for MAF and VG export"
        for key, default in (("max_cores", 4), ("max_memory_mb", 8196)):
            validation = cls._positive_int(inputs, key, default)
            if isinstance(validation, str):
                return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = str(inputs.get("output", "."))
        export_format = cls._format(inputs)
        cmd = [
            "ln",
            "-s",
            str(inputs.get("hal_file", "")),
            f"{out_dir}/alignment.hal",
            "&&",
            "cd",
            out_dir,
            "&&",
        ]
        if export_format == "maf_selector":
            cmd.extend([
                "hal2maf",
                "--refGenome",
                str(inputs.get("ref_level", "")),
                "alignment.hal",
                "alignment.maf",
            ])
        elif export_format == "vg_selector":
            cmd.extend([
                "hal2vg",
                "alignment.hal",
                "--progress",
                ">",
                "alignment.pg",
            ])
        else:
            max_cores = cls._positive_int(inputs, "max_cores", 4)
            max_memory = cls._positive_int(inputs, "max_memory_mb", 8196)
            assert isinstance(max_cores, int)
            assert isinstance(max_memory, int)
            cmd.extend([
                "hal2assemblyHub.py",
                "--maxCores",
                str(max_cores),
                "--maxMemory",
                f"{max_memory}M",
                "./jobStore",
                "alignment.hal",
                "assemblyhub",
                "&&",
                "tar",
                "-cv",
                "assemblyhub",
                ">",
                "assemblyhub.tar",
            ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        export_format = cls._format(inputs)
        if export_format == "vg_selector":
            return [node_out / "alignment.pg"]
        if export_format == "ah_selector":
            return [node_out / "assemblyhub.tar"]
        return [node_out / "alignment.maf"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "hal_file": ("HAL", {"description": "HAL file generated by Cactus"}),
            },
            "optional": {
                "format": (
                    "STRING",
                    {
                        "default": "maf_selector",
                        "options": cls.FORMATS,
                        "description": "Export MAF, VG, or UCSC Assembly Hub format",
                    },
                ),
                "ref_level": ("STRING", {"default": "", "description": "Reference genome label for MAF and VG exports"}),
                "max_cores": ("INT", {"default": 4, "min": 1, "max": 512, "display": "slider"}),
                "max_memory_mb": ("INT", {"default": 8196, "min": 1, "display": "slider"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
