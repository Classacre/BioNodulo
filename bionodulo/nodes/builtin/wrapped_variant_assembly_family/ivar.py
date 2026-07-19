"""Focused ivar node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from .evidence import pin_contract

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

pin_contract(IVarConsensusNode)
pin_contract(IVarFilterVariantsNode)
pin_contract(IVarTrimNode)
pin_contract(IVarRemoveReadsNode)
pin_contract(IVarVariantsNode)

__all__ = ['IVarConsensusNode', 'IVarFilterVariantsNode', 'IVarTrimNode', 'IVarRemoveReadsNode', 'IVarVariantsNode']
