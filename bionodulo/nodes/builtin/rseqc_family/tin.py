"""RSeQC transcript-integrity node pinned to the 5.0.3 sdist."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import RSeQCCommandNode


class RSeQCTINNode(RSeQCCommandNode):
    """Calculate per-transcript TIN files for one or more indexed BAMs."""

    NODE_ID = "rseqc_tin"
    DISPLAY_NAME = "RSeQC Transcript Integrity Number"
    DESCRIPTION = "Calculate transcript integrity numbers from sorted and indexed BAM alignments."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "RSeQC",
        "tin.py",
        "TIN",
        "Transcript Integrity Number",
        "RNA integrity",
        "RNA degradation",
        "RNA-seq QC",
    ]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("tin_results",)
    REQUIRED_EXECUTABLES = ["tin.py"]
    UPSTREAM_SCRIPT = "scripts/tin.py"
    UPSTREAM_SOURCE = "scripts/tin.py"
    UPSTREAM_OUTPUT_SOURCE = "scripts/tin.py:main"
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#tin-py"
    CITATION_DOIS = ["10.1186/s12859-016-0922-z", "10.1093/bioinformatics/bts356"]
    CITATION_URLS = [
        "https://doi.org/10.1186/s12859-016-0922-z",
        "https://doi.org/10.1093/bioinformatics/bts356",
    ]
    CITATION_TEXT = "Measure transcript integrity using RNA-seq data; RSeQC: quality control of RNA-seq experiments."
    RUN_IN_NODE_OUTPUT_DIR = True
    REQUIRED_PATH_LIST_INPUTS = ("input", "bam_indexes")
    REQUIRED_PATH_INPUTS = ("refgene",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (
                    "BAM_LIST",
                    {
                        "multiple": True,
                        "description": "Sorted and indexed BAM alignment files",
                    },
                ),
                "bam_indexes": (
                    "FILE_LIST",
                    {
                        "multiple": True,
                        "description": "One exact colocated <bam>.bai index per BAM",
                    },
                ),
                "refgene": (
                    "BED",
                    {"description": "Standard 12-column BED gene model"},
                ),
            },
            "optional": {
                "min_cov": (
                    "INT",
                    {
                        "default": 10,
                        "min": 1,
                        "description": "Minimum reads mapped to a transcript",
                    },
                ),
                "sample_size": (
                    "INT",
                    {
                        "default": 100,
                        "min": 1,
                        "description": "Equal-spaced mRNA positions sampled per transcript",
                    },
                ),
                "subtract_background": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Subtract intronic background noise",
                    },
                ),
                # Legacy workflow keys remain accepted but are hidden from the
                # normal UI so older serialized workflows can be recovered.
                "minCov": (
                    "INT",
                    {"default": None, "min": 1, "advanced": True},
                ),
                "samplesize": (
                    "INT",
                    {"default": None, "min": 1, "advanced": True},
                ),
                "subtractbackground": (
                    "BOOLEAN",
                    {"default": None, "advanced": True},
                ),
                "inputs": (
                    "BAM_LIST",
                    {
                        "default": None,
                        "multiple": True,
                        "advanced": True,
                        "description": "Compatibility alias for input",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        return [node_dir]

    @staticmethod
    def _resolve_alias(
        inputs: dict[str, Any],
        canonical: str,
        legacy: str,
        default: Any,
    ) -> tuple[Any, bool | str]:
        canonical_present = canonical in inputs and inputs[canonical] is not None
        legacy_present = legacy in inputs and inputs[legacy] is not None
        if canonical_present and legacy_present and inputs[canonical] != inputs[legacy]:
            return default, f"Inputs '{canonical}' and '{legacy}' conflict"
        if canonical_present:
            return inputs[canonical], True
        if legacy_present:
            return inputs[legacy], True
        return default, True

    @classmethod
    def _resolved_options(cls, inputs: dict[str, Any]) -> tuple[dict[str, Any], bool | str]:
        min_cov, validation = cls._resolve_alias(inputs, "min_cov", "minCov", 10)
        if validation is not True:
            return {}, validation
        sample_size, validation = cls._resolve_alias(inputs, "sample_size", "samplesize", 100)
        if validation is not True:
            return {}, validation
        subtract, validation = cls._resolve_alias(inputs, "subtract_background", "subtractbackground", False)
        if validation is not True:
            return {}, validation
        return {
            "min_cov": min_cov,
            "sample_size": sample_size,
            "subtract_background": subtract,
        }, True

    @classmethod
    def _resolved_bams(cls, inputs: dict[str, Any]) -> tuple[list[str], bool | str]:
        canonical = cls.path_list(inputs.get("input"))
        legacy = cls.path_list(inputs.get("inputs"))
        if canonical and legacy and canonical != legacy:
            return [], "Inputs 'input' and 'inputs' conflict"
        bams = canonical or legacy
        if not bams:
            return [], "Input 'input' must contain at least one non-empty BAM path"
        return bams, True

    @staticmethod
    def _source_output_names(bams: list[str]) -> list[str]:
        names: list[str] = []
        for bam in bams:
            prefix = Path(bam).name.replace("bam", "")
            names.extend([f"{prefix}summary.txt", f"{prefix}tin.xls"])
        return names

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation_inputs = dict(inputs)
        bams, validation = cls._resolved_bams(inputs)
        if validation is not True:
            return validation
        validation_inputs["input"] = bams
        validation = super().VALIDATE_INPUTS(validation_inputs)
        if validation is not True:
            return validation

        indexes = cls.path_list(inputs.get("bam_indexes"))
        if len(bams) != len(indexes):
            return "Input 'bam_indexes' must contain one exact index for each BAM in 'input'"
        for bam in bams:
            if not bam.lower().endswith(".bam"):
                return f"Input 'input' contains a non-BAM path: {bam}"
            if "," in bam:
                return "Input 'input' BAM paths cannot contain commas"
        output_names = cls._source_output_names(bams)
        if len(output_names) != len(set(output_names)):
            return "Input 'input' BAM basenames must be unique because tin.py writes basename-derived outputs"
        validation = cls.validate_bam_indexes(
            validation_inputs,
            bams_key="input",
            indexes_key="bam_indexes",
        )
        if validation is not True:
            return validation

        options, validation = cls._resolved_options(inputs)
        if validation is not True:
            return validation
        validation = cls.validate_int(options["min_cov"], "min_cov", minimum=1)
        if validation is not True:
            return validation
        validation = cls.validate_int(options["sample_size"], "sample_size", minimum=1)
        if validation is not True:
            return validation
        if not isinstance(options["subtract_background"], bool):
            return "Input 'subtract_background' must be a boolean"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        bams, _ = cls._resolved_bams(inputs)
        options, _ = cls._resolved_options(inputs)
        command = [
            "tin.py",
            "-i",
            ",".join(bams),
            "-r",
            cls.path_value(inputs["refgene"]),
            "-c",
            str(options["min_cov"]),
            "-n",
            str(options["sample_size"]),
        ]
        if options["subtract_background"]:
            command.append("-s")
        return command

    async def run(self, **kwargs: Any) -> tuple[str]:
        result = await super().run(**kwargs)
        output_dir = Path(result[0])
        bams, validation = self.__class__._resolved_bams(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        missing = [name for name in self.__class__._source_output_names(bams) if not (output_dir / name).is_file()]
        if missing:
            raise RuntimeError(f"tin.py did not create expected output(s): {', '.join(missing)}")
        return result
