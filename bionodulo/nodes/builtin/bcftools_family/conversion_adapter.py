"""BCFtools 1.24 conversions between VCF and documented genetics formats."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import (
    COMMON_FILTER_INPUTS,
    CoreBCFtoolsCommandNode,
    CoreFixedVcfOutputNode,
    add_fixed_vcf_output,
    add_flag,
    add_value,
    require_path,
    uses_regions,
    validate_choice,
    validate_data_index,
    validate_reference_index,
)


class BCFtoolsConvertToVcfNode(CoreFixedVcfOutputNode):
    """Convert TSV, gVCF, GEN, HAP, or HAP/LEGEND inputs to VCF."""

    LEGACY_NODE_ID = "bcftools_convert_to_vcf"
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
                "convert_3n6": ("BOOLEAN", {"default": False, "description": "Expect 3*N+6 GEN/SAMPLE input"}),
                "vcf_ids": ("BOOLEAN", {"default": False}),
                "threads": ("INT", {"default": 4, "min": 0}),
                "convert_from": (
                    "STRING",
                    {"default": "", "advanced": True, "description": "Compatibility alias for mode"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _mode(cls, inputs: dict[str, Any]) -> str:
        value = str(inputs.get("mode") or inputs.get("convert_from") or "tsv")
        return {
            "tsv2vcf": "tsv",
            "gvcf2vcf": "gvcf",
            "gen": "gen_sample",
            "hap": "hap_sample",
            "haplegendsample": "hap_legend_sample",
        }.get(value, value)

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
        if mode != "tsv" and (inputs.get("columns") or inputs.get("samples") or inputs.get("samples_file")):
            return "columns, samples, and samples_file apply only to tsv mode"
        if mode in {"gen_sample", "hap_sample", "hap_legend_sample"}:
            validation = require_path(inputs, "sample_file")
            if validation is not True:
                return validation
        elif inputs.get("sample_file"):
            return "sample_file requires a GEN or HAP conversion mode"
        if mode == "hap_legend_sample":
            validation = require_path(inputs, "legend_file")
            if validation is not True:
                return validation
        elif inputs.get("legend_file"):
            return "legend_file requires hap_legend_sample mode"
        if inputs.get("sex_file") or inputs.get("haploid2diploid"):
            return "sex_file and haploid2diploid apply only when converting from VCF"
        if inputs.get("convert_3n6") and mode != "gen_sample":
            return "convert_3n6 requires gen_sample mode"
        if inputs.get("vcf_ids") and mode not in {"gen_sample", "hap_sample"}:
            return "vcf_ids is supported only for GEN/SAMPLE or HAP/SAMPLE input"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        mode = cls._mode(inputs)
        command = ["bcftools", "convert"]
        if mode == "tsv":
            command.extend(
                ["--tsv2vcf", str(inputs["input_file"]), "-c", str(inputs["columns"]), "-f", str(inputs["reference"])]
            )
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
            add_flag(command, "--3N6", inputs.get("convert_3n6"))
            add_flag(command, "--vcf-ids", inputs.get("vcf_ids"))
        threads = inputs.get("threads", 4)
        if threads:
            command.extend(["--threads", str(threads)])
        add_fixed_vcf_output(command, cls, inputs)
        if mode == "gvcf":
            command.append(str(inputs["input_file"]))
        return command


class BCFtoolsConvertFromVcfNode(CoreBCFtoolsCommandNode):
    """Convert a VCF into one native multi-file result directory."""

    LEGACY_NODE_ID = "bcftools_convert_from_vcf"
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
                "tag": (
                    "STRING",
                    {"default": "", "options": ["", "GT", "PL", "GP"], "description": "GEN probability source tag"},
                ),
                "convert_3n6": ("BOOLEAN", {"default": False, "description": "Write 3*N+6 GEN format"}),
                "vcf_ids": ("BOOLEAN", {"default": False}),
                "haploid2diploid": ("BOOLEAN", {"default": False}),
                "sex_file": ("FILE", {"default": ""}),
                "keep_duplicates": ("BOOLEAN", {"default": False}),
                "include": COMMON_FILTER_INPUTS["include"],
                "exclude": COMMON_FILTER_INPUTS["exclude"],
                "regions": COMMON_FILTER_INPUTS["regions"],
                "regions_file": COMMON_FILTER_INPUTS["regions_file"],
                "regions_overlap": COMMON_FILTER_INPUTS["regions_overlap"],
                "targets": COMMON_FILTER_INPUTS["targets"],
                "targets_file": COMMON_FILTER_INPUTS["targets_file"],
                "targets_overlap": COMMON_FILTER_INPUTS["targets_overlap"],
                "samples": ("STRING", {"default": ""}),
                "samples_file": ("FILE", {"default": ""}),
                "threads": ("INT", {"default": 4, "min": 0}),
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
        mode = str(inputs.get("convert_to", "gen_sample"))
        validation = validate_choice(mode, "convert_to", cls.MODES)
        if validation is not True:
            return validation
        if inputs.get("tag"):
            validation = validate_choice(str(inputs["tag"]), "tag", ("GT", "PL", "GP"))
            if validation is not True:
                return validation
            if mode != "gen_sample":
                return "tag requires gen_sample mode"
        if inputs.get("convert_3n6") and mode != "gen_sample":
            return "convert_3n6 requires gen_sample mode"
        if inputs.get("keep_duplicates") and mode != "gen_sample":
            return "keep_duplicates requires gen_sample mode"
        if inputs.get("haploid2diploid") and mode == "gen_sample":
            return "haploid2diploid requires a HAP output mode"
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
                f"{result_dir / 'converted.hap'},{result_dir / 'converted.legend'},{result_dir / 'converted.samples'}"
            )
        command = ["bcftools", "convert", flag, output_spec]
        add_value(command, "--tag", inputs.get("tag"))
        add_flag(command, "--3N6", inputs.get("convert_3n6"))
        add_flag(command, "--vcf-ids", inputs.get("vcf_ids"))
        add_flag(command, "--haploid2diploid", inputs.get("haploid2diploid"))
        add_value(command, "--sex", inputs.get("sex_file"))
        add_flag(command, "--keep-duplicates", inputs.get("keep_duplicates"))
        add_value(command, "--include", inputs.get("include"))
        add_value(command, "--exclude", inputs.get("exclude"))
        add_value(command, "--samples", inputs.get("samples"))
        add_value(command, "--samples-file", inputs.get("samples_file"))
        add_value(command, "--regions", inputs.get("regions"))
        add_value(command, "--regions-file", inputs.get("regions_file"))
        add_value(command, "--regions-overlap", inputs.get("regions_overlap"))
        add_value(command, "--targets", inputs.get("targets"))
        add_value(command, "--targets-file", inputs.get("targets_file"))
        add_value(command, "--targets-overlap", inputs.get("targets_overlap"))
        threads = inputs.get("threads", 4)
        if threads:
            command.extend(["--threads", str(threads)])
        command.append(str(inputs["input_file"]))
        return command
