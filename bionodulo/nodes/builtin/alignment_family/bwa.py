"""BWA 0.7.19 aln/samse/sampe wrapper with validated index bundles."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import BWA_INDEX_FASTA, BwaCommandNode, find_index_prefix, stage_file
from .legacy_adapter import path_list, path_value, validate_int


class BWANode(BwaCommandNode):
    """Map short reads with BWA aln and emit a coordinate-sorted BAM/BAI pair."""

    NODE_ID = "bwa"
    DISPLAY_NAME = "Map with BWA"
    DESCRIPTION = "Map short reads with BWA aln/samse/sampe and emit coordinate-sorted BAM plus BAI."
    SEARCH_ALIASES = ["bwa", "bwa aln", "bwa samse", "bwa sampe"]
    RETURN_TYPES = ("BAM", "BAI")
    RETURN_NAMES = ("bam_output", "bam_output_index")
    REQUIRED_EXECUTABLES = ["bwa", "samtools"]
    REQUIRED_CONDA_PACKAGES = ["bwa", "samtools"]
    PACKAGE_CONSTRAINTS = ("bwa==0.7.19", "samtools==1.23.1")
    PACKAGE_CONSTRAINT = "; ".join(PACKAGE_CONSTRAINTS)
    DOCUMENTATION_URL = "https://github.com/lh3/bwa/blob/v0.7.19/bwa.1"
    UPSTREAM_SOURCE = "bwtaln.c; bwase.c; bwape.c"
    SHELL = True
    INPUT_MODES = ("single", "paired", "paired_collection", "single_bam", "paired_bam")
    REFERENCE_SOURCES = ("history", "cached")
    INDEX_ALGORITHMS = ("auto", "is", "bwtsw", "rb2")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "ref_file": ("FASTA,INDEX_DIR", {"description": "History FASTA or complete BWA index directory"}),
                "input_type_selector": ("STRING", {"default": "paired", "options": list(cls.INPUT_MODES)}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64}),
            },
            "optional": {
                "fastq_input1": ("FASTQ_LIST", {"default": "", "description": "Single, forward, or paired collection reads"}),
                "fastq_input2": ("FASTQ", {"default": "", "description": "Reverse reads"}),
                "bam_input": ("BAM", {"default": "", "description": "Unaligned BAM for BAM modes"}),
                "reference_source_selector": ("STRING", {"default": "history", "options": list(cls.REFERENCE_SOURCES)}),
                "index_a": ("STRING", {"default": "auto", "options": list(cls.INDEX_ALGORITHMS)}),
                "read_group": ("STRING", {"default": "", "description": "Complete escaped @RG line passed to samse/sampe -r"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _reads(cls, inputs: dict[str, Any]) -> list[str]:
        mode = str(inputs.get("input_type_selector", "paired") or "paired")
        if mode == "paired":
            return path_list([inputs.get("fastq_input1"), inputs.get("fastq_input2")])
        if mode == "paired_collection":
            return path_list(inputs.get("fastq_input1"), mapping_keys=("forward", "reverse"))
        if mode in {"single_bam", "paired_bam"}:
            return path_list(inputs.get("bam_input"))
        return path_list(inputs.get("fastq_input1"))

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "aligned.bam", node_out / "aligned.bam.bai"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if path_value(inputs.get("ref_file")) is None:
            return "ref_file must be a non-empty path"
        mode = str(inputs.get("input_type_selector", "paired") or "paired")
        if mode not in cls.INPUT_MODES:
            return f"input_type_selector must be one of: {', '.join(cls.INPUT_MODES)}"
        reads = cls._reads(inputs)
        expected = 2 if mode in {"paired", "paired_collection"} else 1
        if len(reads) != expected:
            return f"{mode} mode requires exactly {expected} input path(s)"
        source = str(inputs.get("reference_source_selector", "history") or "history")
        if source not in cls.REFERENCE_SOURCES:
            return f"reference_source_selector must be one of: {', '.join(cls.REFERENCE_SOURCES)}"
        if source == "cached":
            try:
                find_index_prefix(str(inputs["ref_file"]), require_reference=False)
            except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
                return str(exc)
        algorithm = str(inputs.get("index_a", "auto") or "auto")
        if algorithm not in cls.INDEX_ALGORITHMS:
            return f"index_a must be one of: {', '.join(cls.INDEX_ALGORITHMS)}"
        return validate_int(inputs.get("threads", 1), "threads", minimum=1, maximum=64)

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        if str(inputs.get("reference_source_selector", "history") or "history") == "cached":
            return
        reference_dir = outputs[0].parent / "reference"
        reference = reference_dir / BWA_INDEX_FASTA
        stage_file(Path(str(inputs["ref_file"])), reference)
        inputs["ref_file"] = str(reference)
        inputs["prepared_index_prefix"] = str(reference)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        node_out = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        source = str(inputs.get("reference_source_selector", "history") or "history")
        command = ["set", "-o", "pipefail", "&&"]
        if source == "cached":
            prefix = find_index_prefix(str(inputs.get("ref_file", "")), require_reference=False)
        else:
            prefix = Path(str(inputs.get("prepared_index_prefix", inputs.get("ref_file", ""))))
            command.extend(["bwa", "index"])
            algorithm = str(inputs.get("index_a", "auto") or "auto")
            if algorithm != "auto":
                command.extend(["-a", algorithm])
            command.extend(["-p", str(prefix), str(inputs.get("ref_file", "")), "&&"])

        mode = str(inputs.get("input_type_selector", "paired") or "paired")
        reads = cls._reads(inputs)
        sai1 = node_out / "first.sai"
        sai2 = node_out / "second.sai"
        aln1 = ["bwa", "aln", "-t", str(inputs.get("threads", 1))]
        if mode == "single_bam":
            aln1.extend(["-b", "-0"])
        elif mode == "paired_bam":
            aln1.extend(["-b", "-1"])
        aln1.extend([str(prefix), reads[0], ">", str(sai1)])
        command.extend(aln1)
        if mode in {"paired", "paired_collection", "paired_bam"}:
            command.append("&&")
            aln2 = ["bwa", "aln", "-t", str(inputs.get("threads", 1))]
            if mode == "paired_bam":
                aln2.extend(["-b", "-2"])
            aln2.extend([str(prefix), reads[-1], ">", str(sai2), "&&"])
            command.extend(aln2)
            sam = ["bwa", "sampe"]
            if inputs.get("read_group"):
                sam.extend(["-r", str(inputs["read_group"])])
            sam.extend([str(prefix), str(sai1), str(sai2), reads[0], reads[-1]])
        else:
            command.append("&&")
            sam = ["bwa", "samse"]
            if inputs.get("read_group"):
                sam.extend(["-r", str(inputs["read_group"])])
            sam.extend([str(prefix), str(sai1), reads[0]])
        output_bam = node_out / "aligned.bam"
        sam.extend(["|", "samtools", "sort", "-@", str(inputs.get("threads", 1)), "-O", "bam", "-o", str(output_bam), "-", "&&", "samtools", "index", "-o", str(node_out / "aligned.bam.bai"), str(output_bam)])
        command.extend(sam)
        return command
