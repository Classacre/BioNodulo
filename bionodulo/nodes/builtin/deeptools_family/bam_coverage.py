"""deepTools bamCoverage node pinned to 3.5.6."""

from __future__ import annotations

from typing import Any

from bionodulo.nodes.builtin._bam_index import validate_colocated_bam_index

from .adapter import DeepToolsCommandNode, deeptools_source_urls


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
    SOURCE_PATHS = (
        "deeptools/bamCoverage.py",
        "deeptools/parserCommon.py",
        "deeptools/bamHandler.py",
        "docs/content/tools/bamCoverage.rst",
        "pyproject.toml",
    )
    SOURCE_URLS = deeptools_source_urls(*SOURCE_PATHS)
    SOURCE_URL = SOURCE_URLS[0]
    UPSTREAM_SOURCE = "; ".join(SOURCE_PATHS[:3])

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
                "threads": ("INT", {"default": 1, "min": 1}),
                "normalize_using": (
                    "STRING",
                    {"default": "None", "options": list(cls.NORMALIZATIONS)},
                ),
            },
            "optional": {
                "bin_size": ("INT", {"default": 50, "min": 1}),
                "effective_genome_size": (
                    "INT",
                    {"default": None, "min": 1, "description": "Required for RPGC normalization"},
                ),
                "center_reads": ("BOOLEAN", {"default": False}),
                "ignore_duplicates": ("BOOLEAN", {"default": False}),
                "extend_reads": (
                    "STRING",
                    {
                        "default": "",
                        "description": (
                            "Blank disables --extendReads; 'auto' emits the flag without a value "
                            "for paired-end estimation; a positive integer sets a fixed fragment length"
                        ),
                    },
                ),
                "blacklist": (
                    "FILE",
                    {
                        "default": "",
                        "multiple": True,
                        "description": "Optional BED/GTF blacklist file(s)",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @staticmethod
    def _extend_reads_value(value: Any) -> bool | int | None:
        if value is None or value is False:
            return None
        if value is True:
            return True
        if isinstance(value, int):
            if value > 0:
                return value
            raise ValueError("extend_reads must be 'auto' or a positive integer when supplied")
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                return None
            if normalized.lower() == "auto":
                return True
            try:
                parsed = int(normalized)
            except ValueError as exc:
                raise ValueError("extend_reads must be 'auto' or a positive integer when supplied") from exc
            if parsed > 0:
                return parsed
        raise ValueError("extend_reads must be 'auto' or a positive integer when supplied")

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_colocated_bam_index(inputs)
        if validation is not True:
            return validation
        threads = inputs.get("threads", 1)
        if isinstance(threads, bool) or not isinstance(threads, int) or threads < 1:
            return "threads must be a positive integer"
        bin_size = inputs.get("bin_size", 50)
        if isinstance(bin_size, bool) or not isinstance(bin_size, int) or bin_size < 1:
            return "bin_size must be a positive integer"
        normalization = str(inputs.get("normalize_using", "None") or "None")
        if normalization not in cls.NORMALIZATIONS:
            return f"Unsupported bamCoverage normalization: {normalization}"
        effective_size = inputs.get("effective_genome_size")
        if effective_size is not None and (
            isinstance(effective_size, bool) or not isinstance(effective_size, int) or effective_size < 1
        ):
            return "effective_genome_size must be a positive integer when supplied"
        if normalization == "RPGC" and not isinstance(effective_size, int):
            return "RPGC normalization requires a positive effective_genome_size"
        try:
            cls._extend_reads_value(inputs.get("extend_reads", ""))
        except ValueError as exc:
            return str(exc)
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
        if inputs.get("effective_genome_size") is not None:
            command.extend(["--effectiveGenomeSize", str(inputs["effective_genome_size"])])
        if inputs.get("center_reads"):
            command.append("--centerReads")
        if inputs.get("ignore_duplicates"):
            command.append("--ignoreDuplicates")
        extend_reads = cls._extend_reads_value(inputs.get("extend_reads", ""))
        if extend_reads is True:
            command.append("--extendReads")
        elif extend_reads is not None:
            command.extend(["--extendReads", str(extend_reads)])
        blacklist = cls._blacklist_paths(inputs.get("blacklist"))
        if blacklist:
            command.append("--blackListFileName")
            command.extend(blacklist)
        return command
