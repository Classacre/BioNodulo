"""MetaPhlAn 4.2.4 taxonomic profiling."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.builtin.metagenomics_family.adapter import (
    MetagenomicsCommandNode,
    add_flag,
    path_list,
    path_value,
    validate_choice,
    validate_int,
    validate_number,
)


class MetaPhlAnNode(MetagenomicsCommandNode):
    """Profile raw FASTA/FASTQ reads with one explicit marker database release."""

    NODE_ID = "metaphlan"
    DISPLAY_NAME = "MetaPhlAn"
    DESCRIPTION = "Profile microbial taxa from raw reads with an explicit MetaPhlAn marker database."
    SEARCH_ALIASES = ["BioNodulo builtin", "MetaPhlAn 4", "taxonomic profiling", "marker genes"]
    RETURN_TYPES = ("METAPHLAN_PROFILE", "FILE")
    RETURN_NAMES = ("profile", "mapout")
    REQUIRED_EXECUTABLES = ["metaphlan"]
    REQUIRED_CONDA_PACKAGES = ["metaphlan"]
    VERSION = "4.2.4"
    BIOCONDA_VERSION = VERSION
    BIOCONDA_CONSTRAINT = "metaphlan=4.2.4"
    BIOCONDA_PACKAGE_URL = "https://anaconda.org/bioconda/metaphlan/files?version=4.2.4"
    GIT_URL = "https://github.com/biobakery/MetaPhlAn.git"
    GIT_COMMIT = "b2293b0d319237c2312e628e5ab2a13095df7e3b"
    UPSTREAM_TAG = "4.2.4"
    UPSTREAM_SOURCE = "metaphlan/metaphlan.py; metaphlan/utils/database_controller.py"
    SOURCE_PATHS = ("metaphlan/metaphlan.py", "metaphlan/utils/database_controller.py")
    SOURCE_REVISION = GIT_COMMIT
    SOURCE_URL = f"{GIT_URL}/blob/{GIT_COMMIT}"
    AUDIT_STATUS = "contract-checked-no-binary-execution"
    DATABASE_INDEX_SUFFIXES = (".1.bt2l", ".2.bt2l", ".3.bt2l", ".4.bt2l", ".rev.1.bt2l", ".rev.2.bt2l")
    SIDECAR_POLICY = (
        "The materialized database must contain the selected index's six Bowtie2 "
        "bt2l members and <index>.pkl; MetaPhlAn otherwise attempts an unavailable "
        "download even when --offline is set."
    )
    DOCUMENTATION_URL = (
        "https://github.com/biobakery/MetaPhlAn/blob/b2293b0d319237c2312e628e5ab2a13095df7e3b/metaphlan/metaphlan.py"
    )
    CITATION_DOIS = ["10.1038/s41587-023-01688-w"]
    CITATION_URLS = ["https://doi.org/10.1038/s41587-023-01688-w"]
    CITATION_TEXT = "Extending and improving metagenomic taxonomic profiling with uncharacterized species."
    OUTPUT_FILENAMES = ("profile.metaphlan.tsv", "mapout.bz2")
    REQUIRED_PATH_INPUTS = ("database",)
    REQUIRED_PATH_LIST_INPUTS = ("reads",)
    INPUT_TYPES_ALLOWED = ("fastq", "fasta")
    ANALYSIS_TYPES = ("rel_ab", "rel_ab_w_read_stats", "clade_profiles", "marker_ab_table", "marker_pres_table")
    TAXONOMIC_LEVELS = ("a", "k", "p", "c", "o", "f", "g", "s", "t")
    STATS = ("avg_g", "avg_l", "tavg_g", "tavg_l", "wavg_g", "wavg_l", "med", "npos_lr", "nreads_lr")
    EXIT_SEMANTICS = (
        "Argument, input, mapping, and database failures call the upstream error helper and exit nonzero; "
        "BioNodulo also requires the profile and mapping outputs."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": (
                    "FASTQ_LIST",
                    {"description": "One or more raw FASTA/FASTQ files; multiple files are passed comma-delimited"},
                ),
                "database": ("DIRECTORY", {"description": "MetaPhlAn database directory"}),
                "index": (
                    "STRING",
                    {
                        "description": "Installed database index name; 'latest' is rejected to prevent implicit downloads"
                    },
                ),
            },
            "optional": {
                "input_type": ("STRING", {"default": "fastq", "options": list(cls.INPUT_TYPES_ALLOWED)}),
                "threads": ("INT", {"default": 4, "min": 1}),
                "read_min_len": ("INT", {"default": 70, "min": 1}),
                "minimum_mapq": ("INT", {"default": None, "min": 0}),
                "minimum_alignment_length": ("INT", {"default": None, "min": 0}),
                "analysis_type": ("STRING", {"default": "rel_ab", "options": list(cls.ANALYSIS_TYPES)}),
                "taxonomic_level": ("STRING", {"default": "a", "options": list(cls.TAXONOMIC_LEVELS)}),
                "stat": ("STRING", {"default": "tavg_g", "options": list(cls.STATS)}),
                "stat_q": ("FLOAT", {"default": 0.2, "min": 0.0, "max": 1.0}),
                "perc_nonzero": ("FLOAT", {"default": 0.33, "min": 0.0, "max": 1.0}),
                "ignore_eukaryotes": ("BOOLEAN", {"default": False}),
                "ignore_bacteria": ("BOOLEAN", {"default": False}),
                "ignore_archaea": ("BOOLEAN", {"default": False}),
                "skip_unclassified_estimation": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        reads = path_list(inputs.get("reads"))
        if any("," in read for read in reads):
            return "MetaPhlAn input paths cannot contain commas because upstream uses commas as file delimiters"
        index = str(inputs.get("index", "")).strip()
        if not index:
            return "Input 'index' must be a non-empty installed database index name"
        if index == "latest":
            return "Input 'index' must name an installed database release; 'latest' can trigger network access"
        for key, value, choices in (
            ("input_type", inputs.get("input_type", "fastq"), cls.INPUT_TYPES_ALLOWED),
            ("analysis_type", inputs.get("analysis_type", "rel_ab"), cls.ANALYSIS_TYPES),
            ("taxonomic_level", inputs.get("taxonomic_level", "a"), cls.TAXONOMIC_LEVELS),
            ("stat", inputs.get("stat", "tavg_g"), cls.STATS),
        ):
            validation = validate_choice(value, key, choices)
            if validation is not True:
                return validation
        for key, default, minimum in (("threads", 4, 1), ("read_min_len", 70, 1)):
            validation = validate_int(inputs.get(key, default), key, minimum=minimum)
            if validation is not True:
                return validation
        for key in ("minimum_mapq", "minimum_alignment_length"):
            if inputs.get(key) is not None:
                validation = validate_int(inputs[key], key, minimum=0)
                if validation is not True:
                    return validation
        for key, default in (("stat_q", 0.2), ("perc_nonzero", 0.33)):
            validation = validate_number(inputs.get(key, default), key, minimum=0.0, maximum=1.0)
            if validation is not True:
                return validation
        return True

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        """Validate the selected MetaPhlAn database bundle once materialized."""

        database = Path(path_value(inputs.get("database")))
        if not database.exists():
            return
        if not database.is_dir():
            raise ValueError(f"MetaPhlAn database must be a directory: {database}")
        index = str(inputs.get("index", "")).strip()
        required = [database / f"{index}{suffix}" for suffix in cls.DATABASE_INDEX_SUFFIXES]
        required.append(database / f"{index}.pkl")
        missing = [path.name for path in required if not path.is_file()]
        if missing:
            raise ValueError("MetaPhlAn database is missing required index sidecar(s): " + ", ".join(missing))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = cls.output_dir(inputs)
        command = cls.checked_command(
            inputs,
            "metaphlan",
            ",".join(path_list(inputs.get("reads"))),
            "--input_type",
            str(inputs.get("input_type", "fastq")),
            "--db_dir",
            path_value(inputs.get("database")),
            "--index",
            str(inputs.get("index", "")),
            "--mapout",
            str(output / cls.OUTPUT_FILENAMES[1]),
            "--nproc",
            str(inputs.get("threads", 4)),
            "--read_min_len",
            str(inputs.get("read_min_len", 70)),
        )
        if inputs.get("minimum_mapq") is not None:
            command.extend(["--min_mapq_val", str(inputs["minimum_mapq"])])
        if inputs.get("minimum_alignment_length") is not None:
            command.extend(["--min_alignment_len", str(inputs["minimum_alignment_length"])])
        analysis_type = str(inputs.get("analysis_type", "rel_ab"))
        command.extend(["-t", analysis_type])
        if analysis_type in {"rel_ab", "rel_ab_w_read_stats"}:
            command.extend(["--tax_lev", str(inputs.get("taxonomic_level", "a"))])
        command.extend(
            [
                "--stat",
                str(inputs.get("stat", "tavg_g")),
                "--stat_q",
                str(inputs.get("stat_q", 0.2)),
                "--perc_nonzero",
                str(inputs.get("perc_nonzero", 0.33)),
            ]
        )
        add_flag(command, "--ignore_eukaryotes", inputs.get("ignore_eukaryotes"))
        add_flag(command, "--ignore_bacteria", inputs.get("ignore_bacteria"))
        add_flag(command, "--ignore_archaea", inputs.get("ignore_archaea"))
        add_flag(command, "--skip_unclassified_estimation", inputs.get("skip_unclassified_estimation"))
        command.extend(["-o", str(output / cls.OUTPUT_FILENAMES[0]), "--offline"])
        return command
