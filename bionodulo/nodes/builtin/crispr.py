"""CRISPR and genome-editing workflow nodes."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


class CRISPRESSONode(CommandNode):
    """Analyze CRISPR amplicon editing outcomes with CRISPResso2."""
    NODE_ID = "crispresso2"
    DISPLAY_NAME = "CRISPRESSO2"
    CATEGORY = "crispr"
    DESCRIPTION = "Analyze CRISPR editing from amplicon sequencing. Quantifies indels, frameshifts, allele-specific outcomes."
    SEARCH_ALIASES = ["crispresso", "crispresso2", "crispr", "amplicon", "indel", "editing analysis"]
    RETURN_TYPES = ("HTML_REPORT", "DIRECTORY")
    RETURN_NAMES = ("report", "results_dir")
    REQUIRED_EXECUTABLES = ["CRISPResso"]
    REQUIRED_CONDA_PACKAGES = ["crispresso2"]
    DOCUMENTATION_URL = "https://github.com/pinellolab/CRISPResso2"
    VERSION = "2.3.2"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        cmd = [
            "CRISPResso",
            "-r1",
            str(inputs.get("r1", "")),
            "-a",
            str(inputs.get("amplicon_seq", "")),
            "-o",
            str(out_dir),
            "--name",
            str(inputs.get("name", "crispresso_run")),
        ]
        if inputs.get("r2"):
            cmd.extend(["-r2", str(inputs["r2"])])
        if inputs.get("guide_seq"):
            cmd.extend(["-g", str(inputs["guide_seq"])])
        if inputs.get("quant_window_center"):
            cmd.extend(["-qc", str(inputs["quant_window_center"])])
        if inputs.get("quant_window_size"):
            cmd.extend(["-w", str(inputs["quant_window_size"])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        name = str(inputs.get("name", "crispresso_run"))
        run_name = f"CRISPResso_on_{name}"
        return [node_out / f"{run_name}.html", node_out / run_name]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "r1": ("FASTQ", {"description": "Forward FASTQ"}),
                "amplicon_seq": ("STRING", {"description": "Reference amplicon sequence"}),
                "name": ("STRING", {"default": "crispresso_run"}),
            },
            "optional": {
                "r2": ("FASTQ", {"description": "Reverse FASTQ (paired)"}),
                "guide_seq": ("STRING", {"default": "", "description": "gRNA sequence (20bp)"}),
                "quant_window_center": ("INT", {"default": -3, "min": -20, "max": 20}),
                "quant_window_size": ("INT", {"default": 1, "min": 0, "max": 100}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class MAGeCKCountNode(CommandNode):
    """Count sgRNA reads for pooled CRISPR screens with MAGeCK."""
    NODE_ID = "mageck_count"
    DISPLAY_NAME = "MAGeCK Count"
    CATEGORY = "crispr"
    DESCRIPTION = "Count sgRNA reads from FASTQ for pooled CRISPR screens. Normalizes and generates count tables."
    SEARCH_ALIASES = ["mageck", "count", "crispr screen", "sgrna", "pooled screen"]
    RETURN_TYPES = ("TSV", "TSV")
    RETURN_NAMES = ("count_table", "normalized_counts")
    REQUIRED_EXECUTABLES = ["mageck"]
    REQUIRED_CONDA_PACKAGES = ["mageck"]
    DOCUMENTATION_URL = "https://sourceforge.net/p/mageck/wiki/Home/"
    VERSION = "0.5.9"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        prefix = str(inputs.get("output_prefix", "mageck_count"))
        cmd = [
            "mageck",
            "count",
            "-l",
            str(inputs.get("library_file", "")),
            "-n",
            f"{out_dir}/{prefix}",
        ]
        fastq_files = inputs.get("fastq_files", [])
        if isinstance(fastq_files, str):
            fastq_files = [fastq_files] if fastq_files else []
        if fastq_files:
            cmd.append("--fastq")
            cmd.extend(str(fastq) for fastq in fastq_files)
        sample_labels = inputs.get("sample_labels", "")
        if isinstance(sample_labels, (list, tuple)):
            sample_labels = ",".join(str(label) for label in sample_labels)
        if sample_labels:
            cmd.extend(["--sample-label", str(sample_labels)])
        if inputs.get("day0_label"):
            cmd.extend(["--day0-label", str(inputs["day0_label"])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        prefix = str(inputs.get("output_prefix", "mageck_count"))
        return [node_out / f"{prefix}.count.txt", node_out / f"{prefix}.count_normalized.txt"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "library_file": ("FILE", {"description": "Library file with sgRNA sequences"}),
                "fastq_files": ("FASTQ_LIST", {"description": "FASTQ files from screen"}),
                "output_prefix": ("STRING", {"default": "mageck_count"}),
            },
            "optional": {
                "sample_labels": ("STRING", {"default": "", "description": "Comma-separated labels"}),
                "day0_label": ("STRING", {"default": "", "description": "Day 0 label for normalization"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class MAGeCKTestNode(CommandNode):
    """Rank CRISPR screen genes from MAGeCK count tables."""
    NODE_ID = "mageck_test"
    DISPLAY_NAME = "MAGeCK Test"
    CATEGORY = "crispr"
    DESCRIPTION = "Identify essential genes from CRISPR screens using negative binomial model. Treatment vs control."
    SEARCH_ALIASES = ["mageck", "test", "crispr screen", "essential genes", "gene ranking"]
    RETURN_TYPES = ("TSV", "TSV")
    RETURN_NAMES = ("gene_summary", "sgrna_summary")
    REQUIRED_EXECUTABLES = ["mageck"]
    REQUIRED_CONDA_PACKAGES = ["mageck"]
    DOCUMENTATION_URL = "https://sourceforge.net/p/mageck/wiki/Home/"
    VERSION = "0.5.9"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        prefix = str(inputs.get("output_prefix", "mageck_test"))
        cmd = [
            "mageck",
            "test",
            "-k",
            str(inputs.get("count_table", "")),
            "-t",
            str(inputs.get("treatment_labels", "")),
            "-c",
            str(inputs.get("control_labels", "")),
            "-n",
            f"{out_dir}/{prefix}",
        ]
        if inputs.get("norm_method"):
            cmd.extend(["--norm-method", str(inputs["norm_method"])])
        if inputs.get("adjust_method"):
            cmd.extend(["--adjust-method", str(inputs["adjust_method"])])
        if inputs.get("sort_criteria"):
            cmd.extend(["--sort-criteria", str(inputs["sort_criteria"])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        prefix = str(inputs.get("output_prefix", "mageck_test"))
        return [node_out / f"{prefix}.gene_summary.txt", node_out / f"{prefix}.sgrna_summary.txt"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "count_table": ("TSV", {"description": "MAGeCK count table"}),
                "treatment_labels": ("STRING", {"description": "Treatment sample labels (comma)"}),
                "control_labels": ("STRING", {"description": "Control sample labels (comma)"}),
                "output_prefix": ("STRING", {"default": "mageck_test"}),
            },
            "optional": {
                "norm_method": ("STRING", {"default": "median", "options": ["median", "total", "control", "none"]}),
                "adjust_method": ("STRING", {"default": "fdr", "options": ["fdr", "holm", "pounds"]}),
                "sort_criteria": ("STRING", {"default": "neg", "options": ["neg", "pos"]}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class CasOffinderNode(CommandNode):
    """Detect candidate CRISPR guide off-target sites with Cas-OFFinder."""
    NODE_ID = "cas_offinder"
    DISPLAY_NAME = "Cas-OFFinder"
    CATEGORY = "crispr"
    DESCRIPTION = "Fast off-target detection for CRISPR gRNAs. Multiple PAMs and mismatch tolerance."
    SEARCH_ALIASES = ["cas-offinder", "off target", "crispr safety", "grna", "guide rna"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("offtarget_sites",)
    REQUIRED_EXECUTABLES = ["cas-offinder"]
    REQUIRED_CONDA_PACKAGES = ["cas-offinder"]
    DOCUMENTATION_URL = "https://github.com/snugel/cas-offinder"
    VERSION = "2.4.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get("output", ".")))
        out_dir.mkdir(parents=True, exist_ok=True)
        input_file = out_dir / "cas_offinder_input.txt"
        output_file = out_dir / "offtarget_sites.txt"
        guide_seq = str(inputs.get("guide_seq", ""))
        pam_sequence = str(inputs.get("pam_sequence", "NNG"))
        search_pattern = f"{'N' * len(guide_seq)}{pam_sequence}"
        query_sequence = f"{guide_seq}{pam_sequence}"

        input_file.write_text(
            "\n".join([
                str(inputs.get("genome_fasta", "")),
                search_pattern,
                f"{query_sequence} {inputs.get('mismatches', 3)}",
            ])
            + "\n",
            encoding="utf-8",
        )
        return [
            "cas-offinder",
            str(input_file),
            str(inputs.get("device", "C")),
            str(output_file),
        ]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "offtarget_sites.txt"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "guide_seq": ("STRING", {"description": "Guide RNA sequence without PAM"}),
                "genome_fasta": ("FASTA", {"description": "Target genome FASTA or 2bit directory"}),
                "mismatches": ("INT", {"default": 3, "min": 0, "max": 10}),
            },
            "optional": {
                "pam_sequence": ("STRING", {"default": "NNG", "description": "PAM pattern (N=wildcard)"}),
                "device": (
                    "STRING",
                    {"default": "C", "options": ["C", "G", "A"], "description": "C=CPU, G=GPU, A=accelerator"},
                ),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
