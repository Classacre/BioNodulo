"""BWA-MEM2 2.3 alignment against a FASTA or validated native index."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import stage_file
from .bwa_mem2_adapter import (
    BWA_MEM2_PREFIX,
    BwaMem2CommandNode,
    bwa_mem2_source_urls,
    find_index_prefix,
    planned_or_index_prefix,
    validate_read_group,
)
from .legacy_adapter import mapped_result, path_list, path_value, validate_int


class BWAMem2Node(BwaMem2CommandNode):
    """Align single, paired, or interleaved reads and emit BAM."""

    NODE_ID = "bwa_mem2"
    DISPLAY_NAME = "BWA-MEM2"
    DESCRIPTION = "Align reads with BWA-MEM2 and optionally coordinate- or name-sort the BAM output."
    SEARCH_ALIASES = ["bwa-mem2", "bwa-mem2 mem", "align", "mapper"]
    RETURN_TYPES = ("BAM", "BAI")
    RETURN_NAMES = ("bam_output", "bam_output_index")
    REQUIRED_EXECUTABLES = ["bwa-mem2", "samtools"]
    REQUIRED_CONDA_PACKAGES = ["bwa-mem2", "samtools"]
    PACKAGE_CONSTRAINTS = ("bwa-mem2==2.3", "samtools==1.23.1")
    PACKAGE_CONSTRAINT = "; ".join(PACKAGE_CONSTRAINTS)
    CONDA_PACKAGE_CONSTRAINTS = {"bwa-mem2": "2.3", "samtools": "1.23.1"}
    UPSTREAM_SOURCE = "src/fastmap.cpp"
    SOURCE_PATHS = ("README.md", "src/fastmap.cpp", "src/FMI_search.cpp", "src/bntseq.cpp")
    SOURCE_URLS = bwa_mem2_source_urls(*SOURCE_PATHS)
    SECONDARY_TOOL_SOURCE = "samtools 1.23.1 samtools_family contract"
    SHELL = True
    INPUT_MODES = ("single", "paired", "paired_collection", "paired_iv")
    REFERENCE_SOURCES = ("history", "cached")
    ANALYSIS_TYPES = ("illumina", "pacbio", "pbref", "ont2d", "intractg", "full")
    OUTPUT_SORTS = ("coordinate", "name", "unsorted")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "ref_file": (
                    ("FASTA", "BWA_MEM2_INDEX", "INDEX_DIR"),
                    {"description": "BWA-MEM2 index directory or FASTA reference"},
                ),
                "fastq_input_selector": ("STRING", {"default": "paired", "options": list(cls.INPUT_MODES)}),
                "fastq_input1": (
                    "FASTQ_LIST",
                    {"description": "Single, forward, paired collection, or interleaved reads"},
                ),
                "threads": ("INT", {"default": 1, "min": 1}),
            },
            "optional": {
                "fastq_input2": ("FASTQ", {"default": "", "description": "Reverse reads for paired mode"}),
                "reference_source_selector": (
                    "STRING",
                    {"default": "history", "options": list(cls.REFERENCE_SOURCES)},
                ),
                "ref_file_type": (
                    "STRING",
                    {
                        "default": "fasta",
                        "options": ["fasta", "fasta.gz", "bwa_mem2_index"],
                        "description": "Declare whether ref_file is a native index directory or a FASTA to index",
                    },
                ),
                "analysis_type_selector": (
                    "STRING",
                    {"default": "illumina", "options": list(cls.ANALYSIS_TYPES)},
                ),
                "output_sort": ("STRING", {"default": "coordinate", "options": list(cls.OUTPUT_SORTS)}),
                "iset_stats": ("STRING", {"default": "", "description": "Insert-size distribution passed to -I"}),
                "read_group": ("STRING", {"default": "", "description": "Complete escaped @RG line passed to -R"}),
                "mark_shorter_splits": ("BOOLEAN", {"default": False, "description": "Use -M"}),
                "min_score": ("INT", {"default": 30, "description": "Minimum score passed to -T"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _reads(cls, inputs: dict[str, Any]) -> list[str]:
        mode = str(inputs.get("fastq_input_selector", "paired") or "paired")
        if mode == "paired":
            return path_list([inputs.get("fastq_input1"), inputs.get("fastq_input2")])
        if mode == "paired_collection":
            return path_list(inputs.get("fastq_input1"), mapping_keys=("forward", "reverse"))
        return path_list(inputs.get("fastq_input1"))

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        outputs = [node_out / "aligned.bam"]
        if str(inputs.get("output_sort", "coordinate") or "coordinate") == "coordinate":
            outputs.append(node_out / "aligned.bam.bai")
        return outputs

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Any]:
        mapped: dict[str, Any] = {"bam_output": planned_paths[0]}
        if len(planned_paths) > 1:
            mapped["bam_output_index"] = planned_paths[1]
        return mapped

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if path_value(inputs.get("ref_file")) is None:
            return "ref_file must be a non-empty path"
        mode = str(inputs.get("fastq_input_selector", "paired") or "paired")
        if mode not in cls.INPUT_MODES:
            return f"fastq_input_selector must be one of: {', '.join(cls.INPUT_MODES)}"
        reads = cls._reads(inputs)
        expected = 2 if mode in {"paired", "paired_collection"} else 1
        if len(reads) != expected:
            return f"{mode} mode requires exactly {expected} read input(s)"
        source = str(inputs.get("reference_source_selector", "history") or "history")
        if source not in cls.REFERENCE_SOURCES:
            return f"reference_source_selector must be one of: {', '.join(cls.REFERENCE_SOURCES)}"
        ref_type = str(inputs.get("ref_file_type", "fasta") or "fasta")
        if ref_type not in {"fasta", "fasta.gz", "bwa_mem2_index"}:
            return "ref_file_type must be one of: fasta, fasta.gz, bwa_mem2_index"
        if ref_type == "bwa_mem2_index":
            try:
                find_index_prefix(str(inputs["ref_file"]))
            except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
                return str(exc)
        analysis_type = str(inputs.get("analysis_type_selector", "illumina") or "illumina")
        if analysis_type not in cls.ANALYSIS_TYPES:
            return f"analysis_type_selector must be one of: {', '.join(cls.ANALYSIS_TYPES)}"
        output_sort = str(inputs.get("output_sort", "coordinate") or "coordinate")
        if output_sort not in cls.OUTPUT_SORTS:
            return f"output_sort must be one of: {', '.join(cls.OUTPUT_SORTS)}"
        validation = validate_int(inputs.get("threads", 1), "threads", minimum=1)
        if validation is not True:
            return validation
        if inputs.get("iset_stats") not in (None, "") and not isinstance(inputs.get("iset_stats"), str):
            return "iset_stats must be a string"
        read_group_validation = validate_read_group(inputs.get("read_group", ""))
        if read_group_validation is not True:
            return read_group_validation
        if not isinstance(inputs.get("mark_shorter_splits", False), bool):
            return "mark_shorter_splits must be a boolean"
        return validate_int(inputs.get("min_score", 30), "min_score")

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        if str(inputs.get("ref_file_type", "fasta") or "fasta") == "bwa_mem2_index":
            return
        index_dir = outputs[0].parent / "reference_index"
        index_dir.mkdir(parents=True, exist_ok=True)
        reference = index_dir / "reference.fa"
        stage_file(Path(str(inputs["ref_file"])), reference)
        inputs["ref_file"] = str(reference)
        inputs["prepared_index_prefix"] = str(index_dir / BWA_MEM2_PREFIX)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        node_out = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = ["set", "-o", "pipefail", "&&"]
        ref_type = str(inputs.get("ref_file_type", "fasta") or "fasta")
        if ref_type == "bwa_mem2_index":
            prefix = planned_or_index_prefix(str(inputs.get("ref_file", "")))
        else:
            prefix = Path(str(inputs.get("prepared_index_prefix", node_out / "reference_index" / BWA_MEM2_PREFIX)))
            command.extend(["bwa-mem2", "index", "-p", str(prefix), str(inputs.get("ref_file", "")), "&&"])

        output_sort = str(inputs.get("output_sort", "coordinate") or "coordinate")
        bwa = ["bwa-mem2", "mem", "-t", str(inputs.get("threads", 1)), "-v", "1"]
        mode = str(inputs.get("fastq_input_selector", "paired") or "paired")
        if mode == "paired_iv":
            bwa.append("-p")
        if inputs.get("iset_stats"):
            bwa.extend(["-I", str(inputs["iset_stats"])])
        analysis_type = str(inputs.get("analysis_type_selector", "illumina") or "illumina")
        if analysis_type not in {"illumina", "full"}:
            bwa.extend(["-x", analysis_type])
        if inputs.get("read_group"):
            bwa.extend(["-R", str(inputs["read_group"])])
        if inputs.get("mark_shorter_splits", False):
            bwa.append("-M")
        bwa.extend(["-T", str(inputs.get("min_score", 30)), str(prefix), *cls._reads(inputs)])
        output_bam = node_out / "aligned.bam"
        if output_sort == "coordinate":
            bwa.extend(
                [
                    "|",
                    "samtools",
                    "sort",
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
                    str(node_out / "aligned.bam.bai"),
                    str(output_bam),
                ]
            )
        elif output_sort == "name":
            bwa.extend(
                [
                    "|",
                    "samtools",
                    "sort",
                    "-n",
                    "-@",
                    str(inputs.get("threads", 1)),
                    "-O",
                    "bam",
                    "-o",
                    str(output_bam),
                    "-",
                ]
            )
        else:
            bwa.extend(["|", "samtools", "view", "-b", "-o", str(output_bam), "-"])
        command.extend(bwa)
        return command

    async def run(self, **kwargs: Any) -> Any:
        return mapped_result(await super().run(**kwargs), self.__class__.MAP_PLANNED_OUTPUTS)
