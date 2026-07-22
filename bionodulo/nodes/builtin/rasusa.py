"""Source-pinned Rasusa 4.1.0 read and alignment subsampling."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from bionodulo.nodes.builtin.annotation_family.staging import stage_file
from bionodulo.nodes.command_node import CommandNode


def _path_value(value: Any) -> str | None:
    try:
        path = os.fsdecode(os.fspath(value))
    except TypeError:
        return None
    return path if path.strip() else None


def _path_list(value: Any, *, mapping_keys: tuple[str, ...] = ()) -> list[str]:
    if isinstance(value, dict):
        values = [value.get(key) for key in mapping_keys]
    elif isinstance(value, (str, os.PathLike)):
        values = [value]
    elif isinstance(value, (list, tuple)):
        values = list(value)
    else:
        return []
    paths: list[str] = []
    for item in values:
        path = _path_value(item)
        if path is None:
            return []
        paths.append(path)
    return paths


def _has_value(value: Any) -> bool:
    return value not in (None, "")


def _add_value(command: list[str], flag: str, value: Any) -> None:
    if _has_value(value):
        command.extend([flag, str(value)])


def _selector(inputs: dict[str, Any]) -> str:
    return str(inputs.get("input_selector", "single") or "single")


_COMPRESSION_SUFFIX_TO_TYPE = {
    ".gz": "g",
    ".bz2": "b",
    ".xz": "x",
    ".lzma": "l",
    ".zst": "z",
}
_COMPRESSION_TYPE_TO_SUFFIX = {value: key for key, value in _COMPRESSION_SUFFIX_TO_TYPE.items()}
_COMPRESSION_TYPE_TO_SUFFIX["u"] = ""


def _read_layout(path: str) -> tuple[str | None, str]:
    name = Path(path).name.lower()
    compression = "u"
    for suffix, compression_type in _COMPRESSION_SUFFIX_TO_TYPE.items():
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            compression = compression_type
            break
    if name.endswith((".fasta", ".fa")):
        return "fasta", compression
    if name.endswith((".fastq", ".fq")):
        return "fastq", compression
    return None, compression


def _output_ext(inputs: dict[str, Any], reads: list[str]) -> str:
    explicit = str(inputs.get("output_ext", "") or "").strip().lstrip(".")
    if explicit:
        return explicit
    input_format, input_compression = _read_layout(reads[0]) if reads else (None, "u")
    output_format = str(inputs.get("output_format", "") or "") or input_format or "fastq"
    compression = str(inputs.get("compress_type", "") or "") or input_compression
    return f"{output_format}{_COMPRESSION_TYPE_TO_SUFFIX[compression]}"


def _compression_from_ext(extension: str) -> str:
    for suffix, compression_type in _COMPRESSION_SUFFIX_TO_TYPE.items():
        if extension.endswith(suffix):
            return compression_type
    return "u"


def _size(value: Any, unit: Any) -> str:
    return f"{value}{unit}"


class RasusaNode(CommandNode):
    """Subsample one/two read files or a coordinate-sorted BAM."""

    NODE_ID = "rasusa"
    DISPLAY_NAME = "Rasusa"
    CATEGORY = "qc"
    DESCRIPTION = "Subsample FASTA/FASTQ reads or downsample a sorted BAM, then emit a sorted BAM/BAI pair."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "rasusa",
        "subsample reads",
        "downsample reads",
        "coverage subsampling",
        "alignment downsampling",
    ]
    RETURN_TYPES = ("FILE_LIST", "FILE", "BAM", "BAI")
    RETURN_NAMES = ("paired_reads", "single_reads", "subsampled_bam", "subsampled_bam_index")
    REQUIRED_EXECUTABLES = ["rasusa", "samtools"]
    REQUIRED_CONDA_PACKAGES = ["rasusa", "samtools"]
    PACKAGE_CONSTRAINTS = ("rasusa==4.1.0", "samtools==1.23.1")
    PACKAGE_CONSTRAINT = "; ".join(PACKAGE_CONSTRAINTS)
    VERSION = "4.1.0"
    GIT_URL = "https://github.com/mbhall88/rasusa.git"
    GIT_COMMIT = "59e28930210f1a7dccffb236273c2bddb7b4fedd"
    DOCUMENTATION_URL = "https://github.com/mbhall88/rasusa/tree/4.1.0"
    CITATION_DOIS = ["10.21105/joss.03941", "10.46471/gigabyte.180"]
    CITATION_URLS = ["https://doi.org/10.21105/joss.03941", "https://doi.org/10.46471/gigabyte.180"]
    CITATION_TEXT = (
        "Rasusa: Randomly subsample sequencing reads to a specified coverage; "
        "Efficient downsampling of genome alignments with Rasusa."
    )
    UPSTREAM_READS_SOURCE = "src/reads.rs"
    UPSTREAM_ALIGNMENT_SOURCE = "src/alignment.rs"
    UPSTREAM_CLI_SOURCE = "src/cli.rs"
    UPSTREAM_READS_SOURCE_SHA256 = "d20bc1264bb6f2965a6f8bcf91d31a6bd75471a9d530d88462caee9ddf8f6c9f"
    UPSTREAM_ALIGNMENT_SOURCE_SHA256 = "1090068d7a7af111677abc50ede22defd2a3e00bfce71e4937e60e77114e62eb"
    UPSTREAM_CLI_SOURCE_SHA256 = "029f5be9e68cb90bfb2ab73325c1e3f587bf5117b692adc0e450022a9ee39d93"
    DOCUMENTATION_SOURCE_URL = "https://github.com/mbhall88/rasusa/blob/59e28930210f1a7dccffb236273c2bddb7b4fedd/README.md"
    DOCUMENTATION_SOURCE_SHA256 = "5383409578d8cc26a24616f17722ef2513c1d7dd109bc9391927efc6a980c912"
    EXIT_SEMANTICS = (
        "Rasusa exits non-zero for invalid target combinations, unreadable or malformed reads/alignments, "
        "missing fetch indexes, and output failures; the aligned mode additionally requires successful "
        "Samtools sorting and indexing of the native Rasusa stream."
    )
    AUDIT_STATUS = "contract-checked-no-external-execution"
    SELECTORS = ("single", "paired", "paired_collection", "aligned")
    SUBSAMPLE_TYPES = ("coverage", "num_bases", "num_reads", "frac_reads")
    OUTPUT_EXTENSIONS = (
        "fastq",
        "fastq.gz",
        "fastq.bz2",
        "fastq.xz",
        "fastq.lzma",
        "fastq.zst",
        "fasta",
        "fasta.gz",
        "fasta.bz2",
        "fasta.xz",
        "fasta.lzma",
        "fasta.zst",
    )
    SHELL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_selector": ("STRING", {"default": "single", "options": list(cls.SELECTORS)}),
            },
            "optional": {
                "reads": ("FILE_LIST", {"default": "", "description": "Single read file or ordered pair"}),
                "reads1": ("FILE", {"default": "", "description": "Forward read file"}),
                "reads2": ("FILE", {"default": "", "description": "Reverse read file"}),
                "collection_forward": ("FILE", {"default": ""}),
                "collection_reverse": ("FILE", {"default": ""}),
                "aligned_input": ("BAM", {"default": "", "description": "Coordinate-sorted BAM"}),
                "aligned_input_index": (
                    "BAI",
                    {"default": "", "description": "Exact <aligned_input>.bai required by fetch strategy"},
                ),
                "subsample_type": ("STRING", {"default": "frac_reads", "options": list(cls.SUBSAMPLE_TYPES)}),
                "genome_size": ("FLOAT", {"default": "", "min": 0}),
                "genome_size_unit": ("STRING", {"default": "b", "options": ["b", "k", "m", "g", "t"]}),
                "coverage": ("FLOAT", {"default": "", "min": 0}),
                "bases": ("FLOAT", {"default": "", "min": 0}),
                "num_bases_unit": ("STRING", {"default": "b", "options": ["b", "k", "m", "g", "t"]}),
                "num": ("INT", {"default": "", "min": 1}),
                "frac": ("FLOAT", {"default": 0.1, "min": 0, "max": 100}),
                "seed": ("INT", {"default": "", "min": 0}),
                "strict": ("BOOLEAN", {"default": False}),
                "verbose": ("BOOLEAN", {"default": False}),
                "output_ext": (
                    "STRING",
                    {
                        "default": "",
                        "options": ["", *cls.OUTPUT_EXTENSIONS],
                        "description": "Empty preserves the input FASTA/FASTQ format and compression",
                    },
                ),
                "compress_type": ("STRING", {"default": "", "options": ["", "u", "b", "g", "l", "x", "z"]}),
                "compress_level": ("INT", {"default": "", "min": 1, "max": 21}),
                "output_format": ("STRING", {"default": "", "options": ["", "fasta", "fastq"]}),
                "strategy": ("STRING", {"default": "stream", "options": ["stream", "fetch"]}),
                "swap_distance": ("INT", {"default": 5, "min": 0}),
                "step_size": ("INT", {"default": 100, "min": 1}),
                "batch_size": ("INT", {"default": 10000, "min": 1000}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _reads(cls, inputs: dict[str, Any]) -> list[str]:
        selector = _selector(inputs)
        if selector == "single":
            reads = _path_list(inputs.get("reads"))
            if reads:
                return reads
            return _path_list(inputs.get("reads1"))
        if selector == "paired_collection":
            reads = _path_list(inputs.get("reads"), mapping_keys=("forward", "reverse"))
            if reads:
                return reads
            return _path_list([inputs.get("collection_forward"), inputs.get("collection_reverse")])
        reads = _path_list(inputs.get("reads"))
        if reads:
            return reads
        return _path_list([inputs.get("reads1"), inputs.get("reads2")])

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        selector = _selector(inputs)
        if selector not in cls.SELECTORS:
            return f"input_selector must be one of: {', '.join(cls.SELECTORS)}"
        for name, default, minimum, maximum in (
            ("seed", None, 0, None),
            ("compress_level", None, 1, 21),
            ("swap_distance", 5, 0, None),
            ("step_size", 100, 1, None),
            ("batch_size", 10000, 1000, None),
            ("threads", 1, 1, 64),
        ):
            value = inputs.get(name, default)
            if value in (None, ""):
                continue
            if isinstance(value, bool) or not isinstance(value, int):
                return f"{name} must be an integer"
            if value < minimum:
                return f"{name} must be at least {minimum}"
            if maximum is not None and value > maximum:
                return f"{name} must be at most {maximum}"
        if selector == "aligned":
            aligned = _path_value(inputs.get("aligned_input"))
            if aligned is None:
                return "aligned_input is required for aligned mode"
            coverage = inputs.get("coverage")
            if isinstance(coverage, bool) or not isinstance(coverage, (int, float)) or coverage < 1:
                return "coverage must be at least 1 for aligned mode"
            if float(coverage) != int(coverage):
                return "coverage must be an integer for aligned mode"
            strategy = str(inputs.get("strategy", "stream") or "stream")
            if strategy not in {"stream", "fetch"}:
                return "strategy must be one of: stream, fetch"
            if strategy == "fetch":
                expected = Path(os.path.abspath(os.path.normpath(f"{aligned}.bai")))
                index = _path_value(inputs.get("aligned_input_index"))
                if index is None:
                    return f"aligned_input_index is required for fetch strategy; expected '{expected}'"
                if Path(os.path.abspath(os.path.normpath(index))) != expected:
                    return f"aligned_input_index must be the exact colocated BAI; expected '{expected}'"
            return True
        reads = cls._reads(inputs)
        expected = 2 if selector in {"paired", "paired_collection"} else 1
        if len(reads) != expected:
            return f"{selector} mode requires exactly {expected} read file(s)"
        subsample_type = str(inputs.get("subsample_type", "frac_reads") or "frac_reads")
        if subsample_type not in cls.SUBSAMPLE_TYPES:
            return f"subsample_type must be one of: {', '.join(cls.SUBSAMPLE_TYPES)}"
        if subsample_type == "coverage":
            for name in ("genome_size", "coverage"):
                value = inputs.get(name)
                if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                    return f"{name} must be greater than 0 for coverage subsampling"
        elif subsample_type == "num_bases":
            value = inputs.get("bases")
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                return "bases must be greater than 0 for num_bases subsampling"
        elif subsample_type == "num_reads":
            value = inputs.get("num")
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                return "num must be an integer of at least 1 for num_reads subsampling"
        else:
            value = inputs.get("frac", 0.1)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100:
                return "frac must be at least 0 and at most 100"
        explicit_extension = str(inputs.get("output_ext", "") or "").strip().lstrip(".")
        if explicit_extension and explicit_extension not in cls.OUTPUT_EXTENSIONS:
            return f"output_ext must be one of: {', '.join(cls.OUTPUT_EXTENSIONS)}"
        output_format = str(inputs.get("output_format", "") or "")
        if output_format not in {"", "fasta", "fastq"}:
            return "output_format must be one of: fasta, fastq"
        if output_format and explicit_extension and not explicit_extension.startswith(output_format):
            return "output_format must match output_ext"
        compress_type = str(inputs.get("compress_type", "") or "")
        if compress_type not in {"", "u", "b", "g", "l", "x", "z"}:
            return "compress_type must be one of: u, b, g, l, x, z"
        if explicit_extension and compress_type and _compression_from_ext(explicit_extension) != compress_type:
            return "compress_type must match output_ext compression"
        layouts = [_read_layout(read) for read in reads]
        known_formats = {read_format for read_format, _compression in layouts if read_format is not None}
        if len(known_formats) > 1:
            return "paired read inputs must use the same FASTA or FASTQ format"
        if not explicit_extension and not output_format and not known_formats:
            return "output_ext or output_format is required when the input read format cannot be inferred"
        if not explicit_extension and not compress_type and len({compression for _format, compression in layouts}) > 1:
            return "output_ext or compress_type is required when paired inputs use different compression"
        target_format = output_format
        if not target_format and explicit_extension:
            target_format = "fasta" if explicit_extension.startswith("fasta") else "fastq"
        if not target_format and known_formats:
            target_format = next(iter(known_formats))
        if known_formats == {"fasta"} and target_format == "fastq":
            return "Rasusa cannot create truthful FASTQ output from FASTA input"
        return True

    @classmethod
    def _append_target(cls, command: list[str], inputs: dict[str, Any]) -> None:
        subsample_type = str(inputs.get("subsample_type", "frac_reads") or "frac_reads")
        if subsample_type == "coverage":
            command.extend(
                [
                    "--genome-size",
                    _size(inputs["genome_size"], inputs.get("genome_size_unit", "b")),
                    "--coverage",
                    str(inputs["coverage"]),
                ]
            )
        elif subsample_type == "num_bases":
            command.extend(["--bases", _size(inputs["bases"], inputs.get("num_bases_unit", "b"))])
        elif subsample_type == "num_reads":
            command.extend(["--num", str(inputs["num"])])
        else:
            command.extend(["--frac", str(inputs.get("frac", 0.1))])

    @classmethod
    def _render_reads(cls, inputs: dict[str, Any]) -> list[str]:
        output_dir = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        reads = cls._reads(inputs)
        extension = _output_ext(inputs, reads)
        command = ["rasusa", "reads"]
        _add_value(command, "--seed", inputs.get("seed"))
        if inputs.get("strict", False):
            command.append("--strict")
        if inputs.get("verbose", False):
            command.append("-v")
        _add_value(command, "--output-format", inputs.get("output_format"))
        _add_value(command, "--compress-level", inputs.get("compress_level"))
        if len(reads) == 2:
            command.extend(
                [
                    "--output",
                    str(output_dir / f"paired_R1.{extension}"),
                    "--output",
                    str(output_dir / f"paired_R2.{extension}"),
                ]
            )
        else:
            command.extend(["--output", str(output_dir / f"single.{extension}")])
        cls._append_target(command, inputs)
        command.extend(["--compress-type", str(inputs.get("compress_type") or _compression_from_ext(extension)), *reads])
        return command

    @classmethod
    def _render_aligned(cls, inputs: dict[str, Any]) -> list[str]:
        output_dir = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        output_bam = output_dir / "subsampled.bam"
        command = ["set", "-o", "pipefail", "&&", "rasusa", "aln"]
        _add_value(command, "--seed", inputs.get("seed"))
        command.extend(["--coverage", str(int(float(inputs["coverage"])))])
        strategy = str(inputs.get("strategy", "stream") or "stream")
        command.extend(["--strategy", strategy])
        if strategy == "stream":
            command.extend(["--swap-distance", str(inputs.get("swap_distance", 5))])
        else:
            command.extend(
                [
                    "--step-size",
                    str(inputs.get("step_size", 100)),
                    "--batch-size",
                    str(inputs.get("batch_size", 10000)),
                ]
            )
        command.extend(
            [
                "--output-format",
                "bam",
                str(inputs.get("aligned_input", "")),
                "|",
                "samtools",
                "sort",
                "--no-PG",
                "-@",
                str(inputs.get("threads", 1)),
                "-O",
                "bam",
                "-o",
                str(output_bam),
                "-",
                "&&",
                "samtools",
                "index",
                "-o",
                str(output_dir / "subsampled.bam.bai"),
                str(output_bam),
            ]
        )
        return command

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        if _selector(inputs) != "aligned" or str(inputs.get("strategy", "stream") or "stream") != "fetch":
            return
        staged_bam = outputs[0].parent / "input" / "alignment.bam"
        staged_bai = Path(f"{staged_bam}.bai")
        inputs["aligned_input"] = str(stage_file(str(inputs["aligned_input"]), staged_bam))
        inputs["aligned_input_index"] = str(stage_file(str(inputs["aligned_input_index"]), staged_bai))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        if _selector(inputs) == "aligned":
            return cls._render_aligned(inputs)
        return cls._render_reads(inputs)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        selector = _selector(inputs)
        if selector == "aligned":
            return [node_out / "subsampled.bam", node_out / "subsampled.bam.bai"]
        extension = _output_ext(inputs, cls._reads(inputs))
        if selector in {"paired", "paired_collection"}:
            return [node_out / f"paired_R1.{extension}", node_out / f"paired_R2.{extension}"]
        return [node_out / f"single.{extension}"]

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Any]:
        if not planned_paths:
            return {}
        if planned_paths[0].name == "subsampled.bam":
            return {"subsampled_bam": planned_paths[0], "subsampled_bam_index": planned_paths[1]}
        if planned_paths[0].name.startswith("paired_R1"):
            return {"paired_reads": planned_paths}
        return {"single_reads": planned_paths[0]}

    async def run(self, **kwargs: Any) -> Any:
        result = await super().run(**kwargs)
        if not isinstance(result, tuple):
            return result
        mapped = self.__class__.MAP_PLANNED_OUTPUTS([Path(path) for path in result])

        def normalize(value: Any) -> Any:
            if isinstance(value, Path):
                return str(value)
            if isinstance(value, list):
                return [str(path) for path in value]
            return value

        return {"outputs": {name: normalize(value) for name, value in mapped.items()}}
