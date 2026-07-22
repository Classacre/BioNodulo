"""BCFtools 1.24 copy-number and consequence analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import (
    COMMON_FILTER_INPUTS,
    CoreBCFtoolsCommandNode,
    CoreFixedVcfOutputNode,
    add_common_filters,
    add_fixed_vcf_output,
    add_flag,
    add_value,
    require_path,
    uses_regions,
    validate_data_index,
    validate_number,
    validate_reference_index,
)


class BCFtoolsCNVNode(CoreBCFtoolsCommandNode):
    """Call CNVs and retain the complete source-defined output directory."""

    NODE_ID = "bcftools_cnv"
    DISPLAY_NAME = "BCFtools CNV"
    DESCRIPTION = "Call copy-number variation from BAF and LRR intensity annotations"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "cnv", "copy number variation", "BAF", "LRR"]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("cnv_results",)
    OUTPUT_FILENAMES = ("results",)
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#cnv"
    UPSTREAM_SOURCE = "vcfcnv.c"
    REQUIRED_EXECUTABLES = ["bcftools", "python"]
    REQUIRED_CONDA_PACKAGES = ["bcftools", "htslib", "python", "numpy", "matplotlib"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("VCF", {"description": "VCF with BAF and LRR intensity fields"}),
            },
            "optional": {
                "input_index": COMMON_FILTER_INPUTS["input_index"],
                "query_sample": (
                    "STRING",
                    {"default": "", "description": "Sample to call; omit only for a single-sample VCF"},
                ),
                "control_sample": ("STRING", {"default": ""}),
                "af_file": ("TSV", {"default": ""}),
                "plot_threshold": ("FLOAT", {"default": None}),
                "aberrant_query": ("FLOAT", {"default": None}),
                "aberrant_control": ("FLOAT", {"default": None}),
                "optimize": ("FLOAT", {"default": None}),
                "baf_weight": ("FLOAT", {"default": None}),
                "baf_dev_query": ("FLOAT", {"default": None}),
                "baf_dev_control": ("FLOAT", {"default": None}),
                "lrr_weight": ("FLOAT", {"default": None}),
                "lrr_dev_query": ("FLOAT", {"default": None}),
                "lrr_dev_control": ("FLOAT", {"default": None}),
                "lrr_smooth_win": ("INT", {"default": None, "min": 0}),
                "same_prob": ("FLOAT", {"default": None}),
                "err_prob": ("FLOAT", {"default": None}),
                "xy_prob": ("FLOAT", {"default": None}),
                "regions": COMMON_FILTER_INPUTS["regions"],
                "regions_file": COMMON_FILTER_INPUTS["regions_file"],
                "regions_overlap": COMMON_FILTER_INPUTS["regions_overlap"],
                "targets": COMMON_FILTER_INPUTS["targets"],
                "targets_file": COMMON_FILTER_INPUTS["targets_file"],
                "targets_overlap": COMMON_FILTER_INPUTS["targets_overlap"],
                "AF_file": ("TSV", {"default": "", "advanced": True}),
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
        query = str(inputs.get("query_sample", "")).strip()
        control = str(inputs.get("control_sample", "")).strip()
        if control and not query:
            return "control_sample requires an explicit query_sample"
        if control and control == query:
            return "query_sample and control_sample must be distinct"
        control_settings = ("aberrant_control", "baf_dev_control", "lrr_dev_control")
        if not control and any(inputs.get(key) not in (None, "") for key in control_settings):
            return "control-specific HMM settings require control_sample"
        if uses_regions(inputs):
            validation = validate_data_index(inputs)
            if validation is not True:
                return validation
        return True

    @classmethod
    def _pair(cls, inputs: dict[str, Any], query_key: str, control_key: str) -> str:
        query = inputs.get(query_key)
        control = inputs.get(control_key)
        if query in (None, "") and control in (None, ""):
            return ""
        if control not in (None, ""):
            return f"{'' if query in (None, '') else query},{control}"
        return str(query)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        command = ["bcftools", "cnv", "--output-dir", str(cls.result_dir(inputs))]
        add_value(command, "--query-sample", inputs.get("query_sample"))
        add_value(command, "--control-sample", inputs.get("control_sample"))
        add_value(command, "--AF-file", inputs.get("af_file") or inputs.get("AF_file"))
        add_value(command, "--plot-threshold", inputs.get("plot_threshold"))
        add_value(command, "--aberrant", cls._pair(inputs, "aberrant_query", "aberrant_control"))
        add_value(command, "--optimize", inputs.get("optimize"))
        add_value(command, "--BAF-weight", inputs.get("baf_weight"))
        add_value(command, "--BAF-dev", cls._pair(inputs, "baf_dev_query", "baf_dev_control"))
        add_value(command, "--LRR-weight", inputs.get("lrr_weight"))
        add_value(command, "--LRR-dev", cls._pair(inputs, "lrr_dev_query", "lrr_dev_control"))
        add_value(command, "--LRR-smooth-win", inputs.get("lrr_smooth_win"))
        add_value(command, "--same-prob", inputs.get("same_prob"))
        add_value(command, "--err-prob", inputs.get("err_prob"))
        add_value(command, "--xy-prob", inputs.get("xy_prob"))
        add_value(command, "--regions", inputs.get("regions"))
        add_value(command, "--regions-file", inputs.get("regions_file"))
        add_value(command, "--regions-overlap", inputs.get("regions_overlap"))
        add_value(command, "--targets", inputs.get("targets"))
        add_value(command, "--targets-file", inputs.get("targets_file"))
        add_value(command, "--targets-overlap", inputs.get("targets_overlap"))
        command.append(str(inputs["input_file"]))
        return command


class BCFtoolsCSQNode(CoreFixedVcfOutputNode):
    """Annotate haplotype-aware consequences from reference and GFF3."""

    NODE_ID = "bcftools_csq"
    DISPLAY_NAME = "BCFtools CSQ"
    DESCRIPTION = "Annotate haplotype-aware variant consequences from FASTA and GFF3"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "csq", "consequence prediction", "BCSQ"]
    RETURN_NAMES = ("csq_vcf",)
    OUTPUT_FILENAME = "csq.vcf.gz"
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#csq"
    UPSTREAM_SOURCE = "csq.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("VCF", {"description": "VCF or BCF to annotate"}),
                "reference": ("FASTA", {"description": "Reference FASTA"}),
                "reference_index": ("FASTA_INDEX", {"description": "Exact <reference>.fai"}),
                "gff_annot": ("GFF3", {"description": "GFF3 formatted for bcftools csq"}),
            },
            "optional": {
                "input_index": COMMON_FILTER_INPUTS["input_index"],
                "ncsq": ("INT", {"default": None, "min": 1}),
                "local_csq": ("BOOLEAN", {"default": False}),
                "phase": ("STRING", {"default": "", "options": ["", "a", "m", "r", "R", "s"]}),
                "custom_tag": ("STRING", {"default": ""}),
                "trim_protein_seq": ("INT", {"default": None, "min": 1}),
                "genetic_code": ("STRING", {"default": ""}),
                "samples": ("STRING", {"default": ""}),
                "samples_file": ("FILE", {"default": ""}),
                "include": COMMON_FILTER_INPUTS["include"],
                "exclude": COMMON_FILTER_INPUTS["exclude"],
                "regions": COMMON_FILTER_INPUTS["regions"],
                "regions_file": COMMON_FILTER_INPUTS["regions_file"],
                "regions_overlap": COMMON_FILTER_INPUTS["regions_overlap"],
                "targets": COMMON_FILTER_INPUTS["targets"],
                "targets_file": COMMON_FILTER_INPUTS["targets_file"],
                "targets_overlap": COMMON_FILTER_INPUTS["targets_overlap"],
                "threads": ("INT", {"default": 0, "min": 0}),
                "annotation": ("GFF3", {"default": "", "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in ("input_file", "reference"):
            validation = require_path(inputs, key)
            if validation is not True:
                return validation
        if not str(inputs.get("gff_annot") or inputs.get("annotation") or "").strip():
            return "gff_annot must be non-empty"
        validation = validate_reference_index(inputs)
        if validation is not True:
            return validation
        if inputs.get("samples") and inputs.get("samples_file"):
            return "samples and samples_file are mutually exclusive"
        if inputs.get("trim_protein_seq") not in (None, ""):
            validation = validate_number(
                inputs["trim_protein_seq"],
                "trim_protein_seq",
                minimum=1,
                integer=True,
            )
            if validation is not True:
                return validation
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
        command = [
            "bcftools",
            "csq",
            "-f",
            str(inputs["reference"]),
            "-g",
            str(inputs.get("gff_annot") or inputs.get("annotation")),
        ]
        add_value(command, "--ncsq", inputs.get("ncsq"))
        add_flag(command, "--local-csq", inputs.get("local_csq"))
        add_value(command, "--phase", inputs.get("phase"))
        add_value(command, "--custom-tag", inputs.get("custom_tag"))
        add_value(command, "--trim-protein-seq", inputs.get("trim_protein_seq"))
        add_value(command, "--genetic-code", inputs.get("genetic_code"))
        add_common_filters(command, inputs, samples=True)
        threads = inputs.get("threads", 0)
        if threads:
            command.extend(["--threads", str(threads)])
        add_fixed_vcf_output(command, cls, inputs)
        command.append(str(inputs["input_file"]))
        return command
