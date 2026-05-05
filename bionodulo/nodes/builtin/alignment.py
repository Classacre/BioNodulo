from __future__ import annotations

from pathlib import Path

from bionodulo.nodes.command_node import CommandNode


class BWAIndexNode(CommandNode):
    NODE_ID = "bwa_index"
    DISPLAY_NAME = "BWA index"
    CATEGORY = "Alignment"
    DESCRIPTION = "Create a BWA reference index."
    SEARCH_ALIASES = ["bwa", "index", "reference", "align"]
    RETURN_TYPES = ("INDEX_DIR",)
    RETURN_NAMES = ("index_dir",)
    REQUIRED_EXECUTABLES = ["bwa"]
    COMMAND = ["bwa", "index", "{inputs.reference}"]

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {"required": {"reference": ("FASTA", {"description": "Reference FASTA"})}, "optional": {}, "hidden": {}}

    @classmethod
    def PLAN_OUTPUTS(cls, node_dir: Path, params: dict, inputs: dict) -> dict:
        return {"index_dir": str(node_dir / "bwa_index")}


class BWAMemNode(CommandNode):
    NODE_ID = "bwa_mem"
    DISPLAY_NAME = "BWA mem"
    CATEGORY = "Alignment"
    DESCRIPTION = "Align FASTQ reads to a BWA-indexed reference."
    SEARCH_ALIASES = ["bwa", "mem", "align", "sam", "bam"]
    RETURN_TYPES = ("SAM",)
    RETURN_NAMES = ("sam",)
    REQUIRED_EXECUTABLES = ["bwa"]
    COMMAND = ["bwa", "mem", "-t", "{params.threads}", "{inputs.reference}", "{inputs.reads[0]}", "{inputs.reads[1]}"]

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {"reference": ("FASTA", {}), "reads": ("FASTQ_LIST", {})},
            "optional": {"threads": ("INT", {"default": 4, "min": 1, "max": 64})},
            "hidden": {},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, node_dir: Path, params: dict, inputs: dict) -> dict:
        return {"sam": str(node_dir / "alignment.sam")}


class SamtoolsSortNode(CommandNode):
    NODE_ID = "samtools_sort"
    DISPLAY_NAME = "samtools sort"
    CATEGORY = "Alignment"
    DESCRIPTION = "Sort SAM/BAM alignments into a coordinate-sorted BAM."
    SEARCH_ALIASES = ["samtools", "sort", "bam"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("bam",)
    REQUIRED_EXECUTABLES = ["samtools"]
    COMMAND = ["samtools", "sort", "-@", "{params.threads}", "-o", "{outputs.bam}", "{inputs.alignment}"]

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {"required": {"alignment": ("SAM", {})}, "optional": {"threads": ("INT", {"default": 4, "min": 1, "max": 64})}, "hidden": {}}


class SamtoolsIndexNode(CommandNode):
    NODE_ID = "samtools_index"
    DISPLAY_NAME = "samtools index"
    CATEGORY = "Alignment"
    DESCRIPTION = "Index a coordinate-sorted BAM."
    SEARCH_ALIASES = ["samtools", "index", "bai", "bam"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("bai",)
    REQUIRED_EXECUTABLES = ["samtools"]
    COMMAND = ["samtools", "index", "{inputs.bam}", "{outputs.bai}"]

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {"required": {"bam": ("BAM", {})}, "optional": {}, "hidden": {}}

    @classmethod
    def PLAN_OUTPUTS(cls, node_dir: Path, params: dict, inputs: dict) -> dict:
        return {"bai": str(node_dir / "alignment.bam.bai")}
