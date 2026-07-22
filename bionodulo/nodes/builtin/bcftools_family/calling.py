"""BCFtools 1.24 likelihood generation and variant calling."""

from __future__ import annotations

from typing import Any

from .adapter import (
    COMMON_FILTER_INPUTS,
    CoreFixedVcfOutputNode,
    add_fixed_vcf_output,
    add_value,
    as_list,
    require_path,
    require_paths,
    uses_regions,
    validate_choice,
    validate_data_index,
    validate_data_indexes,
    validate_number,
    validate_reference_index,
)


class BCFtoolsMpileupNode(CoreFixedVcfOutputNode):
    """Generate genotype likelihoods from coordinate-sorted alignments."""

    NODE_ID = "bcftools_mpileup"
    DISPLAY_NAME = "BCFtools Mpileup"
    DESCRIPTION = "Generate compressed VCF genotype likelihoods from BAM or CRAM alignments"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "mpileup", "genotype likelihoods", "BAM CRAM pileup"]
    RETURN_NAMES = ("mpileup_vcf",)
    OUTPUT_FILENAME = "mpileup.vcf.gz"
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#mpileup"
    REQUIRED_EXECUTABLES = ["bcftools"]
    UPSTREAM_SOURCE = "mpileup.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        optional = {
            "reference": ("FASTA", {"default": "", "description": "Faidx-indexed reference FASTA"}),
            "reference_index": ("FASTA_INDEX", {"default": "", "description": "Exact <reference>.fai sidecar"}),
            "no_reference": ("BOOLEAN", {"default": False, "description": "Explicitly run without a reference"}),
            "alignment_indexes": (
                "FILE_LIST",
                {"default": [], "description": "One colocated BAI, CSI, or CRAI per alignment for region jumps"},
            ),
            "max_depth": (
                "INT",
                {"default": None, "min": 0, "description": "Maximum reads per input; 0 removes the limit"},
            ),
            "minimum_mapping_quality": ("INT", {"default": None, "min": 0}),
            "minimum_base_quality": ("INT", {"default": None, "min": 0}),
            "annotate": ("STRING_LIST", {"default": [], "description": "Output annotation tags"}),
            "gvcf": ("STRING", {"default": "", "description": "Comma-separated minimum depth thresholds"}),
            "samples": ("STRING", {"default": ""}),
            "samples_file": ("FILE", {"default": ""}),
            "regions": COMMON_FILTER_INPUTS["regions"],
            "regions_file": COMMON_FILTER_INPUTS["regions_file"],
            "regions_overlap": COMMON_FILTER_INPUTS["regions_overlap"],
            "targets": COMMON_FILTER_INPUTS["targets"],
            "targets_file": COMMON_FILTER_INPUTS["targets_file"],
            "targets_overlap": COMMON_FILTER_INPUTS["targets_overlap"],
            "skip_all_set": ("STRING", {"default": "", "description": "Documented SAM flag names or integer mask"}),
            "skip_any_set": ("STRING", {"default": "", "description": "Documented SAM flag names or integer mask"}),
            "skip_all_unset": ("STRING", {"default": "", "description": "Documented SAM flag names or integer mask"}),
            "skip_any_unset": ("STRING", {"default": "", "description": "Documented SAM flag names or integer mask"}),
            "threads": ("INT", {"default": 4, "min": 0}),
            "reference_source": (
                "STRING",
                {"default": "", "options": ["", "history", "cached", "none"], "advanced": True},
            ),
        }
        return {
            "required": {"input_bams": ("FILE_LIST", {"description": "Coordinate-sorted BAM or CRAM inputs"})},
            "optional": optional,
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _no_reference(cls, inputs: dict[str, Any]) -> bool:
        return bool(inputs.get("no_reference")) or inputs.get("reference_source") == "none"

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = require_paths(inputs, "input_bams")
        if validation is not True:
            return validation
        if cls._no_reference(inputs):
            if inputs.get("reference") or inputs.get("reference_index"):
                return "no_reference cannot be combined with reference or reference_index"
        else:
            validation = require_path(inputs, "reference")
            if validation is not True:
                return validation
            validation = validate_reference_index(inputs)
            if validation is not True:
                return validation
        if inputs.get("max_depth") not in (None, ""):
            validation = validate_number(inputs["max_depth"], "max_depth", minimum=0, integer=True)
            if validation is not True:
                return validation
        if uses_regions(inputs):
            validation = validate_data_indexes(
                inputs,
                data_key="input_bams",
                index_key="alignment_indexes",
                alignment=True,
            )
            if validation is not True:
                return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        command = ["bcftools", "mpileup"]
        if cls._no_reference(inputs):
            command.append("--no-reference")
        else:
            command.extend(["-f", str(inputs["reference"])])
        add_value(command, "--max-depth", inputs.get("max_depth"))
        add_value(command, "--min-MQ", inputs.get("minimum_mapping_quality"))
        add_value(command, "--min-BQ", inputs.get("minimum_base_quality"))
        annotate = ",".join(as_list(inputs.get("annotate")))
        add_value(command, "--annotate", annotate)
        add_value(command, "--gvcf", inputs.get("gvcf"))
        add_value(command, "--samples", inputs.get("samples"))
        add_value(command, "--samples-file", inputs.get("samples_file"))
        for key, flag in (
            ("regions", "--regions"),
            ("regions_file", "--regions-file"),
            ("regions_overlap", "--regions-overlap"),
            ("targets", "--targets"),
            ("targets_file", "--targets-file"),
            ("targets_overlap", "--targets-overlap"),
            ("skip_all_set", "--skip-all-set"),
            ("skip_any_set", "--skip-any-set"),
            ("skip_all_unset", "--skip-all-unset"),
            ("skip_any_unset", "--skip-any-unset"),
        ):
            add_value(command, flag, inputs.get(key))
        threads = inputs.get("threads", 4)
        if threads:
            command.extend(["--threads", str(threads)])
        add_fixed_vcf_output(command, cls, inputs)
        command.extend(as_list(inputs.get("input_bams")))
        return command


class BCFtoolsCallNode(CoreFixedVcfOutputNode):
    """Call variants from a likelihood VCF using one exclusive caller."""

    NODE_ID = "bcftools_call"
    DISPLAY_NAME = "BCFtools Call"
    DESCRIPTION = "Call SNP and indel variants from genotype likelihoods"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "call", "variant calling", "SNP indel calling"]
    RETURN_NAMES = ("called_vcf",)
    OUTPUT_FILENAME = "called.vcf.gz"
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#call"
    UPSTREAM_SOURCE = "vcfcall.c"
    CALLERS = ("multiallelic", "consensus")
    CONSTRAINTS = ("none", "alleles")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input_file": ("VCF", {"description": "Likelihood VCF or BCF, typically from mpileup"})},
            "optional": {
                "input_index": COMMON_FILTER_INPUTS["input_index"],
                "caller": ("STRING", {"default": "multiallelic", "options": list(cls.CALLERS)}),
                "constrain": ("STRING", {"default": "none", "options": list(cls.CONSTRAINTS)}),
                "gvcf": ("STRING_LIST", {"default": [], "description": "Integer depth thresholds"}),
                "prior_freqs": ("STRING", {"default": "", "description": "AN,AC prior-frequency tags"}),
                "group_samples": ("FILE", {"default": "", "description": "Population grouping file"}),
                "group_samples_tag": ("STRING", {"default": ""}),
                "prior": ("FLOAT", {"default": None, "min": 0}),
                "samples": ("STRING", {"default": ""}),
                "samples_file": ("FILE", {"default": ""}),
                "regions": COMMON_FILTER_INPUTS["regions"],
                "regions_file": COMMON_FILTER_INPUTS["regions_file"],
                "regions_overlap": COMMON_FILTER_INPUTS["regions_overlap"],
                "targets": COMMON_FILTER_INPUTS["targets"],
                "targets_file": COMMON_FILTER_INPUTS["targets_file"],
                "targets_overlap": COMMON_FILTER_INPUTS["targets_overlap"],
                "ploidy": ("STRING", {"default": ""}),
                "ploidy_file": ("FILE", {"default": ""}),
                "insert_missed": ("BOOLEAN", {"default": False}),
                "pval_threshold": ("FLOAT", {"default": None, "min": 0, "max": 1}),
                "variants_only": ("BOOLEAN", {"default": False}),
                "skip_variants": ("STRING", {"default": "", "options": ["", "snps", "indels"]}),
                "threads": ("INT", {"default": 4, "min": 0}),
                "method": (
                    "STRING",
                    {"default": "", "advanced": True, "description": "Compatibility alias for caller"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _caller(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("caller") or inputs.get("method") or "multiallelic")

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = require_path(inputs, "input_file")
        if validation is not True:
            return validation
        caller = cls._caller(inputs)
        validation = validate_choice(caller, "caller", cls.CALLERS)
        if validation is not True:
            return validation
        constrain = str(inputs.get("constrain", "none") or "none")
        if constrain == "trio":
            return "constrain=trio is not runnable in BCFtools 1.24; upstream aborts constrained trio calling"
        validation = validate_choice(constrain, "constrain", cls.CONSTRAINTS)
        if validation is not True:
            return validation
        if constrain == "alleles":
            if caller != "multiallelic":
                return "constrain=alleles requires the multiallelic caller"
            if not (inputs.get("targets") or inputs.get("targets_file")):
                return "constrain=alleles requires targets or targets_file"
        if inputs.get("insert_missed") and constrain != "alleles":
            return "insert_missed requires constrain=alleles"
        if inputs.get("gvcf") and caller != "multiallelic":
            return "gvcf requires the multiallelic caller"
        if inputs.get("gvcf") and inputs.get("variants_only"):
            return "variants_only and gvcf are mutually exclusive"
        if inputs.get("group_samples") and caller != "multiallelic":
            return "group_samples requires the multiallelic caller"
        if inputs.get("group_samples_tag") and not inputs.get("group_samples"):
            return "group_samples_tag requires group_samples"
        if inputs.get("prior_freqs"):
            prior_tags = str(inputs["prior_freqs"]).split(",")
            if len(prior_tags) != 2 or any(not tag.strip() for tag in prior_tags):
                return "prior_freqs must contain exactly two non-empty comma-separated tags"
            if caller != "multiallelic":
                return "prior_freqs requires the multiallelic caller"
        if inputs.get("prior") not in (None, ""):
            validation = validate_number(inputs["prior"], "prior", minimum=0)
            if validation is not True:
                return validation
            if caller != "multiallelic":
                return "prior requires the multiallelic caller"
        if inputs.get("pval_threshold") not in (None, ""):
            validation = validate_number(inputs["pval_threshold"], "pval_threshold", minimum=0, maximum=1)
            if validation is not True:
                return validation
            if caller != "consensus":
                return "pval_threshold requires the consensus caller"
        if inputs.get("novel_rate") not in (None, ""):
            return "novel_rate applies only to trio calling, which is disabled in BCFtools 1.24"
        if inputs.get("ploidy") and inputs.get("ploidy_file"):
            return "ploidy and ploidy_file are mutually exclusive"
        for value in as_list(inputs.get("gvcf")):
            try:
                if int(value) < 0 or str(int(value)) != value.strip():
                    raise ValueError
            except ValueError:
                return "gvcf must contain only non-negative integers"
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
        caller = cls._caller(inputs)
        command = ["bcftools", "call", "-m" if caller == "multiallelic" else "-c"]
        constrain = str(inputs.get("constrain", "none") or "none")
        if constrain != "none":
            command.extend(["--constrain", constrain])
        gvcf = ",".join(as_list(inputs.get("gvcf")))
        add_value(command, "--gvcf", gvcf)
        add_value(command, "--prior-freqs", inputs.get("prior_freqs"))
        add_value(command, "--group-samples", inputs.get("group_samples"))
        add_value(command, "--group-samples-tag", inputs.get("group_samples_tag"))
        add_value(command, "--prior", inputs.get("prior"))
        add_value(command, "--samples", inputs.get("samples"))
        add_value(command, "--samples-file", inputs.get("samples_file"))
        for key, flag in (
            ("regions", "--regions"),
            ("regions_file", "--regions-file"),
            ("regions_overlap", "--regions-overlap"),
            ("targets", "--targets"),
            ("targets_file", "--targets-file"),
            ("targets_overlap", "--targets-overlap"),
            ("ploidy", "--ploidy"),
            ("ploidy_file", "--ploidy-file"),
            ("pval_threshold", "--pval-threshold"),
            ("skip_variants", "--skip-variants"),
        ):
            add_value(command, flag, inputs.get(key))
        if inputs.get("insert_missed"):
            command.append("--insert-missed")
        if inputs.get("variants_only"):
            command.append("--variants-only")
        threads = inputs.get("threads", 4)
        if threads:
            command.extend(["--threads", str(threads)])
        add_fixed_vcf_output(command, cls, inputs)
        command.append(str(inputs["input_file"]))
        return command
