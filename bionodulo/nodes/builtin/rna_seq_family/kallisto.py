"""Kallisto 0.52.0 transcript indexing and quantification nodes."""

from __future__ import annotations

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


def _validate_threads(inputs: dict[str, Any], default: int = 1) -> bool | str:
    threads = inputs.get("threads", default)
    if isinstance(threads, bool) or not isinstance(threads, int):
        return "threads must be an integer"
    if not 1 <= threads <= 64:
        return "threads must be between 1 and 64"
    return True


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


class _KallistoCommandNode(CommandNode):
    CATEGORY = "rna_seq"
    REQUIRED_EXECUTABLES = ["kallisto"]
    REQUIRED_CONDA_PACKAGES = ["kallisto"]
    VERSION = "0.52.0"
    GIT_URL = "https://github.com/pachterlab/kallisto.git"
    GIT_COMMIT = "4e9f29cf3b021260415430c057a22469ca081391"
    UPSTREAM_TAG = "v0.52.0"
    UPSTREAM_CLI_SOURCE = "src/main.cpp"
    DOCUMENTATION_URL = "https://github.com/pachterlab/kallisto/tree/v0.52.0"
    SHELL = False


class KallistoIndexNode(_KallistoCommandNode):
    """Build Kallisto's single binary transcript index file."""

    NODE_ID = "kallisto_index"
    DISPLAY_NAME = "Kallisto Index"
    DESCRIPTION = "Build a Kallisto 0.52.0 transcript index"
    SEARCH_ALIASES = ["kallisto", "index", "transcriptome", "pseudoalign"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("index",)
    INDEX_FILENAME = "transcripts.idx"

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
                    {"default": 1, "min": 1, "max": 64, "display": "slider"},
                ),
            },
            "optional": {
                "kmer": (
                    "INT",
                    {
                        "default": 31,
                        "min": 3,
                        "max": 31,
                        "description": "Odd k-mer length; Kallisto default is 31",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / cls.INDEX_FILENAME]

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
        validation = _validate_threads(inputs)
        if validation is not True:
            return validation
        kmer = inputs.get("kmer", 31)
        if isinstance(kmer, bool) or not isinstance(kmer, int):
            return "kmer must be an integer"
        if not 3 <= kmer <= 31 or kmer % 2 == 0:
            return "kmer must be odd and between 3 and 31"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        return [
            "kallisto",
            "index",
            "-i",
            str(output / cls.INDEX_FILENAME),
            "-k",
            str(inputs.get("kmer", 31)),
            "-t",
            str(inputs.get("threads", 1)),
            *_path_list(inputs.get("transcripts"), "transcripts"),
        ]

    @classmethod
    def reference_cache_id(cls, inputs: dict[str, Any]) -> Optional[str]:
        from bionodulo.execution import reference_cache as _rc

        transcripts = _path_list(inputs.get("transcripts"), "transcripts")
        return _rc.compute_ref_id(
            "kallisto",
            [
                *(_rc.file_identity(path) for path in transcripts),
                f"kallisto-{cls.VERSION}",
                f"k{inputs.get('kmer', 31)}",
            ],
        )

    async def run(self, **kwargs: Any) -> Any:
        result = await super().run(**kwargs)
        index = Path(result[0])
        if not index.is_file() or index.stat().st_size == 0:
            raise RuntimeError(f"Kallisto index output is missing or empty: {index}")
        return result


class KallistoQuantNode(_KallistoCommandNode):
    """Quantify single-end or paired-end reads with Kallisto."""

    NODE_ID = "kallisto_quant"
    DISPLAY_NAME = "Kallisto Quant"
    DESCRIPTION = "Estimate transcript abundance with Kallisto 0.52.0"
    SEARCH_ALIASES = ["kallisto", "quant", "expression", "pseudoalign"]
    RETURN_TYPES = ("ABUNDANCE", "TXT")
    RETURN_NAMES = ("abundance", "report")
    STDERR_OUTPUT_INDEX = 1
    ABUNDANCE_FILENAME = "abundance.tsv"
    RUN_INFO_FILENAME = "run_info.json"
    HDF5_FILENAME = "abundance.h5"
    REPORT_FILENAME = "kallisto.stderr.log"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "index": ("FILE", {"description": "Kallisto binary index file"}),
                "threads": (
                    "INT",
                    {"default": 1, "min": 1, "max": 64, "display": "slider"},
                ),
            },
            "optional": {
                "reads": (
                    "FASTQ_LIST",
                    {"description": "Single reads or ordered pairs [R1, R2, ...]"},
                ),
                "r1": ("FASTQ", {"multiple": True, "description": "Mate-1 FASTQ file(s)"}),
                "r2": ("FASTQ", {"multiple": True, "description": "Mate-2 FASTQ file(s)"}),
                "bootstrap": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 1000,
                        "step": 10,
                        "display": "slider",
                    },
                ),
                "single_end": (
                    "BOOLEAN",
                    {"default": False, "label": "Single-end reads", "advanced": True},
                ),
                "fragment_length": (
                    "FLOAT",
                    {
                        "default": None,
                        "min": 0.0,
                        "label": "Fragment Length",
                        "advanced": True,
                    },
                ),
                "sd": (
                    "FLOAT",
                    {
                        "default": None,
                        "min": 0.0,
                        "label": "Fragment SD",
                        "advanced": True,
                    },
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

        single_end = bool(inputs.get("single_end", False))
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
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / cls.ABUNDANCE_FILENAME, node_out / cls.REPORT_FILENAME]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        index = inputs.get("index")
        if not isinstance(index, (str, os.PathLike)) or not os.fsdecode(os.fspath(index)).strip():
            return "index must be a non-empty path"
        validation = _validate_files([os.fsdecode(os.fspath(index))], "index")
        if validation is not True:
            return validation
        validation = _validate_threads(inputs)
        if validation is not True:
            return validation
        bootstrap = inputs.get("bootstrap", 0)
        if isinstance(bootstrap, bool) or not isinstance(bootstrap, int):
            return "bootstrap must be an integer"
        if bootstrap < 0:
            return "bootstrap must be zero or greater"
        try:
            mode, first_reads, second_reads = cls._read_mode(inputs)
        except (TypeError, ValueError) as exc:
            return str(exc)
        validation = _validate_files([*first_reads, *second_reads], "reads")
        if validation is not True:
            return validation

        fragment_length = inputs.get("fragment_length")
        sd = inputs.get("sd")
        if (fragment_length is None) != (sd is None):
            return "fragment_length and sd must be supplied together"
        for name, value in (("fragment_length", fragment_length), ("sd", sd)):
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return f"{name} must be a number"
            if value <= 0:
                return f"{name} must be greater than zero"
        if mode == "single" and fragment_length is None:
            return "single-end mode requires fragment_length and sd"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        mode, first_reads, second_reads = cls._read_mode(inputs)
        output = str(inputs.get("output", inputs.get("output_dir", ".")))
        command = [
            "kallisto",
            "quant",
            "-i",
            str(inputs.get("index", "")),
            "-o",
            output,
            "-t",
            str(inputs.get("threads", 1)),
        ]
        bootstrap = inputs.get("bootstrap", 0)
        if bootstrap:
            command.extend(["-b", str(bootstrap)])
        if mode == "single":
            command.extend(
                [
                    "--single",
                    "-l",
                    str(inputs.get("fragment_length")),
                    "-s",
                    str(inputs.get("sd")),
                    *first_reads,
                ]
            )
        else:
            paired_reads = [path for pair in zip(first_reads, second_reads) for path in pair]
            command.extend(paired_reads)
        return command

    async def run(self, **kwargs: Any) -> Any:
        result = await super().run(**kwargs)
        output_dir = Path(result[0]).parent
        required = {
            self.ABUNDANCE_FILENAME: output_dir / self.ABUNDANCE_FILENAME,
            self.RUN_INFO_FILENAME: output_dir / self.RUN_INFO_FILENAME,
            self.REPORT_FILENAME: output_dir / self.REPORT_FILENAME,
        }
        invalid = [name for name, path in required.items() if not path.is_file() or path.stat().st_size == 0]
        hdf5 = output_dir / self.HDF5_FILENAME
        if hdf5.exists() and (not hdf5.is_file() or hdf5.stat().st_size == 0):
            invalid.append(self.HDF5_FILENAME)
        if invalid:
            raise RuntimeError(f"Kallisto quant output is missing or empty: {', '.join(invalid)}")
        return result
