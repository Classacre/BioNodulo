"""BioNodulo built-in wrapped tool nodes split by tool family."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

class RSeQCInferExperimentNode(CommandNode):
    """Infer RNA-seq strandedness from alignments and a BED12 gene model."""

    NODE_ID = "rseqc_infer_experiment"
    DISPLAY_NAME = "RSeQC Infer Experiment"
    REQUIRED_CONDA_PACKAGES = ["rseqc"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Estimate RNA-seq strandedness and library configuration from mapped reads."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "rseqc", "infer_experiment", "strandedness", "rna-seq qc", "library orientation"]
    RETURN_TYPES = ("STATS_FILE",)
    RETURN_NAMES = ("infer_experiment",)
    REQUIRED_EXECUTABLES = ["infer_experiment.py"]
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#infer-experiment-py"
    CITATION_DOIS = ["10.1093/bioinformatics/bts356"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/bts356"]
    CITATION_TEXT = "RSeQC: quality control of RNA-seq experiments."
    VERSION = "5.0.3"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "infer_experiment.py",
            "-i",
            str(inputs.get("input", "")),
            "-r",
            str(inputs.get("refgene", "")),
            "--sample-size",
            str(inputs.get("sample_size", 200000)),
            "--mapq",
            str(inputs.get("mapq", 30)),
        ]
        _add_shell_redirect(cmd, f"{_out(inputs)}/infer_experiment.txt")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "infer_experiment.txt"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "BAM or SAM alignment file"}),
                "refgene": ("BED", {"description": "Reference gene model in BED12 format"}),
            },
            "optional": {
                "sample_size": ("INT", {"default": 200000, "min": 1, "description": "Number of usable reads to sample"}),
                "mapq": ("INT", {"default": 30, "min": 0, "max": 255, "description": "Minimum mapping quality"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class RSeQCFPKMCountNode(CommandNode):
    """Calculate raw fragment counts, FPM, and FPKM per gene."""

    NODE_ID = "rseqc_fpkm_count"
    DISPLAY_NAME = "RSeQC FPKM Count"
    REQUIRED_CONDA_PACKAGES = ["rseqc"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Calculate raw read count, FPM, and FPKM for each gene in a BED12 reference gene model."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "rseqc", "FPKM_count", "fpkm", "gene expression", "fragments per kilobase", "rna-seq qc"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("fpkm_counts",)
    REQUIRED_EXECUTABLES = ["FPKM_count.py"]
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#fpkm-count-py"
    CITATION_DOIS = ["10.1093/bioinformatics/bts356"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/bts356"]
    CITATION_TEXT = "RSeQC: quality control of RNA-seq experiments."
    VERSION = "5.0.3"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = [
            "FPKM_count.py",
            "-i",
            str(inputs.get("input", "")),
            "-o",
            f"{out}/output",
            "-r",
            str(inputs.get("refgene", "")),
        ]

        strand_specific = str(inputs.get("strand_specific", "none"))
        if strand_specific == "pair":
            strand_rule = {
                "sd": "1++,1--,2+-,2-+",
                "ds": "1+-,1-+,2++,2--",
            }.get(str(inputs.get("pair_type", "sd")), "1++,1--,2+-,2-+")
            cmd.extend(["-d", strand_rule])
        elif strand_specific == "single":
            strand_rule = {
                "s": "++,--",
                "d": "+-,-+",
            }.get(str(inputs.get("single_type", "s")), "++,--")
            cmd.extend(["-d", strand_rule])

        if inputs.get("skip_multi_hits"):
            cmd.append("--skip-multi-hits")
            cmd.extend(["--mapq", str(inputs.get("mapq", 30))])
        if inputs.get("only_exonic"):
            cmd.append("--only-exonic")
        cmd.append(f"--single-read={inputs.get('single_read', '1')}")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.FPKM.xls"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "BAM alignment file"}),
                "refgene": ("BED", {"description": "Reference gene model in BED12 format"}),
            },
            "optional": {
                "strand_specific": ("STRING", {"default": "none", "options": ["none", "pair", "single"], "description": "Strand-specific library type"}),
                "pair_type": ("STRING", {"default": "sd", "options": ["sd", "ds"], "description": "Paired-end strand rule"}),
                "single_type": ("STRING", {"default": "s", "options": ["s", "d"], "description": "Single-end strand rule"}),
                "skip_multi_hits": ("BOOLEAN", {"default": False, "description": "Use only uniquely mapped reads"}),
                "mapq": ("INT", {"default": 30, "min": 0, "max": 255, "description": "Minimum mapping quality when skipping multiple-hit reads"}),
                "only_exonic": ("BOOLEAN", {"default": False, "description": "Count only UTR exon and CDS exon reads"}),
                "single_read": ("STRING", {"default": "1", "options": ["1", "0.5", "0"], "description": "How to count read pairs with only one mapped end"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class RSeQCRPKMSaturationNode(CommandNode):
    """Assess whether expression estimates are saturated by sequencing depth."""

    NODE_ID = "rseqc_rpkm_saturation"
    DISPLAY_NAME = "RSeQC RPKM Saturation"
    REQUIRED_CONDA_PACKAGES = ["rseqc"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Resample RNA-seq alignments to evaluate whether transcript RPKM estimates are stable at the current sequencing depth."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "rseqc",
        "RPKM_saturation",
        "rpkm saturation",
        "expression saturation",
        "sequencing depth",
        "jackknifing",
        "rna-seq qc",
    ]
    RETURN_TYPES = ("IMAGE", "TSV", "TSV", "TEXT")
    RETURN_NAMES = ("saturation_plot", "rpkm_values", "raw_counts", "r_script")
    REQUIRED_EXECUTABLES = ["RPKM_saturation.py"]
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#rpkm-saturation-py"
    CITATION_DOIS = ["10.1093/bioinformatics/bts356"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/bts356"]
    CITATION_TEXT = "RSeQC: quality control of RNA-seq experiments."
    VERSION = "5.0.3"

    @classmethod
    def _strand_rule(cls, inputs: dict[str, Any]) -> str:
        strand_specific = str(inputs.get("strand_specific", "none"))
        if strand_specific == "pair":
            return {
                "sd": "1++,1--,2+-,2-+",
                "ds": "1+-,1-+,2++,2--",
            }.get(str(inputs.get("pair_type", "sd")), "1++,1--,2+-,2-+")
        if strand_specific == "single":
            return {
                "s": "++,--",
                "d": "+-,-+",
            }.get(str(inputs.get("single_type", "s")), "++,--")
        return ""

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = [
            "RPKM_saturation.py",
            "-i",
            str(inputs.get("input", "")),
            "-o",
            f"{out}/output",
            "-r",
            str(inputs.get("refgene", "")),
        ]
        strand_rule = cls._strand_rule(inputs)
        if strand_rule:
            cmd.extend(["-d", strand_rule])
        cmd.extend(
            [
                "-l",
                str(inputs.get("percentile_floor", 5)),
                "-u",
                str(inputs.get("percentile_ceiling", 100)),
                "-s",
                str(inputs.get("percentile_step", 5)),
                "-c",
                str(inputs.get("rpkm_cutoff", "0.01")),
                "--mapq",
                str(inputs.get("mapq", 30)),
            ]
        )
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [
            out / "output.saturation.pdf",
            out / "output.eRPKM.xls",
            out / "output.rawCount.xls",
        ]
        if inputs.get("rscript_output"):
            outputs.append(out / "output.saturation.r")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "BAM or SAM alignment file"}),
                "refgene": ("BED", {"description": "Reference gene model in BED12 format"}),
            },
            "optional": {
                "strand_specific": (
                    "STRING",
                    {"default": "none", "options": ["none", "pair", "single"], "description": "Strand-specific library type"},
                ),
                "pair_type": ("STRING", {"default": "sd", "options": ["sd", "ds"], "description": "Paired-end strand rule"}),
                "single_type": ("STRING", {"default": "s", "options": ["s", "d"], "description": "Single-end strand rule"}),
                "percentile_floor": ("INT", {"default": 5, "min": 0, "max": 100, "description": "Lower resampling percentile"}),
                "percentile_ceiling": ("INT", {"default": 100, "min": 0, "max": 100, "description": "Upper resampling percentile"}),
                "percentile_step": ("INT", {"default": 5, "min": 1, "max": 100, "description": "Resampling percentile increment"}),
                "rpkm_cutoff": ("STRING", {"default": "0.01", "description": "Ignore transcripts with RPKM below this threshold"}),
                "mapq": ("INT", {"default": 30, "min": 0, "max": 255, "description": "Minimum mapping quality"}),
                "rscript_output": ("BOOLEAN", {"default": False, "description": "Expose the R script used to generate the saturation plot"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class RSeQCBam2WigNode(CommandNode):
    """Convert RNA-seq BAM alignments to wiggle coverage tracks."""

    NODE_ID = "rseqc_bam2wig"
    DISPLAY_NAME = "RSeQC BAM to Wiggle"
    REQUIRED_CONDA_PACKAGES = ["rseqc"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Convert RNA-seq BAM alignments into wiggle coverage tracks for genome browser visualization."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "rseqc",
        "bam2wig",
        "BAM to Wiggle",
        "wiggle",
        "coverage track",
        "genome browser",
        "rna-seq qc",
    ]
    RETURN_TYPES = ("WIG", "WIG", "WIG")
    RETURN_NAMES = ("wiggle", "forward_wiggle", "reverse_wiggle")
    REQUIRED_EXECUTABLES = ["bam2wig.py"]
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#bam2wig-py"
    CITATION_DOIS = ["10.1093/bioinformatics/bts356"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/bts356"]
    CITATION_TEXT = "RSeQC: quality control of RNA-seq experiments."
    VERSION = "5.0.3"

    @classmethod
    def _strand_rule(cls, inputs: dict[str, Any]) -> str:
        strand_specific = str(inputs.get("strand_specific", "none"))
        if strand_specific == "pair":
            return {
                "sd": "1++,1--,2+-,2-+",
                "ds": "1+-,1-+,2++,2--",
            }.get(str(inputs.get("pair_type", "sd")), "1++,1--,2+-,2-+")
        if strand_specific == "single":
            return {
                "s": "++,--",
                "d": "+-,-+",
            }.get(str(inputs.get("single_type", "s")), "++,--")
        return ""

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = [
            "bam2wig.py",
            "-i",
            str(inputs.get("input", "")),
            "-s",
            str(inputs.get("chromsize", "")),
            "-o",
            f"{out}/outfile",
        ]
        strand_rule = cls._strand_rule(inputs)
        if strand_rule:
            cmd.extend(["-d", strand_rule])
        if inputs.get("normalize"):
            cmd.extend(["-t", str(inputs.get("totalwig", ""))])
        if inputs.get("skip_multi_hits"):
            cmd.append("--skip-multi-hits")
            cmd.extend(["--mapq", str(inputs.get("mapq", 30))])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        if str(inputs.get("strand_specific", "none")) == "none":
            return [out / "outfile.wig"]
        return [out / "outfile.Forward.wig", out / "outfile.Reverse.wig"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "Sorted and indexed BAM alignment file"}),
                "chromsize": (
                    "FILE",
                    {"description": "Chromosome size file with chromosome name and size columns"},
                ),
            },
            "optional": {
                "strand_specific": (
                    "STRING",
                    {"default": "none", "options": ["none", "pair", "single"], "description": "Strand-specific library type"},
                ),
                "pair_type": ("STRING", {"default": "sd", "options": ["sd", "ds"], "description": "Paired-end strand rule"}),
                "single_type": ("STRING", {"default": "s", "options": ["s", "d"], "description": "Single-end strand rule"}),
                "normalize": ("BOOLEAN", {"default": False, "description": "Normalize wiggle coverage to a specified total wigsum"}),
                "totalwig": ("INT", {"default": 1000000000, "min": 1, "description": "Target wigsum used when normalization is enabled"}),
                "skip_multi_hits": ("BOOLEAN", {"default": False, "description": "Skip multiple-hit reads and use only uniquely mapped reads"}),
                "mapq": ("INT", {"default": 30, "min": 0, "max": 255, "description": "Minimum mapping quality when skipping multiple-hit reads"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class RSeQCClippingProfileNode(CommandNode):
    """Estimate clipped-base profiles across RNA-seq reads."""

    NODE_ID = "rseqc_clipping_profile"
    DISPLAY_NAME = "RSeQC Clipping Profile"
    REQUIRED_CONDA_PACKAGES = ["rseqc"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Calculate the distribution of soft-clipped nucleotides across RNA-seq reads from BAM alignments."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "rseqc",
        "clipping_profile",
        "clipping profile",
        "soft clipping",
        "CIGAR",
        "RNA-seq read clipping",
        "rna-seq qc",
    ]
    RETURN_TYPES = ("IMAGE", "TSV", "TEXT")
    RETURN_NAMES = ("clipping_profile_plot", "clipping_profile", "r_script")
    REQUIRED_EXECUTABLES = ["clipping_profile.py"]
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#clipping-profile-py"
    CITATION_DOIS = ["10.1093/bioinformatics/bts356"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/bts356"]
    CITATION_TEXT = "RSeQC: quality control of RNA-seq experiments."
    VERSION = "5.0.3"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        return [
            "clipping_profile.py",
            "-i",
            str(inputs.get("input", "")),
            "-o",
            f"{out}/output",
            "-q",
            str(inputs.get("mapq", 30)),
            "-s",
            str(inputs.get("layout", "SE")),
        ]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [
            out / "output.clipping_profile.pdf",
            out / "output.clipping_profile.xls",
        ]
        if inputs.get("rscript_output"):
            outputs.append(out / "output.clipping_profile.r")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "BAM alignment file with CIGAR strings that can include soft clipping"}),
            },
            "optional": {
                "mapq": (
                    "INT",
                    {
                        "default": 30,
                        "min": 0,
                        "max": 255,
                        "description": "Minimum mapping quality for an alignment to be considered uniquely mapped",
                    },
                ),
                "layout": (
                    "STRING",
                    {"default": "SE", "options": ["SE", "PE"], "description": "Sequencing layout: single-end or paired-end"},
                ),
                "rscript_output": (
                    "BOOLEAN",
                    {"default": False, "description": "Expose the R script used to generate the clipping profile plot"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class RSeQCDeletionProfileNode(CommandNode):
    """Estimate deleted-base profiles across RNA-seq reads."""

    NODE_ID = "rseqc_deletion_profile"
    DISPLAY_NAME = "RSeQC Deletion Profile"
    REQUIRED_CONDA_PACKAGES = ["rseqc"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Calculate the distribution of deleted nucleotides across RNA-seq reads from BAM alignments."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "rseqc",
        "deletion_profile",
        "deletion profile",
        "deleted nucleotides",
        "read deletions",
        "CIGAR",
        "rna-seq qc",
    ]
    RETURN_TYPES = ("IMAGE", "TSV", "TEXT")
    RETURN_NAMES = ("deletion_profile_plot", "deletion_profile", "r_script")
    REQUIRED_EXECUTABLES = ["deletion_profile.py"]
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#deletion-profile-py"
    CITATION_DOIS = ["10.1093/bioinformatics/bts356"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/bts356"]
    CITATION_TEXT = "RSeQC: quality control of RNA-seq experiments."
    VERSION = "5.0.3"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        return [
            "deletion_profile.py",
            "-i",
            str(inputs.get("input", "")),
            "-o",
            f"{out}/output",
            "-l",
            str(inputs.get("read_align_length", "")),
            "-n",
            str(inputs.get("read_num", 1000000)),
            "-q",
            str(inputs.get("mapq", 30)),
        ]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [
            out / "output.deletion_profile.pdf",
            out / "output.deletion_profile.txt",
        ]
        if inputs.get("rscript_output"):
            outputs.append(out / "output.deletion_profile.r")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "BAM alignment file"}),
                "read_align_length": (
                    "INT",
                    {
                        "min": 1,
                        "description": "Alignment length of reads; for example 101 for a 101M read alignment",
                    },
                ),
            },
            "optional": {
                "read_num": (
                    "INT",
                    {
                        "default": 1000000,
                        "min": 1,
                        "description": "Number of aligned reads with deletions used to calculate the profile",
                    },
                ),
                "mapq": ("INT", {"default": 30, "min": 0, "max": 255, "description": "Minimum mapping quality"}),
                "rscript_output": (
                    "BOOLEAN",
                    {"default": False, "description": "Expose the R script used to generate the deletion profile plot"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class RSeQCGeneBodyCoverageNode(CommandNode):
    """Assess RNA-seq coverage uniformity across scaled gene bodies."""

    NODE_ID = "rseqc_gene_body_coverage"
    DISPLAY_NAME = "RSeQC Gene Body Coverage"
    REQUIRED_CONDA_PACKAGES = ["rseqc"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Calculate read coverage across scaled gene bodies to reveal RNA-seq 5 prime or 3 prime coverage bias."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "rseqc",
        "geneBody_coverage",
        "gene body coverage",
        "coverage uniformity",
        "5 prime bias",
        "3 prime bias",
        "rna-seq qc",
    ]
    RETURN_TYPES = ("IMAGE", "IMAGE", "TSV", "TEXT")
    RETURN_NAMES = ("coverage_curves", "coverage_heatmap", "coverage_table", "r_script")
    REQUIRED_EXECUTABLES = ["geneBody_coverage.py"]
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#genebody-coverage-py"
    CITATION_DOIS = ["10.1093/bioinformatics/bts356"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/bts356"]
    CITATION_TEXT = "RSeQC: quality control of RNA-seq experiments."
    VERSION = "5.0.3"
    SHELL = True

    @classmethod
    def _bam_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("input", inputs.get("inputs")))

    @classmethod
    def _linked_bam_names(cls, bam_files: list[str]) -> list[str]:
        names: list[str] = []
        seen: dict[str, int] = {}
        for bam_file in bam_files:
            name = _safe_name(bam_file)
            if not name.endswith(".bam"):
                name = f"{name}.bam"
            count = seen.get(name, 0)
            seen[name] = count + 1
            if count:
                stem = name[:-4] if name.endswith(".bam") else name
                name = f"{stem}.{count + 1}.bam"
            names.append(name)
        return names

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        bam_files = cls._bam_files(inputs)
        if len(bam_files) <= 1:
            input_arg = bam_files[0] if bam_files else ""
            return [
                "geneBody_coverage.py",
                "-i",
                input_arg,
                "-r",
                str(inputs.get("refgene", "")),
                "--minimum_length",
                str(inputs.get("minimum_length", 100)),
                "-o",
                f"{out}/output",
            ]

        input_dir = f"{out}/input_bams"
        input_list = f"{out}/input_list.txt"
        linked_names = cls._linked_bam_names(bam_files)
        linked_paths = [f"{input_dir}/{linked_name}" for linked_name in linked_names]
        cmd = ["mkdir", "-p", input_dir]
        for source, linked_path in zip(bam_files, linked_paths, strict=True):
            cmd.extend(["&&", "ln", "-sf", source, linked_path])
        cmd.extend(["&&", "printf", "%s\\n"])
        cmd.extend(linked_paths)
        cmd.extend(
            [
                ">",
                input_list,
                "&&",
                "geneBody_coverage.py",
                "-i",
                input_list,
                "-r",
                str(inputs.get("refgene", "")),
                "--minimum_length",
                str(inputs.get("minimum_length", 100)),
                "-o",
                f"{out}/output",
            ]
        )
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [
            out / "output.geneBodyCoverage.curves.pdf",
        ]
        if len(cls._bam_files(inputs)) >= 3:
            outputs.append(out / "output.geneBodyCoverage.heatMap.pdf")
        outputs.append(out / "output.geneBodyCoverage.txt")
        if inputs.get("rscript_output"):
            outputs.append(out / "output.geneBodyCoverage.r")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (
                    "BAM",
                    {
                        "multiple": True,
                        "description": "Sorted and indexed BAM alignment file or multiple BAM files to merge into one coverage plot",
                    },
                ),
                "refgene": ("BED", {"description": "Reference gene model in BED12 format"}),
            },
            "optional": {
                "minimum_length": (
                    "INT",
                    {
                        "default": 100,
                        "min": 100,
                        "description": "Minimum mRNA length in bp; transcripts shorter than this are skipped",
                    },
                ),
                "rscript_output": (
                    "BOOLEAN",
                    {"default": False, "description": "Expose the R script used to generate the gene body coverage plots"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class RSeQCGeneBodyCoverage2Node(CommandNode):
    """Assess RNA-seq gene body coverage from BigWig signal."""

    NODE_ID = "rseqc_gene_body_coverage2"
    DISPLAY_NAME = "RSeQC Gene Body Coverage BigWig"
    REQUIRED_CONDA_PACKAGES = ["rseqc"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Calculate read coverage across scaled gene bodies from a BigWig signal file with lower memory use."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "rseqc",
        "geneBody_coverage2",
        "gene body coverage bigwig",
        "BigWig coverage",
        "coverage uniformity",
        "5 prime bias",
        "3 prime bias",
        "rna-seq qc",
    ]
    RETURN_TYPES = ("IMAGE", "TSV", "TEXT")
    RETURN_NAMES = ("coverage_plot", "coverage_table", "r_script")
    REQUIRED_EXECUTABLES = ["geneBody_coverage2.py"]
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#genebody-coverage2-py"
    CITATION_DOIS = ["10.1093/bioinformatics/bts356"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/bts356"]
    CITATION_TEXT = "RSeQC: quality control of RNA-seq experiments."
    VERSION = "5.0.3"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        return [
            "geneBody_coverage2.py",
            "-i",
            str(inputs.get("input", "")),
            "-r",
            str(inputs.get("refgene", "")),
            "-o",
            f"{out}/output",
        ]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [
            out / "output.geneBodyCoverage.pdf",
            out / "output.geneBodyCoverage.txt",
        ]
        if inputs.get("rscript_output"):
            outputs.append(out / "output.geneBodyCoverage_plot.r")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BIGWIG", {"description": "Coverage signal file in BigWig format"}),
                "refgene": ("BED", {"description": "Reference gene model in BED12 format"}),
            },
            "optional": {
                "rscript_output": (
                    "BOOLEAN",
                    {"default": False, "description": "Expose the R script used to generate the gene body coverage plot"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class RSeQCInnerDistanceNode(CommandNode):
    """Estimate inner distance or insert size for paired RNA-seq reads."""

    NODE_ID = "rseqc_inner_distance"
    DISPLAY_NAME = "RSeQC Inner Distance"
    REQUIRED_CONDA_PACKAGES = ["rseqc"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Calculate the mRNA inner distance between paired RNA-seq reads and summarize the insert-size distribution."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "rseqc",
        "inner_distance",
        "inner distance",
        "insert size",
        "paired reads",
        "fragment distance",
        "rna-seq qc",
    ]
    RETURN_TYPES = ("IMAGE", "TSV", "TSV", "TEXT")
    RETURN_NAMES = ("inner_distance_plot", "inner_distances", "inner_distance_frequency", "r_script")
    REQUIRED_EXECUTABLES = ["inner_distance.py"]
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#inner-distance-py"
    CITATION_DOIS = ["10.1093/bioinformatics/bts356"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/bts356"]
    CITATION_TEXT = "RSeQC: quality control of RNA-seq experiments."
    VERSION = "5.0.3"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        return [
            "inner_distance.py",
            "-i",
            str(inputs.get("input", "")),
            "-o",
            f"{out}/output",
            "-r",
            str(inputs.get("refgene", "")),
            "--sample-size",
            str(inputs.get("sample_size", 200000)),
            "--lower-bound",
            str(inputs.get("lower_bound", -250)),
            "--upper-bound",
            str(inputs.get("upper_bound", 250)),
            "--step",
            str(inputs.get("step", 5)),
            "--mapq",
            str(inputs.get("mapq", 30)),
        ]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [
            out / "output.inner_distance_plot.pdf",
            out / "output.inner_distance.txt",
            out / "output.inner_distance_freq.txt",
        ]
        if inputs.get("rscript_output"):
            outputs.append(out / "output.inner_distance_plot.r")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "BAM or SAM paired-end alignment file"}),
                "refgene": ("BED", {"description": "Reference gene model in BED12 format"}),
            },
            "optional": {
                "sample_size": (
                    "INT",
                    {"default": 200000, "min": 1, "description": "Number of read pairs sampled to estimate inner distance"},
                ),
                "lower_bound": (
                    "INT",
                    {"default": -250, "description": "Lower bound in bp for plotting the inner-distance histogram"},
                ),
                "upper_bound": (
                    "INT",
                    {"default": 250, "description": "Upper bound in bp for plotting the inner-distance histogram"},
                ),
                "step": ("INT", {"default": 5, "min": 1, "description": "Step size in bp for histogram bins"}),
                "mapq": ("INT", {"default": 30, "min": 0, "max": 255, "description": "Minimum mapping quality"}),
                "rscript_output": (
                    "BOOLEAN",
                    {"default": False, "description": "Expose the R script used to generate the inner-distance histogram"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class RSeQCInsertionProfileNode(CommandNode):
    """Estimate inserted-base profiles across RNA-seq reads."""

    NODE_ID = "rseqc_insertion_profile"
    DISPLAY_NAME = "RSeQC Insertion Profile"
    REQUIRED_CONDA_PACKAGES = ["rseqc"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Calculate the distribution of inserted nucleotides across RNA-seq reads from BAM alignments."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "rseqc",
        "insertion_profile",
        "insertion profile",
        "inserted nucleotides",
        "read insertions",
        "CIGAR",
        "rna-seq qc",
    ]
    RETURN_TYPES = ("IMAGE", "TSV", "TEXT")
    RETURN_NAMES = ("insertion_profile_plot", "insertion_profile", "r_script")
    REQUIRED_EXECUTABLES = ["insertion_profile.py"]
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#insertion-profile-py"
    CITATION_DOIS = ["10.1093/bioinformatics/bts356"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/bts356"]
    CITATION_TEXT = "RSeQC: quality control of RNA-seq experiments."
    VERSION = "5.0.3"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        return [
            "insertion_profile.py",
            "-i",
            str(inputs.get("input", "")),
            "-o",
            f"{out}/output",
            "-q",
            str(inputs.get("mapq", 30)),
            "-s",
            str(inputs.get("layout", "SE")),
        ]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [
            out / "output.insertion_profile.pdf",
            out / "output.insertion_profile.xls",
        ]
        if inputs.get("rscript_output"):
            outputs.append(out / "output.insertion_profile.r")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "BAM or SAM alignment file with CIGAR strings that can include insertions"}),
            },
            "optional": {
                "mapq": (
                    "INT",
                    {
                        "default": 30,
                        "min": 0,
                        "max": 255,
                        "description": "Minimum mapping quality for an alignment to be considered uniquely mapped",
                    },
                ),
                "layout": (
                    "STRING",
                    {"default": "SE", "options": ["SE", "PE"], "description": "Sequencing layout: single-end or paired-end"},
                ),
                "rscript_output": (
                    "BOOLEAN",
                    {"default": False, "description": "Expose the R script used to generate the insertion profile plot"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class RSeQCReadHexamerNode(CommandNode):
    """Calculate read and reference hexamer frequencies."""

    NODE_ID = "rseqc_read_hexamer"
    DISPLAY_NAME = "RSeQC Read Hexamer"
    REQUIRED_CONDA_PACKAGES = ["rseqc"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Calculate hexamer or 6-mer frequencies for read FASTA/FASTQ files and optional reference genome or mRNA sequences."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "rseqc",
        "read_hexamer",
        "read hexamer",
        "hexamer frequency",
        "6mer frequency",
        "kmer bias",
        "nucleotide composition",
        "rna-seq qc",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("hexamer_frequencies",)
    REQUIRED_EXECUTABLES = ["read_hexamer.py"]
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#read-hexamer-py"
    CITATION_DOIS = ["10.1093/bioinformatics/bts356"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/bts356"]
    CITATION_TEXT = "RSeQC: quality control of RNA-seq experiments."
    VERSION = "5.0.3"
    SHELL = True

    @classmethod
    def _safe_input_names(cls, paths: list[str]) -> list[str]:
        names: list[str] = []
        seen: set[str] = set()
        for index, path in enumerate(paths):
            name = sub(r"[^\w\-_]", "_", Path(path).name)
            if name in seen:
                name = f"{name}.{index}"
            seen.add(name)
            names.append(name)
        return names

    @classmethod
    def _stage_input(cls, source: str, target: str) -> str:
        quoted_source = shlex.quote(source)
        quoted_target = shlex.quote(target)
        if source.endswith((".gz", ".gzip")):
            return f"gunzip -c {quoted_source} > {quoted_target}"
        return f"ln -sf {quoted_source} {quoted_target}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        input_paths = _as_list(inputs.get("inputs", inputs.get("input")))
        input_names = cls._safe_input_names(input_paths)
        setup = [cls._stage_input(path, name) for path, name in zip(input_paths, input_names, strict=False)]
        cmd = ["read_hexamer.py", "-i", ",".join(input_names)]
        refgenome = str(inputs.get("refgenome", "") or "")
        if refgenome:
            cmd.extend(["-r", refgenome])
        refgene = str(inputs.get("refgene", "") or "")
        if refgene:
            cmd.extend(["-g", refgene])
        cmd.extend([">", f"{_out(inputs)}/read_hexamer.tsv"])
        parts = setup + [_shell_join(cmd)]
        return " && ".join(parts)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "read_hexamer.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputs": (
                    "FASTQ",
                    {
                        "multiple": True,
                        "description": "Read sequence files in FASTA or FASTQ format; gzipped FASTQ/FASTA inputs are decompressed before analysis",
                    },
                ),
            },
            "optional": {
                "refgenome": ("FASTA", {"description": "Optional reference genome FASTA for genome hexamer frequencies"}),
                "refgene": ("FASTA", {"description": "Optional reference mRNA FASTA for transcript hexamer frequencies"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class RSeQCReadQualityNode(CommandNode):
    """Calculate Phred base quality distributions for aligned reads."""

    NODE_ID = "rseqc_read_quality"
    DISPLAY_NAME = "RSeQC Read Quality"
    REQUIRED_CONDA_PACKAGES = ["rseqc", "r-base"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Calculate Phred base quality score distributions for BAM or SAM alignments and generate quality heatmap and boxplot reports."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "rseqc",
        "read_quality",
        "read quality",
        "Phred quality",
        "base quality",
        "quality heatmap",
        "quality boxplot",
        "rna-seq qc",
    ]
    RETURN_TYPES = ("IMAGE", "IMAGE", "TEXT")
    RETURN_NAMES = ("quality_heatmap", "quality_boxplot", "r_script")
    REQUIRED_EXECUTABLES = ["read_quality.py"]
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#read-quality-py"
    CITATION_DOIS = ["10.1093/bioinformatics/bts356"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/bts356"]
    CITATION_TEXT = "RSeQC: quality control of RNA-seq experiments."
    VERSION = "5.0.3"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        return [
            "read_quality.py",
            "--input-file",
            str(inputs.get("input", "")),
            "--out-prefix",
            f"{out}/output",
            "-r",
            str(inputs.get("reduce", 1000)),
            "--mapq",
            str(inputs.get("mapq", 30)),
        ]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [
            out / "output.qual.heatmap.pdf",
            out / "output.qual.boxplot.pdf",
        ]
        if inputs.get("rscript_output"):
            outputs.append(out / "output.qual.r")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "BAM or SAM alignment file"}),
            },
            "optional": {
                "reduce": (
                    "INT",
                    {
                        "default": 1000,
                        "min": 1,
                        "description": "Ignore Phred-score bins represented fewer than this many times in the boxplot to reduce memory use",
                    },
                ),
                "mapq": ("INT", {"default": 30, "min": 0, "max": 255, "description": "Minimum mapping quality"}),
                "rscript_output": (
                    "BOOLEAN",
                    {"default": False, "description": "Expose the R script used to generate the quality plots"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class RSeQCRNAFragmentSizeNode(CommandNode):
    """Estimate RNA-seq fragment sizes for each transcript."""

    NODE_ID = "rseqc_rna_fragment_size"
    DISPLAY_NAME = "RSeQC RNA Fragment Size"
    REQUIRED_CONDA_PACKAGES = ["rseqc"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Estimate mean, median, and standard deviation of RNA-seq fragment sizes for each gene or transcript."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "rseqc",
        "RNA_fragment_size",
        "rna fragment size",
        "insert size",
        "fragment length",
        "rna-seq qc",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("fragment_sizes",)
    REQUIRED_EXECUTABLES = ["RNA_fragment_size.py"]
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#rna-fragment-size-py"
    CITATION_DOIS = ["10.1093/bioinformatics/bts356"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/bts356"]
    CITATION_TEXT = "RSeQC: quality control of RNA-seq experiments."
    VERSION = "5.0.3"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "RNA_fragment_size.py",
            "-i",
            str(inputs.get("input", "")),
            "--refgene",
            str(inputs.get("refgene", "")),
            "--mapq",
            str(inputs.get("mapq", 30)),
            "--frag-num",
            str(inputs.get("frag_num", 3)),
        ]
        _add_shell_redirect(cmd, f"{_out(inputs)}/fragment_sizes.tsv")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "fragment_sizes.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "BAM alignment file"}),
                "refgene": ("BED", {"description": "Reference gene model in BED12 format"}),
            },
            "optional": {
                "mapq": ("INT", {"default": 30, "min": 0, "max": 255, "description": "Minimum mapping quality"}),
                "frag_num": (
                    "INT",
                    {"default": 3, "min": 1, "description": "Minimum number of fragments required to report a transcript"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class RSeQCJunctionAnnotationNode(CommandNode):
    """Compare detected splice junctions with a BED12 gene model."""

    NODE_ID = "rseqc_junction_annotation"
    DISPLAY_NAME = "RSeQC Junction Annotation"
    REQUIRED_CONDA_PACKAGES = ["rseqc", "r-base"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Classify detected splice junctions as annotated, complete novel, or partial novel against a BED12 gene model."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "rseqc",
        "junction_annotation",
        "splice junction annotation",
        "splice events",
        "novel junctions",
        "rna-seq qc",
    ]
    RETURN_TYPES = ("IMAGE", "IMAGE", "TSV", "TEXT", "STATS_FILE")
    RETURN_NAMES = ("splice_events_plot", "splice_junction_plot", "junctions", "r_script", "stats")
    REQUIRED_EXECUTABLES = ["junction_annotation.py"]
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#junction-annotation-py"
    CITATION_DOIS = ["10.1093/bioinformatics/bts356"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/bts356"]
    CITATION_TEXT = "RSeQC: quality control of RNA-seq experiments."
    VERSION = "5.0.3"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        return [
            "junction_annotation.py",
            "--input-file",
            str(inputs.get("input", "")),
            "--refgene",
            str(inputs.get("refgene", "")),
            "--out-prefix",
            f"{out}/output",
            "--min-intron",
            str(inputs.get("min_intron", 50)),
            "--mapq",
            str(inputs.get("mapq", 30)),
            "2>",
            f"{out}/stats.txt",
        ]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [
            out / "output.splice_events.pdf",
            out / "output.splice_junction.pdf",
            out / "output.junction.xls",
        ]
        if inputs.get("rscript_output"):
            outputs.append(out / "output.junction_plot.r")
        outputs.append(out / "stats.txt")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "BAM or SAM alignment file"}),
                "refgene": ("BED", {"description": "Reference gene model in BED12 format"}),
            },
            "optional": {
                "min_intron": ("INT", {"default": 50, "min": 1, "description": "Minimum intron length in base pairs"}),
                "mapq": ("INT", {"default": 30, "min": 0, "max": 255, "description": "Minimum mapping quality"}),
                "rscript_output": ("BOOLEAN", {"default": False, "description": "Expose the R script used to generate junction plots"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class RSeQCJunctionSaturationNode(CommandNode):
    """Assess whether splice-junction discovery is saturated by sequencing depth."""

    NODE_ID = "rseqc_junction_saturation"
    DISPLAY_NAME = "RSeQC Junction Saturation"
    REQUIRED_CONDA_PACKAGES = ["rseqc"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Resample alignments to evaluate saturation of known and novel splice-junction detection."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "rseqc",
        "junction_saturation",
        "splice junction saturation",
        "alternative splicing",
        "sequencing depth",
        "rna-seq qc",
    ]
    RETURN_TYPES = ("IMAGE", "TEXT")
    RETURN_NAMES = ("junction_saturation_plot", "r_script")
    REQUIRED_EXECUTABLES = ["junction_saturation.py"]
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#junction-saturation-py"
    CITATION_DOIS = ["10.1093/bioinformatics/bts356"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/bts356"]
    CITATION_TEXT = "RSeQC: quality control of RNA-seq experiments."
    VERSION = "5.0.3"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = [
            "junction_saturation.py",
            "--input-file",
            str(inputs.get("input", "")),
            "--refgene",
            str(inputs.get("refgene", "")),
            "--out-prefix",
            f"{out}/output",
            "--min-intron",
            str(inputs.get("min_intron", 50)),
            "--min-coverage",
            str(inputs.get("min_coverage", 1)),
            "--mapq",
            str(inputs.get("mapq", 30)),
        ]
        if inputs.get("percentiles_mode") == "specify":
            cmd.extend(
                [
                    "--percentile-floor",
                    str(inputs.get("percentile_floor", 5)),
                    "--percentile-ceiling",
                    str(inputs.get("percentile_ceiling", 100)),
                    "--percentile-step",
                    str(inputs.get("percentile_step", 5)),
                ]
            )
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "output.junctionSaturation_plot.pdf"]
        if inputs.get("rscript_output"):
            outputs.append(out / "output.junctionSaturation_plot.r")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "BAM or SAM alignment file"}),
                "refgene": ("BED", {"description": "Reference gene model in BED12 format"}),
            },
            "optional": {
                "min_intron": ("INT", {"default": 50, "min": 1, "description": "Minimum intron length in base pairs"}),
                "min_coverage": (
                    "INT",
                    {"default": 1, "min": 1, "description": "Minimum number of supporting reads required to call a junction"},
                ),
                "mapq": ("INT", {"default": 30, "min": 0, "max": 255, "description": "Minimum mapping quality"}),
                "percentiles_mode": (
                    "STRING",
                    {
                        "default": "default",
                        "options": ["default", "specify"],
                        "description": "Use default sampling percentiles or specify sampling bounds and step",
                    },
                ),
                "percentile_floor": ("INT", {"default": 5, "min": 0, "max": 100, "description": "Lower sampling percentile"}),
                "percentile_ceiling": ("INT", {"default": 100, "min": 0, "max": 100, "description": "Upper sampling percentile"}),
                "percentile_step": ("INT", {"default": 5, "min": 1, "max": 100, "description": "Sampling percentile increment"}),
                "rscript_output": ("BOOLEAN", {"default": False, "description": "Expose the R script used to generate the saturation plot"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class RSeQCMismatchProfileNode(CommandNode):
    """Calculate mismatch distribution across read positions."""

    NODE_ID = "rseqc_mismatch_profile"
    DISPLAY_NAME = "RSeQC Mismatch Profile"
    REQUIRED_CONDA_PACKAGES = ["rseqc"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Calculate the distribution of mismatches across read positions for BAM alignments with MD tags."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "rseqc",
        "mismatch_profile",
        "mismatch profile",
        "MD tag",
        "read mismatches",
        "rna-seq qc",
    ]
    RETURN_TYPES = ("IMAGE", "TSV", "TEXT")
    RETURN_NAMES = ("mismatch_profile_plot", "mismatch_profile", "r_script")
    REQUIRED_EXECUTABLES = ["mismatch_profile.py"]
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#mismatch-profile-py"
    CITATION_DOIS = ["10.1093/bioinformatics/bts356"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/bts356"]
    CITATION_TEXT = "RSeQC: quality control of RNA-seq experiments."
    VERSION = "5.0.3"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        return [
            "mismatch_profile.py",
            "-i",
            str(inputs.get("input", "")),
            "-o",
            f"{out}/output",
            "-l",
            str(inputs.get("read_align_length", "")),
            "-n",
            str(inputs.get("read_num", 1000000)),
            "-q",
            str(inputs.get("mapq", 30)),
        ]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [
            out / "output.mismatch_profile.pdf",
            out / "output.mismatch_profile.xls",
        ]
        if inputs.get("rscript_output"):
            outputs.append(out / "output.mismatch_profile.r")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "BAM alignment file containing MD tags"}),
                "read_align_length": (
                    "INT",
                    {
                        "min": 1,
                        "description": "Alignment length of reads; for example 101 for a 101M read alignment",
                    },
                ),
            },
            "optional": {
                "read_num": (
                    "INT",
                    {
                        "default": 1000000,
                        "min": 1,
                        "description": "Number of aligned reads with mismatches used to calculate the profile",
                    },
                ),
                "mapq": ("INT", {"default": 30, "min": 0, "max": 255, "description": "Minimum mapping quality"}),
                "rscript_output": (
                    "BOOLEAN",
                    {"default": False, "description": "Expose the R script used to generate the mismatch profile plot"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class RSeQCReadGCNode(CommandNode):
    """Calculate GC content distribution of aligned reads."""

    NODE_ID = "rseqc_read_gc"
    DISPLAY_NAME = "RSeQC Read GC"
    REQUIRED_CONDA_PACKAGES = ["rseqc"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Calculate GC content distribution for reads in BAM or SAM alignments."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "rseqc",
        "read_GC",
        "read GC",
        "GC content",
        "GC bias",
        "rna-seq qc",
    ]
    RETURN_TYPES = ("IMAGE", "TSV", "TEXT")
    RETURN_NAMES = ("gc_plot", "gc_counts", "r_script")
    REQUIRED_EXECUTABLES = ["read_GC.py"]
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#read-gc-py"
    CITATION_DOIS = ["10.1093/bioinformatics/bts356"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/bts356"]
    CITATION_TEXT = "RSeQC: quality control of RNA-seq experiments."
    VERSION = "5.0.3"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        return [
            "read_GC.py",
            "--input-file",
            str(inputs.get("input", "")),
            "--out-prefix",
            f"{out}/output",
            "--mapq",
            str(inputs.get("mapq", 30)),
        ]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [
            out / "output.GC_plot.pdf",
            out / "output.GC.xls",
        ]
        if inputs.get("rscript_output"):
            outputs.append(out / "output.GC_plot.r")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "BAM or SAM alignment file"}),
            },
            "optional": {
                "mapq": (
                    "INT",
                    {
                        "default": 30,
                        "min": 0,
                        "max": 255,
                        "description": "Minimum mapping quality for an alignment to be called uniquely mapped",
                    },
                ),
                "rscript_output": (
                    "BOOLEAN",
                    {"default": False, "description": "Expose the R script used to generate the GC plot"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class RSeQCReadNVCNode(CommandNode):
    """Check nucleotide composition bias across read cycles."""

    NODE_ID = "rseqc_read_nvc"
    DISPLAY_NAME = "RSeQC Read NVC"
    REQUIRED_CONDA_PACKAGES = ["rseqc"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Calculate nucleotide-versus-cycle composition to inspect nucleotide composition bias across aligned reads."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "rseqc",
        "read_NVC",
        "read NVC",
        "nucleotide composition",
        "nucleotide versus cycle",
        "random priming bias",
        "rna-seq qc",
    ]
    RETURN_TYPES = ("IMAGE", "TSV", "TEXT")
    RETURN_NAMES = ("nvc_plot", "nvc_table", "r_script")
    REQUIRED_EXECUTABLES = ["read_NVC.py"]
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#read-nvc-py"
    CITATION_DOIS = ["10.1093/bioinformatics/bts356"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/bts356"]
    CITATION_TEXT = "RSeQC: quality control of RNA-seq experiments."
    VERSION = "5.0.3"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = [
            "read_NVC.py",
            "--input-file",
            str(inputs.get("input", "")),
            "--out-prefix",
            f"{out}/output",
        ]
        if inputs.get("nx"):
            cmd.append("--nx")
        cmd.extend(["--mapq", str(inputs.get("mapq", 30))])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [
            out / "output.NVC_plot.pdf",
            out / "output.NVC.xls",
        ]
        if inputs.get("rscript_output"):
            outputs.append(out / "output.NVC_plot.r")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "BAM or SAM alignment file with fixed read length"}),
            },
            "optional": {
                "nx": (
                    "BOOLEAN",
                    {"default": False, "description": "Include N and X alongside A, T, C, and G in the NVC plot"},
                ),
                "mapq": (
                    "INT",
                    {
                        "default": 30,
                        "min": 0,
                        "max": 255,
                        "description": "Minimum mapping quality for an alignment to be called uniquely mapped",
                    },
                ),
                "rscript_output": (
                    "BOOLEAN",
                    {"default": False, "description": "Expose the R script used to generate the NVC plot"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class RSeQCBamStatNode(CommandNode):
    """Summarize BAM or SAM mapping statistics with RSeQC."""

    NODE_ID = "rseqc_bam_stat"
    DISPLAY_NAME = "RSeQC BAM Stat"
    REQUIRED_CONDA_PACKAGES = ["rseqc"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Calculate mapped-read summary statistics from a BAM or SAM alignment file."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "rseqc", "bam_stat", "bam stats", "mapping statistics", "rna-seq qc", "sam stats"]
    RETURN_TYPES = ("STATS_FILE",)
    RETURN_NAMES = ("mapping_stats",)
    REQUIRED_EXECUTABLES = ["bam_stat.py"]
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#bam-stat-py"
    CITATION_DOIS = ["10.1093/bioinformatics/bts356"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/bts356"]
    CITATION_TEXT = "RSeQC: quality control of RNA-seq experiments."
    VERSION = "5.0.3"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "bam_stat.py",
            "-i",
            str(inputs.get("input", "")),
            "-q",
            str(inputs.get("mapq", 30)),
        ]
        _add_shell_redirect(cmd, f"{_out(inputs)}/bam_stat.txt")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "bam_stat.txt"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "BAM or SAM alignment file"}),
            },
            "optional": {
                "mapq": ("INT", {"default": 30, "min": 0, "max": 255, "description": "Minimum mapping quality for uniquely mapped reads"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class RSeQCReadDistributionNode(CommandNode):
    """Calculate mapped-read distribution across gene-model features."""

    NODE_ID = "rseqc_read_distribution"
    DISPLAY_NAME = "RSeQC Read Distribution"
    REQUIRED_CONDA_PACKAGES = ["rseqc"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Calculate how mapped reads are distributed across genomic features from a BED12 gene model."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "rseqc", "read_distribution", "read distribution", "mapped reads", "genome features", "rna-seq qc"]
    RETURN_TYPES = ("STATS_FILE",)
    RETURN_NAMES = ("read_distribution",)
    REQUIRED_EXECUTABLES = ["read_distribution.py"]
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#read-distribution-py"
    CITATION_DOIS = ["10.1093/bioinformatics/bts356"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/bts356"]
    CITATION_TEXT = "RSeQC: quality control of RNA-seq experiments."
    VERSION = "5.0.3"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "read_distribution.py",
            "-i",
            str(inputs.get("input", "")),
            "-r",
            str(inputs.get("refgene", "")),
        ]
        _add_shell_redirect(cmd, f"{_out(inputs)}/read_distribution.txt")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "read_distribution.txt"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "BAM or SAM alignment file"}),
                "refgene": ("BED", {"description": "Reference gene model in BED12 format"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class RSeQCReadDuplicationNode(CommandNode):
    """Estimate read duplication rates with sequence and mapping strategies."""

    NODE_ID = "rseqc_read_duplication"
    DISPLAY_NAME = "RSeQC Read Duplication"
    REQUIRED_CONDA_PACKAGES = ["rseqc"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Determine read duplication rates from mapped read positions and read sequences."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "rseqc", "read_duplication", "read duplication", "duplication rate", "PCR bias", "rna-seq qc"]
    RETURN_TYPES = ("IMAGE", "TSV", "TSV", "TEXT")
    RETURN_NAMES = ("duplication_plot", "position_duplication", "sequence_duplication", "r_script")
    REQUIRED_EXECUTABLES = ["read_duplication.py"]
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#read-duplication-py"
    CITATION_DOIS = ["10.1093/bioinformatics/bts356"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/bts356"]
    CITATION_TEXT = "RSeQC: quality control of RNA-seq experiments."
    VERSION = "5.0.3"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        return [
            "read_duplication.py",
            "-i",
            str(inputs.get("input", "")),
            "-o",
            f"{out}/output",
            "-u",
            str(inputs.get("up_limit", 500)),
            "-q",
            str(inputs.get("mapq", 30)),
        ]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [
            out / "output.DupRate_plot.pdf",
            out / "output.pos.DupRate.xls",
            out / "output.seq.DupRate.xls",
        ]
        if inputs.get("rscript_output"):
            outputs.append(out / "output.DupRate_plot.r")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "BAM or SAM alignment file"}),
            },
            "optional": {
                "up_limit": ("INT", {"default": 500, "min": 1, "description": "Upper limit of duplicated times used for plotting"}),
                "mapq": ("INT", {"default": 30, "min": 0, "max": 255, "description": "Minimum mapping quality for uniquely mapped reads"}),
                "rscript_output": ("BOOLEAN", {"default": False, "description": "Expose the R script used to generate the duplication plot"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class RSeQCTINNode(CommandNode):
    """Evaluate RNA integrity at transcript and sample level with TIN."""

    NODE_ID = "rseqc_tin"
    DISPLAY_NAME = "RSeQC Transcript Integrity Number"
    REQUIRED_CONDA_PACKAGES = ["rseqc"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Calculate transcript integrity number scores from sorted and indexed BAM alignments against a BED12 gene model."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "rseqc",
        "tin",
        "tin.py",
        "Transcript Integrity Number",
        "transcript integrity",
        "RNA integrity",
        "RNA degradation",
        "medTIN",
        "rna-seq qc",
    ]
    RETURN_TYPES = ("TSV", "TSV")
    RETURN_NAMES = ("tin_summary", "tin_table")
    REQUIRED_EXECUTABLES = ["tin.py"]
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#tin-py"
    CITATION_DOIS = ["10.1186/s12859-016-0922-z", "10.1093/bioinformatics/bts356"]
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in CITATION_DOIS]
    CITATION_TEXT = "Measure transcript integrity using RNA-seq data; RSeQC: quality control of RNA-seq experiments."
    VERSION = "5.0.3"
    SHELL = True

    @classmethod
    def _bam_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("input", inputs.get("inputs")))

    @classmethod
    def _linked_bam_names(cls, bam_files: list[str]) -> list[str]:
        names: list[str] = []
        seen: dict[str, int] = {}
        for bam_file in bam_files:
            name = _safe_name(bam_file)
            if not name.endswith(".bam"):
                name = f"{name}.bam"
            count = seen.get(name, 0)
            seen[name] = count + 1
            if count:
                stem = name[:-4] if name.endswith(".bam") else name
                name = f"{stem}.{count + 1}.bam"
            names.append(name)
        return names

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_dir = f"{out}/input_bams"
        input_list = f"{out}/input_list.txt"
        bam_files = cls._bam_files(inputs)
        linked_paths = [
            f"{input_dir}/{linked_name}"
            for linked_name in cls._linked_bam_names(bam_files)
        ]

        parts = [f"mkdir -p {shlex.quote(input_dir)}"]
        for source, linked_path in zip(bam_files, linked_paths, strict=True):
            parts.append(f"ln -sf {shlex.quote(source)} {shlex.quote(linked_path)}")

        printf_cmd = ["printf", "%s\\n", *linked_paths, ">", input_list]
        parts.append(_shell_join(printf_cmd))
        tin_cmd = [
            "tin.py",
            "-i",
            input_list,
            "--refgene",
            str(inputs.get("refgene", "")),
            "--minCov",
            str(inputs.get("minCov", inputs.get("min_cov", 10))),
            "--sample-size",
            str(inputs.get("samplesize", inputs.get("sample_size", 100))),
        ]
        if inputs.get("subtractbackground", inputs.get("subtract_background")):
            tin_cmd.append("--subtract-background")
        parts.append(_shell_join(tin_cmd))
        parts.append(f"mv *summary.txt {shlex.quote(f'{out}/summary.tab')}")
        parts.append(f"mv *tin.xls {shlex.quote(f'{out}/tin.xls')}")
        return " && ".join(parts)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [
            out / "summary.tab",
            out / "tin.xls",
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (
                    "BAM",
                    {
                        "multiple": True,
                        "description": "Sorted and indexed BAM alignment file or files used to calculate transcript integrity",
                    },
                ),
                "refgene": ("BED", {"description": "Reference gene model in BED12 format"}),
            },
            "optional": {
                "minCov": (
                    "INT",
                    {
                        "default": 10,
                        "min": 1,
                        "description": "Minimum number of reads mapped to a transcript",
                    },
                ),
                "samplesize": (
                    "INT",
                    {
                        "default": 100,
                        "min": 1,
                        "description": "Number of equal-spaced nucleotide positions sampled from each mRNA",
                    },
                ),
                "subtractbackground": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Subtract background noise estimated from intronic reads",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
