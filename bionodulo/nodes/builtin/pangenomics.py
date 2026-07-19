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


class MinigraphCactusNode(CommandNode):
    """Build pangenome graphs from multiple assemblies with Minigraph-Cactus."""

    NODE_ID = "minigraph_cactus"
    DISPLAY_NAME = "Minigraph-Cactus"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Build pangenome graphs from assemblies using the Cactus Minigraph-Cactus pipeline."
    SEARCH_ALIASES = [
        "minigraph-cactus",
        "cactus-pangenome",
        "HPRC",
        "pangenome construction",
        "whole-genome alignment",
        "giraffe",
    ]
    RETURN_TYPES = ("GBZ", "VCF_GZ", "GFA", "ODGI")
    RETURN_NAMES = ("graph_gbz", "variants_vcf", "graph_gfa", "graph_odgi")
    REQUIRED_EXECUTABLES = ["cactus-pangenome"]
    REQUIRED_CONDA_PACKAGES = ["cactus"]
    DOCUMENTATION_URL = "https://github.com/ComparativeGenomicsToolkit/cactus/blob/master/doc/pangenome.md"
    VERSION = "2.9.0"

    _OUTPUT_FLAGS = ("gbz", "vcf", "gfa", "odgi")

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if int(inputs.get("threads", 1) or 0) <= 0:
            return "Minigraph-Cactus threads must be greater than zero."
        if not any(bool(inputs.get(flag, False)) for flag in cls._OUTPUT_FLAGS):
            return "Minigraph-Cactus requires at least one graph or variant output flag."
        return True

    @classmethod
    def _out_name(cls, inputs: dict[str, Any]) -> str:
        return _safe_output_stem(inputs.get("out_name"), "pangenome")

    @classmethod
    def _work_dir(cls, inputs: dict[str, Any], out_dir: Path) -> Path:
        if inputs.get("work_dir"):
            return Path(str(inputs["work_dir"]))
        return out_dir / "work"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = Path(str(inputs.get("output", ".")))
        work_dir = cls._work_dir(inputs, out_dir)
        max_cores = int(inputs.get("max_cores", 0) or 0)
        if max_cores <= 0:
            max_cores = int(inputs.get("threads", 1) or 1)

        cmd = [
            "cactus-pangenome",
            str(work_dir),
            str(inputs.get("seq_file", "")),
            "--outDir",
            str(out_dir),
            "--outName",
            cls._out_name(inputs),
            "--reference",
            str(inputs.get("reference", "")),
            "--maxCores",
            str(max_cores),
        ]

        cons_batch_size = int(inputs.get("cons_batch_size", 0) or 0)
        if cons_batch_size > 0:
            cmd.extend(["--batchSize", str(cons_batch_size)])

        for flag in ("gbz", "giraffe", "vcf", "gfa", "odgi", "viz"):
            if inputs.get(flag):
                cmd.append(f"--{flag}")
        if inputs.get("chrom_vg"):
            cmd.append("--chrom-vg")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        out_name = cls._out_name(inputs)
        return [
            node_out / f"{out_name}.gbz",
            node_out / f"{out_name}.vcf.gz",
            node_out / f"{out_name}.gfa.gz",
            node_out / f"{out_name}.og",
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "seq_file": ("FILE", {"description": "Cactus seqFile listing assembly names and FASTA paths"}),
                "reference": ("STRING", {"description": "Reference genome name from the seqFile"}),
            },
            "optional": {
                "out_name": ("STRING", {"default": "pangenome", "description": "Output filename prefix"}),
                "work_dir": ("STRING", {"default": "", "description": "Optional Cactus working directory"}),
                "threads": ("INT", {"default": 16, "min": 1, "max": 512, "display": "slider"}),
                "max_cores": ("INT", {"default": 0, "min": 0, "max": 512, "display": "slider"}),
                "cons_batch_size": ("INT", {"default": 0, "min": 0, "max": 100000}),
                "gbz": ("BOOLEAN", {"default": True}),
                "giraffe": ("BOOLEAN", {"default": True}),
                "vcf": ("BOOLEAN", {"default": True}),
                "gfa": ("BOOLEAN", {"default": True}),
                "odgi": ("BOOLEAN", {"default": False}),
                "viz": ("BOOLEAN", {"default": False}),
                "chrom_vg": ("BOOLEAN", {"default": False}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class CactusGalaxyNode(CommandNode):
    """Run the Galaxy Cactus whole-genome multiple alignment wrapper."""

    NODE_ID = "cactus_cactus"
    DISPLAY_NAME = "Cactus"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Whole-genome multiple sequence alignment with Progressive Cactus or Minigraph-Cactus."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "Cactus",
        "cactus_cactus",
        "Progressive Cactus",
        "Minigraph-Cactus",
        "whole-genome multiple alignment",
        "HAL alignment",
        "pangenome graph",
    ]
    RETURN_TYPES = ("FILE", "GFA")
    RETURN_NAMES = ("out_hal", "out_gfa")
    REQUIRED_EXECUTABLES = ["cactus", "cactus-pangenome"]
    REQUIRED_CONDA_PACKAGES = ["cactus"]
    DOCUMENTATION_URL = "https://github.com/ComparativeGenomicsToolkit/cactus"
    CITATION_DOIS = ["10.1038/s41586-020-2871-y"]
    CITATION_URLS = ["https://doi.org/10.1038/s41586-020-2871-y"]
    CITATION_TEXT = "Progressive Cactus is a multiple-genome aligner for the thousand-genome era."
    VERSION = "2.7.1+galaxy0"
    SHELL = True

    MODES = ["interspecies", "intraspecies"]

    @classmethod
    def _mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("aln_mode_select", "interspecies") or "interspecies")

    @classmethod
    def _labels(cls, inputs: dict[str, Any]) -> list[str]:
        value = inputs.get("labels", [])
        if isinstance(value, (list, tuple)):
            return [str(item) for item in value]
        return [item for item in re.split(r"[\s,]+", str(value or "")) if item]

    @classmethod
    def _seqs(cls, inputs: dict[str, Any]) -> list[str]:
        value = inputs.get("in_seqs", [])
        if isinstance(value, (list, tuple)):
            return [str(item) for item in value if str(item)]
        text = str(value or "")
        return [item for item in re.split(r"[\n,]+", text) if item.strip()]

    @classmethod
    def _positive_int(cls, inputs: dict[str, Any], key: str, default: int) -> int | str:
        value = inputs.get(key, default)
        if value in (None, ""):
            value = default
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if parsed <= 0:
            return f"{key} must be greater than zero"
        return parsed

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        seqs = cls._seqs(inputs)
        labels = cls._labels(inputs)
        if not seqs:
            return "at least one input genome FASTA is required"
        if len(labels) != len(seqs):
            return "labels must match in_seqs length"
        if any(not re.fullmatch(r"[0-9A-Za-z_]+", label) for label in labels):
            return "labels may contain only letters, digits, and underscores"
        mode = cls._mode(inputs)
        if mode not in cls.MODES:
            return f"aln_mode_select must be one of: {', '.join(cls.MODES)}"
        if mode == "interspecies" and not str(inputs.get("in_tree", "")).strip():
            return "in_tree is required for interspecies mode"
        if mode == "intraspecies":
            ref_level = str(inputs.get("ref_level", "")).strip()
            if not ref_level:
                return "ref_level is required for intraspecies mode"
            if ref_level not in labels:
                return "ref_level must match one of the labels"
        for key, default in (("max_cores", 4), ("max_memory_mb", 16384)):
            validation = cls._positive_int(inputs, key, default)
            if isinstance(validation, str):
                return validation
        return True

    @classmethod
    def _seq_filename(cls, label: str, fasta: str) -> str:
        suffixes = Path(fasta).suffixes
        if suffixes[-2:] == [".fa", ".gz"]:
            ext = "fa.gz"
        elif suffixes[-2:] == [".fasta", ".gz"]:
            ext = "fasta.gz"
        elif suffixes:
            ext = suffixes[-1].lstrip(".")
        else:
            ext = "fasta"
        return f"{label}.{ext}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = str(inputs.get("output", "."))
        seqfile = f"{out_dir}/seqfile.txt"
        mode = cls._mode(inputs)
        labels = cls._labels(inputs)
        seqs = cls._seqs(inputs)
        max_cores = cls._positive_int(inputs, "max_cores", 4)
        max_memory = cls._positive_int(inputs, "max_memory_mb", 16384)
        assert isinstance(max_cores, int)
        assert isinstance(max_memory, int)

        cmd = ["mkdir", "-p", out_dir, "&&"]
        if mode == "interspecies":
            cmd.extend(["cat", str(inputs.get("in_tree", "")), ">", seqfile, "&&"])
        else:
            cmd.extend(["rm", "-f", seqfile, "&&", "touch", seqfile, "&&"])

        for label, fasta in zip(labels, seqs):
            seq_name = cls._seq_filename(label, fasta)
            cmd.extend(
                [
                    "ln",
                    "-s",
                    fasta,
                    f"{out_dir}/{seq_name}",
                    "&&",
                    "printf",
                    "%s %s\n",
                    label,
                    seq_name,
                    ">>",
                    seqfile,
                    "&&",
                ]
            )

        cmd.extend(["cd", out_dir, "&&"])
        if mode == "intraspecies":
            cmd.extend(
                [
                    "cactus-pangenome",
                    "--reference",
                    str(inputs.get("ref_level", "")),
                    "--binariesMode",
                    "local",
                    "--maxCores",
                    str(max_cores),
                    "--maxMemory",
                    f"{max_memory}M",
                    "--outDir",
                    "./",
                    "--outName",
                    "alignment",
                    "jobStore",
                    "seqfile.txt",
                ]
            )
        else:
            cmd.extend(
                [
                    "cactus",
                    "--binariesMode",
                    "local",
                    "--maxCores",
                    str(max_cores),
                    "--maxMemory",
                    f"{max_memory}M",
                    "--workDir",
                    "./",
                    "jobStore",
                    "seqfile.txt",
                    "alignment.full.hal",
                ]
            )
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        outputs = [node_out / "alignment.full.hal"]
        if cls._mode(inputs) == "intraspecies":
            outputs.append(node_out / "alignment.gfa.gz")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_seqs": ("FASTA_LIST", {"multiple": True, "description": "Input genome FASTA or FASTA.GZ files"}),
                "labels": ("STRING_LIST", {"multiple": True, "description": "Genome labels matching the input FASTA order"}),
            },
            "optional": {
                "aln_mode_select": (
                    "STRING",
                    {
                        "default": "interspecies",
                        "options": cls.MODES,
                        "description": "Between-species Progressive Cactus or within-species Minigraph-Cactus mode",
                    },
                ),
                "in_tree": ("FILE", {"default": "", "description": "Guide tree in Newick/NHX format for interspecies mode"}),
                "ref_level": ("STRING", {"default": "", "description": "Reference genome label for intraspecies mode"}),
                "max_cores": ("INT", {"default": 4, "min": 1, "max": 512, "display": "slider"}),
                "max_memory_mb": ("INT", {"default": 16384, "min": 1, "display": "slider"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class CactusExportNode(CommandNode):
    """Export Cactus HAL alignments to Galaxy-supported downstream formats."""

    NODE_ID = "cactus_export"
    DISPLAY_NAME = "Cactus Export"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Convert Cactus HAL whole-genome alignments to MAF, VG, or UCSC Assembly Hub archives."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "Cactus Export",
        "cactus_export",
        "HAL export",
        "hal2maf",
        "hal2vg",
        "hal2assemblyHub",
        "MAF alignment",
        "UCSC Assembly Hub",
    ]
    RETURN_TYPES = ("MAF", "VG", "TAR")
    RETURN_NAMES = ("out_maf", "out_vg", "out_ah")
    REQUIRED_EXECUTABLES = ["hal2maf", "hal2vg", "hal2assemblyHub.py", "tar"]
    REQUIRED_CONDA_PACKAGES = ["cactus", "tar"]
    DOCUMENTATION_URL = "https://github.com/ComparativeGenomicsToolkit/cactus#using-the-output"
    CITATION_DOIS = ["10.1038/s41586-020-2871-y"]
    CITATION_URLS = ["https://doi.org/10.1038/s41586-020-2871-y"]
    CITATION_TEXT = "Progressive Cactus is a multiple-genome aligner for the thousand-genome era."
    VERSION = "2.7.1+galaxy0"
    SHELL = True

    FORMATS = ["maf_selector", "vg_selector", "ah_selector"]

    @classmethod
    def _format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("format", "maf_selector") or "maf_selector")

    @classmethod
    def _positive_int(cls, inputs: dict[str, Any], key: str, default: int) -> int | str:
        value = inputs.get(key, default)
        if value in (None, ""):
            value = default
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if parsed <= 0:
            return f"{key} must be greater than zero"
        return parsed

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("hal_file", "")).strip():
            return "hal_file is required"
        export_format = cls._format(inputs)
        if export_format not in cls.FORMATS:
            return f"format must be one of: {', '.join(cls.FORMATS)}"
        if export_format in {"maf_selector", "vg_selector"} and not str(inputs.get("ref_level", "")).strip():
            return "ref_level is required for MAF and VG export"
        for key, default in (("max_cores", 4), ("max_memory_mb", 8196)):
            validation = cls._positive_int(inputs, key, default)
            if isinstance(validation, str):
                return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = str(inputs.get("output", "."))
        export_format = cls._format(inputs)
        cmd = [
            "ln",
            "-s",
            str(inputs.get("hal_file", "")),
            f"{out_dir}/alignment.hal",
            "&&",
            "cd",
            out_dir,
            "&&",
        ]
        if export_format == "maf_selector":
            cmd.extend([
                "hal2maf",
                "--refGenome",
                str(inputs.get("ref_level", "")),
                "alignment.hal",
                "alignment.maf",
            ])
        elif export_format == "vg_selector":
            cmd.extend([
                "hal2vg",
                "alignment.hal",
                "--progress",
                ">",
                "alignment.pg",
            ])
        else:
            max_cores = cls._positive_int(inputs, "max_cores", 4)
            max_memory = cls._positive_int(inputs, "max_memory_mb", 8196)
            assert isinstance(max_cores, int)
            assert isinstance(max_memory, int)
            cmd.extend([
                "hal2assemblyHub.py",
                "--maxCores",
                str(max_cores),
                "--maxMemory",
                f"{max_memory}M",
                "./jobStore",
                "alignment.hal",
                "assemblyhub",
                "&&",
                "tar",
                "-cv",
                "assemblyhub",
                ">",
                "assemblyhub.tar",
            ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        export_format = cls._format(inputs)
        if export_format == "vg_selector":
            return [node_out / "alignment.pg"]
        if export_format == "ah_selector":
            return [node_out / "assemblyhub.tar"]
        return [node_out / "alignment.maf"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "hal_file": ("HAL", {"description": "HAL file generated by Cactus"}),
            },
            "optional": {
                "format": (
                    "STRING",
                    {
                        "default": "maf_selector",
                        "options": cls.FORMATS,
                        "description": "Export MAF, VG, or UCSC Assembly Hub format",
                    },
                ),
                "ref_level": ("STRING", {"default": "", "description": "Reference genome label for MAF and VG exports"}),
                "max_cores": ("INT", {"default": 4, "min": 1, "max": 512, "display": "slider"}),
                "max_memory_mb": ("INT", {"default": 8196, "min": 1, "display": "slider"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


# Stable ODGI and PGGB IDs are owned by focused source-pinned modules. These
# imports preserve the historical ``bionodulo.nodes.builtin.pangenomics`` path.
from bionodulo.nodes.builtin.pangenomics_family.odgi_build import (  # noqa: E402,F401
    ODGIBuildNode,
)
from bionodulo.nodes.builtin.pangenomics_family.odgi_stats import (  # noqa: E402,F401
    ODGIStatsNode,
)
from bionodulo.nodes.builtin.pangenomics_family.odgi_view import (  # noqa: E402,F401
    ODGIViewNode,
)
from bionodulo.nodes.builtin.pangenomics_family.odgi_visualize import (  # noqa: E402,F401
    ODGIVisualizeNode,
)
from bionodulo.nodes.builtin.pangenomics_family.odgi_viz import ODGIVizNode  # noqa: E402,F401
from bionodulo.nodes.builtin.pangenomics_family.pggb import PGGBNode  # noqa: E402,F401
from bionodulo.nodes.builtin.pangenomics_family.pggb_build import (  # noqa: E402,F401
    PGGBBuildNode,
)
