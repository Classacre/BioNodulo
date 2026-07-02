"""BioNodulo built-in wrapped tool nodes split by tool family."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

class LoFreqCallNode(CommandNode):
    """Call SNVs and indels from BAM alignments with LoFreq."""

    NODE_ID = "lofreq_call"
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

    NODE_ID = "lofreq_alnqual"
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
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        alnquals_to_use = str(inputs.get("alnquals_to_use", "") or "")
        cmd = [
            "lofreq",
            "alnqual",
            "-b",
            "" if alnquals_to_use == "-B" or inputs.get("extended_baq", True) else "-e",
        ]
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
        _add_shell_redirect(cmd, f"{out}/alnqual.bam")
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

    NODE_ID = "lofreq_indelqual"
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

    NODE_ID = "lofreq_filter"
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

    NODE_ID = "lofreq_viterbi"
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

class FreyjaVariantsNode(CommandNode):
    """Call SARS-CoV-2 variants and sequencing depths for Freyja demixing."""

    NODE_ID = "freyja_variants"
    DISPLAY_NAME = "Freyja Variants"
    REQUIRED_CONDA_PACKAGES = ["freyja"]
    CATEGORY = "variant"
    DESCRIPTION = "Call variants and genome-wide sequencing depths from aligned viral reads for Freyja demixing."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Freyja",
        "freyja variants",
        "wastewater sequencing",
        "lineage abundance",
        "SARS-CoV-2 variants",
        "sequencing depth",
    ]
    RETURN_TYPES = ("TSV", "TSV")
    RETURN_NAMES = ("variants", "depths")
    REQUIRED_EXECUTABLES = ["freyja"]
    DOCUMENTATION_URL = "https://github.com/andersen-lab/Freyja"
    CITATION_DOIS = ["10.1038/s41586-022-05049-6"]
    CITATION_URLS = [f"{DOI_URL}10.1038/s41586-022-05049-6"]
    CITATION_TEXT = "Wastewater sequencing reveals early cryptic SARS-CoV-2 variant transmission."
    VERSION = "2.0.1"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        return [
            "freyja",
            "variants",
            str(inputs.get("bam_file", "")),
            "--variants",
            f"{out}/variants.tsv",
            "--depths",
            f"{out}/depths.tsv",
            "--ref",
            str(inputs.get("ref_file", "")),
        ]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "variants.tsv", out / "depths.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam_file": ("BAM", {"description": "BAM file aligned to the same reference used for variant calling"}),
                "ref_file": ("FASTA", {"description": "Reference FASTA used for alignment"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class FreyjaDemixNode(CommandNode):
    """Estimate lineage abundances from Freyja variant and depth tables."""

    NODE_ID = "freyja_demix"
    DISPLAY_NAME = "Freyja Demix"
    REQUIRED_CONDA_PACKAGES = ["freyja", "sed"]
    CATEGORY = "variant"
    DESCRIPTION = "Estimate mixed viral lineage abundances from Freyja variant calls and sequencing depths."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Freyja",
        "freyja demix",
        "lineage abundances",
        "wastewater variants",
        "deconvolution",
        "UShER barcodes",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("abundances",)
    REQUIRED_EXECUTABLES = ["freyja", "sed"]
    DOCUMENTATION_URL = "https://github.com/andersen-lab/Freyja"
    CITATION_DOIS = ["10.1038/s41586-022-05049-6"]
    CITATION_URLS = [f"{DOI_URL}10.1038/s41586-022-05049-6"]
    CITATION_TEXT = "Wastewater sequencing reveals early cryptic SARS-CoV-2 variant transmission."
    VERSION = "2.0.1"
    SHELL = True

    @classmethod
    def _sample_name(cls, inputs: dict[str, Any]) -> str:
        if str(inputs.get("sample_name_source", "auto")) == "manual":
            return str(inputs.get("sample_name", "sample") or "sample")
        return Path(str(inputs.get("variants_in", "sample.tsv") or "sample.tsv")).name

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        sample_name = cls._sample_name(inputs)
        if str(inputs.get("sample_name_source", "auto")) == "manual":
            ext = Path(str(inputs.get("variants_in", ""))).suffix.lstrip(".") or "tsv"
            staged_name = f"{_safe_identifier(sample_name)}.{ext}"
        else:
            staged_name = _safe_name(sample_name)
        staged_variants = f"{out}/{staged_name}"
        cmd: list[str] = []
        if str(inputs.get("barcodes_source", "repo")) == "custom":
            cmd.extend(["ln", "-sf", str(inputs.get("usher_barcodes", "")), f"{out}/usher_barcodes.csv", "&&"])
        cmd.extend([
            "ln",
            "-sf",
            str(inputs.get("variants_in", "")),
            staged_variants,
            "&&",
            "freyja",
            "demix",
            staged_variants,
            str(inputs.get("depth_file", "")),
        ])
        _add_if_value(cmd, "--eps", inputs.get("eps"))
        _add_if_value(cmd, "--meta", inputs.get("meta"))
        if inputs.get("confirmedonly"):
            cmd.append("--confirmedonly")
        if inputs.get("wgisaid"):
            cmd.append("--wgisaid")
        if str(inputs.get("barcodes_source", "repo")) == "custom":
            cmd.extend(["--barcodes", f"{out}/usher_barcodes.csv"])
        cmd.extend([
            "--covcut",
            str(inputs.get("depth_cutoff", 10)),
            "--output",
            f"{out}/abundances_raw.tsv",
            "&&",
            "sed",
            f"s/{staged_name}/{sample_name}/",
            f"{out}/abundances_raw.tsv",
            ">",
            f"{out}/abundances.tsv",
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "abundances.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "variants_in": ("TSV", {"description": "Freyja variants TSV or compatible VCF/tabular variant calls"}),
                "depth_file": ("TSV", {"description": "Genome-wide sequencing depth table"}),
            },
            "optional": {
                "sample_name_source": ("STRING", {"default": "auto", "options": ["auto", "manual"], "description": "Use input filename or explicit sample name"}),
                "sample_name": (
                    "STRING",
                    {
                        "default": "",
                        "description": "Sample name to write into the demixed abundance table",
                        "displayOptions": {"show": {"sample_name_source": ["manual"]}},
                    },
                ),
                "barcodes_source": ("STRING", {"default": "repo", "options": ["repo", "custom"], "description": "Use Freyja's bundled or a provided UShER barcode table"}),
                "usher_barcodes": (
                    "CSV",
                    {
                        "description": "Custom UShER barcodes CSV",
                        "displayOptions": {"show": {"barcodes_source": ["custom"]}},
                    },
                ),
                "meta": ("JSON", {"default": "", "description": "Optional custom lineage metadata JSON"}),
                "eps": ("FLOAT", {"default": "", "min": 0, "description": "Minimum lineage abundance to include"}),
                "confirmedonly": ("BOOLEAN", {"default": False, "description": "Remove unconfirmed lineages"}),
                "wgisaid": ("BOOLEAN", {"default": False, "description": "Use the larger non-public GISAID lineage library"}),
                "depth_cutoff": ("INT", {"default": 10, "min": 0, "description": "Depth cutoff for coverage estimate"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class FreyjaBootNode(CommandNode):
    """Bootstrap Freyja lineage-abundance estimates."""

    NODE_ID = "freyja_boot"
    DISPLAY_NAME = "Freyja Boot"
    REQUIRED_CONDA_PACKAGES = ["freyja"]
    CATEGORY = "variant"
    DESCRIPTION = "Bootstrap Freyja lineage abundances and optionally emit lineage and summary boxplots."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Freyja",
        "freyja boot",
        "bootstrap lineages",
        "lineage uncertainty",
        "boxplot",
        "wastewater variants",
    ]
    RETURN_TYPES = ("CSV", "CSV", "PDF", "PDF")
    RETURN_NAMES = ("boot_lineages", "boot_summarized", "boot_lineages_plot", "boot_summarized_plot")
    REQUIRED_EXECUTABLES = ["freyja"]
    DOCUMENTATION_URL = "https://github.com/andersen-lab/Freyja"
    CITATION_DOIS = ["10.1038/s41586-022-05049-6"]
    CITATION_URLS = [f"{DOI_URL}10.1038/s41586-022-05049-6"]
    CITATION_TEXT = "Wastewater sequencing reveals early cryptic SARS-CoV-2 variant transmission."
    VERSION = "2.0.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd: list[str] = []
        if str(inputs.get("barcodes_source", "repo")) == "custom":
            cmd.extend(["ln", "-sf", str(inputs.get("usher_barcodes", "")), f"{out}/usher_barcodes.csv", "&&"])
        cmd.extend([
            "freyja",
            "boot",
            str(inputs.get("variants_file", "")),
            str(inputs.get("depth_file", "")),
        ])
        _add_if_value(cmd, "--eps", inputs.get("eps"))
        _add_if_value(cmd, "--meta", inputs.get("meta"))
        if inputs.get("confirmedonly"):
            cmd.append("--confirmedonly")
        cmd.extend([
            "--pathogen",
            str(inputs.get("pathogen", "SARS-CoV-2")),
            "--nt",
            f"${{GALAXY_SLOTS:-{inputs.get('threads', 4)}}}",
        ])
        _add_if_value(cmd, "--nb", inputs.get("nb"))
        cmd.extend(["--output_base", f"{out}/boot_output"])
        if str(inputs.get("barcodes_source", "repo")) == "custom":
            cmd.extend(["--barcodes", f"{out}/usher_barcodes.csv"])
        if inputs.get("boxplot_pdf"):
            cmd.extend(["--boxplot", "pdf"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "boot_output_lineages.csv", out / "boot_output_summarized.csv"]
        if inputs.get("boxplot_pdf"):
            outputs.extend([out / "boot_output_lineages.pdf", out / "boot_output_summarized.pdf"])
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "variants_file": ("TSV", {"description": "Freyja variants TSV or compatible VCF/tabular variant calls"}),
                "depth_file": ("TSV", {"description": "Genome-wide sequencing depth table"}),
            },
            "optional": {
                "barcodes_source": ("STRING", {"default": "repo", "options": ["repo", "custom"], "description": "Use Freyja's bundled or a provided UShER barcode table"}),
                "usher_barcodes": (
                    "CSV",
                    {
                        "description": "Custom UShER barcodes CSV",
                        "displayOptions": {"show": {"barcodes_source": ["custom"]}},
                    },
                ),
                "meta": ("JSON", {"default": "", "description": "Optional custom lineage metadata JSON"}),
                "eps": ("FLOAT", {"default": "", "min": 0, "description": "Minimum lineage abundance to include"}),
                "confirmedonly": ("BOOLEAN", {"default": False, "description": "Remove unconfirmed lineages"}),
                "pathogen": (
                    "STRING",
                    {
                        "default": "SARS-CoV-2",
                        "options": ["SARS-CoV-2", "MPXV", "H5NX", "H1N1pdm", "FLU-B-VIC", "MEASLESN450", "MEASLES", "RSVa", "RSVb"],
                        "description": "Pathogen barcode set to use",
                    },
                ),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
                "nb": ("INT", {"default": "", "min": 1, "description": "Optional number of bootstraps"}),
                "boxplot_pdf": ("BOOLEAN", {"default": False, "description": "Generate lineage and summarized boxplot PDFs"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class FreyjaAggregatePlotNode(CommandNode):
    """Aggregate Freyja demixing results and generate plot/dashboard reports."""

    NODE_ID = "freyja_aggregate_plot"
    DISPLAY_NAME = "Freyja Aggregate Plot"
    REQUIRED_CONDA_PACKAGES = ["freyja"]
    CATEGORY = "variant"
    DESCRIPTION = "Aggregate Freyja demixing outputs and create lineage abundance dashboard or PDF plots."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Freyja",
        "freyja aggregate",
        "freyja plot",
        "freyja dash",
        "lineage abundance dashboard",
        "wastewater visualization",
    ]
    RETURN_TYPES = ("TSV", "HTML_REPORT", "PDF")
    RETURN_NAMES = ("aggregated", "abundances_dashboard", "abundances_plot")
    REQUIRED_EXECUTABLES = ["freyja"]
    DOCUMENTATION_URL = "https://github.com/andersen-lab/Freyja"
    CITATION_DOIS = ["10.1038/s41586-022-05049-6"]
    CITATION_URLS = [f"{DOI_URL}10.1038/s41586-022-05049-6"]
    CITATION_TEXT = "Wastewater sequencing reveals early cryptic SARS-CoV-2 variant transmission."
    VERSION = "2.0.1"
    SHELL = True

    @classmethod
    def _aggregated_input(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        if str(inputs.get("aggregation_mode", "aggregate")) == "aggregate":
            return f"{out}/aggregated.tsv"
        return str(inputs.get("tsv_aggregated", ""))

    @classmethod
    def _add_aggregate_command(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        out = _out(inputs)
        if str(inputs.get("aggregation_mode", "aggregate")) != "aggregate":
            return
        demix_dir = f"{out}/demix_outputs"
        cmd.extend(["mkdir", "-p", demix_dir])
        for demix_file in _as_list(inputs.get("demix_file")):
            cmd.extend(["&&", "ln", "-sf", demix_file, f"{demix_dir}/{_safe_name(demix_file)}"])
        cmd.extend(["&&", "freyja", "aggregate", demix_dir, "--output", f"{out}/aggregated.tsv"])

    @classmethod
    def _add_dash_command(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        out = _out(inputs)
        aggregated = cls._aggregated_input(inputs)
        if cmd:
            cmd.append("&&")
        cmd.extend([
            "printf",
            "%s",
            str(inputs.get("plot_title", "")),
            ">",
            f"{out}/plot_title.txt",
            "&&",
            "printf",
            "%s",
            str(inputs.get("plot_intro", "")),
            ">",
            f"{out}/plot_intro.txt",
            "&&",
            "freyja",
            "dash",
            "--mincov",
            str(inputs.get("mincov", 60)),
            aggregated,
            str(inputs.get("csv_meta", "")),
            f"{out}/plot_title.txt",
            f"{out}/plot_intro.txt",
            "--output",
            f"{out}/abundances_dashboard.html",
        ])

    @classmethod
    def _add_plot_command(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        out = _out(inputs)
        aggregated = cls._aggregated_input(inputs)
        if cmd:
            cmd.append("&&")
        cmd.extend(["freyja", "plot"])
        if inputs.get("lineages"):
            cmd.append("--lineages")
        cmd.extend([
            "--mincov",
            str(inputs.get("mincov", 60)),
            aggregated,
            "--output",
            f"{out}/abundances_plot.pdf",
        ])
        if str(inputs.get("metadata_mode", "provided")) != "none" and inputs.get("csv_meta"):
            cmd.extend(["--times", str(inputs.get("csv_meta"))])
            interval = str(inputs.get("interval", "MS"))
            if interval == "MS":
                cmd.extend(["--interval", "MS"])
            else:
                cmd.extend(["--interval", "D", "--windowsize", "70"])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd: list[str] = []
        cls._add_aggregate_command(cmd, inputs)
        plot_format = str(inputs.get("plot_format", "none"))
        if plot_format in {"dash", "plot_and_dash"}:
            cls._add_dash_command(cmd, inputs)
        if plot_format in {"plot", "plot_and_dash"}:
            cls._add_plot_command(cmd, inputs)
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs: list[Path] = []
        if str(inputs.get("aggregation_mode", "aggregate")) == "aggregate":
            outputs.append(out / "aggregated.tsv")
        plot_format = str(inputs.get("plot_format", "none"))
        if plot_format in {"dash", "plot_and_dash"}:
            outputs.append(out / "abundances_dashboard.html")
        if plot_format in {"plot", "plot_and_dash"}:
            outputs.append(out / "abundances_plot.pdf")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "aggregation_mode": ("STRING", {"default": "aggregate", "options": ["aggregate", "provided"], "description": "Aggregate demix outputs or use an existing aggregate table"}),
                "plot_format": ("STRING", {"default": "none", "options": ["none", "plot", "dash", "plot_and_dash"], "description": "Reports to generate"}),
            },
            "optional": {
                "demix_file": (
                    "TSV_LIST",
                    {
                        "default": [],
                        "description": "One or more Freyja demix abundance tables",
                        "displayOptions": {"show": {"aggregation_mode": ["aggregate"]}},
                    },
                ),
                "tsv_aggregated": (
                    "TSV",
                    {
                        "description": "Existing Freyja aggregate table",
                        "displayOptions": {"show": {"aggregation_mode": ["provided"]}},
                    },
                ),
                "csv_meta": ("CSV", {"default": "", "description": "Sample metadata CSV for plot or dashboard output"}),
                "plot_title": ("STRING", {"default": "", "description": "Dashboard title"}),
                "plot_intro": ("STRING", {"default": "", "description": "Dashboard introduction"}),
                "lineages": ("BOOLEAN", {"default": False, "description": "Use lineage-specific breakdown in the plot"}),
                "mincov": ("FLOAT", {"default": 60, "min": 0, "max": 100, "description": "Minimum genome coverage percentage"}),
                "metadata_mode": ("STRING", {"default": "provided", "options": ["provided", "none"], "description": "Whether plot metadata is provided"}),
                "interval": ("STRING", {"default": "MS", "options": ["MS", "D"], "description": "Plot date binning interval"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class PreseqCCurveNode(CommandNode):
    """Estimate sequencing-library complexity curves with preseq c_curve."""

    NODE_ID = "preseq_c_curve"
    DISPLAY_NAME = "Preseq c_curve"
    REQUIRED_CONDA_PACKAGES = ["preseq"]
    CATEGORY = "qc"
    DESCRIPTION = "Estimate a sequencing library complexity curve from a coordinate-sorted BAM file."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Preseq",
        "preseq c_curve",
        "library complexity",
        "sequencing saturation",
        "distinct reads",
        "duplicate complexity",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("complexity_curve",)
    REQUIRED_EXECUTABLES = ["preseq"]
    DOCUMENTATION_URL = "https://smithlabresearch.org/software/preseq/"
    CITATION_DOIS = ["10.1038/nmeth.2375"]
    CITATION_URLS = [f"{DOI_URL}10.1038/nmeth.2375"]
    CITATION_TEXT = "Predicting the molecular complexity of sequencing libraries."
    VERSION = "3.2.0"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        staged_bam = f"{out}/input.bam"
        cmd = [
            "ln",
            "-sf",
            str(inputs.get("input_bam", "")),
            staged_bam,
            "&&",
            "preseq",
            "c_curve",
            "-B",
            staged_bam,
        ]
        if inputs.get("verbose"):
            cmd.append("-v")
        cmd.extend(["-s", str(inputs.get("step_size", 1000))])
        _add_if_value(cmd, "-l", inputs.get("max_read_len"))
        cmd.extend(["-o", f"{out}/complexity_curve.tsv"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "complexity_curve.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bam": ("BAM", {"description": "Coordinate-sorted BAM file"}),
                "step_size": ("INT", {"default": 1000, "min": 100, "description": "Step size for complexity curve calculation"}),
            },
            "optional": {
                "max_read_len": ("INT", {"default": "", "min": 1, "description": "Optional maximum read length to consider"}),
                "verbose": ("BOOLEAN", {"default": False, "description": "Print verbose preseq diagnostics"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class PreseqLCExtrapNode(CommandNode):
    """Extrapolate sequencing-library yield curves with preseq lc_extrap."""

    NODE_ID = "preseq_lc_extrap"
    DISPLAY_NAME = "Preseq lc_extrap"
    REQUIRED_CONDA_PACKAGES = ["preseq"]
    CATEGORY = "qc"
    DESCRIPTION = "Predict additional distinct reads from deeper sequencing of a coordinate-sorted BAM library."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Preseq",
        "preseq lc_extrap",
        "yield extrapolation",
        "library complexity",
        "future sequencing",
        "distinct read yield",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("yield_extrapolation",)
    REQUIRED_EXECUTABLES = ["preseq"]
    DOCUMENTATION_URL = "https://smithlabresearch.org/software/preseq/"
    CITATION_DOIS = ["10.1038/nmeth.2375"]
    CITATION_URLS = [f"{DOI_URL}10.1038/nmeth.2375"]
    CITATION_TEXT = "Predicting the molecular complexity of sequencing libraries."
    VERSION = "3.2.0"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        staged_bam = f"{out}/input.bam"
        cmd = [
            "ln",
            "-sf",
            str(inputs.get("input_bam", "")),
            staged_bam,
            "&&",
            "preseq",
            "lc_extrap",
            "-B",
            staged_bam,
        ]
        if inputs.get("verbose"):
            cmd.append("-v")
        cmd.extend([
            "-e",
            str(inputs.get("extrap_limit", 10000000)),
            "-s",
            str(inputs.get("step_size", 100000)),
            "-o",
            f"{out}/yield_extrapolation.tsv",
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "yield_extrapolation.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bam": ("BAM", {"description": "Coordinate-sorted BAM file"}),
                "extrap_limit": ("INT", {"default": 10000000, "min": 1, "description": "Total reads to extrapolate to"}),
                "step_size": ("INT", {"default": 100000, "min": 1, "description": "Step size for yield extrapolation"}),
            },
            "optional": {
                "verbose": ("BOOLEAN", {"default": False, "description": "Print verbose preseq diagnostics"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class ABySSPENode(CommandNode):
    """Assemble reads with the ABySS paired-end pipeline."""

    NODE_ID = "abyss_pe"
    DISPLAY_NAME = "ABySS"
    REQUIRED_CONDA_PACKAGES = ["abyss", "bwa"]
    CATEGORY = "assembly"
    DESCRIPTION = "Run the ABySS de novo assembler pipeline for paired-end, mate-pair, single-end, or long-read libraries."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ABySS",
        "abyss-pe",
        "de novo assembler",
        "short read assembly",
        "paired-end assembly",
        "genome assembler",
    ]
    RETURN_TYPES = ("FASTA", "FASTA", "FASTA", "FASTA", "FASTA", "TSV")
    RETURN_NAMES = ("unitigs", "contigs", "scaffolds", "long_scaffolds", "indels", "stats")
    REQUIRED_EXECUTABLES = ["abyss-pe"]
    DOCUMENTATION_URL = "https://github.com/bcgsc/abyss"
    CITATION_DOIS = ["10.1101/gr.214346.116", "10.1101/gr.089532.108"]
    CITATION_URLS = [f"{DOI_URL}10.1101/gr.214346.116", f"{DOI_URL}10.1101/gr.089532.108"]
    CITATION_TEXT = "ABySS 2.0: resource-efficient assembly of large genomes using a Bloom filter; ABySS: a parallel assembler for short read sequence data."
    VERSION = "2.3.10"
    SHELL = True

    PARAM_DEFAULTS = {
        "k": 41,
        "q": "",
        "Q": "",
        "e": "",
        "E": "",
        "t": "",
        "c": "",
        "b": "",
        "m": "",
        "p": "",
        "a": "",
        "l": "",
        "s": "",
        "n": "",
        "d": "",
        "S": "",
        "N": "",
    }

    @classmethod
    def _libraries(cls, inputs: dict[str, Any]) -> list[dict[str, Any]]:
        libraries = inputs.get("libraries") or inputs.get("libs") or []
        if isinstance(libraries, dict):
            return [libraries]
        return list(libraries)

    @classmethod
    def _read_list(cls, value: Any) -> list[str]:
        if isinstance(value, dict):
            return [str(v) for v in (value.get("reads") or value.get("read") or [])]
        return _as_list(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd: list[str] = []
        libnames: dict[str, list[str]] = {"lib": [], "mp": [], "long": []}
        library_assignments: list[str] = []
        for index, library in enumerate(cls._libraries(inputs)):
            lib_type = str(library.get("type", library.get("lib_type", "lib")))
            if lib_type in {"lib", "mp"}:
                forward = str(library.get("forward", library.get("read1", "")))
                reverse = str(library.get("reverse", library.get("read2", "")))
                forward_link = f"{out}/{lib_type}_forward_{index}.{_safe_name(forward).split('.', 1)[1] if '.' in _safe_name(forward) else 'fastq'}"
                reverse_link = f"{out}/{lib_type}_reverse_{index}.{_safe_name(reverse).split('.', 1)[1] if '.' in _safe_name(reverse) else 'fastq'}"
                cmd.extend(["ln", "-sf", forward, forward_link, "&&", "ln", "-sf", reverse, reverse_link, "&&"])
                name = f"{lib_type}{index}"
                libnames[lib_type].append(name)
                library_assignments.append(f"{name}={forward_link} {reverse_link}")
            elif lib_type == "se":
                links: list[str] = []
                for read_index, read in enumerate(cls._read_list(library.get("reads", library.get("read", [])))):
                    link = f"{out}/se_{index}_{read_index}.{_safe_name(read).split('.', 1)[1] if '.' in _safe_name(read) else 'fastq'}"
                    cmd.extend(["ln", "-sf", read, link, "&&"])
                    links.append(link)
                if links:
                    library_assignments.append(f"se={' '.join(links)}")
            elif lib_type == "long":
                for read_index, read in enumerate(cls._read_list(library.get("reads", library.get("read", [])))):
                    link = f"{out}/long_{index + read_index}.{_safe_name(read).split('.', 1)[1] if '.' in _safe_name(read) else 'fasta'}"
                    cmd.extend(["ln", "-sf", read, link, "&&"])
                    name = f"long{index + read_index}"
                    libnames["long"].append(name)
                    library_assignments.append(f"{name}={link}")

        cmd.extend([
            "abyss-pe",
            "name=abyss",
            f"j=${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}",
            f"B=$(( ${{GALAXY_MEMORY_MB:-{inputs.get('memory_mb', 2048)}}} * 9 / 10 ))M",
            f"k={inputs.get('k', 41)}",
        ])
        for key, default in cls.PARAM_DEFAULTS.items():
            if key == "k":
                continue
            value = inputs.get(key, default)
            if value is not None and str(value) != "":
                cmd.append(f"{key}={value}")
        if inputs.get("K") is not None and str(inputs.get("K")) != "":
            insert_at = cmd.index(f"k={inputs.get('k', 41)}") + 1
            cmd.insert(insert_at, f"K={inputs.get('K')}")
        if inputs.get("SS"):
            insert_at = cmd.index(f"k={inputs.get('k', 41)}") + 1
            while insert_at < len(cmd) and cmd[insert_at].split("=", 1)[0] in {"K", "q", "Q", "e", "E", "t", "c", "b"}:
                insert_at += 1
            cmd.insert(insert_at, "SS=--SS")
        for lib_type in ("lib", "mp", "long"):
            if libnames[lib_type]:
                cmd.append(f"{lib_type}={' '.join(libnames[lib_type])}")
        cmd.extend(library_assignments)
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        lib_types = {str(library.get("type", library.get("lib_type", "lib"))) for library in cls._libraries(inputs)}
        outputs = [out / "abyss-unitigs.fa"]
        if "lib" in lib_types:
            outputs.append(out / "abyss-contigs.fa")
        if lib_types & {"lib", "mp"}:
            outputs.append(out / "abyss-scaffolds.fa")
        if "long" in lib_types:
            outputs.append(out / "abyss-long-scaffs.fa")
        outputs.extend([out / "abyss-indel.fa", out / "abyss-stats.tab"])
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "libraries": ("JSON", {"description": "ABySS libraries: objects with type lib/mp/se/long and read paths"}),
                "k": ("INT", {"default": 41, "min": 1, "description": "K-mer length or k-mer-pair span"}),
            },
            "optional": {
                "K": ("INT", {"default": "", "min": 1, "description": "Single k-mer length in a k-mer pair"}),
                "q": ("INT", {"default": 3, "min": 0, "max": 40, "description": "Minimum base quality when trimming"}),
                "Q": ("INT", {"default": 0, "min": 0, "max": 40, "description": "Mask bases below this quality as N"}),
                "e": ("INT", {"default": "", "min": 0, "description": "Minimum erosion k-mer coverage"}),
                "E": ("INT", {"default": "", "min": 0, "description": "Minimum erosion k-mer coverage per strand"}),
                "t": ("INT", {"default": "", "min": 0, "description": "Maximum length of blunt contigs to trim"}),
                "c": ("FLOAT", {"default": "", "min": 0, "description": "Minimum mean k-mer coverage of a unitig"}),
                "b": ("INT", {"default": "", "min": 0, "description": "Maximum bubble length"}),
                "SS": ("BOOLEAN", {"default": False, "description": "Assemble in strand-specific mode"}),
                "m": ("INT", {"default": "", "min": 0, "description": "Minimum overlap of two unitigs"}),
                "p": ("FLOAT", {"default": 0.9, "min": 0, "max": 1, "description": "Minimum sequence identity of a bubble"}),
                "a": ("INT", {"default": 2, "min": 0, "description": "Maximum number of branches of a bubble"}),
                "l": ("INT", {"default": "", "min": 1, "description": "Minimum alignment length of a read"}),
                "s": ("INT", {"default": 200, "min": 0, "description": "Minimum unitig length for building contigs"}),
                "n": ("INT", {"default": 10, "min": 0, "description": "Minimum number of pairs for building contigs"}),
                "d": ("INT", {"default": 6, "min": 0, "description": "Allowable error of a distance estimate"}),
                "S": ("STRING", {"default": "", "description": "Minimum contig size for building scaffolds"}),
                "N": ("STRING", {"default": "", "description": "Minimum number of pairs for building scaffolds"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 256, "display": "slider"}),
                "memory_mb": ("INT", {"default": 2048, "min": 1, "description": "Memory in MB for ABySS Bloom filter"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class ABySSPEGalaxyNode(ABySSPENode):
    """Galaxy wrapper ID for the ABySS paired-end pipeline."""

    NODE_ID = "abyss-pe"
    DISPLAY_NAME = "ABySS (Galaxy)"
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ABySS",
        "abyss-pe",
        "de novo assembler",
        "short read assembly",
        "paired-end assembly",
        "genome assembler",
    ]

class BayeScanNode(CommandNode):
    """Detect loci under selection from population genotype data with BayeScan."""

    NODE_ID = "bayescan"
    DISPLAY_NAME = "BayeScan"
    REQUIRED_CONDA_PACKAGES = ["bayescan"]
    CATEGORY = "population_genetics"
    DESCRIPTION = "Identify candidate loci under natural selection from population allele-frequency differences."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BayeScan",
        "bayescan2",
        "natural selection",
        "population genetics",
        "FST",
        "genome scan",
        "dominant markers",
        "codominant markers",
    ]
    RETURN_TYPES = ("TXT", "TXT", "TXT", "TXT", "TXT", "TXT")
    RETURN_NAMES = ("log", "selection", "verification", "acceptance_rate", "pilot_runs", "allele_frequencies")
    REQUIRED_EXECUTABLES = ["bayescan2"]
    DOCUMENTATION_URL = "http://cmpg.unibe.ch/software/BayeScan/"
    CITATION_DOIS = ["10.1534/genetics.108.092221"]
    CITATION_URLS = [f"{DOI_URL}10.1534/genetics.108.092221"]
    CITATION_TEXT = "A genome-scan method to identify selected loci appropriate for both dominant and codominant markers."
    VERSION = "2.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        discovered_dir = f"{out}/output_dir"
        cmd = [
            "mkdir",
            "-p",
            discovered_dir,
            "&&",
            "bayescan2",
            str(inputs.get("input", "")),
            "-od",
            discovered_dir,
        ]
        if inputs.get("discard_loci_file"):
            cmd.extend(["-d", str(inputs.get("discard_loci_file"))])
        if inputs.get("snp_genotypes_matrix"):
            cmd.append("-fstat")
        if inputs.get("fstats"):
            cmd.append("-snp")
        if inputs.get("pilot_runs"):
            cmd.append("-out_pilot")
        if inputs.get("allele_frequency"):
            cmd.append("-out_freq")
        cmd.extend(
            [
                "-o",
                "bayescan",
                "-n",
                str(inputs.get("sample_size", 5000)),
                "-thin",
                str(inputs.get("thinning_interval", 10)),
                "-nbp",
                str(inputs.get("num_pilot_runs", 20)),
                "-pilot",
                str(inputs.get("length_pilot_run", 5000)),
                "-burn",
                str(inputs.get("burn", 50000)),
                "-pr_odds",
                str(inputs.get("prior_odds", 10)),
                "-lb_fis",
                str(inputs.get("lower_prior", 0.0)),
                "-hb_fis",
                str(inputs.get("higher_prior", 1.0)),
                "-aflp_pc",
                str(inputs.get("threshold", 0.1)),
                ">",
                f"{out}/bayescan.log",
            ]
        )
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        discovered_dir = out / "output_dir"
        discovered_dir.mkdir(parents=True, exist_ok=True)
        outputs = [
            out / "bayescan.log",
            discovered_dir / "bayescan.sel",
            discovered_dir / "bayescan_Verif.txt",
            discovered_dir / "bayescan_AccRte.txt",
        ]
        if inputs.get("pilot_runs"):
            outputs.append(discovered_dir / "bayescan_prop.txt")
        if inputs.get("allele_frequency"):
            outputs.append(discovered_dir / "bayescan_freq.txt")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TXT", {"description": "BayeScan genotype data file in tab- or space-delimited text format"}),
            },
            "optional": {
                "discard_loci_file": ("TSV", {"default": "", "description": "Optional list of loci to discard before analysis"}),
                "snp_genotypes_matrix": (
                    "BOOLEAN",
                    {"default": False, "description": "Use SNP genotypes matrix input mode (-fstat in the Galaxy wrapper)"},
                ),
                "fstats": ("BOOLEAN", {"default": False, "description": "Only estimate F-statistics without selection testing"}),
                "sample_size": ("INT", {"default": 5000, "min": 1, "description": "Number of output iterations"}),
                "thinning_interval": ("INT", {"default": 10, "min": 1, "description": "MCMC thinning interval"}),
                "num_pilot_runs": ("INT", {"default": 20, "min": 0, "description": "Number of pilot runs"}),
                "length_pilot_run": ("INT", {"default": 5000, "min": 1, "description": "Length of each pilot run"}),
                "burn": ("INT", {"default": 50000, "min": 0, "description": "Additional burn-in length"}),
                "prior_odds": ("INT", {"default": 10, "min": 1, "description": "Prior odds for the neutral model"}),
                "lower_prior": (
                    "FLOAT",
                    {"default": 0.0, "min": 0, "max": 1, "description": "Lower bound for the dominant-data Fis prior"},
                ),
                "higher_prior": (
                    "FLOAT",
                    {"default": 1.0, "min": 0, "max": 1, "description": "Upper bound for the dominant-data Fis prior"},
                ),
                "threshold": (
                    "FLOAT",
                    {"default": 0.1, "min": 0, "max": 1, "description": "AFLP recessive-genotype threshold fraction"},
                ),
                "pilot_runs": ("BOOLEAN", {"default": False, "description": "Write optional pilot-run diagnostics"}),
                "allele_frequency": ("BOOLEAN", {"default": False, "description": "Write optional allele-frequency output"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BayeScanGalaxyNode(BayeScanNode):
    """Galaxy wrapper ID for BayeScan."""

    NODE_ID = "BayeScan"
    DISPLAY_NAME = "BayeScan (Galaxy)"
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BayeScan",
        "bayescan2",
        "natural selection",
        "population genetics",
        "FST",
        "genome scan",
        "dominant markers",
        "codominant markers",
    ]

class BellavistaPrepareNode(CommandNode):
    """Prepare BellaVista spatial transcriptomics inputs."""

    NODE_ID = "bellavista_prepare"
    DISPLAY_NAME = "Bellavista"
    CATEGORY = "visualization"
    DESCRIPTION = "Prepare large images for bellavista visualizer."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Bellavista",
        "BellaVista",
        "bellavista_prepare",
        "spatial transcriptomics",
        "imaging-based spatial transcriptomics",
        "MERSCOPE",
        "Xenium",
        "OME-Zarr",
        "visualizer",
    ]
    RETURN_TYPES = ("TGZ", "JSON")
    RETURN_NAMES = ("bellavista_output", "config")
    REQUIRED_EXECUTABLES = ["bash", "cat", "chmod", "cp", "mkdir", "tar"]
    DOCUMENTATION_URL = "https://github.com/pkosurilab/BellaVista"
    CITATION_DOIS = ["10.1016/j.bpj.2024.11.3199"]
    CITATION_URLS = [f"{DOI_URL}10.1016/j.bpj.2024.11.3199", "https://github.com/pkosurilab/BellaVista"]
    CITATION_TEXT = "Open-source Visualization for Imaging-Based Spatial Transcriptomics."
    VERSION = "0.0.2"
    ENVIRONMENT = {"container": "quay.io/bgruening/bellavista:0.0.2-3"}
    SHELL = True
    TECHNOLOGIES = ["Xenium", "MERSCOPE"]

    @classmethod
    def _bool(cls, inputs: dict[str, Any], name: str, default: bool) -> bool:
        value = inputs.get(name, default)
        if isinstance(value, str):
            return value.lower() in {"true", "yes", "1"}
        return bool(value)

    @classmethod
    def _technology(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("technology", "MERSCOPE") or "MERSCOPE")

    @classmethod
    def _staged_name(cls, path: Any) -> str:
        return _safe_name(str(path))

    @classmethod
    def _selected_genes(cls, inputs: dict[str, Any]) -> list[str]:
        genes = str(inputs.get("selected_genes", "") or "")
        return [gene.strip() for gene in genes.split(",") if gene.strip()]

    @classmethod
    def _config_payload(cls, inputs: dict[str, Any]) -> dict[str, Any]:
        plot_transcripts = cls._bool(inputs, "plot_transcripts", True)
        plot_cell_seg = cls._bool(inputs, "plot_cell_seg", True)
        plot_nuclear_seg = cls._bool(inputs, "plot_nuclear_seg", False)
        plot_all_genes = str(inputs.get("plot_all_genes", "Yes") or "Yes")
        input_files: dict[str, Any] = {
            "images": [cls._staged_name(image) for image in _as_list(inputs.get("images"))],
        }
        if plot_cell_seg:
            input_files["cell_segmentation"] = cls._staged_name(inputs.get("cell_segmentation", ""))
        if plot_nuclear_seg:
            input_files["nuclear_segmentation"] = cls._staged_name(inputs.get("nuclear_segmentation", ""))
        if cls._technology(inputs) == "MERSCOPE":
            input_files["um_to_px_transform"] = "micron_to_mosaic_pixel_transform.csv"
        if plot_transcripts:
            input_files["transcript_filename"] = cls._staged_name(inputs.get("transcript_filename", ""))
        input_files["z_plane"] = int(inputs.get("z_plane", 0))

        visualization_parameters: dict[str, Any] = {
            "plot_image": True,
            "plot_transcripts": plot_transcripts,
            "plot_cell_seg": plot_cell_seg,
            "plot_nuclear_seg": plot_nuclear_seg,
            "genes_visible_on_startup": False,
            "plot_allgenes": plot_all_genes == "Yes",
        }
        if plot_all_genes != "Yes":
            visualization_parameters["selected_genes"] = cls._selected_genes(inputs)
        visualization_parameters.update(
            {
                "rotate_angle": int(inputs.get("rotate_angle", 0)),
                "transcript_point_size": int(inputs.get("transcript_point_size", 1)),
            }
        )

        return {
            "system": cls._technology(inputs),
            "data_folder": "./",
            "create_bellavista_inputs": True,
            "visualization_parameters": visualization_parameters,
            "input_files": input_files,
        }

    @classmethod
    def _config_json(cls, inputs: dict[str, Any]) -> str:
        return json.dumps(cls._config_payload(inputs), separators=(",", ":"))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_dir = f"{out}/input"
        config_path = f"{input_dir}/config.json"
        commands = [
            f"export TIME_LIMIT_SECONDS={shlex.quote(str(inputs.get('timeout', 3600)))}",
            f"export BELLAVISTA_DIR={shlex.quote(f'{input_dir}/')}",
            _shell_join(["mkdir", "-p", input_dir, f"{input_dir}/BellaVista_output"]),
            _shell_join(["chmod", "-R", "777", f"{input_dir}/"]),
        ]
        if cls._bool(inputs, "plot_transcripts", True):
            commands.append(
                _shell_join(["cp", str(inputs.get("transcript_filename", "")), f"{input_dir}/{cls._staged_name(inputs.get('transcript_filename', ''))}"])
            )
        for image in _as_list(inputs.get("images")):
            commands.append(_shell_join(["cp", image, f"{input_dir}/{cls._staged_name(image)}"]))
        if cls._bool(inputs, "plot_cell_seg", True):
            commands.append(
                _shell_join(["cp", str(inputs.get("cell_segmentation", "")), f"{input_dir}/{cls._staged_name(inputs.get('cell_segmentation', ''))}"])
            )
        if cls._bool(inputs, "plot_nuclear_seg", False):
            commands.append(
                _shell_join(
                    [
                        "cp",
                        str(inputs.get("nuclear_segmentation", "")),
                        f"{input_dir}/{cls._staged_name(inputs.get('nuclear_segmentation', ''))}",
                    ]
                )
            )
        if cls._technology(inputs) == "MERSCOPE":
            commands.append(
                _shell_join(["cp", str(inputs.get("um_to_px_transform", "")), f"{input_dir}/micron_to_mosaic_pixel_transform.csv"])
            )
        config_json = cls._config_json(inputs)
        commands.extend(
            [
                f"printf %s {shlex.quote(config_json)} > {shlex.quote(config_path)}",
                _shell_join(["cat", config_path]),
                _shell_join(["cp", config_path, f"{input_dir}/config_orig.json"]),
                f"cd {shlex.quote(f'{input_dir}/')} && {_shell_join(['bash', str(inputs.get('script_path', 'bellavista.bash'))])}",
                f"cd {shlex.quote(out)} && {_shell_join(['tar', '-czf', f'{out}/bellavista.tar.gz', 'input/'])}",
            ]
        )
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        (out / "input").mkdir(parents=True, exist_ok=True)
        outputs = [out / "bellavista.tar.gz"]
        if cls._bool(inputs, "config", True):
            outputs.append(out / "input" / "config_orig.json")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "images": ("FILE", {"is_list": True, "description": "TIFF or OME-TIFF image files to prepare"}),
            },
            "optional": {
                "technology": (
                    "STRING",
                    {
                        "default": "MERSCOPE",
                        "options": cls.TECHNOLOGIES,
                        "description": "Spatial transcriptomic technology represented by the input data",
                    },
                ),
                "um_to_px_transform": (
                    "CSV",
                    {
                        "default": "",
                        "description": "MERSCOPE micron-to-mosaic-pixel transform CSV",
                    },
                ),
                "plot_transcripts": ("BOOLEAN", {"default": True, "description": "Include transcript spatial locations"}),
                "transcript_filename": (
                    "FILE",
                    {"default": "", "description": "Transcript spatial locations in CSV or Parquet format"},
                ),
                "plot_all_genes": ("STRING", {"default": "Yes", "options": ["Yes", "No"]}),
                "selected_genes": ("STRING", {"default": "", "description": "Comma-separated genes to visualize"}),
                "plot_cell_seg": ("BOOLEAN", {"default": True, "description": "Include cell segmentation data"}),
                "cell_segmentation": ("FILE", {"default": "", "description": "Cell segmentation Parquet or Zarr data"}),
                "plot_nuclear_seg": ("BOOLEAN", {"default": False, "description": "Include nuclear segmentation data"}),
                "nuclear_segmentation": ("FILE", {"default": "", "description": "Nuclear segmentation Parquet or Zarr data"}),
                "z_plane": ("INT", {"default": 0, "min": 0, "description": "Image z-plane to visualize"}),
                "transcript_point_size": ("INT", {"default": 1, "min": 0, "description": "Transcript point size"}),
                "rotate_angle": ("INT", {"default": 0, "min": -180, "max": 180, "description": "Image rotation angle"}),
                "config": ("BOOLEAN", {"default": True, "description": "Also return the generated config JSON"}),
                "timeout": ("INT", {"default": 3600, "min": 0, "max": 21600, "advanced": True}),
                "script_path": (
                    "FILE",
                    {"default": "bellavista.bash", "advanced": True, "description": "Path to the Galaxy Bellavista helper script"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not _as_list(inputs.get("images")):
            return "images is required"
        technology = cls._technology(inputs)
        if technology not in cls.TECHNOLOGIES:
            return f"technology must be one of: {', '.join(cls.TECHNOLOGIES)}"
        if technology == "MERSCOPE" and not inputs.get("um_to_px_transform"):
            return "um_to_px_transform is required for MERSCOPE"
        if cls._bool(inputs, "plot_transcripts", True) and not inputs.get("transcript_filename"):
            return "transcript_filename is required when plot_transcripts is true"
        if str(inputs.get("plot_all_genes", "Yes") or "Yes") == "No" and not cls._selected_genes(inputs):
            return "selected_genes is required when plot_all_genes is No"
        if cls._bool(inputs, "plot_cell_seg", True) and not inputs.get("cell_segmentation"):
            return "cell_segmentation is required when plot_cell_seg is true"
        if cls._bool(inputs, "plot_nuclear_seg", False) and not inputs.get("nuclear_segmentation"):
            return "nuclear_segmentation is required when plot_nuclear_seg is true"
        return True

class BellerophonNode(CommandNode):
    """Filter and merge Arima Genomics chimeric read alignments with Bellerophon."""

    NODE_ID = "bellerophon"
    DISPLAY_NAME = "Bellerophon"
    REQUIRED_CONDA_PACKAGES = ["bellerophon", "samtools"]
    CATEGORY = "assembly"
    DESCRIPTION = "Filter mapped reads spanning Arima Genomics junctions, keep the 5-prime read, merge mates, and sort the BAM output."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Bellerophon",
        "Arima Genomics",
        "chimeric reads",
        "Hi-C",
        "junction-spanning reads",
        "qname sorted BAM",
        "genome assembly",
    ]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("merged_bam",)
    REQUIRED_EXECUTABLES = ["bellerophon", "samtools"]
    DOCUMENTATION_URL = "https://github.com/ArimaGenomics/bellerophon"
    CITATION_DOIS = ["10.1038/s41586-021-03451-0"]
    CITATION_URLS = [f"{DOI_URL}10.1038/s41586-021-03451-0"]
    CITATION_TEXT = "Semi-automated assembly of high-quality diploid human reference genomes."
    VERSION = "1.0"
    SHELL = True

    @classmethod
    def _format_suffix(cls, inputs: dict[str, Any], key: str, path_key: str) -> str:
        fmt = str(inputs.get(key, "")).strip().lower().lstrip(".")
        if fmt in {"sam", "bam"}:
            return fmt
        suffix = Path(str(inputs.get(path_key, ""))).suffix.lower().lstrip(".")
        return "sam" if suffix == "sam" else "bam"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        forward_input = f"{out}/forward_input.{cls._format_suffix(inputs, 'forward_format', 'forward')}"
        reverse_input = f"{out}/reverse_input.{cls._format_suffix(inputs, 'reverse_format', 'reverse')}"
        threads = f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}"
        cmd = [
            "ln",
            "-s",
            str(inputs.get("forward", "")),
            forward_input,
            "&&",
            "ln",
            "-s",
            str(inputs.get("reverse", "")),
            reverse_input,
            "&&",
            "bellerophon",
            "--forward",
            forward_input,
            "--reverse",
            reverse_input,
            "--quality",
            str(inputs.get("quality", 20)),
            "--output",
            f"{out}/merged_out.bam",
            "--threads",
            threads,
            "&&",
            "samtools",
            "sort",
            "--no-PG",
            "-O",
            "BAM",
            "-o",
            f"{out}/merged.bam",
            "-@",
            threads,
            f"{out}/merged_out.bam",
        ]
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "merged.bam"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "forward": ("BAM", {"description": "First qname-sorted BAM or SAM reads, usually forward reads"}),
                "reverse": ("BAM", {"description": "Second qname-sorted BAM or SAM reads, usually reverse reads"}),
                "quality": ("INT", {"default": 20, "min": 0, "max": 255, "description": "Minimum mapping quality"}),
            },
            "optional": {
                "forward_format": (
                    "STRING",
                    {
                        "default": "bam",
                        "options": ["bam", "sam"],
                        "advanced": True,
                        "description": "Galaxy input datatype for staging the forward reads",
                    },
                ),
                "reverse_format": (
                    "STRING",
                    {
                        "default": "bam",
                        "options": ["bam", "sam"],
                        "advanced": True,
                        "description": "Galaxy input datatype for staging the reverse reads",
                    },
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class ChromeisterNode(CommandNode):
    """Run ultra-fast pairwise genome comparison and dotplot generation with Chromeister."""

    NODE_ID = "chromeister"
    DISPLAY_NAME = "Chromeister"
    REQUIRED_CONDA_PACKAGES = ["chromeister"]
    CATEGORY = "comparative_genomics"
    DESCRIPTION = "Compare two FASTA assemblies with Chromeister to produce a comparison matrix, dotplot, event calls, and similarity score."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Chromeister",
        "pairwise genome comparison",
        "dotplot",
        "synteny blocks",
        "large-scale rearrangements",
        "whole genome comparison",
        "CHROMEISTER",
    ]
    RETURN_TYPES = ("TXT", "IMAGE", "CSV", "TXT", "IMAGE", "TXT")
    RETURN_NAMES = ("matrix", "dotplot_png", "metainfo_csv", "events_txt", "events_png", "score")
    REQUIRED_EXECUTABLES = ["CHROMEISTER", "compute_score.R", "compute_score-nogrid.R", "detect_events.py"]
    DOCUMENTATION_URL = "https://github.com/estebanpw/chromeister"
    CITATION_DOIS = ["10.1038/s41598-019-46773-w"]
    CITATION_URLS = [f"{DOI_URL}10.1038/s41598-019-46773-w"]
    CITATION_TEXT = "Ultrafast genome comparison for large-scale genomic experiments."
    VERSION = "1.5.a"
    SHELL = True

    @classmethod
    def _staged_names(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        out = _out(inputs)
        query_name = _safe_name(str(inputs.get("query", "query.fasta"))) or "query.fasta"
        db_name = _safe_name(str(inputs.get("db", "db.fasta"))) or "db.fasta"
        return f"{out}/{query_name}", f"{out}/{db_name}"

    @classmethod
    def _matrix_prefix(cls, inputs: dict[str, Any]) -> str:
        query_name, db_name = cls._staged_names(inputs)
        return f"{query_name}-{Path(db_name).name}.mat"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        query_name, db_name = cls._staged_names(inputs)
        matrix = cls._matrix_prefix(inputs)
        score_script = "compute_score.R" if inputs.get("grid", True) else "compute_score-nogrid.R"
        cmd = [
            "ln",
            "-s",
            str(inputs.get("query", "")),
            query_name,
            "&&",
            "ln",
            "-s",
            str(inputs.get("db", "")),
            db_name,
            "&&",
            "CHROMEISTER",
            "-query",
            query_name,
            "-db",
            db_name,
            "-dimension",
            str(inputs.get("dimension", 1000)),
            "-kmer",
            str(inputs.get("kmer", 32)),
            "-diffuse",
            str(inputs.get("diffuse", 4)),
            "-out",
            matrix,
            "&&",
            score_script,
            matrix,
            str(inputs.get("dimension", 1000)),
            ">",
            f"{out}/comparison_score.txt",
            "&&",
            "detect_events.py",
            f"{matrix}.raw.txt",
        ]
        if inputs.get("pngevents", True):
            cmd.extend([
                "png",
                "&&",
                "mv",
                f"{matrix}.events.png",
                f"{out}/events.png",
            ])
        cmd.extend(
            [
                "&&",
                "mv",
                matrix,
                f"{out}/comparison_matrix.txt",
                "&&",
                "mv",
                f"{matrix}.filt.png",
                f"{out}/dotplot.png",
                "&&",
                "mv",
                f"{matrix}.events.txt",
                f"{out}/events.txt",
                "&&",
                "mv",
                f"{matrix}.csv",
                f"{out}/comparison_metainfo.csv",
            ]
        )
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [
            out / "comparison_matrix.txt",
            out / "dotplot.png",
            out / "comparison_metainfo.csv",
            out / "events.txt",
        ]
        if inputs.get("pngevents", False):
            outputs.append(out / "events.png")
        outputs.append(out / "comparison_score.txt")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query": ("FASTA", {"description": "Query sequence FASTA"}),
                "db": ("FASTA", {"description": "Reference sequence FASTA"}),
            },
            "optional": {
                "dimension": (
                    "INT",
                    {
                        "default": 1000,
                        "min": 500,
                        "max": 2000,
                        "description": "Output dotplot size in pixels per side",
                    },
                ),
                "kmer": ("INT", {"default": 32, "options": [32, 16], "description": "K-mer seed size"}),
                "diffuse": (
                    "INT",
                    {"default": 4, "min": 1, "max": 4, "description": "Heuristic subsampling level"},
                ),
                "grid": ("BOOLEAN", {"default": True, "description": "Use grid-aware score computation for multi-FASTA inputs"}),
                "pngevents": ("BOOLEAN", {"default": True, "description": "Generate a PNG plot of detected rearrangement events"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BigWigOutlierBedNode(CommandNode):
    """Convert high, low, or zero BigWig outlier runs into BED features."""

    NODE_ID = "bigwig_outlier_bed"
    DISPLAY_NAME = "Bigwig outliers to bed features"
    REQUIRED_CONDA_PACKAGES = ["python", "numpy", "pybigtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Write continuous high, low, or zero-valued BigWig outlier regions as BED features, with optional contig statistics."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BigWig outliers",
        "bigwig_outlier_bed",
        "pybigtools",
        "coverage outliers",
        "BED features",
        "quantile cutoff",
        "contig statistics",
    ]
    RETURN_TYPES = ("BED", "BED", "BED", "BED", "TXT")
    RETURN_NAMES = ("high_low_bed", "high_bed", "low_bed", "zero_bed", "contig_statistics")
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = "https://github.com/jackh726/bigtools"
    CITATION_DOIS = ["10.1093/bioinformatics/btae350"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/btae350"]
    CITATION_TEXT = "Bigtools: a high-performance toolkit for BigWig and BigBed files."
    VERSION = "0.2.5"
    SHELL = True

    BED_OUTPUTS = {
        "bedouthilo": "high_low_regions.bed",
        "bedouthi": "high_regions.bed",
        "bedoutlo": "low_regions.bed",
        "bedoutzero": "zero_regions.bed",
    }

    @classmethod
    def _output_names(cls, outbeds: str) -> list[str]:
        if outbeds == "outhilo":
            return ["bedouthilo"]
        if outbeds == "outhi":
            return ["bedouthi"]
        if outbeds == "outlo":
            return ["bedoutlo"]
        if outbeds == "outzero":
            return ["bedoutzero"]
        if outbeds == "outall":
            return ["bedouthilo", "bedouthi", "bedoutlo"]
        if outbeds == "outlohi":
            return ["bedouthi", "bedoutlo"]
        return []

    @classmethod
    def _bigwig_labels(cls, inputs: dict[str, Any], bigwigs: list[str]) -> list[str]:
        labels = _as_list(inputs.get("bigwiglabels"))
        if labels:
            return labels
        return [Path(bigwig).name for bigwig in bigwigs]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        bigwigs = _as_list(inputs.get("bigwig"))
        cmd = ["python", str(inputs.get("script", "bigwig_outlier_bed.py"))]
        for bigwig in bigwigs:
            cmd.extend(["--bigwig", bigwig])
        for label in cls._bigwig_labels(inputs, bigwigs):
            cmd.extend(["--bigwiglabels", label])
        outbeds = str(inputs.get("outbeds", "outhilo"))
        cmd.extend(["--outbeds", outbeds])
        for output_name in cls._output_names(outbeds):
            cmd.extend([f"--{output_name}", f"{out}/{cls.BED_OUTPUTS[output_name]}"])
        cmd.extend(["--minwin", str(inputs.get("minwin", 10))])
        if inputs.get("qhi") is not None and str(inputs.get("qhi")) != "":
            cmd.extend(["--qhi", str(inputs.get("qhi"))])
        if inputs.get("qlo") is not None and str(inputs.get("qlo")) != "":
            cmd.extend(["--qlo", str(inputs.get("qlo"))])
        if str(inputs.get("tableout", "create")) == "create" or outbeds == "outtab":
            cmd.extend(["--tableoutfile", f"{out}/contig_statistics.txt"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outbeds = str(inputs.get("outbeds", "outhilo"))
        outputs = [out / cls.BED_OUTPUTS[output_name] for output_name in cls._output_names(outbeds)]
        if str(inputs.get("tableout", "create")) == "create" or outbeds == "outtab":
            outputs.append(out / "contig_statistics.txt")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        outbed_options = ["outhilo", "outhi", "outlo", "outzero", "outall", "outlohi", "outtab"]
        return {
            "required": {
                "bigwig": (
                    "BIGWIG",
                    {
                        "multiple": True,
                        "description": "One or more BigWig files sharing the same reference sequence",
                    },
                ),
            },
            "optional": {
                "bigwiglabels": (
                    "STRING",
                    {"default": [], "multiple": True, "description": "Optional labels aligned to the BigWig inputs"},
                ),
                "minwin": (
                    "INT",
                    {
                        "default": 10,
                        "min": 1,
                        "description": "Minimum continuous bases required for a BED feature",
                    },
                ),
                "qhi": (
                    "FLOAT",
                    {"default": 0.99999, "min": 0, "max": 1, "description": "Upper quantile cutoff for high regions"},
                ),
                "qlo": (
                    "FLOAT",
                    {"default": 0.00001, "min": 0, "max": 1, "description": "Lower quantile cutoff for low regions"},
                ),
                "outbeds": (
                    "STRING",
                    {
                        "default": "outhilo",
                        "options": outbed_options,
                        "description": "Select high/low/zero BED outputs or table-only mode",
                    },
                ),
                "tableout": (
                    "STRING",
                    {
                        "default": "create",
                        "options": ["create", "donotmake"],
                        "description": "Whether to write the contig statistics table",
                    },
                ),
                "script": (
                    "FILE",
                    {
                        "default": "bigwig_outlier_bed.py",
                        "advanced": True,
                        "description": "Path to the Galaxy bigwig_outlier_bed.py helper script",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class AmpliGoneNode(CommandNode):
    """Find and remove primers from amplicon sequencing reads with AmpliGone."""

    NODE_ID = "ampligone"
    DISPLAY_NAME = "AmpliGone"
    REQUIRED_CONDA_PACKAGES = ["AmpliGone"]
    CATEGORY = "sequence"
    DESCRIPTION = "Remove primer-derived sequence from FASTQ or BAM amplicon reads using primer coordinates or primer FASTA against a reference."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "AmpliGone",
        "AmpliGone primer removal",
        "primer removal",
        "amplicon reads",
        "ARTIC primers",
        "Nanopore",
        "Illumina",
        "fragmented amplicons",
    ]
    RETURN_TYPES = ("FASTQ", "BED")
    RETURN_NAMES = ("cleaned_reads", "primer_coordinates")
    REQUIRED_EXECUTABLES = ["ampligone"]
    DOCUMENTATION_URL = "https://rivm-bioinformatics.github.io/AmpliGone/"
    CITATION_DOIS = ["10.5281/zenodo.7684307"]
    CITATION_URLS = [f"{DOI_URL}10.5281/zenodo.7684307"]
    CITATION_TEXT = "AmpliGone: find and remove primers from NGS amplicon reads."
    VERSION = "2.0.1"
    SHELL = True

    @classmethod
    def _staged_ext(cls, datatype: Any, default: str) -> str:
        ext = str(datatype or default).replace("sanger", "").strip(".")
        return ext or default

    @classmethod
    def _cleaned_name(cls, inputs: dict[str, Any]) -> str:
        return "cleaned_reads.fastq.gz" if str(inputs.get("input_ext", "")).endswith(".gz") else "cleaned_reads.fastq"

    @classmethod
    def _staged_names(cls, inputs: dict[str, Any]) -> tuple[str, str, str, str]:
        out = _out(inputs)
        input_ext = cls._staged_ext(inputs.get("input_ext"), Path(str(inputs.get("input", ""))).suffix.lstrip(".") or "fastq")
        reference_ext = cls._staged_ext(inputs.get("reference_ext"), "fasta")
        primers_ext = cls._staged_ext(inputs.get("primers_ext"), Path(str(inputs.get("primers", ""))).suffix.lstrip(".") or "bed")
        cleaned_name = cls._cleaned_name(inputs)
        return (
            f"{out}/reads.{input_ext}",
            f"{out}/reference.{reference_ext}",
            f"{out}/primers.{primers_ext}",
            f"{out}/{cleaned_name}",
        )

    @classmethod
    def _should_export_primers(cls, inputs: dict[str, Any]) -> bool:
        return bool(inputs.get("export_primers")) and cls._staged_ext(inputs.get("primers_ext"), "bed") == "fasta"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        reads, reference, primers, cleaned = cls._staged_names(inputs)
        output_name = f"{out}/output.fastq.gz" if cleaned.endswith(".gz") else f"{out}/output.fastq"
        cmd = [
            "ln",
            "-sf",
            str(inputs.get("input", "")),
            reads,
            "&&",
            "touch",
            cleaned,
            "&&",
            "ln",
            "-sf",
            cleaned,
            output_name,
            "&&",
            "ln",
            "-sf",
            str(inputs.get("reference", "")),
            reference,
            "&&",
            "ln",
            "-sf",
            str(inputs.get("primers", "")),
            primers,
        ]
        if cls._should_export_primers(inputs):
            cmd.extend([
                "&&",
                "touch",
                f"{out}/primer_coordinates.bed",
                "&&",
                "ln",
                "-sf",
                f"{out}/primer_coordinates.bed",
                f"{out}/primers.bed",
            ])
        cmd.extend(
            [
                "&&",
                "ampligone",
                "--input",
                reads,
                "--reference",
                reference,
                "--primers",
                primers,
                "--threads",
                f"${{GALAXY_SLOTS:-{inputs.get('threads', 2)}}}",
            ]
        )
        amplicon_type = str(inputs.get("amplicon_type", "end-to-end") or "")
        if amplicon_type:
            cmd.extend(["--amplicon-type", amplicon_type])
        if amplicon_type == "fragmented":
            cmd.extend(["--fragment-lookaround-size", str(inputs.get("fragment_lookaround_size", 10))])
        if inputs.get("error_rate") is not None and str(inputs.get("error_rate")) != "":
            cmd.extend(["--error-rate", str(inputs.get("error_rate"))])
        if cls._should_export_primers(inputs):
            cmd.extend(["--export-primers", f"{out}/primers.bed"])
        cmd.extend(["--output", output_name])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / cls._cleaned_name(inputs)]
        if cls._should_export_primers(inputs):
            outputs.append(out / "primer_coordinates.bed")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTQ", {"description": "Reads in FASTQ, gzipped FASTQ, or BAM format"}),
                "reference": ("FASTA", {"description": "Reference genome FASTA"}),
                "primers": ("FILE", {"description": "Primer sequences in FASTA or BED format"}),
            },
            "optional": {
                "input_ext": (
                    "STRING",
                    {"default": "fastq", "options": ["fastq", "fastq.gz", "bam"], "advanced": True},
                ),
                "reference_ext": ("STRING", {"default": "fasta", "advanced": True}),
                "primers_ext": (
                    "STRING",
                    {"default": "bed", "options": ["bed", "fasta"], "advanced": True},
                ),
                "export_primers": (
                    "BOOLEAN",
                    {"default": False, "description": "Export detected primer coordinates when primers are provided as FASTA"},
                ),
                "amplicon_type": (
                    "STRING",
                    {
                        "default": "end-to-end",
                        "options": ["end-to-end", "end-to-mid", "fragmented"],
                        "description": "Expected relationship between read length and amplicon length",
                    },
                ),
                "fragment_lookaround_size": (
                    "INT",
                    {"default": 10, "min": 0, "description": "Bases to search around primer sites for fragmented amplicons"},
                ),
                "error_rate": (
                    "FLOAT",
                    {"default": 0.1, "min": 0, "max": 1, "description": "Maximum allowed primer-search error rate"},
                ),
                "threads": ("INT", {"default": 2, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BinetteNode(CommandNode):
    """Refine metagenomic binning outputs into high-quality MAGs with Binette."""

    NODE_ID = "binette"
    DISPLAY_NAME = "Binette"
    REQUIRED_CONDA_PACKAGES = ["binette"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Refine multiple contig-to-bin tables into high-quality metagenome-assembled genomes with quality reports."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Binette",
        "Binette binning refinement",
        "binning refinement",
        "metagenomic binning",
        "MAG refinement",
        "CheckM2 database",
        "contig-to-bin tables",
    ]
    RETURN_TYPES = ("DIRECTORY", "DIRECTORY", "TSV")
    RETURN_NAMES = ("bins", "quality_reports", "final_quality_report")
    REQUIRED_EXECUTABLES = ["binette"]
    DOCUMENTATION_URL = "https://github.com/genotoul-bioinfo/Binette"
    CITATION_DOIS = ["10.21105/joss.06782"]
    CITATION_URLS = [f"{DOI_URL}10.21105/joss.06782"]
    CITATION_TEXT = "Binette: a fast and accurate binning refinement tool to construct high-quality MAGs."
    VERSION = "1.2.1"
    SHELL = True

    @classmethod
    def _checkm2_db(cls, inputs: dict[str, Any], out: str) -> str:
        if str(inputs.get("database_type", "cached")) == "his":
            return f"{out}/input_database.dmnd"
        return str(inputs.get("checkm2_db_path", inputs.get("datamanager", inputs.get("database_path", ""))))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        input_dir = f"{out}/input"
        output_dir = f"{out}/output"
        cmd = ["mkdir", "-p", input_dir, output_dir]
        for index, table in enumerate(_as_list(inputs.get("contig2bin_tables", inputs.get("bins")))):
            cmd.extend(["&&", "ln", "-s", table, f"{input_dir}/bin_table_{index}.tsv"])
        cmd.extend(["&&", "ln", "-s", str(inputs.get("contigs", "")), f"{out}/input_contigs.fasta"])
        if str(inputs.get("database_type", "cached")) == "his":
            cmd.extend(["&&", "ln", "-s", str(inputs.get("checkm2_db", "")), f"{out}/input_database.dmnd"])
        if inputs.get("proteins"):
            cmd.extend(["&&", "ln", "-s", str(inputs.get("proteins")), f"{out}/input_proteins.fasta"])
        cmd.extend(
            [
                "&&",
                "binette",
                "-b",
                f"{input_dir}/*.tsv",
                "-c",
                f"{out}/input_contigs.fasta",
            ]
        )
        if inputs.get("proteins"):
            cmd.extend(["-p", f"{out}/input_proteins.fasta"])
        cmd.extend(
            [
                "--min_completeness",
                str(inputs.get("min_completeness", 40)),
                "-t",
                f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}",
                "-o",
                f"{output_dir}/",
                "-w",
                str(inputs.get("contamination_weight", 2)),
                "--checkm2_db",
                cls._checkm2_db(inputs, out),
            ]
        )
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID / "output"
        bins = out / "final_bins"
        quality_reports = out / "input_bins_quality_reports"
        bins.mkdir(parents=True, exist_ok=True)
        quality_reports.mkdir(parents=True, exist_ok=True)
        return [bins, quality_reports, out / "final_bins_quality_reports.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "contig2bin_tables": (
                    "TSV",
                    {
                        "multiple": True,
                        "min_items": 2,
                        "description": "At least two contig-to-bin tables from independent binning tools",
                    },
                ),
                "contigs": ("FASTA", {"description": "Assembly contigs used to generate the binning tables"}),
            },
            "optional": {
                "proteins": (
                    "FASTA",
                    {"default": "", "description": "Optional Prodigal-format predicted protein FASTA"},
                ),
                "min_completeness": (
                    "INT",
                    {"default": 40, "min": 0, "max": 100, "description": "Minimum completeness threshold for final bins"},
                ),
                "contamination_weight": (
                    "INT",
                    {"default": 2, "description": "Weight applied to contamination in the bin selection score"},
                ),
                "database_type": (
                    "STRING",
                    {
                        "default": "cached",
                        "options": ["cached", "his"],
                        "description": "Use a cached CheckM2 DIAMOND database or a database from workflow history",
                    },
                ),
                "checkm2_db": (
                    "FILE",
                    {"default": "", "description": "History CheckM2 DIAMOND database for database_type=his"},
                ),
                "checkm2_db_path": (
                    "FILE",
                    {"default": "", "description": "Cached CheckM2 DIAMOND database path for database_type=cached"},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        tables = _as_list(inputs.get("contig2bin_tables", inputs.get("bins")))
        if len(tables) < 2:
            return "at least two contig-to-bin tables are required"
        if not str(inputs.get("contigs", "")).strip():
            return "contigs FASTA is required"
        if str(inputs.get("database_type", "cached")) == "his":
            if not str(inputs.get("checkm2_db", "")).strip():
                return "CheckM2 DIAMOND database is required for history database mode"
        elif not str(cls._checkm2_db(inputs, _out(inputs))).strip():
            return "cached CheckM2 DIAMOND database path is required"
        return super().VALIDATE_INPUTS(inputs)

class BiaPyNode(CommandNode):
    """Run BiaPy deep-learning workflows for bioimage analysis."""

    NODE_ID = "biapy"
    DISPLAY_NAME = "Build a workflow with BiaPy"
    CATEGORY = "ai"
    DESCRIPTION = "Run BiaPy deep-learning workflows for bioimage analysis."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BiaPy",
        "biapy",
        "Build a workflow with BiaPy",
        "accessible deep learning on bioimages",
        "bioimage analysis",
        "image segmentation",
        "object detection",
        "image denoising",
        "BioImage Model Zoo",
    ]
    RETURN_TYPES = ("DIRECTORY", "DIRECTORY", "DIRECTORY", "DIRECTORY", "DIRECTORY", "YAML")
    RETURN_NAMES = ("predictions_raw", "predictions_post_proc", "test_metrics", "train_charts", "train_logs", "config_file")
    REQUIRED_EXECUTABLES = ["biapy", "ln", "mkdir", "mktemp", "mv", "python3"]
    DOCUMENTATION_URL = "https://biapy.readthedocs.io/"
    CITATION_DOIS = ["10.1038/s41592-025-02699-y"]
    CITATION_URLS = [f"{DOI_URL}10.1038/s41592-025-02699-y"]
    CITATION_TEXT = "BiaPy: accessible deep learning on bioimages."
    VERSION = "3.6.8"
    ENVIRONMENT = {"container": "biapyx/biapy:3.6.8-11.8"}
    SHELL = True
    MODES = ["custom_cfg", "create_new_cfg"]
    WORKFLOWS = ["semantic", "instance", "detection", "denoising", "sr", "cls", "sr2", "i2i"]
    PHASES = ["train_test", "train", "test"]
    MODEL_SOURCES = ["biapy", "biapy_pretrained", "bmz_pretrained"]
    OUTPUT_OPTIONS = ["raw", "post_proc", "metrics", "tcharts", "tlogs", "checkpoint"]

    @classmethod
    def _phase(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("phase", inputs.get("phases", "train_test")) or "train_test")

    @classmethod
    def _selected_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        outputs = _as_list(inputs.get("selected_outputs"))
        return outputs or ["raw"]

    @classmethod
    def _file_ext(cls, path: str, default: str = "dat") -> str:
        suffixes = Path(path).suffixes
        if not suffixes:
            return default
        if len(suffixes) >= 2 and suffixes[-1] == ".gz":
            return "".join(suffixes[-2:]).lstrip(".")
        return suffixes[-1].lstrip(".") or default

    @classmethod
    def _stage_files(cls, command_parts: list[str], files: list[str], directory: str, prefix: str) -> None:
        if not files:
            return
        command_parts.append(_shell_join(["mkdir", "-p", directory]))
        for index, path in enumerate(files):
            staged = f"{directory}/{prefix}-{index}.{cls._file_ext(path)}"
            command_parts.append(_shell_join(["ln", "-fs", path, staged]))

    @classmethod
    def _yaml_command(cls, inputs: dict[str, Any], out: str) -> str:
        mode = str(inputs.get("selected_mode", "custom_cfg") or "custom_cfg")
        script = str(inputs.get("create_yaml_script", "create_yaml.py"))
        config = f"{out}/config.yaml"
        threads = f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}"
        train_raw_dir = f"{out}/dataset/train/raw"
        train_gt_dir = f"{out}/dataset/train/gt"
        test_raw_dir = f"{out}/dataset/test/raw"
        test_gt_dir = f"{out}/dataset/test/gt"
        checkpoint_file = f"{out}/output/my_experiment/checkpoints/checkpoint.safetensors"
        cmd = ["python3", script]
        if mode == "custom_cfg":
            cmd.extend(["--input_config_path", str(inputs.get("config_path", "")), "--num_cpus", threads])
        else:
            cmd.extend(
                [
                    "--new_config",
                    "--num_cpus",
                    threads,
                    "--out_config_path",
                    config,
                    "--biapy_version",
                    cls.VERSION,
                    "--workflow",
                    str(inputs.get("workflow", "semantic")),
                    "--dims",
                    str(inputs.get("is_3d", inputs.get("dims", "2d"))),
                    "--obj_slices",
                    str(inputs.get("obj_slices", "")),
                    "--obj_size",
                    str(inputs.get("obj_size", "0-25")),
                    "--img_channel",
                    str(inputs.get("img_channel", 1)),
                ]
            )
            model_source = str(inputs.get("model_source", "biapy") or "biapy")
            if model_source == "biapy_pretrained":
                cmd.extend(["--model_source", "biapy", "--model", checkpoint_file])
            elif model_source == "bmz_pretrained":
                cmd.extend(["--model_source", "bmz", "--model", str(inputs.get("bmz_model_name", ""))])
            else:
                cmd.extend(["--model_source", "biapy"])
        if mode == "custom_cfg":
            cmd.extend(["--out_config_path", config, "--biapy_version", cls.VERSION])
        phase = cls._phase(inputs)
        if phase in {"train_test", "train"} and _as_list(inputs.get("raw_train")):
            cmd.extend(["--raw_train", train_raw_dir])
            if _as_list(inputs.get("gt_train")):
                cmd.extend(["--gt_train", train_gt_dir])
        if phase in {"train_test", "test"} and _as_list(inputs.get("raw_test")):
            cmd.extend(["--test_raw_path", test_raw_dir])
            if _as_list(inputs.get("gt_test")):
                cmd.extend(["--test_gt_path", test_gt_dir])
        if mode == "custom_cfg" and inputs.get("biapy_model_path"):
            cmd.extend(["--model", checkpoint_file, "--model_source", "biapy"])
        return _shell_join(cmd).replace("'${GALAXY_SLOTS:-", "${GALAXY_SLOTS:-").replace("}'", "}")

    @classmethod
    def _raw_output_command(cls, out: str) -> str:
        result_dir = f"{out}/output/my_experiment/results/my_experiment_1"
        raw_dir = f"{out}/raw"
        candidates = [
            "per_image_instances",
            "full_image_instances",
            "per_image_binarized",
            "full_image_binarized",
            "full_image",
            "per_image_local_max_check",
            "as_3d_stack_binarized",
            "per_image",
        ]
        body = [f"mkdir -p {shlex.quote(raw_dir)} && {{ "]
        for index, candidate in enumerate(candidates):
            keyword = "if" if index == 0 else "elif"
            source = f"{result_dir}/{candidate}"
            body.append(f"{keyword} [ -d {shlex.quote(source)} ]; then mv {shlex.quote(source)}/* {shlex.quote(raw_dir)}/; ")
        predictions = f"{result_dir}/predictions.csv"
        body.append(f"elif [ -f {shlex.quote(predictions)} ]; then mv {shlex.quote(predictions)} {shlex.quote(raw_dir)}/; fi; }}")
        return "".join(body)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        checkpoint_file = f"{out}/output/my_experiment/checkpoints/checkpoint.safetensors"
        phase = cls._phase(inputs)
        outputs = cls._selected_outputs(inputs)
        command_parts = [
            "set -xeu",
            "export OPENCV_IO_ENABLE_OPENEXR=0",
            "WORKTMP=$(mktemp -d galaxy-torchinductor.XXXXXX)",
            "export TORCHINDUCTOR_CACHE_DIR=$WORKTMP/torchinductor",
            "mkdir -p $TORCHINDUCTOR_CACHE_DIR",
            _shell_join(["mkdir", "-p", f"{out}/output", f"{out}/output/my_experiment/checkpoints"]),
        ]
        if inputs.get("biapy_model_path"):
            command_parts.append(_shell_join(["ln", "-fs", str(inputs.get("biapy_model_path")), checkpoint_file]))
        command_parts.append(cls._yaml_command(inputs, out))
        if phase in {"train_test", "train"}:
            cls._stage_files(command_parts, _as_list(inputs.get("raw_train")), f"{out}/dataset/train/raw", "training")
            cls._stage_files(command_parts, _as_list(inputs.get("gt_train")), f"{out}/dataset/train/gt", "training-gt")
        if phase in {"train_test", "test"}:
            cls._stage_files(command_parts, _as_list(inputs.get("raw_test")), f"{out}/dataset/test/raw", "test")
            cls._stage_files(command_parts, _as_list(inputs.get("gt_test")), f"{out}/dataset/test/gt", "test-gt")
        command_parts.append(
            _shell_join(
                [
                    "biapy",
                    "--config",
                    f"{out}/config.yaml",
                    "--result_dir",
                    f"{out}/output",
                    "--name",
                    "my_experiment",
                    "--run_id",
                    "1",
                    "--gpu",
                    '${GALAXY_BIAPY_GPU_STRING:-""}',
                ]
            ).replace("'${GALAXY_BIAPY_GPU_STRING:-\"\"}'", '${GALAXY_BIAPY_GPU_STRING:-""}')
        )
        if phase in {"train_test", "test"}:
            if "raw" in outputs:
                command_parts.append(cls._raw_output_command(out))
            if "post_proc" in outputs:
                command_parts.append(_shell_join(["mkdir", "-p", f"{out}/post_proc"]))
            if "metrics" in outputs and _as_list(inputs.get("gt_test")):
                command_parts.append(
                    f"{_shell_join(['mkdir', '-p', f'{out}/metrics'])} && "
                    f"mv {shlex.quote(f'{out}/output/my_experiment/results/my_experiment_1/test_results_metrics.csv')} "
                    f"{shlex.quote(f'{out}/metrics/')} 2>/dev/null || true"
                )
        if phase in {"train_test", "train"}:
            if "tcharts" in outputs:
                command_parts.append(_shell_join(["mkdir", "-p", f"{out}/train_charts"]))
            if "tlogs" in outputs:
                command_parts.append(_shell_join(["mkdir", "-p", f"{out}/train_logs"]))
        if "checkpoint" in outputs:
            command_parts.append(_shell_join(["mkdir", "-p", f"{out}/checkpoints"]))
        return " && ".join(command_parts)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs: list[Path] = []
        selected = cls._selected_outputs(inputs)
        mapping = {
            "raw": out / "raw",
            "post_proc": out / "post_proc",
            "metrics": out / "metrics",
            "tcharts": out / "train_charts",
            "tlogs": out / "train_logs",
        }
        for option in ["raw", "post_proc", "metrics", "tcharts", "tlogs"]:
            if option in selected:
                path = mapping[option]
                path.mkdir(parents=True, exist_ok=True)
                outputs.append(path)
        outputs.append(out / "config.yaml")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {},
            "optional": {
                "selected_mode": (
                    "STRING",
                    {"default": "custom_cfg", "options": cls.MODES, "description": "Reuse an existing YAML config or create one"},
                ),
                "config_path": ("YAML", {"default": "", "description": "Existing BiaPy YAML configuration"}),
                "biapy_model_path": ("FILE", {"default": "", "description": "Optional BiaPy safetensors checkpoint"}),
                "workflow": (
                    "STRING",
                    {"default": "semantic", "options": cls.WORKFLOWS, "description": "BiaPy workflow type"},
                ),
                "phase": ("STRING", {"default": "train_test", "options": cls.PHASES}),
                "is_3d": ("STRING", {"default": "2d", "options": ["2d", "3d", "2d_stack"]}),
                "obj_slices": ("STRING", {"default": "", "options": ["", "1-5", "5-10", "10-20", "20-60", "60+"]}),
                "obj_size": ("STRING", {"default": "0-25", "options": ["0-25", "25-100", "100-200", "200-500", "500+"]}),
                "img_channel": ("INT", {"default": 1, "min": 1, "max": 10}),
                "model_source": ("STRING", {"default": "biapy", "options": cls.MODEL_SOURCES}),
                "bmz_model_name": ("STRING", {"default": ""}),
                "raw_train": ("FILE", {"default": [], "is_list": True, "description": "Training raw images"}),
                "gt_train": ("FILE", {"default": [], "is_list": True, "description": "Training target images"}),
                "raw_test": ("FILE", {"default": [], "is_list": True, "description": "Test raw images"}),
                "gt_test": ("FILE", {"default": [], "is_list": True, "description": "Optional test target images"}),
                "selected_outputs": (
                    "STRING",
                    {
                        "default": ["raw"],
                        "options": cls.OUTPUT_OPTIONS,
                        "multiple": True,
                        "description": "BiaPy output collections to expose",
                    },
                ),
                "create_yaml_script": (
                    "FILE",
                    {"default": "create_yaml.py", "advanced": True, "description": "Path to the Galaxy create_yaml.py helper"},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        mode = str(inputs.get("selected_mode", "custom_cfg") or "custom_cfg")
        if mode not in cls.MODES:
            return f"selected_mode must be one of: {', '.join(cls.MODES)}"
        if mode == "custom_cfg":
            if not str(inputs.get("config_path", "")).strip():
                return "config_path is required for custom_cfg mode"
            return True
        workflow = str(inputs.get("workflow", "semantic") or "semantic")
        if workflow not in cls.WORKFLOWS:
            return f"workflow must be one of: {', '.join(cls.WORKFLOWS)}"
        phase = cls._phase(inputs)
        if phase not in cls.PHASES:
            return f"phase must be one of: {', '.join(cls.PHASES)}"
        if phase in {"train_test", "train"} and not _as_list(inputs.get("raw_train")):
            return "raw_train is required when phase includes train"
        if phase in {"train_test", "test"} and not _as_list(inputs.get("raw_test")):
            return "raw_test is required when phase includes test"
        model_source = str(inputs.get("model_source", "biapy") or "biapy")
        if model_source not in cls.MODEL_SOURCES:
            return f"model_source must be one of: {', '.join(cls.MODEL_SOURCES)}"
        if model_source == "biapy_pretrained" and not str(inputs.get("biapy_model_path", "")).strip():
            return "biapy_model_path is required for BiaPy pretrained models"
        if model_source == "bmz_pretrained" and not str(inputs.get("bmz_model_name", "")).strip():
            return "bmz_model_name is required for BioImage Model Zoo models"
        return True

class BinningRefinerNode(CommandNode):
    """Improve metagenome bins by combining outputs from multiple binning programs."""

    NODE_ID = "bin_refiner"
    DISPLAY_NAME = "Binning refiner"
    REQUIRED_CONDA_PACKAGES = ["binning_refiner"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Refine metagenome bins from one or more FASTA bin sets and report refined-bin membership and source lengths."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Binning refiner",
        "Binning_refiner",
        "Binning refiner metagenome bins",
        "bin_refiner",
        "genome bins",
        "metagenome bin refinement",
        "contamination reduction",
        "refined bins",
    ]
    RETURN_TYPES = ("DIRECTORY", "TSV", "TSV")
    RETURN_NAMES = ("refined_bins", "refined_contigs", "sources_and_length")
    REQUIRED_EXECUTABLES = ["Binning_refiner"]
    DOCUMENTATION_URL = "https://github.com/songweizhi/Binning_refiner"
    CITATION_DOIS = ["10.1093/bioinformatics/btx086"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/btx086"]
    CITATION_TEXT = "Binning_refiner improves genome bins through the combination of different binning programs."
    VERSION = "1.4.3"
    SHELL = True

    @classmethod
    def _input_bins(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("input_bins", inputs.get("bins")))

    @classmethod
    def _element_identifiers(cls, inputs: dict[str, Any], input_bins: list[str]) -> list[str]:
        identifiers = _as_list(inputs.get("element_identifiers", inputs.get("identifiers")))
        return [
            _safe_identifier(identifiers[index]) if index < len(identifiers) and identifiers[index] else _safe_name(input_bin)
            for index, input_bin in enumerate(input_bins)
        ]

    @classmethod
    def _input_exts(cls, inputs: dict[str, Any], input_bins: list[str]) -> list[str]:
        raw_exts = _as_list(inputs.get("input_exts", inputs.get("exts")))
        exts: list[str] = []
        for index, input_bin in enumerate(input_bins):
            if index < len(raw_exts) and raw_exts[index]:
                ext = raw_exts[index].lstrip(".")
            else:
                suffixes = "".join(Path(input_bin).suffixes).lstrip(".")
                ext = suffixes or "fasta"
            exts.append(ext)
        return exts

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_dir = f"{out}/input_bin_dir"
        bins_dir = f"{input_dir}/bins"
        output_root = f"{out}/refined_Binning_refiner_outputs"
        input_bins = cls._input_bins(inputs)
        identifiers = cls._element_identifiers(inputs, input_bins)
        input_exts = cls._input_exts(inputs, input_bins)
        commands = [_shell_join(["mkdir", "-p", bins_dir])]
        for index, input_bin in enumerate(input_bins):
            staged = f"{bins_dir}/{identifiers[index]}.{input_exts[index]}"
            if input_exts[index].endswith(".gz") or input_exts[index].endswith("gz") or input_bin.endswith(".gz"):
                commands.append(f"gunzip -c {shlex.quote(input_bin)} > {shlex.quote(staged)}")
            else:
                commands.append(_shell_join(["ln", "-s", input_bin, staged]))
        commands.extend(
            [
                _shell_join(["Binning_refiner", "-i", input_dir, "-p", "refined", "-m", str(inputs.get("m", 512))]),
                _shell_join(["mv", f"{output_root}/refined_contigs.txt", f"{out}/refined_contigs.tsv"]),
                _shell_join(["mv", f"{output_root}/refined_sources_and_length.txt", f"{out}/sources_and_length.tsv"]),
            ]
        )
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        refined_bins = out / "refined_Binning_refiner_outputs" / "refined_refined_bins"
        refined_bins.mkdir(parents=True, exist_ok=True)
        return [refined_bins, out / "refined_contigs.tsv", out / "sources_and_length.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bins": (
                    "FASTA_LIST",
                    {
                        "multiple": True,
                        "description": "Binned FASTA or FASTA.GZ files produced by metagenome binning tools",
                    },
                ),
            },
            "optional": {
                "m": (
                    "INT",
                    {"default": 512, "min": 1, "description": "Minimum size in Kbp for a refined bin to be retained"},
                ),
                "element_identifiers": (
                    "STRING",
                    {"default": [], "multiple": True, "advanced": True, "description": "Optional Galaxy collection element names"},
                ),
                "input_exts": (
                    "STRING",
                    {"default": [], "multiple": True, "advanced": True, "description": "Optional datatype extensions for staged bins"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._input_bins(inputs):
            return "at least one binned FASTA is required"
        if int(inputs.get("m", 512)) < 1:
            return "minimum refined bin size must be >= 1 Kbp"
        return super().VALIDATE_INPUTS(inputs)

class BioExtBam2MsaNode(CommandNode):
    """Extract a FASTA multiple sequence alignment from an indexed BAM/SAM alignment."""

    NODE_ID = "bioext_bam2msa"
    DISPLAY_NAME = "Convert BAM"
    REQUIRED_CONDA_PACKAGES = ["python-bioext"]
    CATEGORY = "alignment"
    DESCRIPTION = "Convert indexed BAM or SAM alignments to a FASTA multiple sequence alignment with BioExt bam2msa."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BioExt",
        "bioext_bam2msa",
        "bam2msa",
        "Convert BAM",
        "BAM to FASTA MSA",
        "multiple sequence alignment",
        "alignment extraction",
        "HyPhy",
    ]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["bam2msa"]
    DOCUMENTATION_URL = BIOEXT_DOCUMENTATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [BIOEXT_CITATION_URL]
    CITATION_TEXT = BIOEXT_CITATION_TEXT
    VERSION = "0.21.10+galaxy0"
    SHELL = True

    @classmethod
    def _region_values(cls, inputs: dict[str, Any]) -> tuple[int, int]:
        start = int(inputs.get("region_start", 0) or 0)
        end = int(inputs.get("region_end", 0) or 0)
        return start, end

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_bam = f"{out}/input_bam"
        input_index = f"{input_bam}.bai"
        output = f"{out}/output.fasta"
        cmd = [
            f"ln -sf {shlex.quote(str(inputs.get('input', '')))} {shlex.quote(input_bam)}",
            f"ln -sf {shlex.quote(str(inputs.get('bam_index', inputs.get('input_index', ''))))} {shlex.quote(input_index)}",
        ]
        bam2msa = ["bam2msa"]
        start, end = cls._region_values(inputs)
        if start and end:
            bam2msa.extend(["-r", f"{start}:{end}"])
        bam2msa.extend([input_bam, output])
        cmd.append(_shell_join(bam2msa))
        return " && ".join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.fasta"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "Indexed BAM or SAM alignment to convert to a FASTA alignment"}),
            },
            "optional": {
                "bam_index": ("FILE", {"description": "BAM index used by bam2msa"}),
                "region_start": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Optional starting coordinate for region extraction"},
                ),
                "region_end": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Optional ending coordinate for region extraction"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input BAM/SAM file is required"
        start, end = cls._region_values(inputs)
        if bool(start) != bool(end):
            return "region_start and region_end must be provided together"
        if start and end < start:
            return "region_end must be greater than or equal to region_start"
        return super().VALIDATE_INPUTS(inputs)

class BioExtBealignNode(CommandNode):
    """Align FASTA reads to a reference with BioExt bealign."""

    NODE_ID = "bioext_bealign"
    DISPLAY_NAME = "Align sequences"
    REQUIRED_CONDA_PACKAGES = ["python-bioext", "gawk", "samtools"]
    CATEGORY = "alignment"
    DESCRIPTION = "Align FASTA sequences to a preset or history reference using BioExt bealign's codon-aware algorithm."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BioExt",
        "bioext_bealign",
        "bealign",
        "Align sequences",
        "codon alignment",
        "reference alignment",
        "BAM alignment",
        "TN-93",
        "HyPhy",
    ]
    RETURN_TYPES = ("BAM", "BAM", "FASTA", "FASTA")
    RETURN_NAMES = ("output", "background", "saved_reference", "discarded_reads")
    REQUIRED_EXECUTABLES = ["bealign", "samtools", "gawk", "sed"]
    DOCUMENTATION_URL = BIOEXT_DOCUMENTATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [BIOEXT_CITATION_URL]
    CITATION_TEXT = BIOEXT_CITATION_TEXT
    VERSION = "0.21.10+galaxy0"
    SHELL = True

    PRESET_REFERENCES = [
        "HXB2_tat",
        "HXB2_gag",
        "HXB2_pol",
        "HXB2_int",
        "HXB2_vif",
        "HXB2_pr",
        "HXB2_vpr",
        "NL4-3_prrt",
        "HXB2_nef",
        "HXB2_env",
        "HXB2_rt",
        "HXB2_prrt",
        "HXB2_rev",
        "HXB2_vpu",
        "CoV2-3C",
        "CoV2-S",
        "CoV2-E",
        "CoV2-M",
        "CoV2-N",
        "CoV2-endornase",
        "CoV2-exonuclease",
        "CoV2-helicase",
        "CoV2-leader",
        "CoV2-methyltransferase",
        "CoV2-nsp2",
        "CoV2-nsp3",
        "CoV2-nsp4",
        "CoV2-nsp6",
        "CoV2-nsp7",
        "CoV2-nsp8",
        "CoV2-nsp9",
        "CoV2-nsp10",
        "CoV2-ORF1a",
        "CoV2-ORF1b",
        "CoV2-ORF3a",
        "CoV2-ORF5",
        "CoV2-ORF6",
        "CoV2-ORF7a",
        "CoV2-ORF7b",
        "CoV2-ORF8",
        "CoV2-ORF10",
        "CoV2-RdRp",
    ]
    ALPHABETS = ["codon", "dna", "amino"]
    SCORE_MATRICES = [
        "BLOSUM62",
        "DNA65",
        "DNA70",
        "DNA88",
        "DNA80",
        "DNA95",
        "PAM200",
        "PAM250",
        "HIV_BETWEEN_F",
    ]

    @classmethod
    def _reference_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("reference_type", "preset") or "preset")

    @classmethod
    def _reference(cls, inputs: dict[str, Any]) -> str:
        default = "CoV2-nsp8" if cls._reference_type(inputs) == "preset" else ""
        return str(inputs.get("reference", default) or default)

    @classmethod
    def _threads(cls, inputs: dict[str, Any]) -> int:
        return int(inputs.get("threads", 2) or 2)

    @classmethod
    def _sanitize_command(cls, source: str, target: str) -> str:
        return f"cat {shlex.quote(source)} {BIOEXT_SANITIZE_PIPE} {shlex.quote(target)}"

    @classmethod
    def _bealign_command(
        cls,
        inputs: dict[str, Any],
        source_fasta: str,
        output_bam: str,
        *,
        background: bool = False,
    ) -> str:
        out = _out(inputs)
        threads = cls._threads(inputs)
        cmd = [
            "bealign",
            "--reference",
            cls._reference(inputs),
            "--alphabet",
            str(inputs.get("alphabet", "codon") or "codon"),
        ]
        expected_identity = inputs.get("expected_identity")
        if expected_identity is not None and str(expected_identity) != "":
            cmd.extend(["--expected-identity", str(expected_identity)])
        if background:
            cmd.append("--keep-reference")
        elif inputs.get("discard"):
            cmd.extend(["--discard", f"{out}/discarded_reads.fasta"])
        cmd.extend(["--score-matrix", str(inputs.get("score_matrix", "BLOSUM62") or "BLOSUM62")])
        if inputs.get("reverse_complement"):
            cmd.append("--reverse-complement")
        if not background and inputs.get("keep_reference"):
            cmd.append("--keep-reference")
        cmd.extend(["--no-sort", source_fasta, output_bam])
        return f"NCPU=${{GALAXY_SLOTS:-{threads}}} {_shell_join(cmd)}"

    @classmethod
    def _has_background(cls, inputs: dict[str, Any]) -> bool:
        return bool(str(inputs.get("background_sequences", inputs.get("sequences", ""))).strip())

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        threads = cls._threads(inputs)
        reads = f"{out}/reads.fa"
        raw_bam = f"{out}/bealign_out.bam"
        output = f"{out}/output.bam"
        commands = [
            "set -o pipefail",
            cls._sanitize_command(str(inputs.get("input", "")), reads),
            cls._bealign_command(inputs, reads, raw_bam),
            f"samtools sort -@${{GALAXY_SLOTS:-{threads}}} -T ${{TMPDIR:-.}} -O bam -o {shlex.quote(output)} {shlex.quote(raw_bam)}",
        ]

        if cls._has_background(inputs):
            background_fasta = f"{out}/background.fa"
            background_bam = f"{out}/bealign_background.bam"
            background_output = f"{out}/background.bam"
            background_source = str(inputs.get("background_sequences", inputs.get("sequences", "")))
            commands.extend(
                [
                    cls._sanitize_command(background_source, background_fasta),
                    cls._bealign_command(inputs, background_fasta, background_bam, background=True),
                    f"samtools sort -@${{GALAXY_SLOTS:-{threads}}} -T ${{TMPDIR:-.}} -O bam -o "
                    f"{shlex.quote(background_output)} {shlex.quote(background_bam)}",
                ]
            )

        if cls._reference_type(inputs) == "preset" and inputs.get("save_reference"):
            commands.append(
                _shell_join(
                    [
                        "python",
                        str(inputs.get("copy_reference_script", "copy_reference.py")),
                        "--reference",
                        cls._reference(inputs),
                        "--dataset",
                        f"{out}/saved_reference.fasta",
                    ]
                )
            )
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "output.bam"]
        if cls._has_background(inputs):
            outputs.append(out / "background.bam")
        if cls._reference_type(inputs) == "preset" and inputs.get("save_reference"):
            outputs.append(out / "saved_reference.fasta")
        if inputs.get("discard"):
            outputs.append(out / "discarded_reads.fasta")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (
                    "FASTA",
                    {"description": "FASTA reads to sanitize and align against the selected reference"},
                ),
            },
            "optional": {
                "reference_type": ("STRING", {"default": "preset", "options": ["preset", "dataset"]}),
                "reference": ("FASTA", {"description": "Preset reference key or history FASTA reference"}),
                "save_reference": ("BOOLEAN", {"default": False, "description": "Save a selected BioExt preset reference"}),
                "background_source": ("STRING", {"default": "data_table", "options": ["data_table", "history"]}),
                "background_sequences": ("FASTA", {"description": "Optional background FASTA sequences"}),
                "expected_identity": (
                    "FLOAT",
                    {"default": "", "min": 0, "max": 1, "description": "Discard sequences below this identity"},
                ),
                "alphabet": ("STRING", {"default": "codon", "options": cls.ALPHABETS}),
                "score_matrix": ("STRING", {"default": "BLOSUM62", "options": cls.SCORE_MATRICES}),
                "discard": ("BOOLEAN", {"default": False, "description": "Write discarded reads to FASTA"}),
                "reverse_complement": ("BOOLEAN", {"default": False}),
                "keep_reference": ("BOOLEAN", {"default": False}),
                "copy_reference_script": ("FILE", {"default": "copy_reference.py", "advanced": True}),
                "threads": ("INT", {"default": 2, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input FASTA reads are required"
        reference_type = cls._reference_type(inputs)
        if reference_type not in {"preset", "dataset"}:
            return "reference_type must be one of: preset, dataset"
        reference = cls._reference(inputs)
        if reference_type == "dataset" and not reference:
            return "reference FASTA is required when reference_type is dataset"
        if reference_type == "preset" and reference not in cls.PRESET_REFERENCES:
            return "reference must be one of the BioExt preset references"
        alphabet = str(inputs.get("alphabet", "codon") or "codon")
        if alphabet not in cls.ALPHABETS:
            return f"alphabet must be one of: {', '.join(cls.ALPHABETS)}"
        score_matrix = str(inputs.get("score_matrix", "BLOSUM62") or "BLOSUM62")
        if score_matrix not in cls.SCORE_MATRICES:
            return f"score_matrix must be one of: {', '.join(cls.SCORE_MATRICES)}"
        expected_identity = inputs.get("expected_identity")
        if expected_identity is not None and str(expected_identity) != "":
            identity = float(expected_identity)
            if identity < 0 or identity > 1:
                return "expected_identity must be between 0 and 1"
        return super().VALIDATE_INPUTS(inputs)

class BeagleNode(CommandNode):
    """Phase genotypes and impute ungenotyped markers with Beagle."""

    NODE_ID = "beagle"
    DISPLAY_NAME = "Beagle"
    REQUIRED_CONDA_PACKAGES = ["beagle"]
    CATEGORY = "variant"
    DESCRIPTION = "Phase genotypes and impute ungenotyped markers from VCF genotype data using Beagle."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Beagle",
        "Beagle genotype imputation",
        "genotype phasing",
        "impute ungenotyped markers",
        "haplotype phasing",
        "VCF imputation",
        "GWAS",
    ]
    RETURN_TYPES = ("VCF", "TXT")
    RETURN_NAMES = ("vcf_file", "log_file")
    REQUIRED_EXECUTABLES = ["beagle"]
    DOCUMENTATION_URL = "https://faculty.washington.edu/browning/beagle/beagle.html"
    CITATION_DOIS = ["10.1016/j.ajhg.2018.07.015", "10.1086/521987"]
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in CITATION_DOIS]
    CITATION_TEXT = "Beagle supports genotype phasing, genotype imputation, and haplotype inference from genotype data."
    VERSION = "5.4_29Oct24.c8e"
    SHELL = True

    @classmethod
    def _bool_text(cls, value: Any, default: bool) -> str:
        if value is None or value == "":
            value = default
        if isinstance(value, str):
            return "false" if value.lower() in {"false", "0", "no"} else "true"
        return "true" if bool(value) else "false"

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        return "phased_imputed.vcf.gz" if str(inputs.get("out_format", "vcf")) == "vcf_bgzip" else "phased_imputed.vcf"

    @classmethod
    def _ref_path(cls, inputs: dict[str, Any], out: str) -> str:
        ref_ext = str(inputs.get("ref_ext", Path(str(inputs.get("ref", "ref.vcf"))).suffix.lstrip(".") or "vcf"))
        return f"{out}/ref.{ref_ext}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd: list[str] = []
        if inputs.get("ref"):
            cmd.extend(["ln", "-s", str(inputs.get("ref")), cls._ref_path(inputs, out), "&&"])
        gt = str(inputs.get("gt", ""))
        gt_arg = gt
        if str(inputs.get("gt_ext", "")).lower() == "vcf_bgzip":
            gt_arg = f"{out}/tmp.gz"
            cmd.extend(["ln", "-s", gt, gt_arg, "&&"])

        cmd.extend(["beagle", f"gt={gt_arg}"])
        if inputs.get("ref"):
            cmd.append(f"ref={cls._ref_path(inputs, out)}")
        for key in ["map", "chrom", "excludesamples", "excludemarkers"]:
            if inputs.get(key):
                cmd.append(f"{key}={inputs[key]}")
        cmd.extend(
            [
                f"ne={inputs.get('ne', 1000000)}",
                f"window={inputs.get('window', 40.0)}",
                f"overlap={inputs.get('overlap', 2.0)}",
            ]
        )
        if inputs.get("seed") not in (None, ""):
            cmd.append(f"seed={inputs.get('seed')}")
        if inputs.get("err") not in (None, ""):
            cmd.append(f"err={inputs.get('err')}")
        cmd.extend(
            [
                f"burnin={inputs.get('burnin', 3)}",
                f"iterations={inputs.get('iterations', 12)}",
                f"phase-states={inputs.get('phase_states', inputs.get('phase-states', 280))}",
                f"impute={cls._bool_text(inputs.get('impute'), True)}",
                f"imp-states={inputs.get('imp_states', inputs.get('imp-states', 1600))}",
                f"imp-segment={inputs.get('imp_segment', inputs.get('imp-segment', 6.0))}",
                f"imp-step={inputs.get('imp_step', inputs.get('imp-step', 0.1))}",
                f"cluster={inputs.get('cluster', 0.005)}",
                f"ap={cls._bool_text(inputs.get('ap'), False)}",
                f"gp={cls._bool_text(inputs.get('gp'), False)}",
                f"out={out}/out",
                f"nthreads=${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}",
            ]
        )
        if str(inputs.get("out_format", "vcf")) == "vcf_bgzip":
            cmd.extend(["&&", "mv", f"{out}/out.vcf.gz", f"{out}/phased_imputed.vcf.gz"])
        else:
            cmd.extend(["&&", "gunzip", f"{out}/out.vcf.gz", "&&", "mv", f"{out}/out.vcf", f"{out}/phased_imputed.vcf"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / cls._output_name(inputs)]
        if inputs.get("output_log"):
            outputs.append(out / "out.log")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "gt": ("VCF", {"description": "VCF file containing genotypes for study samples"}),
            },
            "optional": {
                "gt_ext": ("STRING", {"default": "vcf", "options": ["vcf", "vcf_bgzip"], "advanced": True}),
                "ref": ("VCF", {"default": "", "description": "Optional phased reference panel in VCF or bref3 format"}),
                "ref_ext": ("STRING", {"default": "vcf", "options": ["vcf", "vcf_bgzip", "bref3"], "advanced": True}),
                "map": ("TXT", {"default": "", "description": "Optional PLINK genetic map in cM units"}),
                "chrom": ("STRING", {"default": "", "description": "Optional chromosome interval such as 22:100-"}),
                "excludesamples": ("TXT", {"default": "", "description": "Samples to exclude from analysis"}),
                "excludemarkers": ("TXT", {"default": "", "description": "Markers to exclude from analysis"}),
                "ne": ("INT", {"default": 1000000, "min": 0, "description": "Effective population size"}),
                "window": ("FLOAT", {"default": 40.0, "min": 0, "description": "Window length in cM"}),
                "overlap": ("FLOAT", {"default": 2.0, "min": 0, "description": "Window overlap in cM"}),
                "err": ("FLOAT", {"default": "", "min": 0, "max": 1, "description": "Allele mismatch probability"}),
                "seed": ("INT", {"default": "", "description": "Random seed"}),
                "output_log": ("BOOLEAN", {"default": False, "description": "Keep Beagle log file"}),
                "burnin": ("INT", {"default": 3, "min": 0, "description": "Maximum burn-in iterations"}),
                "iterations": ("INT", {"default": 12, "min": 0, "description": "Phasing iterations"}),
                "phase_states": ("INT", {"default": 280, "min": 0, "description": "Model states for phasing"}),
                "impute": ("BOOLEAN", {"default": True, "description": "Impute markers present in the reference panel"}),
                "imp_states": ("INT", {"default": 1600, "min": 0, "description": "Model states for imputation"}),
                "imp_segment": ("FLOAT", {"default": 6.0, "min": 0, "description": "Minimum cM length of imputation haplotype segments"}),
                "imp_step": ("FLOAT", {"default": 0.1, "min": 0, "description": "Step length in cM for short IBS detection"}),
                "cluster": ("FLOAT", {"default": 0.005, "min": 0, "description": "Maximum cM distance in a marker cluster"}),
                "ap": ("BOOLEAN", {"default": False, "description": "Include posterior allele probabilities"}),
                "gp": ("BOOLEAN", {"default": False, "description": "Include posterior genotype probabilities"}),
                "out_format": ("STRING", {"default": "vcf", "options": ["vcf", "vcf_bgzip"], "description": "Output VCF datatype"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("gt", "")).strip():
            return "VCF genotype input is required"
        window = float(inputs.get("window", 40.0) or 0)
        overlap = float(inputs.get("overlap", 2.0) or 0)
        if window < overlap * 1.1:
            return "window must be at least 1.1 times overlap"
        if inputs.get("err") not in (None, ""):
            err = float(inputs.get("err", 0))
            if err < 0 or err > 1:
                return "err must be between 0 and 1"
        return super().VALIDATE_INPUTS(inputs)

class BreseqNode(CommandNode):
    """Detect and annotate mutations in haploid microbial resequencing data with breseq."""

    NODE_ID = "breseq"
    DISPLAY_NAME = "breseq"
    REQUIRED_CONDA_PACKAGES = ["breseq", "tar"]
    CATEGORY = "variant"
    DESCRIPTION = "Find mutations in haploid microbial genomes and annotate GenomeDiff variants with breseq and gdtools."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "breseq",
        "breseq mutation detection",
        "GenomeDiff",
        "gdtools ANNOTATE",
        "microbial resequencing",
        "haploid microbial genomes",
        "laboratory evolution",
    ]
    RETURN_TYPES = ("HTML_REPORT", "HTML_REPORT", "TSV", "TSV", "ZIP", "TXT", "TSV", "PHYLIP", "JSON")
    RETURN_NAMES = ("report", "annreport", "output", "genomediff", "zip_output", "log", "tabdelim", "phylipout", "jsonout")
    REQUIRED_EXECUTABLES = ["breseq", "gdtools", "tar"]
    DOCUMENTATION_URL = "https://barricklab.org/twiki/bin/view/Lab/ToolsBacterialGenomeResequencing"
    CITATION_DOIS = ["10.1007/978-1-4939-0554-6_12"]
    CITATION_URLS = [f"{DOI_URL}10.1007/978-1-4939-0554-6_12"]
    CITATION_TEXT = "Identification of mutations in laboratory-evolved microbes from next-generation sequencing data using breseq."
    VERSION = "0.35.5"
    SHELL = True

    DETECT_OUTPUTS = {
        "html": "report.html",
        "gd": "output.gd",
        "zip": "results.tar.gz",
        "log": "log.txt",
    }
    ANNOTATE_OUTPUTS = {
        "html": "annotated_report.html",
        "gd": "annotated.gd",
        "tsv": "annotated.tsv",
        "phylip": "comparison.phy",
        "json": "annotated.json",
    }

    @classmethod
    def _formats(cls, inputs: dict[str, Any]) -> list[str]:
        raw = inputs.get("formats", inputs.get("output_formats"))
        if raw is None or raw == "":
            return ["phylip"] if str(inputs.get("mode", "detect")) == "compare" else ["gd"]
        if isinstance(raw, str):
            return [part.strip() for part in raw.split(",") if part.strip()]
        return [str(value) for value in raw if str(value)]

    @classmethod
    def _references(cls, inputs: dict[str, Any]) -> list[str]:
        refs = _as_list(inputs.get("references", inputs.get("own_genome")))
        refs.extend(_as_list(inputs.get("fixed_references", inputs.get("fixed_genome"))))
        return refs

    @classmethod
    def _add_references(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        for reference in cls._references(inputs):
            cmd.extend(["--reference", reference])

    @classmethod
    def _detect_command(cls, inputs: dict[str, Any], out: str) -> list[str]:
        results_dir = f"{out}/results"
        cmd = ["breseq", "--num-processors", f"${{GALAXY_SLOTS:-{inputs.get('threads', 4)}}}", "-o", results_dir]
        cls._add_references(cmd, inputs)
        cmd.extend(_as_list(inputs.get("fastqs", inputs.get("reads"))))
        if inputs.get("name"):
            cmd.extend(["--name", str(inputs.get("name"))])
        polymorphism = inputs.get("polymorphism_prediction")
        if isinstance(polymorphism, str):
            if polymorphism.strip():
                cmd.append(polymorphism)
        elif polymorphism:
            cmd.append("--polymorphism-prediction")
        if inputs.get("predict_junctions") is False:
            cmd.append("--no-junction-prediction")

        formats = set(cls._formats(inputs))
        if "gd" in formats:
            cmd.extend(["&&", "cp", f"{results_dir}/output/output.gd", f"{out}/output.gd"])
        if "html" in formats:
            cmd.extend(
                [
                    "&&",
                    "cp",
                    f"{results_dir}/output/index.html",
                    f"{out}/report.html",
                    "&&",
                    "mkdir",
                    "-p",
                    f"{out}/report_extra_files",
                    "&&",
                    "cp",
                    "-R",
                    f"{results_dir}/output/.",
                    f"{out}/report_extra_files",
                ]
            )
        if "zip" in formats:
            cmd.extend(["&&", "tar", "-zcf", f"{out}/results.tar.gz", results_dir])
        if "log" in formats:
            cmd.extend(["&&", "cp", f"{results_dir}/output/log.txt", f"{out}/log.txt"])
        return cmd

    @classmethod
    def _annotate_output(cls, output_format: str, out: str) -> str:
        return f"{out}/{cls.ANNOTATE_OUTPUTS.get(output_format, f'annotated.{output_format}')}"

    @classmethod
    def _annotate_command(cls, inputs: dict[str, Any], out: str) -> list[str]:
        commands: list[str] = []
        for index, output_format in enumerate(cls._formats(inputs)):
            if index:
                commands.append("&&")
            commands.extend(["gdtools", "ANNOTATE", "--format", output_format, "-o", cls._annotate_output(output_format, out)])
            cls._add_references(commands, inputs)
            commands.extend(_as_list(inputs.get("gds", inputs.get("genomediffs"))))
        return commands

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        if str(inputs.get("mode", "detect")) == "detect":
            return cls._detect_command(inputs, out)
        return cls._annotate_command(inputs, out)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        formats = set(cls._formats(inputs))
        if str(inputs.get("mode", "detect")) == "detect":
            return [out / cls.DETECT_OUTPUTS[fmt] for fmt in ["html", "gd", "zip", "log"] if fmt in formats]
        return [out / cls.ANNOTATE_OUTPUTS[fmt] for fmt in ["html", "gd", "tsv", "phylip", "json"] if fmt in formats]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "references": (
                    "FILE_LIST",
                    {"multiple": True, "description": "One or more FASTA or GenBank reference genomes"},
                ),
            },
            "optional": {
                "mode": ("STRING", {"default": "detect", "options": ["detect", "annotate", "compare"], "description": "Run breseq variant detection or gdtools annotation/comparison"}),
                "fastqs": ("FASTQ_LIST", {"description": "FASTQ reads for detect mode"}),
                "gds": ("TSV_LIST", {"description": "GenomeDiff files for annotate or compare mode"}),
                "formats": ("STRING_LIST", {"description": "Output formats selected in the Galaxy wrapper"}),
                "polymorphism_prediction": (
                    "BOOLEAN",
                    {"default": False, "description": "Detect polymorphic variants rather than consensus mutations"},
                ),
                "name": ("STRING", {"default": "", "description": "Human-readable analysis name"}),
                "predict_junctions": ("BOOLEAN", {"default": True, "description": "Predict new sequence junctions"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._references(inputs):
            return "at least one reference genome is required"
        mode = str(inputs.get("mode", "detect"))
        if mode == "detect" and not _as_list(inputs.get("fastqs", inputs.get("reads"))):
            return "at least one FASTQ read file is required for detect mode"
        if mode in {"annotate", "compare"}:
            gds = _as_list(inputs.get("gds", inputs.get("genomediffs")))
            if not gds:
                return "at least one GenomeDiff input is required for annotate or compare mode"
            if mode == "compare" and len(gds) < 2:
                return "compare mode requires at least two GenomeDiff inputs"
        return super().VALIDATE_INPUTS(inputs)

class BiSCoTNode(CommandNode):
    """Improve Bionano optical-map scaffolding with BiSCoT."""

    NODE_ID = "biscot"
    DISPLAY_NAME = "BiSCoT"
    REQUIRED_CONDA_PACKAGES = ["biscot", "blat", "ucsc-pslsort", "ucsc-pslreps"]
    CATEGORY = "assembly"
    DESCRIPTION = "Correct Bionano optical-map scaffolds by merging contigs, re-estimating gaps, and writing FASTA and AGP scaffolds."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BiSCoT",
        "BiSCoT optical map",
        "Bionano scaffolding correction",
        "optical maps",
        "CMAP",
        "XMAP",
        "AGP scaffolds",
    ]
    RETURN_TYPES = ("TXT", "FASTA", "AGP")
    RETURN_NAMES = ("log", "fasta", "agp")
    REQUIRED_EXECUTABLES = ["biscot"]
    DOCUMENTATION_URL = "https://github.com/institut-de-genomique/biscot"
    CITATION_DOIS = ["10.7717/peerj.10150"]
    CITATION_URLS = [f"{DOI_URL}10.7717/peerj.10150"]
    CITATION_TEXT = "BiSCoT: improving large eukaryotic genome assemblies with optical maps."
    VERSION = "2.3.3"
    SHELL = True

    @classmethod
    def _secondary_cmap(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("secondary_map_cmap_2", inputs.get("cmap_2", "")) or "")

    @classmethod
    def _secondary_xmap(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("secondary_map_xmap_2", inputs.get("xmap_2", "")) or "")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = [
            "biscot",
            "--cmap-ref",
            str(inputs.get("cmap_ref", "")),
            "--cmap-1",
            str(inputs.get("cmap_1", "")),
            "--xmap-1",
            str(inputs.get("xmap_1", "")),
            "--key",
            str(inputs.get("key", "")),
            "--contigs",
            str(inputs.get("contigs", "")),
        ]
        secondary_cmap = cls._secondary_cmap(inputs)
        secondary_xmap = cls._secondary_xmap(inputs)
        if secondary_cmap:
            cmd.extend(["--cmap-2", secondary_cmap, "--xmap-2", secondary_xmap])
        if inputs.get("xmap_2enz"):
            cmd.extend(["--xmap-2enz", str(inputs.get("xmap_2enz"))])
        if inputs.get("only_confirmed_pos"):
            cmd.append("--only-confirmed-pos")
        if inputs.get("log_file"):
            cmd.extend(["&&", "cp", "biscot/biscot.log", f"{out}/biscot.log"])
        cmd.extend(
            [
                "&&",
                "cp",
                "biscot/scaffolds.fasta",
                f"{out}/scaffolds.fasta",
                "&&",
                "cp",
                "biscot/scaffolds.agp",
                f"{out}/scaffolds.agp",
            ]
        )
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = []
        if inputs.get("log_file"):
            outputs.append(out / "biscot.log")
        outputs.extend([out / "scaffolds.fasta", out / "scaffolds.agp"])
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "cmap_ref": ("FILE", {"description": "Reference anchor CMAP file from Bionano scaffolding"}),
                "cmap_1": ("FILE", {"description": "Primary query CMAP file describing contig labels"}),
                "xmap_1": ("FILE", {"description": "Primary XMAP alignment file for contig labels on the anchor"}),
                "key": ("TSV", {"description": "Bionano key file mapping maps to contig names"}),
                "contigs": ("FASTA", {"description": "Contig FASTA previously scaffolded with Bionano"}),
            },
            "optional": {
                "secondary_map_cmap_2": ("FILE", {"default": "", "description": "Optional secondary-enzyme query CMAP file"}),
                "secondary_map_xmap_2": ("FILE", {"default": "", "description": "Optional secondary-enzyme XMAP file"}),
                "xmap_2enz": ("FILE", {"default": "", "description": "Optional two-enzyme XMAP file confirming label mappings"}),
                "only_confirmed_pos": (
                    "BOOLEAN",
                    {"default": False, "description": "Retain only alignment positions confirmed by the two-enzyme XMAP"},
                ),
                "log_file": ("BOOLEAN", {"default": False, "description": "Export the BiSCoT log file"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for field in ["cmap_ref", "cmap_1", "xmap_1", "key", "contigs"]:
            if not str(inputs.get(field, "")).strip():
                return f"{field} is required"
        secondary_cmap = cls._secondary_cmap(inputs)
        secondary_xmap = cls._secondary_xmap(inputs)
        if secondary_cmap and not secondary_xmap:
            return "secondary_map_xmap_2 is required when secondary_map_cmap_2 is provided"
        if secondary_xmap and not secondary_cmap:
            return "secondary_map_cmap_2 is required when secondary_map_xmap_2 is provided"
        return super().VALIDATE_INPUTS(inputs)

class BiGSCAPENode(CommandNode):
    """Construct BGC sequence similarity networks and gene cluster families with BiG-SCAPE."""

    NODE_ID = "bigscape"
    DISPLAY_NAME = "BiG-SCAPE"
    REQUIRED_CONDA_PACKAGES = ["bigscape"]
    CATEGORY = "secondary_metabolism"
    DESCRIPTION = "Construct sequence similarity networks of biosynthetic gene clusters and group them into gene cluster families."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BiG-SCAPE",
        "BiG-SCAPE gene cluster families",
        "biosynthetic gene clusters",
        "BGC networks",
        "GCF clustering",
        "MIBiG",
        "Pfam-A",
    ]
    RETURN_TYPES = ("HTML_REPORT", "DIRECTORY", "DIRECTORY", "DIRECTORY", "DIRECTORY", "TXT")
    RETURN_NAMES = ("html", "network_annotations", "clan_tables", "clustering_tables", "network_files", "logfile")
    REQUIRED_EXECUTABLES = ["bigscape", "hmmpress"]
    DOCUMENTATION_URL = "https://github.com/medema-group/BiG-SCAPE"
    CITATION_DOIS = ["10.1038/s41589-019-0400-9"]
    CITATION_URLS = [f"{DOI_URL}10.1038/s41589-019-0400-9"]
    CITATION_TEXT = "BiG-SCAPE and CORASON identify biosynthetic gene cluster families."
    VERSION = "1.1.9"
    SHELL = True

    MIBIG_OPTIONS = ["", "--mibig", "--mibig21", "--mibig14", "--mibig13"]

    @classmethod
    def _inputs(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("inputdir", inputs.get("inputs")))

    @classmethod
    def _identifiers(cls, inputs: dict[str, Any], files: list[str]) -> list[str]:
        identifiers = _as_list(inputs.get("element_identifiers", inputs.get("identifiers")))
        return [
            _safe_identifier(identifiers[index]) if index < len(identifiers) and identifiers[index] else _safe_name(path)
            for index, path in enumerate(files)
        ]

    @classmethod
    def _cutoffs(cls, inputs: dict[str, Any]) -> list[str]:
        cutoffs = _as_list(inputs.get("cutoffs", inputs.get("cutoff")))
        return cutoffs or ["0.3"]

    @classmethod
    def _clan_cutoff(cls, inputs: dict[str, Any]) -> list[str]:
        raw = _as_list(inputs.get("clan_cutoff", inputs.get("clan_cutoffs")))
        if len(raw) >= 2:
            return raw[:2]
        return []

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        input_dir = f"{out}/input"
        result_dir = f"{out}/result"
        pfam_dir = f"{out}/pfam"
        html_files = f"{out}/html_extra_files"
        cmd = ["mkdir", "-p", html_files, result_dir, input_dir, pfam_dir]
        input_files = cls._inputs(inputs)
        for path, identifier in zip(input_files, cls._identifiers(inputs, input_files), strict=False):
            cmd.extend(["&&", "ln", "-s", path, f"{input_dir}/region.{identifier}.gbk"])
        cmd.extend(["&&", "ln", "-s", str(inputs.get("pfam_dir", "")), f"{pfam_dir}/Pfam-A.hmm"])
        cmd.extend(["&&", "hmmpress", f"{pfam_dir}/Pfam-A.hmm"])
        anchorfile = str(inputs.get("anchorfile", "") or "")
        anchor_identifier = _safe_identifier(str(inputs.get("anchor_identifier", Path(anchorfile).name or "anchorfile.txt")))
        if anchorfile:
            cmd.extend(["&&", "ln", "-s", anchorfile, f"{out}/{anchor_identifier}"])
        cmd.extend(
            [
                "&&",
                "bigscape",
                "--inputdir",
                input_dir,
            ]
        )
        mibig = str(inputs.get("mibig", "") or "")
        if mibig:
            cmd.append(mibig)
        cmd.extend(["--outputdir", result_dir])
        if inputs.get("label"):
            cmd.extend(["--label", str(inputs.get("label"))])
        cmd.extend(["--pfam_dir", pfam_dir, "--cores", f"${{GALAXY_SLOTS:-{inputs.get('threads', 8)}}}"])
        if inputs.get("verbose"):
            cmd.append("--verbose")
        if inputs.get("include_singletons"):
            cmd.append("--include_singletons")
        cmd.extend(
            [
                "--domain_overlap_cutoff",
                str(inputs.get("domain_overlap_cutoff", 0.1)),
                "--min_bgc_size",
                str(inputs.get("min_big_size", inputs.get("min_bgc_size", 0))),
            ]
        )
        if inputs.get("mix"):
            cmd.append("--mix")
        if inputs.get("no_classify"):
            cmd.append("--no_classify")
        banned_classes = _as_list(inputs.get("banned_classes"))
        if banned_classes:
            cmd.append("--banned_classes")
            cmd.extend(banned_classes)
        cmd.append("--cutoffs")
        cmd.extend(cls._cutoffs(inputs))
        if inputs.get("clans_off"):
            cmd.append("--clans-off")
        clan_cutoff = cls._clan_cutoff(inputs)
        if clan_cutoff:
            cmd.extend(["--clan_cutoff", *clan_cutoff])
        if inputs.get("hybrids_off"):
            cmd.append("--hybrids-off")
        cmd.extend(["--mode", str(inputs.get("mode", "glocal"))])
        if anchorfile:
            cmd.extend(["--anchorfile", anchor_identifier])
        if inputs.get("force_hmmscan"):
            cmd.append("--force_hmmscan")
        if inputs.get("domain_includelist"):
            cmd.append("--domain_includelist")
        if inputs.get("log"):
            cmd.extend([">", f"{out}/log.txt"])
        cmd.extend(
            [
                "&&",
                "cp",
                f"{result_dir}/index.html",
                f"{out}/index.html",
                "&&",
                "cp",
                "-r",
                f"{result_dir}/html_content",
                html_files,
            ]
        )
        if inputs.get("log"):
            cmd.extend(["&&", "cp", f"{out}/log.txt", f"{out}/bigscape.log"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        for directory in ["network_annotations", "clan_tables", "clustering_tables", "network_files"]:
            (out / directory).mkdir(parents=True, exist_ok=True)
        outputs = [out / "index.html", out / "network_annotations"]
        if not inputs.get("clans_off"):
            outputs.append(out / "clan_tables")
        outputs.extend([out / "clustering_tables", out / "network_files"])
        if inputs.get("log"):
            outputs.append(out / "bigscape.log")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        class_options = ["PKSI", "PKSother", "NRPS", "RiPPs", "Saccharides", "Terpene", "PKS-NRP_Hybrids", "Others"]
        return {
            "required": {
                "inputdir": ("FILE_LIST", {"multiple": True, "description": "GenBank BGC files to include in clustering"}),
                "pfam_dir": ("FILE", {"description": "Pfam-A.hmm HMM database file"}),
            },
            "optional": {
                "element_identifiers": (
                    "STRING",
                    {"default": [], "multiple": True, "advanced": True, "description": "Galaxy collection element identifiers"},
                ),
                "mibig": ("STRING", {"default": "", "options": cls.MIBIG_OPTIONS, "description": "Optional MIBiG database flag"}),
                "label": ("STRING", {"default": "", "description": "Extra label added to BiG-SCAPE run names"}),
                "verbose": ("BOOLEAN", {"default": False, "description": "Print detailed progress information"}),
                "log": ("BOOLEAN", {"default": False, "description": "Capture BiG-SCAPE stdout to a log output"}),
                "include_singletons": ("BOOLEAN", {"default": False, "description": "Include BGCs below the cutoff distance"}),
                "domain_overlap_cutoff": ("FLOAT", {"default": 0.1, "min": 0.0, "max": 1.0}),
                "min_big_size": ("INT", {"default": 0, "min": 0, "description": "Minimum BGC size in bp"}),
                "mix": ("BOOLEAN", {"default": False, "description": "Mix all BGC classes in the analysis"}),
                "no_classify": ("BOOLEAN", {"default": False, "description": "Disable product-class based output"}),
                "banned_classes": ("STRING_LIST", {"default": [], "options": class_options, "description": "Classes excluded from classification"}),
                "cutoffs": ("FLOAT_LIST", {"default": [0.3], "description": "Raw distance cutoff values"}),
                "clans_off": ("BOOLEAN", {"default": False, "description": "Turn off second-layer GCF-to-GCC clustering"}),
                "clan_cutoff": ("FLOAT_LIST", {"default": [], "description": "Optional GCF and GCC clan cutoff values"}),
                "hybrids_off": ("BOOLEAN", {"default": False, "description": "Exclude hybrid predicted products"}),
                "mode": ("STRING", {"default": "glocal", "options": ["glocal", "global", "auto"], "description": "Alignment mode"}),
                "anchorfile": ("FILE", {"default": "", "description": "Optional custom anchor domain file"}),
                "anchor_identifier": ("STRING", {"default": "", "advanced": True, "description": "Safe filename for the staged anchor file"}),
                "force_hmmscan": ("BOOLEAN", {"default": False, "description": "Force hmmscan domain prediction"}),
                "domain_includelist": ("FILE", {"default": "", "description": "Optional domain include list"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._inputs(inputs):
            return "at least one GenBank BGC input is required"
        if not str(inputs.get("pfam_dir", "")).strip():
            return "Pfam-A.hmm input is required"
        domain_overlap = float(inputs.get("domain_overlap_cutoff", 0.1))
        if domain_overlap < 0 or domain_overlap > 1:
            return "domain_overlap_cutoff must be between 0 and 1"
        for cutoff in cls._cutoffs(inputs):
            value = float(cutoff)
            if value < 0.1 or value > 1.0:
                return "cutoff values must be between 0.1 and 1.0"
        clan_cutoff = cls._clan_cutoff(inputs)
        if clan_cutoff:
            if len(clan_cutoff) != 2:
                return "clan_cutoff requires exactly two values"
            for cutoff in clan_cutoff:
                value = float(cutoff)
                if value < 0.1 or value > 1.0:
                    return "clan_cutoff values must be between 0.1 and 1.0"
        return super().VALIDATE_INPUTS(inputs)

class CompleasmNode(CommandNode):
    """Assess genome assembly completeness with compleasm."""

    NODE_ID = "compleasm"
    DISPLAY_NAME = "compleasm"
    REQUIRED_CONDA_PACKAGES = ["compleasm"]
    CATEGORY = "assembly"
    DESCRIPTION = "Assess genome assembly completeness with compleasm using cached BUSCO lineage data."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "compleasm",
        "compleasm genome completeness",
        "BUSCO lineage",
        "assembly completeness",
        "miniprot",
        "single-copy orthologs",
    ]
    RETURN_TYPES = ("TSV", "TSV", "GFF", "FASTA", "TXT")
    RETURN_NAMES = ("full_table_busco", "full_table", "miniprot", "translated_protein", "summary")
    REQUIRED_EXECUTABLES = ["compleasm"]
    DOCUMENTATION_URL = "https://github.com/huangnengCSU/compleasm"
    CITATION_DOIS = ["10.1101/2023.06.03.543588"]
    CITATION_URLS = [f"{DOI_URL}10.1101/2023.06.03.543588"]
    CITATION_TEXT = "Compleasm: a faster and more accurate reimplementation of the BUSCO lineage assessment."
    VERSION = "0.2.6"
    SHELL = True

    OUTPUT_FILES = {
        "full_table_busco": ("full_table_busco_format.tsv", "full_table_busco.tsv"),
        "full_table": ("full_table.tsv", "full_table.tsv"),
        "miniprot": ("miniprot_output.gff", "miniprot.gff"),
        "translated_protein": ("translated_protein.fasta", "translated_protein.fasta"),
        "summary": ("summary.txt", "summary.txt"),
    }
    OUTPUT_ORDER = ["full_table_busco", "full_table", "miniprot", "translated_protein", "summary"]

    @classmethod
    def _outputs(cls, inputs: dict[str, Any]) -> list[str]:
        outputs = _as_list(inputs.get("outputs"))
        return outputs or ["full_table_busco"]

    @classmethod
    def _database_path(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("busco_database_path", inputs.get("busco_database", inputs.get("database_path", ""))) or "")

    @classmethod
    def _lineage(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("lineage_dataset", inputs.get("lineage", "")) or "")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        lineage = cls._lineage(inputs)
        galaxy_db = f"{out}/galaxy_db"
        galaxy_output = f"{out}/galaxy_output"
        lineage_output = f"{galaxy_output}/{lineage}"
        cmd = [
            "mkdir",
            "-p",
            galaxy_db,
            "&&",
            "ln",
            "-s",
            f"{cls._database_path(inputs)}/lineages/{lineage}",
            f"{galaxy_db}/{lineage}",
            "&&",
            "touch",
            f"{galaxy_db}/{lineage}.done",
            "&&",
            "compleasm",
            "run",
            "-a",
            str(inputs.get("input", "")),
            "-o",
            galaxy_output,
            "--mode",
            str(inputs.get("mode", "busco")),
            "-L",
            galaxy_db,
            "-l",
            lineage,
            "-t",
            f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}",
        ]
        if inputs.get("specified_contigs"):
            cmd.extend(["--specified_contigs", str(inputs.get("specified_contigs"))])
        selected = set(cls._outputs(inputs))
        for name in cls.OUTPUT_ORDER:
            if name not in selected:
                continue
            source, target = cls.OUTPUT_FILES[name]
            source_path = f"{galaxy_output}/{source}" if name == "summary" else f"{lineage_output}/{source}"
            cmd.extend(["&&", "cp", source_path, f"{out}/{target}"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        selected = set(cls._outputs(inputs))
        return [out / cls.OUTPUT_FILES[name][1] for name in cls.OUTPUT_ORDER if name in selected]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTA", {"description": "Input genome assembly FASTA"}),
                "busco_database_path": ("DIRECTORY", {"description": "Cached BUSCO database root containing lineage directories"}),
                "lineage_dataset": ("STRING", {"description": "BUSCO lineage dataset name"}),
            },
            "optional": {
                "mode": (
                    "STRING",
                    {"default": "busco", "options": ["busco", "lite"], "description": "Use BUSCO/hmmsearch mode or lite mode"},
                ),
                "specified_contigs": (
                    "STRING",
                    {"default": "", "description": "Optional space-separated contig names to evaluate"},
                ),
                "outputs": (
                    "STRING_LIST",
                    {
                        "default": ["full_table_busco"],
                        "options": cls.OUTPUT_ORDER,
                        "description": "Compleasm outputs to copy from Galaxy work directory",
                    },
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input genome FASTA is required"
        if not cls._database_path(inputs).strip():
            return "BUSCO database path is required"
        if not cls._lineage(inputs).strip():
            return "lineage_dataset is required"
        for output in cls._outputs(inputs):
            if output not in cls.OUTPUT_FILES:
                return f"unknown compleasm output: {output}"
        specified_contigs = str(inputs.get("specified_contigs", "") or "")
        if specified_contigs and not re.fullmatch(r"[0-9A-Za-z_ ]+", specified_contigs):
            return "specified_contigs may contain only letters, numbers, underscores, and spaces"
        return super().VALIDATE_INPUTS(inputs)

class EASTRNode(CommandNode):
    """Detect and remove spurious RNA-seq splice junction alignments with EASTR."""

    NODE_ID = "eastr"
    DISPLAY_NAME = "EASTR"
    REQUIRED_CONDA_PACKAGES = ["eastr-cpp", "bowtie2"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Emend spliced transcript read alignments by identifying and removing spurious splice junctions."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "EASTR",
        "EASTR splice junction filtering",
        "spurious splice junctions",
        "spliced transcript reads",
        "filtered BAM",
        "Bowtie2 junction screening",
    ]
    RETURN_TYPES = ("BED", "BAM", "BED", "BED", "TXT")
    RETURN_NAMES = ("removed_junctions", "filtered_bam", "kept_junctions", "original_junctions", "log")
    REQUIRED_EXECUTABLES = ["eastr", "bowtie2-build"]
    DOCUMENTATION_URL = "https://github.com/iepertea/EASTR"
    CITATION_DOIS = ["10.1038/s41467-023-43017-4"]
    CITATION_URLS = [f"{DOI_URL}10.1038/s41467-023-43017-4"]
    CITATION_TEXT = "EASTR: identifying and eliminating systematic spurious spliced alignments in RNA-seq data."
    VERSION = "2.1.1"
    SHELL = True

    INPUT_SELECT_OPTIONS = ["bam", "gtf", "bed"]
    ADVANCED_INT_OPTIONS = {
        "bt2_k": ("--bt2_k", 10),
        "overhang": ("-o", 50),
        "anchor": ("-a", 7),
        "min_duplicate_exon_length": ("--min_duplicate_exon_length", 27),
        "min_junc_score": ("--min_junc_score", 1),
        "match_score": ("-A", 3),
        "mismatch_penalty": ("-B", 4),
        "kmer": ("-k", 3),
        "window": ("-w", 2),
        "min_chain_score": ("-m", 25),
    }

    @classmethod
    def _input_select(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("input_select", inputs.get("input_type", "")) or "")

    @classmethod
    def _optional_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        raw = inputs.get("optional_outputs")
        if isinstance(raw, str):
            return [part.strip() for part in raw.split(",") if part.strip()]
        return _as_list(raw)

    @classmethod
    def _option_value(cls, inputs: dict[str, Any], name: str, default: int) -> str:
        return str(inputs.get(name, inputs.get(f"adv_{name}", default)))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        input_select = cls._input_select(inputs)
        reference = f"{out}/reference.fa"
        cmd = ["ln", "-s", str(inputs.get("reference", "")), reference]
        if input_select == "bam":
            cmd.extend(["&&", "ln", "-s", str(inputs.get("input", "")), f"{out}/input.bam"])
            if inputs.get("bam_index"):
                cmd.extend(["&&", "ln", "-s", str(inputs.get("bam_index")), f"{out}/input.bam.bai"])
        cmd.extend(["&&", "eastr", "-r", reference, "-p", f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}"])
        if input_select == "bam":
            cmd.extend(["--bam", f"{out}/input.bam", "--out_filtered_bam", f"{out}/filtered.bam"])
        elif input_select == "gtf":
            cmd.extend(["--gtf", str(inputs.get("input", ""))])
        else:
            cmd.extend(["--bed", str(inputs.get("input", ""))])
        cmd.extend(["--out_removed_junctions", f"{out}/removed_junctions.bed"])
        optional_outputs = cls._optional_outputs(inputs)
        if "kept" in optional_outputs:
            cmd.extend(["--out_kept_junctions", f"{out}/kept_junctions.bed"])
        if "original" in optional_outputs:
            cmd.extend(["--out_original_junctions", f"{out}/original_junctions.bed"])
        for name, (flag, default) in cls.ADVANCED_INT_OPTIONS.items():
            cmd.extend([flag, cls._option_value(inputs, name, default)])
        if inputs.get("trusted_bed"):
            cmd.extend(["--trusted_bed", str(inputs.get("trusted_bed"))])
        if inputs.get("log"):
            cmd.extend(["--verbose", "2>", f"{out}/eastr.log"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "removed_junctions.bed"]
        if cls._input_select(inputs) == "bam":
            outputs.append(out / "filtered.bam")
        optional_outputs = cls._optional_outputs(inputs)
        if "kept" in optional_outputs:
            outputs.append(out / "kept_junctions.bed")
        if "original" in optional_outputs:
            outputs.append(out / "original_junctions.bed")
        if inputs.get("log"):
            outputs.append(out / "eastr.log")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_select": (
                    "STRING",
                    {
                        "default": "bam",
                        "options": cls.INPUT_SELECT_OPTIONS,
                        "description": "Input mode: coordinate-sorted BAM, transcript GTF, or intron BED",
                    },
                ),
                "input": ("FILE", {"description": "BAM, GTF, or BED input matching input_select"}),
                "reference": ("FASTA", {"description": "Reference genome FASTA used for junction sequence screening"}),
            },
            "optional": {
                "bam_index": ("FILE", {"default": "", "description": "BAM index, staged next to BAM for BAM input mode"}),
                "optional_outputs": (
                    "STRING_LIST",
                    {"default": [], "options": ["kept", "original"], "description": "Additional kept/original junction BED outputs"},
                ),
                "bt2_k": ("INT", {"default": 10, "min": 1, "description": "Minimum distinct Bowtie2 alignments for spurious classification"}),
                "overhang": ("INT", {"default": 50, "min": 1, "description": "Flanking sequence length on each side of a junction"}),
                "anchor": ("INT", {"default": 7, "min": 1, "description": "Minimum anchor length in each exon"}),
                "min_duplicate_exon_length": ("INT", {"default": 27, "min": 1}),
                "min_junc_score": ("INT", {"default": 1, "min": 0}),
                "match_score": ("INT", {"default": 3, "min": 1}),
                "mismatch_penalty": ("INT", {"default": 4, "min": 1}),
                "kmer": ("INT", {"default": 3, "min": 1}),
                "window": ("INT", {"default": 2, "min": 1}),
                "min_chain_score": ("INT", {"default": 25, "min": 1}),
                "trusted_bed": ("BED", {"default": "", "description": "Trusted junctions that will never be removed"}),
                "log": ("BOOLEAN", {"default": False, "description": "Capture EASTR verbose progress output"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        input_select = cls._input_select(inputs)
        if not input_select:
            return "input_select is required"
        if input_select not in cls.INPUT_SELECT_OPTIONS:
            return "input_select must be one of: bam, gtf, bed"
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        if not str(inputs.get("reference", "")).strip():
            return "reference FASTA is required"
        for name, (_, default) in cls.ADVANCED_INT_OPTIONS.items():
            value = int(inputs.get(name, inputs.get(f"adv_{name}", default)))
            minimum = 0 if name == "min_junc_score" else 1
            if value < minimum:
                return f"{name} must be >= {minimum}"
        for output in cls._optional_outputs(inputs):
            if output not in {"kept", "original"}:
                return f"unknown EASTR optional output: {output}"
        return super().VALIDATE_INPUTS(inputs)

class Export2GraphlanNode(CommandNode):
    """Convert tabular taxonomic profiles into GraPhlAn tree and annotation files."""

    NODE_ID = "export2graphlan"
    DISPLAY_NAME = "Export to GraPhlAn"
    REQUIRED_CONDA_PACKAGES = ["export2graphlan"]
    CATEGORY = "visualization"
    DESCRIPTION = "Convert MetaPhlAn, LEfSe, or HUMAnN profiles into GraPhlAn tree and annotation inputs."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "export2graphlan",
        "export2graphlan GraPhlAn conversion",
        "GraPhlAn annotation",
        "LEfSe to GraPhlAn",
        "MetaPhlAn tree visualization",
        "taxonomic profile visualization",
    ]
    RETURN_TYPES = ("TXT", "TXT")
    RETURN_NAMES = ("tree", "annotation")
    REQUIRED_EXECUTABLES = ["export2graphlan.py"]
    DOCUMENTATION_URL = "https://github.com/SegataLab/export2graphlan/"
    CITATION_DOIS = ["10.7717/peerj.1029"]
    CITATION_URLS = [f"{DOI_URL}10.7717/peerj.1029"]
    CITATION_TEXT = "Compact graphical representation of phylogenetic data and metadata with GraPhlAn."
    VERSION = "0.20"

    TEXT_OPTIONS = [
        ("annotations", "--annotations"),
        ("external_annotations", "--external_annotations"),
        ("background_levels", "--background_levels"),
        ("background_clades", "--background_clades"),
        ("background_colors", "--background_colors"),
        ("title", "--title"),
    ]
    INT_OPTIONS = [
        ("title_font_size", "--title_font_size"),
        ("def_clade_size", "--def_clade_size"),
        ("min_clade_size", "--min_clade_size"),
        ("max_clade_size", "--max_clade_size"),
        ("def_font_size", "--def_font_size"),
        ("min_font_size", "--min_font_size"),
        ("max_font_size", "--max_font_size"),
        ("annotation_legend_font_size", "--annotation_legend_font_size"),
        ("most_abundant", "--most_abundant"),
        ("least_biomarkers", "--least_biomarkers"),
        ("fname_row", "--fname_row"),
        ("sname_row", "--sname_row"),
        ("metadata_rows", "--metadata_rows"),
        ("stop", "--stop"),
        ("ftop", "--ftop"),
    ]
    FLOAT_OPTIONS = [
        ("abundance_threshold", "--abundance_threshold"),
        ("sperc", "--sperc"),
        ("fperc", "--fperc"),
    ]
    POSITIVE_INT_OPTIONS = {
        "title_font_size",
        "def_clade_size",
        "min_clade_size",
        "max_clade_size",
        "def_font_size",
        "min_font_size",
        "max_font_size",
        "annotation_legend_font_size",
        "most_abundant",
        "least_biomarkers",
        "stop",
        "ftop",
    }
    COMMAND_OPTION_ORDER = [
        *TEXT_OPTIONS,
        ("title_font_size", "--title_font_size"),
        ("def_clade_size", "--def_clade_size"),
        ("min_clade_size", "--min_clade_size"),
        ("max_clade_size", "--max_clade_size"),
        ("def_font_size", "--def_font_size"),
        ("min_font_size", "--min_font_size"),
        ("max_font_size", "--max_font_size"),
        ("annotation_legend_font_size", "--annotation_legend_font_size"),
        ("abundance_threshold", "--abundance_threshold"),
        ("most_abundant", "--most_abundant"),
        ("least_biomarkers", "--least_biomarkers"),
        ("fname_row", "--fname_row"),
        ("sname_row", "--sname_row"),
        ("metadata_rows", "--metadata_rows"),
        ("skip_rows", "--skip_rows"),
        ("sperc", "--sperc"),
        ("fperc", "--fperc"),
        ("stop", "--stop"),
        ("ftop", "--ftop"),
    ]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = [
            "export2graphlan.py",
            "--lefse_input",
            str(inputs.get("lefse_input", "")),
        ]
        _add_if_value(cmd, "--lefse_output", inputs.get("lefse_output"))
        cmd.extend(["-t", f"{out}/tree.txt", "-a", f"{out}/annotation.txt"])
        for name, flag in cls.COMMAND_OPTION_ORDER:
            _add_if_value(cmd, flag, inputs.get(name))
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "tree.txt", out / "annotation.txt"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "lefse_input": ("FILE", {"description": "LEfSe-style, MetaPhlAn, or HUMAnN tabular profile input"}),
            },
            "optional": {
                "lefse_output": ("FILE", {"default": "", "description": "Optional LEfSe biomarker result table"}),
                "annotations": ("STRING", {"default": "", "description": "Comma-separated levels to annotate in the tree"}),
                "external_annotations": (
                    "STRING",
                    {"default": "", "description": "Comma-separated levels that use an external annotation legend"},
                ),
                "background_levels": ("STRING", {"default": "", "description": "Comma-separated levels to shade in the background"}),
                "background_clades": ("STRING", {"default": "", "description": "Comma-separated clades to shade in the background"}),
                "background_colors": ("STRING", {"default": "", "description": "Comma-separated RGB or HSV background colors"}),
                "title": ("STRING", {"default": "", "description": "GraPhlAn plot title"}),
                "title_font_size": ("INT", {"default": "", "min": 1}),
                "def_clade_size": ("INT", {"default": "", "min": 1}),
                "min_clade_size": ("INT", {"default": "", "min": 1}),
                "max_clade_size": ("INT", {"default": "", "min": 1}),
                "def_font_size": ("INT", {"default": "", "min": 1}),
                "min_font_size": ("INT", {"default": "", "min": 1}),
                "max_font_size": ("INT", {"default": "", "min": 1}),
                "annotation_legend_font_size": ("INT", {"default": "", "min": 1}),
                "abundance_threshold": ("FLOAT", {"default": "", "min": 0}),
                "most_abundant": ("INT", {"default": "", "min": 1}),
                "least_biomarkers": ("INT", {"default": "", "min": 1}),
                "fname_row": ("INT", {"default": "", "min": -1, "description": "Feature-name row index; -1 means absent"}),
                "sname_row": ("INT", {"default": "", "min": -1, "description": "Sample-name row index; -1 means absent"}),
                "metadata_rows": ("INT", {"default": "", "min": 0}),
                "skip_rows": ("STRING", {"default": "", "description": "Comma-separated 0-based row indexes to skip"}),
                "sperc": ("FLOAT", {"default": "", "min": 0, "max": 100}),
                "fperc": ("FLOAT", {"default": "", "min": 0, "max": 100}),
                "stop": ("INT", {"default": "", "min": 1}),
                "ftop": ("INT", {"default": "", "min": 1}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("lefse_input", "")).strip():
            return "lefse_input is required"
        for name, _ in cls.INT_OPTIONS:
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if name in cls.POSITIVE_INT_OPTIONS and value < 1:
                return f"{name} must be >= 1"
            if name in {"fname_row", "sname_row"} and value < -1:
                return f"{name} must be >= -1"
            if name == "metadata_rows" and value < 0:
                return "metadata_rows must be >= 0"
        for name, _ in cls.FLOAT_OPTIONS:
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                return f"{name} must be a number"
            if value < 0:
                return f"{name} must be >= 0"
            if name in {"sperc", "fperc"} and value > 100:
                return f"{name} must be <= 100"
        skip_rows = str(inputs.get("skip_rows", "") or "")
        if skip_rows and not re.fullmatch(r"\d+(,\d+)*", skip_rows):
            return "skip_rows must be comma-separated integer row indexes"
        return super().VALIDATE_INPUTS(inputs)

class GraphlanAnnotateNode(CommandNode):
    """Add graphical annotations to a tree before rendering it with GraPhlAn."""

    NODE_ID = "graphlan_annotate"
    DISPLAY_NAME = "GraPhlAn Annotate"
    REQUIRED_CONDA_PACKAGES = ["graphlan"]
    CATEGORY = "visualization"
    DESCRIPTION = "Apply GraPhlAn annotation settings to a Newick, NHX, Nexus, or PhyloXML tree."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "GraPhlAn Annotate",
        "graphlan_annotate tree annotation",
        "GraPhlAn personalization",
        "phylogenetic tree annotation",
        "circular tree annotations",
    ]
    RETURN_TYPES = ("PHYLOXML",)
    RETURN_NAMES = ("output_tree",)
    REQUIRED_EXECUTABLES = ["graphlan_annotate.py"]
    DOCUMENTATION_URL = "https://github.com/biobakery/graphlan"
    CITATION_DOIS = ["10.7717/peerj.1029"]
    CITATION_URLS = [f"{DOI_URL}10.7717/peerj.1029"]
    CITATION_TEXT = "Compact graphical representation of phylogenetic data and metadata with GraPhlAn."
    VERSION = "1.1.3"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = ["graphlan_annotate.py"]
        _add_if_value(cmd, "--annot", inputs.get("annot"))
        cmd.extend([str(inputs.get("input_tree", "")), f"{out}/output_tree.phyloxml"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output_tree.phyloxml"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_tree": (
                    "PHYLOGENY_TREE",
                    {"description": "Input tree in Newick, NHX, Nexus, or PhyloXML format"},
                ),
            },
            "optional": {
                "annot": (
                    "TXT",
                    {"default": "", "description": "Optional tab-delimited GraPhlAn annotation file"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_tree", "")).strip():
            return "input_tree is required"
        return super().VALIDATE_INPUTS(inputs)

class GraphlanNode(CommandNode):
    """Render annotated phylogenetic trees with GraPhlAn."""

    NODE_ID = "graphlan"
    DISPLAY_NAME = "GraPhlAn"
    REQUIRED_CONDA_PACKAGES = ["graphlan"]
    CATEGORY = "visualization"
    DESCRIPTION = "Produce graphical circular representations of taxonomic or phylogenetic trees with GraPhlAn."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "GraPhlAn",
        "graphlan circular tree rendering",
        "phylogenetic tree visualization",
        "taxonomic tree image",
        "publication-ready tree plot",
    ]
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    REQUIRED_EXECUTABLES = ["graphlan.py"]
    DOCUMENTATION_URL = "https://github.com/biobakery/graphlan"
    CITATION_DOIS = ["10.7717/peerj.1029"]
    CITATION_URLS = [f"{DOI_URL}10.7717/peerj.1029"]
    CITATION_TEXT = "Compact graphical representation of phylogenetic data and metadata with GraPhlAn."
    VERSION = "1.1.3"
    OUTPUT_FORMATS = ["png", "pdf", "ps", "eps", "svg"]

    @classmethod
    def _format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("image_format", inputs.get("format", "png")) or "png").lower()

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        output_format = cls._format(inputs)
        cmd = [
            "graphlan.py",
            "--format",
            output_format,
            "--size",
            str(inputs.get("size", 7)),
        ]
        _add_if_value(cmd, "--pad", inputs.get("pad"))
        if output_format == "png":
            _add_if_value(cmd, "--dpi", inputs.get("dpi"))
        cmd.extend([str(inputs.get("input_tree", "")), f"{out}/image.{output_format}"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f"image.{cls._format(inputs)}"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_tree": ("PHYLOGENY_TREE", {"description": "Input tree in text, NHX, or PhyloXML format"}),
            },
            "optional": {
                "image_format": ("STRING", {"default": "png", "options": cls.OUTPUT_FORMATS, "description": "Output image format"}),
                "size": ("INT", {"default": 7, "min": 1, "description": "Output figure size"}),
                "pad": ("INT", {"default": "", "min": 0, "description": "Padding around the outermost graphical element"}),
                "dpi": (
                    "INT",
                    {
                        "default": "",
                        "min": 1,
                        "description": "PNG resolution in dots per inch",
                        "displayOptions": {"show": {"image_format": ["png"]}},
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_tree", "")).strip():
            return "input_tree is required"
        output_format = cls._format(inputs)
        if output_format not in cls.OUTPUT_FORMATS:
            return "image_format must be one of: png, pdf, ps, eps, svg"
        for name, minimum in {"size": 1, "pad": 0, "dpi": 1}.items():
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < minimum:
                return f"{name} must be >= {minimum}"
        return super().VALIDATE_INPUTS(inputs)

class ExonerateNode(CommandNode):
    """Run Exonerate pairwise sequence comparison."""

    NODE_ID = "exonerate"
    DISPLAY_NAME = "Exonerate"
    REQUIRED_CONDA_PACKAGES = ["exonerate", "python", "bcbiogff"]
    CATEGORY = "alignment"
    DESCRIPTION = "Run pairwise sequence comparison with Exonerate alignment models and Galaxy-style GFF outputs."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Exonerate",
        "exonerate pairwise sequence comparison",
        "est2genome",
        "protein2genome",
        "coding2coding",
        "target GFF",
        "query GFF",
    ]
    RETURN_TYPES = ("GFF", "GFF3", "TXT")
    RETURN_NAMES = ("output_gff", "output_gff3", "output_ali")
    REQUIRED_EXECUTABLES = ["exonerate", "python"]
    DOCUMENTATION_URL = "https://www.ebi.ac.uk/about/vertebrate-genomics/software/exonerate"
    CITATION_DOIS = ["10.1186/1471-2105-6-31"]
    CITATION_URLS = [f"{DOI_URL}10.1186/1471-2105-6-31"]
    CITATION_TEXT = "Exonerate: a generic tool for sequence comparison."
    VERSION = "2.4.0"
    SHELL = True

    MODELS = ["ungapped", "est2genome", "protein2genome", "coding2coding"]
    OUTFORMATS = ["targetgff", "querygff", "alignment"]
    MODEL_TYPES = {
        "est2genome": ("dna", "dna"),
        "protein2genome": ("protein", "dna"),
        "coding2coding": ("dna", "dna"),
    }

    @classmethod
    def _model(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("model", "ungapped") or "ungapped")

    @classmethod
    def _outformat(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("outformat", "targetgff") or "targetgff")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        model = cls._model(inputs)
        outformat = cls._outformat(inputs)
        cmd = [
            "exonerate",
            "--query",
            str(inputs.get("query", "")),
            "--target",
            str(inputs.get("target", inputs.get("input_fasta", ""))),
            "--score",
            str(inputs.get("score", 100)),
            "--percent",
            str(inputs.get("percent", 0.0)),
            "--bestn",
            str(inputs.get("bestn", 0)),
            "--verbose",
            "0",
        ]
        if model != "ungapped":
            cmd.extend(["--model", model])
        if model in cls.MODEL_TYPES:
            query_type, target_type = cls.MODEL_TYPES[model]
            cmd.extend(["--querytype", query_type, "--targettype", target_type])
        _add_if_value(cmd, "--minintron", inputs.get("minintron"))
        _add_if_value(cmd, "--maxintron", inputs.get("maxintron"))
        cmd.extend(["--cores", f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}"])
        if outformat == "alignment":
            cmd.extend(["--showalignment", "yes", "--showvulgar", "no", ">", f"{out}/output.txt"])
            return _shell_join(cmd).replace("'${GALAXY_SLOTS:-", "${GALAXY_SLOTS:-").replace("}'", "}")
        if outformat == "querygff":
            cmd.extend(["--showalignment", "no", "--showvulgar", "no", "--showtargetgff", "no", "--showquerygff", "yes"])
        else:
            cmd.extend(["--showalignment", "no", "--showvulgar", "no", "--showtargetgff", "yes", "--showquerygff", "no"])
        cmd.extend([">", f"{out}/output.gff"])
        converter = str(inputs.get("gff3_converter", "exonerategff_to_gff3.py") or "exonerategff_to_gff3.py")
        convert_cmd = ["python", converter, f"{out}/output.gff", ">", f"{out}/output.gff3"]
        shell_cmd = _shell_join(cmd).replace("'${GALAXY_SLOTS:-", "${GALAXY_SLOTS:-").replace("}'", "}")
        return f"{shell_cmd} && {_shell_join(convert_cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        if cls._outformat(inputs) == "alignment":
            return [out / "output.txt"]
        return [out / "output.gff", out / "output.gff3"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query": ("FASTA", {"description": "Query sequence FASTA"}),
                "target": ("FASTA", {"description": "Target/reference sequence FASTA"}),
            },
            "optional": {
                "model": ("STRING", {"default": "ungapped", "options": cls.MODELS, "description": "Exonerate alignment model"}),
                "outformat": ("STRING", {"default": "targetgff", "options": cls.OUTFORMATS, "description": "Galaxy output format"}),
                "score": ("INT", {"default": 100, "min": 0, "max": 10000}),
                "percent": ("FLOAT", {"default": 0.0, "min": 0, "max": 100}),
                "bestn": ("INT", {"default": 0, "min": 0, "max": 10000}),
                "minintron": ("INT", {"default": "", "min": 0}),
                "maxintron": ("INT", {"default": "", "min": 0}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
                "gff3_converter": (
                    "FILE",
                    {
                        "default": "exonerategff_to_gff3.py",
                        "description": "Galaxy helper script that converts Exonerate GFF to GFF3",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("query", "")).strip():
            return "query FASTA is required"
        if not str(inputs.get("target", inputs.get("input_fasta", ""))).strip():
            return "target FASTA is required"
        model = cls._model(inputs)
        if model not in cls.MODELS:
            return "model must be one of: ungapped, est2genome, protein2genome, coding2coding"
        outformat = cls._outformat(inputs)
        if outformat not in cls.OUTFORMATS:
            return "outformat must be one of: targetgff, querygff, alignment"
        for name, minimum in {"score": 0, "bestn": 0, "minintron": 0, "maxintron": 0, "threads": 1}.items():
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < minimum:
                return f"{name} must be >= {minimum}"
        percent = float(inputs.get("percent", 0.0))
        if percent < 0 or percent > 100:
            return "percent must be between 0 and 100"
        return super().VALIDATE_INPUTS(inputs)

class EvidenceModelerNode(CommandNode):
    """Combine gene prediction evidence into consensus gene structures with EVidenceModeler."""

    NODE_ID = "evidencemodeler"
    DISPLAY_NAME = "EVidenceModeler"
    REQUIRED_CONDA_PACKAGES = ["evidencemodeler"]
    CATEGORY = "annotation"
    DESCRIPTION = "Combine ab initio gene predictions, protein alignments, and transcript alignments into consensus gene structures."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "EVidenceModeler",
        "EvidenceModeler gene structure consensus",
        "EVM",
        "gene predictions",
        "protein alignments",
        "transcript alignments",
    ]
    RETURN_TYPES = ("GFF3", "FASTA")
    RETURN_NAMES = ("evm_gff", "evm_pep")
    REQUIRED_EXECUTABLES = ["EVidenceModeler"]
    DOCUMENTATION_URL = "https://github.com/EVidenceModeler/EVidenceModeler.github.io"
    CITATION_DOIS = ["10.1186/gb-2008-9-1-r7", "10.1080/21501203.2011.606851"]
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in CITATION_DOIS]
    CITATION_TEXT = (
        "Automated eukaryotic gene structure annotation using EVidenceModeler and the Program to Assemble Spliced Alignments; "
        "Eukaryotic genome annotation using EVidenceModeler and the Program to Assemble Spliced Alignments."
    )
    VERSION = "2.1.0"
    SHELL = True

    STOP_CODONS = ["TAA", "TGA", "TAG"]
    BINARY_OPTIONS = ["0", "1"]

    @classmethod
    def _stop_codons(cls, inputs: dict[str, Any]) -> str:
        values = _as_list(inputs.get("stop_codon"))
        return ",".join(values) if values else "TAA,TGA,TAG"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [
            _shell_join(["ln", "-s", str(inputs.get("input_genome", "")), "input_genome.fasta"]),
            _shell_join(["ln", "-s", str(inputs.get("input_predictions", "")), "input_predictions.gff"]),
            _shell_join(["ln", "-s", str(inputs.get("input_weights", "")), "input_weights.txt"]),
            _shell_join(["ln", "-s", str(inputs.get("input_proteins", "")), "input_proteins.gff"]),
        ]
        if inputs.get("input_transcript"):
            commands.append(_shell_join(["ln", "-s", str(inputs.get("input_transcript")), "input_transcript.gff"]))
        cmd = [
            "EVidenceModeler",
            "--sample_id",
            "galaxy",
            "--genome",
            "./input_genome.fasta",
            "--gene_predictions",
            "./input_predictions.gff",
            "--weights",
            "./input_weights.txt",
            "--protein_alignments",
            "./input_proteins.gff",
            "--segmentSize",
            str(inputs.get("segmentsize", 100000)),
            "--overlapSize",
            str(inputs.get("overlapsize", 10000)),
        ]
        if inputs.get("input_transcript"):
            cmd.extend(["--transcript_alignments", "./input_transcript.gff"])
        _add_if_value(cmd, "--repeats", inputs.get("input_repeat"))
        _add_if_value(cmd, "--terminalExons", inputs.get("input_terminalexon"))
        cmd.extend(
            [
                "--stop_codons",
                cls._stop_codons(inputs),
                "--min_intron_length",
                str(inputs.get("min_intron_length", 20)),
                "--search_long_introns",
                str(inputs.get("search_long_introns", 0)),
                "--re_search_intergenic",
                str(inputs.get("re_search_intergenic", 0)),
                "--terminal_intergenic_re_search",
                str(inputs.get("terminal_intergenic_re_search", 0)),
            ]
        )
        commands.append(_shell_join(cmd))
        commands.append(_shell_join(["cp", "galaxy.EVM.gff3", f"{out}/galaxy.EVM.gff3"]))
        commands.append(_shell_join(["cp", "galaxy.EVM.pep", f"{out}/galaxy.EVM.pep"]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "galaxy.EVM.gff3", out / "galaxy.EVM.pep"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_genome": ("FASTA", {"description": "Genome FASTA input"}),
                "input_predictions": ("GFF3", {"description": "Gene predictions GFF3"}),
                "input_weights": ("TXT", {"description": "EvidenceModeler weights file"}),
                "input_proteins": ("GFF3", {"description": "Protein alignment GFF3"}),
            },
            "optional": {
                "input_transcript": ("GFF3", {"default": "", "description": "Transcript alignment GFF3"}),
                "segmentsize": ("INT", {"default": 100000, "min": 1, "description": "Length of one sequence segment"}),
                "overlapsize": ("INT", {"default": 10000, "min": 0, "description": "Sequence overlap between segments"}),
                "input_repeat": ("GFF3", {"default": "", "description": "Masked genome repeats"}),
                "input_terminalexon": ("GFF3", {"default": "", "description": "Terminal exon evidence file"}),
                "stop_codon": (
                    "STRING_LIST",
                    {"default": ["TAA", "TGA", "TAG"], "options": cls.STOP_CODONS, "description": "Stop codons to use"},
                ),
                "min_intron_length": ("INT", {"default": 20, "min": 0}),
                "search_long_introns": ("STRING", {"default": "0", "options": cls.BINARY_OPTIONS}),
                "re_search_intergenic": ("STRING", {"default": "0", "options": cls.BINARY_OPTIONS}),
                "terminal_intergenic_re_search": ("STRING", {"default": "0", "options": cls.BINARY_OPTIONS}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for name in ["input_genome", "input_predictions", "input_weights", "input_proteins"]:
            if not str(inputs.get(name, "")).strip():
                return f"{name} is required"
        for name, minimum in {"segmentsize": 1, "overlapsize": 0, "min_intron_length": 0}.items():
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < minimum:
                return f"{name} must be >= {minimum}"
        for name in ["search_long_introns", "re_search_intergenic", "terminal_intergenic_re_search"]:
            value = str(inputs.get(name, 0))
            if value not in cls.BINARY_OPTIONS:
                return f"{name} must be one of: 0, 1"
        stop_codons = _as_list(inputs.get("stop_codon"))
        if stop_codons and any(codon not in cls.STOP_CODONS for codon in stop_codons):
            return "stop_codon values must be one or more of: TAA, TGA, TAG"
        return super().VALIDATE_INPUTS(inputs)

class COMEBinNode(CommandNode):
    """Bin metagenomic contigs with COMEBin."""

    NODE_ID = "comebin"
    DISPLAY_NAME = "COMEBin"
    REQUIRED_CONDA_PACKAGES = ["comebin"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Bin metagenomic contigs using contrastive multi-view representation learning with COMEBin."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "COMEBin",
        "COMEBin metagenomic binning",
        "contrastive multi-view binning",
        "metagenome bins",
        "contig binning",
        "coverage embeddings",
    ]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("bins",)
    REQUIRED_EXECUTABLES = ["run_comebin.sh"]
    DOCUMENTATION_URL = "https://github.com/ziyewang/COMEBin"
    CITATION_DOIS = ["10.1038/s41467-023-44290-z"]
    CITATION_URLS = [f"{DOI_URL}10.1038/s41467-023-44290-z"]
    CITATION_TEXT = "COMEBin enables accurate and robust binning of metagenomic contigs using contrastive multi-view representation learning."
    VERSION = "1.0.4"
    SHELL = True

    @classmethod
    def _bam_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("bam_files"))

    @classmethod
    def _assembly_identifier(cls, inputs: dict[str, Any]) -> str:
        return _safe_identifier(str(inputs.get("assembly_identifier", Path(str(inputs.get("assembly_file", "assembly"))).name or "assembly")))

    @classmethod
    def _bam_identifiers(cls, inputs: dict[str, Any], bam_files: list[str]) -> list[str]:
        identifiers = _as_list(inputs.get("bam_identifiers"))
        if identifiers:
            return [_safe_identifier(identifier) for identifier in identifiers]
        return [_safe_identifier(Path(path).stem) for path in bam_files]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        bam_files = cls._bam_files(inputs)
        assembly = f"{cls._assembly_identifier(inputs)}.fasta"
        commands = [
            _shell_join(["mkdir", "-p", out, "outputs", "bam_files"]),
            _shell_join(["ln", "-s", str(inputs.get("assembly_file", "")), assembly]),
        ]
        for path, identifier in zip(bam_files, cls._bam_identifiers(inputs, bam_files), strict=False):
            commands.append(_shell_join(["ln", "-s", path, f"./bam_files/{identifier}.bam"]))
        cmd = [
            "run_comebin.sh",
            "-a",
            assembly,
            "-o",
            "outputs",
            "-p",
            "bam_files",
            "-t",
            f"${{GALAXY_SLOTS:-{inputs.get('threads', 12)}}}",
            "-l",
            str(inputs.get("loss", 0.15)),
            "-n",
            str(inputs.get("learning", 6)),
            "-e",
            str(inputs.get("emb_comebin", 2048)),
            "-c",
            str(inputs.get("emb_cov", 2048)),
            "-b",
            str(inputs.get("batch", 1024)),
        ]
        commands.append(_shell_join(cmd).replace("'${GALAXY_SLOTS:-", "${GALAXY_SLOTS:-").replace("}'", "}"))
        commands.append(_shell_join(["cp", "-r", "outputs/comebin_res/comebin_res_bins", f"{out}/bins"]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        (out / "bins").mkdir(parents=True, exist_ok=True)
        return [out / "bins"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "assembly_file": ("FASTA", {"description": "Metagenomic assembly FASTA"}),
                "bam_files": ("BAM_LIST", {"multiple": True, "description": "BAM files aligned to the assembly"}),
            },
            "optional": {
                "assembly_identifier": (
                    "STRING",
                    {"default": "", "advanced": True, "description": "Galaxy collection element identifier for the assembly"},
                ),
                "bam_identifiers": (
                    "STRING",
                    {"default": [], "multiple": True, "advanced": True, "description": "Galaxy collection element identifiers for BAMs"},
                ),
                "learning": ("INT", {"default": 6, "min": 1, "description": "Views for contrastive multi-view learning"}),
                "loss": ("FLOAT", {"default": 0.15, "min": 0, "description": "Temperature in the contrastive loss function"}),
                "emb_comebin": ("INT", {"default": 2048, "min": 1, "description": "Embedding size for the COMEBin network"}),
                "emb_cov": ("INT", {"default": 2048, "min": 1, "description": "Embedding size for the coverage network"}),
                "batch": ("INT", {"default": 1024, "min": 1, "description": "Batch size"}),
                "threads": ("INT", {"default": 12, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("assembly_file", "")).strip():
            return "assembly_file is required"
        if not cls._bam_files(inputs):
            return "at least one BAM file is required"
        for name in ["learning", "emb_comebin", "emb_cov", "batch", "threads"]:
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < 1:
                return f"{name} must be >= 1"
        loss = float(inputs.get("loss", 0.15))
        if loss <= 0:
            return "loss must be > 0"
        return super().VALIDATE_INPUTS(inputs)

class COMEBinBamNode(CommandNode):
    """Generate a COMEBin-compatible BAM file from reads and an assembly."""

    NODE_ID = "comebin_bam"
    DISPLAY_NAME = "Generate BAM file for COMEBin"
    REQUIRED_CONDA_PACKAGES = ["comebin"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Generate a COMEBin-compatible BAM coverage file from reads using the COMEBin MetaWRAP-derived helper."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "COMEBin BAM",
        "COMEBin BAM generation",
        "gen_cov_file.sh",
        "COMEBin coverage BAM",
        "metagenomic coverage",
    ]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("bam_file",)
    REQUIRED_EXECUTABLES = ["gen_cov_file.sh"]
    DOCUMENTATION_URL = "https://github.com/ziyewang/COMEBin"
    CITATION_DOIS = ["10.1038/s41467-023-44290-z"]
    CITATION_URLS = [f"{DOI_URL}10.1038/s41467-023-44290-z"]
    CITATION_TEXT = "COMEBin enables accurate and robust binning of metagenomic contigs using contrastive multi-view representation learning."
    VERSION = "1.0.4"
    SHELL = True

    @classmethod
    def _read_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("read_type", inputs.get("is_select", "normal")) or "normal")

    @classmethod
    def _input_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("input_type", inputs.get("input_typ", "paired")) or "paired")

    @staticmethod
    def _is_gz(path: Any) -> bool:
        return str(path).endswith(".gz")

    @classmethod
    def _paired_reads(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        reads = inputs.get("paired_reads")
        if isinstance(reads, dict):
            return str(reads.get("forward", "")), str(reads.get("reverse", ""))
        parts = _as_list(reads)
        if len(parts) >= 2:
            return parts[0], parts[1]
        return str(inputs.get("forward", "")), str(inputs.get("reverse", ""))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [_shell_join(["mkdir", "-p", "outputs", out])]
        assembly = str(inputs.get("assembly", ""))
        if cls._is_gz(assembly):
            commands.append(_shell_join(["ln", "-s", assembly, "assembly.fasta.gz"]))
            commands.append(_shell_join(["gunzip", "assembly.fasta.gz"]))
        else:
            commands.append(_shell_join(["ln", "-s", assembly, "assembly.fasta"]))
        read_type = cls._read_type(inputs)
        if read_type == "normal":
            forward, reverse = cls._paired_reads(inputs)
            if cls._is_gz(forward):
                commands.append(_shell_join(["ln", "-s", forward, "read_1.fastq.gz"]))
                commands.append(_shell_join(["ln", "-s", reverse, "read_2.fastq.gz"]))
                commands.append(_shell_join(["gunzip", "read_1.fastq.gz"]))
                commands.append(_shell_join(["gunzip", "read_2.fastq.gz"]))
            else:
                commands.append(_shell_join(["ln", "-s", forward, "read_1.fastq"]))
                commands.append(_shell_join(["ln", "-s", reverse, "read_2.fastq"]))
        else:
            single_reads = str(inputs.get("single_reads", ""))
            if cls._is_gz(single_reads):
                commands.append(_shell_join(["ln", "-s", single_reads, "read.fastq.gz"]))
                commands.append(_shell_join(["gunzip", "read.fastq.gz"]))
            else:
                commands.append(_shell_join(["ln", "-s", single_reads, "read.fastq"]))
        cmd = [
            "gen_cov_file.sh",
            "-a",
            "assembly.fasta",
            "-o",
            "outputs",
            "-t",
            f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}",
            "-l",
            str(inputs.get("length", 1000)),
        ]
        if read_type == "normal":
            cmd.extend(["read_1.fastq", "read_2.fastq"])
        else:
            cmd.extend(["--single-end", "read.fastq"])
        commands.append(_shell_join(cmd).replace("'${GALAXY_SLOTS:-", "${GALAXY_SLOTS:-").replace("}'", "}"))
        commands.append(_shell_join(["mv", "outputs/work_files/read.bam", f"{out}/bam_file.bam"]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "bam_file.bam"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "assembly": ("FASTA", {"description": "Assembly FASTA or FASTA.GZ"}),
                "read_type": ("STRING", {"default": "normal", "options": ["normal", "single"], "description": "Paired-end or single-end reads"}),
            },
            "optional": {
                "input_type": ("STRING", {"default": "paired", "options": ["paired", "single"], "description": "Paired collection or separate reads"}),
                "paired_reads": ("FASTQ_LIST", {"default": "", "description": "Paired read collection or [forward, reverse]"}),
                "forward": ("FASTQ", {"default": "", "description": "Forward FASTQ for separate paired reads"}),
                "reverse": ("FASTQ", {"default": "", "description": "Reverse FASTQ for separate paired reads"}),
                "single_reads": ("FASTQ", {"default": "", "description": "Single-end FASTQ"}),
                "length": ("INT", {"default": 1000, "min": 1, "description": "Minimum contig length"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("assembly", "")).strip():
            return "assembly is required"
        read_type = cls._read_type(inputs)
        if read_type not in {"normal", "single"}:
            return "read_type must be one of: normal, single"
        if read_type == "normal":
            input_type = cls._input_type(inputs)
            if input_type not in {"paired", "single"}:
                return "input_type must be one of: paired, single"
            forward, reverse = cls._paired_reads(inputs)
            if not forward or not reverse:
                return "forward and reverse reads are required"
        elif not str(inputs.get("single_reads", "")).strip():
            return "single_reads is required"
        for name in ["length", "threads"]:
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < 1:
                return f"{name} must be >= 1"
        return super().VALIDATE_INPUTS(inputs)

class DrepCompareNode(CommandNode):
    """Compare genome FASTA files with dRep."""

    NODE_ID = "drep_compare"
    DISPLAY_NAME = "dRep compare"
    REQUIRED_CONDA_PACKAGES = ["drep"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Compare genome sets with dRep using Mash primary clustering and optional secondary ANI clustering."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "dRep",
        "dRep compare",
        "dRep genome comparison",
        "genome dereplication",
        "average nucleotide identity",
        "Mash ANI clustering",
    ]
    RETURN_TYPES = ("TXT", "TXT", "PDF", "PDF", "PDF", "PDF", "CSV", "CSV", "CSV", "CSV")
    RETURN_NAMES = (
        "log",
        "warnings",
        "primary_clustering_dendrogram",
        "secondary_clustering_dendrograms",
        "secondary_clustering_mds",
        "clustering_scatterplots",
        "bdb",
        "cdb",
        "mdb",
        "ndb",
    )
    REQUIRED_EXECUTABLES = ["dRep"]
    DOCUMENTATION_URL = "https://drep.readthedocs.io/en/latest/overview.html"
    CITATION_DOIS = [DREP_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{DREP_CITATION_DOI}"]
    CITATION_TEXT = DREP_CITATION_TEXT
    VERSION = "3.6.2"
    SHELL = True

    COMPARISON_STEPS = ["default", "SkipMash", "SkipSecondary"]
    SECONDARY_ALGORITHMS = ["fastANI", "ANImf", "ANIn", "gANI", "goANI"]
    NUCMER_PRESETS = ["normal", "tight"]
    COVERAGE_METHODS = ["larger", "total"]
    CLUSTER_ALGORITHMS = ["average", "ward", "single", "median", "centroid", "weighted"]
    DEFAULT_OUTPUTS = ["log", "warnings", "Primary_clustering_dendrogram", "Clustering_scatterplots"]
    OUTPUTS = {
        "log": ("outdir/log/logger.log", "log.txt"),
        "warnings": ("outdir/log/warnings.txt", "warnings.txt"),
        "Primary_clustering_dendrogram": (
            "outdir/figures/Primary_clustering_dendrogram.pdf",
            "Primary_clustering_dendrogram.pdf",
        ),
        "Secondary_clustering_dendrograms": (
            "outdir/figures/Secondary_clustering_dendrograms.pdf",
            "Secondary_clustering_dendrograms.pdf",
        ),
        "Secondary_clustering_MDS": ("outdir/figures/Secondary_clustering_MDS.pdf", "Secondary_clustering_MDS.pdf"),
        "Clustering_scatterplots": ("outdir/figures/Clustering_scatterplots.pdf", "Clustering_scatterplots.pdf"),
        "Bdb": ("outdir/data_tables/Bdb.csv", "Bdb.csv"),
        "Cdb": ("outdir/data_tables/Cdb.csv", "Cdb.csv"),
        "Mdb": ("outdir/data_tables/Mdb.csv", "Mdb.csv"),
        "Ndb": ("outdir/data_tables/Ndb.csv", "Ndb.csv"),
    }

    @classmethod
    def _genomes(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("genomes"))

    @classmethod
    def _genome_identifiers(cls, inputs: dict[str, Any], genomes: list[str]) -> list[str]:
        identifiers = _as_list(inputs.get("genome_identifiers", inputs.get("element_identifiers")))
        if not identifiers:
            identifiers = [Path(path).name for path in genomes]
        identifiers.extend(Path(path).name for path in genomes[len(identifiers) :])
        return [_safe_identifier(identifier) for identifier in identifiers[: len(genomes)]]

    @classmethod
    def _selected_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        selected = _as_list(inputs.get("select_outputs"))
        if not selected:
            return cls.DEFAULT_OUTPUTS.copy()
        return [output for output in selected if output in cls.OUTPUTS]

    @classmethod
    def _add_mash_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--MASH_sketch",
                str(inputs.get("MASH_sketch", 1000)),
                "--P_ani",
                str(inputs.get("P_ani", 0.9)),
            ]
        )
        if inputs.get("multiround_primary_clustering"):
            cmd.append("--multiround_primary_clustering")
        cmd.extend(["--primary_chunksize", str(inputs.get("primary_chunksize", 5000))])

    @classmethod
    def _add_secondary_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        algorithm = str(inputs.get("S_algorithm", "ANImf") or "ANImf")
        cmd.extend(["--S_algorithm", algorithm])
        if algorithm == "fastANI":
            if inputs.get("greedy_secondary_clustering"):
                cmd.append("--greedy_secondary_clustering")
        elif algorithm in {"ANImf", "ANIn"}:
            cmd.extend(["--n_PRESET", str(inputs.get("n_PRESET", "normal"))])
            cmd.extend(["--coverage_method", str(inputs.get("coverage_method", "larger"))])
        cmd.extend(["--S_ani", str(inputs.get("S_ani", 0.99))])
        cmd.extend(["--cov_thresh", str(inputs.get("cov_thresh", 0.1))])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        genomes = cls._genomes(inputs)
        genome_names = [f"{identifier}.fasta" for identifier in cls._genome_identifiers(inputs, genomes)]
        commands = [_shell_join(["mkdir", "-p", out])]
        for genome, genome_name in zip(genomes, genome_names, strict=False):
            commands.append(_shell_join(["ln", "-s", genome, genome_name]))

        cmd = ["dRep", "compare", "outdir", "-g", *genome_names]
        comparison_steps = str(inputs.get("comparison_steps", inputs.get("select", "default")) or "default")
        if comparison_steps == "default":
            cls._add_mash_options(cmd, inputs)
            cls._add_secondary_options(cmd, inputs)
        elif comparison_steps == "SkipMash":
            cmd.append("--SkipMash")
            cls._add_secondary_options(cmd, inputs)
        else:
            cls._add_mash_options(cmd, inputs)
            cmd.append("--SkipSecondary")
        cmd.extend(["--clusterAlg", str(inputs.get("clusterAlg", "average"))])
        if inputs.get("run_tertiary_clustering"):
            cmd.append("--run_tertiary_clustering")
        cmd.extend(["--warn_dist", str(inputs.get("warn_dist", 0.25))])
        cmd.extend(["--warn_sim", str(inputs.get("warn_sim", 0.98))])
        cmd.extend(["--warn_aln", str(inputs.get("warn_aln", 0.25))])
        cmd.extend(["--processors", f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}"])
        commands.append(_shell_join(cmd).replace("'${GALAXY_SLOTS:-", "${GALAXY_SLOTS:-").replace("}'", "}"))
        for output in cls._selected_outputs(inputs):
            source, filename = cls.OUTPUTS[output]
            commands.append(_shell_join(["cp", source, f"{out}/{filename}"]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls.OUTPUTS[output][1] for output in cls._selected_outputs(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "genomes": ("FASTA_LIST", {"multiple": True, "min": 2, "description": "Genome FASTA files to compare"}),
            },
            "optional": {
                "genome_identifiers": (
                    "STRING",
                    {"default": [], "multiple": True, "advanced": True, "description": "Galaxy collection element identifiers"},
                ),
                "comparison_steps": (
                    "STRING",
                    {"default": "default", "options": cls.COMPARISON_STEPS, "description": "Genome comparison stages to run"},
                ),
                "MASH_sketch": ("INT", {"default": 1000, "min": 0, "description": "Mash sketch size"}),
                "P_ani": ("FLOAT", {"default": 0.9, "min": 0, "max": 1, "description": "ANI threshold for primary clusters"}),
                "multiround_primary_clustering": (
                    "BOOLEAN",
                    {"default": False, "description": "Cluster primary chunks separately before merging"},
                ),
                "primary_chunksize": ("INT", {"default": 5000, "min": 1, "description": "Genome chunk size for primary clustering"}),
                "S_algorithm": (
                    "STRING",
                    {"default": "ANImf", "options": cls.SECONDARY_ALGORITHMS, "description": "Secondary clustering algorithm"},
                ),
                "greedy_secondary_clustering": (
                    "BOOLEAN",
                    {"default": False, "description": "Use greedy secondary clustering with fastANI"},
                ),
                "n_PRESET": ("STRING", {"default": "normal", "options": cls.NUCMER_PRESETS, "description": "Nucmer preset"}),
                "coverage_method": (
                    "STRING",
                    {"default": "larger", "options": cls.COVERAGE_METHODS, "description": "Alignment coverage calculation"},
                ),
                "S_ani": ("FLOAT", {"default": 0.99, "min": 0, "max": 1, "description": "ANI threshold for secondary clusters"}),
                "cov_thresh": ("FLOAT", {"default": 0.1, "min": 0, "max": 1, "description": "Minimum overlap for secondary comparisons"}),
                "clusterAlg": ("STRING", {"default": "average", "options": cls.CLUSTER_ALGORITHMS, "description": "SciPy linkage algorithm"}),
                "run_tertiary_clustering": ("BOOLEAN", {"default": False, "description": "Run an additional clustering pass"}),
                "warn_dist": ("FLOAT", {"default": 0.25, "min": 0, "max": 1, "description": "Distance from threshold for cluster warnings"}),
                "warn_sim": ("FLOAT", {"default": 0.98, "min": 0, "max": 1, "description": "Similarity threshold for warnings"}),
                "warn_aln": ("FLOAT", {"default": 0.25, "min": 0, "max": 1, "description": "Minimum aligned fraction for warnings"}),
                "select_outputs": (
                    "STRING_LIST",
                    {"default": cls.DEFAULT_OUTPUTS.copy(), "options": list(cls.OUTPUTS), "description": "Galaxy dRep outputs to collect"},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if len(cls._genomes(inputs)) < 2:
            return "at least two genome FASTA files are required"
        comparison_steps = str(inputs.get("comparison_steps", inputs.get("select", "default")) or "default")
        if comparison_steps not in cls.COMPARISON_STEPS:
            return "comparison_steps must be one of: default, SkipMash, SkipSecondary"
        algorithm = str(inputs.get("S_algorithm", "ANImf") or "ANImf")
        if algorithm not in cls.SECONDARY_ALGORITHMS:
            return "S_algorithm must be one of: fastANI, ANImf, ANIn, gANI, goANI"
        if str(inputs.get("n_PRESET", "normal") or "normal") not in cls.NUCMER_PRESETS:
            return "n_PRESET must be one of: normal, tight"
        if str(inputs.get("coverage_method", "larger") or "larger") not in cls.COVERAGE_METHODS:
            return "coverage_method must be one of: larger, total"
        if str(inputs.get("clusterAlg", "average") or "average") not in cls.CLUSTER_ALGORITHMS:
            return "clusterAlg must be one of: average, ward, single, median, centroid, weighted"
        for name, minimum in {"MASH_sketch": 0, "primary_chunksize": 1, "threads": 1}.items():
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < minimum:
                return f"{name} must be >= {minimum}"
        for name in ["P_ani", "S_ani", "cov_thresh", "warn_dist", "warn_sim", "warn_aln"]:
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                return f"{name} must be a number"
            if not 0 <= value <= 1:
                return f"{name} must be between 0 and 1"
        return super().VALIDATE_INPUTS(inputs)

class DrepDereplicateNode(DrepCompareNode):
    """De-replicate genome FASTA files with dRep."""

    NODE_ID = "drep_dereplicate"
    DISPLAY_NAME = "dRep dereplicate"
    REQUIRED_CONDA_PACKAGES = ["drep", "checkm-genome"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "De-replicate genome sets with dRep, genome quality filtering, and representative genome scoring."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "dRep",
        "dRep dereplicate",
        "dRep genome dereplication",
        "bin dereplication",
        "metagenome genome recovery",
        "representative genomes",
    ]
    RETURN_TYPES = ("DIRECTORY", "TXT", "TXT", "PDF", "PDF", "PDF", "PDF", "CSV", "CSV", "CSV", "CSV", "PDF", "PDF", "CSV", "TSV")
    RETURN_NAMES = (
        "dereplicated_genomes",
        "log",
        "warnings",
        "primary_clustering_dendrogram",
        "secondary_clustering_dendrograms",
        "secondary_clustering_mds",
        "clustering_scatterplots",
        "bdb",
        "cdb",
        "mdb",
        "ndb",
        "cluster_scoring",
        "winning_genomes",
        "widb",
        "chdb",
    )
    REQUIRED_EXECUTABLES = ["dRep"]
    DOCUMENTATION_URL = "https://drep.readthedocs.io/en/latest/overview.html#genome-de-replication"
    CITATION_DOIS = [DREP_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{DREP_CITATION_DOI}"]
    CITATION_TEXT = DREP_CITATION_TEXT
    VERSION = "3.6.2"
    SHELL = True

    QUALITY_SOURCES = ["checkm", "genomeInfo", "ignoreGenomeQuality"]
    CHECKM_METHODS = ["lineage_wf", "taxonomy_wf"]
    DEFAULT_OUTPUTS = [
        "log",
        "warnings",
        "Primary_clustering_dendrogram",
        "Clustering_scatterplots",
        "Cluster_scoring",
        "Winning_genomes",
        "Widb",
    ]
    OUTPUTS = {
        **DrepCompareNode.OUTPUTS,
        "Cluster_scoring": ("outdir/figures/Cluster_scoring.pdf", "Cluster_scoring.pdf"),
        "Winning_genomes": ("outdir/figures/Winning_genomes.pdf", "Winning_genomes.pdf"),
        "Widb": ("outdir/data_tables/Widb.csv", "Widb.csv"),
        "Chdb": ("outdir/data/checkM/checkM_outdir/Chdb.tsv", "Chdb.tsv"),
    }

    @classmethod
    def _add_filter_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(["--length", str(inputs.get("length", 50000))])
        cmd.extend(["--completeness", str(inputs.get("completeness", 75))])
        cmd.extend(["--contamination", str(inputs.get("contamination", 25))])

    @classmethod
    def _add_quality_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        source = str(inputs.get("quality_source", inputs.get("source", "checkm")) or "checkm")
        if source == "checkm":
            cmd.extend(["--checkM_method", str(inputs.get("checkM_method", "lineage_wf"))])
            if str(inputs.get("set_recursion", "")) != "":
                cmd.extend(["--set_recurison", str(inputs.get("set_recursion"))])
            cmd.extend(["--checkm_group_size", str(inputs.get("checkm_group_size", 2000))])
        elif source == "genomeInfo":
            cmd.extend(["--genomeInfo", str(inputs.get("genomeInfo", ""))])
        else:
            cmd.append("--ignoreGenomeQuality")

    @classmethod
    def _add_scoring_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(["--completeness_weight", str(inputs.get("completeness_weight", 1))])
        cmd.extend(["--contamination_weight", str(inputs.get("contamination_weight", 5))])
        cmd.extend(["--strain_heterogeneity_weight", str(inputs.get("strain_heterogeneity_weight", 1))])
        cmd.extend(["--N50_weight", str(inputs.get("N50_weight", 0.5))])
        cmd.extend(["--size_weight", str(inputs.get("size_weight", 0))])
        cmd.extend(["--centrality_weight", str(inputs.get("centrality_weight", 1))])
        if str(inputs.get("extra_weight_table", "")) != "":
            cmd.extend(["--extra_weight_table", str(inputs.get("extra_weight_table"))])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        genomes = cls._genomes(inputs)
        genome_names = [f"{identifier}.fasta" for identifier in cls._genome_identifiers(inputs, genomes)]
        commands = [_shell_join(["mkdir", "-p", out])]
        for genome, genome_name in zip(genomes, genome_names, strict=False):
            commands.append(_shell_join(["ln", "-s", genome, genome_name]))

        cmd = ["dRep", "dereplicate", "outdir", "-g", *genome_names]
        cls._add_filter_options(cmd, inputs)
        cls._add_quality_options(cmd, inputs)
        comparison_steps = str(inputs.get("comparison_steps", inputs.get("select", "default")) or "default")
        if comparison_steps == "default":
            cls._add_mash_options(cmd, inputs)
            cls._add_secondary_options(cmd, inputs)
        elif comparison_steps == "SkipMash":
            cmd.append("--SkipMash")
            cls._add_secondary_options(cmd, inputs)
        else:
            cls._add_mash_options(cmd, inputs)
            cmd.append("--SkipSecondary")
        cmd.extend(["--clusterAlg", str(inputs.get("clusterAlg", "average"))])
        if inputs.get("run_tertiary_clustering"):
            cmd.append("--run_tertiary_clustering")
        cls._add_scoring_options(cmd, inputs)
        cmd.extend(["--warn_dist", str(inputs.get("warn_dist", 0.25))])
        cmd.extend(["--warn_sim", str(inputs.get("warn_sim", 0.98))])
        cmd.extend(["--warn_aln", str(inputs.get("warn_aln", 0.25))])
        cmd.extend(["--processors", f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}"])
        commands.append(
            _shell_join(cmd).replace("'${GALAXY_SLOTS:-", "${GALAXY_SLOTS:-").replace("}'", "}")
            + " || (rc=$?; ls -ltr `find outdir -type f`; cat outdir/data/checkM/checkM_outdir/checkm.log; "
            "cat outdir/log/logger.log; exit $rc)"
        )
        commands.append(_shell_join(["cp", "-r", "outdir/dereplicated_genomes", f"{out}/dereplicated_genomes"]))
        for output in cls._selected_outputs(inputs):
            source, filename = cls.OUTPUTS[output]
            commands.append(_shell_join(["cp", source, f"{out}/{filename}"]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        (out / "dereplicated_genomes").mkdir(parents=True, exist_ok=True)
        return [out / "dereplicated_genomes", *[out / cls.OUTPUTS[output][1] for output in cls._selected_outputs(inputs)]]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        parent = super().INPUT_TYPES()
        optional = dict(parent["optional"])
        optional.update(
            {
                "length": ("INT", {"default": 50000, "min": 1, "description": "Minimum genome length"}),
                "completeness": ("INT", {"default": 75, "min": 0, "max": 100, "description": "Minimum genome completeness percent"}),
                "contamination": ("INT", {"default": 25, "min": 0, "max": 100, "description": "Maximum genome contamination percent"}),
                "quality_source": (
                    "STRING",
                    {"default": "checkm", "options": cls.QUALITY_SOURCES, "description": "Genome quality filtering source"},
                ),
                "checkM_method": ("STRING", {"default": "lineage_wf", "options": cls.CHECKM_METHODS, "description": "CheckM workflow"}),
                "set_recursion": ("INT", {"default": "", "min": 1, "advanced": True, "description": "Optional Python recursion limit"}),
                "checkm_group_size": ("INT", {"default": 2000, "min": 1, "description": "Number of genomes passed to CheckM at a time"}),
                "genomeInfo": ("CSV", {"default": "", "description": "CSV quality information for genomes"}),
                "completeness_weight": ("FLOAT", {"default": 1, "description": "Scoring weight for completeness"}),
                "contamination_weight": ("FLOAT", {"default": 5, "description": "Scoring weight for contamination"}),
                "strain_heterogeneity_weight": (
                    "FLOAT",
                    {"default": 1, "min": 0, "max": 1, "description": "Scoring weight for strain heterogeneity"},
                ),
                "N50_weight": ("FLOAT", {"default": 0.5, "description": "Scoring weight for log genome N50"}),
                "size_weight": ("FLOAT", {"default": 0, "description": "Scoring weight for log genome size"}),
                "centrality_weight": ("FLOAT", {"default": 1, "description": "Scoring weight for cluster centrality"}),
                "extra_weight_table": ("TSV", {"default": "", "description": "Genome-specific extra scoring weights"}),
                "select_outputs": (
                    "STRING_LIST",
                    {"default": cls.DEFAULT_OUTPUTS.copy(), "options": list(cls.OUTPUTS), "description": "Galaxy dRep outputs to collect"},
                ),
            }
        )
        return {
            "required": parent["required"],
            "optional": optional,
            "hidden": parent["hidden"],
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        quality_source = str(inputs.get("quality_source", inputs.get("source", "checkm")) or "checkm")
        if quality_source not in cls.QUALITY_SOURCES:
            return "quality_source must be one of: checkm, genomeInfo, ignoreGenomeQuality"
        if quality_source == "genomeInfo" and not str(inputs.get("genomeInfo", "")).strip():
            return "genomeInfo is required"
        if str(inputs.get("checkM_method", "lineage_wf") or "lineage_wf") not in cls.CHECKM_METHODS:
            return "checkM_method must be one of: lineage_wf, taxonomy_wf"
        for name, minimum in {"length": 1, "checkm_group_size": 1, "set_recursion": 1}.items():
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < minimum:
                return f"{name} must be >= {minimum}"
        for name in ["completeness", "contamination"]:
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if not 0 <= value <= 100:
                return f"{name} must be between 0 and 100"
        for name in [
            "completeness_weight",
            "contamination_weight",
            "strain_heterogeneity_weight",
            "N50_weight",
            "size_weight",
            "centrality_weight",
        ]:
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                return f"{name} must be a number"
            if name == "strain_heterogeneity_weight" and not 0 <= value <= 1:
                return "strain_heterogeneity_weight must be between 0 and 1"
        return True

class CamiAmberNode(CommandNode):
    """Evaluate metagenome binning results with CAMI AMBER."""

    NODE_ID = "cami_amber"
    DISPLAY_NAME = "CAMI AMBER"
    REQUIRED_CONDA_PACKAGES = ["cami-amber"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Evaluate genome reconstructions and taxonomic assignments from metagenome benchmark data with AMBER."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "CAMI AMBER",
        "AMBER metagenome binning evaluation",
        "Assessment of Metagenome BinnERs",
        "binning benchmark",
        "genome reconstruction metrics",
    ]
    RETURN_TYPES = ("HTML_REPORT", "TSV", "TSV", "TSV")
    RETURN_NAMES = ("html", "result", "metrics_genome", "metrics_bin")
    REQUIRED_EXECUTABLES = ["amber.py"]
    DOCUMENTATION_URL = "https://github.com/CAMI-challenge/AMBER"
    CITATION_DOIS = ["10.1093/gigascience/giy069"]
    CITATION_URLS = [f"{DOI_URL}10.1093/gigascience/giy069"]
    CITATION_TEXT = "AMBER: Assessment of Metagenome BinnERs."
    VERSION = "2.0.7"
    SHELL = True

    NCBI_MODES = ["none", "manual", "data"]

    @classmethod
    def _binning_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("binning_files", inputs.get("input_files")))

    @classmethod
    def _labels(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("labels"))

    @classmethod
    def _thresholds(cls, inputs: dict[str, Any], key: str) -> list[str]:
        return _as_list(inputs.get(key))

    @classmethod
    def _ncbi_mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("ncbi_mode", "none") or "none")

    @classmethod
    def _ncbi_identifiers(cls, inputs: dict[str, Any], files: list[str]) -> list[str]:
        identifiers = _as_list(inputs.get("ncbi_identifiers", inputs.get("element_identifiers")))
        if not identifiers:
            identifiers = [Path(path).name for path in files]
        identifiers.extend(Path(path).name for path in files[len(identifiers) :])
        return [_safe_identifier(identifier) for identifier in identifiers[: len(files)]]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [_shell_join(["mkdir", "-p", "output", "inputs", f"{out}/html_files"])]
        ncbi_mode = cls._ncbi_mode(inputs)
        if ncbi_mode == "manual":
            commands[0] = _shell_join(["mkdir", "-p", "output", "inputs", f"{out}/html_files", "ncbi"])
            ncbi_files = _as_list(inputs.get("ncbi_files"))
            for file, identifier in zip(ncbi_files, cls._ncbi_identifiers(inputs, ncbi_files), strict=False):
                commands.append(_shell_join(["ln", "-s", file, f"./ncbi/{identifier}"]))
        binning_files = cls._binning_files(inputs)
        for index, file in enumerate(binning_files):
            commands.append(_shell_join(["ln", "-s", file, f"./inputs/{index}.tsv"]))

        cmd = ["amber.py", "-g", str(inputs.get("gold_standard_file", ""))]
        labels = cls._labels(inputs)
        if labels:
            cmd.extend(["-l", ",".join(labels)])
        cmd.extend(["-p", str(inputs.get("filter", 0))])
        if str(inputs.get("min_length", "")) != "":
            cmd.extend(["-n", str(inputs.get("min_length"))])
        if str(inputs.get("desc", "")) != "":
            cmd.extend(["-d", str(inputs.get("desc"))])
        min_completeness = cls._thresholds(inputs, "min_completeness")
        if min_completeness:
            cmd.extend(["--min_completeness", ",".join(min_completeness)])
        max_contamination = cls._thresholds(inputs, "max_contamination")
        if max_contamination:
            cmd.extend(["--max_contamination", ",".join(max_contamination)])
        _add_if_value(cmd, "-r", inputs.get("remove_genomes"))
        _add_if_value(cmd, "-k", inputs.get("remove_keyword"))
        _add_if_value(cmd, "--genome_coverage", inputs.get("genome_coverage"))
        if ncbi_mode == "manual":
            cmd.extend(["--ncbi_dir", "ncbi"])
        elif ncbi_mode == "data":
            cmd.extend(["--ncbi_dir", str(inputs.get("ncbi_dir", ""))])
        cmd.extend(["-o", "output"])
        cmd.extend(f"inputs/{index}.tsv" for index in range(len(binning_files)))
        commands.append(_shell_join(cmd))
        commands.append(_shell_join(["mv", "output/heatmap_bar.png", f"{out}/html_files"]))
        commands.extend(
            [
                _shell_join(["cp", "output/index.html", f"{out}/index.html"]),
                _shell_join(["cp", "output/results.tsv", f"{out}/results.tsv"]),
                _shell_join(["cp", "output/genome_metrics_cami1.tsv", f"{out}/genome_metrics_cami1.tsv"]),
                _shell_join(["cp", "output/bin_metrics.tsv", f"{out}/bin_metrics.tsv"]),
            ]
        )
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        (out / "html_files").mkdir(parents=True, exist_ok=True)
        return [
            out / "index.html",
            out / "results.tsv",
            out / "genome_metrics_cami1.tsv",
            out / "bin_metrics.tsv",
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "gold_standard_file": ("TSV", {"description": "Gold standard CAMI biobox file with sequence lengths"}),
                "binning_files": ("TSV", {"multiple": True, "description": "CAMI biobox binning files to evaluate"}),
            },
            "optional": {
                "labels": ("STRING", {"default": [], "multiple": True, "description": "Optional labels for binning files"}),
                "filter": ("INT", {"default": 0, "min": 0, "description": "Filter out the n smallest genome bins"}),
                "min_length": ("INT", {"default": "", "min": 1, "description": "Minimum sequence length"}),
                "desc": ("STRING", {"default": "", "description": "HTML report description"}),
                "min_completeness": (
                    "INT",
                    {"default": [], "multiple": True, "min": 0, "max": 100, "description": "Minimum completeness thresholds"},
                ),
                "max_contamination": (
                    "INT",
                    {"default": [], "multiple": True, "min": 0, "max": 100, "description": "Maximum contamination thresholds"},
                ),
                "remove_genomes": ("TSV", {"default": "", "description": "Genome removal list"}),
                "remove_keyword": ("STRING", {"default": "", "description": "Keyword for genome removal list"}),
                "genome_coverage": ("TSV", {"default": "", "description": "Genome coverage table"}),
                "ncbi_mode": ("STRING", {"default": "none", "options": cls.NCBI_MODES, "description": "NCBI taxonomy source"}),
                "ncbi_files": ("TSV", {"default": [], "multiple": True, "description": "Manual NCBI nodes, merged, and names DMP files"}),
                "ncbi_identifiers": (
                    "STRING",
                    {"default": [], "multiple": True, "advanced": True, "description": "Galaxy element identifiers for manual NCBI files"},
                ),
                "ncbi_dir": ("DIRECTORY", {"default": "", "description": "NCBI taxonomy directory from a data manager"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("gold_standard_file", "")).strip():
            return "gold_standard_file is required"
        binning_files = cls._binning_files(inputs)
        if not binning_files:
            return "at least one binning file is required"
        labels = cls._labels(inputs)
        if labels and len(labels) != len(binning_files):
            return "labels count must match binning_files count"
        for name, minimum in {"filter": 0, "min_length": 1}.items():
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < minimum:
                return f"{name} must be >= {minimum}"
        for name in ["min_completeness", "max_contamination"]:
            for raw in cls._thresholds(inputs, name):
                try:
                    value = int(raw)
                except (TypeError, ValueError):
                    return f"{name} values must be integers"
                if not 0 <= value <= 100:
                    return f"{name} values must be between 0 and 100"
        ncbi_mode = cls._ncbi_mode(inputs)
        if ncbi_mode not in cls.NCBI_MODES:
            return "ncbi_mode must be one of: none, manual, data"
        if ncbi_mode == "manual" and not _as_list(inputs.get("ncbi_files")):
            return "ncbi_files are required when ncbi_mode is manual"
        if ncbi_mode == "data" and not str(inputs.get("ncbi_dir", "")).strip():
            return "ncbi_dir is required when ncbi_mode is data"
        return super().VALIDATE_INPUTS(inputs)

class CamiAmberAddNode(CommandNode):
    """Add sequence lengths to a CAMI AMBER gold standard file."""

    NODE_ID = "cami_amber_add"
    DISPLAY_NAME = "CAMI AMBER add length column"
    REQUIRED_CONDA_PACKAGES = ["cami-amber"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Create an AMBER gold standard biobox file by adding sequence lengths from matching FASTA or FASTQ records."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "CAMI AMBER add length column",
        "AMBER gold standard length",
        "add_length_column.py",
        "biobox length column",
        "metagenome benchmark gold standard",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("file",)
    REQUIRED_EXECUTABLES = ["add_length_column.py"]
    DOCUMENTATION_URL = "https://github.com/CAMI-challenge/AMBER"
    CITATION_DOIS = ["10.1093/gigascience/giy069"]
    CITATION_URLS = [f"{DOI_URL}10.1093/gigascience/giy069"]
    CITATION_TEXT = "AMBER: Assessment of Metagenome BinnERs."
    VERSION = "2.0.7"
    SHELL = True

    @classmethod
    def _staged_name(cls, inputs: dict[str, Any], path_key: str, identifier_key: str) -> str:
        identifier = str(inputs.get(identifier_key, "") or "")
        if identifier:
            return _safe_identifier(identifier)
        return _safe_identifier(Path(str(inputs.get(path_key, ""))).name)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        gold_name = cls._staged_name(inputs, "gold_standard_file", "gold_standard_identifier")
        fasta_name = cls._staged_name(inputs, "fasta_file", "fasta_identifier")
        commands = [
            _shell_join(["mkdir", "-p", out]),
            _shell_join(["ln", "-s", str(inputs.get("gold_standard_file", "")), gold_name]),
            _shell_join(["ln", "-s", str(inputs.get("fasta_file", "")), fasta_name]),
        ]
        cmd = ["add_length_column.py", "-g", gold_name, "-f", fasta_name, ">", "gold_standard_file.tsv"]
        commands.append(_shell_join(cmd))
        commands.append(_shell_join(["cp", "gold_standard_file.tsv", f"{out}/gold_standard_file.tsv"]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "gold_standard_file.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "gold_standard_file": ("TSV", {"description": "Input CAMI biobox gold standard file"}),
                "fasta_file": ("FILE", {"description": "Matching FASTA/FASTQ file, optionally compressed"}),
            },
            "optional": {
                "gold_standard_identifier": ("STRING", {"default": "", "advanced": True, "description": "Galaxy element identifier"}),
                "fasta_identifier": ("STRING", {"default": "", "advanced": True, "description": "Galaxy element identifier"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("gold_standard_file", "")).strip():
            return "gold_standard_file is required"
        if not str(inputs.get("fasta_file", "")).strip():
            return "fasta_file is required"
        return super().VALIDATE_INPUTS(inputs)

class CamiAmberConvertNode(CommandNode):
    """Convert FASTA bins to CAMI AMBER biobox format."""

    NODE_ID = "cami_amber_convert"
    DISPLAY_NAME = "CAMI AMBER convert to biobox"
    REQUIRED_CONDA_PACKAGES = ["cami-amber"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Convert one or more FASTA bin files to CAMI AMBER biobox binning TSV format."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "CAMI AMBER convert to biobox",
        "AMBER biobox conversion",
        "convert_fasta_bins_to_biobox_format.py",
        "FASTA bins to biobox",
        "binning TSV",
    ]
    RETURN_TYPES = ("TSV", "DIRECTORY")
    RETURN_NAMES = ("binning_file", "binning_collection")
    REQUIRED_EXECUTABLES = ["convert_fasta_bins_to_biobox_format.py"]
    DOCUMENTATION_URL = "https://github.com/CAMI-challenge/AMBER"
    CITATION_DOIS = ["10.1093/gigascience/giy069"]
    CITATION_URLS = [f"{DOI_URL}10.1093/gigascience/giy069"]
    CITATION_TEXT = "AMBER: Assessment of Metagenome BinnERs."
    VERSION = "2.0.7"
    SHELL = True

    WORK_OPTIONS = ["single", "all"]

    @classmethod
    def _files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("files"))

    @classmethod
    def _file_identifiers(cls, inputs: dict[str, Any], files: list[str]) -> list[str]:
        identifiers = _as_list(inputs.get("file_identifiers", inputs.get("element_identifiers")))
        if not identifiers:
            identifiers = [Path(path).name for path in files]
        identifiers.extend(Path(path).name for path in files[len(identifiers) :])
        return [_safe_identifier(identifier) for identifier in identifiers[: len(files)]]

    @staticmethod
    def _single_output_name(identifier: str) -> str:
        return f"{identifier.split('.')[0]}.tsv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        files = cls._files(inputs)
        identifiers = cls._file_identifiers(inputs, files)
        commands = [_shell_join(["mkdir", "-p", "output", out])]
        for path, identifier in zip(files, identifiers, strict=False):
            commands.append(_shell_join(["ln", "-s", path, identifier]))
        work = str(inputs.get("work", "single") or "single")
        if work == "single":
            for identifier in identifiers:
                commands.append(
                    _shell_join(
                        [
                            "convert_fasta_bins_to_biobox_format.py",
                            "-o",
                            f"output/{cls._single_output_name(identifier)}",
                            identifier,
                        ]
                    )
                )
            commands.append(_shell_join(["cp", "-r", "output", f"{out}/binning_collection"]))
        else:
            commands.append(_shell_join(["convert_fasta_bins_to_biobox_format.py", "-o", "output/binning.tsv", *identifiers]))
            commands.append(_shell_join(["cp", "output/binning.tsv", f"{out}/binning.tsv"]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        if str(inputs.get("work", "single") or "single") == "all":
            return [out / "binning.tsv"]
        (out / "binning_collection").mkdir(parents=True, exist_ok=True)
        return [out / "binning_collection"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "work": ("STRING", {"default": "single", "options": cls.WORK_OPTIONS, "description": "Convert each bin separately or merge all bins"}),
                "files": ("FASTA", {"multiple": True, "description": "FASTA bin files"}),
            },
            "optional": {
                "file_identifiers": ("STRING", {"default": [], "multiple": True, "advanced": True, "description": "Galaxy element identifiers"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        files = cls._files(inputs)
        if not files:
            return "at least one FASTA file is required"
        work = str(inputs.get("work", "single") or "single")
        if work not in cls.WORK_OPTIONS:
            return "work must be one of: single, all"
        identifiers = _as_list(inputs.get("file_identifiers", inputs.get("element_identifiers")))
        if identifiers and len(identifiers) != len(files):
            return "file_identifiers count must match files count"
        return super().VALIDATE_INPUTS(inputs)

class BioboxAddTaxidNode(CommandNode):
    """Add taxonomy IDs to CAMI AMBER biobox binning data."""

    NODE_ID = "biobox_add_taxid"
    DISPLAY_NAME = "Biobox add taxid"
    REQUIRED_CONDA_PACKAGES = ["biobox_add_taxid"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Add taxid output from BAT or GTDB to biobox binning data."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Biobox add taxid",
        "biobox_add_taxid.py",
        "CAMI AMBER biobox taxid",
        "ContigID2TaxID",
        "BinID2TaxID",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["biobox_add_taxid.py"]
    DOCUMENTATION_URL = "https://github.com/SantaMcCloud/biobox_add_taxid/tree/release-1.0"
    CITATION_URLS = ["https://github.com/SantaMcCloud/biobox_add_taxid/tree/release-1.0"]
    CITATION_TEXT = "biobox_add_taxid: add TaxID columns to CAMI AMBER biobox files."
    VERSION = "1.2+galaxy0"
    SHELL = True

    INPUT_MODES = ["contig", "bin"]

    @classmethod
    def _input_mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("input_mode", inputs.get("is_select", "contig")) or "contig")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        mode = cls._input_mode(inputs)
        taxid_input = "contig2taxid" if mode == "contig" else "binid2taxid"
        staged_taxid = "contig.tsv" if mode == "contig" else "bin.tsv"
        taxid_flag = "-c" if mode == "contig" else "-b"
        commands = [
            _shell_join(["mkdir", "-p", out]),
            _shell_join(["ln", "-s", str(inputs.get("biobox_file", "")), "biobox.tsv"]),
            _shell_join(["ln", "-s", str(inputs.get(taxid_input, "")), staged_taxid]),
        ]
        commands.append(
            _shell_join(
                [
                    "biobox_add_taxid.py",
                    "biobox.tsv",
                    taxid_flag,
                    staged_taxid,
                    "-k_c",
                    str(inputs.get("key_col", "")),
                    "-t_c",
                    str(inputs.get("taxid_col", "")),
                ]
            )
        )
        commands.append(_shell_join(["cp", "modified_biobox_file.tsv", f"{out}/modified_biobox_file.tsv"]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "modified_biobox_file.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "biobox_file": ("TSV", {"description": "Input CAMI AMBER biobox file"}),
                "input_mode": (
                    "STRING",
                    {"default": "contig", "options": cls.INPUT_MODES, "description": "Taxonomy mapping input type"},
                ),
                "key_col": ("INT", {"min": 1, "description": "Column containing contig or bin identifiers"}),
                "taxid_col": ("INT", {"min": 1, "description": "Column containing NCBI TaxIDs"}),
            },
            "optional": {
                "contig2taxid": ("TSV", {"default": "", "description": "ContigID2TaxID table, for contig mode"}),
                "binid2taxid": ("TSV", {"default": "", "description": "BinID2TaxID table, for bin mode"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("biobox_file", "")).strip():
            return "biobox_file is required"
        mode = cls._input_mode(inputs)
        if mode not in cls.INPUT_MODES:
            return f"input_mode must be one of: {', '.join(cls.INPUT_MODES)}"
        if mode == "contig" and not str(inputs.get("contig2taxid", "")).strip():
            return "contig2taxid is required when input_mode is contig"
        if mode == "bin" and not str(inputs.get("binid2taxid", "")).strip():
            return "binid2taxid is required when input_mode is bin"
        for name in ["key_col", "taxid_col"]:
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                return f"{name} is required"
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < 1:
                return f"{name} must be >= 1"
        return super().VALIDATE_INPUTS(inputs)

class FargeneNode(CommandNode):
    """Identify fragmented antibiotic resistance genes with fARGene."""

    NODE_ID = "fargene"
    DISPLAY_NAME = "fargene"
    REQUIRED_CONDA_PACKAGES = ["fargene", "tar"]
    CATEGORY = "annotation"
    DESCRIPTION = "Identify and reconstruct antibiotic resistance genes from metagenomic reads or contigs with fARGene."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "fARGene",
        "fragmented antibiotic resistance genes",
        "antibiotic resistance gene identifier",
        "ARG prediction",
        "metagenomic resistance genes",
    ]
    RETURN_TYPES = ("TXT", "TGZ", "TXT", "DIRECTORY", "DIRECTORY")
    RETURN_NAMES = ("summary", "retrieved_fragments", "fargene_log", "hmmsearchresults", "predicted_genes")
    REQUIRED_EXECUTABLES = ["fargene", "tar"]
    DOCUMENTATION_URL = "https://github.com/fannyhb/fargene"
    CITATION_DOIS = ["10.1186/s40168-019-0670-1"]
    CITATION_URLS = [f"{DOI_URL}10.1186/s40168-019-0670-1"]
    CITATION_TEXT = "Identification and reconstruction of novel antibiotic resistance genes from metagenomes."
    VERSION = "0.1"
    SHELL = True

    INPUT_TYPES_ALLOWED = ["paired", "collection", "sequence"]
    MODELS = ["class_a", "class_b_1_2", "class_b_3", "class_c", "class_d_1", "class_d_2", "qnr"]

    @classmethod
    def _input_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("input_type", "") or "")

    @classmethod
    def _identifier(cls, inputs: dict[str, Any], path_key: str, identifier_key: str) -> str:
        identifier = str(inputs.get(identifier_key, "") or "")
        if identifier:
            return _safe_identifier(identifier)
        return _safe_identifier(Path(str(inputs.get(path_key, ""))).name)

    @classmethod
    def _sequence_identifiers(cls, inputs: dict[str, Any], sequences: list[str]) -> list[str]:
        identifiers = _as_list(inputs.get("sequence_identifiers", inputs.get("element_identifiers")))
        if not identifiers:
            identifiers = [Path(path).name for path in sequences]
        identifiers.extend(Path(path).name for path in sequences[len(identifiers) :])
        return [_safe_identifier(identifier) for identifier in identifiers[: len(sequences)]]

    @classmethod
    def _collection_entries(cls, inputs: dict[str, Any]) -> list[tuple[str, str, str]]:
        entries = []
        for index, item in enumerate(inputs.get("input_collection") or []):
            if isinstance(item, dict):
                identifier = _safe_identifier(str(item.get("identifier", item.get("name", f"pair_{index + 1}"))))
                entries.append((str(item.get("forward", "")), str(item.get("reverse", "")), identifier))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                entries.append((str(item[0]), str(item[1]), f"pair_{index + 1}"))
        return entries

    @classmethod
    def _add_optional_flags(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if float(inputs.get("meta_score", 0.0) or 0.0) != 0.0:
            cmd.extend(["--meta-score", str(inputs.get("meta_score"))])
        if float(inputs.get("score", 0.0) or 0.0) != 0.0:
            cmd.extend(["--score", str(inputs.get("score"))])
        if inputs.get("protein"):
            cmd.append("--protein")
        if int(inputs.get("min_orf_length", 90) or 90) != 90:
            cmd.extend(["--min-orf-length", str(inputs.get("min_orf_length"))])
        for key, flag in [
            ("retrieve_whole", "--retrieve-whole"),
            ("no_orf_predict", "--no-orf-predict"),
            ("no_quality_filtering", "--no-quality-filtering"),
            ("no_assembly", "--no-assembly"),
            ("orf_finder", "--orf-finder"),
            ("store_peptides", "--store-peptides"),
        ]:
            if inputs.get(key):
                cmd.append(flag)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [_shell_join(["mkdir", "-p", out])]
        input_type = cls._input_type(inputs)
        if input_type == "paired":
            r1_name = f"{cls._identifier(inputs, 'R1', 'R1_identifier')}.fastq"
            r2_name = f"{cls._identifier(inputs, 'R2', 'R2_identifier')}.fastq"
            commands.append(_shell_join(["ln", "-fs", str(inputs.get("R1", "")), r1_name]))
            commands.append(_shell_join(["ln", "-fs", str(inputs.get("R2", "")), r2_name]))
        elif input_type == "collection":
            for forward, reverse, identifier in cls._collection_entries(inputs):
                commands.append(_shell_join(["ln", "-fs", forward, f"{identifier}_1.fastq"]))
                commands.append(_shell_join(["ln", "-fs", reverse, f"{identifier}_2.fastq"]))
        elif input_type == "sequence":
            sequences = _as_list(inputs.get("input_sequence"))
            for path, identifier in zip(sequences, cls._sequence_identifiers(inputs, sequences), strict=False):
                commands.append(_shell_join(["ln", "-fs", path, f"{identifier}.fasta"]))

        cmd = ["fargene", "--infiles"]
        if input_type in {"paired", "collection"}:
            cmd.extend(["*.fastq", "--meta"])
        else:
            cmd.append("*.fasta")
        cmd.extend(
            [
                "--hmm-model",
                str(inputs.get("models", "class_a")),
                "--output",
                "fargene_output",
                "--tmp-dir",
                "tmp",
                "-p",
                f"${{GALAXY_SLOTS:-{inputs.get('threads', 4)}}}",
            ]
        )
        cls._add_optional_flags(cmd, inputs)
        command = _shell_join(cmd).replace("'${GALAXY_SLOTS:-", "${GALAXY_SLOTS:-").replace("}'", "}")
        if input_type in {"paired", "collection"}:
            command += " && tar -czf retrievedFragments.tar.gz fargene_output/retrievedFragments"
        command += " 2>&1"
        commands.append(command)
        commands.append(_shell_join(["cp", "fargene_output/results_summary.txt", f"{out}/results_summary.txt"]))
        if input_type in {"paired", "collection"}:
            commands.append(_shell_join(["cp", "retrievedFragments.tar.gz", f"{out}/retrievedFragments.tar.gz"]))
        commands.append(_shell_join(["cp", "fargene_analysis.log", f"{out}/fargene_analysis.log"]))
        commands.append(_shell_join(["cp", "-r", "fargene_output/hmmsearchresults", f"{out}/hmmsearchresults"]))
        commands.append(_shell_join(["cp", "-r", "fargene_output/predictedGenes", f"{out}/predictedGenes"]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        (out / "hmmsearchresults").mkdir(parents=True, exist_ok=True)
        (out / "predictedGenes").mkdir(parents=True, exist_ok=True)
        outputs = [out / "results_summary.txt"]
        if cls._input_type(inputs) in {"paired", "collection"}:
            outputs.append(out / "retrievedFragments.tar.gz")
        outputs.extend([out / "fargene_analysis.log", out / "hmmsearchresults", out / "predictedGenes"])
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_type": ("STRING", {"options": cls.INPUT_TYPES_ALLOWED, "description": "Paired reads, paired collection, or contigs/genomes"}),
                "models": ("STRING", {"default": "class_a", "options": cls.MODELS, "description": "Resistance gene HMM model"}),
            },
            "optional": {
                "R1": ("FASTQ", {"default": "", "description": "Forward reads for paired input"}),
                "R2": ("FASTQ", {"default": "", "description": "Reverse reads for paired input"}),
                "R1_identifier": ("STRING", {"default": "", "advanced": True, "description": "Galaxy element identifier for R1"}),
                "R2_identifier": ("STRING", {"default": "", "advanced": True, "description": "Galaxy element identifier for R2"}),
                "input_collection": ("FASTQ_LIST", {"default": [], "multiple": True, "description": "Paired read collection"}),
                "input_sequence": ("FASTA", {"default": [], "multiple": True, "description": "Input contigs or genomes"}),
                "sequence_identifiers": (
                    "STRING",
                    {"default": [], "multiple": True, "advanced": True, "description": "Galaxy element identifiers for sequences"},
                ),
                "score": ("FLOAT", {"default": 0.0, "min": 0, "description": "Threshold for classifying nearly complete genes"}),
                "meta_score": ("FLOAT", {"default": 0.0, "min": 0, "description": "Fragment score per amino acid"}),
                "protein": ("BOOLEAN", {"default": False, "description": "Use protein mode"}),
                "min_orf_length": ("INT", {"default": 90, "min": 1, "description": "Minimum predicted ORF length"}),
                "retrieve_whole": ("BOOLEAN", {"default": False, "description": "Retrieve whole sequence where a hit is detected"}),
                "no_orf_predict": ("BOOLEAN", {"default": False, "description": "Disable ORF prediction"}),
                "no_quality_filtering": ("BOOLEAN", {"default": False, "description": "Disable metagenomic quality filtering"}),
                "no_assembly": ("BOOLEAN", {"default": False, "description": "Skip assembly and contig retrieval"}),
                "orf_finder": ("BOOLEAN", {"default": False, "description": "Use NCBI ORFfinder instead of prodigal"}),
                "store_peptides": ("BOOLEAN", {"default": False, "description": "Store translated sequences"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        input_type = cls._input_type(inputs)
        if input_type not in cls.INPUT_TYPES_ALLOWED:
            return "input_type must be one of: paired, collection, sequence"
        if input_type == "paired" and (not str(inputs.get("R1", "")).strip() or not str(inputs.get("R2", "")).strip()):
            return "R1 and R2 are required for paired input"
        if input_type == "collection" and not cls._collection_entries(inputs):
            return "input_collection is required for collection input"
        if input_type == "sequence" and not _as_list(inputs.get("input_sequence")):
            return "input_sequence is required for sequence input"
        model = str(inputs.get("models", "class_a") or "class_a")
        if model not in cls.MODELS:
            return "models must be one of: class_a, class_b_1_2, class_b_3, class_c, class_d_1, class_d_2, qnr"
        for name, minimum in {"score": 0, "meta_score": 0, "min_orf_length": 1, "threads": 1}.items():
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = float(raw) if name in {"score", "meta_score"} else int(raw)
            except (TypeError, ValueError):
                return f"{name} must be a number" if name in {"score", "meta_score"} else f"{name} must be an integer"
            if value < minimum:
                return f"{name} must be >= {minimum}"
        return super().VALIDATE_INPUTS(inputs)

class MetaBAT2Node(CommandNode):
    """Bin metagenomic contigs with MetaBAT2."""

    NODE_ID = "metabat2"
    DISPLAY_NAME = "MetaBAT2"
    REQUIRED_CONDA_PACKAGES = ["metabat2"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Bin metagenome assemblies using MetaBAT2 abundance and tetranucleotide-frequency clustering."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "MetaBAT2",
        "MetaBAT 2",
        "metagenome binning",
        "metabat2 bins",
        "contig abundance binning",
    ]
    RETURN_TYPES = ("DIRECTORY", "TSV", "DIRECTORY", "FASTA", "FASTA", "FASTA", "TXT")
    RETURN_NAMES = ("bins", "bin_saveCls", "bin_onlyLabel", "lowDepth", "tooShort", "unbinned", "process_log")
    REQUIRED_EXECUTABLES = ["metabat2"]
    DOCUMENTATION_URL = "https://bitbucket.org/berkeleylab/metabat/src/master/"
    CITATION_DOIS = ["10.7717/peerj.7359"]
    CITATION_URLS = [f"{DOI_URL}10.7717/peerj.7359"]
    CITATION_TEXT = "MetaBAT 2: an adaptive binning algorithm for robust and efficient genome reconstruction from metagenome assemblies."
    VERSION = "2.18.23"
    SHELL = True

    EXTRA_OUTPUTS = ["lowDepth", "tooShort", "unbinned", "log"]

    @classmethod
    def _extra_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("extra_outputs"))

    @classmethod
    def _base_coverage_depth(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("base_coverage_depth", "no") or "no")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = [
            "metabat2",
            "--inFile",
            str(inputs.get("inFile", "")),
            "--outFile",
            "bins/bin",
        ]
        if cls._base_coverage_depth(inputs) == "yes":
            if inputs.get("abdFile"):
                cmd.extend(["--abdFile", str(inputs.get("abdFile"))])
            elif inputs.get("cvExt"):
                cmd.extend(["--cvExt", str(inputs.get("cvExt"))])
        cmd.extend(
            [
                "--minContig",
                str(inputs.get("minContig", 2500)),
                "--minSmallContig",
                str(inputs.get("minSmallContig", 1000)),
                "--maxP",
                str(inputs.get("maxP", 95)),
                "--minS",
                str(inputs.get("minS", 60)),
                "--maxEdges",
                str(inputs.get("maxEdges", 200)),
                "--pTNF",
                str(inputs.get("pTNF", 0)),
            ]
        )
        if inputs.get("noAdd"):
            cmd.append("--noAdd")
        cmd.extend(
            [
                "--minRecruitingSize",
                str(inputs.get("minRecruitingSize", 10)),
                "--minCV",
                str(inputs.get("minCV", 1.0)),
                "--minCVSum",
                str(inputs.get("minCVSum", 1.0)),
                "--seed",
                str(inputs.get("seed", 0)),
                "--minClsSize",
                str(inputs.get("minClsSize", 200000)),
                "--numThreads",
                f"${{GALAXY_SLOTS:-{inputs.get('threads', 4)}}}",
            ]
        )
        if inputs.get("onlyLabel"):
            cmd.append("--onlyLabel")
        if inputs.get("saveCls"):
            if inputs.get("fullHeader"):
                cmd.append("--fullHeader")
            cmd.append("--noBinOut")
        if "unbinned" in cls._extra_outputs(inputs):
            cmd.append("--unbinned")
        command = _shell_join(cmd).replace("'${GALAXY_SLOTS:-", "${GALAXY_SLOTS:-").replace("}'", "}") + " > process_log.txt"
        commands = [_shell_join(["mkdir", "-p", "bins", out]), command]
        extra_outputs = cls._extra_outputs(inputs)
        if "log" in extra_outputs:
            commands.append(_shell_join(["mv", "process_log.txt", f"{out}/process_log.txt"]))
        if inputs.get("saveCls") and not inputs.get("onlyLabel"):
            commands.append(_shell_join(["cp", "bins/bin.MemberMatrix.txt", f"{out}/bin.MemberMatrix.txt"]))
        elif inputs.get("onlyLabel"):
            commands.append(_shell_join(["cp", "-r", "bins", f"{out}/bin_onlyLabel"]))
        else:
            commands.append(_shell_join(["cp", "-r", "bins", f"{out}/bins"]))
        for name, filename in [
            ("lowDepth", "bin.lowDepth.fa"),
            ("tooShort", "bin.tooShort.fa"),
            ("unbinned", "bin.unbinned.fa"),
        ]:
            if name in extra_outputs and not inputs.get("saveCls") and not inputs.get("onlyLabel"):
                commands.append(_shell_join(["cp", f"bins/{filename}", f"{out}/{filename}"]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs: list[Path]
        if inputs.get("saveCls") and not inputs.get("onlyLabel"):
            outputs = [out / "bin.MemberMatrix.txt"]
        elif inputs.get("onlyLabel"):
            (out / "bin_onlyLabel").mkdir(parents=True, exist_ok=True)
            outputs = [out / "bin_onlyLabel"]
        else:
            (out / "bins").mkdir(parents=True, exist_ok=True)
            outputs = [out / "bins"]
            extra_outputs = cls._extra_outputs(inputs)
            for name, filename in [
                ("lowDepth", "bin.lowDepth.fa"),
                ("tooShort", "bin.tooShort.fa"),
                ("unbinned", "bin.unbinned.fa"),
            ]:
                if name in extra_outputs:
                    outputs.append(out / filename)
        if "log" in cls._extra_outputs(inputs):
            outputs.append(out / "process_log.txt")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inFile": ("FASTA", {"description": "FASTA or FASTA.GZ file containing contigs"}),
            },
            "optional": {
                "base_coverage_depth": ("STRING", {"default": "no", "options": ["no", "yes"], "description": "Use a base coverage depth file"}),
                "abdFile": ("TSV", {"default": "", "description": "Depth matrix with mean and variance of base coverage"}),
                "cvExt": ("TSV", {"default": "", "description": "Base coverage depth file without variance"}),
                "minContig": ("INT", {"default": 2500, "min": 1500}),
                "minSmallContig": ("INT", {"default": 1000, "min": 500}),
                "maxP": ("INT", {"default": 95, "min": 1, "max": 100}),
                "minS": ("INT", {"default": 60, "min": 1, "max": 99}),
                "maxEdges": ("INT", {"default": 200, "min": 1}),
                "pTNF": ("INT", {"default": 0, "min": 0}),
                "noAdd": ("BOOLEAN", {"default": False}),
                "minRecruitingSize": ("INT", {"default": 10, "min": 0}),
                "minCV": ("FLOAT", {"default": 1.0, "min": 0}),
                "minCVSum": ("FLOAT", {"default": 1.0, "min": 0}),
                "seed": ("INT", {"default": 0, "min": 0}),
                "minClsSize": ("INT", {"default": 200000, "min": 0}),
                "onlyLabel": ("BOOLEAN", {"default": False, "description": "Output only sequence labels"}),
                "saveCls": ("BOOLEAN", {"default": False, "description": "Save cluster memberships as matrix"}),
                "fullHeader": ("BOOLEAN", {"default": False, "description": "Preserve full FASTA headers when saving cluster matrix"}),
                "extra_outputs": ("STRING_LIST", {"default": [], "options": cls.EXTRA_OUTPUTS, "description": "Additional MetaBAT2 outputs"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("inFile", "")).strip():
            return "inFile is required"
        base = cls._base_coverage_depth(inputs)
        if base not in {"no", "yes"}:
            return "base_coverage_depth must be one of: no, yes"
        if base == "yes" and not str(inputs.get("abdFile", "")).strip() and not str(inputs.get("cvExt", "")).strip():
            return "abdFile or cvExt is required when base_coverage_depth is yes"
        if inputs.get("saveCls") and inputs.get("onlyLabel"):
            return "saveCls and onlyLabel cannot both be enabled"
        for output in cls._extra_outputs(inputs):
            if output not in cls.EXTRA_OUTPUTS:
                return "extra_outputs values must be one or more of: lowDepth, tooShort, unbinned, log"
        integer_bounds = {
            "minContig": (1500, None),
            "minSmallContig": (500, None),
            "maxP": (1, 100),
            "minS": (1, 99),
            "maxEdges": (1, None),
            "pTNF": (0, None),
            "minRecruitingSize": (0, None),
            "seed": (0, None),
            "minClsSize": (0, None),
            "threads": (1, None),
        }
        for name, (minimum, maximum) in integer_bounds.items():
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < minimum:
                return f"{name} must be >= {minimum}"
            if maximum is not None and value > maximum:
                return f"{name} must be between {minimum} and {maximum}"
        for name in ["minCV", "minCVSum"]:
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                return f"{name} must be a number"
            if value < 0:
                return f"{name} must be >= 0"
        return super().VALIDATE_INPUTS(inputs)

class MetaBAT2JgiSummarizeBamContigDepthsNode(CommandNode):
    """Calculate contig depth matrices for MetaBAT2."""

    NODE_ID = "metabat2_jgi_summarize_bam_contig_depths"
    DISPLAY_NAME = "Calculate contig depths"
    REQUIRED_CONDA_PACKAGES = ["metabat2"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Calculate per-contig coverage depth matrices from one or more BAM files for MetaBAT2 binning."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Calculate contig depths",
        "jgi_summarize_bam_contig_depths",
        "MetaBAT2 depth matrix",
        "contig coverage depth",
        "BAM contig depths",
    ]
    RETURN_TYPES = ("TSV", "FASTA", "TSV", "TSV", "TSV")
    RETURN_NAMES = ("outputDepth", "outputPairedContigs", "outputGC", "outputReadStats", "outputKmers")
    REQUIRED_EXECUTABLES = ["jgi_summarize_bam_contig_depths"]
    DOCUMENTATION_URL = "https://bitbucket.org/berkeleylab/metabat/src/master/"
    CITATION_DOIS = ["10.7717/peerj.7359"]
    CITATION_URLS = [f"{DOI_URL}10.7717/peerj.7359"]
    CITATION_TEXT = "MetaBAT 2: an adaptive binning algorithm for robust and efficient genome reconstruction from metagenome assemblies."
    VERSION = "2.18.23"

    MODE_TYPES = ["individual", "co"]

    @classmethod
    def _mode_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("mode_type", inputs.get("type", "")) or "")

    @classmethod
    def _bam_inputs(cls, inputs: dict[str, Any]) -> list[str]:
        if cls._mode_type(inputs) == "individual":
            return _as_list(inputs.get("bam_indiv_input"))
        return _as_list(inputs.get("bam_co_inputs"))

    @classmethod
    def _use_reference(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("use_reference", "no") or "no")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = [
            "mkdir",
            "-p",
            out,
            "&&",
            "jgi_summarize_bam_contig_depths",
            "--outputDepth",
            f"{out}/outputDepth.tsv",
            "--percentIdentity",
            str(inputs.get("percentIdentity", 97)),
        ]
        if inputs.get("output_paired_contigs"):
            cmd.extend(["--pairedContigs", f"{out}/outputPairedContigs.fa"])
        if inputs.get("noIntraDepthVariance"):
            cmd.append("--noIntraDepthVariance")
        if inputs.get("showDepth"):
            cmd.append("--showDepth")
        cmd.extend(["--minMapQual", str(inputs.get("minMapQual", 0))])
        cmd.extend(["--weightMapQual", str(inputs.get("weightMapQual", 0.0))])
        if inputs.get("includeEdgeBases"):
            cmd.append("--includeEdgeBases")
        cmd.extend(["--maxEdgeBases", str(inputs.get("maxEdgeBases", 75))])
        if cls._use_reference(inputs) == "yes":
            cmd.extend(["--referenceFasta", str(inputs.get("referenceFasta", ""))])
            cmd.extend(["--outputGC", f"{out}/outputGC.tsv"])
            cmd.extend(["--gcWindow", str(inputs.get("gcWindow", 100))])
            cmd.extend(["--outputReadStats", f"{out}/outputReadStats.tsv"])
            cmd.extend(["--outputKmers", f"{out}/outputKmers.tsv"])
        cmd.extend(["--shredLength", str(inputs.get("shredLength", 16000))])
        cmd.extend(["--shredDepth", str(inputs.get("shredDepth", 5))])
        cmd.extend(["--minContigLength", str(inputs.get("minContigLength", 1))])
        cmd.extend(["--minContigDepth", str(inputs.get("minContigDepth", 0.0))])
        cmd.extend(cls._bam_inputs(inputs))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "outputDepth.tsv"]
        if inputs.get("output_paired_contigs"):
            outputs.append(out / "outputPairedContigs.fa")
        if cls._use_reference(inputs) == "yes":
            outputs.extend([out / "outputGC.tsv", out / "outputReadStats.tsv", out / "outputKmers.tsv"])
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "mode_type": ("STRING", {"options": cls.MODE_TYPES, "description": "Process one BAM or multiple BAM files together"}),
            },
            "optional": {
                "bam_indiv_input": ("BAM", {"default": "", "description": "BAM for individual mode"}),
                "bam_co_inputs": ("BAM", {"default": [], "multiple": True, "description": "BAM files for co-processing mode"}),
                "use_reference": ("STRING", {"default": "no", "options": ["no", "yes"], "description": "Use the reference genome for additional outputs"}),
                "reference_source": ("STRING", {"default": "cached", "options": ["cached", "history"], "advanced": True}),
                "referenceFasta": ("FASTA", {"default": "", "description": "Reference FASTA used for read mapping"}),
                "gcWindow": ("INT", {"default": 100, "min": 1, "description": "Sliding window size for GC calculations"}),
                "percentIdentity": ("INT", {"default": 97, "min": 0, "max": 100, "description": "Minimum end-to-end percent identity"}),
                "output_paired_contigs": ("BOOLEAN", {"default": False, "description": "Output sparse matrix of contigs spanned by paired reads"}),
                "noIntraDepthVariance": ("BOOLEAN", {"default": False, "description": "Remove variance from mean depth"}),
                "showDepth": ("BOOLEAN", {"default": False, "description": "Output per-base depth files"}),
                "minMapQual": ("INT", {"default": 0, "min": 0, "description": "Minimum mapping quality"}),
                "weightMapQual": ("FLOAT", {"default": 0.0, "min": 0, "description": "Weight per-base depth by mapping quality"}),
                "includeEdgeBases": ("BOOLEAN", {"default": False, "description": "Include edge bases when calculating depth"}),
                "maxEdgeBases": ("INT", {"default": 75, "min": 0, "description": "Maximum edge length for depth calculation"}),
                "shredLength": ("INT", {"default": 16000, "min": 1, "description": "Maximum shred length"}),
                "shredDepth": ("INT", {"default": 5, "min": 1, "description": "Depth for overlapping shreds"}),
                "minContigLength": ("INT", {"default": 1, "min": 1, "description": "Minimum contig length"}),
                "minContigDepth": ("FLOAT", {"default": 0.0, "min": 0, "description": "Minimum depth for breaking contigs"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        mode_type = cls._mode_type(inputs)
        if mode_type not in cls.MODE_TYPES:
            return "mode_type must be one of: individual, co"
        if mode_type == "individual" and not str(inputs.get("bam_indiv_input", "")).strip():
            return "bam_indiv_input is required for individual mode"
        if mode_type == "co" and not _as_list(inputs.get("bam_co_inputs")):
            return "at least one BAM is required for co mode"
        use_reference = cls._use_reference(inputs)
        if use_reference not in {"no", "yes"}:
            return "use_reference must be one of: no, yes"
        if use_reference == "yes" and not str(inputs.get("referenceFasta", "")).strip():
            return "referenceFasta is required when use_reference is yes"
        for name, minimum, maximum in [
            ("percentIdentity", 0, 100),
            ("gcWindow", 1, None),
            ("minMapQual", 0, None),
            ("maxEdgeBases", 0, None),
            ("shredLength", 1, None),
            ("shredDepth", 1, None),
            ("minContigLength", 1, None),
        ]:
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < minimum:
                return f"{name} must be >= {minimum}"
            if maximum is not None and value > maximum:
                return f"{name} must be between {minimum} and {maximum}"
        for name in ["weightMapQual", "minContigDepth"]:
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                return f"{name} must be a number"
            if value < 0:
                return f"{name} must be >= 0"
        return super().VALIDATE_INPUTS(inputs)

class FastSparNode(CommandNode):
    """Estimate sparse correlations for compositional OTU tables with FastSpar."""

    NODE_ID = "fastspar"
    DISPLAY_NAME = "FastSpar"
    REQUIRED_CONDA_PACKAGES = ["fastspar"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Estimate FastSpar/SparCC correlation and covariance matrices from compositional OTU count tables."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "FastSpar",
        "FastSpar correlation",
        "SparCC compositional correlation",
        "OTU correlation",
        "microbiome co-occurrence",
    ]
    RETURN_TYPES = ("TSV", "TSV")
    RETURN_NAMES = ("correlation", "covariance")
    REQUIRED_EXECUTABLES = ["fastspar"]
    DOCUMENTATION_URL = "https://github.com/scwatts/fastspar"
    CITATION_DOIS = ["10.1093/bioinformatics/bty734", "10.1371/journal.pcbi.1002687"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/bty734", f"{DOI_URL}10.1371/journal.pcbi.1002687"]
    CITATION_TEXT = "FastSpar: rapid and scalable correlation estimation for compositional data; Sparse correlations for compositional data."
    VERSION = "1.0.0"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = [
            "fastspar",
            "--otu_table",
            str(inputs.get("otu_table", "")),
            "--iterations",
            str(inputs.get("iterations", 50)),
            "--exclude_iterations",
            str(inputs.get("exclude_iterations", 10)),
            "--threshold",
            str(inputs.get("threshold", 0.1)),
            "--seed",
            str(inputs.get("seed", 1)),
            "--correlation",
            f"{out}/median_correlation.tsv",
            "--covariance",
            f"{out}/median_covariance.tsv",
            "--threads",
            f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}",
            "--yes",
        ]
        return _shell_join(["mkdir", "-p", out]) + " && " + _shell_join(cmd).replace("'${GALAXY_SLOTS:-", "${GALAXY_SLOTS:-").replace("}'", "}")

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "median_correlation.tsv", out / "median_covariance.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "otu_table": ("TSV", {"description": "Absolute OTU count table in TSV format"}),
            },
            "optional": {
                "iterations": ("INT", {"default": 50, "min": 1, "max": 1000, "description": "Correlation estimation rounds"}),
                "exclude_iterations": (
                    "INT",
                    {"default": 10, "min": 0, "max": 100, "description": "Iterations excluding highly correlated pairs"},
                ),
                "threshold": ("FLOAT", {"default": 0.1, "min": 0, "max": 1, "description": "Correlation exclusion threshold"}),
                "seed": ("INT", {"default": 1, "description": "Random number seed"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("otu_table", "")).strip():
            return "otu_table is required"
        for name, minimum, maximum in [
            ("iterations", 1, 1000),
            ("exclude_iterations", 0, 100),
            ("threads", 1, None),
        ]:
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < minimum or (maximum is not None and value > maximum):
                return f"{name} must be between {minimum} and {maximum}" if maximum is not None else f"{name} must be >= {minimum}"
        threshold_raw = inputs.get("threshold")
        if threshold_raw is not None and str(threshold_raw) != "":
            try:
                threshold = float(threshold_raw)
            except (TypeError, ValueError):
                return "threshold must be a number"
            if not 0 <= threshold <= 1:
                return "threshold must be between 0 and 1"
        return super().VALIDATE_INPUTS(inputs)

class FastSparReduceNode(CommandNode):
    """Filter FastSpar matrices into sparse edge tables."""

    NODE_ID = "fastspar_reduce"
    DISPLAY_NAME = "FastSpar: Reduce correlation table"
    REQUIRED_CONDA_PACKAGES = ["fastspar"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Filter FastSpar correlation and p-value matrices into sparse tabular edge lists."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "FastSpar reduce",
        "FastSpar: Reduce correlation table",
        "FastSpar sparse filter",
        "filtered correlations",
        "p-value threshold",
        "microbiome network edges",
    ]
    RETURN_TYPES = ("TSV", "TSV")
    RETURN_NAMES = ("correlations", "pvalues")
    REQUIRED_EXECUTABLES = ["fastspar_reduce"]
    DOCUMENTATION_URL = "https://github.com/scwatts/fastspar"
    CITATION_DOIS = ["10.1093/bioinformatics/bty734", "10.1371/journal.pcbi.1002687"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/bty734", f"{DOI_URL}10.1371/journal.pcbi.1002687"]
    CITATION_TEXT = "FastSpar: rapid and scalable correlation estimation for compositional data; Sparse correlations for compositional data."
    VERSION = "1.0.0"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = [
            "fastspar_reduce",
            "--correlation_table",
            str(inputs.get("correlation_table", "")),
            "--pvalue_table",
            str(inputs.get("pvalue_table", "")),
            "--correlation",
            str(inputs.get("correlation", 0.1)),
            "--pvalue",
            str(inputs.get("pvalue", 0.05)),
            "--output_prefix",
            "sparse",
        ]
        moves = [
            "mv",
            "sparse_filtered_correlation.tsv",
            f"{out}/filtered_correlations.tsv",
            "&&",
            "mv",
            "sparse_filtered_pvalue.tsv",
            f"{out}/filtered_pvalues.tsv",
        ]
        return f"{_shell_join(['mkdir', '-p', out])} && {_shell_join(cmd)} && {_shell_join(moves)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "filtered_correlations.tsv", out / "filtered_pvalues.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "correlation_table": ("TSV", {"description": "Symmetric FastSpar correlation matrix"}),
                "pvalue_table": ("TSV", {"description": "Matching FastSpar empirical p-value matrix"}),
            },
            "optional": {
                "correlation": (
                    "FLOAT",
                    {"default": 0.1, "min": 0, "max": 1, "description": "Minimum absolute correlation to retain"},
                ),
                "pvalue": ("FLOAT", {"default": 0.05, "min": 0, "max": 1, "description": "Maximum p-value to retain"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("correlation_table", "")).strip():
            return "correlation_table is required"
        if not str(inputs.get("pvalue_table", "")).strip():
            return "pvalue_table is required"
        for name in ["correlation", "pvalue"]:
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                return f"{name} must be a number"
            if not 0 <= value <= 1:
                return f"{name} must be between 0 and 1"
        return super().VALIDATE_INPUTS(inputs)

class FastSparPvaluesNode(CommandNode):
    """Estimate empirical p-values for FastSpar correlations."""

    NODE_ID = "fastspar_pvalues"
    DISPLAY_NAME = "FastSpar: estimate p-values"
    REQUIRED_CONDA_PACKAGES = ["fastspar", "parallel"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Estimate empirical p-values for FastSpar correlations with bootstrap resampling."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "FastSpar p-values",
        "FastSpar: estimate p-values",
        "FastSpar bootstrap p-values",
        "SparCC empirical p-values",
        "microbiome correlation significance",
    ]
    RETURN_TYPES = ("TSV", "TSV", "TSV")
    RETURN_NAMES = ("correlation", "covariance", "pvalues")
    REQUIRED_EXECUTABLES = ["fastspar", "fastspar_bootstrap", "fastspar_pvalues", "parallel"]
    DOCUMENTATION_URL = "https://github.com/scwatts/fastspar"
    CITATION_DOIS = ["10.1093/bioinformatics/bty734", "10.1371/journal.pcbi.1002687"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/bty734", f"{DOI_URL}10.1371/journal.pcbi.1002687"]
    CITATION_TEXT = "FastSpar: rapid and scalable correlation estimation for compositional data; Sparse correlations for compositional data."
    VERSION = "1.0.0"
    SHELL = True

    @classmethod
    def _slots(cls, inputs: dict[str, Any]) -> str:
        return f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}"

    @classmethod
    def _shell(cls, cmd: list[str]) -> str:
        command = re.sub(r"'\$\{GALAXY_SLOTS:-([^}]+)\}'", r"${GALAXY_SLOTS:-\1}", _shell_join(cmd))
        return (
            command.replace("'{}'", "{}")
            .replace("'bootstrap_correlation/cor_{/}'", "bootstrap_correlation/cor_{/}")
            .replace("'bootstrap_correlation/cov_{/}'", "bootstrap_correlation/cov_{/}")
            .replace("'bootstrap_counts/*'", "bootstrap_counts/*")
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        slots = cls._slots(inputs)
        otu_table = str(inputs.get("otu_table", ""))
        iterations = str(inputs.get("iterations", 50))
        exclude_iterations = str(inputs.get("exclude_iterations", 10))
        threshold = str(inputs.get("threshold", 0.1))
        seed = str(inputs.get("seed", 1))
        number = str(inputs.get("number", 1000))
        mode = str(inputs.get("correlation_mode", "original") or "original")

        steps = [cls._shell(["mkdir", "-p", out, "bootstrap_counts", "bootstrap_correlation"])]
        if mode == "new":
            correlation_file = f"{out}/median_correlation.tsv"
            steps.append(
                cls._shell(
                    [
                        "fastspar",
                        "--otu_table",
                        otu_table,
                        "--iterations",
                        iterations,
                        "--exclude_iterations",
                        exclude_iterations,
                        "--threshold",
                        threshold,
                        "--seed",
                        seed,
                        "--correlation",
                        correlation_file,
                        "--covariance",
                        f"{out}/median_covariance.tsv",
                        "--threads",
                        slots,
                        "--yes",
                    ]
                )
            )
        else:
            correlation_file = str(inputs.get("correlation_file", ""))

        steps.append(
            cls._shell(
                [
                    "fastspar_bootstrap",
                    "--otu_table",
                    otu_table,
                    "--number",
                    number,
                    "--prefix",
                    "bootstrap_counts/data",
                    "--seed",
                    seed,
                    "--threads",
                    slots,
                ]
            )
        )
        steps.append(
            cls._shell(
                [
                    "parallel",
                    "--max-procs",
                    slots,
                    "fastspar",
                    "--otu_table",
                    "{}",
                    "--correlation",
                    "bootstrap_correlation/cor_{/}",
                    "--covariance",
                    "bootstrap_correlation/cov_{/}",
                    "--iterations",
                    iterations,
                    "--exclude_iterations",
                    exclude_iterations,
                    "--threshold",
                    threshold,
                    "--seed",
                    seed,
                    ":::",
                    "bootstrap_counts/*",
                ]
            )
        )
        pvalues_cmd = [
            "fastspar_pvalues",
            "--otu_table",
            otu_table,
            "--correlation",
            correlation_file,
            "--prefix",
            "bootstrap_correlation/cor_data_",
            "--permutations",
            number,
        ]
        if inputs.get("pseudo"):
            pvalues_cmd.append("--pseudo")
        pvalues_cmd.extend(["--threads", slots, "--outfile", f"{out}/pvalues.tsv"])
        steps.append(cls._shell(pvalues_cmd))
        return " && ".join(steps)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = []
        if str(inputs.get("correlation_mode", "original") or "original") == "new":
            outputs.extend([out / "median_correlation.tsv", out / "median_covariance.tsv"])
        outputs.append(out / "pvalues.tsv")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "otu_table": ("TSV", {"description": "Absolute OTU count table in TSV format"}),
            },
            "optional": {
                "correlation_mode": (
                    "STRING",
                    {"default": "original", "options": ["new", "original"], "description": "Recalculate or use an existing correlation matrix"},
                ),
                "correlation_file": ("TSV", {"default": "", "description": "Existing FastSpar correlation matrix for original mode"}),
                "number": ("INT", {"default": 1000, "min": 10, "max": 10000, "description": "Number of bootstrap samples"}),
                "iterations": ("INT", {"default": 50, "min": 1, "max": 1000, "description": "Correlation estimation rounds"}),
                "exclude_iterations": (
                    "INT",
                    {"default": 10, "min": 0, "max": 100, "description": "Iterations excluding highly correlated pairs"},
                ),
                "threshold": ("FLOAT", {"default": 0.1, "min": 0, "max": 1, "description": "Correlation exclusion threshold"}),
                "seed": ("INT", {"default": 1, "description": "Random number seed"}),
                "pseudo": ("BOOLEAN", {"default": False, "description": "Calculate pseudo p-values instead of exact p-values"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("otu_table", "")).strip():
            return "otu_table is required"
        mode = str(inputs.get("correlation_mode", "original") or "original")
        if mode not in {"new", "original"}:
            return "correlation_mode must be one of: new, original"
        if mode == "original" and not str(inputs.get("correlation_file", "")).strip():
            return "correlation_file is required when correlation_mode is original"
        for name, minimum, maximum in [
            ("number", 10, 10000),
            ("iterations", 1, 1000),
            ("exclude_iterations", 0, 100),
            ("threads", 1, None),
        ]:
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < minimum or (maximum is not None and value > maximum):
                return f"{name} must be between {minimum} and {maximum}" if maximum is not None else f"{name} must be >= {minimum}"
        threshold_raw = inputs.get("threshold")
        if threshold_raw is not None and str(threshold_raw) != "":
            try:
                threshold = float(threshold_raw)
            except (TypeError, ValueError):
                return "threshold must be a number"
            if not 0 <= threshold <= 1:
                return "threshold must be between 0 and 1"
        return super().VALIDATE_INPUTS(inputs)

class IVarConsensusNode(CommandNode):
    """Call a viral amplicon consensus sequence from samtools mpileup using iVar."""

    NODE_ID = "ivar_consensus"
    DISPLAY_NAME = "iVar Consensus"
    REQUIRED_CONDA_PACKAGES = ["samtools", "ivar"]
    CATEGORY = "variant"
    DESCRIPTION = "Call a consensus FASTA from aligned viral amplicon reads with iVar consensus."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "ivar", "ivar consensus", "viral consensus", "amplicon consensus", "consensus fasta"]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("consensus_fasta",)
    REQUIRED_EXECUTABLES = ["samtools", "ivar"]
    DOCUMENTATION_URL = "https://andersen-lab.github.io/ivar/html/"
    CITATION_DOIS = ["10.1186/s13059-018-1618-7"]
    CITATION_URLS = [f"{DOI_URL}10.1186/s13059-018-1618-7"]
    CITATION_TEXT = "An amplicon-based sequencing framework for accurately measuring intrahost virus diversity using PrimalSeq and iVar."
    VERSION = "1.4.4"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = [
            "samtools",
            "mpileup",
            "-A",
            "-a",
            "-d",
            "0",
            "-Q",
            "0",
            str(inputs.get("input_bam", "")),
            "|",
            "ivar",
            "consensus",
            "-p",
            f"{out}/consensus",
            "-q",
            str(inputs.get("min_qual", 20)),
            "-t",
            str(inputs.get("min_freq", 0.0)),
            "-c",
            str(inputs.get("min_indel_freq", 0.8)),
            "-m",
            str(inputs.get("min_depth", 10)),
        ]
        depth_action = str(inputs.get("depth_action", "-n N") or "")
        if depth_action:
            cmd.extend(depth_action.split())
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "consensus.fa"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bam": ("BAM", {"description": "Aligned BAM file"}),
                "min_qual": ("INT", {"default": 20, "min": 0, "max": 255}),
                "min_freq": ("FLOAT", {"default": 0.0, "min": 0, "max": 1}),
                "min_indel_freq": ("FLOAT", {"default": 0.8, "min": 0, "max": 1}),
                "min_depth": ("INT", {"default": 10, "min": 1}),
                "depth_action": ("STRING", {"default": "-n N", "options": ["-k", "-n N", "-n -"]}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class IVarFilterVariantsNode(CommandNode):
    """Filter iVar variant TSV calls across replicates or samples."""

    NODE_ID = "ivar_filtervariants"
    DISPLAY_NAME = "iVar Filter Variants"
    REQUIRED_CONDA_PACKAGES = ["ivar"]
    CATEGORY = "variant"
    DESCRIPTION = "Intersect iVar variant TSV calls across replicates or samples aligned to the same reference."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ivar",
        "ivar filtervariants",
        "replicate variants",
        "variant intersection",
        "viral variant filtering",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("filtered_variants",)
    REQUIRED_EXECUTABLES = ["ivar"]
    DOCUMENTATION_URL = "https://andersen-lab.github.io/ivar/html/"
    CITATION_DOIS = ["10.1186/s13059-018-1618-7"]
    CITATION_URLS = [f"{DOI_URL}10.1186/s13059-018-1618-7"]
    CITATION_TEXT = "An amplicon-based sequencing framework for accurately measuring intrahost virus diversity using PrimalSeq and iVar."
    VERSION = "1.4.4"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = ["ivar", "filtervariants"]
        _add_if_value(cmd, "-t", inputs.get("min_fraction", 1.0))
        cmd.extend(["-p", f"{out}/filtered"])
        cmd.extend(_as_list(inputs.get("inputs")))
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "filtered.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputs": ("TSV", {"list": True, "description": "iVar variant TSV files for each replicate or sample"}),
            },
            "optional": {
                "min_fraction": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0,
                        "max": 1,
                        "description": "Minimum fraction of files required to contain the same variant",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class IVarTrimNode(CommandNode):
    """Soft-clip primers and quality-trim aligned amplicon reads with iVar."""

    NODE_ID = "ivar_trim"
    DISPLAY_NAME = "iVar Trim"
    REQUIRED_CONDA_PACKAGES = ["ivar", "viramp-hub", "samtools"]
    CATEGORY = "variant"
    DESCRIPTION = "Soft-clip primer sequences and quality-trim aligned viral amplicon reads with iVar trim."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ivar",
        "ivar trim",
        "primer trimming",
        "quality trimming",
        "amplicon trimming",
        "soft clip primers",
    ]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("trimmed_bam",)
    REQUIRED_EXECUTABLES = ["scheme-convert", "ivar", "samtools"]
    DOCUMENTATION_URL = "https://andersen-lab.github.io/ivar/html/"
    CITATION_DOIS = ["10.1186/s13059-018-1618-7"]
    CITATION_URLS = [f"{DOI_URL}10.1186/s13059-018-1618-7"]
    CITATION_TEXT = "An amplicon-based sequencing framework for accurately measuring intrahost virus diversity using PrimalSeq and iVar."
    VERSION = "1.4.4"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        bed = f"{out}/ivar.bed"
        amplicon_info = f"{out}/amplicon_info.tsv"
        cmd = [
            "scheme-convert",
            "--to",
            "bed",
            "--bed-type",
            "ivar",
            "-o",
            bed,
            str(inputs.get("input_bed", "")),
        ]
        amplicon_mode = str(inputs.get("amplicon_mode", "none"))
        if amplicon_mode in {"computed", "provided"}:
            cmd.extend(["&&", "scheme-convert"])
            if amplicon_mode == "provided":
                cmd.extend(["-a", str(inputs.get("amplicon_info", ""))])
            cmd.extend(["--to", "amplicon-info", "-r", "outer", "-o", amplicon_info, bed])
        cmd.extend(
            [
                "&&",
                "ivar",
                "trim",
                "-i",
                str(inputs.get("input_bam", "")),
                "-b",
                bed,
            ]
        )
        if amplicon_mode in {"computed", "provided"}:
            cmd.extend(["-f", amplicon_info])
        cmd.extend(["-x", str(inputs.get("primer_pos_wiggle", 0))])
        if inputs.get("include_reads_without_primers"):
            cmd.append("-e")
        trimmed_length_filter = str(inputs.get("trimmed_length_filter", "auto"))
        min_len = {
            "off": "0",
            "auto": "-1",
            "custom": str(inputs.get("min_len", 30)),
        }.get(trimmed_length_filter, "-1")
        cmd.extend(
            [
                "-m",
                min_len,
                "-q",
                str(inputs.get("min_qual", 20)),
                "-s",
                str(inputs.get("window_width", 4)),
                "|",
                "samtools",
                "sort",
                "-@",
                str(inputs.get("threads", 1)),
                "-T",
                "${TMPDIR:-.}",
                "-o",
                f"{out}/trimmed.sorted.bam",
                "-",
            ]
        )
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "trimmed.sorted.bam"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bam": ("BAM", {"description": "Aligned and sorted BAM to primer-trim"}),
                "input_bed": ("BED", {"description": "Six-column primer binding site BED"}),
                "amplicon_mode": (
                    "STRING",
                    {
                        "default": "none",
                        "options": ["none", "computed", "provided"],
                        "description": "Whether to drop reads not fully contained in known amplicons",
                    },
                ),
                "primer_pos_wiggle": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "description": "Wiggle room for read ends relative to primer binding sites",
                    },
                ),
                "include_reads_without_primers": (
                    "BOOLEAN",
                    {"default": False, "description": "Include reads that do not end in any primer binding site"},
                ),
                "min_qual": (
                    "INT",
                    {"default": 20, "min": 0, "max": 255, "description": "Sliding-window minimum base quality"},
                ),
                "window_width": (
                    "INT",
                    {"default": 4, "min": 0, "max": 255, "description": "Sliding-window width for quality trimming"},
                ),
                "trimmed_length_filter": (
                    "STRING",
                    {
                        "default": "auto",
                        "options": ["off", "auto", "custom"],
                        "description": "Minimum retained read length mode after trimming",
                    },
                ),
                "threads": (
                    "INT",
                    {"default": 1, "min": 1, "max": 128, "display": "slider", "description": "Threads for samtools sort"},
                ),
            },
            "optional": {
                "amplicon_info": (
                    "TSV",
                    {
                        "description": "Tab-separated primer names for each amplicon",
                        "displayOptions": {"show": {"amplicon_mode": ["provided"]}},
                    },
                ),
                "min_len": (
                    "INT",
                    {
                        "default": 30,
                        "min": 1,
                        "description": "Custom minimum trimmed read length",
                        "displayOptions": {"show": {"trimmed_length_filter": ["custom"]}},
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class IVarRemoveReadsNode(CommandNode):
    """Remove reads from iVar-trimmed BAMs when primer binding sites are affected."""

    NODE_ID = "ivar_removereads"
    DISPLAY_NAME = "iVar Remove Reads"
    REQUIRED_CONDA_PACKAGES = ["ivar", "viramp-hub", "python"]
    CATEGORY = "variant"
    DESCRIPTION = "Remove reads from iVar-trimmed BAMs for amplicons whose primer binding sites overlap variants."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ivar",
        "ivar removereads",
        "ivar getmasked",
        "primer mismatch",
        "remove primer-biased reads",
        "amplicon filtering",
    ]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("filtered_bam",)
    REQUIRED_EXECUTABLES = ["scheme-convert", "ivar", "python"]
    DOCUMENTATION_URL = "https://andersen-lab.github.io/ivar/html/"
    CITATION_DOIS = ["10.1186/s13059-018-1618-7"]
    CITATION_URLS = [f"{DOI_URL}10.1186/s13059-018-1618-7"]
    CITATION_TEXT = "An amplicon-based sequencing framework for accurately measuring intrahost virus diversity using PrimalSeq and iVar."
    VERSION = "1.4.4"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        bed = f"{out}/ivar.bed"
        amplicon_info = f"{out}/amplicon_info.tsv"
        masked_primers = f"{out}/masked_primers"
        masked_primers_txt = f"{masked_primers}.txt"
        cmd = [
            "scheme-convert",
            "--to",
            "bed",
            "--bed-type",
            "ivar",
            "-o",
            bed,
            str(inputs.get("input_bed", "")),
            "&&",
            "scheme-convert",
        ]
        if str(inputs.get("amplicon_mode", "computed")) == "provided":
            cmd.extend(["-a", str(inputs.get("amplicon_info", ""))])
        cmd.extend(
            [
                "--to",
                "amplicon-info",
                "-o",
                amplicon_info,
                bed,
                "&&",
                "ivar",
                "getmasked",
                "-i",
                str(inputs.get("variants_tsv", "")),
                "-b",
                bed,
                "-f",
                amplicon_info,
                "-p",
                masked_primers,
                "&&",
                "python",
                "-m",
                "bionodulo.nodes.scripts.ivar_complete_mask",
                masked_primers_txt,
                amplicon_info,
                "&&",
                "ivar",
                "removereads",
                "-i",
                str(inputs.get("input_bam", "")),
                "-b",
                bed,
                "-p",
                f"{out}/removed_reads.bam",
                "-t",
                masked_primers_txt,
            ]
        )
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "removed_reads.bam"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bam": ("BAM", {"description": "Aligned, sorted BAM preprocessed with iVar trim"}),
                "variants_tsv": (
                    "TSV",
                    {"description": "Variant TSV scanned for variants that affect primer binding sites"},
                ),
                "input_bed": ("BED", {"description": "Six-column primer binding site BED used for iVar trim"}),
                "amplicon_mode": (
                    "STRING",
                    {
                        "default": "computed",
                        "options": ["computed", "provided"],
                        "description": "Compute amplicon pairs from primer names or provide an amplicon-info table",
                    },
                ),
            },
            "optional": {
                "amplicon_info": (
                    "TSV",
                    {
                        "description": "Tab-separated primer names for each amplicon",
                        "displayOptions": {"show": {"amplicon_mode": ["provided"]}},
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class IVarVariantsNode(CommandNode):
    """Call viral amplicon variants from samtools mpileup using iVar."""

    NODE_ID = "ivar_variants"
    DISPLAY_NAME = "iVar Variants"
    REQUIRED_CONDA_PACKAGES = ["samtools", "ivar"]
    CATEGORY = "variant"
    DESCRIPTION = "Call iSNVs and indels from aligned viral amplicon reads with iVar variants."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "ivar", "ivar variants", "viral variants", "amplicon variants", "iSNV"]
    RETURN_TYPES = ("TSV", "VCF")
    RETURN_NAMES = ("variants_tsv", "variants_vcf")
    REQUIRED_EXECUTABLES = ["samtools", "ivar"]
    DOCUMENTATION_URL = "https://andersen-lab.github.io/ivar/html/"
    CITATION_DOIS = ["10.1186/s13059-018-1618-7"]
    CITATION_URLS = [f"{DOI_URL}10.1186/s13059-018-1618-7"]
    CITATION_TEXT = "An amplicon-based sequencing framework for accurately measuring intrahost virus diversity using PrimalSeq and iVar."
    VERSION = "1.4.4"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        output_format = str(inputs.get("output_format", "tabular"))
        cmd = [
            "samtools",
            "mpileup",
            "-A",
            "-d",
            "0",
            "--reference",
            str(inputs.get("ref", "")),
            "-B",
            "-Q",
            "0",
            str(inputs.get("input_bam", "")),
            "|",
            "ivar",
            "variants",
            "-p",
            f"{out}/variants",
            "-q",
            str(inputs.get("min_qual", 20)),
            "-t",
            str(inputs.get("min_freq", 0.03)),
        ]
        gtf = str(inputs.get("gtf", ""))
        if output_format in {"tabular", "tabular_and_vcf"} and gtf:
            cmd.extend(["-r", str(inputs.get("ref", "")), "-g", gtf])
        if output_format in {"vcf", "tabular_and_vcf"}:
            cmd.extend(["&&", "ivar_variants_to_vcf.py"])
            if inputs.get("pass_only"):
                cmd.append("--pass_only")
            cmd.extend([f"{out}/variants.tsv", f"{out}/variants.vcf"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        output_format = str(inputs.get("output_format", "tabular"))
        outputs: list[Path] = []
        if output_format in {"tabular", "tabular_and_vcf"}:
            outputs.append(out / "variants.tsv")
        if output_format in {"vcf", "tabular_and_vcf"}:
            outputs.append(out / "variants.vcf")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bam": ("BAM", {"description": "Aligned BAM file"}),
                "ref": ("FASTA", {"description": "Reference FASTA used for alignment"}),
                "min_qual": ("INT", {"default": 20, "min": 0, "max": 255}),
                "min_freq": ("FLOAT", {"default": 0.03, "min": 0, "max": 1}),
                "output_format": ("STRING", {"default": "tabular", "options": ["tabular", "vcf", "tabular_and_vcf"]}),
            },
            "optional": {
                "gtf": ("GFF", {"description": "Optional ORF annotations for amino-acid effect columns"}),
                "pass_only": ("BOOLEAN", {"default": False, "description": "Only include PASS variants in VCF output"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class GTDBTkClassifyWFNode(CommandNode):
    """Assign bacterial and archaeal taxonomy with GTDB-Tk classify_wf."""

    NODE_ID = "gtdbtk_classify_wf"
    DISPLAY_NAME = "GTDB-Tk Classify"
    REQUIRED_CONDA_PACKAGES = ["gtdbtk"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Classify one or more bacterial or archaeal genomes against the GTDB reference taxonomy."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "gtdbtk", "GTDB-Tk", "classify_wf", "taxonomy", "genome taxonomy", "MAG classification"]
    RETURN_TYPES = ("DIRECTORY", "DIRECTORY", "DIRECTORY", "DIRECTORY", "STATS_FILE")
    RETURN_NAMES = ("align", "identify", "classify", "summary", "process_log")
    REQUIRED_EXECUTABLES = ["gtdbtk"]
    DOCUMENTATION_URL = "https://ecogenomics.github.io/GTDBTk/commands/classify_wf.html"
    CITATION_DOIS = ["10.1093/bioinformatics/btz848"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/btz848"]
    CITATION_TEXT = "GTDB-Tk: a toolkit to classify genomes with the Genome Taxonomy Database."
    VERSION = "2.7.2"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        input_dir = f"{out}/input_dir"
        output_dir = f"{out}/output_dir"
        cmd = ["mkdir", "-p", input_dir, output_dir]
        genomes = _as_list(inputs.get("input"))
        extension = str(inputs.get("extension", "")).lstrip(".")
        for genome in genomes:
            link_name = _safe_name(genome)
            if extension and not link_name.endswith(f".{extension}"):
                link_name = f"{link_name}.{extension}"
            cmd.extend(["&&", "ln", "-sf", genome, f"{input_dir}/{link_name}"])

        cmd.extend([
            "&&",
            "export",
            f"GTDBTK_DATA_PATH={inputs.get('gtdbtk_data_path', '')}",
            "&&",
            "gtdbtk",
            "classify_wf",
            "--genome_dir",
            input_dir,
            "--extension",
            extension,
            "--out_dir",
            output_dir,
            "--cpus",
            str(inputs.get("threads", 4)),
            "--min_perc_aa",
            str(inputs.get("min_perc_aa", 10)),
        ])
        if inputs.get("force"):
            cmd.append("--force")
        cmd.extend(["--min_af", str(inputs.get("min_af", 0.65))])
        if inputs.get("full_tree"):
            cmd.append("--full_tree")
        if inputs.get("skip_ani_screen", True):
            cmd.append("--skip_ani_screen")
        if inputs.get("output_process_log"):
            cmd.extend([
                "&&",
                "cat",
                f"{output_dir}/gtdbtk.warnings.log",
                f"{output_dir}/gtdbtk.log",
                ">",
                f"{out}/process.log",
            ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        gtdbtk_out = out / "output_dir"
        outputs = [gtdbtk_out / "align", gtdbtk_out / "identify", gtdbtk_out / "classify", gtdbtk_out]
        if inputs.get("output_process_log"):
            outputs.append(out / "process.log")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTA_LIST", {"description": "Genome FASTA or FASTA.GZ files to classify"}),
                "gtdbtk_data_path": ("DIRECTORY", {"description": "Local GTDB-Tk reference database path"}),
            },
            "optional": {
                "extension": ("STRING", {"default": "fna.gz", "description": "Input genome extension visible to GTDB-Tk"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 256, "display": "slider"}),
                "min_perc_aa": ("INT", {"default": 10, "min": 0, "max": 100}),
                "force": ("BOOLEAN", {"default": False, "advanced": True}),
                "min_af": ("FLOAT", {"default": 0.65, "min": 0, "max": 1}),
                "full_tree": ("BOOLEAN", {"default": False, "advanced": True}),
                "skip_ani_screen": ("BOOLEAN", {"default": True, "description": "Skip ANI screen when a Mash DB is unavailable", "advanced": True}),
                "output_process_log": ("BOOLEAN", {"default": False, "description": "Emit combined GTDB-Tk warnings and process log"}),
            },
            "hidden": {"output": ("STRING", {})},
        }
