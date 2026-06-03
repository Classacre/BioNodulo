"""Variant calling and manipulation nodes for BioNodulo.

Provides nodes for variant calling with bcftools, GATK, FreeBayes,
and filtering with bcftools and VCFtools.
"""
from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


class BcftoolsMpileupNode(CommandNode):
    """Call variants with bcftools mpileup + call."""
    NODE_ID = "bcftools_mpileup"
    DISPLAY_NAME = "bcftools mpileup + call"
    REQUIRED_CONDA_PACKAGES = ['bcftools']
    CATEGORY = "variant"
    DESCRIPTION = "Generate VCF variant calls from a BAM alignment using bcftools"
    SEARCH_ALIASES = ["bcftools", "mpileup", "variant call", "snp calling"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("vcf",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/bcftools.html"
    VERSION = "1.22"
    SHELL = False

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get("output", inputs.get("output_dir", ".")))
        parts = [
            "bcftools", "mpileup",
            "-f", shlex.quote(str(inputs.get("reference", ""))),
        ]
        if inputs.get("max_depth"):
            parts.extend(["-d", shlex.quote(str(inputs["max_depth"]))])
        if inputs.get("min_bq"):
            parts.extend(["-Q", shlex.quote(str(inputs["min_bq"]))])
        parts.extend(["-Ou", shlex.quote(str(inputs.get("bam", "")))])
        parts.extend([
            "|", "bcftools", "call",
            "-mv", "-Oz",
            "-o", shlex.quote(f"{output}/vcf.vcf.gz"),
        ])
        if inputs.get("ploidy"):
            parts.extend(["--ploidy", shlex.quote(str(inputs["ploidy"]))])
        # Wrap in bash -c so the entire pipeline runs inside the pixi
        # environment when env_prefix is prepended by the executor.
        return ["bash", "-c", " ".join(parts)]

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


class Sniffles2Node(CommandNode):
    """Call structural variants from long-read alignments with Sniffles2."""
    NODE_ID = "sniffles2"
    DISPLAY_NAME = "Sniffles2 SV Caller"
    CATEGORY = "variant"
    DESCRIPTION = (
        "Long-read SV caller for PacBio HiFi and ONT. Supports tandem repeat annotation and phased SV output."
    )
    SEARCH_ALIASES = [
        "sniffles2",
        "sniffles",
        "structural variant",
        "long-read sv",
        "nanopore sv",
        "pacbio sv",
        "hifi sv",
    ]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("sv_vcf",)
    REQUIRED_EXECUTABLES = ["sniffles"]
    REQUIRED_CONDA_PACKAGES = ["sniffles"]
    DOCUMENTATION_URL = "https://github.com/fritzsedlazeck/Sniffles"
    VERSION = "2.5.3"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "sniffles",
            "--input", str(inputs.get("bam", "")),
            "--vcf", f"{inputs.get('output', '.')}/sv_vcf.vcf.gz",
            "--reference", str(inputs.get("reference", "")),
            "--threads", str(inputs.get("threads", 4)),
        ]
        if inputs.get("tandem_repeats"):
            cmd.extend(["--tandem-repeats", str(inputs["tandem_repeats"])])
        if inputs.get("minsvlen"):
            cmd.extend(["--minsvlen", str(inputs["minsvlen"])])
        if inputs.get("minsupport"):
            cmd.extend(["--minsupport", str(inputs["minsupport"])])
        if inputs.get("phase"):
            cmd.append("--phase")
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Sorted, indexed BAM from a long-read aligner"}),
                "reference": ("FASTA", {"description": "Reference FASTA"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "tandem_repeats": ("BED", {"description": "Tandem repeat annotations", "advanced": True}),
                "minsvlen": ("INT", {"default": 50, "min": 20, "label": "Min SV Length"}),
                "minsupport": ("INT", {"default": 10, "min": 1, "label": "Min Supporting Reads"}),
                "phase": ("BOOLEAN", {"default": False, "description": "Output phased SVs"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class SURVIVORMergeNode(CommandNode):
    """Merge structural variant callsets into a consensus VCF with SURVIVOR."""
    NODE_ID = "survivor_merge"
    DISPLAY_NAME = "SURVIVOR Merge"
    CATEGORY = "variant"
    DESCRIPTION = "Merge SV calls from multiple VCFs into a consensus callset for multi-caller pipelines."
    SEARCH_ALIASES = ["survivor", "merge sv", "consensus sv", "multi-caller", "structural variant merge"]
    RETURN_TYPES = ("VCF",)
    RETURN_NAMES = ("merged_sv",)
    REQUIRED_EXECUTABLES = ["SURVIVOR"]
    REQUIRED_CONDA_PACKAGES = ["survivor"]
    DOCUMENTATION_URL = "https://github.com/fritzsedlazeck/SURVIVOR"
    VERSION = "1.0.7"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get("output", ".")))
        out_dir.mkdir(parents=True, exist_ok=True)
        vcf_files = inputs.get("vcf_files", [])
        if isinstance(vcf_files, str):
            vcf_files = [vcf_files]

        sample_list = out_dir / "sample_files.txt"
        sample_list.write_text("".join(f"{vcf}\n" for vcf in vcf_files), encoding="utf-8")

        return [
            "SURVIVOR",
            "merge",
            str(sample_list),
            str(inputs.get("max_distance", 1000)),
            str(inputs.get("min_callers", 1)),
            str(inputs.get("use_type", 1)),
            str(inputs.get("use_strand", 1)),
            str(inputs.get("min_sv_size", 30)),
            str(out_dir / "merged_sv.vcf"),
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf_files": ("VCF_GZ", {"description": "List of VCF files to merge"}),
                "max_distance": ("INT", {"default": 1000, "min": 0, "label": "Max Breakpoint Distance (bp)"}),
                "min_callers": ("INT", {"default": 1, "min": 1, "label": "Min Supporting Callers"}),
            },
            "optional": {
                "use_type": ("INT", {"default": 1, "min": 0, "max": 1}),
                "use_strand": ("INT", {"default": 1, "min": 0, "max": 1}),
                "min_sv_size": ("INT", {"default": 30, "min": 10}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class CuteSVNode(CommandNode):
    """Call long-read structural variants with cuteSV."""
    NODE_ID = "cutesv"
    DISPLAY_NAME = "cuteSV Caller"
    CATEGORY = "variant"
    DESCRIPTION = "Efficient long-read SV caller for ONT and PacBio HiFi."
    SEARCH_ALIASES = [
        "cutesv",
        "cuteSV",
        "long-read sv",
        "nanopore sv",
        "pacbio sv",
        "structural variant",
    ]
    RETURN_TYPES = ("VCF",)
    RETURN_NAMES = ("sv_vcf",)
    REQUIRED_EXECUTABLES = ["cuteSV"]
    REQUIRED_CONDA_PACKAGES = ["cute-sv"]
    DOCUMENTATION_URL = "https://github.com/tjiangHIT/cuteSV"
    VERSION = "2.1.1"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = str(inputs.get("output", "."))
        cmd = [
            "cuteSV",
            "--threads",
            str(inputs.get("threads", 4)),
            "--genome",
            str(inputs.get("reference", "")),
            "--sample",
            str(inputs.get("sample_name", "sample")),
        ]
        if inputs.get("max_cluster_bias_ins"):
            cmd.extend(["--max_cluster_bias_INS", str(inputs["max_cluster_bias_ins"])])
        if inputs.get("min_size"):
            cmd.extend(["--min_size", str(inputs["min_size"])])
        if inputs.get("max_size"):
            cmd.extend(["--max_size", str(inputs["max_size"])])
        cmd.extend([
            str(inputs.get("bam", "")),
            f"{out_dir}/sv_vcf.vcf",
            out_dir,
        ])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input sorted, indexed BAM from a long-read aligner"}),
                "reference": ("FASTA", {"description": "Reference FASTA"}),
                "sample_name": ("STRING", {"default": "sample"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "max_cluster_bias_ins": ("INT", {"default": 1000, "min": 50, "label": "Max Cluster Bias INS"}),
                "min_size": ("INT", {"default": 30, "min": 10, "label": "Min SV Size"}),
                "max_size": ("INT", {"default": 100000, "min": 1000, "label": "Max SV Size"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class SVIMNode(CommandNode):
    """Call long-read structural variants with SVIM."""
    NODE_ID = "svim"
    DISPLAY_NAME = "SVIM SV Caller"
    CATEGORY = "variant"
    DESCRIPTION = "Long-read SV caller optimized for Oxford Nanopore data."
    SEARCH_ALIASES = ["svim", "long-read sv", "nanopore sv", "structural variant"]
    RETURN_TYPES = ("VCF",)
    RETURN_NAMES = ("sv_vcf",)
    REQUIRED_EXECUTABLES = ["svim"]
    REQUIRED_CONDA_PACKAGES = ["svim"]
    DOCUMENTATION_URL = "https://github.com/eldariont/svim"
    VERSION = "2.0.0"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = str(inputs.get("output", "."))
        cmd = [
            "svim",
            "alignment",
            "--sample",
            str(inputs.get("sample_name", "sample")),
        ]
        if inputs.get("min_sv_size"):
            cmd.extend(["--min_sv_size", str(inputs["min_sv_size"])])
        if inputs.get("max_sv_size"):
            cmd.extend(["--max_sv_size", str(inputs["max_sv_size"])])
        if inputs.get("sequence_alleles"):
            cmd.append("--sequence_alleles")
        if inputs.get("symbolic_alleles"):
            cmd.append("--symbolic_alleles")
        cmd.extend([
            "--interspersed_duplications_as_insertions",
            "--tandem_duplications_as_insertions",
            out_dir,
            str(inputs.get("bam", "")),
            str(inputs.get("reference", "")),
        ])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input sorted, indexed BAM from a long-read aligner"}),
                "reference": ("FASTA", {"description": "Reference FASTA (indexed)"}),
                "sample_name": ("STRING", {"default": "sample"}),
            },
            "optional": {
                "min_sv_size": ("INT", {"default": 50, "min": 20}),
                "max_sv_size": ("INT", {"default": 50000, "min": 1000}),
                "sequence_alleles": ("BOOLEAN", {"default": True}),
                "symbolic_alleles": ("BOOLEAN", {"default": False}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class SmooveNode(CommandNode):
    """Call and genotype structural variants with smoove."""
    NODE_ID = "smoove"
    DISPLAY_NAME = "Smoove SV Caller"
    CATEGORY = "variant"
    DESCRIPTION = "Automated SV calling with smoove (LUMPY wrapper), genotyping, and quality filtering."
    SEARCH_ALIASES = ["smoove", "lumpy", "structural variant", "sv caller", "genotyped sv"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("genotyped_sv",)
    REQUIRED_EXECUTABLES = ["smoove"]
    REQUIRED_CONDA_PACKAGES = ["smoove", "lumpy-sv", "svtyper"]
    DOCUMENTATION_URL = "https://github.com/brentp/smoove"
    VERSION = "0.2.8"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "smoove",
            "call",
            "--name",
            str(inputs.get("sample_name", "sample")),
            "--fasta",
            str(inputs.get("reference", "")),
            "-p",
            str(inputs.get("threads", 4)),
            "--outdir",
            str(inputs.get("output", ".")),
        ]
        if inputs.get("genotype"):
            cmd.append("--genotype")
        if inputs.get("exclude"):
            cmd.extend(["--exclude", str(inputs["exclude"])])
        cmd.append(str(inputs.get("bam", "")))
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM (sorted and indexed)"}),
                "reference": ("FASTA", {"description": "Reference FASTA (indexed)"}),
                "sample_name": ("STRING", {"default": "sample"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "exclude": ("BED", {"description": "Exclude regions BED", "advanced": True}),
                "genotype": ("BOOLEAN", {"default": True, "description": "Run svtyper genotyping"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class DellyNode(CommandNode):
    """Call structural variants with DELLY."""
    NODE_ID = "delly"
    DISPLAY_NAME = "DELLY SV Caller"
    CATEGORY = "variant"
    DESCRIPTION = "Paired-end + split-read SV caller. Supports germline, somatic, and long-read modes."
    SEARCH_ALIASES = ["delly", "structural variant", "sv caller", "somatic sv", "long-read sv"]
    RETURN_TYPES = ("BCF",)
    RETURN_NAMES = ("sv_calls",)
    REQUIRED_EXECUTABLES = ["delly"]
    REQUIRED_CONDA_PACKAGES = ["delly"]
    DOCUMENTATION_URL = "https://github.com/dellytools/delly"
    VERSION = "1.2.6"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        mode = inputs.get("mode", "call")
        cmd = [
            "delly",
            "lr" if mode == "lr" else "call",
            "-g",
            str(inputs.get("reference", "")),
            "-o",
            f"{inputs.get('output', '.')}/sv_calls.bcf",
        ]
        if inputs.get("exclude_regions"):
            cmd.extend(["-x", str(inputs["exclude_regions"])])
        if inputs.get("map_qual") is not None:
            cmd.extend(["-q", str(inputs["map_qual"])])
        cmd.append(str(inputs.get("bam", "")))
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM (sorted and indexed)"}),
                "reference": ("FASTA", {"description": "Reference FASTA"}),
                "mode": ("STRING", {"default": "call", "options": ["call", "lr"]}),
            },
            "optional": {
                "exclude_regions": ("BED", {"description": "Exclude regions BED", "advanced": True}),
                "map_qual": ("INT", {"default": 1, "min": 0, "label": "Min MapQ", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class MantaNode(CommandNode):
    """Call paired-end structural variants with Manta."""
    NODE_ID = "manta"
    DISPLAY_NAME = "Manta SV Caller"
    CATEGORY = "variant"
    DESCRIPTION = (
        "Call structural variants (DEL, DUP, INS, INV, BND) from paired-end sequencing. "
        "Supports germline and somatic modes."
    )
    SEARCH_ALIASES = [
        "manta",
        "structural variant",
        "sv caller",
        "illumina sv",
        "germline sv",
        "somatic sv",
    ]
    RETURN_TYPES = ("VCF_GZ", "VCF_GZ")
    RETURN_NAMES = ("candidate_sv", "diploid_sv")
    REQUIRED_EXECUTABLES = ["configManta.py", "runWorkflow.py"]
    REQUIRED_CONDA_PACKAGES = ["manta"]
    DOCUMENTATION_URL = "https://github.com/Illumina/manta"
    VERSION = "1.6.0"
    SHELL = True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        variants_dir = node_out / "results" / "variants"
        variants_dir.mkdir(parents=True, exist_ok=True)
        return [
            variants_dir / "candidateSV.vcf.gz",
            variants_dir / "diploidSV.vcf.gz",
        ]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = str(inputs.get("output", "."))
        cmd = [
            "configManta.py",
            "--bam",
            str(inputs.get("bam", "")),
            "--referenceFasta",
            str(inputs.get("reference", "")),
            "--runDir",
            out_dir,
        ]
        if inputs.get("normal_bam"):
            cmd.extend(["--normalBam", str(inputs["normal_bam"])])
        if inputs.get("exome"):
            cmd.append("--exome")
        if inputs.get("rna"):
            cmd.append("--rna")
        cmd.extend([
            "&&",
            f"{out_dir}/runWorkflow.py",
            "-m",
            "local",
            "-j",
            str(inputs.get("threads", 4)),
        ])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM (sorted and indexed)"}),
                "reference": ("FASTA", {"description": "Reference FASTA (indexed)"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "normal_bam": ("BAM", {"description": "Normal BAM for somatic mode", "advanced": True}),
                "exome": ("BOOLEAN", {"default": False, "description": "Exome/targeted mode", "advanced": True}),
                "rna": ("BOOLEAN", {"default": False, "description": "RNA-seq mode", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class CNVkitCallNode(CommandNode):
    """Convert CNVkit segment ratios to copy-number calls."""
    NODE_ID = "cnvkit_call"
    DISPLAY_NAME = "CNVkit Call"
    CATEGORY = "variant"
    DESCRIPTION = (
        "Convert segmented CNV ratios to absolute copy number calls. "
        "Supports purity, ploidy, and BAF integration."
    )
    SEARCH_ALIASES = ["cnvkit", "cnv call", "copy number", "segment", "call"]
    RETURN_TYPES = ("VCF",)
    RETURN_NAMES = ("cnv_calls",)
    REQUIRED_EXECUTABLES = ["cnvkit.py"]
    REQUIRED_CONDA_PACKAGES = ["cnvkit"]
    DOCUMENTATION_URL = "https://cnvkit.readthedocs.io/"
    VERSION = "0.9.12"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "cnvkit.py",
            "call",
            str(inputs.get("cns_file", "")),
            "-o",
            f"{inputs.get('output', '.')}/cnv_calls.vcf",
        ]
        if inputs.get("vcf"):
            cmd.extend(["--vcf", str(inputs["vcf"])])
        if inputs.get("sample_sex"):
            cmd.extend(["--sample-sex", str(inputs["sample_sex"])])
        if inputs.get("ploidy"):
            cmd.extend(["--ploidy", str(inputs["ploidy"])])
        if inputs.get("purity"):
            cmd.extend(["--purity", str(inputs["purity"])])
        if inputs.get("method"):
            cmd.extend(["--method", str(inputs["method"])])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "cns_file": ("FILE", {"description": "CNVkit .cns segment file"}),
            },
            "optional": {
                "vcf": ("VCF_GZ", {"description": "SNV VCF for BAF integration"}),
                "sample_sex": ("STRING", {"default": "", "options": ["", "male", "female"]}),
                "ploidy": ("INT", {"default": 2, "min": 1, "max": 8}),
                "purity": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05, "label": "Tumor Purity"},
                ),
                "method": ("STRING", {"default": "threshold", "options": ["threshold", "clonal", "none"]}),
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
    RETURN_TYPES = ("VCF_INDEX",)
    RETURN_NAMES = ("index",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    REQUIRED_CONDA_PACKAGES = ['bcftools']
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/bcftools.html"
    VERSION = "1.20"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "bcftools", "index",
            "--tbi" if inputs.get("tbi", True) else "--csi",
            "-f",
            str(inputs.get("vcf", "")),
        ]
        return cmd

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

    async def run(self, **kwargs):
        import shutil
        from pathlib import Path
        result = await super().run(**kwargs)
        vcf = kwargs.get("vcf", "")
        output_dir = kwargs.get("output_dir") or (kwargs.get("context") and getattr(kwargs["context"], "node_dir", "."))
        if vcf and output_dir:
            vcf_path = Path(vcf)
            tbi = vcf_path.with_suffix(vcf_path.suffix + ".tbi")
            csi = vcf_path.with_suffix(vcf_path.suffix + ".csi")
            index_file = tbi if tbi.exists() else csi
            outputs = self.__class__.PLAN_OUTPUTS(kwargs, output_dir)
            if index_file.exists() and outputs:
                target = outputs[0]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(index_file), str(target))
        return result


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
    REQUIRED_CONDA_PACKAGES = ['bcftools']
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/bcftools.html"
    VERSION = "1.20"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "bcftools", "stats",
            str(inputs.get("vcf", "")),
        ]
        if inputs.get("samples"):
            cmd.extend(["-s", str(inputs["samples"])])
        cmd.extend([">", f"{inputs.get('output', '.')}/stats.stats.txt"])
        return cmd

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
    REQUIRED_CONDA_PACKAGES = ['bcftools']
    CATEGORY = "variant"
    DESCRIPTION = "Filter VCF variants using bcftools expressions"
    SEARCH_ALIASES = ["bcftools", "filter", "variant filter"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("filtered_vcf",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/bcftools.html"
    VERSION = "1.20"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "bcftools", "filter",
            "-i", str(inputs.get("expr", "")),
            "-Oz",
            "-o", f"{inputs.get('output', '.')}/filtered_vcf.vcf.gz",
            str(inputs.get("vcf", "")),
        ]
        if inputs.get("set_gt"):
            cmd.extend(["--set-GT", str(inputs["set_gt"])])
        return cmd

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
    REQUIRED_CONDA_PACKAGES = ['gatk4']
    CATEGORY = "variant"
    DESCRIPTION = "Call germline SNPs and indels with GATK HaplotypeCaller"
    SEARCH_ALIASES = ["gatk", "haplotypecaller", "variant", "snp", "indel"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("vcf",)
    REQUIRED_EXECUTABLES = ["gatk"]
    DOCUMENTATION_URL = "https://gatk.broadinstitute.org/hc/en-us/articles/360037225632-HaplotypeCaller"
    VERSION = "4.6.2.0"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "gatk", "HaplotypeCaller",
            "-R", str(inputs.get("reference", "")),
            "-I", str(inputs.get("bam", "")),
            "-O", f"{inputs.get('output', '.')}/vcf.vcf.gz",
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
        if inputs.get("sample_ploidy"):
            cmd.extend(["-ploidy", str(inputs["sample_ploidy"])])
        if inputs.get("intervals"):
            cmd.extend(["-L", str(inputs["intervals"])])
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
                "sample_ploidy": ("INT", {"default": 2, "min": 1, "max": 8, "display": "slider", "label": "Sample Ploidy", "advanced": True}),
                "intervals": ("STRING", {"default": "", "description": "Intervals to process (e.g., chr1:1-1000)", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class GatkBaseRecalibratorNode(CommandNode):
    """Base quality score recalibration with GATK."""
    NODE_ID = "gatk_base_recalibrator"
    DISPLAY_NAME = "GATK BaseRecalibrator"
    REQUIRED_CONDA_PACKAGES = ['gatk4']
    CATEGORY = "variant"
    DESCRIPTION = "Recalibrate base quality scores using known variants"
    SEARCH_ALIASES = ["gatk", "bqsr", "recalibrate", "base quality"]
    RETURN_TYPES = ("TABLE",)
    RETURN_NAMES = ("recal_table",)
    REQUIRED_EXECUTABLES = ["gatk"]
    DOCUMENTATION_URL = "https://gatk.broadinstitute.org/hc/en-us/articles/360036898312-BaseRecalibrator"
    VERSION = "4.5.0"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "gatk", "BaseRecalibrator",
            "-I", str(inputs.get("bam", "")),
            "-R", str(inputs.get("reference", "")),
            "-O", f"{inputs.get('output', '.')}/recal_table.out",
        ]
        known = inputs.get("known_sites", "")
        if known:
            if isinstance(known, list):
                for ks in known:
                    cmd.extend(["--known-sites", str(ks)])
            else:
                for ks in str(known).split(","):
                    ks = ks.strip()
                    if ks:
                        cmd.extend(["--known-sites", ks])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM file"}),
                "reference": ("FASTA", {"description": "Reference FASTA"}),
                "known_sites": ("VCF_GZ", {"description": "Known variants VCF (e.g., dbSNP, Mills). Use comma-separated paths for multiple sites."}),
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
    RETURN_NAMES = ("bam",)
    REQUIRED_EXECUTABLES = ["gatk"]
    REQUIRED_CONDA_PACKAGES = ['gatk4']
    DOCUMENTATION_URL = "https://gatk.broadinstitute.org/hc/en-us/articles/360037055952-ApplyBQSR"
    VERSION = "4.5.0"
    COMMAND = [
        "gatk", "ApplyBQSR",
        "-R", "{inputs.reference}",
        "-I", "{inputs.bam}",
        "--bqsr-recal-file", "{inputs.recal_table}",
        "-O", "{output}/bam.bam",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM file"}),
                "reference": ("FASTA", {"description": "Reference FASTA"}),
                "recal_table": (("TABLE", "FILE"), {"description": "Recalibration table from BaseRecalibrator"}),
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
    REQUIRED_CONDA_PACKAGES = ['freebayes']
    CATEGORY = "variant"
    DESCRIPTION = "Bayesian haplotype-based variant caller"
    SEARCH_ALIASES = ["freebayes", "variant caller", "bayesian", "snp"]
    RETURN_TYPES = ("VCF",)
    RETURN_NAMES = ("vcf",)
    REQUIRED_EXECUTABLES = ["freebayes"]
    DOCUMENTATION_URL = "https://github.com/freebayes/freebayes"
    VERSION = "1.3.10"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["freebayes", "-f", str(inputs.get("reference", ""))]
        if inputs.get("pooled"):
            cmd.append("--pooled-continuous")
        if inputs.get("ploidy"):
            cmd.extend(["-p", str(inputs["ploidy"])])
        if inputs.get("min_mapping_quality") is not None:
            cmd.extend(["--min-mapping-quality", str(inputs["min_mapping_quality"])])
        if inputs.get("min_base_quality") is not None:
            cmd.extend(["--min-base-quality", str(inputs["min_base_quality"])])
        if inputs.get("haplotype_length") is not None:
            cmd.extend(["--haplotype-length", str(inputs["haplotype_length"])])
        cmd.append(str(inputs.get("bam", "")))
        cmd.extend([">", f"{inputs.get('output', '.')}/vcf.vcf"])
        return cmd

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
                "min_mapping_quality": ("INT", {"default": 1, "min": 0, "label": "Min Mapping Quality", "advanced": True}),
                "min_base_quality": ("INT", {"default": 0, "min": 0, "label": "Min Base Quality", "advanced": True}),
                "haplotype_length": ("INT", {"default": 3, "min": 0, "label": "Haplotype Length", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


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
    REQUIRED_CONDA_PACKAGES = ['vcftools']
    DOCUMENTATION_URL = "https://vcftools.github.io/index.html"
    VERSION = "0.1.17"
    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        vcf = str(inputs.get("vcf", ""))
        cmd = ["vcftools"]
        if vcf.endswith(".gz"):
            cmd.extend(["--gzvcf", vcf])
        else:
            cmd.extend(["--vcf", vcf])
        if inputs.get("maf") is not None and float(inputs.get("maf", 0)) > 0:
            cmd.extend(["--maf", str(inputs["maf"])])
        if inputs.get("min_qual") is not None:
            cmd.extend(["--minQ", str(inputs["min_qual"])])
        if inputs.get("min_dp") is not None:
            cmd.extend(["--min-meanDP", str(inputs["min_dp"])])
        if inputs.get("max_missing") is not None:
            cmd.extend(["--max-missing", str(inputs["max_missing"])])
        if inputs.get("recode_info_all"):
            cmd.append("--recode-INFO-all")
        cmd.extend([
            "--recode",
            "--out", f"{inputs.get('output', '.')}/filtered_vcf",
        ])
        return cmd

    async def run(self, **kwargs):
        import shutil
        from pathlib import Path
        result = await super().run(**kwargs)
        output_dir = kwargs.get("output_dir") or (kwargs.get("context") and getattr(kwargs["context"], "node_dir", "."))
        if output_dir:
            node_out = Path(output_dir) / self.__class__.NODE_ID
            actual = node_out / "filtered_vcf.recode.vcf"
            outputs = self.__class__.PLAN_OUTPUTS(kwargs, output_dir)
            if actual.exists() and outputs:
                target = outputs[0]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(actual), str(target))
        return result

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
                "recode_info_all": ("BOOLEAN", {"default": False, "description": "Recode all INFO fields", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
