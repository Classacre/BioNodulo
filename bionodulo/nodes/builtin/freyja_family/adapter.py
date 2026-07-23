"""Focused freyja node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin._variant_assembly_contracts import pin_contract

class FreyjaVariantsNode(CommandNode):
    """Call SARS-CoV-2 variants and sequencing depths for Freyja demixing."""

    LEGACY_NODE_ID = "freyja_variants"
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

    LEGACY_NODE_ID = "freyja_demix"
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

    LEGACY_NODE_ID = "freyja_boot"
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

    LEGACY_NODE_ID = "freyja_aggregate_plot"
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

pin_contract(FreyjaVariantsNode)
pin_contract(FreyjaDemixNode)
pin_contract(FreyjaBootNode)
pin_contract(FreyjaAggregatePlotNode)

__all__ = ['FreyjaVariantsNode', 'FreyjaDemixNode', 'FreyjaBootNode', 'FreyjaAggregatePlotNode']
