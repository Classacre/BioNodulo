"""Salmon 2.3.4 transcript indexing and quantification nodes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from bionodulo.nodes.command_node import CommandNode


def _path_list(value: Any, name: str) -> list[str]:
    if isinstance(value, (str, os.PathLike)):
        values = [value]
    elif isinstance(value, (list, tuple)):
        values = list(value)
    else:
        raise TypeError(f"{name} must be a path or ordered path collection")

    paths: list[str] = []
    for item in values:
        try:
            path = os.fsdecode(os.fspath(item))
        except TypeError as exc:
            raise TypeError(f"each {name} entry must be path-like") from exc
        if not path.strip():
            raise ValueError(f"{name} paths must be non-empty")
        paths.append(path)
    if not paths:
        raise ValueError(f"{name} must contain at least one path")
    return paths


def _validate_threads(inputs: dict[str, Any], default: int) -> bool | str:
    threads = inputs.get("threads", default)
    if isinstance(threads, bool) or not isinstance(threads, int):
        return "threads must be an integer"
    # Salmon's `usize` thread option accepts zero as its documented "all
    # available cores" sentinel; the CLI deliberately has no upper bound.
    if threads < 0:
        return "threads must be zero or a positive integer"
    return True


def _validate_boolean(inputs: dict[str, Any], name: str, default: bool) -> bool | str:
    value = inputs.get(name, default)
    if not isinstance(value, bool):
        return f"{name} must be a boolean"
    return True


def _library_type(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("lib_type must be a string")
    return value.upper()


def _validate_files(paths: list[str], name: str) -> bool | str:
    for value in paths:
        path = Path(value)
        if not path.is_file():
            return f"{name} path is not a materialized file: {value}"
        try:
            if path.stat().st_size == 0:
                return f"{name} file is empty: {value}"
        except OSError as exc:
            return f"cannot inspect {name} file {value}: {exc}"
    return True


def _validate_directory(value: Any, name: str) -> bool | str:
    try:
        path = Path(os.fsdecode(os.fspath(value)))
    except TypeError:
        return f"{name} must be a path-like value"
    if not path.is_dir():
        return f"{name} is not a materialized directory: {path}"
    try:
        if not any(path.iterdir()):
            return f"{name} directory is empty: {path}"
    except OSError as exc:
        return f"cannot inspect {name} directory {path}: {exc}"
    return True


def _validate_salmon_index(value: Any) -> bool | str:
    try:
        index = Path(os.fsdecode(os.fspath(value)))
    except TypeError:
        return "index must be a path-like value"
    if not index.is_dir():
        return f"index is not a materialized directory: {index}"
    info_path = index / SalmonIndexNode.INFO_FILENAME
    if not info_path.is_file():
        return f"index is missing required {SalmonIndexNode.INFO_FILENAME}: {info_path}"
    try:
        if info_path.stat().st_size == 0:
            return f"index {SalmonIndexNode.INFO_FILENAME} is empty: {info_path}"
        info = json.loads(info_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return f"cannot parse index {SalmonIndexNode.INFO_FILENAME}: {exc}"
    if not isinstance(info, dict):
        return f"index {SalmonIndexNode.INFO_FILENAME} must contain a JSON object"

    index_version = info.get("index_version")
    if isinstance(index_version, bool) or not isinstance(index_version, int):
        return f"index {SalmonIndexNode.INFO_FILENAME} must contain an integer index_version"
    if index_version < SalmonIndexNode.MIN_READABLE_INDEX_VERSION:
        return (
            f"index format v{index_version} is too old; Salmon {SalmonIndexNode.VERSION} "
            f"requires v{SalmonIndexNode.MIN_READABLE_INDEX_VERSION}+ and the index must be rebuilt"
        )

    has_ec_table = info.get("has_ec_table")
    if not isinstance(has_ec_table, bool):
        return f"index {SalmonIndexNode.INFO_FILENAME} has a non-boolean has_ec_table"
    required_files = list(SalmonIndexNode.REQUIRED_INDEX_FILES)
    if has_ec_table:
        required_files.append("index.ectab")
    missing: list[str] = []
    empty: list[str] = []
    for relative_path in required_files:
        artifact = index / relative_path
        if not artifact.is_file():
            missing.append(relative_path)
        else:
            try:
                if artifact.stat().st_size == 0:
                    empty.append(relative_path)
            except OSError as exc:
                return f"cannot inspect Salmon index artifact {artifact}: {exc}"
    if missing or empty:
        details: list[str] = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if empty:
            details.append(f"empty: {', '.join(empty)}")
        return f"Salmon index is incomplete ({'; '.join(details)})"
    return True


class _SalmonCommandNode(CommandNode):
    CATEGORY = "rna_seq"
    REQUIRED_EXECUTABLES = ["salmon"]
    REQUIRED_CONDA_PACKAGES = ["salmon"]
    VERSION = "2.3.4"
    CONDA_PACKAGE_CONSTRAINTS = {"salmon": VERSION}
    PACKAGE_CONSTRAINTS = (f"salmon=={VERSION}",)
    PACKAGE_CONSTRAINT = PACKAGE_CONSTRAINTS[0]
    GIT_URL = "https://github.com/COMBINE-lab/salmon.git"
    GIT_COMMIT = "d53fed6f0af6966a40825558f0edf71b6df7cf52"
    UPSTREAM_TAG = "v2.3.4"
    UPSTREAM_CLI_SOURCE = "crates/salmon-cli/src/main.rs"
    UPSTREAM_INDEX_SOURCE = "crates/salmon-index/src/lib.rs"
    UPSTREAM_QUANT_OUTPUT_SOURCE = "crates/salmon-quant/src/output.rs"
    DOCUMENTATION_URL = "https://github.com/COMBINE-lab/salmon/tree/v2.3.4/website/src/content/docs"
    SOURCE_AUTHORITIES = {
        "cli_contract": f"{GIT_URL}/blob/{GIT_COMMIT}/{UPSTREAM_CLI_SOURCE}",
        "index_contract": f"{GIT_URL}/blob/{GIT_COMMIT}/{UPSTREAM_INDEX_SOURCE}",
        "quant_output_contract": (
            f"{GIT_URL}/blob/{GIT_COMMIT}/{UPSTREAM_QUANT_OUTPUT_SOURCE}"
        ),
        "documentation": DOCUMENTATION_URL,
    }
    AUDIT_STATUS = "contract-checked-no-binary-execution"
    EXIT_SEMANTICS = (
        "Input validation or a non-zero Salmon exit fails the node; success requires every "
        "unconditional Salmon index or quant artifact declared by the selected operation."
    )
    SHELL = False


class SalmonIndexNode(_SalmonCommandNode):
    """Build the complete opaque Salmon 2.x index directory."""

    NODE_ID = "salmon_index"
    DISPLAY_NAME = "Salmon Index"
    DESCRIPTION = "Build a Salmon 2.3.4 transcript index"
    SEARCH_ALIASES = ["salmon", "index", "transcriptome", "quant"]
    RETURN_TYPES = ("INDEX_DIR",)
    RETURN_NAMES = ("index",)
    UPSTREAM_SOURCE = "crates/salmon-index/src/lib.rs"
    INDEX_DIRECTORY = "index"
    INFO_FILENAME = "info.json"
    MIN_READABLE_INDEX_VERSION = 1
    REQUIRED_INDEX_FILES = (
        "index.ssi",
        "index.ssi.mphf",
        "index.ctab",
        "index.refinfo",
        "refseq.bin",
        "refseq_offsets.json",
        "duplicate_clusters.tsv",
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "transcripts": (
                    "FASTA",
                    {
                        "multiple": True,
                        "description": "One or more transcript FASTA files",
                    },
                ),
                "threads": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "description": "Worker threads; 0 uses all available cores",
                    },
                ),
            },
            "optional": {
                "kmer": (
                    "INT",
                    {
                        "default": 31,
                        "min": 1,
                        "max": 63,
                        "description": "Odd k-mer length; Salmon default is 31",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / cls.INDEX_DIRECTORY]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        try:
            transcripts = _path_list(inputs.get("transcripts"), "transcripts")
        except (TypeError, ValueError) as exc:
            return str(exc)
        validation = _validate_files(transcripts, "transcripts")
        if validation is not True:
            return validation
        validation = _validate_threads(inputs, 0)
        if validation is not True:
            return validation
        kmer = inputs.get("kmer", 31)
        if isinstance(kmer, bool) or not isinstance(kmer, int):
            return "kmer must be an integer"
        if not 1 <= kmer <= 63 or kmer % 2 == 0:
            return "kmer must be odd and between 1 and 63"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        return [
            "salmon",
            "index",
            "-t",
            *_path_list(inputs.get("transcripts"), "transcripts"),
            "-i",
            str(output / cls.INDEX_DIRECTORY),
            "-p",
            str(inputs.get("threads", 0)),
            "-k",
            str(inputs.get("kmer", 31)),
        ]

    @classmethod
    def reference_cache_id(cls, inputs: dict[str, Any]) -> Optional[str]:
        from bionodulo.execution import reference_cache as _rc

        transcripts = _path_list(inputs.get("transcripts"), "transcripts")
        return _rc.compute_ref_id(
            "salmon",
            [
                *(_rc.file_identity(path) for path in transcripts),
                f"salmon-{cls.VERSION}",
                f"k{inputs.get('kmer', 31)}",
            ],
        )

    async def run(self, **kwargs: Any) -> Any:
        result = await super().run(**kwargs)
        validation = _validate_salmon_index(result[0])
        if validation is not True:
            raise RuntimeError(f"Salmon index output is invalid: {validation}")
        return result


class SalmonQuantNode(_SalmonCommandNode):
    """Quantify single-end or paired-end reads with Salmon 2.3.4."""

    NODE_ID = "salmon_quant"
    DISPLAY_NAME = "Salmon Quant"
    DESCRIPTION = "Estimate transcript abundance with Salmon 2.3.4"
    SEARCH_ALIASES = ["salmon", "quant", "expression", "tpm", "counts"]
    RETURN_TYPES = ("COUNTS", "DIRECTORY")
    RETURN_NAMES = ("counts", "quant_dir")
    UPSTREAM_SOURCE = "crates/salmon-quant/src/output.rs"
    QUANT_FILENAME = "quant.sf"
    REQUIRED_QUANT_FILES = (
        "quant.sf",
        "cmd_info.json",
        "lib_format_counts.json",
        "aux_info/meta_info.json",
        "aux_info/ambig_info.tsv",
        "aux_info/fld.gz",
        "aux_info/observed_bias.gz",
        "aux_info/observed_bias_3p.gz",
        "aux_info/expected_bias.gz",
        "libParams/flenDist.txt",
        "logs/salmon_quant.log",
    )
    LIBRARY_TYPES = (
        "A",
        "IU",
        "ISF",
        "ISR",
        "OU",
        "OSF",
        "OSR",
        "MU",
        "MSF",
        "MSR",
        "U",
        "SF",
        "SR",
    )
    PAIRED_LIBRARY_TYPES = {"A", "IU", "ISF", "ISR", "OU", "OSF", "OSR", "MU", "MSF", "MSR"}
    SINGLE_LIBRARY_TYPES = {"A", "U", "SF", "SR"}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "index": ("INDEX_DIR", {"description": "Salmon 2.x index directory"}),
                "threads": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "description": "Worker threads; 0 uses all available cores",
                    },
                ),
            },
            "optional": {
                "reads": (
                    "FASTQ_LIST",
                    {
                        "description": "Single reads or ordered pairs [R1, R2, ...]",
                    },
                ),
                "r1": ("FASTQ", {"multiple": True, "description": "Mate-1 FASTQ file(s)"}),
                "r2": ("FASTQ", {"multiple": True, "description": "Mate-2 FASTQ file(s)"}),
                "single_end": (
                    "BOOLEAN",
                    {"default": False, "description": "Treat every supplied read file as single-end"},
                ),
                "lib_type": (
                    "STRING",
                    {
                        "default": "A",
                        "options": list(cls.LIBRARY_TYPES),
                        "label": "Library Type",
                        "advanced": True,
                    },
                ),
                "gc_bias": (
                    "BOOLEAN",
                    {"default": False, "label": "GC Bias Correction", "advanced": True},
                ),
                "seq_bias": (
                    "BOOLEAN",
                    {"default": False, "label": "Seq Bias Correction", "advanced": True},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _read_mode(cls, inputs: dict[str, Any]) -> tuple[str, list[str], list[str]]:
        reads_value = inputs.get("reads")
        has_reads = reads_value not in (None, "", [], ())
        has_aliases = inputs.get("r1") not in (None, "", [], ()) or inputs.get("r2") not in (
            None,
            "",
            [],
            (),
        )
        if has_reads and has_aliases:
            raise ValueError("use reads or r1/r2 aliases, not both")

        single_end = inputs.get("single_end", False)
        if not isinstance(single_end, bool):
            raise ValueError("single_end must be a boolean")
        if has_reads:
            reads = _path_list(reads_value, "reads")
            if single_end or len(reads) == 1:
                return "single", reads, []
            if len(reads) % 2:
                raise ValueError("paired reads must contain an even number of FASTQ paths")
            return "paired", reads[0::2], reads[1::2]

        mate1 = _path_list(inputs.get("r1"), "r1") if inputs.get("r1") not in (None, "", [], ()) else []
        mate2 = _path_list(inputs.get("r2"), "r2") if inputs.get("r2") not in (None, "", [], ()) else []
        if single_end or (mate1 and not mate2 and len(mate1) == 1):
            if mate2:
                raise ValueError("r2 cannot be supplied in single-end mode")
            if not mate1:
                raise ValueError("single-end mode requires at least one read file")
            return "single", mate1, []
        if not mate1 or not mate2:
            raise ValueError("paired mode requires both r1 and r2")
        if len(mate1) != len(mate2):
            raise ValueError("r1 and r2 must contain the same number of files")
        return "paired", mate1, mate2

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        quant_dir = Path(output_dir) / cls.NODE_ID
        quant_dir.mkdir(parents=True, exist_ok=True)
        return [quant_dir / cls.QUANT_FILENAME, quant_dir]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        index = inputs.get("index")
        if not isinstance(index, (str, os.PathLike)) or not os.fsdecode(os.fspath(index)).strip():
            return "index must be a non-empty path"
        validation = _validate_salmon_index(index)
        if validation is not True:
            return validation
        validation = _validate_threads(inputs, 0)
        if validation is not True:
            return validation
        for name in ("single_end", "gc_bias", "seq_bias"):
            validation = _validate_boolean(inputs, name, False)
            if validation is not True:
                return validation
        try:
            mode, first_reads, second_reads = cls._read_mode(inputs)
        except (TypeError, ValueError) as exc:
            return str(exc)
        validation = _validate_files([*first_reads, *second_reads], "reads")
        if validation is not True:
            return validation
        try:
            lib_type = _library_type(inputs.get("lib_type", "A"))
        except ValueError as exc:
            return str(exc)
        if lib_type not in cls.LIBRARY_TYPES:
            return f"lib_type must be one of: {', '.join(cls.LIBRARY_TYPES)}"
        allowed = cls.SINGLE_LIBRARY_TYPES if mode == "single" else cls.PAIRED_LIBRARY_TYPES
        if lib_type not in allowed:
            return f"lib_type {lib_type} is not valid for {mode}-end reads"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        mode, first_reads, second_reads = cls._read_mode(inputs)
        output = str(inputs.get("output", inputs.get("output_dir", ".")))
        lib_type = _library_type(inputs.get("lib_type", "A"))
        command = [
            "salmon",
            "quant",
            "-i",
            str(inputs.get("index", "")),
            "-l",
            lib_type,
            "-o",
            output,
            "-p",
            str(inputs.get("threads", 0)),
        ]
        if mode == "single":
            command.extend(["-r", *first_reads])
        else:
            command.extend(["-1", *first_reads, "-2", *second_reads])
        if inputs.get("gc_bias", False) is True:
            command.append("--gcBias")
        if inputs.get("seq_bias", False) is True:
            command.append("--seqBias")
        return command

    async def run(self, **kwargs: Any) -> Any:
        result = await super().run(**kwargs)
        quant_dir = Path(result[1])
        missing: list[str] = []
        empty: list[str] = []
        for relative_path in self.REQUIRED_QUANT_FILES:
            path = quant_dir / relative_path
            if not path.is_file():
                missing.append(relative_path)
            elif path.stat().st_size == 0:
                empty.append(relative_path)
        if missing or empty:
            details: list[str] = []
            if missing:
                details.append(f"missing: {', '.join(missing)}")
            if empty:
                details.append(f"empty: {', '.join(empty)}")
            raise RuntimeError(f"Salmon quant output is incomplete ({'; '.join(details)})")
        return result
