"""Focused gtdbtk node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin._variant_assembly_contracts import pin_contract

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

pin_contract(GTDBTkClassifyWFNode)

__all__ = ['GTDBTkClassifyWFNode']
