"""BCFtools 1.24 filtering, normalization, combination, and reheadering."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .adapter import (
    BCFTOOLS_GIT_COMMIT,
    COMMON_FILTER_INPUTS,
    BCFtoolsCommandNode,
    FixedVcfOutputNode,
    add_common_filters,
    add_fixed_vcf_output,
    add_flag,
    add_value,
    as_list,
    path_value,
    require_path,
    require_paths,
    uses_regions,
    validate_choice,
    validate_data_index,
    validate_data_indexes,
    validate_exclusive,
    validate_number,
    validate_reference_index,
)


class BCFtoolsFilterNode(FixedVcfOutputNode):
    """Apply documented expressions, masks, gaps, and soft filters."""

    NODE_ID = "bcftools_filter"
    DISPLAY_NAME = "BCFtools Filter"
    DESCRIPTION = "Filter VCF records by expression, masks, variant gaps, and regions"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "filter", "VCF filter", "soft filter"]
    RETURN_NAMES = ("filtered_vcf",)
    OUTPUT_FILENAME = "filtered.vcf.gz"
    DOCUMENTATION_URL = "https://www.htslib.org/doc/1.24/bcftools.html#filter"
    UPSTREAM_SOURCE = "vcffilter.c"
    SOURCE_REVISION = BCFTOOLS_GIT_COMMIT
    SOURCE_URL = f"https://github.com/samtools/bcftools/blob/{BCFTOOLS_GIT_COMMIT}/vcffilter.c"
    SOURCE_PATHS = ("vcffilter.c", "doc/bcftools.1")
    AUDIT_STATUS = "contract-checked-no-external-execution"
    EXIT_SEMANTICS = (
        "bcftools filter exits non-zero for malformed expressions, invalid gap/mask options, "
        "missing mask soft-filter labels, unavailable indexed random-access input, or output "
        "write failures. A zero exit is accepted only when the planned compressed VCF exists."
    )
    SNP_GAP_TYPES = ("indel", "mnp", "bnd", "other", "overlap")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        optional = dict(COMMON_FILTER_INPUTS)
        optional.update({
            "soft_filter": ("STRING", {"default": "", "description": "FILTER label, or + to append"}),
            "mode": ("STRING", {"default": "", "options": ["", "+", "x"]}),
            "set_gts": ("STRING", {"default": "", "options": ["", ".", "0"]}),
            "snp_gap": ("STRING", {"default": ""}),
            "indel_gap": ("INT", {"default": None, "min": 0}),
            "mask": ("STRING", {"default": ""}),
            "mask_file": ("FILE", {"default": ""}),
            "mask_negate": ("BOOLEAN", {"default": False}),
            "mask_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"]}),
            "threads": ("INT", {"default": 4, "min": 0}),
            "expr": ("STRING", {"default": "", "advanced": True, "description": "Compatibility alias for include"}),
            "vcf": ("VCF", {"default": "", "advanced": True, "description": "Compatibility alias for input_file"}),
        })
        return {
            "required": {"input_file": ("VCF", {"description": "VCF or BCF to filter"})},
            "optional": optional,
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _input(cls, inputs: dict[str, Any]) -> str:
        return path_value(inputs, "input_file", "vcf")

    @classmethod
    def _include(cls, inputs: dict[str, Any]) -> Any:
        return inputs.get("include") or inputs.get("expr")

    @classmethod
    def _validate_snp_gap(cls, value: Any) -> bool | str:
        if value in (None, ""):
            return True
        if not isinstance(value, str):
            return "snp_gap must be a string in INT[:TYPE,...] form"
        amount, separator, variant_types = value.partition(":")
        if not re.fullmatch(r"[0-9]+", amount):
            return "snp_gap must start with a non-negative integer"
        if separator:
            selected = variant_types.split(",")
            if not variant_types or any(item not in cls.SNP_GAP_TYPES for item in selected):
                return f"snp_gap types must be one of: {', '.join(cls.SNP_GAP_TYPES)}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        normalized = dict(inputs)
        normalized.setdefault("input_file", cls._input(inputs))
        normalized["include"] = cls._include(inputs)
        validation = BCFtoolsCommandNode.VALIDATE_INPUTS.__func__(cls, normalized)
        if validation is not True:
            return validation
        validation = require_path(normalized, "input_file")
        if validation is not True:
            return validation
        validation = validate_exclusive(normalized, "include", "exclude")
        if validation is not True:
            return validation
        if inputs.get("mask") and inputs.get("mask_file"):
            return "mask and mask_file are mutually exclusive"
        if (inputs.get("mask") or inputs.get("mask_file")) and not inputs.get("soft_filter"):
            return "soft_filter is required with mask or mask_file"
        if inputs.get("mask_negate") and not (inputs.get("mask") or inputs.get("mask_file")):
            return "mask_negate requires mask or mask_file"
        validation = validate_choice(inputs.get("mode", ""), "mode", ("", "+", "x"))
        if validation is not True:
            return validation
        validation = validate_choice(inputs.get("set_gts", ""), "set_gts", ("", ".", "0"))
        if validation is not True:
            return validation
        validation = validate_choice(
            inputs.get("mask_overlap", ""), "mask_overlap", ("", "0", "1", "2")
        )
        if validation is not True:
            return validation
        validation = cls._validate_snp_gap(inputs.get("snp_gap", ""))
        if validation is not True:
            return validation
        if inputs.get("indel_gap") not in (None, ""):
            validation = validate_number(
                inputs["indel_gap"], "indel_gap", minimum=0, integer=True
            )
            if validation is not True:
                return validation
        validation = validate_number(inputs.get("threads", 4), "threads", minimum=0, integer=True)
        if validation is not True:
            return validation
        if uses_regions(inputs):
            normalized["input_file"] = cls._input(inputs)
            validation = validate_data_index(normalized)
            if validation is not True:
                return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        command = ["bcftools", "filter"]
        add_value(command, "--include", cls._include(inputs))
        add_value(command, "--exclude", inputs.get("exclude"))
        add_value(command, "--soft-filter", inputs.get("soft_filter"))
        add_value(command, "--mode", inputs.get("mode"))
        add_value(command, "--set-GTs", inputs.get("set_gts"))
        add_value(command, "--SnpGap", inputs.get("snp_gap"))
        add_value(command, "--IndelGap", inputs.get("indel_gap"))
        mask_prefix = "^" if inputs.get("mask_negate") else ""
        if inputs.get("mask"):
            command.extend(["--mask", f"{mask_prefix}{inputs['mask']}"])
        if inputs.get("mask_file"):
            command.extend(["--mask-file", f"{mask_prefix}{inputs['mask_file']}"])
        add_value(command, "--mask-overlap", inputs.get("mask_overlap"))
        for key, flag in (
            ("regions", "--regions"),
            ("regions_file", "--regions-file"),
            ("regions_overlap", "--regions-overlap"),
            ("targets", "--targets"),
            ("targets_file", "--targets-file"),
            ("targets_overlap", "--targets-overlap"),
        ):
            add_value(command, flag, inputs.get(key))
        threads = inputs.get("threads", 4)
        if threads:
            command.extend(["--threads", str(threads)])
        add_fixed_vcf_output(command, cls, inputs)
        command.append(cls._input(inputs))
        return command


class BCFtoolsNormNode(FixedVcfOutputNode):
    """Normalize alleles and multiallelic records with documented modes."""

    NODE_ID = "bcftools_norm"
    DISPLAY_NAME = "BCFtools Norm"
    DESCRIPTION = "Left-align, atomize, deduplicate, split, or join VCF records"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "norm", "normalize VCF", "left-align indels"]
    RETURN_NAMES = ("normalized_vcf",)
    OUTPUT_FILENAME = "normalized.vcf.gz"
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#norm"
    UPSTREAM_SOURCE = "vcfnorm.c"
    RM_DUP = ("", "snps", "indels", "both", "all", "exact")
    MULTIALLELICS = ("", "-snps", "-indels", "-both", "-any", "+snps", "+indels", "+both", "+any")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        optional = dict(COMMON_FILTER_INPUTS)
        optional.update({
            "reference": ("FASTA", {"default": "", "description": "Reference used for left alignment"}),
            "reference_index": ("FASTA_INDEX", {"default": "", "description": "Exact <reference>.fai"}),
            "check_ref": ("STRING", {"default": "", "options": ["", "e", "w", "x", "s", "wx", "ws"]}),
            "atomize": ("BOOLEAN", {"default": False}),
            "atom_overlaps": ("STRING", {"default": "", "options": ["", ".", "*"]}),
            "rm_dup": ("STRING", {"default": "", "options": list(cls.RM_DUP)}),
            "multiallelics": ("STRING", {"default": "", "options": list(cls.MULTIALLELICS)}),
            "multi_overlaps": ("STRING", {"default": "", "options": ["", "0", "."]}),
            "sort": ("STRING", {"default": "pos", "options": ["pos", "lex"]}),
            "strict_filter": ("BOOLEAN", {"default": False}),
            "threads": ("INT", {"default": 4, "min": 0, "max": 128}),
            "vcf": ("VCF", {"default": "", "advanced": True}),
            "multiallelic_mode": ("STRING", {"default": "", "advanced": True}),
            "deduplicate": ("STRING", {"default": "", "advanced": True}),
        })
        return {
            "required": {"input_file": ("VCF", {"description": "VCF or BCF to normalize"})},
            "optional": optional,
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _input(cls, inputs: dict[str, Any]) -> str:
        return path_value(inputs, "input_file", "vcf")

    @classmethod
    def _multiallelics(cls, inputs: dict[str, Any]) -> str:
        value = str(inputs.get("multiallelics") or inputs.get("multiallelic_mode") or "")
        return {"split": "-both", "join": "+both", "-": "-both", "+": "+both"}.get(value, value)

    @classmethod
    def _rm_dup(cls, inputs: dict[str, Any]) -> str:
        value = str(inputs.get("rm_dup") or inputs.get("deduplicate") or "")
        return "" if value == "none" else value

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        normalized = dict(inputs)
        normalized.setdefault("input_file", cls._input(inputs))
        validation = BCFtoolsCommandNode.VALIDATE_INPUTS.__func__(cls, normalized)
        if validation is not True:
            return validation
        validation = require_path(normalized, "input_file")
        if validation is not True:
            return validation
        multiallelics = cls._multiallelics(inputs)
        validation = validate_choice(multiallelics, "multiallelics", cls.MULTIALLELICS)
        if validation is not True:
            return validation
        rm_dup = cls._rm_dup(inputs)
        validation = validate_choice(rm_dup, "rm_dup", cls.RM_DUP)
        if validation is not True:
            return validation
        if inputs.get("check_ref") and not inputs.get("reference"):
            return "check_ref requires reference"
        if inputs.get("reference"):
            validation = validate_reference_index(inputs)
            if validation is not True:
                return validation
        elif inputs.get("reference_index"):
            return "reference_index requires reference"
        if uses_regions(inputs):
            normalized["input_file"] = cls._input(inputs)
            validation = validate_data_index(normalized)
            if validation is not True:
                return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        command = ["bcftools", "norm"]
        add_value(command, "--fasta-ref", inputs.get("reference"))
        add_value(command, "--check-ref", inputs.get("check_ref"))
        add_flag(command, "--atomize", inputs.get("atomize"))
        add_value(command, "--atom-overlaps", inputs.get("atom_overlaps"))
        add_value(command, "--rm-dup", cls._rm_dup(inputs))
        add_value(command, "--multiallelics", cls._multiallelics(inputs))
        add_value(command, "--multi-overlaps", inputs.get("multi_overlaps"))
        add_value(command, "--sort", inputs.get("sort", "pos"))
        add_flag(command, "--strict-filter", inputs.get("strict_filter"))
        add_common_filters(command, inputs)
        threads = inputs.get("threads", 4)
        if threads:
            command.extend(["--threads", str(threads)])
        add_fixed_vcf_output(command, cls, inputs)
        command.append(cls._input(inputs))
        return command


class BCFtoolsViewNode(FixedVcfOutputNode):
    """Subset typed VCF output without header-only text modes."""

    NODE_ID = "bcftools_view"
    DISPLAY_NAME = "BCFtools View"
    DESCRIPTION = "Subset samples and records while retaining typed compressed VCF output"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "view", "subset VCF", "filter samples"]
    RETURN_NAMES = ("view_vcf",)
    OUTPUT_FILENAME = "view.vcf.gz"
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#view"
    UPSTREAM_SOURCE = "vcfview.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        optional = dict(COMMON_FILTER_INPUTS)
        optional.update({
            "samples": ("STRING", {"default": ""}),
            "samples_file": ("FILE", {"default": ""}),
            "force_samples": ("BOOLEAN", {"default": False}),
            "drop_genotypes": ("BOOLEAN", {"default": False}),
            "no_update": ("BOOLEAN", {"default": False}),
            "apply_filters": ("STRING", {"default": ""}),
            "types": ("STRING", {"default": ""}),
            "exclude_types": ("STRING", {"default": ""}),
            "min_alleles": ("INT", {"default": None, "min": 1}),
            "max_alleles": ("INT", {"default": None, "min": 1}),
            "min_af": ("STRING", {"default": ""}),
            "max_af": ("STRING", {"default": ""}),
            "genotype": ("STRING", {"default": ""}),
            "threads": ("INT", {"default": 4, "min": 0, "max": 128}),
        })
        return {
            "required": {"input_file": ("VCF", {"description": "VCF or BCF to subset"})},
            "optional": optional,
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = require_path(inputs, "input_file")
        if validation is not True:
            return validation
        if inputs.get("types") and inputs.get("exclude_types"):
            return "types and exclude_types are mutually exclusive"
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
        command = ["bcftools", "view"]
        add_common_filters(command, inputs, samples=True)
        add_flag(command, "--force-samples", inputs.get("force_samples"))
        add_flag(command, "--drop-genotypes", inputs.get("drop_genotypes"))
        add_flag(command, "--no-update", inputs.get("no_update"))
        for key, flag in (
            ("apply_filters", "--apply-filters"),
            ("types", "--types"),
            ("exclude_types", "--exclude-types"),
            ("min_alleles", "--min-alleles"),
            ("max_alleles", "--max-alleles"),
            ("min_af", "--min-af"),
            ("max_af", "--max-af"),
            ("genotype", "--genotype"),
        ):
            add_value(command, flag, inputs.get(key))
        threads = inputs.get("threads", 4)
        if threads:
            command.extend(["--threads", str(threads)])
        add_fixed_vcf_output(command, cls, inputs)
        command.append(str(inputs["input_file"]))
        return command


class BCFtoolsConcatNode(FixedVcfOutputNode):
    """Concatenate ordered VCF chunks with validated overlap modes."""

    NODE_ID = "bcftools_concat"
    DISPLAY_NAME = "BCFtools Concat"
    DESCRIPTION = "Concatenate two or more ordered VCF or BCF files"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "concat", "concatenate VCF", "ligate phased VCF"]
    RETURN_NAMES = ("concat_vcf",)
    OUTPUT_FILENAME = "concat.vcf.gz"
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#concat"
    UPSTREAM_SOURCE = "vcfconcat.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input_files": ("VCF_LIST", {"multiple": True, "description": "Ordered VCF or BCF chunks"})},
            "optional": {
                "input_indexes": ("VCF_INDEX", {"default": [], "multiple": True}),
                "allow_overlaps": ("BOOLEAN", {"default": False}),
                "rm_duplicates": ("BOOLEAN", {"default": False}),
                "rm_dups": ("STRING", {"default": "", "options": ["", "snps", "indels", "both", "all", "exact"]}),
                "ligate": ("BOOLEAN", {"default": False}),
                "ligate_force": ("BOOLEAN", {"default": False}),
                "ligate_warn": ("BOOLEAN", {"default": False}),
                "naive": ("BOOLEAN", {"default": False}),
                "naive_force": ("BOOLEAN", {"default": False}),
                "regions": COMMON_FILTER_INPUTS["regions"],
                "regions_file": COMMON_FILTER_INPUTS["regions_file"],
                "regions_overlap": COMMON_FILTER_INPUTS["regions_overlap"],
                "threads": ("INT", {"default": 4, "min": 0, "max": 128}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = require_paths(inputs, "input_files", minimum=2)
        if validation is not True:
            return validation
        naive = bool(inputs.get("naive") or inputs.get("naive_force"))
        ligate = bool(inputs.get("ligate") or inputs.get("ligate_force") or inputs.get("ligate_warn"))
        if naive and (ligate or inputs.get("allow_overlaps")):
            return "naive mode cannot be combined with ligation or overlap processing"
        if inputs.get("allow_overlaps") and ligate:
            return "allow_overlaps and ligate modes are mutually exclusive"
        if inputs.get("ligate_force") and inputs.get("ligate_warn"):
            return "ligate_force and ligate_warn are mutually exclusive"
        if (inputs.get("rm_duplicates") or inputs.get("rm_dups") or uses_regions(inputs)) and not inputs.get("allow_overlaps"):
            return "duplicate removal and regions require allow_overlaps"
        if uses_regions(inputs):
            validation = validate_data_indexes(inputs, data_key="input_files", index_key="input_indexes")
            if validation is not True:
                return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        command = ["bcftools", "concat"]
        add_flag(command, "--allow-overlaps", inputs.get("allow_overlaps"))
        add_flag(command, "--remove-duplicates", inputs.get("rm_duplicates"))
        add_value(command, "--rm-dups", inputs.get("rm_dups"))
        add_flag(command, "--ligate", inputs.get("ligate"))
        add_flag(command, "--ligate-force", inputs.get("ligate_force"))
        add_flag(command, "--ligate-warn", inputs.get("ligate_warn"))
        add_flag(command, "--naive", inputs.get("naive"))
        add_flag(command, "--naive-force", inputs.get("naive_force"))
        add_value(command, "--regions", inputs.get("regions"))
        add_value(command, "--regions-file", inputs.get("regions_file"))
        add_value(command, "--regions-overlap", inputs.get("regions_overlap"))
        threads = inputs.get("threads", 4)
        if threads:
            command.extend(["--threads", str(threads)])
        add_fixed_vcf_output(command, cls, inputs)
        command.extend(as_list(inputs.get("input_files")))
        return command


class BCFtoolsMergeNode(FixedVcfOutputNode):
    """Merge sample sets from multiple VCF files."""

    NODE_ID = "bcftools_merge"
    DISPLAY_NAME = "BCFtools Merge"
    DESCRIPTION = "Merge non-overlapping sample sets from multiple VCF or BCF files"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "merge", "merge samples", "multi-sample VCF"]
    RETURN_NAMES = ("merged_vcf",)
    OUTPUT_FILENAME = "merged.vcf.gz"
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#merge"
    UPSTREAM_SOURCE = "vcfmerge.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input_files": ("VCF_LIST", {"multiple": True, "description": "VCFs with distinct sample sets"})},
            "optional": {
                "input_indexes": ("VCF_INDEX", {"default": [], "multiple": True, "description": "One colocated index per input unless no_index"}),
                "no_index": ("BOOLEAN", {"default": False}),
                "force_samples": ("BOOLEAN", {"default": False}),
                "force_single": ("BOOLEAN", {"default": False}),
                "merge": ("STRING", {"default": "", "description": "Documented merge logic"}),
                "info_rules": ("STRING", {"default": ""}),
                "missing_rules": ("STRING", {"default": ""}),
                "missing_to_ref": ("BOOLEAN", {"default": False}),
                "regions": COMMON_FILTER_INPUTS["regions"],
                "regions_file": COMMON_FILTER_INPUTS["regions_file"],
                "regions_overlap": COMMON_FILTER_INPUTS["regions_overlap"],
                "threads": ("INT", {"default": 4, "min": 0, "max": 128}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = require_paths(inputs, "input_files", minimum=2)
        if validation is not True:
            return validation
        if not inputs.get("no_index"):
            validation = validate_data_indexes(inputs, data_key="input_files", index_key="input_indexes")
            if validation is not True:
                return validation
        elif uses_regions(inputs):
            return "regions require indexed inputs; disable no_index"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        command = ["bcftools", "merge"]
        add_flag(command, "--no-index", inputs.get("no_index"))
        add_flag(command, "--force-samples", inputs.get("force_samples"))
        add_flag(command, "--force-single", inputs.get("force_single"))
        add_flag(command, "--missing-to-ref", inputs.get("missing_to_ref"))
        add_value(command, "--merge", inputs.get("merge"))
        add_value(command, "--info-rules", inputs.get("info_rules"))
        add_value(command, "--missing-rules", inputs.get("missing_rules"))
        add_value(command, "--regions", inputs.get("regions"))
        add_value(command, "--regions-file", inputs.get("regions_file"))
        add_value(command, "--regions-overlap", inputs.get("regions_overlap"))
        threads = inputs.get("threads", 4)
        if threads:
            command.extend(["--threads", str(threads)])
        add_fixed_vcf_output(command, cls, inputs)
        command.extend(as_list(inputs.get("input_files")))
        return command


class BCFtoolsIsecNode(FixedVcfOutputNode):
    """Select one indexed VCF stream from an intersection or complement."""

    NODE_ID = "bcftools_isec"
    DISPLAY_NAME = "BCFtools Isec"
    DESCRIPTION = "Create a selected compressed-VCF intersection, union, or complement"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "isec", "VCF intersection", "VCF complement"]
    RETURN_NAMES = ("isec_vcf",)
    OUTPUT_FILENAME = "isec.vcf.gz"
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#isec"
    UPSTREAM_SOURCE = "vcfisec.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_files": ("VCF_LIST", {"multiple": True, "description": "Two or more indexed VCFs"}),
                "input_indexes": ("VCF_INDEX", {"multiple": True, "description": "One colocated index per VCF"}),
            },
            "optional": {
                "nfiles": ("STRING", {"default": "", "description": "[+-=]N or ~BITMAP selection"}),
                "complement": ("BOOLEAN", {"default": False}),
                "write": ("INT", {"default": 1, "min": 1}),
                "collapse": ("STRING", {"default": "none", "options": ["snps", "indels", "both", "all", "some", "none", "id"]}),
                "apply_filters": ("STRING", {"default": ""}),
                "include": COMMON_FILTER_INPUTS["include"],
                "exclude": COMMON_FILTER_INPUTS["exclude"],
                "regions": COMMON_FILTER_INPUTS["regions"],
                "regions_file": COMMON_FILTER_INPUTS["regions_file"],
                "regions_overlap": COMMON_FILTER_INPUTS["regions_overlap"],
                "targets": COMMON_FILTER_INPUTS["targets"],
                "targets_file": COMMON_FILTER_INPUTS["targets_file"],
                "targets_overlap": COMMON_FILTER_INPUTS["targets_overlap"],
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = require_paths(inputs, "input_files", minimum=2)
        if validation is not True:
            return validation
        validation = validate_data_indexes(inputs, data_key="input_files", index_key="input_indexes")
        if validation is not True:
            return validation
        write = inputs.get("write", 1)
        if isinstance(write, bool) or not isinstance(write, int) or not 1 <= write <= len(as_list(inputs.get("input_files"))):
            return "write must select exactly one existing input file"
        if inputs.get("complement") and inputs.get("nfiles"):
            return "complement and nfiles are mutually exclusive"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        input_files = as_list(inputs.get("input_files"))
        command = ["bcftools", "isec"]
        if inputs.get("complement"):
            command.append("--complement")
        else:
            command.extend(["--nfiles", str(inputs.get("nfiles") or f"={len(input_files)}")])
        command.extend(["--write", str(inputs.get("write", 1))])
        add_value(command, "--collapse", inputs.get("collapse", "none"))
        add_value(command, "--apply-filters", inputs.get("apply_filters"))
        add_common_filters(command, inputs)
        add_fixed_vcf_output(command, cls, inputs)
        command.extend(input_files)
        return command


class BCFtoolsReheaderNode(BCFtoolsCommandNode):
    """Modify a header while preserving the input VCF/BCF encoding."""

    NODE_ID = "bcftools_reheader"
    DISPLAY_NAME = "BCFtools Reheader"
    DESCRIPTION = "Replace VCF headers, sample names, or contigs without changing encoding"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "reheader", "rename samples", "replace VCF header"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("reheadered_vcf",)
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#reheader"
    UPSTREAM_SOURCE = "reheader.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input_file": (("VCF", "VCF_GZ", "BCF"), {"description": "VCF or BCF whose encoding is retained"})},
            "optional": {
                "header": ("TXT", {"default": ""}),
                "samples_file": ("TXT", {"default": ""}),
                "samples": ("STRING_LIST", {"default": [], "description": "Ordered inline sample-name list"}),
                "fai": ("FASTA_INDEX", {"default": "", "description": "FAI used to replace contig declarations"}),
                "threads": ("INT", {"default": 0, "min": 0, "max": 128}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _suffix(cls, inputs: dict[str, Any]) -> str:
        name = str(inputs.get("input_file", "")).lower()
        for suffix in (".vcf.gz", ".bcf", ".vcf"):
            if name.endswith(suffix):
                return suffix
        return ""

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        return [node_dir / f"reheadered{cls._suffix(inputs) or '.vcf.gz'}"]

    @classmethod
    def output_path(cls, inputs: dict[str, Any]) -> Path:
        return cls.output_dir(inputs) / f"reheadered{cls._suffix(inputs)}"

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = require_path(inputs, "input_file")
        if validation is not True:
            return validation
        if not cls._suffix(inputs):
            return "input_file must end in .vcf, .vcf.gz, or .bcf so encoding can be preserved"
        changes = [inputs.get("header"), inputs.get("samples_file"), as_list(inputs.get("samples")), inputs.get("fai")]
        if not any(changes):
            return "at least one of header, samples_file, samples, or fai is required"
        if inputs.get("samples_file") and inputs.get("samples"):
            return "samples_file and samples are mutually exclusive"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        command = ["bcftools", "reheader"]
        add_value(command, "--header", inputs.get("header"))
        add_value(command, "--samples-file", inputs.get("samples_file"))
        samples = ",".join(as_list(inputs.get("samples")))
        add_value(command, "--samples-list", samples)
        add_value(command, "--fai", inputs.get("fai"))
        threads = inputs.get("threads", 0)
        if threads:
            command.extend(["--threads", str(threads)])
        command.extend(["-o", str(cls.output_path(inputs)), str(inputs["input_file"])])
        return command
