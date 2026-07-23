"""Focused lofreq node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin._variant_assembly_contracts import pin_contract

class LoFreqCallNode(CommandNode):
    """Call SNVs and indels from BAM alignments with LoFreq."""

    LEGACY_NODE_ID = "lofreq_call"
    DISPLAY_NAME = "LoFreq Call"
    REQUIRED_CONDA_PACKAGES = ["lofreq"]
    CATEGORY = "variant"
    DESCRIPTION = "Call sequence-quality-aware SNVs and indels from mapped reads using LoFreq."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "lofreq", "lofreq call", "variant caller", "low frequency variants", "SNV"]
    RETURN_TYPES = ("VCF",)
    RETURN_NAMES = ("variants",)
    REQUIRED_EXECUTABLES = ["lofreq"]
    DOCUMENTATION_URL = "http://csb5.github.io/lofreq/"
    CITATION_DOIS = ["10.1093/nar/gks918"]
    CITATION_URLS = [f"{DOI_URL}10.1093/nar/gks918"]
    CITATION_TEXT = "LoFreq: a sequence-quality aware, ultra-sensitive variant caller for high-throughput sequencing datasets."
    VERSION = "2.1.5"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = [
            "lofreq",
            "call-parallel",
            "--pp-threads",
            str(inputs.get("threads", 1)),
            "--verbose",
            "--ref",
            str(inputs.get("reference", "")),
            "--out",
            f"{out}/variants.vcf",
        ]
        variant_types = str(inputs.get("variant_types", ""))
        if variant_types:
            cmd.extend(variant_types.split())
        _add_if_value(cmd, "--bed", inputs.get("bed"))
        _add_if_value(cmd, "--min-cov", inputs.get("min_cov"))
        _add_if_value(cmd, "--max-depth", inputs.get("max_depth"))
        if inputs.get("use_orphan"):
            cmd.append("--use-orphan")
        _add_if_value(cmd, "--min-bq", inputs.get("min_bq"))
        _add_if_value(cmd, "--min-alt-bq", inputs.get("min_alt_bq"))
        _add_if_value(cmd, "--def-alt-bq", inputs.get("def_alt_bq"))
        alnquals_to_use = str(inputs.get("alnquals_to_use", ""))
        if alnquals_to_use:
            cmd.extend(alnquals_to_use.split())
        extended_baq = str(inputs.get("extended_baq", ""))
        if extended_baq:
            cmd.extend(extended_baq.split())
        _add_if_value(cmd, "--min-mq", inputs.get("min_mq"))
        if inputs.get("no_mq"):
            cmd.append("--no-mq")
        else:
            _add_if_value(cmd, "--max-mq", inputs.get("max_mq"))
        if inputs.get("src_qual"):
            cmd.append("--src-qual")
            ign_vcf = _as_list(inputs.get("ign_vcf"))
            if ign_vcf:
                cmd.extend(["--ign-vcf", ",".join(ign_vcf)])
            _add_if_value(cmd, "--def-nm-q", inputs.get("def_nm_q"))
        _add_if_value(cmd, "--min-jq", inputs.get("min_jq"))
        _add_if_value(cmd, "--min-alt-jq", inputs.get("min_alt_jq"))
        _add_if_value(cmd, "--def-alt-jq", inputs.get("def_alt_jq"))
        _add_if_value(cmd, "--sig", inputs.get("sig", 0.01))
        _add_if_value(cmd, "--bonf", inputs.get("bonf", "dynamic"))
        if inputs.get("no_default_filter"):
            cmd.append("--no-default-filter")
        cmd.append(str(inputs.get("reads", "")))
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "variants.vcf"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("BAM", {"description": "Mapped reads in coordinate-sorted BAM format"}),
                "reference": ("FASTA", {"description": "Reference genome FASTA"}),
                "variant_types": ("STRING", {"default": "", "options": ["", "--call-indels", "--call-indels --only-indels"]}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "optional": {
                "bed": ("BED", {"description": "Restrict calls to BED regions"}),
                "min_cov": ("INT", {"default": 1, "min": 1}),
                "max_depth": ("INT", {"default": 1000000, "min": 1}),
                "use_orphan": ("BOOLEAN", {"default": False, "advanced": True}),
                "min_bq": ("INT", {"default": 6, "min": 0}),
                "min_alt_bq": ("INT", {"default": 6, "min": 0}),
                "def_alt_bq": ("INT", {"default": "", "advanced": True}),
                "alnquals_to_use": ("STRING", {"default": "", "options": ["", "-A", "-B", "-A -B"], "advanced": True}),
                "extended_baq": ("STRING", {"default": "", "options": ["", "-e"], "advanced": True}),
                "min_mq": ("INT", {"default": 0, "min": 0}),
                "max_mq": ("INT", {"default": 255, "min": 0}),
                "no_mq": ("BOOLEAN", {"default": False, "advanced": True}),
                "src_qual": ("BOOLEAN", {"default": False, "advanced": True}),
                "ign_vcf": ("VCF_LIST", {"description": "Known variants to ignore for source quality", "advanced": True}),
                "def_nm_q": ("INT", {"default": -1, "advanced": True}),
                "min_jq": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "min_alt_jq": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "def_alt_jq": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "sig": ("FLOAT", {"default": 0.01, "min": 0, "max": 1}),
                "bonf": ("STRING", {"default": "dynamic"}),
                "no_default_filter": ("BOOLEAN", {"default": False, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class LoFreqAlnQualNode(CommandNode):
    """Add LoFreq base and indel alignment quality tags to reads."""

    LEGACY_NODE_ID = "lofreq_alnqual"
    DISPLAY_NAME = "LoFreq Alignment Quality"
    REQUIRED_CONDA_PACKAGES = ["lofreq"]
    CATEGORY = "variant"
    DESCRIPTION = "Compute base and indel alignment quality scores for mapped reads and store them as LoFreq BAM tags."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "lofreq",
        "lofreq alnqual",
        "alignment quality",
        "BAQ",
        "IDAQ",
        "base alignment quality",
        "indel alignment quality",
        "variant preprocessing",
    ]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("reads_with_alignment_qualities",)
    REQUIRED_EXECUTABLES = ["lofreq"]
    DOCUMENTATION_URL = "https://csb5.github.io/lofreq/commands/"
    CITATION_DOIS = ["10.1093/nar/gks918"]
    CITATION_URLS = [f"{DOI_URL}10.1093/nar/gks918"]
    CITATION_TEXT = "LoFreq: a sequence-quality aware, ultra-sensitive variant caller for high-throughput sequencing datasets."
    VERSION = "2.1.5"
    SHELL = False
    STDOUT_OUTPUT_INDEX = 0

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        alnquals_to_use = str(inputs.get("alnquals_to_use", "") or "")
        cmd = ["lofreq", "alnqual", "-b"]
        if alnquals_to_use != "-B" and not inputs.get("extended_baq", True):
            cmd.append("-e")
        if alnquals_to_use:
            cmd.extend(alnquals_to_use.split())
        if inputs.get("recompute_all"):
            cmd.append("-r")
        cmd.extend(
            [
                str(inputs.get("reads", "")),
                str(inputs.get("reference", "")),
            ]
        )
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "alnqual.bam"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("BAM", {"description": "Mapped reads in BAM format"}),
                "reference": ("FASTA", {"description": "Reference genome FASTA"}),
            },
            "optional": {
                "alnquals_to_use": (
                    "STRING",
                    {
                        "default": "",
                        "options": ["", "-A", "-B"],
                        "description": "Alignment quality scores to add: base and indel qualities, base-only, or indel-only",
                    },
                ),
                "extended_baq": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "description": "Use extended BAQ when base alignment qualities are computed",
                        "displayOptions": {"show": {"alnquals_to_use": ["", "-A"]}},
                    },
                ),
                "recompute_all": (
                    "BOOLEAN",
                    {"default": False, "description": "Overwrite existing alignment quality tags with newly computed values"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class LoFreqIndelQualNode(CommandNode):
    """Insert indel quality tags into BAM reads for LoFreq indel calling."""

    LEGACY_NODE_ID = "lofreq_indelqual"
    DISPLAY_NAME = "LoFreq Indel Quality"
    REQUIRED_CONDA_PACKAGES = ["lofreq"]
    CATEGORY = "variant"
    DESCRIPTION = "Insert indel qualities into mapped reads using uniform values or Dindel-based estimates for LoFreq indel calling."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "lofreq",
        "lofreq indelqual",
        "indel quality",
        "indel qualities",
        "Dindel",
        "BI BD tags",
        "variant preprocessing",
    ]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("reads_with_indel_qualities",)
    REQUIRED_EXECUTABLES = ["lofreq"]
    DOCUMENTATION_URL = "https://csb5.github.io/lofreq/commands/"
    CITATION_DOIS = ["10.1093/nar/gks918", "10.1101/gr.112326.110"]
    CITATION_URLS = [f"{DOI_URL}10.1093/nar/gks918", f"{DOI_URL}10.1101/gr.112326.110"]
    CITATION_TEXT = "LoFreq indel quality insertion supports Dindel-based estimates for accurate short-read indel calling."
    VERSION = "2.1.5"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = ["lofreq", "indelqual"]
        if str(inputs.get("strategy", "uniform")) == "dindel":
            cmd.extend(["--dindel", "--ref", str(inputs.get("reference", ""))])
        else:
            insertions = str(inputs.get("insertions", 30))
            deletions = str(inputs.get("deletions", "") or "")
            uniform_qualities = f"{insertions},{deletions}" if deletions else insertions
            cmd.extend(["--uniform", uniform_qualities])
        cmd.extend(["-o", f"{out}/indelqual.bam", str(inputs.get("reads", ""))])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "indelqual.bam"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("BAM", {"description": "Mapped reads in BAM format"}),
                "strategy": ("STRING", {"default": "uniform", "options": ["uniform", "dindel"], "description": "Indel quality calculation approach"}),
            },
            "optional": {
                "insertions": (
                    "INT",
                    {
                        "default": 30,
                        "min": 0,
                        "description": "Uniform insertion quality to add",
                        "displayOptions": {"show": {"strategy": ["uniform"]}},
                    },
                ),
                "deletions": (
                    "INT",
                    {
                        "default": "",
                        "min": 0,
                        "description": "Optional separate uniform deletion quality; blank reuses insertion quality",
                        "displayOptions": {"show": {"strategy": ["uniform"]}},
                    },
                ),
                "reference": (
                    "FASTA",
                    {
                        "description": "Reference genome FASTA used by Dindel-based indel quality estimation",
                        "displayOptions": {"show": {"strategy": ["dindel"]}},
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class LoFreqFilterNode(CommandNode):
    """Posteriorly filter LoFreq VCF variant calls."""

    LEGACY_NODE_ID = "lofreq_filter"
    DISPLAY_NAME = "LoFreq Filter"
    REQUIRED_CONDA_PACKAGES = ["lofreq"]
    CATEGORY = "variant"
    DESCRIPTION = "Filter LoFreq VCF variants by type, quality, coverage, allele frequency, and strand-bias evidence."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "lofreq",
        "lofreq filter",
        "lofreq strand bias filter",
        "variant filtering",
        "posterior filtering",
        "strand bias",
        "multiple testing correction",
        "VCF filter",
    ]
    RETURN_TYPES = ("VCF",)
    RETURN_NAMES = ("filtered_variants",)
    REQUIRED_EXECUTABLES = ["lofreq"]
    DOCUMENTATION_URL = "https://csb5.github.io/lofreq/commands/"
    CITATION_DOIS = ["10.1093/nar/gks918"]
    CITATION_URLS = [f"{DOI_URL}10.1093/nar/gks918"]
    CITATION_TEXT = "LoFreq filters sequence-quality-aware variant calls using configurable quality, coverage, allele-frequency, and strand-bias criteria."
    VERSION = "2.1.5"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = [
            "lofreq",
            "filter",
            "-i",
            str(inputs.get("invcf", "")),
            "--no-defaults",
            "--verbose",
        ]
        flag_or_drop = str(inputs.get("flag_or_drop", "") or "")
        if flag_or_drop:
            cmd.append(flag_or_drop)
        keep_only = str(inputs.get("keep_only", "") or "")
        if keep_only:
            cmd.append(keep_only)

        if keep_only in ("", "--only-snvs"):
            snvqual_filter = str(inputs.get("snvqual_filter", "no"))
            if snvqual_filter == "min-phred":
                _add_if_value(cmd, "-Q", inputs.get("snvqual_thresh", 0))
            elif snvqual_filter == "mtc":
                _add_if_value(cmd, "-q", inputs.get("snvqual_mtc", "bonf"))
                _add_if_value(cmd, "-r", inputs.get("snvqual_alpha", 1))
                _add_if_value(cmd, "-s", inputs.get("snvqual_ntests", 1))

        if keep_only in ("", "--only-indels"):
            indelqual_filter = str(inputs.get("indelqual_filter", "no"))
            if indelqual_filter == "min-phred":
                _add_if_value(cmd, "-K", inputs.get("indelqual_thresh", 0))
            elif indelqual_filter == "mtc":
                _add_if_value(cmd, "-k", inputs.get("indelqual_mtc", "bonf"))
                _add_if_value(cmd, "-l", inputs.get("indelqual_alpha", 1))
                _add_if_value(cmd, "-m", inputs.get("indelqual_ntests", 1))

        _add_if_value(cmd, "-v", inputs.get("cov_min", 10))
        _add_if_value(cmd, "-V", inputs.get("cov_max", 0))
        _add_if_value(cmd, "-a", inputs.get("af_min", 0))
        _add_if_value(cmd, "-A", inputs.get("af_max", 0))

        strand_bias = str(inputs.get("strand_bias", "mtc"))
        if strand_bias == "max-phred":
            _add_if_value(cmd, "-B", inputs.get("sb_thresh", 0))
        elif strand_bias == "mtc":
            _add_if_value(cmd, "-b", inputs.get("sb_mtc", "fdr"))
            _add_if_value(cmd, "-c", inputs.get("sb_alpha", 0.001))
        if strand_bias != "no":
            if not inputs.get("sb_compound", True):
                cmd.append("--sb-no-compound")
            if inputs.get("sb_indels"):
                cmd.append("--sb-incl-indels")

        cmd.extend(["-o", f"{out}/filtered.vcf"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "filtered.vcf"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "invcf": ("VCF", {"description": "VCF or bgzipped VCF variants to filter"}),
                "keep_only": ("STRING", {"default": "", "options": ["", "--only-snvs", "--only-indels"], "description": "Variant types to retain"}),
            },
            "optional": {
                "snvqual_filter": (
                    "STRING",
                    {
                        "default": "no",
                        "options": ["no", "min-phred", "mtc"],
                        "description": "SNV quality filter mode",
                        "displayOptions": {"show": {"keep_only": ["", "--only-snvs"]}},
                    },
                ),
                "snvqual_thresh": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "description": "Minimum SNV QUAL value",
                        "displayOptions": {"show": {"snvqual_filter": ["min-phred"]}},
                    },
                ),
                "snvqual_alpha": (
                    "FLOAT",
                    {
                        "default": 1,
                        "min": 0,
                        "max": 1,
                        "description": "Multiple-testing corrected SNV p-value threshold",
                        "displayOptions": {"show": {"snvqual_filter": ["mtc"]}},
                    },
                ),
                "snvqual_mtc": (
                    "STRING",
                    {
                        "default": "bonf",
                        "options": ["bonf", "holm", "fdr"],
                        "description": "SNV multiple testing correction method",
                        "displayOptions": {"show": {"snvqual_filter": ["mtc"]}},
                    },
                ),
                "snvqual_ntests": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "description": "Estimated number of SNV tests performed",
                        "displayOptions": {"show": {"snvqual_filter": ["mtc"]}},
                    },
                ),
                "indelqual_filter": (
                    "STRING",
                    {
                        "default": "no",
                        "options": ["no", "min-phred", "mtc"],
                        "description": "Indel quality filter mode",
                        "displayOptions": {"show": {"keep_only": ["", "--only-indels"]}},
                    },
                ),
                "indelqual_thresh": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "description": "Minimum indel QUAL value",
                        "displayOptions": {"show": {"indelqual_filter": ["min-phred"]}},
                    },
                ),
                "indelqual_alpha": (
                    "FLOAT",
                    {
                        "default": 1,
                        "min": 0,
                        "max": 1,
                        "description": "Multiple-testing corrected indel p-value threshold",
                        "displayOptions": {"show": {"indelqual_filter": ["mtc"]}},
                    },
                ),
                "indelqual_mtc": (
                    "STRING",
                    {
                        "default": "bonf",
                        "options": ["bonf", "holm", "fdr"],
                        "description": "Indel multiple testing correction method",
                        "displayOptions": {"show": {"indelqual_filter": ["mtc"]}},
                    },
                ),
                "indelqual_ntests": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "description": "Estimated number of indel tests performed",
                        "displayOptions": {"show": {"indelqual_filter": ["mtc"]}},
                    },
                ),
                "cov_min": ("INT", {"default": 10, "min": 0, "description": "Minimum depth at variant sites"}),
                "cov_max": ("INT", {"default": 0, "min": 0, "description": "Maximum depth at variant sites; 0 leaves the upper bound open"}),
                "af_min": ("FLOAT", {"default": 0, "min": 0, "max": 1, "description": "Minimum allele frequency"}),
                "af_max": ("FLOAT", {"default": 0, "min": 0, "max": 1, "description": "Maximum allele frequency; 0 leaves the upper bound open"}),
                "strand_bias": (
                    "STRING",
                    {
                        "default": "mtc",
                        "options": ["no", "max-phred", "mtc"],
                        "description": "Strand-bias filter mode",
                    },
                ),
                "sb_thresh": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "description": "Maximum strand-bias phred value",
                        "displayOptions": {"show": {"strand_bias": ["max-phred"]}},
                    },
                ),
                "sb_alpha": (
                    "FLOAT",
                    {
                        "default": 0.001,
                        "min": 0,
                        "max": 1,
                        "description": "Multiple-testing corrected strand-bias p-value threshold",
                        "displayOptions": {"show": {"strand_bias": ["mtc"]}},
                    },
                ),
                "sb_mtc": (
                    "STRING",
                    {
                        "default": "fdr",
                        "options": ["bonf", "holm", "fdr"],
                        "description": "Strand-bias multiple testing correction method",
                        "displayOptions": {"show": {"strand_bias": ["mtc"]}},
                    },
                ),
                "sb_compound": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "description": "Use compound strand-bias filtering",
                        "displayOptions": {"hide": {"strand_bias": ["no"]}},
                    },
                ),
                "sb_indels": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Apply strand-bias filtering to indels",
                        "displayOptions": {"hide": {"strand_bias": ["no"]}},
                    },
                ),
                "flag_or_drop": (
                    "STRING",
                    {
                        "default": "",
                        "options": ["", "--print-all"],
                        "description": "Drop failing variants or keep them with FILTER annotations",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class LoFreqViterbiNode(CommandNode):
    """Realign mapped reads probabilistically with LoFreq viterbi."""

    LEGACY_NODE_ID = "lofreq_viterbi"
    DISPLAY_NAME = "LoFreq Viterbi Realignment"
    REQUIRED_CONDA_PACKAGES = ["lofreq", "samtools"]
    CATEGORY = "variant"
    DESCRIPTION = "Probabilistically realign mapped Illumina reads with LoFreq viterbi and emit a coordinate-sorted BAM."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "lofreq",
        "lofreq viterbi",
        "realign reads",
        "read realignment",
        "Viterbi realignment",
        "mapping error correction",
        "variant preprocessing",
    ]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("realigned_reads",)
    REQUIRED_EXECUTABLES = ["lofreq", "samtools"]
    DOCUMENTATION_URL = "https://csb5.github.io/lofreq/commands/"
    CITATION_DOIS = ["10.1093/nar/gks918"]
    CITATION_URLS = [f"{DOI_URL}10.1093/nar/gks918"]
    CITATION_TEXT = "LoFreq viterbi performs probabilistic realignment of mapped reads to correct mapping errors before variant calling."
    VERSION = "2.1.5"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        replace_bq2 = str(inputs.get("replace_bq2", "keep"))
        defqual = {"keep": 2, "dynamic": -1}.get(replace_bq2, inputs.get("defqual", 2))
        cmd = [
            "lofreq",
            "viterbi",
            "--ref",
            str(inputs.get("reference", "")),
        ]
        if inputs.get("keepflags"):
            cmd.append("--keepflags")
        cmd.extend(
            [
                "--defqual",
                str(defqual),
                "--out",
                f"{out}/tmp.bam",
                str(inputs.get("reads", "")),
                "&&",
                "samtools",
                "sort",
                "--no-PG",
                "-T",
                "${TMPDIR:-.}",
                "-@",
                str(inputs.get("threads", 1)),
                "-O",
                "BAM",
                "-o",
                f"{out}/realigned.bam",
                f"{out}/tmp.bam",
            ]
        )
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "realigned.bam"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("BAM", {"description": "Mapped reads in BAM format to realign"}),
                "reference": ("FASTA", {"description": "Reference genome FASTA"}),
            },
            "optional": {
                "keepflags": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Keep MC, MD, NM, and A tags instead of resetting alignment-dependent values",
                    },
                ),
                "replace_bq2": (
                    "STRING",
                    {
                        "default": "keep",
                        "options": ["keep", "dynamic", "fixed"],
                        "description": "How to handle Illumina pre-1.8 base qualities of 2",
                    },
                ),
                "defqual": (
                    "INT",
                    {
                        "default": 2,
                        "min": 0,
                        "description": "Fixed replacement quality for bases with quality 2",
                        "displayOptions": {"show": {"replace_bq2": ["fixed"]}},
                    },
                ),
                "threads": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "max": 128,
                        "display": "slider",
                        "description": "Threads for samtools sort after realignment",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

pin_contract(LoFreqCallNode)
pin_contract(LoFreqAlnQualNode)
pin_contract(LoFreqIndelQualNode)
pin_contract(LoFreqFilterNode)
pin_contract(LoFreqViterbiNode)

__all__ = ['LoFreqCallNode', 'LoFreqAlnQualNode', 'LoFreqIndelQualNode', 'LoFreqFilterNode', 'LoFreqViterbiNode']
