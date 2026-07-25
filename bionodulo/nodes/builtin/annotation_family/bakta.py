"""Focused Bakta bacterial-genome annotation contract."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode, _shell_join

from .evidence import attach_evidence


@attach_evidence
class BaktaNode(CommandNode):
    """Galaxy-aligned bacterial genome annotation with Bakta."""

    NODE_ID = "bakta"
    DISPLAY_NAME = "Bakta"
    CATEGORY = "annotation"
    DESCRIPTION = "Rapid and standardized annotation of bacterial genomes, MAGs and plasmids."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "Bakta",
        "bakta",
        "bacterial genome annotation",
        "MAGs",
        "plasmids",
        "AMRFinderPlus",
        "GFF3",
    ]
    RETURN_TYPES = (
        "TSV",
        "GFF3",
        "GBFF",
        "EMBL",
        "FASTA",
        "FASTA",
        "FASTA",
        "TSV",
        "FASTA",
        "TXT",
        "JSON",
        "SVG",
        "TXT",
    )
    RETURN_NAMES = (
        "annotation_tsv",
        "annotation_gff3",
        "annotation_gbff",
        "annotation_embl",
        "annotation_fna",
        "annotation_ffn",
        "annotation_faa",
        "hypotheticals_tsv",
        "hypotheticals_faa",
        "summary_txt",
        "annotation_json",
        "annotation_plot",
        "logfile",
    )
    REQUIRED_EXECUTABLES = ["bakta", "ln", "mkdir", "cp", "tee"]
    REQUIRED_CONDA_PACKAGES = ["bakta", "coreutils"]
    DOCUMENTATION_URL = "https://github.com/oschwengers/bakta"
    CITATION_DOIS = ["10.1099/mgen.0.000685"]
    CITATION_URLS = ["https://doi.org/10.1099/mgen.0.000685"]
    CITATION_TEXT = (
        "Bakta: rapid and standardized annotation of bacterial genomes via "
        "alignment-free sequence identification."
    )
    SHELL = True

    SKIP_ANALYSIS_OPTIONS = [
        "--skip-trna",
        "--skip-tmrna",
        "--skip-rrna",
        "--skip-ncrna",
        "--skip-ncrna-region",
        "--skip-crispr",
        "--skip-cds",
        "--skip-pseudo",
        "--skip-sorf",
        "--skip-gap",
        "--skip-ori",
        "--skip-plot",
    ]
    OUTPUT_SELECTION_OPTIONS = [
        "file_tsv",
        "file_gff3",
        "file_gbff",
        "file_embl",
        "file_fna",
        "file_ffn",
        "file_faa",
        "hypo_tsv",
        "hypo_fa",
        "sum_txt",
        "file_json",
        "file_plot",
        "log_txt",
    ]
    DEFAULT_OUTPUT_SELECTION = ["file_tsv", "file_gff3", "file_ffn", "file_plot"]
    OUTPUT_PREFIX = "bakta_output"
    OUTPUT_FILES = {
        "file_tsv": ("annotation_tsv.tsv", f"bakta_output/{OUTPUT_PREFIX}.tsv"),
        "file_gff3": ("annotation_gff3.gff3", f"bakta_output/{OUTPUT_PREFIX}.gff3"),
        "file_gbff": ("annotation_gbff.gbff", f"bakta_output/{OUTPUT_PREFIX}.gbff"),
        "file_embl": ("annotation_embl.embl", f"bakta_output/{OUTPUT_PREFIX}.embl"),
        "file_fna": ("annotation_fna.fasta", f"bakta_output/{OUTPUT_PREFIX}.fna"),
        "file_ffn": ("annotation_ffn.fasta", f"bakta_output/{OUTPUT_PREFIX}.ffn"),
        "file_faa": ("annotation_faa.fasta", f"bakta_output/{OUTPUT_PREFIX}.faa"),
        "hypo_tsv": (
            "hypotheticals_tsv.tsv",
            f"bakta_output/{OUTPUT_PREFIX}.hypotheticals.tsv",
        ),
        "hypo_fa": (
            "hypotheticals_faa.fasta",
            f"bakta_output/{OUTPUT_PREFIX}.hypotheticals.faa",
        ),
        "sum_txt": ("summary_txt.txt", f"bakta_output/{OUTPUT_PREFIX}.txt"),
        "file_json": ("annotation_json.json", f"bakta_output/{OUTPUT_PREFIX}.json"),
        "file_plot": ("annotation_plot.svg", f"bakta_output/{OUTPUT_PREFIX}.svg"),
        "log_txt": ("logfile.txt", "logfile.txt"),
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("FASTA", {"description": "Genome in FASTA or FASTA.GZ format"}),
                "bakta_db": ("DIRECTORY", {"description": "Bakta database path"}),
                "amrfinder_db": ("DIRECTORY", {"description": "AMRFinderPlus database path"}),
            },
            "optional": {
                "min_contig_length": (
                    "INT",
                    {
                        "default": 1,
                        "min": 0,
                        "description": (
                            "Minimum contig size; Galaxy uses 200 in compliant mode when unset"
                        ),
                    },
                ),
                "genus": ("STRING", {"default": ""}),
                "species": ("STRING", {"default": ""}),
                "strain": ("STRING", {"default": ""}),
                "plasmid": ("STRING", {"default": ""}),
                "complete": ("BOOLEAN", {"default": False}),
                "prodigal": ("TXT", {"default": "", "description": "Prodigal training file"}),
                "translation_table": (
                    "STRING",
                    {
                        "default": "11",
                        "options": ["4", "11"],
                        "description": "Genetic translation table",
                    },
                ),
                "keep_contig_headers": ("BOOLEAN", {"default": False}),
                "replicons": ("TSV", {"default": ""}),
                "compliant": ("BOOLEAN", {"default": False}),
                "proteins": ("FASTA", {"default": ""}),
                "meta": ("BOOLEAN", {"default": False}),
                "regions": ("GFF", {"default": ""}),
                "skip_analysis": (
                    "STRING_LIST",
                    {"default": [], "options": cls.SKIP_ANALYSIS_OPTIONS, "is_list": True},
                ),
                "output_selection": (
                    "STRING_LIST",
                    {
                        "default": list(cls.DEFAULT_OUTPUT_SELECTION),
                        "options": cls.OUTPUT_SELECTION_OPTIONS,
                        "is_list": True,
                    },
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _as_list(cls, value: Any, default: list[str] | None = None) -> list[str]:
        if value is None or value == "":
            return list(default or [])
        if isinstance(value, (list, tuple, set)):
            return [str(item) for item in value if str(item)]
        return [part.strip() for part in re.split(r"[\n,]+", str(value)) if part.strip()]

    @classmethod
    def _output_selection(cls, inputs: dict[str, Any]) -> list[str]:
        return cls._as_list(inputs.get("output_selection"), cls.DEFAULT_OUTPUT_SELECTION)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for name in ("input_file", "bakta_db", "amrfinder_db"):
            if not str(inputs.get(name, "")).strip():
                return f"{name} is required"

        min_contig_length = inputs.get("min_contig_length")
        if min_contig_length not in (None, ""):
            try:
                if int(min_contig_length) < 0:
                    return "min_contig_length must be >= 0"
            except (TypeError, ValueError):
                return "min_contig_length must be an integer"

        if str(inputs.get("translation_table", "11") or "11") not in {"4", "11"}:
            return "translation_table must be one of: 4, 11"

        skip_analysis = cls._as_list(inputs.get("skip_analysis"))
        invalid_skip = [entry for entry in skip_analysis if entry not in cls.SKIP_ANALYSIS_OPTIONS]
        if invalid_skip:
            return f"skip_analysis entries must be one of: {', '.join(cls.SKIP_ANALYSIS_OPTIONS)}"

        output_selection = cls._output_selection(inputs)
        invalid_outputs = [entry for entry in output_selection if entry not in cls.OUTPUT_SELECTION_OPTIONS]
        if invalid_outputs:
            return (
                "output_selection entries must be one of: "
                f"{', '.join(cls.OUTPUT_SELECTION_OPTIONS)}"
            )
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out_dir = str(inputs.get("output", "."))
        command = [
            "bakta",
            "--verbose",
            "--threads",
            str(inputs.get("threads", 1) or 1),
            "--db",
            "./database_path",
            "--output",
            cls.OUTPUT_PREFIX,
            "--min-contig-length",
            str(inputs.get("min_contig_length", 1) or 1),
            "--prefix",
            cls.OUTPUT_PREFIX,
        ]
        for flag, input_name in (
            ("--genus", "genus"),
            ("--species", "species"),
            ("--strain", "strain"),
            ("--plasmid", "plasmid"),
        ):
            if inputs.get(input_name):
                command.extend([flag, str(inputs[input_name])])

        for input_name, flag in (("complete", "--complete"), ("meta", "--meta")):
            if inputs.get(input_name):
                command.append(flag)

        if inputs.get("prodigal"):
            command.extend(["--prodigal-tf", str(inputs["prodigal"])])
        if inputs.get("translation_table"):
            command.extend(["--translation-table", str(inputs["translation_table"])])
        command.extend(["--gram", "?"])
        if inputs.get("keep_contig_headers"):
            command.append("--keep-contig-headers")
        if inputs.get("replicons"):
            command.extend(["--replicons", str(inputs["replicons"])])
        if inputs.get("compliant"):
            command.append("--compliant")
        if inputs.get("proteins"):
            command.extend(["--proteins", str(inputs["proteins"])])
        if inputs.get("regions"):
            command.extend(["--regions", str(inputs["regions"])])

        command.extend(cls._as_list(inputs.get("skip_analysis")))
        command.extend(
            [str(inputs.get("input_file", "")), "2>&1", "|", "tee", f"{out_dir}/logfile.txt"]
        )

        commands = [
            _shell_join(["mkdir", "-p", "./database_path/amrfinderplus-db", out_dir]),
            f"ln -s {_shell_join([str(inputs.get('bakta_db', ''))])}/* database_path",
            _shell_join(
                [
                    "ln",
                    "-s",
                    f"{str(inputs.get('amrfinder_db', '')).rstrip('/')}/",
                    "database_path/amrfinderplus-db/latest",
                ]
            ),
            _shell_join(command),
        ]
        for selected in cls._output_selection(inputs):
            if selected == "log_txt":
                continue
            target, source = cls.OUTPUT_FILES[selected]
            commands.append(_shell_join(["cp", source, f"{out_dir}/{target}"]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / cls.OUTPUT_FILES[selected][0] for selected in cls._output_selection(inputs)]
