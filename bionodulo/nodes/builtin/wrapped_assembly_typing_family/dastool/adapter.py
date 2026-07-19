"""Shared DAS Tool and bin-map contracts for focused owners."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from bionodulo.nodes.builtin.wrapped_assembly_typing_family.contracts import (
    TOOLS_IUC_GIT_COMMIT,
    ToolsIUCCommandContract,
)


class DASToolContractNode(ToolsIUCCommandContract):
    GIT_COMMIT = TOOLS_IUC_GIT_COMMIT
    SOURCE_URL = f"https://github.com/galaxyproject/tools-iuc/tree/{TOOLS_IUC_GIT_COMMIT}/tools/das_tool"
    GALAXY_WRAPPER_SOURCE_URL = SOURCE_URL
    GALAXY_WRAPPER_VERSION = "1.1.7+galaxy1"
    PACKAGE_CONSTRAINT = "das_tool==1.1.7"


class _DASToolContract(DASToolContractNode):
    """Integrate metagenomic binning predictions with DAS Tool."""

    LEGACY_NODE_ID = "das_tool"
    DISPLAY_NAME = "DAS Tool"
    REQUIRED_CONDA_PACKAGES = ["das_tool"]
    CATEGORY = "metagenomics"
    DESCRIPTION = (
        "Integrate multiple metagenomic binning predictions into an optimized, non-redundant set of genome bins."
    )
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "das tool",
        "DAS Tool",
        "DAS_Tool",
        "dastool",
        "genome-resolved metagenomics",
        "bin dereplication",
        "bin aggregation",
        "metagenome binning",
    ]
    RETURN_TYPES = ("TSV", "TSV", "TEXT", "TSV", "FASTA_LIST", "FASTA", "FASTA")
    RETURN_NAMES = ("summary", "contigs2bin", "log", "eval", "bins", "unbinned_contigs", "proteins")
    REQUIRED_EXECUTABLES = ["DAS_Tool"]
    DOCUMENTATION_URL = "https://github.com/cmks/DAS_Tool"
    CITATION_DOIS = ["10.1038/s41564-018-0171-1"]
    CITATION_URLS = ["https://doi.org/10.1038/s41564-018-0171-1"]
    CITATION_TEXT = "Recovery of genomes from metagenomes via a dereplication, aggregation and scoring strategy."
    VERSION = "1.1.7"
    SHELL = True

    @classmethod
    def _binning_entries(cls, inputs: dict[str, Any]) -> list[tuple[str, str]]:
        repeat = inputs.get("binning")
        if isinstance(repeat, (list, tuple)):
            entries: list[tuple[str, str]] = []
            for item in repeat:
                if isinstance(item, dict):
                    bin_file = str(item.get("bins", ""))
                    label = str(item.get("labels", item.get("label", "")))
                else:
                    bin_file = str(item)
                    label = ""
                if bin_file:
                    entries.append((bin_file, label))
            if entries:
                return entries

        bins = _as_list(inputs.get("bins"))
        raw_labels = inputs.get("labels", inputs.get("bin_labels"))
        if isinstance(raw_labels, (list, tuple)):
            labels = [str(label) if label is not None else "" for label in raw_labels]
        elif raw_labels is None or raw_labels == "":
            labels = []
        else:
            labels = [str(raw_labels)]
        return [(bin_file, labels[index] if index < len(labels) else "") for index, bin_file in enumerate(bins)]

    @classmethod
    def _labels(cls, entries: list[tuple[str, str]]) -> list[str]:
        return [_safe_label(label) if label else _safe_name(bin_file) for bin_file, label in entries]

    @classmethod
    def _write_bins_enabled(cls, inputs: dict[str, Any]) -> bool:
        value = inputs.get("write_bins")
        if isinstance(value, bool):
            return value
        return str(value if value is not None else "--write_bins") != ""

    @classmethod
    def _output_proteins_enabled(cls, inputs: dict[str, Any]) -> bool:
        return bool(inputs.get("output_proteins", inputs.get("output_proteins_file", inputs.get("proteins_output"))))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        entries = cls._binning_entries(inputs)
        proteins = str(inputs.get("proteins", ""))
        cmd: list[str] = []
        if proteins:
            cmd.extend(["ln", "-sf", proteins, f"{out}/proteins", "&&"])
        cmd.extend(
            [
                "DAS_Tool",
                "--contigs",
                str(inputs.get("contigs", "")),
                "--outputbasename",
                f"{out}/outputs",
                "--bins",
                ",".join(bin_file for bin_file, _label in entries),
                "--labels",
                ",".join(cls._labels(entries)),
                "--search_engine",
                str(inputs.get("search_engine", "diamond")),
            ]
        )
        if proteins:
            cmd.extend(["--proteins", f"{out}/proteins"])
        cmd.extend(
            [
                "--score_threshold",
                str(inputs.get("score_threshold", 0.5)),
                "--duplicate_penalty",
                str(inputs.get("duplicate_penalty", 0.6)),
                "--megabin_penalty",
                str(inputs.get("megabin_penalty", 0.5)),
                "--max_iter_post_threshold",
                str(inputs.get("max_iter_post_threshold", 10)),
            ]
        )
        if inputs.get("write_bin_evals"):
            cmd.append("--write_bin_evals")
        if cls._write_bins_enabled(inputs):
            cmd.append("--write_bins")
            if inputs.get("write_unbinned"):
                cmd.append("--write_unbinned")
        if inputs.get("debug"):
            cmd.append("--debug")
        cmd.extend(["--threads", str(inputs.get("threads", 1))])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [
            out / "outputs_DASTool_summary.tsv",
            out / "outputs_DASTool_contig2bin.tsv",
            out / "outputs_DASTool.log",
        ]
        if inputs.get("write_bin_evals"):
            outputs.append(out / "outputs_allBins.eval")
        if cls._write_bins_enabled(inputs):
            bins_dir = out / "outputs_DASTool_bins"
            bins_dir.mkdir(parents=True, exist_ok=True)
            outputs.append(bins_dir)
            if inputs.get("write_unbinned"):
                outputs.append(bins_dir / "unbinned.fa")
        if cls._output_proteins_enabled(inputs):
            outputs.append(out / "outputs_proteins.faa")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "contigs": ("FASTA", {"description": "Assembled contig sequences"}),
                "bins": (
                    "TSV",
                    {
                        "list": True,
                        "min_items": 1,
                        "description": "One or more contig-to-bin tables with contig IDs and bin IDs",
                    },
                ),
            },
            "optional": {
                "labels": (
                    "STRING",
                    {
                        "list": True,
                        "description": "Binning prediction labels; blank labels fall back to sanitized table filenames",
                    },
                ),
                "search_engine": (
                    "STRING",
                    {
                        "default": "diamond",
                        "options": ["diamond", "blastp"],
                        "description": "Engine used for single-copy gene identification",
                    },
                ),
                "proteins": (
                    "FASTA",
                    {"default": "", "description": "Optional predicted proteins in Prodigal FASTA format"},
                ),
                "score_threshold": (
                    "FLOAT",
                    {
                        "default": 0.5,
                        "min": 0,
                        "max": 1,
                        "description": "Score threshold until selection algorithm keeps selecting bins",
                    },
                ),
                "duplicate_penalty": (
                    "FLOAT",
                    {
                        "default": 0.6,
                        "min": 0,
                        "max": 3,
                        "description": "Penalty for duplicate single-copy genes per bin",
                    },
                ),
                "megabin_penalty": (
                    "FLOAT",
                    {"default": 0.5, "min": 0, "max": 3, "description": "Penalty for megabins"},
                ),
                "max_iter_post_threshold": (
                    "INT",
                    {
                        "default": 10,
                        "min": 1,
                        "description": "Maximum iterations after reaching the score threshold",
                    },
                ),
                "output_proteins": ("BOOLEAN", {"default": False, "description": "Output predicted proteins"}),
                "write_bin_evals": (
                    "BOOLEAN",
                    {"default": False, "description": "Write evaluation of input bin sets"},
                ),
                "write_bins": (
                    "STRING",
                    {
                        "default": "--write_bins",
                        "options": ["--write_bins", ""],
                        "description": "Export selected bins as FASTA files",
                    },
                ),
                "write_unbinned": (
                    "BOOLEAN",
                    {"default": False, "description": "Export unbinned contigs when writing bins"},
                ),
                "debug": ("BOOLEAN", {"default": False, "description": "Write debug information to the log file"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _FastaToContig2BinContract(DASToolContractNode):
    """Convert genome-bin FASTA files into a DAS Tool contig-to-bin table."""

    LEGACY_NODE_ID = "fasta_to_contig2bin"
    DISPLAY_NAME = "FASTA to Contig2Bin"
    REQUIRED_CONDA_PACKAGES = ["das_tool"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Convert a list of genome-bin FASTA files into a tabular contig-to-bin assignment table for DAS Tool."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Fasta_to_Contig2Bin",
        "Fasta_to_Contig2Bin.sh",
        "DAS Tool helper",
        "contig2bin",
        "contigs2bin",
        "genome bins",
        "bin FASTA",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("contigs2bin",)
    REQUIRED_EXECUTABLES = ["Fasta_to_Contig2Bin.sh"]
    DOCUMENTATION_URL = "https://github.com/cmks/DAS_Tool#preparation-of-input-files"
    CITATION_DOIS = ["10.1038/s41564-018-0171-1"]
    CITATION_URLS = ["https://doi.org/10.1038/s41564-018-0171-1"]
    CITATION_TEXT = "Recovery of genomes from metagenomes via a dereplication, aggregation and scoring strategy."
    VERSION = "1.1.7"
    SHELL = True

    @classmethod
    def _input_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("inputs", inputs.get("input")))

    @classmethod
    def _element_identifiers(cls, inputs: dict[str, Any], input_files: list[str]) -> list[str]:
        raw = inputs.get("element_identifiers", inputs.get("identifiers", inputs.get("labels")))
        if isinstance(raw, (list, tuple)):
            identifiers = [str(identifier) if identifier is not None else "" for identifier in raw]
        elif raw is None or raw == "":
            identifiers = []
        else:
            identifiers = [str(raw)]
        return [
            _safe_identifier(identifiers[index]) if index < len(identifiers) and identifiers[index] else _safe_name(input_file)
            for index, input_file in enumerate(input_files)
        ]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        input_dir = f"{out}/inputs"
        input_files = cls._input_files(inputs)
        identifiers = cls._element_identifiers(inputs, input_files)
        cmd = ["mkdir", "-p", input_dir]
        for input_file, identifier in zip(input_files, identifiers, strict=True):
            cmd.extend(["&&", "ln", "-sf", input_file, f"{input_dir}/{identifier}.fasta"])
        cmd.extend(
            [
                "&&",
                "Fasta_to_Contig2Bin.sh",
                "--extension",
                "fasta",
                "--input_folder",
                input_dir,
                ">",
                f"{out}/contigs2bin.tsv",
            ]
        )
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "contigs2bin.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputs": (
                    "FASTA_LIST",
                    {"description": "Genome-bin FASTA files to convert into contig-to-bin assignments"},
                ),
            },
            "optional": {
                "element_identifiers": (
                    "STRING",
                    {
                        "list": True,
                        "description": "Optional bin labels matching the FASTA collection element identifiers",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
