"""Metagenomics analysis nodes for BioNodulo.

Provides nodes for taxonomic classification (Kraken2, Bracken, MetaPhlAn),
functional profiling (HUMAnN), binning (MaxBin), and quality assessment (CheckM).
"""
from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode, _shell_join


DOI_URL = "https://doi.org/"
METAPHLAN_DOI = "10.1038/s41587-023-01688-w"
METAPHLAN_CITATION_TEXT = (
    "Extending and improving metagenomic taxonomic profiling with uncharacterized species using MetaPhlAn 4."
)


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
    REQUIRED_CONDA_PACKAGES = ['kraken2']
    CATEGORY = "metagenomics"
    DESCRIPTION = "Ultra-fast taxonomic classification of metagenomic reads"
    SEARCH_ALIASES = ["kraken2", "classify", "taxonomy", "metagenomics"]
    RETURN_TYPES = ("KRAKEN_OUTPUT", "KRAKEN_REPORT")
    RETURN_NAMES = ("output", "report")
    REQUIRED_EXECUTABLES = ["kraken2"]
    DOCUMENTATION_URL = "https://ccb.jhu.edu/software/kraken2/"
    VERSION = "2.1.3"
    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "kraken2",
            "--db", str(inputs.get("db", "")),
            "--output", f"{inputs.get('output', '.')}/output.kraken",
            "--report", f"{inputs.get('output', '.')}/report.kreport",
            "--threads", str(inputs.get("threads", 8)),
        ]
        reads = inputs.get("reads", [])
        if isinstance(reads, str):
            reads = [reads]
        r1 = reads[0] if len(reads) > 0 else inputs.get("r1", "")
        r2 = reads[1] if len(reads) > 1 else inputs.get("r2", "")
        if r1 and r2:
            cmd.append("--paired")
            cmd.extend([str(r1), str(r2)])
        elif r1:
            cmd.append(str(r1))
        if inputs.get("confidence"):
            cmd.extend(["--confidence", str(inputs["confidence"])])
        if inputs.get("minimum_hit_groups") is not None:
            cmd.extend(["--minimum-hit-groups", str(inputs["minimum_hit_groups"])])
        if inputs.get("memory_mapping"):
            cmd.append("--memory-mapping")
        return cmd

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
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "reads": ("FASTQ_LIST", {"description": "Paired-end FASTQ reads [R1, R2]"}),
                "r1": ("FASTQ", {"description": "Forward reads (R1)"}),
                "r2": ("FASTQ", {"description": "Reverse reads (R2)"}),
                "confidence": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01, "label": "Confidence", "advanced": True}),
                "minimum_hit_groups": ("INT", {"default": 2, "label": "Min Hit Groups", "advanced": True}),
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
    REQUIRED_CONDA_PACKAGES = ['bracken']
    CATEGORY = "metagenomics"
    DESCRIPTION = "Bayesian Re-estimation of Abundance after classification with Kraken"
    SEARCH_ALIASES = ["bracken", "abundance", "kraken", "metagenomics"]
    RETURN_TYPES = ("KRAKEN_REPORT",)
    RETURN_NAMES = ("report",)
    REQUIRED_EXECUTABLES = ["bracken"]
    DOCUMENTATION_URL = "https://ccb.jhu.edu/software/bracken/"
    VERSION = "3.1"
    COMMAND = [
        "bracken",
        "-d", "{inputs.db}",
        "-i", "{inputs.report}",
        "-o", "{output}/report.kreport",
        "-r", "{inputs.read_length}",
        "-l", "{inputs.level}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "report": ("KRAKEN_REPORT", {"description": "Kraken2 report file"}),
                "db": ("DIRECTORY", {"description": "Kraken2 database directory"}),
                "read_length": ("STRING", {"default": "100", "description": "Read length (35, 50, 75, 100, 150, 200, 250, 300)"}),
                "level": ("STRING", {"default": "S", "description": "Taxonomic level: D, P, C, O, F, G, S"}),
            },
            "optional": {},
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
        "Galaxy",
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
    REQUIRED_CONDA_PACKAGES = ['humann']
    CATEGORY = "metagenomics"
    DESCRIPTION = "Functional profiling of microbial communities"
    SEARCH_ALIASES = ["humann", "functional", "pathway", "gene family"]
    RETURN_TYPES = ("HUMANN_OUTPUT", "TSV", "TSV", "TSV")
    RETURN_NAMES = ("output_dir", "genefamilies", "pathabundance", "pathcoverage")
    REQUIRED_EXECUTABLES = ["humann"]
    DOCUMENTATION_URL = "https://huttenhower.sph.harvard.edu/humann/"
    VERSION = "3.8"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        reads = inputs.get("reads", "")
        if isinstance(reads, list) and reads:
            reads = reads[0]
        cmd = [
            "humann",
            "--input", str(reads),
            "--output", f"{inputs.get('output', '.')}/output_dir.out",
            "--threads", str(inputs.get("threads", 8)),
        ]
        if inputs.get("nuc_db"):
            cmd.extend(["--nucleotide-database", str(inputs["nuc_db"])])
        if inputs.get("prot_db"):
            cmd.extend(["--protein-database", str(inputs["prot_db"])])
        if inputs.get("bypass_nucleotide_search"):
            cmd.append("--bypass-nucleotide-search")
        if inputs.get("bypass_translated_search"):
            cmd.append("--bypass-translated-search")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        output_path = node_out / "output_dir.out"
        output_path.mkdir(parents=True, exist_ok=True)
        stem = cls._read_stem(inputs.get("reads", "sample"))
        return [
            output_path,
            output_path / f"{stem}_genefamilies.tsv",
            output_path / f"{stem}_pathabundance.tsv",
            output_path / f"{stem}_pathcoverage.tsv",
        ]

    @staticmethod
    def _read_stem(reads: Any) -> str:
        if isinstance(reads, (list, tuple)) and reads:
            reads = reads[0]
        name = Path(str(reads or "sample")).name
        for suffix in (".fastq.gz", ".fq.gz", ".fastq", ".fq", ".fasta.gz", ".fa.gz", ".fasta", ".fa"):
            if name.lower().endswith(suffix):
                name = name[: -len(suffix)]
                break
        return name or "sample"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ_LIST", {"description": "Quality-controlled metagenomic reads"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "nuc_db": ("DIRECTORY", {"description": "ChocoPhlAn nucleotide database"}),
                "prot_db": ("DIRECTORY", {"description": "UniRef protein database"}),
                "bypass_nucleotide_search": ("BOOLEAN", {"default": False, "label": "Bypass Nucleotide Search", "advanced": True}),
                "bypass_translated_search": ("BOOLEAN", {"default": False, "label": "Bypass Translated Search", "advanced": True}),
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
