"""Kraken2 2.17.1 taxonomic classification."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import (
    MetagenomicsCommandNode,
    add_flag,
    path_list,
    path_value,
    validate_int,
    validate_number,
)


class Kraken2Node(MetagenomicsCommandNode):
    """Classify one or more sequence files against one explicit Kraken2 database."""

    NODE_ID = "kraken2"
    DISPLAY_NAME = "Kraken2"
    DESCRIPTION = "Classify metagenomic reads and write native Kraken2 classification and report files."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "Kraken2",
        "taxonomic classification",
        "Kraken report",
    ]
    RETURN_TYPES = ("KRAKEN_OUTPUT", "KRAKEN_REPORT")
    RETURN_NAMES = ("classification", "report")
    REQUIRED_EXECUTABLES = ["kraken2"]
    REQUIRED_CONDA_PACKAGES = ["kraken2"]
    VERSION = "2.17.1"
    BIOCONDA_VERSION = VERSION
    BIOCONDA_CONSTRAINT = "kraken2=2.17.1"
    BIOCONDA_PACKAGE_URL = "https://anaconda.org/bioconda/kraken2/files?version=2.17.1"
    GIT_URL = "https://github.com/DerrickWood/kraken2.git"
    GIT_COMMIT = "5e2aa928d00b96d61f204d517437637863da1d8c"
    UPSTREAM_TAG = "v2.17.1"
    UPSTREAM_SOURCE = "scripts/kraken2; src/classify.cc; docs/MANUAL.markdown"
    SOURCE_PATHS = ("scripts/kraken2", "src/classify.cc", "docs/MANUAL.markdown")
    SOURCE_REVISION = GIT_COMMIT
    SOURCE_URL = f"{GIT_URL}/blob/{GIT_COMMIT}"
    AUDIT_STATUS = "contract-checked-no-binary-execution"
    DATABASE_FILES = ("hash.k2d", "opts.k2d", "taxo.k2d")
    SIDECAR_POLICY = (
        "The materialized database directory must contain hash.k2d, opts.k2d, "
        "and taxo.k2d; compressed reads require the native gzip/bzip2 switch."
    )
    DOCUMENTATION_URL = (
        "https://github.com/DerrickWood/kraken2/blob/5e2aa928d00b96d61f204d517437637863da1d8c/docs/MANUAL.markdown"
    )
    CITATION_DOIS = ["10.1186/s13059-019-1891-0"]
    CITATION_URLS = ["https://doi.org/10.1186/s13059-019-1891-0"]
    CITATION_TEXT = "Improved metagenomic analysis with Kraken 2."
    OUTPUT_FILENAMES = ("classification.kraken", "report.kreport")
    COMPRESSION_OPTIONS = ("auto", "none", "gzip", "bzip2")
    REQUIRED_PATH_INPUTS = ("db",)
    REQUIRED_PATH_LIST_INPUTS = ("reads",)
    EXIT_SEMANTICS = (
        "The wrapper rejects missing database files, invalid pairing, and invalid thresholds; "
        "the classifier exit code is propagated and BioNodulo also requires both planned outputs."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "db": ("DIRECTORY", {"description": "Kraken2 database containing hash.k2d, opts.k2d, and taxo.k2d"}),
                "reads": (
                    "FASTQ_LIST",
                    {"description": "One or more FASTA/FASTQ files; paired mode requires a positive even count"},
                ),
            },
            "optional": {
                "threads": ("INT", {"default": 1, "min": 1}),
                "paired": ("BOOLEAN", {"default": False}),
                "quick": ("BOOLEAN", {"default": False}),
                "confidence": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0}),
                "minimum_base_quality": ("INT", {"default": 0, "min": 0}),
                "minimum_hit_groups": ("INT", {"default": 2, "min": 0}),
                "use_names": ("BOOLEAN", {"default": False}),
                "memory_mapping": ("BOOLEAN", {"default": False}),
                "compression": (
                    "STRING",
                    {
                        "default": "auto",
                        "options": list(cls.COMPRESSION_OPTIONS),
                        "description": "Compression flag for compressed FASTA/FASTQ inputs",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        reads = path_list(inputs.get("reads"))
        if inputs.get("paired", False) and len(reads) % 2:
            return "Paired Kraken2 input requires a positive even number of read files"
        compression = str(inputs.get("compression", "auto"))
        if compression not in cls.COMPRESSION_OPTIONS:
            return f"Input 'compression' must be one of: {', '.join(cls.COMPRESSION_OPTIONS)}"
        if compression == "auto":
            suffixes = {
                ".gz" if path.lower().endswith((".gz", ".gzip")) else ".bz2"
                if path.lower().endswith((".bz2", ".bzip2"))
                else ""
                for path in reads
            }
            if len(suffixes - {""}) > 1 or (suffixes - {""} and "" in suffixes):
                return "Input 'reads' mixes compressed and uncompressed files; set compression explicitly"
        elif compression == "gzip" and any(
            path.lower().endswith((".bz2", ".bzip2")) for path in reads
        ):
            return "compression=gzip cannot be used with bzip2 inputs"
        elif compression == "bzip2" and any(
            path.lower().endswith((".gz", ".gzip")) for path in reads
        ):
            return "compression=bzip2 cannot be used with gzip inputs"
        for key, default, minimum in (
            ("threads", 1, 1),
            ("minimum_base_quality", 0, 0),
            ("minimum_hit_groups", 2, 0),
        ):
            validation = validate_int(inputs.get(key, default), key, minimum=minimum)
            if validation is not True:
                return validation
        return validate_number(inputs.get("confidence", 0.0), "confidence", minimum=0.0, maximum=1.0)

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        """Validate the native database bundle once it is materialized."""

        database = Path(path_value(inputs.get("db")))
        if not database.exists():
            return
        if not database.is_dir():
            raise ValueError(f"Kraken2 database must be a directory: {database}")
        missing = [name for name in cls.DATABASE_FILES if not (database / name).is_file()]
        if missing:
            raise ValueError(
                "Kraken2 database is missing required sidecar(s): "
                + ", ".join(missing)
            )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = cls.output_dir(inputs)
        command = cls.checked_command(
            inputs,
            "kraken2",
            "--db",
            path_value(inputs.get("db")),
            "--threads",
            str(inputs.get("threads", 1)),
        )
        add_flag(command, "--quick", inputs.get("quick"))
        command.extend(
            [
                "--confidence",
                str(inputs.get("confidence", 0.0)),
                "--minimum-base-quality",
                str(inputs.get("minimum_base_quality", 0)),
                "--minimum-hit-groups",
                str(inputs.get("minimum_hit_groups", 2)),
            ]
        )
        add_flag(command, "--use-names", inputs.get("use_names"))
        add_flag(command, "--memory-mapping", inputs.get("memory_mapping"))
        add_flag(command, "--paired", inputs.get("paired"))
        compression = str(inputs.get("compression", "auto"))
        if compression == "auto":
            reads = path_list(inputs.get("reads"))
            suffixes = {
                "gzip"
                if path.lower().endswith((".gz", ".gzip"))
                else "bzip2"
                if path.lower().endswith((".bz2", ".bzip2"))
                else "none"
                for path in reads
            }
            if suffixes == {"gzip"}:
                compression = "gzip"
            elif suffixes == {"bzip2"}:
                compression = "bzip2"
            else:
                compression = "none"
        if compression != "none":
            command.append(f"--{compression}-compressed")
        command.extend(
            [
                "--output",
                str(output / cls.OUTPUT_FILENAMES[0]),
                "--report",
                str(output / cls.OUTPUT_FILENAMES[1]),
                *path_list(inputs.get("reads")),
            ]
        )
        return command
