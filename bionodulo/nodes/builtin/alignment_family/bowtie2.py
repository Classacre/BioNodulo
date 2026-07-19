"""Bowtie2 2.5.5 legacy ID with validated index and conditional artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import stage_file
from .bowtie2_adapter import BOWTIE2_SUFFIX_FAMILIES, Bowtie2CommandNode
from .fm_index_bundle import find_index_bundle, planned_or_complete_prefix
from .legacy_adapter import mapped_result, path_list, path_value, validate_int


class Bowtie2Node(Bowtie2CommandNode):
    """Align one single-end or paired read set with optional read artifacts."""

    NODE_ID = "bowtie2"
    DISPLAY_NAME = "Bowtie2"
    DESCRIPTION = "Align reads with Bowtie2 and emit truthful SAM/BAM and optional read artifacts."
    SEARCH_ALIASES = ["bowtie2", "bowtie2-build", "read mapping"]
    RETURN_TYPES = ("FILE", "BAI", "FILE", "FILE_LIST", "FILE_LIST")
    RETURN_NAMES = ("alignments", "alignment_index", "mapping_stats", "unaligned_reads", "aligned_reads")
    REQUIRED_EXECUTABLES = ["bowtie2", "bowtie2-build", "samtools"]
    REQUIRED_CONDA_PACKAGES = ["bowtie2", "samtools"]
    PACKAGE_CONSTRAINTS = ("bowtie2==2.5.5", "samtools==1.23.1")
    PACKAGE_CONSTRAINT = "; ".join(PACKAGE_CONSTRAINTS)
    UPSTREAM_WRAPPER = "bowtie2"
    UPSTREAM_SOURCE = "bt2_search.cpp"
    SHELL = True
    REFERENCE_SOURCES = ("indexed", "history")
    LIBRARY_TYPES = ("single", "paired_collection")
    OUTPUT_FORMATS = ("bam", "sam", "input_order_bam")
    LEGACY_OUTPUT_FORMATS = {"qname_input_sorted_bam": "input_order_bam"}
    READ_FORMATS = ("fastq", "fasta")
    COMPRESSIONS = ("", "gz", "bz2")
    PRESETS = (
        "no_presets",
        "--very-fast",
        "--fast",
        "--sensitive",
        "--very-sensitive",
        "--very-fast-local",
        "--fast-local",
        "--sensitive-local",
        "--very-sensitive-local",
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "ref_file": ("FASTA,INDEX_DIR", {"description": "History FASTA or complete Bowtie2 index directory"}),
                "input_1": ("FILE_LIST", {"description": "Single read or ordered paired collection"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64}),
            },
            "optional": {
                "library_type": ("STRING", {"default": "single", "options": list(cls.LIBRARY_TYPES)}),
                "reference_source_selector": ("STRING", {"default": "indexed", "options": list(cls.REFERENCE_SOURCES)}),
                "reads_format": ("STRING", {"default": "fastq", "options": list(cls.READ_FORMATS)}),
                "reads_compression": ("STRING", {"default": "", "options": list(cls.COMPRESSIONS)}),
                "preset": ("STRING", {"default": "no_presets", "options": list(cls.PRESETS)}),
                "sam_output_format": ("STRING", {"default": "bam", "options": list(cls.OUTPUT_FORMATS)}),
                "unaligned_file": ("BOOLEAN", {"default": False}),
                "aligned_file": ("BOOLEAN", {"default": False}),
                "save_mapping_stats": ("BOOLEAN", {"default": False}),
                "rg_id": ("STRING", {"default": ""}),
                "rg_sample": ("STRING", {"default": ""}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _reads(cls, inputs: dict[str, Any]) -> list[str]:
        if str(inputs.get("library_type", "single") or "single") == "paired_collection":
            return path_list(inputs.get("input_1"), mapping_keys=("forward", "reverse"))
        reads = path_list(inputs.get("input_1"))
        return reads[:1]

    @classmethod
    def _artifact_extension(cls, inputs: dict[str, Any]) -> str:
        extension = ".fasta" if inputs.get("reads_format", "fastq") == "fasta" else ".fastq"
        compression = str(inputs.get("reads_compression", "") or "")
        return f"{extension}.{compression}" if compression else extension

    @classmethod
    def _output_format(cls, inputs: dict[str, Any]) -> str:
        value = str(inputs.get("sam_output_format", "bam") or "bam")
        return cls.LEGACY_OUTPUT_FORMATS.get(value, value)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        output_format = cls._output_format(inputs)
        outputs = [node_out / ("alignments.sam" if output_format == "sam" else "alignments.bam")]
        if output_format == "bam":
            outputs.append(node_out / "alignments.bam.bai")
        if inputs.get("save_mapping_stats", False):
            outputs.append(node_out / "mapping_stats.txt")
        extension = cls._artifact_extension(inputs)
        paired = str(inputs.get("library_type", "single") or "single") == "paired_collection"
        for enabled, stem in ((inputs.get("unaligned_file", False), "unaligned_reads"), (inputs.get("aligned_file", False), "aligned_reads")):
            if not enabled:
                continue
            if paired:
                outputs.extend([node_out / f"{stem}.1{extension}", node_out / f"{stem}.2{extension}"])
            else:
                outputs.append(node_out / f"{stem}{extension}")
        return outputs

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Any]:
        mapped: dict[str, Any] = {"alignments": planned_paths[0]}
        for path in planned_paths[1:]:
            if path.name == "alignments.bam.bai":
                mapped["alignment_index"] = path
            elif path.name == "mapping_stats.txt":
                mapped["mapping_stats"] = path
            elif path.name.startswith("unaligned_reads"):
                mapped.setdefault("unaligned_reads", []).append(path)
            elif path.name.startswith("aligned_reads"):
                mapped.setdefault("aligned_reads", []).append(path)
        return mapped

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if path_value(inputs.get("ref_file")) is None:
            return "ref_file must be a non-empty path"
        library_type = str(inputs.get("library_type", "single") or "single")
        if library_type not in cls.LIBRARY_TYPES:
            return f"library_type must be one of: {', '.join(cls.LIBRARY_TYPES)}"
        reads = cls._reads(inputs)
        expected = 2 if library_type == "paired_collection" else 1
        if len(reads) != expected:
            return f"{library_type} mode requires exactly {expected} read input(s)"
        source = str(inputs.get("reference_source_selector", "indexed") or "indexed")
        if source not in cls.REFERENCE_SOURCES:
            return f"reference_source_selector must be one of: {', '.join(cls.REFERENCE_SOURCES)}"
        if source == "indexed":
            try:
                find_index_bundle(str(inputs["ref_file"]), label="Bowtie2", suffix_families=BOWTIE2_SUFFIX_FAMILIES)
            except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
                return str(exc)
        for name, options, default in (
            ("reads_format", cls.READ_FORMATS, "fastq"),
            ("reads_compression", cls.COMPRESSIONS, ""),
            ("preset", cls.PRESETS, "no_presets"),
        ):
            if str(inputs.get(name, default) or default) not in options:
                return f"{name} must be one of: {', '.join(options)}"
        output_format = str(inputs.get("sam_output_format", "bam") or "bam")
        if output_format not in (*cls.OUTPUT_FORMATS, *cls.LEGACY_OUTPUT_FORMATS):
            return f"sam_output_format must be one of: {', '.join(cls.OUTPUT_FORMATS)}"
        if str(inputs.get("rg_sample", "") or "").strip() and not str(inputs.get("rg_id", "") or "").strip():
            return "rg_id is required when rg_sample is set"
        return validate_int(inputs.get("threads", 1), "threads", minimum=1, maximum=64)

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        if str(inputs.get("reference_source_selector", "indexed") or "indexed") == "indexed":
            return
        reference_dir = outputs[0].parent / "reference"
        reference = reference_dir / "reference.fa"
        stage_file(Path(str(inputs["ref_file"])), reference)
        inputs["ref_file"] = str(reference)
        inputs["prepared_index_prefix"] = str(reference_dir / "index")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        node_out = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        source = str(inputs.get("reference_source_selector", "indexed") or "indexed")
        command = ["set", "-o", "pipefail", "&&"]
        if source == "indexed":
            prefix = planned_or_complete_prefix(str(inputs.get("ref_file", "")), label="Bowtie2", suffix_families=BOWTIE2_SUFFIX_FAMILIES)
        else:
            prefix = Path(str(inputs.get("prepared_index_prefix", node_out / "reference" / "index")))
            command.extend(["bowtie2-build", "--threads", str(inputs.get("threads", 1)), str(inputs.get("ref_file", "")), str(prefix), "&&"])

        bowtie = ["bowtie2", "-p", str(inputs.get("threads", 1)), "-x", str(prefix)]
        if inputs.get("reads_format", "fastq") == "fasta":
            bowtie.append("-f")
        preset = str(inputs.get("preset", "no_presets") or "no_presets")
        if preset != "no_presets":
            bowtie.append(preset)
        if inputs.get("rg_id"):
            bowtie.extend(["--rg-id", str(inputs["rg_id"])])
        if inputs.get("rg_sample"):
            bowtie.extend(["--rg", f"SM:{inputs['rg_sample']}"])
        reads = cls._reads(inputs)
        paired = len(reads) == 2
        bowtie.extend(["-1", reads[0], "-2", reads[1]] if paired else ["-U", reads[0]])

        extension = cls._artifact_extension(inputs)
        compression = str(inputs.get("reads_compression", "") or "")
        for enabled, stem, single_flags, paired_flags in (
            (inputs.get("unaligned_file", False), "unaligned_reads", {"": "--un", "gz": "--un-gz", "bz2": "--un-bz2"}, {"": "--un-conc", "gz": "--un-conc-gz", "bz2": "--un-conc-bz2"}),
            (inputs.get("aligned_file", False), "aligned_reads", {"": "--al", "gz": "--al-gz", "bz2": "--al-bz2"}, {"": "--al-conc", "gz": "--al-conc-gz", "bz2": "--al-conc-bz2"}),
        ):
            if not enabled:
                continue
            if paired:
                bowtie.extend([paired_flags[compression], str(node_out / f"{stem}.%{extension}")])
            else:
                bowtie.extend([single_flags[compression], str(node_out / f"{stem}{extension}")])

        output_format = cls._output_format(inputs)
        if output_format == "input_order_bam":
            bowtie.append("--reorder")
        if inputs.get("save_mapping_stats", False):
            bowtie.extend(["2>", str(node_out / "mapping_stats.txt")])
        if output_format == "sam":
            bowtie.extend(["-S", str(node_out / "alignments.sam")])
        elif output_format == "input_order_bam":
            bowtie.extend(["|", "samtools", "view", "-b", "-o", str(node_out / "alignments.bam"), "-"])
        else:
            output_bam = node_out / "alignments.bam"
            bowtie.extend(["|", "samtools", "sort", "-@", str(inputs.get("threads", 1)), "-O", "bam", "-o", str(output_bam), "-", "&&", "samtools", "index", "-o", str(node_out / "alignments.bam.bai"), str(output_bam)])
        command.extend(bowtie)
        return command

    async def run(self, **kwargs: Any) -> Any:
        return mapped_result(await super().run(**kwargs), self.__class__.MAP_PLANNED_OUTPUTS)
