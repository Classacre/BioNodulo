"""BCFtools 1.24 conversions between VCF and documented genetics formats."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import (
    COMMON_FILTER_INPUTS,
    BCFtoolsCommandNode,
    FixedVcfOutputNode,
    add_fixed_vcf_output,
    add_flag,
    add_value,
    require_path,
    uses_regions,
    validate_choice,
    validate_data_index,
    validate_reference_index,
)


class BCFtoolsConvertToVcfNode(FixedVcfOutputNode):
    """Convert TSV, gVCF, GEN, HAP, or HAP/LEGEND inputs to VCF."""

    NODE_ID = "bcftools_convert_to_vcf"
    DISPLAY_NAME = "BCFtools Convert to VCF"
    DESCRIPTION = "Convert documented tabular or genetics formats into compressed VCF"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "convert", "TSV to VCF", "GEN HAP to VCF"]
    RETURN_NAMES = ("converted_vcf",)
    OUTPUT_FILENAME = "converted.vcf.gz"
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#convert"
    UPSTREAM_SOURCE = "vcfconvert.c"
    MODES = ("tsv", "gvcf", "gen_sample", "hap_sample", "hap_legend_sample")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "mode": ("STRING", {"default": "tsv", "options": list(cls.MODES)}),
                "input_file": ("FILE", {"description": "Primary TSV, gVCF, GEN, or HAP input"}),
            },
            "optional": {
                "sample_file": ("FILE", {"default": "", "description": "SAMPLE companion for GEN/HAP modes"}),
                "legend_file": ("FILE", {"default": "", "description": "LEGEND companion for HAP/LEGEND mode"}),
                "reference": ("FASTA", {"default": "", "description": "Reference required by TSV and gVCF conversion"}),
                "reference_index": ("FASTA_INDEX", {"default": "", "description": "Exact <reference>.fai"}),
                "columns": ("STRING", {"default": "", "description": "TSV column mapping"}),
                "samples": ("STRING", {"default": "", "description": "TSV sample names"}),
                "samples_file": ("FILE", {"default": "", "description": "TSV sample-name file"}),
                "sex_file": ("FILE", {"default": ""}),
                "haploid2diploid": ("BOOLEAN", {"default": False}),
                "vcf_ids": ("BOOLEAN", {"default": False}),
                "threads": ("INT", {"default": 4, "min": 0, "max": 128}),
                "convert_from": ("STRING", {"default": "", "advanced": True, "description": "Compatibility alias for mode"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _mode(cls, inputs: dict[str, Any]) -> str:
        value = str(inputs.get("mode") or inputs.get("convert_from") or "tsv")
        return {"tsv2vcf": "tsv", "gvcf2vcf": "gvcf", "gen": "gen_sample", "hap": "hap_sample", "haplegendsample": "hap_legend_sample"}.get(value, value)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = require_path(inputs, "input_file")
        if validation is not True:
            return validation
        mode = cls._mode(inputs)
        validation = validate_choice(mode, "mode", cls.MODES)
        if validation is not True:
            return validation
        if mode in {"tsv", "gvcf"}:
            validation = require_path(inputs, "reference")
            if validation is not True:
                return validation
            validation = validate_reference_index(inputs)
            if validation is not True:
                return validation
        elif inputs.get("reference") or inputs.get("reference_index"):
            return "reference and reference_index apply only to tsv and gvcf modes"
        if mode == "tsv" and not str(inputs.get("columns", "")).strip():
            return "columns is required for tsv mode"
        if mode in {"gen_sample", "hap_sample", "hap_legend_sample"}:
            validation = require_path(inputs, "sample_file")
            if validation is not True:
                return validation
        if mode == "hap_legend_sample":
            validation = require_path(inputs, "legend_file")
            if validation is not True:
                return validation
        elif inputs.get("legend_file"):
            return "legend_file requires hap_legend_sample mode"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        mode = cls._mode(inputs)
        command = ["bcftools", "convert"]
        if mode == "tsv":
            command.extend(["--tsv2vcf", str(inputs["input_file"]), "-c", str(inputs["columns"]), "-f", str(inputs["reference"])])
            add_value(command, "--samples", inputs.get("samples"))
            add_value(command, "--samples-file", inputs.get("samples_file"))
        elif mode == "gvcf":
            command.extend(["--gvcf2vcf", "-f", str(inputs["reference"])])
        else:
            companions = [str(inputs["input_file"])]
            flag = "--gensample2vcf"
            if mode == "hap_sample":
                flag = "--hapsample2vcf"
            elif mode == "hap_legend_sample":
                flag = "--haplegendsample2vcf"
                companions.append(str(inputs["legend_file"]))
            companions.append(str(inputs["sample_file"]))
            command.extend([flag, ",".join(companions)])
            add_value(command, "--sex", inputs.get("sex_file"))
            add_flag(command, "--haploid2diploid", inputs.get("haploid2diploid"))
            add_flag(command, "--vcf-ids", inputs.get("vcf_ids"))
        threads = inputs.get("threads", 4)
        if threads:
            command.extend(["--threads", str(threads)])
        add_fixed_vcf_output(command, cls, inputs)
        if mode == "gvcf":
            command.append(str(inputs["input_file"]))
        return command


class BCFtoolsConvertFromVcfNode(BCFtoolsCommandNode):
    """Convert a VCF into one native multi-file result directory."""

    NODE_ID = "bcftools_convert_from_vcf"
    DISPLAY_NAME = "BCFtools Convert from VCF"
    DESCRIPTION = "Convert VCF to GEN/SAMPLE, HAP/SAMPLE, or HAP/LEGEND/SAMPLE files"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "convert", "VCF to GEN", "VCF to HAP"]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("converted_files",)
    OUTPUT_FILENAMES = ("results",)
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#convert"
    UPSTREAM_SOURCE = "vcfconvert.c"
    MODES = ("gen_sample", "hap_sample", "hap_legend_sample")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input_file": ("VCF", {"description": "VCF or BCF to convert"})},
            "optional": {
                "input_index": COMMON_FILTER_INPUTS["input_index"],
                "convert_to": ("STRING", {"default": "gen_sample", "options": list(cls.MODES)}),
                "regions": COMMON_FILTER_INPUTS["regions"],
                "regions_file": COMMON_FILTER_INPUTS["regions_file"],
                "regions_overlap": COMMON_FILTER_INPUTS["regions_overlap"],
                "samples": ("STRING", {"default": ""}),
                "samples_file": ("FILE", {"default": ""}),
                "threads": ("INT", {"default": 4, "min": 0, "max": 128}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        result_dir = Path(output_dir) / cls.NODE_ID / "results"
        result_dir.mkdir(parents=True, exist_ok=True)
        return [result_dir]

    @classmethod
    def result_dir(cls, inputs: dict[str, Any]) -> Path:
        return cls.output_dir(inputs) / "results"

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = require_path(inputs, "input_file")
        if validation is not True:
            return validation
        validation = validate_choice(str(inputs.get("convert_to", "gen_sample")), "convert_to", cls.MODES)
        if validation is not True:
            return validation
        if inputs.get("samples") and inputs.get("samples_file"):
            return "samples and samples_file are mutually exclusive"
        if uses_regions(inputs):
            validation = validate_data_index(inputs)
            if validation is not True:
                return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        mode = str(inputs.get("convert_to", "gen_sample"))
        result_dir = cls.result_dir(inputs)
        if mode == "gen_sample":
            flag = "--gensample"
            output_spec = f"{result_dir / 'converted.gen'},{result_dir / 'converted.samples'}"
        elif mode == "hap_sample":
            flag = "--hapsample"
            output_spec = f"{result_dir / 'converted.hap'},{result_dir / 'converted.samples'}"
        else:
            flag = "--haplegendsample"
            output_spec = (
                f"{result_dir / 'converted.hap'},"
                f"{result_dir / 'converted.legend'},"
                f"{result_dir / 'converted.samples'}"
            )
        command = ["bcftools", "convert", flag, output_spec]
        add_value(command, "--samples", inputs.get("samples"))
        add_value(command, "--samples-file", inputs.get("samples_file"))
        add_value(command, "--regions", inputs.get("regions"))
        add_value(command, "--regions-file", inputs.get("regions_file"))
        add_value(command, "--regions-overlap", inputs.get("regions_overlap"))
        threads = inputs.get("threads", 4)
        if threads:
            command.extend(["--threads", str(threads)])
        command.append(str(inputs["input_file"]))
        return command
