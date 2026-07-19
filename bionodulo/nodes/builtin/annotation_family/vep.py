"""Ensembl Variant Effect Predictor 113.4 using a staged offline cache."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import (
    AnnotationCommandNode,
    path_value,
    validate_choice,
    validate_exact_path,
    validate_int,
)


class VEPNode(AnnotationCommandNode):
    """Annotate variants with VEP using one explicit full cache directory."""

    NODE_ID = "vep"
    DISPLAY_NAME = "VEP"
    DESCRIPTION = "Ensembl Variant Effect Predictor 113.4 with an explicit offline cache."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "VEP",
        "variant effect predictor",
        "Ensembl",
        "variant annotation",
        "ClinVar",
    ]
    RETURN_TYPES = ("FILE", "HTML_REPORT")
    RETURN_NAMES = ("annotated_vcf", "vep_report")
    REQUIRED_EXECUTABLES = ["vep"]
    REQUIRED_CONDA_PACKAGES = ["ensembl-vep"]
    CONDA_PACKAGE_CONSTRAINTS = {"ensembl-vep": "113.4"}
    VERSION = "113.4"
    GIT_URL = "https://github.com/Ensembl/ensembl-vep.git"
    GIT_COMMIT = "a6786e4357f442a81624f58d9e79f343909d717f"
    DOCUMENTATION_URL = "https://www.ensembl.org/info/docs/tools/vep/script/vep_options.html"
    SOURCE_URL = "https://github.com/Ensembl/ensembl-vep/blob/release/113.4/modules/Bio/EnsEMBL/VEP/Config.pm"
    UPSTREAM_SOURCE = "modules/Bio/EnsEMBL/VEP/Config.pm; modules/Bio/EnsEMBL/VEP/CacheDir.pm"
    CITATION_DOIS = ["10.1186/s13059-016-0974-4"]
    CITATION_URLS = ["https://doi.org/10.1186/s13059-016-0974-4"]
    CITATION_TEXT = "The Ensembl Variant Effect Predictor."
    REQUIRED_PATH_INPUTS = ("vcf", "cache_dir")
    OUTPUT_FORMATS = ("vcf", "tab")
    PREDICTION_FORMATS = ("b", "s", "p")
    CACHE_VERSION = 113
    EXIT_SEMANTICS = (
        "VEP exits non-zero for an absent cache, cache/assembly mismatch, invalid option combination, "
        "or unreadable custom annotation; BioNodulo also requires both output and stats files."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": (("VCF", "VCF_GZ"), {"description": "Input VCF"}),
                "cache_dir": (
                    "DIRECTORY",
                    {
                        "description": (
                            "Full species/version/assembly VEP cache directory, for example homo_sapiens/113_GRCh38"
                        )
                    },
                ),
            },
            "optional": {
                "assembly": ("STRING", {"default": "GRCh38"}),
                "species": ("STRING", {"default": "homo_sapiens"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64}),
                "everything": ("BOOLEAN", {"default": False}),
                "symbol": ("BOOLEAN", {"default": False}),
                "af": ("BOOLEAN", {"default": False}),
                "max_af": ("BOOLEAN", {"default": False}),
                "sift": ("STRING", {"default": "", "options": ["", *cls.PREDICTION_FORMATS]}),
                "polyphen": (
                    "STRING",
                    {"default": "", "options": ["", *cls.PREDICTION_FORMATS]},
                ),
                "clinvar": ("VCF_GZ", {"description": "Sorted, bgzip-compressed ClinVar VCF"}),
                "clinvar_index": (
                    "VCF_INDEX",
                    {"description": "Exact <clinvar>.tbi index required with a ClinVar VCF"},
                ),
                "output_format": ("STRING", {"default": "vcf", "options": list(cls.OUTPUT_FORMATS)}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in ("assembly", "species"):
            value = str(inputs.get(key, "GRCh38" if key == "assembly" else "homo_sapiens")).strip()
            if not value or "/" in value or "\\" in value:
                return f"Input '{key}' must be a non-empty identifier"
        validation = validate_int(inputs.get("threads", 1), "threads", minimum=1, maximum=64)
        if validation is not True:
            return validation
        validation = validate_choice(inputs.get("output_format", "vcf"), "output_format", cls.OUTPUT_FORMATS)
        if validation is not True:
            return validation
        for key in ("sift", "polyphen"):
            value = inputs.get(key, "")
            if value not in (None, ""):
                validation = validate_choice(value, key, cls.PREDICTION_FORMATS)
                if validation is not True:
                    return validation

        clinvar = path_value(inputs.get("clinvar"))
        clinvar_index = path_value(inputs.get("clinvar_index"))
        if clinvar:
            return validate_exact_path(clinvar_index, Path(f"{clinvar}.tbi"), "clinvar_index")
        if clinvar_index:
            return "Input 'clinvar_index' requires 'clinvar'"
        return True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        output_format = str(inputs.get("output_format", "vcf"))
        validation = validate_choice(output_format, "output_format", cls.OUTPUT_FORMATS)
        if validation is not True:
            raise ValueError(str(validation))
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        return [node_dir / f"annotated_vcf.{output_format}", node_dir / "vep_report.html"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        output = Path(path_value(inputs.get("output", inputs.get("output_dir", "."))))
        output_format = str(inputs.get("output_format", "vcf"))
        command = [
            "vep",
            "--input_file",
            path_value(inputs["vcf"]),
            "--output_file",
            str(output / f"annotated_vcf.{output_format}"),
            "--format",
            "vcf",
            f"--{output_format}",
            "--fork",
            str(inputs.get("threads", 1)),
            "--species",
            str(inputs.get("species", "homo_sapiens")),
            "--assembly",
            str(inputs.get("assembly", "GRCh38")),
            "--offline",
            "--full_cache_dir",
            path_value(inputs["cache_dir"]),
            "--force_overwrite",
        ]
        if inputs.get("everything", False):
            command.append("--everything")
        else:
            if inputs.get("symbol", False):
                command.append("--symbol")
            if inputs.get("af", False):
                command.append("--af")
            if inputs.get("max_af", False):
                command.append("--max_af")
            for key, flag in (("sift", "--sift"), ("polyphen", "--polyphen")):
                value = inputs.get(key, "")
                if value not in (None, ""):
                    command.extend([flag, str(value)])
        if inputs.get("clinvar"):
            command.extend(
                [
                    "--custom",
                    (f"file={path_value(inputs['clinvar'])},short_name=ClinVar,format=vcf,type=exact,fields=CLNSIG"),
                ]
            )
        command.extend(["--stats_file", str(output / "vep_report.html")])
        return command
