"""Metagenomics analysis nodes for BioNodulo.

Provides nodes for taxonomic classification (Kraken2, Bracken, MetaPhlAn),
functional profiling (HUMAnN), binning (MaxBin), and quality assessment (CheckM).
"""
from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any, Optional

from bionodulo.nodes.command_node import CommandNode, _shell_join


DOI_URL = "https://doi.org/"
METAPHLAN_DOI = "10.1038/s41587-023-01688-w"
METAPHLAN_CITATION_TEXT = (
    "Extending and improving metagenomic taxonomic profiling with uncharacterized species using MetaPhlAn 4."
)
HUMANN_CITATION_DOIS = ["10.7554/eLife.65088", "10.1371/journal.pcbi.1002358"]
HUMANN_CITATION_TEXT = (
    "bioBakery 3: a platform for analyzing meta'omic datasets; "
    "HUMAnN: the HMP Unified Metabolic Analysis Network."
)
KRAKEN2_CITATION_DOI = "10.1186/gb-2014-15-3-r46"
KRAKEN2_CITATION_TEXT = "Kraken: ultrafast metagenomic sequence classification using exact alignments."
BRACKEN_CITATION_DOI = "10.7717/peerj-cs.104"
BRACKEN_CITATION_TEXT = "Bracken: estimating species abundance in metagenomics data."


def _as_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if str(v) != ""]
    return [str(value)]


def _add_shell_redirect(cmd: list[str], output_path: str) -> None:
    cmd.extend([">", output_path])


def _shell_join_allow_substitution(cmd: list[str]) -> str:
    parts: list[str] = []
    for token in cmd:
        parts.append(token if token.startswith("$(") else _shell_join([token]))
    return " ".join(parts)


class Kraken2Node(CommandNode):
    """Taxonomic classification with Kraken2."""

    NODE_ID = "kraken2"
    DISPLAY_NAME = "Kraken2"
    REQUIRED_CONDA_PACKAGES = ["kraken2"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Assign taxonomic labels to sequencing reads with Kraken2."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "Kraken2",
        "taxonomic classification",
        "classified reads",
        "unclassified reads",
        "Kraken report",
        "MPA style report",
        "minimizer data",
    ]
    RETURN_TYPES = ("KRAKEN_OUTPUT", "KRAKEN_REPORT", "FASTQ", "FASTQ", "DIRECTORY", "DIRECTORY")
    RETURN_NAMES = (
        "output",
        "report",
        "classified_reads",
        "unclassified_reads",
        "classified_read_pairs",
        "unclassified_read_pairs",
    )
    REQUIRED_EXECUTABLES = ["kraken2"]
    DOCUMENTATION_URL = "https://ccb.jhu.edu/software/kraken2/"
    CITATION_DOIS = [KRAKEN2_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{KRAKEN2_CITATION_DOI}"]
    CITATION_TEXT = KRAKEN2_CITATION_TEXT
    VERSION = "2.17.1"
    SHELL = True

    @classmethod
    def _out(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("output", "."))

    @classmethod
    def _output_path(cls, out: str) -> str:
        return f"{out}/output.kraken"

    @classmethod
    def _report_path(cls, out: str) -> str:
        return f"{out}/report.kreport"

    @classmethod
    def _classified_path(cls, out: str, input_ext: str) -> str:
        return f"{out}/classified_reads.{input_ext}"

    @classmethod
    def _unclassified_path(cls, out: str, input_ext: str) -> str:
        return f"{out}/unclassified_reads.{input_ext}"

    @classmethod
    def _classified_pair_dir(cls, out: str) -> str:
        return f"{out}/classified_read_pairs"

    @classmethod
    def _unclassified_pair_dir(cls, out: str) -> str:
        return f"{out}/unclassified_read_pairs"

    @classmethod
    def _read_files(cls, inputs: dict[str, Any]) -> list[str]:
        reads = _as_list(inputs.get("reads"))
        if reads:
            return reads
        return [read for read in [str(inputs.get("r1", "")), str(inputs.get("r2", ""))] if read]

    @classmethod
    def _single_paired_selector(cls, inputs: dict[str, Any], reads: list[str]) -> str:
        if inputs.get("single_paired_selector"):
            return str(inputs["single_paired_selector"])
        if inputs.get("paired", False) or len(reads) > 1:
            return "collection"
        return "no"

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        input_ext = str(inputs.get("input_ext", "")).lower()
        if input_ext:
            return input_ext
        reads = cls._read_files(inputs)
        if not reads:
            return "fastq"
        name = reads[0].lower()
        for ext in ("fastq.gz", "fastq.bz2", "fasta.gz", "fasta.bz2", "fq.gz", "fq.bz2", "fa.gz", "fa.bz2"):
            if name.endswith(ext):
                return "fastq.gz" if ext == "fq.gz" else "fastq.bz2" if ext == "fq.bz2" else "fasta.gz" if ext == "fa.gz" else "fasta.bz2" if ext == "fa.bz2" else ext
        if name.endswith((".fasta", ".fa", ".fna")):
            return "fasta"
        return "fastq"

    @classmethod
    def _split_command(cls, input_ext: str) -> str:
        if input_ext.endswith(".gz"):
            return "gzip -c"
        if input_ext.endswith(".bz2"):
            return "bzip2 -c"
        return "cat"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = cls._out(inputs)
        reads = cls._read_files(inputs)
        selector = cls._single_paired_selector(inputs, reads)
        input_ext = cls._input_ext(inputs)
        cmd = [
            "kraken2",
            "--threads", str(inputs.get("threads", 8)),
            "--db", str(inputs.get("db", "")),
        ]
        if inputs.get("quick"):
            cmd.append("--quick")
        if selector == "collection":
            cmd.append("--paired")
            cmd.extend(reads[:2])
        elif reads:
            cmd.append(reads[0])
        if inputs.get("split_reads"):
            if selector == "collection":
                cmd.extend(["--unclassified-out", "un_out#", "--classified-out", "cl_out#"])
            else:
                cmd.extend(["--unclassified-out", "un_out", "--classified-out", "cl_out"])
        cmd.extend(
            [
                "--confidence",
                str(inputs.get("confidence", 0.0)),
                "--minimum-base-quality",
                str(inputs.get("min_base_quality", 0)),
                "--minimum-hit-groups",
                str(inputs.get("minimum_hit_groups", 2)),
            ]
        )
        if inputs.get("use_names"):
            cmd.append("--use-names")
        if inputs.get("create_report", True):
            cmd.extend(["--report", cls._report_path(out)])
            if inputs.get("use_mpa_style"):
                cmd.append("--use-mpa-style")
            if inputs.get("report_zero_counts"):
                cmd.append("--report-zero-counts")
            if inputs.get("report_minimizer_data"):
                cmd.append("--report-minimizer-data")
        if inputs.get("memory_mapping"):
            cmd.append("--memory-mapping")

        command = _shell_join(cmd)
        command += " > " + shlex.quote(cls._output_path(out))
        if not inputs.get("split_reads"):
            return command

        split_command = cls._split_command(input_ext)
        if selector == "collection":
            classified_dir = cls._classified_pair_dir(out)
            unclassified_dir = cls._unclassified_pair_dir(out)
            postprocess = [
                _shell_join(["mkdir", "-p", classified_dir, unclassified_dir]),
                f"{split_command} un_out_1 > {shlex.quote(f'{unclassified_dir}/forward.{input_ext}')}",
                f"{split_command} un_out_2 > {shlex.quote(f'{unclassified_dir}/reverse.{input_ext}')}",
                f"{split_command} cl_out_1 > {shlex.quote(f'{classified_dir}/forward.{input_ext}')}",
                f"{split_command} cl_out_2 > {shlex.quote(f'{classified_dir}/reverse.{input_ext}')}",
            ]
        else:
            postprocess = [
                f"{split_command} un_out > {shlex.quote(cls._unclassified_path(out, input_ext))}",
                f"{split_command} cl_out > {shlex.quote(cls._classified_path(out, input_ext))}",
            ]
        return " && ".join([command, *postprocess])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "output.kraken"]
        if inputs.get("create_report", True):
            outputs.append(out / "report.kreport")
        if inputs.get("split_reads"):
            selector = cls._single_paired_selector(inputs, cls._read_files(inputs))
            if selector == "collection":
                outputs.extend([out / "classified_read_pairs", out / "unclassified_read_pairs"])
            else:
                input_ext = cls._input_ext(inputs)
                outputs.extend([out / f"classified_reads.{input_ext}", out / f"unclassified_reads.{input_ext}"])
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get("db"):
            return "db is required"
        reads = cls._read_files(inputs)
        if not reads:
            return "reads is required"
        if cls._single_paired_selector(inputs, reads) == "collection" and len(reads) < 2:
            return "Paired Kraken2 input requires two read files"
        confidence = inputs.get("confidence", 0.0)
        if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
            return "confidence must be between 0 and 1"
        return True

    async def run(self, **kwargs: Any) -> Any:
        """Accept reads list and split into r1/r2 for Kraken2."""
        reads = kwargs.get("reads", [])
        if isinstance(reads, (list, tuple)) and len(reads) >= 2:
            kwargs["r1"] = reads[0]
            kwargs["r2"] = reads[1]
        return await super().run(**kwargs)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "db": ("DIRECTORY", {"description": "Kraken2 database directory"}),
                "reads": ("FILE", {"description": "Input sequences"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "single_paired_selector": (
                    "STRING",
                    {"default": "no", "options": ["no", "collection"], "description": "Single reads or paired read collection"},
                ),
                "r1": ("FASTQ", {"default": "", "description": "Legacy forward reads input"}),
                "r2": ("FASTQ", {"default": "", "description": "Legacy reverse reads input"}),
                "input_ext": (
                    "STRING",
                    {
                        "default": "fastq",
                        "options": ["fasta", "fasta.gz", "fasta.bz2", "fastq", "fastq.gz", "fastq.bz2"],
                        "description": "Input extension used for split-read outputs",
                    },
                ),
                "use_names": ("BOOLEAN", {"default": False, "label": "Print scientific names instead of just taxids"}),
                "confidence": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01, "label": "Confidence", "advanced": True}),
                "min_base_quality": ("INT", {"default": 0, "min": 0, "label": "Minimum Base Quality", "advanced": True}),
                "minimum_hit_groups": ("INT", {"default": 2, "label": "Minimum hit groups", "advanced": True}),
                "quick": ("BOOLEAN", {"default": False, "label": "Enable quick operation", "advanced": True}),
                "split_reads": ("BOOLEAN", {"default": False, "label": "Split classified and unclassified outputs"}),
                "create_report": ("BOOLEAN", {"default": True, "label": "Print a report with aggregate counts/clade"}),
                "use_mpa_style": ("BOOLEAN", {"default": False, "label": "Format report output like Kraken 1 MPA report", "advanced": True}),
                "report_zero_counts": ("BOOLEAN", {"default": False, "label": "Report counts for all taxa", "advanced": True}),
                "report_minimizer_data": ("BOOLEAN", {"default": False, "label": "Report minimizer data", "advanced": True}),
                "memory_mapping": ("BOOLEAN", {"default": False, "label": "Memory Mapping", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class Kraken2BuildNode(CommandNode):
    """Build Kraken2 database."""
    NODE_ID = "kraken2_build"
    DISPLAY_NAME = "Kraken2 Build DB"
    CATEGORY = "metagenomics"
    DESCRIPTION = "Build a Kraken2 database from reference sequences"
    SEARCH_ALIASES = ["kraken2", "build", "database", "custom db"]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("db",)
    REQUIRED_EXECUTABLES = ["kraken2-build"]
    REQUIRED_CONDA_PACKAGES = ['kraken2']
    DOCUMENTATION_URL = "https://ccb.jhu.edu/software/kraken2/"
    VERSION = "2.1.6"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        step = inputs.get("step", "download-taxonomy")
        cmd = [
            "kraken2-build",
            "--db", str(inputs.get("db", "")),
            "--threads", str(inputs.get("threads", 8)),
        ]
        if step == "download-taxonomy":
            cmd.append("--download-taxonomy")
        elif step == "download-library":
            cmd.extend(["--download-library", str(inputs.get("library", "bacteria"))])
        elif step == "build":
            cmd.append("--build")
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "db": ("DIRECTORY", {"description": "Output database directory"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
                "step": (["download-taxonomy", "download-library", "build"], {"default": "download-taxonomy"}),
            },
            "optional": {
                "library": ("STRING", {"default": "bacteria", "description": "RefSeq library to download"}),
            },
            "hidden": {},
        }


class BrackenNode(CommandNode):
    """Abundance estimation with Bracken."""

    NODE_ID = "bracken"
    DISPLAY_NAME = "Bracken"
    REQUIRED_CONDA_PACKAGES = ["bracken"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Re-estimate taxonomic abundance from a Kraken report with Bracken."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "Bracken",
        "est_abundance.py",
        "Kraken report",
        "taxonomy abundance",
        "Kraken-style Bracken report",
    ]
    RETURN_TYPES = ("TSV", "TSV", "TXT")
    RETURN_NAMES = ("report", "kraken_report", "logfile")
    REQUIRED_EXECUTABLES = ["est_abundance.py"]
    DOCUMENTATION_URL = "https://github.com/jenniferlu717/Bracken/releases"
    CITATION_DOIS = [BRACKEN_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BRACKEN_CITATION_DOI}"]
    CITATION_TEXT = BRACKEN_CITATION_TEXT
    VERSION = "3.1"
    SHELL = True

    @classmethod
    def _out(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("output", "."))

    @classmethod
    def _report_path(cls, out: str) -> str:
        return f"{out}/report.tsv"

    @classmethod
    def _kraken_report_path(cls, out: str) -> str:
        return f"{out}/kraken_report.tsv"

    @classmethod
    def _log_path(cls, out: str) -> str:
        return f"{out}/bracken.log"

    @classmethod
    def _kmer_distribution(cls, inputs: dict[str, Any]) -> str:
        if inputs.get("kmer_distr"):
            return str(inputs["kmer_distr"])
        if inputs.get("db"):
            read_length = str(inputs.get("read_length", 100))
            return f"{inputs['db']}/database{read_length}mers.kmer_distrib"
        return ""

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = cls._out(inputs)
        cmd = [
            "set",
            "-o",
            "pipefail",
            "&&",
            "est_abundance.py",
            "-i",
            str(inputs.get("report", inputs.get("input", ""))),
            "-k",
            cls._kmer_distribution(inputs),
            "-l",
            str(inputs.get("level", "S")),
            "-t",
            str(inputs.get("threshold", 10)),
            "-o",
            cls._report_path(out),
            "--out-report",
            "bracken.report",
        ]
        if inputs.get("logfile_output"):
            cmd.extend(["|", "tee", cls._log_path(out)])
        rendered = _shell_join(cmd)
        if inputs.get("out_report"):
            rendered += " && " + _shell_join(["mv", "bracken.report", cls._kraken_report_path(out)])
        return rendered

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "report.tsv"]
        if inputs.get("out_report"):
            outputs.append(out / "kraken_report.tsv")
        if inputs.get("logfile_output"):
            outputs.append(out / "bracken.log")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get("report") and not inputs.get("input"):
            return "report is required"
        if not inputs.get("kmer_distr") and not inputs.get("db"):
            return "kmer_distr is required unless db is provided for legacy Kraken database compatibility"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "report": ("TSV", {"description": "Kraken report file"}),
            },
            "optional": {
                "kmer_distr": (
                    "FILE",
                    {"default": "", "description": "Bracken k-mer distribution file (required unless 'db' is provided, from which it is derived)"},
                ),
                "db": (
                    "DIRECTORY",
                    {"default": "", "description": "Legacy Kraken database directory used to derive database{read_length}mers.kmer_distrib"},
                ),
                "read_length": ("STRING", {"default": "100", "description": "Legacy read length used with db"}),
                "level": (
                    "STRING",
                    {"default": "S", "options": ["S2", "S1", "S", "G", "F", "O", "C", "P", "D"], "description": "Taxonomic level"},
                ),
                "threshold": (
                    "INT",
                    {
                        "default": 10,
                        "description": "Minimum Kraken-assigned reads required before final abundance estimation",
                    },
                ),
                "out_report": ("BOOLEAN", {"default": False, "description": "Produce Kraken-style Bracken report"}),
                "logfile_output": ("BOOLEAN", {"default": False, "description": "Add log file output"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class MetaPhlAnNode(CommandNode):
    """Taxonomic profiling with MetaPhlAn."""

    NODE_ID = "metaphlan"
    DISPLAY_NAME = "MetaPhlAn"
    REQUIRED_CONDA_PACKAGES = ["metaphlan"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Profile microbial community composition with MetaPhlAn 4 marker genes."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "MetaPhlAn",
        "metagenomic profiling",
        "relative abundance",
        "marker abundance",
        "VSC breadth",
        "Krona",
        "BIOM",
    ]
    RETURN_TYPES = ("METAPHLAN_PROFILE", "TSV", "SAM", "BIOM", "DIRECTORY", "TSV", "TSV", "FASTQ", "DIRECTORY")
    RETURN_NAMES = (
        "profile",
        "mapout",
        "sam_output",
        "biom_output",
        "split_levels",
        "krona_output",
        "vsc_breadth_coverage",
        "subsampled_reads",
        "subsampled_paired_reads",
    )
    REQUIRED_EXECUTABLES = ["metaphlan"]
    DOCUMENTATION_URL = "https://github.com/biobakery/MetaPhlAn"
    CITATION_DOIS = [METAPHLAN_DOI]
    CITATION_URLS = [f"{DOI_URL}{METAPHLAN_DOI}"]
    CITATION_TEXT = METAPHLAN_CITATION_TEXT
    VERSION = "4.2.4"
    SHELL = True

    @classmethod
    def _out(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("output", "."))

    @classmethod
    def _input_selector(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("input_selector", inputs.get("input_type", "raw")))

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        input_ext = str(inputs.get("input_ext", inputs.get("input_type", "fastq"))).lower()
        if input_ext.endswith(".gz"):
            input_ext = input_ext.removesuffix(".gz")
        elif input_ext.endswith(".bz2"):
            input_ext = input_ext.removesuffix(".bz2")
        return "fasta" if input_ext.startswith("fasta") else "fastq" if input_ext.startswith("fastq") else input_ext

    @classmethod
    def _raw_selector(cls, inputs: dict[str, Any], reads: list[str]) -> str:
        if inputs.get("raw_selector"):
            return str(inputs["raw_selector"])
        if inputs.get("paired", False):
            return "paired"
        if len(reads) > 1:
            return "multiple"
        return "single"

    @classmethod
    def _profile_path(cls, out: str) -> str:
        return f"{out}/profile.metaphlan.tsv"

    @classmethod
    def _mapout_path(cls, out: str) -> str:
        return f"{out}/mapout.tsv"

    @classmethod
    def _sam_path(cls, out: str) -> str:
        return f"{out}/sam_output.sam"

    @classmethod
    def _biom_path(cls, out: str) -> str:
        return f"{out}/biom_output.biom"

    @classmethod
    def _split_levels_path(cls, out: str) -> str:
        return f"{out}/split_levels"

    @classmethod
    def _krona_path(cls, out: str) -> str:
        return f"{out}/krona_output.tsv"

    @classmethod
    def _vsc_path(cls, out: str) -> str:
        return f"{out}/vsc_breadth_coverage.tsv"

    @classmethod
    def _subsampled_reads_path(cls, out: str) -> str:
        return f"{out}/subsampled.fastq"

    @classmethod
    def _subsampled_paired_path(cls, out: str) -> str:
        return f"{out}/subsampled_paired_reads"

    @classmethod
    def _formatoutput_script(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("formatoutput_script", "formatoutput.py"))

    @classmethod
    def _customizemetadata_script(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("customizemetadata_script", "customizemetadata.py"))

    @classmethod
    def _prepare_raw_input(cls, inputs: dict[str, Any], reads: list[str]) -> tuple[list[str], list[str], str, str]:
        raw_selector = cls._raw_selector(inputs, reads)
        input_ext = str(inputs.get("input_ext", inputs.get("input_type", "fastq"))).lower()
        commands: list[str] = []
        file_arg = ""
        if raw_selector == "single":
            read = reads[0] if reads else ""
            if input_ext.endswith("gz"):
                commands.append(_shell_join(["zcat", read, ">", "in"]))
                file_arg = "in"
            elif input_ext.endswith("bz2"):
                commands.append(_shell_join(["bzcat", read, ">", "in"]))
                file_arg = "in"
            else:
                file_arg = read
        elif raw_selector == "multiple":
            prepared: list[str] = []
            for index, read in enumerate(reads):
                name = f"input_{index}"
                if input_ext.endswith("gz"):
                    commands.append(_shell_join(["zcat", read, ">", name]))
                    prepared.append(name)
                elif input_ext.endswith("bz2"):
                    commands.append(_shell_join(["bzcat", read, ">", name]))
                    prepared.append(name)
                else:
                    prepared.append(read)
            file_arg = ",".join(prepared)
        elif raw_selector in {"paired", "paired_collection"}:
            forward = reads[0] if reads else ""
            reverse = reads[1] if len(reads) > 1 else ""
            if input_ext.endswith("gz"):
                commands.append(_shell_join(["zcat", forward, ">", "in_f"]))
                commands.append(_shell_join(["zcat", reverse, ">", "in_r"]))
            elif input_ext.endswith("bz2"):
                commands.append(_shell_join(["bzcat", forward, ">", "in_f"]))
                commands.append(_shell_join(["bzcat", reverse, ">", "in_r"]))
            else:
                commands.append(_shell_join(["ln", "-s", forward, "in_f"]))
                commands.append(_shell_join(["ln", "-s", reverse, "in_r"]))
            file_arg = "-1 in_f -2 in_r" if str(inputs.get("subsample_mode", "no")) == "paired" else "in_f,in_r"
        return commands, file_arg.split(), cls._input_ext(inputs), raw_selector

    @classmethod
    def _database_setup(cls, inputs: dict[str, Any]) -> tuple[list[str], list[str]]:
        if str(inputs.get("db_selector", "cached")) != "history":
            return [], [
                "--db_dir",
                str(inputs.get("bt2_db", "")),
                "--index",
                str(inputs.get("index", "mpa_vJun23_CHOCOPhlAnSGB_202403")),
            ]

        setup = [
            _shell_join(["mkdir", "ref_db"]),
            shlex.join(["bowtie2-build", "--large-index", str(inputs.get("custom_marker_sequences", "")), "ref_db/custom_db"]),
            shlex.join(
                [
                    "python",
                    cls._customizemetadata_script(inputs),
                    "transform_json_to_pkl",
                    "--json",
                    str(inputs.get("custom_marker_metadata", "")),
                    "--pkl",
                    "ref_db/custom_db.pkl",
                ]
            ),
        ]
        return setup, ["--db_dir", "ref_db/", "--index", "custom_db"]

    @classmethod
    def _analysis_args(cls, inputs: dict[str, Any]) -> list[str]:
        analysis_type = str(inputs.get("analysis_type", "rel_ab"))
        args = ["-t", analysis_type]
        if analysis_type in {"rel_ab", "rel_ab_w_read_stats"}:
            args.extend(["--tax_lev", str(inputs.get("tax_lev", "a"))])
        elif analysis_type == "marker_ab_table" and inputs.get("nreads") not in {None, ""}:
            args.extend(["--nreads", str(inputs.get("nreads"))])
        elif analysis_type == "marker_pres_table" and inputs.get("pres_th") not in {None, ""}:
            args.extend(["--pres_th", str(inputs.get("pres_th"))])
        if inputs.get("min_alignment_len") not in {None, ""}:
            args.extend(["--min_alignment_len", str(inputs.get("min_alignment_len"))])
        for option in _as_list(inputs.get("organism_profiling")):
            args.append(f"--{option}")
        args.extend(
            [
                "--stat",
                str(inputs.get("stat", "tavg_g")),
                "--stat_q",
                str(inputs.get("stat_q", 0.2)),
                "--perc_nonzero",
                str(inputs.get("perc_nonzero", 0.33)),
            ]
        )
        if inputs.get("ignore_markers"):
            args.extend(["--ignore_markers", str(inputs.get("ignore_markers"))])
        if bool(inputs.get("avoid_disqm", True)):
            args.append("--avoid_disqm")
        return args

    @classmethod
    def _output_args(cls, inputs: dict[str, Any], out: str) -> list[str]:
        output_file = cls._biom_path(out) if inputs.get("biom_format_output", False) else cls._profile_path(out)
        args = [
            "--sample_id_key",
            str(inputs.get("sample_id_key", "SampleID")),
            "--sample_id",
            str(inputs.get("sample_id", "Metaphlan_Analysis")),
        ]
        if inputs.get("use_group_representative", False):
            args.append("--use_group_representative")
        if inputs.get("CAMI_format_output", False):
            args.append("--CAMI_format_output")
        if inputs.get("skip_unclassified_estimation", False):
            args.append("--skip_unclassified_estimation")
        args.extend(["-o", output_file, "--mapout", "mapout", "-s", cls._sam_path(out), "--nproc", str(inputs.get("threads", 8))])
        return args

    @classmethod
    def _subsampling_args(cls, inputs: dict[str, Any]) -> list[str]:
        mode = str(inputs.get("subsample_mode", "no"))
        args: list[str] = []
        if mode == "single":
            args.extend(["--subsampling", str(inputs.get("subsampling", ""))])
        elif mode == "paired":
            args.extend(["--subsampling_paired", str(inputs.get("subsampling_paired", ""))])
        if mode != "no":
            if inputs.get("mapping_subsampling", False):
                args.append("--mapping_subsampling")
            if inputs.get("subsampling_seed") not in {None, ""}:
                args.extend(["--subsampling_seed", str(inputs.get("subsampling_seed"))])
            args.extend(["--subsampling_output", "subsampled.out"])
        return args

    @classmethod
    def _postprocessing_commands(cls, inputs: dict[str, Any], out: str, raw_input: bool) -> list[str]:
        commands: list[str] = []
        if raw_input:
            commands.append(_shell_join(["mv", "mapout", cls._mapout_path(out)]))
        if (
            str(inputs.get("analysis_type", "rel_ab")) in {"rel_ab", "rel_ab_w_read_stats"}
            and str(inputs.get("tax_lev", "a")) == "a"
            and inputs.get("split_levels", False)
        ):
            commands.extend(
                [
                    _shell_join(["mkdir", "split_levels"]),
                    shlex.join(
                        [
                            "python",
                            cls._formatoutput_script(inputs),
                            "split_levels",
                            "--metaphlan_output",
                            cls._profile_path(out),
                            "--outdir",
                            "split_levels",
                        ]
                    ),
                    _shell_join(["mv", "split_levels", cls._split_levels_path(out)]),
                ]
            )
        if inputs.get("krona_output", False):
            commands.append(
                shlex.join(
                    [
                        "python",
                        cls._formatoutput_script(inputs),
                        "format_for_krona",
                        "--metaphlan_output",
                        cls._profile_path(out),
                        "--krona_output",
                        cls._krona_path(out),
                    ]
                )
            )
        return commands

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        reads = _as_list(inputs.get("reads"))
        selector = cls._input_selector(inputs)
        raw_selector = cls._raw_selector(inputs, reads)
        if not reads:
            return "Required input 'reads' is missing"
        if selector == "raw" and raw_selector in {"paired", "paired_collection"} and len(reads) < 2:
            return "Paired MetaPhlAn input requires two read files"
        if str(inputs.get("db_selector", "cached")) == "history":
            if not inputs.get("custom_marker_sequences"):
                return "custom_marker_sequences is required when db_selector is history"
            if not inputs.get("custom_marker_metadata"):
                return "custom_marker_metadata is required when db_selector is history"
        elif not inputs.get("bt2_db"):
            return "bt2_db is required when db_selector is cached"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = cls._out(inputs)
        reads = _as_list(inputs.get("reads"))
        selector = cls._input_selector(inputs)
        setup_commands: list[str] = []
        file_tokens: list[str]
        input_type: str
        if selector == "raw":
            raw_setup, file_tokens, input_type, _raw_selector = cls._prepare_raw_input(inputs, reads)
            setup_commands.extend(raw_setup)
        else:
            read = reads[0] if reads else ""
            input_type = selector
            file_tokens = [read]

        db_setup, db_args = cls._database_setup(inputs)
        setup_commands.extend(db_setup)
        cmd = ["metaphlan", *file_tokens, "--input_type", input_type]
        if selector == "raw":
            cmd.extend(
                [
                    "--read_min_len",
                    str(inputs.get("read_min_len", 70)),
                    "--bt2_ps",
                    str(inputs.get("bt2_ps", "very-sensitive")),
                    "--min_mapq_val",
                    str(inputs.get("min_mapq_val", 5)),
                ]
            )
        elif selector == "sam":
            cmd.extend(["--nreads", f"$(cat {shlex.quote(file_tokens[0])} | grep -c -v '^@')"])
        cmd.extend(db_args)
        if inputs.get("profile_vsc", False):
            cmd.extend(["--profile_vsc", "--vsc_out", cls._vsc_path(out), "--vsc_breadth", str(inputs.get("vsc_breadth", 0.75))])
        cmd.extend(cls._analysis_args(inputs))
        cmd.extend(cls._output_args(inputs, out))
        cmd.extend(cls._subsampling_args(inputs))
        if inputs.get("offline", False):
            cmd.append("--offline")

        commands = [*setup_commands, _shell_join_allow_substitution(cmd)]
        commands.extend(cls._postprocessing_commands(inputs, out, selector == "raw"))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "profile.metaphlan.tsv"]
        if cls._input_selector(inputs) == "raw":
            outputs.extend([out / "mapout.tsv", out / "sam_output.sam"])
        if inputs.get("biom_format_output", False):
            outputs.append(out / "biom_output.biom")
        if (
            str(inputs.get("analysis_type", "rel_ab")) in {"rel_ab", "rel_ab_w_read_stats"}
            and str(inputs.get("tax_lev", "a")) == "a"
            and inputs.get("split_levels", False)
        ):
            outputs.append(out / "split_levels")
        if inputs.get("krona_output", False):
            outputs.append(out / "krona_output.tsv")
        if inputs.get("profile_vsc", False):
            outputs.append(out / "vsc_breadth_coverage.tsv")
        if str(inputs.get("subsample_mode", "no")) == "single":
            outputs.append(out / "subsampled.fastq")
        if str(inputs.get("subsample_mode", "no")) == "paired":
            outputs.append(out / "subsampled_paired_reads")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ_LIST", {"description": "Metagenomic reads (single or paired-end)"}),
                "bt2_db": ("DIRECTORY", {"description": "MetaPhlAn Bowtie2 database directory"}),
                "index": ("STRING", {"default": "mpa_vJun23_CHOCOPhlAnSGB_202403"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "input_selector": (
                    "STRING",
                    {"default": "raw", "options": ["raw", "sam", "mapout"], "description": "Raw reads, SAM, or MetaPhlAn mapout input"},
                ),
                "raw_selector": (
                    "STRING",
                    {
                        "default": "single",
                        "options": ["single", "multiple", "paired", "paired_collection"],
                        "description": "Raw input layout",
                    },
                ),
                "input_type": ("STRING", {"default": "fastq", "options": ["fastq", "fasta", "sam", "mapout"], "advanced": True}),
                "input_ext": ("STRING", {"default": "fastq", "description": "Original raw input extension, including .gz or .bz2 when compressed"}),
                "paired": ("BOOLEAN", {"default": False, "label": "Paired-end reads", "advanced": True}),
                "db_selector": ("STRING", {"default": "cached", "options": ["cached", "history"], "description": "Use cached database or custom history files"}),
                "custom_marker_sequences": ("FASTA", {"default": "", "description": "Custom marker FASTA for history database mode"}),
                "custom_marker_metadata": ("JSON", {"default": "", "description": "Custom marker metadata JSON for history database mode"}),
                "customizemetadata_script": ("FILE", {"default": "customizemetadata.py", "advanced": True}),
                "formatoutput_script": ("FILE", {"default": "formatoutput.py", "advanced": True}),
                "read_min_len": ("INT", {"default": 70, "min": 1, "description": "Minimum read length for raw input"}),
                "bt2_ps": (
                    "STRING",
                    {
                        "default": "very-sensitive",
                        "options": ["sensitive", "very-sensitive", "sensitive-local", "very-sensitive-local"],
                        "description": "BowTie2 preset for raw FASTA input",
                    },
                ),
                "min_mapq_val": ("INT", {"default": 5, "min": 0, "description": "Minimum MAPQ value"}),
                "profile_vsc": ("BOOLEAN", {"default": False, "description": "Profile viruses with VSCs"}),
                "vsc_breadth": ("FLOAT", {"default": 0.75, "min": 0, "max": 1, "description": "Minimum VSC breadth of coverage"}),
                "analysis_type": (
                    "STRING",
                    {
                        "default": "rel_ab",
                        "options": ["rel_ab", "rel_ab_w_read_stats", "clade_profiles", "marker_ab_table", "marker_pres_table"],
                        "label": "Analysis Type",
                    },
                ),
                "tax_lev": (
                    "STRING",
                    {"default": "a", "options": ["a", "k", "p", "c", "o", "f", "g", "s"], "label": "Taxonomic Level"},
                ),
                "split_levels": ("BOOLEAN", {"default": False, "description": "Generate one report per taxonomic level"}),
                "nreads": ("INT", {"default": "", "description": "Original read count for marker abundance normalization"}),
                "pres_th": ("INT", {"default": "", "description": "Presence threshold for marker_pres_table"}),
                "min_alignment_len": ("INT", {"default": "", "description": "Discard alignments below this length"}),
                "organism_profiling": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "options": ["ignore_eukaryotes", "ignore_bacteria", "ignore_archaea", "ignore_ksgbs", "ignore_usgbs"],
                        "description": "Organism groups to ignore",
                    },
                ),
                "stat": (
                    "STRING",
                    {
                        "default": "tavg_g",
                        "options": ["avg_g", "avg_l", "tavg_g", "tavg_l", "wavg_g", "wavg_l", "med"],
                        "description": "Marker aggregation statistic",
                    },
                ),
                "stat_q": ("FLOAT", {"default": 0.2, "description": "Quantile for robust statistics"}),
                "perc_nonzero": ("FLOAT", {"default": 0.33, "description": "Minimum nonzero marker fraction"}),
                "ignore_markers": ("TEXT", {"default": "", "description": "File containing markers to ignore"}),
                "avoid_disqm": ("BOOLEAN", {"default": True, "description": "Deactivate disambiguation of quasi-markers"}),
                "subsample_mode": ("STRING", {"default": "no", "options": ["no", "single", "paired"], "description": "Optional subsampling mode"}),
                "subsampling": ("INT", {"default": "", "min": 1, "description": "Number of reads for single-end subsampling"}),
                "subsampling_paired": ("INT", {"default": "", "min": 1, "description": "Number of paired reads for paired subsampling"}),
                "mapping_subsampling": ("BOOLEAN", {"default": False, "description": "Subsample mapping results instead of reads"}),
                "subsampling_seed": ("INT", {"default": "", "min": 0, "description": "Subsampling seed"}),
                "sample_id_key": ("STRING", {"default": "SampleID", "description": "Sample ID metadata key"}),
                "sample_id": ("STRING", {"default": "Metaphlan_Analysis", "description": "Sample ID value"}),
                "use_group_representative": ("BOOLEAN", {"default": False, "description": "Use species as representative for species groups"}),
                "CAMI_format_output": ("BOOLEAN", {"default": False, "description": "Report using CAMI format"}),
                "skip_unclassified_estimation": ("BOOLEAN", {"default": False, "description": "Do not estimate unclassified taxa"}),
                "biom_format_output": ("BOOLEAN", {"default": False, "description": "Write BIOM output"}),
                "krona_output": ("BOOLEAN", {"default": False, "description": "Write Krona-compatible output"}),
                "offline": ("BOOLEAN", {"default": True, "description": "Run without downloading reference data"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class HUMAnNNode(CommandNode):
    """Functional profiling with HUMAnN."""

    NODE_ID = "humann"
    DISPLAY_NAME = "HUMAnN"
    REQUIRED_CONDA_PACKAGES = ["humann"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Profile microbial pathway and gene-family abundance with HUMAnN 3."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "HUMAnN",
        "functional profiling",
        "pathway abundance",
        "gene families",
        "ChocoPhlAn",
        "UniRef",
        "intermediate output files",
    ]
    RETURN_TYPES = (
        "HUMANN_OUTPUT",
        "TSV",
        "TSV",
        "TSV",
        "BIOM",
        "BIOM",
        "BIOM",
        "TXT",
        "TSV",
        "TSV",
        "SAM",
        "TSV",
        "FASTA",
        "FASTA",
        "TSV",
        "FASTA",
    )
    RETURN_NAMES = (
        "output_dir",
        "genefamilies",
        "pathabundance",
        "pathcoverage",
        "genefamilies_biom",
        "pathabundance_biom",
        "pathcoverage_biom",
        "log",
        "metaphlan_bowtie2",
        "metaphlan_bugs_list",
        "bowtie2_alignment",
        "bowtie2_reduced_alignment",
        "bowtie2_unaligned",
        "custom_chocophlan_database",
        "diamond_aligned",
        "diamond_unaligned",
    )
    REQUIRED_EXECUTABLES = ["humann"]
    DOCUMENTATION_URL = "https://huttenhower.sph.harvard.edu/humann/"
    CITATION_DOIS = HUMANN_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HUMANN_CITATION_DOIS]
    CITATION_TEXT = HUMANN_CITATION_TEXT
    VERSION = "3.9"
    SHELL = True

    _WORKFLOWS_WITH_PRESCREEN = {"none", "bypass_translated_search"}
    _WORKFLOWS_WITH_NUCLEOTIDE = {
        "none",
        "bypass_prescreen",
        "bypass_taxonomic_profiling",
        "bypass_nucleotide_index",
        "bypass_translated_search",
    }
    _WORKFLOWS_WITH_TRANSLATED = {
        "none",
        "bypass_prescreen",
        "bypass_taxonomic_profiling",
        "bypass_nucleotide_index",
        "bypass_nucleotide_search",
    }

    @classmethod
    def _out(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("output", "."))

    @classmethod
    def _output_basename(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("output_basename", "humann") or "humann")

    @classmethod
    def _output_dir_path(cls, out: str) -> str:
        return f"{out}/output"

    @classmethod
    def _log_path(cls, out: str) -> str:
        return f"{out}/humann.log"

    @classmethod
    def _customizemetadata_script(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("customizemetadata_script", "customizemetadata.py"))

    @classmethod
    def _first_read(cls, reads: Any) -> str:
        if isinstance(reads, (list, tuple)) and reads:
            return str(reads[0])
        return str(reads or "")

    @classmethod
    def _input_format(cls, inputs: dict[str, Any]) -> str:
        input_selector = str(inputs.get("input_selector", "raw"))
        input_ext = str(inputs.get("input_ext", "")).lower()
        read = cls._first_read(inputs.get("reads", inputs.get("input", ""))).lower()
        probe = input_ext or read
        if input_selector == "abundance":
            return "biom" if "biom" in probe else "genetable"
        if input_selector == "mapping":
            return "bam" if probe.endswith("bam") else "sam"
        if probe.endswith(("fastq.gz", "fq.gz")):
            return "fastq.gz"
        if probe.endswith(("fasta.gz", "fa.gz", "fna.gz")):
            return "fasta.gz"
        if probe.endswith(("fasta", "fa", "fna")):
            return "fasta"
        return "fastq"

    @classmethod
    def _safe_humann_label(cls, value: str) -> str:
        return "".join(char if char.isalnum() or char in {"_", "-", "."} else "_" for char in value)

    @classmethod
    def _nucleotide_labels(cls, inputs: dict[str, Any], files: list[str]) -> list[str]:
        names = _as_list(inputs.get("nucleotide_database_names"))
        if len(names) == len(files):
            return [cls._safe_humann_label(name) for name in names]
        labels: list[str] = []
        for file in files:
            name = Path(file).name
            for suffix in (".fasta.gz", ".fa.gz", ".ffn.gz", ".fasta", ".fa", ".ffn", ".gz"):
                if name.lower().endswith(suffix):
                    name = name[: -len(suffix)]
                    break
            labels.append(cls._safe_humann_label(name))
        return labels

    @classmethod
    def _prepare_prescreen(cls, inputs: dict[str, Any]) -> tuple[list[str], list[str]]:
        if str(inputs.get("metaphlan_db_selector", "cached")) == "history":
            setup = [
                _shell_join(["mkdir", "metaphlan_db"]),
                shlex.join(
                    [
                        "bowtie2-build",
                        "--large-index",
                        str(inputs.get("metaphlan_bowtie2db", "")),
                        "metaphlan_db/custom_db-v30",
                    ]
                ),
                shlex.join(
                    [
                        "python",
                        cls._customizemetadata_script(inputs),
                        "transform_json_to_pkl",
                        "--json",
                        str(inputs.get("metaphlan_mpa_pkl", "")),
                        "--pkl",
                        "metaphlan_db/custom_db-v30.pkl",
                    ]
                ),
            ]
            metaphlan_option = "-t rel_ab --bowtie2db metaphlan_db/ --index custom_db-v30"
        else:
            db_path = str(inputs.get("metaphlan_db", inputs.get("metaphlan_cached_db", "")))
            db_index = str(inputs.get("metaphlan_index", inputs.get("metaphlan_dbkey", "")))
            metaphlan_option = f"-t rel_ab --bowtie2db {db_path}"
            if db_index:
                metaphlan_option += f" --index {db_index}"
            setup = []
        args = ["--metaphlan-options", metaphlan_option, "--prescreen-threshold", str(inputs.get("prescreen_threshold", 0.01))]
        return setup, args

    @classmethod
    def _prepare_nucleotide(cls, inputs: dict[str, Any]) -> tuple[list[str], list[str]]:
        if str(inputs.get("nucleotide_db_selector", "cached")) == "history":
            files = _as_list(inputs.get("nucleotide_database"))
            labels = cls._nucleotide_labels(inputs, files)
            setup = [_shell_join(["mkdir", "nucleotide_db"])]
            setup.extend(
                shlex.join(["ln", "-s", file, f"nucleotide_db/{label}.v201901_v31"])
                for file, label in zip(files, labels, strict=False)
            )
            db_path = "nucleotide_db"
        else:
            db_path = str(inputs.get("nuc_db", inputs.get("nucleotide_database", "")))
            setup = []
        args = [
            "--nucleotide-database",
            db_path,
            "--nucleotide-identity-threshold",
            str(inputs.get("nucleotide_identity_threshold", 0)),
            "--nucleotide-subject-coverage-threshold",
            str(inputs.get("nucleotide_subject_coverage_threshold", 50)),
            "--nucleotide-query-coverage-threshold",
            str(inputs.get("nucleotide_query_coverage_threshold", 90)),
        ]
        return setup, args

    @classmethod
    def _search_mode(cls, inputs: dict[str, Any], database: str) -> str:
        if inputs.get("search_mode"):
            return str(inputs["search_mode"])
        return "uniref50" if "uniref50" in database.lower() else "uniref90"

    @classmethod
    def _prepare_translated(cls, inputs: dict[str, Any]) -> tuple[list[str], list[str]]:
        setup: list[str] = []
        if str(inputs.get("protein_db_selector", "cached")) == "history":
            protein_database = str(inputs.get("protein_database", ""))
            setup = [
                _shell_join(["mkdir", "protein_db"]),
                shlex.join(
                    [
                        "diamond",
                        "makedb",
                        "--in",
                        protein_database,
                        "--db",
                        "protein_db/protein-db-201901b",
                        "--threads",
                        str(inputs.get("threads", 4)),
                    ]
                ),
            ]
            db_path = "protein_db"
        else:
            db_path = str(inputs.get("prot_db", inputs.get("protein_database", "")))

        args = [
            "--translated-alignment",
            str(inputs.get("translated_alignment", "diamond")),
            "--protein-database",
            db_path,
            "--search-mode",
            cls._search_mode(inputs, db_path),
            "--evalue",
            str(inputs.get("evalue", 1)),
        ]
        if inputs.get("translated_identity_threshold") not in (None, ""):
            args.extend(["--identity-threshold", str(inputs["translated_identity_threshold"])])
        args.extend(
            [
                "--translated-subject-coverage-threshold",
                str(inputs.get("translated_subject_coverage_threshold", 50)),
                "--translated-query-coverage-threshold",
                str(inputs.get("translated_query_coverage_threshold", 90)),
            ]
        )
        return setup, args

    @classmethod
    def _boolean_on_off(cls, inputs: dict[str, Any], name: str, default: bool) -> str:
        return "on" if bool(inputs.get(name, default)) else "off"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        reads = cls._first_read(inputs.get("reads", inputs.get("input", "")))
        workflow = str(inputs.get("workflow_selector", "none"))
        input_selector = str(inputs.get("input_selector", "raw"))
        out = cls._out(inputs)
        setup_commands: list[str] = []
        workflow_args: list[str] = []

        if input_selector != "abundance":
            if workflow == "bypass_prescreen":
                workflow_args.append("--bypass-prescreen")
            elif workflow == "bypass_taxonomic_profiling":
                workflow_args.extend(["--taxonomic-profile", str(inputs.get("taxonomic_profile", ""))])
            elif workflow == "bypass_nucleotide_index":
                workflow_args.append("--bypass-nucleotide-index")
            elif workflow == "bypass_nucleotide_search":
                workflow_args.append("--bypass-nucleotide-search")
            elif workflow == "bypass_translated_search":
                workflow_args.append("--bypass-translated-search")

            if workflow in cls._WORKFLOWS_WITH_PRESCREEN:
                setup, args = cls._prepare_prescreen(inputs)
                setup_commands.extend(setup)
                workflow_args.extend(args)
            if workflow in cls._WORKFLOWS_WITH_NUCLEOTIDE:
                setup, args = cls._prepare_nucleotide(inputs)
                setup_commands.extend(setup)
                workflow_args.extend(args)
            if workflow in cls._WORKFLOWS_WITH_TRANSLATED:
                setup, args = cls._prepare_translated(inputs)
                setup_commands.extend(setup)
                workflow_args.extend(args)

        cmd = [
            "humann",
            "--input",
            reads,
            "--input-format",
            cls._input_format(inputs),
            "-o",
            cls._output_dir_path(out),
        ]
        cmd.extend(workflow_args)
        cmd.extend(
            [
                "--gap-fill",
                cls._boolean_on_off(inputs, "gap_fill", True),
                "--minpath",
                cls._boolean_on_off(inputs, "minpath", True),
                "--pathways",
                str(inputs.get("pathways", "metacyc")),
                "--xipe",
                cls._boolean_on_off(inputs, "xipe", False),
                "--annotation-gene-index",
                str(inputs.get("annotation_gene_index", 3)),
            ]
        )
        if inputs.get("id_mapping"):
            cmd.extend(["--id-mapping", str(inputs["id_mapping"])])
        cmd.extend(
            [
                "--log-level",
                "DEBUG",
                "--o-log",
                cls._log_path(out),
                "--output-basename",
                cls._output_basename(inputs),
                "--output-format",
                str(inputs.get("output_format", "tsv")),
                "--output-max-decimals",
                str(inputs.get("output_max_decimals", 10)),
            ]
        )
        if inputs.get("remove_column_description_output"):
            cmd.append("--remove-column-description-output")
        if inputs.get("remove_stratified_output"):
            cmd.append("--remove-stratified-output")
        cmd.extend(["--threads", str(inputs.get("threads", 8)), "--memory-use", str(inputs.get("memory_use", "minimum"))])
        return " && ".join([*setup_commands, _shell_join(cmd)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        output_path = node_out / "output"
        output_path.mkdir(parents=True, exist_ok=True)
        basename = cls._output_basename(inputs)
        output_format = str(inputs.get("output_format", "tsv"))
        suffix = "biom" if output_format == "biom" else "tsv"
        abundance_input = str(inputs.get("input_selector", "raw")) == "abundance"
        outputs = [output_path]
        if not abundance_input:
            outputs.append(output_path / f"{basename}_genefamilies.{suffix}")
        outputs.extend(
            [
                output_path / f"{basename}_pathabundance.{suffix}",
                output_path / f"{basename}_pathcoverage.{suffix}",
                node_out / "humann.log",
            ]
        )

        temp_dir = output_path / f"{basename}_temp"
        intermediate_outputs = {
            "metaphlan_bowtie2": temp_dir / f"{basename}_metaphlan_bowtie2.txt",
            "metaphlan_bugs_list": temp_dir / f"{basename}_metaphlan_bugs_list.tsv",
            "bowtie2_alignment": temp_dir / f"{basename}_bowtie2_aligned.sam",
            "bowtie2_reduced_alignment": temp_dir / f"{basename}_bowtie2_aligned.tsv",
            "bowtie2_unaligned": temp_dir / f"{basename}_bowtie2_unaligned.fa",
            "custom_chocophlan_database": temp_dir / f"{basename}_custom_chocophlan_database.ffn",
            "diamond_aligned": temp_dir / f"{basename}_diamond_aligned.tsv",
            "diamond_unaligned": temp_dir / f"{basename}_diamond_unaligned.fa",
        }
        for name in _as_list(inputs.get("intermediate_temp")):
            if name in intermediate_outputs:
                outputs.append(intermediate_outputs[name])
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        reads = cls._first_read(inputs.get("reads", inputs.get("input", "")))
        if not reads:
            return "reads is required"
        workflow = str(inputs.get("workflow_selector", "none"))
        input_selector = str(inputs.get("input_selector", "raw"))
        if input_selector == "abundance":
            return True

        if workflow in cls._WORKFLOWS_WITH_PRESCREEN and str(inputs.get("metaphlan_db_selector", "cached")) == "history":
            if not inputs.get("metaphlan_bowtie2db"):
                return "metaphlan_bowtie2db is required when metaphlan_db_selector is history"
            if not inputs.get("metaphlan_mpa_pkl"):
                return "metaphlan_mpa_pkl is required when metaphlan_db_selector is history"

        if workflow in cls._WORKFLOWS_WITH_NUCLEOTIDE:
            if str(inputs.get("nucleotide_db_selector", "cached")) == "history":
                if not _as_list(inputs.get("nucleotide_database")):
                    return "nucleotide_database is required when nucleotide_db_selector is history"
            elif not inputs.get("nuc_db") and not inputs.get("nucleotide_database"):
                return "nuc_db is required when nucleotide_db_selector is cached"

        if workflow in cls._WORKFLOWS_WITH_TRANSLATED:
            if str(inputs.get("protein_db_selector", "cached")) == "history":
                if not inputs.get("protein_database"):
                    return "protein_database is required when protein_db_selector is history"
            elif not inputs.get("prot_db") and not inputs.get("protein_database"):
                return "prot_db is required when protein_db_selector is cached"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FILE", {"description": "Raw reads, precomputed mappings, or abundance table"}),
                "nuc_db": ("DIRECTORY", {"description": "Cached ChocoPhlAn nucleotide database"}),
                "prot_db": ("DIRECTORY", {"description": "Cached UniRef protein database"}),
            },
            "optional": {
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
                "input_selector": (
                    "STRING",
                    {"default": "raw", "options": ["raw", "mapping", "abundance"], "description": "Galaxy input mode"},
                ),
                "input_ext": ("STRING", {"default": "fastq", "description": "Input extension used to set HUMAnN input format"}),
                "workflow_selector": (
                    "STRING",
                    {
                        "default": "none",
                        "options": [
                            "none",
                            "bypass_prescreen",
                            "bypass_taxonomic_profiling",
                            "bypass_nucleotide_index",
                            "bypass_nucleotide_search",
                            "bypass_translated_search",
                        ],
                        "description": "Galaxy HUMAnN workflow step selection",
                    },
                ),
                "taxonomic_profile": ("TSV", {"default": "", "description": "Taxonomic profile for bypass_taxonomic_profiling"}),
                "metaphlan_db_selector": ("STRING", {"default": "cached", "options": ["cached", "history"]}),
                "metaphlan_db": ("DIRECTORY", {"default": "", "description": "Cached MetaPhlAn marker database"}),
                "metaphlan_index": ("STRING", {"default": "", "description": "Cached MetaPhlAn index/dbkey"}),
                "metaphlan_bowtie2db": ("FASTA", {"default": "", "description": "History MetaPhlAn marker FASTA"}),
                "metaphlan_mpa_pkl": ("JSON", {"default": "", "description": "History MetaPhlAn marker metadata JSON"}),
                "prescreen_threshold": ("FLOAT", {"default": 0.01, "min": 0, "max": 100}),
                "nucleotide_db_selector": ("STRING", {"default": "cached", "options": ["cached", "history"]}),
                "nucleotide_database": ("FASTA", {"default": [], "multiple": True, "description": "History ChocoPhlAn pangenome FASTA files"}),
                "nucleotide_database_names": (
                    "STRING",
                    {"default": [], "multiple": True, "description": "Element identifiers for history nucleotide databases"},
                ),
                "nucleotide_identity_threshold": ("FLOAT", {"default": 0, "min": 0, "max": 100}),
                "nucleotide_subject_coverage_threshold": ("FLOAT", {"default": 50, "min": 0, "max": 100}),
                "nucleotide_query_coverage_threshold": ("FLOAT", {"default": 90, "min": 0, "max": 100}),
                "protein_db_selector": ("STRING", {"default": "cached", "options": ["cached", "history"]}),
                "protein_database": ("FASTA", {"default": "", "description": "History UniRef protein FASTA"}),
                "search_mode": ("STRING", {"default": "", "options": ["", "uniref50", "uniref90"]}),
                "evalue": ("FLOAT", {"default": 1}),
                "translated_identity_threshold": ("FLOAT", {"default": ""}),
                "translated_subject_coverage_threshold": ("FLOAT", {"default": 50, "min": 0, "max": 100}),
                "translated_query_coverage_threshold": ("FLOAT", {"default": 90, "min": 0, "max": 100}),
                "gap_fill": ("BOOLEAN", {"default": True}),
                "minpath": ("BOOLEAN", {"default": True}),
                "pathways": ("STRING", {"default": "metacyc", "options": ["metacyc", "unipathway"]}),
                "xipe": ("BOOLEAN", {"default": False}),
                "annotation_gene_index": ("INT", {"default": 3}),
                "id_mapping": ("TSV", {"default": ""}),
                "output_basename": ("STRING", {"default": "humann"}),
                "output_format": ("STRING", {"default": "tsv", "options": ["tsv", "biom"]}),
                "output_max_decimals": ("INT", {"default": 10}),
                "remove_column_description_output": ("BOOLEAN", {"default": False}),
                "remove_stratified_output": ("BOOLEAN", {"default": False}),
                "intermediate_temp": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "options": [
                            "metaphlan_bowtie2",
                            "metaphlan_bugs_list",
                            "bowtie2_alignment",
                            "bowtie2_reduced_alignment",
                            "bowtie2_unaligned",
                            "custom_chocophlan_database",
                            "diamond_aligned",
                            "diamond_unaligned",
                        ],
                        "description": "Intermediate output files",
                    },
                ),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class MaxBinNode(CommandNode):
    """Metagenomic binning with MaxBin."""
    NODE_ID = "maxbin"
    DISPLAY_NAME = "MaxBin2"
    CATEGORY = "metagenomics"
    DESCRIPTION = "Unsupervised metagenomic binning using expectation maximization"
    SEARCH_ALIASES = ["maxbin", "binning", "metagenome", "mags"]
    RETURN_TYPES = ("BINS",)
    RETURN_NAMES = ("bins",)
    REQUIRED_EXECUTABLES = ["run_MaxBin.pl"]
    REQUIRED_CONDA_PACKAGES = ['maxbin2']
    DOCUMENTATION_URL = "https://sourceforge.net/projects/maxbin/"
    VERSION = "2.2.7"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "run_MaxBin.pl",
            "-contig", str(inputs.get("contigs", "")),
            "-out", f"{inputs.get('output', '.')}/bins.out",
            "-reads", str(inputs.get("reads", "")),
            "-thread", str(inputs.get("threads", 8)),
        ]
        if inputs.get("abund"):
            cmd.extend(["-abund", str(inputs["abund"])])
        if inputs.get("min_prob") is not None:
            cmd.extend(["-min_prob", str(inputs["min_prob"])])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "contigs": ("CONTIGS", {"description": "Metagenomic contigs FASTA"}),
                "reads": ("FASTQ", {"description": "Metagenomic reads FASTQ"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "abund": ("FILE", {"description": "Optional abundance file"}),
                "min_prob": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class CheckMNode(CommandNode):
    """Assess metagenomic bin quality with CheckM."""
    NODE_ID = "checkm"
    DISPLAY_NAME = "CheckM"
    CATEGORY = "metagenomics"
    DESCRIPTION = "Assess the quality of microbial genomes recovered from metagenomes"
    SEARCH_ALIASES = ["checkm", "bin quality", "completeness", "contamination"]
    RETURN_TYPES = ("STATS_FILE",)
    RETURN_NAMES = ("quality_report",)
    REQUIRED_EXECUTABLES = ["checkm"]
    REQUIRED_CONDA_PACKAGES = ['checkm-genome']
    DOCUMENTATION_URL = "https://github.com/Ecogenomics/CheckM"
    VERSION = "1.2.5"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        step = inputs.get("step", "lineage_wf")
        cmd = ["checkm", step]
        if step == "lineage_wf":
            cmd.extend([
                "-x", str(inputs.get("extension", "fa")),
                "-t", str(inputs.get("threads", 8)),
            ])
            if inputs.get("pplacer_threads"):
                cmd.extend(["--pplacer_threads", str(inputs["pplacer_threads"])])
            if inputs.get("reduced_tree"):
                cmd.append("--reduced_tree")
            cmd.extend([str(inputs.get("bins", "")), f"{inputs.get('output', '.')}/bins.out"])
        elif step == "qa":
            cmd.extend([
                "-o", str(inputs.get("qa_output", "1")),
                "-f", f"{inputs.get('output', '.')}/qa_output.out",
            ])
            cmd.extend([str(inputs.get("markers_file", "")), str(inputs.get("output", "."))])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bins": ("BINS", {"description": "Directory with MAG bins (.fa files)"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
                "step": (["lineage_wf", "qa"], {"default": "lineage_wf"}),
            },
            "optional": {
                "extension": ("STRING", {"default": "fa", "label": "File Extension"}),
                "pplacer_threads": ("INT", {"default": 1, "min": 1, "max": 64, "label": "pplacer Threads", "advanced": True}),
                "reduced_tree": ("BOOLEAN", {"default": False, "label": "Reduced Tree", "advanced": True}),
                "markers_file": ("FILE", {"description": "Marker file for qa step", "label": "Markers File", "advanced": True}),
                "qa_output": ("STRING", {"default": "1", "label": "QA Output Format", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
