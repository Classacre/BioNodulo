"""MaxBin2 2.2.7 metagenomic binning."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import MetagenomicsCommandNode, add_flag, path_list, path_value, validate_choice, validate_int, validate_number


class MaxBinNode(MetagenomicsCommandNode):
    """Run MaxBin2 and expose its documented prefix-family artifacts."""

    NODE_ID = "maxbin"
    DISPLAY_NAME = "MaxBin2"
    DESCRIPTION = "Bin metagenomic contigs with MaxBin2 2.2.7."
    SEARCH_ALIASES = ["BioNodulo builtin", "MaxBin2", "metagenomic binning", "MAGs"]
    RETURN_TYPES = ("DIRECTORY", "TSV", "TEXT", "TSV", "FASTA", "FASTA", "ARCHIVE")
    RETURN_NAMES = (
        "bin_collection",
        "summary",
        "log",
        "marker_counts",
        "unclassified_contigs",
        "too_short_contigs",
        "marker_archive",
    )
    REQUIRED_EXECUTABLES = ["run_MaxBin.pl"]
    REQUIRED_CONDA_PACKAGES = ["maxbin2"]
    VERSION = "2.2.7"
    BIOCONDA_VERSION = VERSION
    BIOCONDA_CONSTRAINT = "maxbin2=2.2.7"
    SOURCE_URL = "https://sourceforge.net/projects/maxbin2/files/MaxBin-2.2.7.tar.gz"
    SOURCE_SHA256 = "cb6429e857280c2b75823c8cd55058ed169c93bc707a46bde0c4383f2bffe09e"
    DOCUMENTATION_URL = "https://sourceforge.net/projects/maxbin2/files/MaxBin-2.2.7.tar.gz"
    UPSTREAM_SOURCE = "README.txt; run_MaxBin.pl"
    CITATION_DOIS = ["10.1186/2049-2618-2-26", "10.1093/bioinformatics/btv638"]
    EXIT_SEMANTICS = (
        "run_MaxBin.pl non-zero exit is fatal; BioNodulo requires the documented summary, log, marker, "
        "noclass, tooshort, and marker archive artifacts."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "contigs": ("CONTIGS", {"description": "Metagenomic contigs FASTA"}),
            },
            "optional": {
                "reads": (
                    "FILE_LIST",
                    {"default": [], "multiple": True, "description": "FASTA/FASTQ read files used to estimate abundance"},
                ),
                "abundance_files": (
                    "FILE_LIST",
                    {"default": [], "multiple": True, "description": "Tab-separated contig abundance files"},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 256}),
                "prob_threshold": ("FLOAT", {"default": 0.8, "min": 0.0, "max": 1.0}),
                "markerset": ("STRING", {"default": "107", "options": ["107", "40"]}),
                "plotmarker": ("BOOLEAN", {"default": False}),
                "verbose": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        prefix = node_dir / "maxbin"
        return [
            node_dir,
            Path(f"{prefix}.summary"),
            Path(f"{prefix}.log"),
            Path(f"{prefix}.marker"),
            Path(f"{prefix}.noclass"),
            Path(f"{prefix}.tooshort"),
            Path(f"{prefix}.marker_of_each_gene.tar.gz"),
        ]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not path_value(inputs.get("contigs")):
            return "Input 'contigs' must be a non-empty path-like value"
        reads = path_list(inputs.get("reads"))
        abundances = path_list(inputs.get("abundance_files"))
        if not reads and not abundances:
            return "MaxBin requires at least one reads or abundance file"
        validation = validate_int(inputs.get("threads", 1), "threads", minimum=1, maximum=256)
        if validation is not True:
            return validation
        validation = validate_number(inputs.get("prob_threshold", 0.8), "prob_threshold", minimum=0, maximum=1)
        if validation is not True:
            return validation
        return validate_choice(inputs.get("markerset", "107"), "markerset", ("107", "40"))

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        node_dir = outputs[0]
        reads = path_list(inputs.get("reads"))
        abundances = path_list(inputs.get("abundance_files"))
        if len(reads) > 1:
            reads_list = node_dir / "reads.list"
            reads_list.write_text("\n".join(reads) + "\n", encoding="utf-8")
            inputs["_reads_list"] = str(reads_list)
        if len(abundances) > 1:
            abundance_list = node_dir / "abundance.list"
            abundance_list.write_text("\n".join(abundances) + "\n", encoding="utf-8")
            inputs["_abundance_list"] = str(abundance_list)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = [
            "run_MaxBin.pl",
            "-contig",
            path_value(inputs.get("contigs")),
            "-out",
            str(output / "maxbin"),
        ]
        reads = path_list(inputs.get("reads"))
        if len(reads) == 1:
            command.extend(["-reads", reads[0]])
        elif reads:
            command.extend(["-reads_list", str(inputs.get("_reads_list", output / "reads.list"))])
        abundances = path_list(inputs.get("abundance_files"))
        if len(abundances) == 1:
            command.extend(["-abund", abundances[0]])
        elif abundances:
            command.extend(["-abund_list", str(inputs.get("_abundance_list", output / "abundance.list"))])
        command.extend(
            [
                "-thread",
                str(inputs.get("threads", 1)),
                "-prob_threshold",
                str(inputs.get("prob_threshold", 0.8)),
                "-markerset",
                str(inputs.get("markerset", "107")),
            ]
        )
        add_flag(command, "-plotmarker", inputs.get("plotmarker"))
        add_flag(command, "-verbose", inputs.get("verbose"))
        return command
