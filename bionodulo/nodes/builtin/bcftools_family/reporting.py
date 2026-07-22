"""BCFtools 1.24 consensus, query, comparison, and HMM reports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import (
    COMMON_FILTER_INPUTS,
    BCFtoolsCommandNode,
    CoreBCFtoolsCommandNode,
    add_common_filters,
    add_flag,
    add_value,
    as_list,
    require_path,
    require_paths,
    uses_regions,
    validate_choice,
    validate_data_index,
    validate_data_indexes,
    validate_reference_index,
)


def _mask_replacements(value: Any) -> list[str]:
    if isinstance(value, str) and "," in value:
        return [item.strip() for item in value.split(",") if item.strip()]
    return as_list(value)


def _validate_character(value: Any, key: str, *, allow_case_modes: bool = False) -> bool | str:
    if value in (None, ""):
        return True
    rendered = str(value)
    if allow_case_modes and rendered.lower() in {"uc", "lc"}:
        return True
    if len(rendered.encode()) != 1:
        suffix = ", uc, or lc" if allow_case_modes else ""
        return f"{key} must be one single-byte character{suffix}"
    if allow_case_modes and not 32 < ord(rendered) < 127:
        return f"{key} must be uc, lc, or one printable ASCII character"
    return True


def _validate_gtcheck_selector(value: Any, key: str) -> bool | str:
    if value in (None, ""):
        return True
    rendered = str(value)
    lowered = rendered.lower()
    if not (lowered.startswith("qry:") or lowered.startswith("gt:")):
        return f"{key} must start with qry: or gt:"
    if not rendered.split(":", 1)[1]:
        return f"{key} must include a non-empty selector after its prefix"
    return True


def _gtcheck_selector_source(value: Any) -> str:
    if value in (None, ""):
        return ""
    source, separator, _ = str(value).partition(":")
    return source.lower() if separator and source.lower() in {"qry", "gt"} else ""


class BCFtoolsStatsNode(CoreBCFtoolsCommandNode):
    """Emit the native textual bcftools stats report on stdout."""

    NODE_ID = "bcftools_stats"
    DISPLAY_NAME = "BCFtools Stats"
    DESCRIPTION = "Calculate raw bcftools summary statistics for one or two VCF files"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "stats", "vcf statistics", "variant summary"]
    RETURN_TYPES = ("STATS_FILE",)
    RETURN_NAMES = ("stats",)
    OUTPUT_FILENAMES = ("stats.txt",)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#stats"
    UPSTREAM_SOURCE = "vcfstats.c"
    COLLAPSE = ("snps", "indels", "both", "all", "some", "none")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input_file": ("VCF", {"description": "Primary VCF or BCF"})},
            "optional": {
                "input_index": COMMON_FILTER_INPUTS["input_index"],
                "comparison_file": ("VCF", {"default": ""}),
                "comparison_index": ("VCF_INDEX", {"default": ""}),
                "reference": ("FASTA", {"default": ""}),
                "reference_index": ("FASTA_INDEX", {"default": ""}),
                "exons": ("FILE", {"default": "", "description": "BGZF-compressed exon intervals"}),
                "exons_index": ("VCF_INDEX", {"default": "", "description": "Colocated TBI or CSI for exons"}),
                "af_bins": ("STRING", {"default": ""}),
                "af_tag": ("STRING", {"default": ""}),
                "depth": ("STRING", {"default": ""}),
                "user_tstv": ("STRING", {"default": ""}),
                "collapse": ("STRING", {"default": "none", "options": list(cls.COLLAPSE)}),
                "apply_filters": ("STRING", {"default": ""}),
                "include": COMMON_FILTER_INPUTS["include"],
                "exclude": COMMON_FILTER_INPUTS["exclude"],
                "samples": ("STRING", {"default": ""}),
                "samples_file": ("FILE", {"default": ""}),
                "regions": COMMON_FILTER_INPUTS["regions"],
                "regions_file": COMMON_FILTER_INPUTS["regions_file"],
                "regions_overlap": COMMON_FILTER_INPUTS["regions_overlap"],
                "targets": COMMON_FILTER_INPUTS["targets"],
                "targets_file": COMMON_FILTER_INPUTS["targets_file"],
                "targets_overlap": COMMON_FILTER_INPUTS["targets_overlap"],
                "threads": ("INT", {"default": 0, "min": 0}),
            },
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
        validation = validate_choice(str(inputs.get("collapse", "none")), "collapse", cls.COLLAPSE)
        if validation is not True:
            return validation
        if inputs.get("reference"):
            validation = validate_reference_index(inputs)
            if validation is not True:
                return validation
        elif inputs.get("reference_index"):
            return "reference_index requires reference"
        if inputs.get("exons"):
            validation = validate_data_index(inputs, data_key="exons", index_key="exons_index")
            if validation is not True:
                return validation
        elif inputs.get("exons_index"):
            return "exons_index requires exons"
        if inputs.get("comparison_file"):
            validation = validate_data_index(inputs)
            if validation is not True:
                return validation
            validation = validate_data_index(inputs, data_key="comparison_file", index_key="comparison_index")
            if validation is not True:
                return validation
        elif inputs.get("comparison_index"):
            return "comparison_index requires comparison_file"
        elif uses_regions(inputs):
            validation = validate_data_index(inputs)
            if validation is not True:
                return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        command = ["bcftools", "stats"]
        add_value(command, "--fasta-ref", inputs.get("reference"))
        add_value(command, "--exons", inputs.get("exons"))
        add_value(command, "--af-bins", inputs.get("af_bins"))
        add_value(command, "--af-tag", inputs.get("af_tag"))
        add_value(command, "--depth", inputs.get("depth"))
        add_value(command, "--user-tstv", inputs.get("user_tstv"))
        add_value(command, "--collapse", inputs.get("collapse", "none"))
        add_value(command, "--apply-filters", inputs.get("apply_filters"))
        add_common_filters(command, inputs, samples=True)
        threads = inputs.get("threads", 0)
        if threads:
            command.extend(["--threads", str(threads)])
        command.append(str(inputs["input_file"]))
        if inputs.get("comparison_file"):
            command.append(str(inputs["comparison_file"]))
        return command


class BCFtoolsConsensusNode(CoreBCFtoolsCommandNode):
    """Apply an indexed variant set to a reference FASTA."""

    NODE_ID = "bcftools_consensus"
    DISPLAY_NAME = "BCFtools Consensus"
    DESCRIPTION = "Apply indexed VCF genotypes or alleles to a reference FASTA"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "consensus", "consensus FASTA", "apply variants"]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("consensus_fasta",)
    OUTPUT_FILENAMES = ("consensus.fa",)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#consensus"
    UPSTREAM_SOURCE = "consensus.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("VCF_GZ", {"description": "Indexed compressed VCF"}),
                "input_index": ("VCF_INDEX", {"description": "Colocated TBI or CSI"}),
                "reference": ("FASTA", {"description": "Reference FASTA to edit"}),
            },
            "optional": {
                "include": COMMON_FILTER_INPUTS["include"],
                "exclude": COMMON_FILTER_INPUTS["exclude"],
                "samples": ("STRING", {"default": ""}),
                "samples_file": ("FILE", {"default": ""}),
                "haplotype": ("STRING", {"default": ""}),
                "iupac_codes": ("BOOLEAN", {"default": True}),
                "masks": ("FILE", {"default": [], "multiple": True}),
                "mask_with": (
                    "STRING_LIST",
                    {"default": [], "description": "One replacement per mask, or one value reused for every mask"},
                ),
                "absent": ("STRING", {"default": ""}),
                "missing": ("STRING", {"default": ""}),
                "mark_del": ("STRING", {"default": ""}),
                "mark_ins": ("STRING", {"default": ""}),
                "mark_snv": ("STRING", {"default": ""}),
                "chain": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        outputs = [node_dir / "consensus.fa"]
        if inputs.get("chain"):
            outputs.append(node_dir / "consensus.chain")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in ("input_file", "reference"):
            validation = require_path(inputs, key)
            if validation is not True:
                return validation
        validation = validate_data_index(inputs)
        if validation is not True:
            return validation
        masks = as_list(inputs.get("masks"))
        replacements = _mask_replacements(inputs.get("mask_with"))
        if replacements and not masks:
            return "mask_with requires at least one mask"
        if len(replacements) not in {0, 1, len(masks)}:
            return "mask_with must contain one value or one value per mask"
        for replacement in replacements:
            validation = _validate_character(replacement, "mask_with", allow_case_modes=True)
            if validation is not True:
                return validation
        for key, allow_case_modes in (
            ("absent", False),
            ("missing", False),
            ("mark_del", False),
            ("mark_ins", True),
            ("mark_snv", True),
        ):
            validation = _validate_character(inputs.get(key), key, allow_case_modes=allow_case_modes)
            if validation is not True:
                return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        command = ["bcftools", "consensus", "--fasta-ref", str(inputs["reference"])]
        if inputs.get("iupac_codes", True):
            command.append("-I")
        add_value(command, "--include", inputs.get("include"))
        add_value(command, "--exclude", inputs.get("exclude"))
        add_value(command, "--samples", inputs.get("samples"))
        add_value(command, "--samples-file", inputs.get("samples_file"))
        add_value(command, "--haplotype", inputs.get("haplotype"))
        masks = as_list(inputs.get("masks"))
        replacements = _mask_replacements(inputs.get("mask_with"))
        for index, mask in enumerate(masks):
            command.extend(["--mask", mask])
            if replacements:
                replacement = replacements[0] if len(replacements) == 1 else replacements[index]
                command.extend(["--mask-with", replacement])
        for key, flag in (
            ("absent", "--absent"),
            ("missing", "--missing"),
            ("mark_del", "--mark-del"),
            ("mark_ins", "--mark-ins"),
            ("mark_snv", "--mark-snv"),
        ):
            add_value(command, flag, inputs.get(key))
        if inputs.get("chain"):
            command.extend(["--chain", str(cls.output_dir(inputs) / "consensus.chain")])
        command.append(str(inputs["input_file"]))
        return command


class BCFtoolsQueryNode(CoreBCFtoolsCommandNode):
    """Format one or more VCF files as a tabular text artifact."""

    NODE_ID = "bcftools_query"
    DISPLAY_NAME = "BCFtools Query"
    DESCRIPTION = "Extract VCF fields with a required bcftools query format string"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "query", "extract fields", "VCF to TSV"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("query_table",)
    OUTPUT_FILENAMES = ("query.tsv",)
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#query"
    UPSTREAM_SOURCE = "vcfquery.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_files": ("VCF_LIST", {"multiple": True, "description": "One or more VCF or BCF inputs"}),
                "format": ("STRING", {"description": "bcftools query format string"}),
            },
            "optional": {
                "input_indexes": ("VCF_INDEX", {"default": [], "multiple": True}),
                "include": COMMON_FILTER_INPUTS["include"],
                "exclude": COMMON_FILTER_INPUTS["exclude"],
                "samples": ("STRING", {"default": ""}),
                "samples_file": ("FILE", {"default": ""}),
                "force_samples": ("BOOLEAN", {"default": False}),
                "print_filtered": ("STRING", {"default": ""}),
                "allow_undef_tags": ("BOOLEAN", {"default": False}),
                "regions": COMMON_FILTER_INPUTS["regions"],
                "regions_file": COMMON_FILTER_INPUTS["regions_file"],
                "regions_overlap": COMMON_FILTER_INPUTS["regions_overlap"],
                "targets": COMMON_FILTER_INPUTS["targets"],
                "targets_file": COMMON_FILTER_INPUTS["targets_file"],
                "targets_overlap": COMMON_FILTER_INPUTS["targets_overlap"],
                "input_file": ("VCF", {"default": "", "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _inputs(cls, inputs: dict[str, Any]) -> list[str]:
        return as_list(inputs.get("input_files")) or as_list(inputs.get("input_file"))

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        normalized = dict(inputs)
        normalized["input_files"] = cls._inputs(inputs)
        validation = BCFtoolsCommandNode.VALIDATE_INPUTS.__func__(cls, normalized)
        if validation is not True:
            return validation
        validation = require_paths(normalized, "input_files")
        if validation is not True:
            return validation
        if not str(inputs.get("format", "")).strip():
            return "format must be non-empty"
        if len(cls._inputs(inputs)) > 1 or uses_regions(inputs):
            normalized["input_indexes"] = inputs.get("input_indexes")
            validation = validate_data_indexes(normalized, data_key="input_files", index_key="input_indexes")
            if validation is not True:
                return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        command = ["bcftools", "query", "-f", str(inputs["format"])]
        add_value(command, "--include", inputs.get("include"))
        add_value(command, "--exclude", inputs.get("exclude"))
        add_value(command, "--samples", inputs.get("samples"))
        add_value(command, "--samples-file", inputs.get("samples_file"))
        add_flag(command, "--force-samples", inputs.get("force_samples"))
        add_value(command, "--print-filtered", inputs.get("print_filtered"))
        add_flag(command, "--allow-undef-tags", inputs.get("allow_undef_tags"))
        for key, flag in (
            ("regions", "--regions"),
            ("regions_file", "--regions-file"),
            ("regions_overlap", "--regions-overlap"),
            ("targets", "--targets"),
            ("targets_file", "--targets-file"),
            ("targets_overlap", "--targets-overlap"),
        ):
            add_value(command, flag, inputs.get(key))
        command.extend(["-o", str(cls.output_dir(inputs) / "query.tsv")])
        command.extend(cls._inputs(inputs))
        return command


class BCFtoolsQueryListSamplesNode(CoreBCFtoolsCommandNode):
    """List VCF sample names without requiring an index."""

    NODE_ID = "bcftools_query_list_samples"
    DISPLAY_NAME = "BCFtools Query List Samples"
    DESCRIPTION = "List sample names from a VCF or BCF header"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "query -l", "list VCF samples"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("samples",)
    OUTPUT_FILENAMES = ("samples.tsv",)
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#query"
    UPSTREAM_SOURCE = "vcfquery.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input_file": ("VCF", {"description": "VCF or BCF header to inspect"})},
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        return require_path(inputs, "input_file")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        return ["bcftools", "query", "-l", "-o", str(cls.output_dir(inputs) / "samples.tsv"), str(inputs["input_file"])]


class BCFtoolsGTcheckNode(CoreBCFtoolsCommandNode):
    """Compare query genotypes against an optional indexed genotype panel."""

    NODE_ID = "bcftools_gtcheck"
    DISPLAY_NAME = "BCFtools GTcheck"
    DESCRIPTION = "Check sample concordance within one VCF or against a genotype VCF"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "gtcheck", "sample concordance", "genotype identity"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("gtcheck_table",)
    OUTPUT_FILENAMES = ("gtcheck.tsv",)
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#gtcheck"
    UPSTREAM_SOURCE = "vcfgtcheck.c"
    ALLOW_MIXED_SAMPLE_SELECTORS = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input_file": ("VCF", {"description": "Query VCF or BCF"})},
            "optional": {
                "input_index": COMMON_FILTER_INPUTS["input_index"],
                "genotypes": ("VCF", {"default": "", "description": "Reference genotype VCF"}),
                "genotypes_index": ("VCF_INDEX", {"default": ""}),
                "pairs": ("STRING", {"default": ""}),
                "pairs_file": ("FILE", {"default": ""}),
                "samples": ("STRING", {"default": ""}),
                "samples_file": ("FILE", {"default": ""}),
                "samples_file_source": (
                    "STRING",
                    {
                        "default": "",
                        "options": ["", "qry", "gt"],
                        "description": "Apply the staged sample file to the query or genotype VCF",
                    },
                ),
                "use": ("STRING", {"default": "", "description": "Ordered GT,PL tag preference"}),
                "include": COMMON_FILTER_INPUTS["include"],
                "exclude": COMMON_FILTER_INPUTS["exclude"],
                "regions": COMMON_FILTER_INPUTS["regions"],
                "regions_file": COMMON_FILTER_INPUTS["regions_file"],
                "regions_overlap": COMMON_FILTER_INPUTS["regions_overlap"],
                "targets": COMMON_FILTER_INPUTS["targets"],
                "targets_file": COMMON_FILTER_INPUTS["targets_file"],
                "targets_overlap": COMMON_FILTER_INPUTS["targets_overlap"],
                "homs_only": ("BOOLEAN", {"default": False}),
                "error_probability": ("INT", {"default": None}),
            },
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
        if inputs.get("pairs") and inputs.get("pairs_file"):
            return "pairs and pairs_file are mutually exclusive"
        validation = _validate_gtcheck_selector(inputs.get("samples"), "samples")
        if validation is not True:
            return validation
        samples_file = inputs.get("samples_file")
        samples_file_source = str(inputs.get("samples_file_source", "")).lower()
        if samples_file:
            if _gtcheck_selector_source(samples_file):
                return "samples_file must be a bare staged path; select qry or gt with samples_file_source"
            validation = validate_choice(samples_file_source, "samples_file_source", ("qry", "gt"))
            if validation is not True:
                return validation
        elif samples_file_source:
            return "samples_file_source requires samples_file"
        if inputs.get("samples") and inputs.get("samples_file"):
            if _gtcheck_selector_source(inputs["samples"]) == samples_file_source:
                return "samples and samples_file cannot both select the same gtcheck input"
        if (inputs.get("pairs") or inputs.get("pairs_file")) and (inputs.get("samples") or inputs.get("samples_file")):
            return "pairs and sample selectors are mutually exclusive"
        if inputs.get("pairs"):
            pairs = str(inputs["pairs"]).split(",")
            if len(pairs) % 2 or any(not sample.strip() for sample in pairs):
                return "pairs must contain complete comma-separated sample pairs"
        if inputs.get("use"):
            tags = [tag.strip().upper() for tag in str(inputs["use"]).split(",")]
            if not 1 <= len(tags) <= 2 or any(tag not in {"GT", "PL"} for tag in tags):
                return "use must contain one or two comma-separated GT or PL tags"
            if len(tags) == 2 and not inputs.get("genotypes"):
                return "two use tags require genotypes"
        if (_gtcheck_selector_source(inputs.get("samples")) == "gt" or samples_file_source == "gt") and not inputs.get(
            "genotypes"
        ):
            return "gt sample selectors require genotypes"
        if inputs.get("homs_only") and not inputs.get("genotypes"):
            return "homs_only requires genotypes"
        if inputs.get("genotypes"):
            validation = validate_data_index(inputs)
            if validation is not True:
                return validation
            validation = validate_data_index(inputs, data_key="genotypes", index_key="genotypes_index")
            if validation is not True:
                return validation
        elif inputs.get("genotypes_index"):
            return "genotypes_index requires genotypes"
        elif uses_regions(inputs):
            validation = validate_data_index(inputs)
            if validation is not True:
                return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        command = ["bcftools", "gtcheck"]
        add_value(command, "--genotypes", inputs.get("genotypes"))
        add_value(command, "--pairs", inputs.get("pairs"))
        add_value(command, "--pairs-file", inputs.get("pairs_file"))
        add_value(command, "--samples", inputs.get("samples"))
        if inputs.get("samples_file"):
            command.extend(["--samples-file", f"{str(inputs['samples_file_source']).lower()}:{inputs['samples_file']}"])
        add_value(command, "--use", inputs.get("use"))
        add_flag(command, "--homs-only", inputs.get("homs_only"))
        add_value(command, "--error-probability", inputs.get("error_probability"))
        add_common_filters(command, inputs)
        command.extend(["-o", str(cls.output_dir(inputs) / "gtcheck.tsv"), str(inputs["input_file"])])
        return command


class BCFtoolsROHNode(CoreBCFtoolsCommandNode):
    """Run the documented bcftools roh HMM and emit region records."""

    NODE_ID = "bcftools_roh"
    DISPLAY_NAME = "BCFtools RoH"
    DESCRIPTION = "Detect runs of homozygosity with the bcftools HMM"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "roh", "runs of homozygosity", "autozygosity"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("roh_table",)
    OUTPUT_FILENAMES = ("roh.tsv",)
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#roh"
    UPSTREAM_SOURCE = "vcfroh.c"
    OUTPUT_TYPES = ("s", "r", "sr")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input_file": ("VCF", {"description": "VCF with genotype likelihoods or genotypes"})},
            "optional": {
                "input_index": COMMON_FILTER_INPUTS["input_index"],
                "af_default": ("FLOAT", {"default": None, "min": 0, "max": 1}),
                "af_tag": ("STRING", {"default": ""}),
                "af_file": ("FILE", {"default": ""}),
                "estimate_af": ("STRING", {"default": ""}),
                "samples": ("STRING", {"default": ""}),
                "samples_file": ("FILE", {"default": ""}),
                "genetic_map": ("FILE", {"default": ""}),
                "rec_rate": ("FLOAT", {"default": None, "min": 0}),
                "gts_only": ("FLOAT", {"default": None}),
                "hw_to_az": ("FLOAT", {"default": None, "min": 0, "max": 1}),
                "az_to_hw": ("FLOAT", {"default": None, "min": 0, "max": 1}),
                "viterbi_training": ("FLOAT", {"default": None}),
                "skip_indels": ("BOOLEAN", {"default": False}),
                "include": COMMON_FILTER_INPUTS["include"],
                "exclude": COMMON_FILTER_INPUTS["exclude"],
                "regions": COMMON_FILTER_INPUTS["regions"],
                "regions_file": COMMON_FILTER_INPUTS["regions_file"],
                "regions_overlap": COMMON_FILTER_INPUTS["regions_overlap"],
                "targets": COMMON_FILTER_INPUTS["targets"],
                "targets_file": COMMON_FILTER_INPUTS["targets_file"],
                "targets_overlap": COMMON_FILTER_INPUTS["targets_overlap"],
                "output_type": ("STRING", {"default": "r", "options": list(cls.OUTPUT_TYPES)}),
                "threads": ("INT", {"default": 0, "min": 0}),
            },
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
        validation = validate_choice(str(inputs.get("output_type", "r")), "output_type", cls.OUTPUT_TYPES)
        if validation is not True:
            return validation
        if inputs.get("samples") and inputs.get("samples_file"):
            return "samples and samples_file are mutually exclusive"
        af_sources = sum(
            value not in (None, "")
            for value in (inputs.get("af_tag"), inputs.get("af_file"), inputs.get("estimate_af"))
        )
        if af_sources > 1:
            return "af_tag, af_file, and estimate_af are mutually exclusive"
        if inputs.get("af_file") and (inputs.get("targets") or inputs.get("targets_file")):
            return "af_file cannot be combined with targets or targets_file"
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
        command = ["bcftools", "roh"]
        for key, flag in (
            ("af_default", "--AF-dflt"),
            ("af_tag", "--AF-tag"),
            ("af_file", "--AF-file"),
            ("estimate_af", "--estimate-AF"),
            ("samples", "--samples"),
            ("samples_file", "--samples-file"),
            ("genetic_map", "--genetic-map"),
            ("rec_rate", "--rec-rate"),
            ("gts_only", "--GTs-only"),
            ("hw_to_az", "--hw-to-az"),
            ("az_to_hw", "--az-to-hw"),
            ("viterbi_training", "--viterbi-training"),
        ):
            add_value(command, flag, inputs.get(key))
        add_flag(command, "--skip-indels", inputs.get("skip_indels"))
        add_common_filters(command, inputs)
        threads = inputs.get("threads", 0)
        if threads:
            command.extend(["--threads", str(threads)])
        command.extend(
            [
                f"-O{inputs.get('output_type', 'r')}",
                "-o",
                str(cls.output_dir(inputs) / "roh.tsv"),
                str(inputs["input_file"]),
            ]
        )
        return command
