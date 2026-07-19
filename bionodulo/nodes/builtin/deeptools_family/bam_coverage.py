"""deepTools bamCoverage node pinned to 3.5.6."""

from __future__ import annotations

from typing import Any

from bionodulo.nodes.builtin._bam_index import validate_colocated_bam_index

from .adapter import DeepToolsCommandNode


class DeepToolsBamCoverageNode(DeepToolsCommandNode):
    """Convert a sorted, indexed BAM into a bigWig coverage track."""

    NODE_ID = "deeptools_bamcoverage"
    DISPLAY_NAME = "deepTools bamCoverage"
    DESCRIPTION = "Convert BAM to bigWig coverage tracks with explicit BAM/BAI pairing"
    SEARCH_ALIASES = ["deeptools", "bamcoverage", "bigwig", "coverage", "chip-seq", "atac-seq"]
    RETURN_TYPES = ("BIGWIG",)
    RETURN_NAMES = ("coverage_bw",)
    REQUIRED_EXECUTABLES = ["bamCoverage"]
    OUTPUT_FILENAMES = ("coverage_bw.bw",)
    DOCUMENTATION_URL = "https://deeptools.readthedocs.io/en/3.5.6/content/tools/bamCoverage.html"
    UPSTREAM_SOURCE = "deeptools/bamCoverage.py"

    NORMALIZATIONS = ("None", "RPKM", "CPM", "BPM", "RPGC")

    @staticmethod
    def _blacklist_paths(value: Any) -> list[str]:
        if value in (None, ""):
            return []
        if isinstance(value, (list, tuple)):
            return [str(item) for item in value if str(item).strip()]
        return [str(value)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Coordinate-sorted BAM"}),
                "bam_index": ("BAI", {"description": "Exact colocated <bam>.bai index"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64}),
                "normalize_using": (
                    "STRING",
                    {"default": "None", "options": list(cls.NORMALIZATIONS)},
                ),
            },
            "optional": {
                "bin_size": ("INT", {"default": 50, "min": 1}),
                "effective_genome_size": ("INT", {"default": 0, "min": 0}),
                "center_reads": ("BOOLEAN", {"default": False}),
                "ignore_duplicates": ("BOOLEAN", {"default": False}),
                "extend_reads": ("INT", {"default": 0, "min": 0}),
                "blacklist": ("BED", {"default": "", "description": "Optional blacklist BED file(s)"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_colocated_bam_index(inputs)
        if validation is not True:
            return validation
        threads = inputs.get("threads", 1)
        if isinstance(threads, bool) or not isinstance(threads, int) or not 1 <= threads <= 64:
            return "threads must be an integer between 1 and 64"
        bin_size = inputs.get("bin_size", 50)
        if isinstance(bin_size, bool) or not isinstance(bin_size, int) or bin_size < 1:
            return "bin_size must be a positive integer"
        normalization = str(inputs.get("normalize_using", "None") or "None")
        if normalization not in cls.NORMALIZATIONS:
            return f"Unsupported bamCoverage normalization: {normalization}"
        effective_size = inputs.get("effective_genome_size", 0)
        if isinstance(effective_size, bool) or not isinstance(effective_size, int) or effective_size < 0:
            return "effective_genome_size must be a non-negative integer"
        if normalization == "RPGC" and effective_size <= 0:
            return "RPGC normalization requires a positive effective_genome_size"
        extend_reads = inputs.get("extend_reads", 0)
        if isinstance(extend_reads, bool) or not isinstance(extend_reads, int) or extend_reads < 0:
            return "extend_reads must be a non-negative integer"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        command = [
            "bamCoverage",
            "-b",
            str(inputs.get("bam", "")),
            "-o",
            str(cls.output_dir(inputs) / cls.OUTPUT_FILENAMES[0]),
            "-p",
            str(inputs.get("threads", 1)),
            "--binSize",
            str(inputs.get("bin_size", 50)),
        ]
        normalization = str(inputs.get("normalize_using", "None") or "None")
        if normalization != "None":
            command.extend(["--normalizeUsing", normalization])
        if inputs.get("effective_genome_size", 0) > 0:
            command.extend(["--effectiveGenomeSize", str(inputs["effective_genome_size"])])
        if inputs.get("center_reads"):
            command.append("--centerReads")
        if inputs.get("ignore_duplicates"):
            command.append("--ignoreDuplicates")
        if inputs.get("extend_reads", 0) > 0:
            command.extend(["--extendReads", str(inputs["extend_reads"])])
        blacklist = cls._blacklist_paths(inputs.get("blacklist"))
        if blacklist:
            command.append("--blackListFileName")
            command.extend(blacklist)
        return command
