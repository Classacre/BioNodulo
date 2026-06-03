"""Pangenomics workflow nodes."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


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
