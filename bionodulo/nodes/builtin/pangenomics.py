"""Pangenomics workflow nodes."""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from bionodulo.nodes.command_node import CommandNode


def _split_path_list(value: Any) -> list[str]:
    if isinstance(value, list | tuple):
        return [str(item) for item in value if str(item)]
    return [item for item in re.split(r"[\s,]+", str(value or "")) if item]


def _safe_output_stem(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        text = fallback
    stem = Path(text).stem
    stem = re.sub(r"\.(gz|bz2|xz|zip)$", "", stem)
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._-")
    return stem or fallback


class VGConstructNode(CommandNode):
    """Construct variation graphs from a reference FASTA and VCF."""
    NODE_ID = "vg_construct"
    DISPLAY_NAME = "vg Construct"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Construct a variation graph from reference FASTA and VCF variants. Foundation for pangenome alignment."
    SEARCH_ALIASES = ["vg", "construct", "variation graph", "pangenome", "graph genome"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("vg_graph",)
    REQUIRED_EXECUTABLES = ["vg"]
    REQUIRED_CONDA_PACKAGES = ["vg"]
    DOCUMENTATION_URL = "https://github.com/vgteam/vg"
    VERSION = "1.62.0"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        vcf = str(inputs.get("vcf", ""))
        cmd = [
            "vg",
            "construct",
            "-r",
            str(inputs.get("reference", "")),
            "-a",
            "-f",
            "-S",
        ]
        if vcf:
            cmd.extend(["-v" if vcf.endswith(".gz") else "-V", vcf])
        if inputs.get("region"):
            cmd.extend(["-R", str(inputs["region"])])
        if inputs.get("max_node_size"):
            cmd.extend(["-m", str(inputs["max_node_size"])])
        if inputs.get("progress"):
            cmd.append("-p")
        cmd.extend([">", f"{out_dir}/vg_graph.vg"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "vg_graph.vg"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reference": ("FASTA", {"description": "Reference FASTA"}),
                "vcf": ("VCF_GZ", {"description": "VCF with variants to embed"}),
            },
            "optional": {
                "region": ("STRING", {"default": "", "description": "Region (e.g., chr1:1-1000000)"}),
                "max_node_size": ("INT", {"default": 32, "min": 1}),
                "progress": ("BOOLEAN", {"default": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class VGIndexNode(CommandNode):
    """Build vg autoindex artifacts for graph read mapping."""

    NODE_ID = "vg_index"
    DISPLAY_NAME = "vg Autoindex"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Build vg autoindex files for Giraffe graph read mapping and downstream graph calling."
    SEARCH_ALIASES = ["vg", "autoindex", "giraffe", "gbz", "minimizer", "distance index", "pangenome index"]
    RETURN_TYPES = ("FILE", "FILE", "FILE", "FILE", "FILE")
    RETURN_NAMES = ("gbz_index", "minimizer_index", "zipcode_index", "distance_index", "xg_index")
    REQUIRED_EXECUTABLES = ["vg"]
    REQUIRED_CONDA_PACKAGES = ["vg"]
    DOCUMENTATION_URL = "https://github.com/vgteam/vg/wiki/Automatic-indexing-for-read-mapping-and-downstream-inference"
    VERSION = "1.62.0"
    SHELL = True

    _WORKFLOWS = {"giraffe"}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        workflow = str(inputs.get("workflow", "giraffe") or "giraffe")
        if workflow not in cls._WORKFLOWS:
            return f"Unsupported vg Autoindex workflow: {workflow}"
        if int(inputs.get("threads", 8) or 0) <= 0:
            return "vg Autoindex threads must be greater than zero."
        return True

    @classmethod
    def _prefix(cls, inputs: dict[str, Any], output_dir: str | Path) -> Path:
        node_out = Path(output_dir)
        fallback_stem = _safe_output_stem(inputs.get("graph_gfa"), "graph")
        stem = _safe_output_stem(inputs.get("output_prefix"), fallback_stem)
        return node_out / stem

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = Path(str(inputs.get("output", ".")))
        prefix = cls._prefix(inputs, out_dir)
        workflow = str(inputs.get("workflow", "giraffe") or "giraffe")
        gbz_index = f"{prefix}.giraffe.gbz"
        xg_index = f"{prefix}.xg"

        cmd = [
            "vg",
            "autoindex",
            "--workflow",
            workflow,
            "--gfa",
            str(inputs.get("graph_gfa", "")),
        ]
        if inputs.get("reference"):
            cmd.extend(["--ref-fasta", str(inputs["reference"])])
        cmd.extend([
            "--prefix",
            str(prefix),
            "--threads",
            str(inputs.get("threads", 8)),
        ])
        if inputs.get("tmp_dir"):
            cmd.extend(["--tmp-dir", str(inputs["tmp_dir"])])
        if inputs.get("target_mem"):
            cmd.extend(["--target-mem", str(inputs["target_mem"])])
        cmd.extend([
            "&&",
            "vg",
            "convert",
            "-x",
            "--drop-haplotypes",
            gbz_index,
            ">",
            xg_index,
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        prefix = cls._prefix(inputs, node_out)
        return [
            Path(f"{prefix}.giraffe.gbz"),
            Path(f"{prefix}.shortread.withzip.min"),
            Path(f"{prefix}.shortread.zipcodes"),
            Path(f"{prefix}.dist"),
            Path(f"{prefix}.xg"),
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "graph_gfa": ("GFA", {"description": "Input pangenome graph in GFA format"}),
            },
            "optional": {
                "workflow": ("STRING", {"default": "giraffe", "options": ["giraffe"]}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 128, "display": "slider"}),
                "output_prefix": ("STRING", {"default": "", "description": "Optional output filename stem"}),
                "reference": ("FASTA", {"description": "Reference FASTA for named reference paths"}),
                "tmp_dir": ("STRING", {"default": "", "description": "Optional temporary directory for vg autoindex"}),
                "target_mem": ("STRING", {"default": "", "description": "Optional target memory limit, for example 64G"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class VGMapNode(CommandNode):
    """Map reads to variation graphs with vg map or giraffe."""
    NODE_ID = "vg_map"
    DISPLAY_NAME = "vg Map/Giraffe"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Map reads to a variation graph using vg map or vg giraffe. Produces GAM alignments."
    SEARCH_ALIASES = ["vg", "map", "giraffe", "pangenome align", "graph alignment", "gam"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("gam_alignment",)
    REQUIRED_EXECUTABLES = ["vg"]
    REQUIRED_CONDA_PACKAGES = ["vg"]
    DOCUMENTATION_URL = "https://github.com/vgteam/vg"
    VERSION = "1.62.0"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get("output", ".")))
        mapper = inputs.get("mapper", "giraffe")
        reads = str(inputs.get("reads", ""))
        reads2 = str(inputs.get("reads2", ""))
        threads = str(inputs.get("threads", 8))

        if mapper == "giraffe":
            cmd = [
                "vg",
                "giraffe",
                "-Z",
                str(inputs.get("gbz_index", "")),
                "-m",
                str(inputs.get("minimizer_index", "")),
                "-z",
                str(inputs.get("zipcode_index", "")),
                "-d",
                str(inputs.get("distance_index", "")),
                "-f",
                reads,
                "-p",
                "-t",
                threads,
            ]
            if reads2:
                cmd.extend(["-f", reads2])
        else:
            cmd = [
                "vg",
                "map",
                "-x",
                str(inputs.get("xg_index", "")),
                "-g",
                str(inputs.get("gcsa_index", "")),
                "-f",
                reads,
                "-t",
                threads,
                "-p",
            ]
            if reads2:
                cmd.extend(["-f", reads2])
            if inputs.get("min_identity"):
                cmd.extend(["--min-ident", str(inputs["min_identity"])])
        cmd.extend([">", str(out_dir / "gam_alignment.gam")])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "gam_alignment.gam"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ", {"description": "Forward/single-end FASTQ"}),
                "mapper": ("STRING", {"default": "giraffe", "options": ["giraffe", "map"]}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "reads2": ("FASTQ", {"description": "Reverse FASTQ (paired)"}),
                "gbz_index": ("FILE", {"description": "Giraffe GBZ index"}),
                "minimizer_index": ("FILE", {"description": "Minimizer index"}),
                "zipcode_index": ("FILE", {"description": "Zipcodes index"}),
                "distance_index": ("FILE", {"description": "Distance index"}),
                "xg_index": ("FILE", {"description": "XG index (for vg map)"}),
                "gcsa_index": ("FILE", {"description": "GCSA index (for vg map)"}),
                "min_identity": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.05}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class VGCallNode(CommandNode):
    """Call variants from graph alignments with vg."""
    NODE_ID = "vg_call"
    DISPLAY_NAME = "vg Call Variants"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Call variants from graph alignments (GAM) using vg pack + vg call. Produces VCF."
    SEARCH_ALIASES = ["vg", "call", "variant calling", "pangenome", "graph caller"]
    RETURN_TYPES = ("VCF",)
    RETURN_NAMES = ("calls_vcf",)
    REQUIRED_EXECUTABLES = ["vg"]
    REQUIRED_CONDA_PACKAGES = ["vg"]
    DOCUMENTATION_URL = "https://github.com/vgteam/vg"
    VERSION = "1.62.0"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get("output", ".")))
        pack = out_dir / "aln.pack"
        calls_vcf = out_dir / "calls_vcf.vcf"
        graph = str(inputs.get("xg_graph", ""))
        threads = str(inputs.get("threads", 4))

        cmd = [
            "vg",
            "pack",
            "-x",
            graph,
            "-g",
            str(inputs.get("gam", "")),
            "-o",
            str(pack),
            "-t",
            threads,
            "&&",
            "vg",
            "call",
            graph,
            "-k",
            str(pack),
            "-t",
            threads,
            "-v",
        ]
        if inputs.get("ref_path"):
            cmd.extend(["-p", str(inputs["ref_path"])])
        if inputs.get("sample"):
            cmd.extend(["-s", str(inputs["sample"])])
        cmd.extend([">", str(calls_vcf)])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "calls_vcf.vcf"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "xg_graph": ("FILE", {"description": "Input XG graph index"}),
                "gam": ("FILE", {"description": "Graph alignments in GAM format"}),
                "threads": ("INT", {"default": 4, "min": 1}),
            },
            "optional": {
                "ref_path": ("STRING", {"default": "", "description": "Reference path for VCF coordinates"}),
                "sample": ("STRING", {"default": "", "description": "Sample name for genotype calls"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class VCFDecomposeNode(CommandNode):
    """Decompose complex pangenome VCF records into primitive alleles."""

    NODE_ID = "vcf_decompose"
    DISPLAY_NAME = "VCF Decompose"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Decompose complex variants in a pangenome VCF into primitive, normalized records."
    SEARCH_ALIASES = ["vcf", "decompose", "pangenome vcf", "primitive variants", "vcflib", "normalize"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("decomposed_vcf",)
    REQUIRED_EXECUTABLES = ["vcfdecompose", "bgzip", "tabix"]
    REQUIRED_CONDA_PACKAGES = ["vcflib", "htslib"]
    DOCUMENTATION_URL = "https://github.com/vcflib/vcflib"
    VERSION = "1.0.9"
    SHELL = True

    _MODES = {"decompose", "normalize"}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        mode = str(inputs.get("mode", "normalize") or "normalize")
        if mode not in cls._MODES:
            return f"Unsupported VCF decompose mode: {mode}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = Path(str(inputs.get("output", ".")))
        output_vcf = out_dir / "decomposed_vcf.vcf.gz"
        mode = str(inputs.get("mode", "normalize") or "normalize")
        threads = int(inputs.get("threads", 0) or 0)

        cmd = ["vcfdecompose"]
        if inputs.get("keep_info"):
            cmd.append("-k")
        cmd.append(str(inputs.get("vcf", "")))

        if mode == "normalize":
            cmd.extend([
                "|",
                "vcfallelicprimitives",
            ])
            if inputs.get("keep_info"):
                cmd.append("-kg")
            if inputs.get("reference"):
                cmd.extend(["-t", "DECOMPOSED", "-f", str(inputs.get("reference", ""))])

        cmd.extend(["|", "bgzip"])
        if threads > 0:
            cmd.extend(["--threads", str(threads)])
        cmd.extend([
            "-c",
            ">",
            str(output_vcf),
            "&&",
            "tabix",
            "-f",
            "-p",
            "vcf",
            str(output_vcf),
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "decomposed_vcf.vcf.gz"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": ("VCF_GZ", {"description": "Input pangenome or complex-variant VCF"}),
                "reference": ("FASTA", {"description": "Reference FASTA for primitive allele normalization"}),
            },
            "optional": {
                "mode": ("STRING", {"default": "normalize", "options": ["decompose", "normalize"]}),
                "keep_info": ("BOOLEAN", {"default": True, "description": "Preserve INFO fields where possible"}),
                "threads": ("INT", {"default": 0, "min": 0, "max": 64, "display": "slider"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class PangenomeSVNode(CommandNode):
    """Call structural variants from a pangenome graph against a reference path."""

    NODE_ID = "pangenome_sv"
    DISPLAY_NAME = "Pangenome SV"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Call structural variants from a pangenome graph against a reference and emit an indexed VCF."
    SEARCH_ALIASES = ["pangenome", "structural variants", "sv", "graph vcf", "pangenome graph", "vg deconstruct"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("sv_vcf",)
    REQUIRED_EXECUTABLES = ["vg", "bcftools", "bgzip", "tabix"]
    REQUIRED_CONDA_PACKAGES = ["vg", "bcftools", "htslib"]
    DOCUMENTATION_URL = "https://github.com/vgteam/vg"
    VERSION = "1.62.0"
    SHELL = True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if int(inputs.get("min_sv_length", 0) or 0) < 0:
            return "Minimum SV length must be non-negative"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = Path(str(inputs.get("output", ".")))
        prefix = out_dir / "graph"
        xg_index = out_dir / "graph.xg"
        output_vcf = out_dir / "sv_vcf.vcf.gz"
        threads = int(inputs.get("threads", 0) or 0)
        min_sv_length = int(inputs.get("min_sv_length", 0) or 0)
        sample_name = str(inputs.get("sample_name", "") or "")

        cmd: list[str] = []
        if sample_name:
            samples_file = out_dir / "samples.txt"
            cmd.extend(["printf", f"'{sample_name}\\n'", ">", str(samples_file), "&&"])

        cmd.extend([
            "vg",
            "autoindex",
            "--workflow",
            "giraffe",
            "--gfa",
            str(inputs.get("graph_gfa", "")),
            "--ref-fasta",
            str(inputs.get("reference", "")),
            "--prefix",
            str(prefix),
        ])
        if threads > 0:
            cmd.extend(["--threads", str(threads)])

        cmd.extend(["&&", "vg", "deconstruct", str(xg_index)])
        if inputs.get("ref_path"):
            cmd.extend(["-P", str(inputs["ref_path"])])
        cmd.extend(["-a", "-e"])
        if threads > 0:
            cmd.extend(["-t", str(threads)])

        if min_sv_length > 0:
            cmd.extend([
                "|",
                "bcftools",
                "view",
                "-i",
                f"ABS(ILEN)>={min_sv_length} || ABS(strlen(ALT)-strlen(REF))>={min_sv_length}",
            ])
        if sample_name:
            cmd.extend(["|", "bcftools", "reheader", "-s", str(out_dir / "samples.txt")])

        cmd.extend(["|", "bgzip"])
        if threads > 0:
            cmd.extend(["--threads", str(threads)])
        cmd.extend([
            "-c",
            ">",
            str(output_vcf),
            "&&",
            "tabix",
            "-f",
            "-p",
            "vcf",
            str(output_vcf),
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "sv_vcf.vcf.gz"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "graph_gfa": ("GFA", {"description": "Input pangenome graph in GFA format"}),
                "reference": ("FASTA", {"description": "Reference FASTA used to interpret graph paths"}),
            },
            "optional": {
                "sample_name": ("STRING", {"default": "", "description": "Optional sample name for the output VCF"}),
                "threads": ("INT", {"default": 8, "min": 0, "max": 64, "display": "slider"}),
                "ref_path": ("STRING", {"default": "", "description": "Reference path to deconstruct"}),
                "min_sv_length": ("INT", {"default": 50, "min": 0, "description": "Minimum variant length to keep"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class PangenomeStatsNode(CommandNode):
    """Compute pangenome growth statistics from graph and gene annotations."""

    NODE_ID = "pangenome_stats"
    DISPLAY_NAME = "Pangenome Stats"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Compute core, shell, and cloud pangenome statistics from annotated pangenome graphs."
    SEARCH_ALIASES = ["pangenome", "panacus", "core genes", "shell genes", "cloud genes", "rarefaction"]
    RETURN_TYPES = ("JSON", "FILE")
    RETURN_NAMES = ("stats", "rarefaction")
    REQUIRED_EXECUTABLES = ["panacus"]
    REQUIRED_CONDA_PACKAGES = ["panacus"]
    DOCUMENTATION_URL = "https://github.com/marschall-lab/panacus"
    VERSION = "0.3.3"
    SHELL = True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        core_threshold = float(inputs.get("core_threshold", 0.9) or 0.9)
        shell_threshold = float(inputs.get("shell_threshold", 0.1) or 0.1)
        if not 0 <= shell_threshold <= 1 or not 0 <= core_threshold <= 1:
            return "Pangenome thresholds must be between 0 and 1"
        if core_threshold <= shell_threshold:
            return "Core threshold must be greater than shell threshold"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = Path(str(inputs.get("output", ".")))
        rarefaction = out_dir / "rarefaction.tsv"
        stats = out_dir / "stats.json"
        threads = int(inputs.get("threads", 0) or 0)

        cmd = [
            "panacus",
            "histgrowth",
            str(inputs.get("graph", "")),
            "--gff",
            str(inputs.get("annotations", "")),
        ]
        if inputs.get("groupby"):
            cmd.extend(["--groupby", str(inputs["groupby"])])
        if threads > 0:
            cmd.extend(["--threads", str(threads)])
        if inputs.get("include_html"):
            cmd.extend(["--html", str(out_dir / "rarefaction.html")])

        cmd.extend([
            ">",
            str(rarefaction),
            "&&",
            "python",
            "-m",
            "bionodulo.nodes.scripts.pangenome_stats_summary",
            "--input",
            str(rarefaction),
            "--output",
            str(stats),
            "--core-threshold",
            str(float(inputs.get("core_threshold", 0.9) or 0.9)),
            "--shell-threshold",
            str(float(inputs.get("shell_threshold", 0.1) or 0.1)),
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "stats.json", node_out / "rarefaction.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "graph": ("GFA", {"description": "Input pangenome graph in GFA format"}),
                "annotations": ("GFF", {"description": "Gene annotations used for pangenome feature summaries"}),
            },
            "optional": {
                "core_threshold": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 1.0, "step": 0.01}),
                "shell_threshold": ("FLOAT", {"default": 0.1, "min": 0.0, "max": 1.0, "step": 0.01}),
                "groupby": ("FILE", {"description": "Optional Panacus group-by or path grouping file"}),
                "threads": ("INT", {"default": 4, "min": 0, "max": 64, "display": "slider"}),
                "include_html": ("BOOLEAN", {"default": False, "description": "Also request Panacus HTML output"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class PangenomeGeneNode(CommandNode):
    """Extract gene presence/absence matrices from pangenome annotations."""

    NODE_ID = "pangenome_gene"
    DISPLAY_NAME = "Pangenome Gene"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Extract gene presence/absence matrix and summary plot from pangenome annotations."
    SEARCH_ALIASES = ["pangenome", "panaroo", "presence absence", "orthologs", "gene clusters"]
    RETURN_TYPES = ("FILE", "IMAGE")
    RETURN_NAMES = ("presence_matrix", "pan_genome_plot")
    REQUIRED_EXECUTABLES = ["panaroo"]
    REQUIRED_CONDA_PACKAGES = ["panaroo"]
    DOCUMENTATION_URL = "https://github.com/gtonkinhill/panaroo"
    VERSION = "1.5.0"
    SHELL = True

    _CLEAN_MODES = {"strict", "moderate", "sensitive"}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if not _split_path_list(inputs.get("annotations")):
            return "At least one GFF annotation is required"
        clean_mode = str(inputs.get("clean_mode", "strict") or "strict")
        if clean_mode not in cls._CLEAN_MODES:
            return f"Unsupported Panaroo clean mode: {clean_mode}"
        core_threshold = float(inputs.get("core_threshold", 0) or 0)
        if not 0 <= core_threshold <= 1:
            return "Core threshold must be between 0 and 1"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = Path(str(inputs.get("output", ".")))
        presence_matrix = out_dir / "presence_matrix.tsv"
        pan_genome_plot = out_dir / "pan_genome_plot.svg"
        annotations = _split_path_list(inputs.get("annotations"))
        threads = int(inputs.get("threads", 0) or 0)
        core_threshold = float(inputs.get("core_threshold", 0) or 0)

        cmd = [
            "panaroo",
            "-i",
            *annotations,
            "-o",
            str(out_dir),
            "--clean-mode",
            str(inputs.get("clean_mode", "strict") or "strict"),
        ]
        if threads > 0:
            cmd.extend(["-t", str(threads)])
        if core_threshold > 0:
            cmd.extend(["--core_threshold", str(core_threshold)])
        if inputs.get("remove_invalid_genes"):
            cmd.append("--remove-invalid-genes")
        if inputs.get("merge_paralogs"):
            cmd.append("--merge_paralogs")

        cmd.extend([
            "&&",
            "cp",
            str(out_dir / "gene_presence_absence.Rtab"),
            str(presence_matrix),
            "&&",
            "cp",
            str(inputs.get("orthologs", "")),
            str(out_dir / "orthologs.tsv"),
            "&&",
            "python",
            "-m",
            "bionodulo.nodes.scripts.pangenome_gene_plot",
            "--input",
            str(presence_matrix),
            "--output",
            str(pan_genome_plot),
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "presence_matrix.tsv", node_out / "pan_genome_plot.svg"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "annotations": ("GFF", {"description": "GFF annotation files; pass a list or comma-separated paths"}),
                "orthologs": ("FILE", {"description": "Ortholog or gene cluster table to retain with outputs"}),
            },
            "optional": {
                "clean_mode": ("STRING", {"default": "strict", "options": ["strict", "moderate", "sensitive"]}),
                "threads": ("INT", {"default": 4, "min": 0, "max": 64, "display": "slider"}),
                "core_threshold": ("FLOAT", {"default": 0.95, "min": 0.0, "max": 1.0, "step": 0.01}),
                "remove_invalid_genes": ("BOOLEAN", {"default": True}),
                "merge_paralogs": ("BOOLEAN", {"default": False}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class MinigraphNode(CommandNode):
    """Construct or align pangenome graphs with minigraph."""
    NODE_ID = "minigraph"
    DISPLAY_NAME = "Minigraph"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Fast sequence-to-graph aligner and pangenome constructor for large genomes."
    SEARCH_ALIASES = ["minigraph", "graph align", "pangenome", "sv graph", "sequence to graph"]
    RETURN_TYPES = ("GFA",)
    RETURN_NAMES = ("output_gfa",)
    REQUIRED_EXECUTABLES = ["minigraph"]
    REQUIRED_CONDA_PACKAGES = ["minigraph"]
    DOCUMENTATION_URL = "https://github.com/lh3/minigraph"
    VERSION = "0.21"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get("output", ".")))
        mode = inputs.get("mode", "construct")
        threads = str(inputs.get("threads", 8))

        if mode == "construct":
            cmd = ["minigraph", "-cxggs", "-t", threads]
            if inputs.get("preset"):
                cmd.extend(["-x", str(inputs["preset"])])
            assemblies = inputs.get("assemblies", [])
            if isinstance(assemblies, list | tuple):
                cmd.extend(str(assembly) for assembly in assemblies if assembly)
            elif assemblies:
                cmd.append(str(assemblies))
        else:
            cmd = [
                "minigraph",
                "-cx",
                str(inputs.get("preset", "ggs")),
                "-t",
                threads,
                str(inputs.get("graph_gfa", "")),
                str(inputs.get("query_fasta", "")),
            ]
        cmd.extend([">", str(out_dir / "output_gfa.gfa")])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "output_gfa.gfa"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "mode": ("STRING", {"default": "construct", "options": ["construct", "align"]}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64}),
            },
            "optional": {
                "assemblies": ("FASTA", {"description": "Assemblies (first=reference)"}),
                "graph_gfa": ("GFA", {"description": "Graph GFA (for align mode)"}),
                "query_fasta": ("FASTA", {"description": "Query FASTA (for align mode)"}),
                "preset": ("STRING", {"default": "ggs", "options": ["ggs", "asm", "ggsa"]}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class PGGBNode(CommandNode):
    """Build reference-free pangenome graphs with PGGB."""
    NODE_ID = "pggb"
    DISPLAY_NAME = "PGGB Build"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Reference-free pangenome graph builder via all-vs-all WGA. Produces GFA, ODGI, VCF."
    SEARCH_ALIASES = ["pggb", "pangenome graph builder", "wga", "all-vs-all", "graph construction"]
    RETURN_TYPES = ("GFA", "FASTA")
    RETURN_NAMES = ("smooth_gfa", "consensus_fasta")
    REQUIRED_EXECUTABLES = ["pggb"]
    REQUIRED_CONDA_PACKAGES = ["pggb"]
    DOCUMENTATION_URL = "https://github.com/pangenome/pggb"
    VERSION = "0.7.3"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "pggb",
            "-i",
            str(inputs.get("input_fasta", "")),
            "-o",
            str(inputs.get("output", ".")),
            "-n",
            str(inputs.get("num_haplotypes", 2)),
            "-t",
            str(inputs.get("threads", 16)),
            "-p",
            str(inputs.get("map_pct_id", 90)),
            "-s",
            str(inputs.get("segment_length", 5000)),
            "-k",
            str(inputs.get("min_match_length", 19)),
            "-G",
            str(inputs.get("graph_poas", 2)),
        ]
        if inputs.get("do_viz"):
            cmd.append("--do-viz")
        if inputs.get("do_layout"):
            cmd.append("--do-layout")
        if inputs.get("consensus_spec"):
            cmd.extend(["-C", str(inputs["consensus_spec"])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "smooth_gfa.gfa", node_out / "consensus_fasta.fa"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fasta": ("FASTA", {"description": "Multi-sequence FASTA with all haplotypes"}),
                "num_haplotypes": ("INT", {"default": 2, "min": 2}),
                "threads": ("INT", {"default": 16, "min": 1, "max": 128}),
            },
            "optional": {
                "map_pct_id": ("INT", {"default": 90, "min": 50, "max": 100}),
                "segment_length": ("INT", {"default": 5000, "min": 1000}),
                "min_match_length": ("INT", {"default": 19, "min": 1}),
                "graph_poas": ("INT", {"default": 2, "min": 1, "max": 8}),
                "consensus_spec": ("STRING", {"default": "", "description": "Consensus spec (e.g., '100,1000,10000')"}),
                "do_viz": ("BOOLEAN", {"default": True}),
                "do_layout": ("BOOLEAN", {"default": False}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class PGGBBuildNode(CommandNode):
    """Construct pangenome graph outputs from multiple haplotype FASTA files."""

    NODE_ID = "pggb_build"
    DISPLAY_NAME = "PGGB Build"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Construct pangenome graph from multiple haplotypes using PGGB."
    SEARCH_ALIASES = ["pggb", "haplotypes", "pangenome graph", "graph construction", "odgi"]
    RETURN_TYPES = ("GFA", "ODGI")
    RETURN_NAMES = ("graph_gfa", "graph_odgi")
    REQUIRED_EXECUTABLES = ["pggb"]
    REQUIRED_CONDA_PACKAGES = ["pggb"]
    DOCUMENTATION_URL = "https://github.com/pangenome/pggb"
    VERSION = "0.7.3"
    SHELL = True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if len(_split_path_list(inputs.get("input_fasta"))) < 2:
            return "PGGB Build requires at least two haplotype FASTA files."
        if int(inputs.get("threads", 1) or 0) <= 0:
            return "PGGB Build threads must be greater than zero."
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = Path(str(inputs.get("output", ".")))
        haplotypes = out_dir / "haplotypes.fa"
        pggb_dir = out_dir / "pggb"
        graph_gfa = out_dir / "graph_gfa.gfa"
        graph_odgi = out_dir / "graph_odgi.odgi"
        fasta_paths = _split_path_list(inputs.get("input_fasta"))

        return [
            "cat",
            *fasta_paths,
            ">",
            str(haplotypes),
            "&&",
            "pggb",
            "-i",
            str(haplotypes),
            "-o",
            str(pggb_dir),
            "-n",
            str(len(fasta_paths)),
            "-t",
            str(inputs.get("threads", 16)),
            "-p",
            str(inputs.get("map_pct_id", 90)),
            "-s",
            str(inputs.get("segment_length", 5000)),
            "-k",
            str(inputs.get("min_match_length", 19)),
            "-G",
            str(inputs.get("graph_poas", 2)),
            "&&",
            "find",
            str(pggb_dir),
            "-name",
            "*.smooth.final.gfa",
            "-print",
            "-quit",
            "|",
            "xargs",
            "-r",
            "-I{}",
            "cp",
            "-f",
            "{}",
            str(graph_gfa),
            "&&",
            "find",
            str(pggb_dir),
            "-name",
            "*.smooth.final.og",
            "-print",
            "-quit",
            "|",
            "xargs",
            "-r",
            "-I{}",
            "cp",
            "-f",
            "{}",
            str(graph_odgi),
        ]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "graph_gfa.gfa", node_out / "graph_odgi.odgi"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fasta": ("FASTA", {"description": "List of haplotype FASTA files"}),
                "threads": ("INT", {"default": 16, "min": 1, "max": 128}),
            },
            "optional": {
                "map_pct_id": ("INT", {"default": 90, "min": 50, "max": 100}),
                "segment_length": ("INT", {"default": 5000, "min": 1000}),
                "min_match_length": ("INT", {"default": 19, "min": 1}),
                "graph_poas": ("INT", {"default": 2, "min": 1, "max": 8}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class ODGIBuildNode(CommandNode):
    """Build an ODGI graph from a GFA pangenome graph and export JSON stats."""

    NODE_ID = "odgi_build"
    DISPLAY_NAME = "odgi Build"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Build an ODGI pangenome graph from GFA input and summarize graph statistics."
    SEARCH_ALIASES = ["odgi", "odgi build", "gfa to odgi", "pangenome graph", "graph conversion", "stats"]
    RETURN_TYPES = ("ODGI", "JSON")
    RETURN_NAMES = ("graph_odgi", "stats")
    REQUIRED_EXECUTABLES = ["odgi"]
    REQUIRED_CONDA_PACKAGES = ["odgi"]
    DOCUMENTATION_URL = "https://odgi.readthedocs.io/"
    VERSION = "0.9.0"
    SHELL = True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if int(inputs.get("threads", 0) or 0) < 0:
            return "odgi Build threads must be zero or greater."
        return True

    @classmethod
    def _planned_paths(cls, inputs: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path]:
        node_out = Path(output_dir)
        fallback_stem = _safe_output_stem(inputs.get("gfa_graph"), "graph")
        stem = _safe_output_stem(inputs.get("output_name"), fallback_stem)
        return node_out / f"{stem}.odgi", node_out / f"{stem}.stats.json"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = Path(str(inputs.get("output", ".")))
        graph_odgi, stats = cls._planned_paths(inputs, out_dir)
        threads = int(inputs.get("threads", 0) or 0)

        cmd = [
            "odgi",
            "build",
            "-g",
            str(inputs.get("gfa_graph", "")),
            "-o",
            str(graph_odgi),
        ]
        if threads > 0:
            cmd.extend(["-t", str(threads)])
        if inputs.get("compact_ids"):
            cmd.append("-c")
        if inputs.get("validate"):
            cmd.append("-v")
        cmd.extend([
            "&&",
            "odgi",
            "stats",
            "-i",
            str(graph_odgi),
            "-j",
            ">",
            str(stats),
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return list(cls._planned_paths(inputs, node_out))

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "gfa_graph": ("GFA", {"description": "Input pangenome graph in GFA format"}),
            },
            "optional": {
                "threads": ("INT", {"default": 4, "min": 0, "max": 64, "display": "slider"}),
                "compact_ids": ("BOOLEAN", {"default": False, "description": "Compact node identifiers while building"}),
                "validate": ("BOOLEAN", {"default": False, "description": "Ask odgi build to validate input graph consistency"}),
                "output_name": ("STRING", {"default": "", "description": "Optional output filename stem"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class ODGIVisualizeNode(CommandNode):
    """Visualize pangenome graph layouts with odgi."""
    NODE_ID = "odgi_visualize"
    DISPLAY_NAME = "odgi Visualize"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Visualize pangenome graphs in 1D and 2D layout using odgi."
    SEARCH_ALIASES = ["odgi", "visualize", "pangenome", "graph viz", "graph layout"]
    RETURN_TYPES = ("IMAGE", "IMAGE")
    RETURN_NAMES = ("graph_1d", "graph_2d")
    REQUIRED_EXECUTABLES = ["odgi"]
    REQUIRED_CONDA_PACKAGES = ["odgi"]
    DOCUMENTATION_URL = "https://odgi.readthedocs.io/"
    VERSION = "0.9.0"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get("output", ".")))
        graph = out_dir / "graph.og"
        sorted_graph = out_dir / "sorted.og"
        graph_1d = out_dir / "graph_1d.png"
        graph_2d = out_dir / "graph_2d.png"

        cmd = [
            "odgi",
            "build",
            "-g",
            str(inputs.get("gfa_graph", "")),
            "-o",
            str(graph),
            "&&",
            "odgi",
            "viz",
            "-i",
            str(graph),
            "-o",
            str(graph_1d),
            "-x",
            str(inputs.get("width", 1200)),
            "-y",
            str(inputs.get("height", 200)),
        ]
        if inputs.get("show_path_names"):
            cmd.append("-p")
        cmd.extend([
            "&&",
            "odgi",
            "sort",
            "-i",
            str(graph),
            "-o",
            str(sorted_graph),
            "-Y",
            "&&",
            "odgi",
            "draw",
            "-i",
            str(sorted_graph),
            "-c",
            str(graph_2d),
            "-H",
            str(inputs.get("draw_height", 600)),
            "-C",
            str(inputs.get("draw_width", 1200)),
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "graph_1d.png", node_out / "graph_2d.png"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "gfa_graph": ("GFA", {"description": "Input pangenome graph in GFA format"}),
            },
            "optional": {
                "width": ("INT", {"default": 1200, "min": 100, "max": 10000}),
                "height": ("INT", {"default": 200, "min": 50, "max": 5000}),
                "draw_width": ("INT", {"default": 1200, "min": 100, "max": 10000}),
                "draw_height": ("INT", {"default": 600, "min": 50, "max": 5000}),
                "show_path_names": ("BOOLEAN", {"default": False}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class ODGIViewNode(CommandNode):
    """Visualize and inspect ODGI pangenome graphs."""

    NODE_ID = "odgi_view"
    DISPLAY_NAME = "ODGI View"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Visualize and extract information from ODGI pangenome graphs."
    SEARCH_ALIASES = ["odgi", "odgi stats", "pangenome graph", "graph view", "paths"]
    RETURN_TYPES = ("FILE", "JSON")
    RETURN_NAMES = ("view", "stats")
    REQUIRED_EXECUTABLES = ["odgi"]
    REQUIRED_CONDA_PACKAGES = ["odgi"]
    DOCUMENTATION_URL = "https://odgi.readthedocs.io/"
    VERSION = "0.9.0"
    SHELL = True

    _MODES = {"png", "paths"}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        mode = str(inputs.get("mode", "png") or "png")
        if mode not in cls._MODES:
            return f"Unsupported ODGI view mode: {mode}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = Path(str(inputs.get("output", ".")))
        graph = str(inputs.get("graph", ""))
        mode = str(inputs.get("mode", "png") or "png")
        view = out_dir / ("view.png" if mode == "png" else "view.txt")
        stats = out_dir / "stats.json"

        if mode == "png":
            cmd = [
                "odgi",
                "viz",
                "-i",
                graph,
                "-o",
                str(view),
            ]
            width = int(inputs.get("width", 0) or 0)
            height = int(inputs.get("height", 0) or 0)
            if width > 0:
                cmd.extend(["-x", str(width)])
            if height > 0:
                cmd.extend(["-y", str(height)])
            if inputs.get("show_path_names"):
                cmd.append("-p")
        else:
            cmd = [
                "odgi",
                "paths",
                "-i",
                graph,
                "-L",
                ">",
                str(view),
            ]

        cmd.extend([
            "&&",
            "odgi",
            "stats",
            "-i",
            graph,
            "-j",
            ">",
            str(stats),
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        mode = str(inputs.get("mode", "png") or "png")
        view_name = "view.png" if mode == "png" else "view.txt"
        return [node_out / view_name, node_out / "stats.json"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "graph": ("ODGI", {"description": "Input pangenome graph in ODGI format"}),
                "mode": ("STRING", {"default": "png", "options": ["png", "paths"]}),
            },
            "optional": {
                "width": ("INT", {"default": 1200, "min": 0, "max": 10000}),
                "height": ("INT", {"default": 200, "min": 0, "max": 5000}),
                "show_path_names": ("BOOLEAN", {"default": False}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
