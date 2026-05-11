"""Variant calling and manipulation nodes for BioNodulo.

Provides nodes for variant calling with bcftools, GATK, FreeBayes,
and filtering with bcftools and VCFtools.
"""
from __future__ import annotations

from typing import Any

from bionodulo.nodes.command_node import CommandNode


class BcftoolsMpileupNode(CommandNode):
    """Call variants with bcftools mpileup + call."""
    NODE_ID = "bcftools_mpileup"
    DISPLAY_NAME = "bcftools mpileup + call"
    CATEGORY = "variant"
    DESCRIPTION = "Generate VCF variant calls from a BAM alignment using bcftools"
    SEARCH_ALIASES = ["bcftools", "mpileup", "variant call", "snp calling"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("vcf",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/bcftools.html"
    VERSION = "1.20"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "bcftools", "mpileup",
            "-f", str(inputs.get("reference", "")),
        ]
        if inputs.get("max_depth"):
            cmd.extend(["-d", str(inputs["max_depth"])])
        if inputs.get("min_bq"):
            cmd.extend(["-Q", str(inputs["min_bq"])])
        cmd.extend(["-Ou", str(inputs.get("bam", ""))])
        cmd.extend([
            "|", "bcftools", "call",
            "-mv", "-Oz",
            "-o", f"{inputs.get('output', '.')}/variants.vcf.gz",
        ])
        if inputs.get("ploidy"):
            cmd.extend(["--ploidy", str(inputs["ploidy"])])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM file (sorted and indexed)"}),
                "reference": ("FASTA", {"description": "Reference FASTA (indexed)"}),
            },
            "optional": {
                "max_depth": ("INT", {"default": 250, "min": 1, "label": "Max Depth", "advanced": True}),
                "min_bq": ("INT", {"default": 13, "min": 0, "label": "Min Base Quality", "advanced": True}),
                "ploidy": ("INT", {"default": 2, "min": 1, "max": 8, "display": "slider", "label": "Ploidy", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class BcftoolsIndexNode(CommandNode):
    """Index a VCF/BCF file."""
    NODE_ID = "bcftools_index"
    DISPLAY_NAME = "bcftools Index"
    CATEGORY = "variant"
    DESCRIPTION = "Index a VCF.gz or BCF file for fast random access"
    SEARCH_ALIASES = ["bcftools", "index", "tbi", "csi"]
    RETURN_TYPES = ("VCF_GZ", "VCF_INDEX")
    RETURN_NAMES = ("vcf", "index")
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/bcftools.html"
    VERSION = "1.20"
    COMMAND = [
        "bcftools", "index",
        "--tbi" if "{inputs.tbi}" == "True" else "--csi",
        "-f",
        "{inputs.vcf}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": ("VCF_GZ", {"description": "Compressed VCF or BCF file"}),
            },
            "optional": {
                "tbi": ("BOOLEAN", {"default": True, "description": "Use TBI format (vs CSI)"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class BcftoolsStatsNode(CommandNode):
    """Generate VCF statistics with bcftools."""
    NODE_ID = "bcftools_stats"
    DISPLAY_NAME = "bcftools Stats"
    CATEGORY = "variant"
    DESCRIPTION = "Generate statistics for a VCF file"
    SEARCH_ALIASES = ["bcftools", "stats", "vcf stats"]
    RETURN_TYPES = ("STATS_FILE",)
    RETURN_NAMES = ("stats",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/bcftools.html"
    VERSION = "1.20"
    SHELL = True
    COMMAND = [
        "bcftools", "stats",
        "{inputs.vcf}",
        ">", "{output}/vcf_stats.txt",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": ("VCF_GZ", {"description": "Input VCF file"}),
            },
            "optional": {
                "samples": ("STRING", {"default": "", "description": "Comma-separated sample list"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class BcftoolsFilterNode(CommandNode):
    """Filter variants with bcftools."""
    NODE_ID = "bcftools_filter"
    DISPLAY_NAME = "bcftools Filter"
    CATEGORY = "variant"
    DESCRIPTION = "Filter VCF variants using bcftools expressions"
    SEARCH_ALIASES = ["bcftools", "filter", "variant filter"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("filtered_vcf",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/bcftools.html"
    VERSION = "1.20"
    COMMAND = [
        "bcftools", "filter",
        "-i", "{inputs.expr}",
        "-Oz",
        "-o", "{output}/filtered.vcf.gz",
        "{inputs.vcf}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": ("VCF_GZ", {"description": "Input VCF file"}),
                "expr": ("STRING", {"default": 'QUAL>30 && DP>10', "description": "Filter expression"}),
            },
            "optional": {
                "set_gt": ("STRING", {"default": ""}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class GatkHaplotypeCallerNode(CommandNode):
    """Call variants with GATK HaplotypeCaller."""
    NODE_ID = "gatk_haplotype_caller"
    DISPLAY_NAME = "GATK HaplotypeCaller"
    CATEGORY = "variant"
    DESCRIPTION = "Call germline SNPs and indels with GATK HaplotypeCaller"
    SEARCH_ALIASES = ["gatk", "haplotypecaller", "variant", "snp", "indel"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("vcf",)
    REQUIRED_EXECUTABLES = ["gatk"]
    DOCUMENTATION_URL = "https://gatk.broadinstitute.org/hc/en-us/articles/360037225632-HaplotypeCaller"
    VERSION = "4.5.0"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "gatk", "HaplotypeCaller",
            "-R", str(inputs.get("reference", "")),
            "-I", str(inputs.get("bam", "")),
            "-O", f"{inputs.get('output', '.')}/variants.g.vcf.gz",
            "--native-pair-hmm-threads", str(inputs.get("threads", 4)),
        ]
        if inputs.get("emit_ref_confidence"):
            cmd.extend(["-ERC", str(inputs["emit_ref_confidence"])])
        if inputs.get("dbsnp"):
            cmd.extend(["--dbsnp", str(inputs["dbsnp"])])
        if inputs.get("stand_call_conf"):
            cmd.extend(["--standard-min-confidence-threshold-for-calling", str(inputs["stand_call_conf"])])
        if inputs.get("min_base_quality"):
            cmd.extend(["--min-base-quality-score", str(inputs["min_base_quality"])])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM (sorted, indexed, with read groups)"}),
                "reference": ("FASTA", {"description": "Reference FASTA (indexed)"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "emit_ref_confidence": ("STRING", {"default": "GVCF", "options": ["NONE", "GVCF", "BP_RESOLUTION"], "label": "Emit Ref Confidence", "advanced": True}),
                "dbsnp": ("VCF_GZ", {"description": "Optional dbSNP VCF for annotation", "advanced": True}),
                "stand_call_conf": ("INT", {"default": 30, "min": 0, "max": 100, "display": "slider", "label": "Call Confidence Threshold", "advanced": True}),
                "min_base_quality": ("INT", {"default": 10, "min": 0, "label": "Min Base Quality", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class GatkBaseRecalibratorNode(CommandNode):
    """Base quality score recalibration with GATK."""
    NODE_ID = "gatk_base_recalibrator"
    DISPLAY_NAME = "GATK BaseRecalibrator"
    CATEGORY = "variant"
    DESCRIPTION = "Recalibrate base quality scores using known variants"
    SEARCH_ALIASES = ["gatk", "bqsr", "recalibrate", "base quality"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("recal_table",)
    REQUIRED_EXECUTABLES = ["gatk"]
    DOCUMENTATION_URL = "https://gatk.broadinstitute.org/hc/en-us/articles/360036898312-BaseRecalibrator"
    VERSION = "4.5.0"
    COMMAND = [
        "gatk", "BaseRecalibrator",
        "-I", "{inputs.bam}",
        "-R", "{inputs.reference}",
        "--known-sites", "{inputs.known_sites}",
        "-O", "{output}/recal_data.table",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM file"}),
                "reference": ("FASTA", {"description": "Reference FASTA"}),
                "known_sites": ("VCF_GZ", {"description": "Known variants VCF (e.g., dbSNP, Mills)"}),
            },
            "optional": {},
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class GatkApplyBQSRNode(CommandNode):
    """Apply BQSR recalibration with GATK."""
    NODE_ID = "gatk_apply_bqsr"
    DISPLAY_NAME = "GATK ApplyBQSR"
    CATEGORY = "variant"
    DESCRIPTION = "Apply base quality score recalibration to a BAM file"
    SEARCH_ALIASES = ["gatk", "apply bqsr", "recalibrate"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("recalibrated_bam",)
    REQUIRED_EXECUTABLES = ["gatk"]
    DOCUMENTATION_URL = "https://gatk.broadinstitute.org/hc/en-us/articles/360037055952-ApplyBQSR"
    VERSION = "4.5.0"
    COMMAND = [
        "gatk", "ApplyBQSR",
        "-R", "{inputs.reference}",
        "-I", "{inputs.bam}",
        "--bqsr-recal-file", "{inputs.recal_table}",
        "-O", "{output}/recalibrated.bam",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM file"}),
                "reference": ("FASTA", {"description": "Reference FASTA"}),
                "recal_table": ("FILE", {"description": "Recalibration table from BaseRecalibrator"}),
            },
            "optional": {},
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class FreeBayesNode(CommandNode):
    """Call variants with FreeBayes."""
    NODE_ID = "freebayes"
    DISPLAY_NAME = "FreeBayes"
    CATEGORY = "variant"
    DESCRIPTION = "Bayesian haplotype-based variant caller"
    SEARCH_ALIASES = ["freebayes", "variant caller", "bayesian", "snp"]
    RETURN_TYPES = ("VCF",)
    RETURN_NAMES = ("vcf",)
    REQUIRED_EXECUTABLES = ["freebayes"]
    DOCUMENTATION_URL = "https://github.com/freebayes/freebayes"
    VERSION = "1.3.6"
    SHELL = True
    COMMAND = [
        "freebayes",
        "-f", "{inputs.reference}",
        "--pooled-continuous" if "{inputs.pooled}" == "True" else "",
        "{inputs.bam}",
        ">", "{output}/variants.vcf",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM file (sorted, indexed)"}),
                "reference": ("FASTA", {"description": "Reference FASTA"}),
            },
            "optional": {
                "pooled": ("BOOLEAN", {"default": False, "description": "Enable pooled calling"}),
                "ploidy": ("INT", {"default": 2, "min": 1, "max": 8, "display": "slider"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["freebayes", "-f", str(inputs.get("reference", ""))]
        if inputs.get("pooled"):
            cmd.append("--pooled-continuous")
        if inputs.get("ploidy"):
            cmd.extend(["-p", str(inputs["ploidy"])])
        cmd.append(str(inputs.get("bam", "")))
        cmd.extend([">", f"{inputs.get('output', '.')}/variants.vcf"])
        return cmd


class VcfToolsFilterNode(CommandNode):
    """Filter VCF with VCFtools."""
    NODE_ID = "vcftools_filter"
    DISPLAY_NAME = "VCFtools Filter"
    CATEGORY = "variant"
    DESCRIPTION = "Filter VCF files using VCFtools"
    SEARCH_ALIASES = ["vcftools", "filter", "vcf", "extract"]
    RETURN_TYPES = ("VCF",)
    RETURN_NAMES = ("filtered_vcf",)
    REQUIRED_EXECUTABLES = ["vcftools"]
    DOCUMENTATION_URL = "https://vcftools.github.io/index.html"
    VERSION = "0.1.16"
    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "vcftools",
            "--vcf", str(inputs.get("vcf", "")),
        ]
        if inputs.get("maf") is not None and float(inputs.get("maf", 0)) > 0:
            cmd.extend(["--maf", str(inputs["maf"])])
        if inputs.get("min_qual") is not None:
            cmd.extend(["--minQ", str(inputs["min_qual"])])
        if inputs.get("min_dp") is not None:
            cmd.extend(["--min-meanDP", str(inputs["min_dp"])])
        if inputs.get("max_missing") is not None:
            cmd.extend(["--max-missing", str(inputs["max_missing"])])
        cmd.extend([
            "--recode",
            "--out", f"{inputs.get('output', '.')}/filtered",
        ])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": ("VCF", {"description": "Input VCF file"}),
            },
            "optional": {
                "maf": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01, "description": "Minor allele frequency threshold", "advanced": True}),
                "min_qual": ("INT", {"default": 30, "min": 0, "label": "Min Quality", "advanced": True}),
                "min_dp": ("INT", {"default": 10, "min": 0, "label": "Min Depth", "advanced": True}),
                "max_missing": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01, "label": "Max Missing", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
