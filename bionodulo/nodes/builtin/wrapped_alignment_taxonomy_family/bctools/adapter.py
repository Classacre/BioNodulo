"""Shared BCtools contracts for focused owners."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from bionodulo.nodes.builtin.wrapped_alignment_taxonomy_family.contracts import ToolsIUCCommandContract

class _BctoolsConvertToBinaryBarcodeContract(ToolsIUCCommandContract):
    """Convert FASTQ barcode bases into R/Y-space binary barcodes."""

    LEGACY_NODE_ID = "bctools_convert_to_binary_barcode"
    DISPLAY_NAME = "Create binary barcodes"
    REQUIRED_CONDA_PACKAGES = ["bctools"]
    CATEGORY = "sequence"
    DESCRIPTION = "Convert FASTQ barcode reads from nucleotide bases into binary R/Y barcode codes."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "bctools",
        "Create binary barcodes",
        "bctools_convert_to_binary_barcode",
        "convert_bc_to_binary_RY.py",
        "binary barcodes",
        "RY-space barcodes",
        "UMI",
        "uvCLAP",
        "FLASH",
    ]
    RETURN_TYPES = ("FASTQ",)
    RETURN_NAMES = ("barcodes_ry",)
    REQUIRED_EXECUTABLES = ["convert_bc_to_binary_RY.py"]
    DOCUMENTATION_URL = BCTOOLS_CITATION_URL
    CITATION_DOIS = [BCTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BCTOOLS_CITATION_DOI}", BCTOOLS_CITATION_URL]
    CITATION_TEXT = BCTOOLS_CITATION_TEXT
    VERSION = "0.2.2+galaxy2"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/barcodes_ry.fastq"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            str(inputs.get("script_path", "convert_bc_to_binary_RY.py") or "convert_bc_to_binary_RY.py"),
            str(inputs.get("barcodes", "")),
            ">",
            cls._output_path(inputs),
        ]
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "barcodes_ry.fastq"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("barcodes", "")).strip():
            return "barcodes is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "barcodes": ("FASTQ", {"description": "FASTQ file containing barcode reads to convert"}),
            },
            "optional": {
                "script_path": (
                    "FILE",
                    {
                        "default": "convert_bc_to_binary_RY.py",
                        "advanced": True,
                        "description": "Path to the bctools convert_bc_to_binary_RY.py executable",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _BctoolsBaseContract(ToolsIUCCommandContract):
    """Shared metadata for bctools Galaxy wrappers."""

    REQUIRED_CONDA_PACKAGES = ["bctools"]
    CATEGORY = "sequence"
    REQUIRED_EXECUTABLES: list[str] = []
    DOCUMENTATION_URL = BCTOOLS_CITATION_URL
    CITATION_DOIS = [BCTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BCTOOLS_CITATION_DOI}", BCTOOLS_CITATION_URL]
    CITATION_TEXT = BCTOOLS_CITATION_TEXT
    VERSION = "0.2.2+galaxy2"
    SHELL = True

    @classmethod
    def _script(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("script_path", cls.REQUIRED_EXECUTABLES[0]) or cls.REQUIRED_EXECUTABLES[0])

    @classmethod
    def _out_path(cls, inputs: dict[str, Any], filename: str) -> str:
        return f"{_out(inputs)}/{filename}"

    @classmethod
    def _plan_paths(cls, output_dir: str | Path, *filenames: str) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / filename for filename in filenames]

    @classmethod
    def _script_input(cls) -> tuple[str, dict[str, Any]]:
        return (
            "FILE",
            {
                "default": cls.REQUIRED_EXECUTABLES[0],
                "advanced": True,
                "description": f"Path to the bctools {cls.REQUIRED_EXECUTABLES[0]} executable",
            },
        )

    @classmethod
    def _base_aliases(cls, *aliases: str) -> list[str]:
        return [BIONODULO_BUILTIN_ALIAS, "bctools", *aliases, "UMI", "barcodes"]

class _BctoolsExtractCrosslinkedNucleotidesContract(_BctoolsBaseContract):
    """Calculate crosslinked nucleotide positions from alignment BED intervals."""

    LEGACY_NODE_ID = "bctools_extract_crosslinked_nucleotides"
    DISPLAY_NAME = "Get crosslinked nucleotides"
    DESCRIPTION = "Calculate crosslinked nucleotide BED coordinates from aligned-read BED intervals."
    SEARCH_ALIASES = _BctoolsBaseContract._base_aliases(
        "Get crosslinked nucleotides",
        "bctools_extract_crosslinked_nucleotides",
        "coords2clnt.py",
        "crosslinking coordinates",
        "threeprime",
    )
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("crosslinking_coordinates",)
    REQUIRED_EXECUTABLES = ["coords2clnt.py"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return cls._out_path(inputs, "crosslinking_coordinates.bed")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [cls._script(inputs)]
        if inputs.get("threeprime", False):
            cmd.append("--threeprime")
        cmd.extend([str(inputs.get("alignment_coordinates", "")), ">", cls._output_path(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return cls._plan_paths(output_dir, "crosslinking_coordinates.bed")

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("alignment_coordinates", "")).strip():
            return "alignment_coordinates is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"alignment_coordinates": ("BED", {"description": "BED alignments"})},
            "optional": {
                "threeprime": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Set crosslink site one nucleotide downstream of the 3-prime end",
                    },
                ),
                "script_path": cls._script_input(),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _BctoolsExtractAlignmentEndsContract(_BctoolsBaseContract):
    """Extract outer alignment coordinates from SAM or BAM."""

    LEGACY_NODE_ID = "bctools_extract_alignment_ends"
    DISPLAY_NAME = "Extract alignment ends"
    DESCRIPTION = "Extract outer alignment-end coordinates from paired SAM or BAM alignments into BED."
    SEARCH_ALIASES = _BctoolsBaseContract._base_aliases(
        "Extract alignment ends",
        "bctools_extract_alignment_ends",
        "extract_aln_ends.py",
        "SAM",
        "BAM",
        "outer coordinates",
    )
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("alignment_ends",)
    REQUIRED_EXECUTABLES = ["extract_aln_ends.py"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return cls._out_path(inputs, "alignment_ends.bed")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        return _shell_join([cls._script(inputs), str(inputs.get("alignments", "")), ">", cls._output_path(inputs)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return cls._plan_paths(output_dir, "alignment_ends.bed")

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("alignments", "")).strip():
            return "alignments is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"alignments": ("FILE", {"description": "SAM or BAM alignments"})},
            "optional": {"script_path": cls._script_input()},
            "hidden": {"output": ("STRING", {})},
        }

class _BctoolsExtractBarcodesContract(_BctoolsBaseContract):
    """Extract barcodes from FASTQ reads according to an X/N pattern."""

    LEGACY_NODE_ID = "bctools_extract_barcodes"
    DISPLAY_NAME = "Extract barcodes"
    DESCRIPTION = "Extract barcode nucleotides from FASTQ reads according to an X/N pattern."
    SEARCH_ALIASES = _BctoolsBaseContract._base_aliases(
        "Extract barcodes",
        "bctools_extract_barcodes",
        "extract_bcs.py",
        "barcode pattern",
        "cleaned reads",
    )
    RETURN_TYPES = ("FASTQ", "FASTQ")
    RETURN_NAMES = ("reads_cleaned", "extracted_barcodes")
    REQUIRED_EXECUTABLES = ["extract_bcs.py"]

    @classmethod
    def _reads_cleaned_path(cls, inputs: dict[str, Any]) -> str:
        return cls._out_path(inputs, "reads_cleaned.fastq")

    @classmethod
    def _extracted_barcodes_path(cls, inputs: dict[str, Any]) -> str:
        return cls._out_path(inputs, "extracted_barcodes.fastq")

    @classmethod
    def _barcode_pattern(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("barcode_pattern", "") or "")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [cls._script(inputs), str(inputs.get("reads", ""))]
        barcode_pattern = cls._barcode_pattern(inputs)
        if barcode_pattern:
            cmd.append(barcode_pattern)
        cmd.extend(["--bcs", cls._extracted_barcodes_path(inputs), ">", cls._reads_cleaned_path(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return cls._plan_paths(output_dir, "reads_cleaned.fastq", "extracted_barcodes.fastq")

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("reads", "")).strip():
            return "reads is required"
        barcode_pattern = cls._barcode_pattern(inputs)
        if any(char not in {"X", "N"} for char in barcode_pattern):
            return "barcode_pattern must contain only X and N"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"reads": ("FASTQ", {"description": "Barcoded FASTQ reads"})},
            "optional": {
                "barcode_pattern": (
                    "STRING",
                    {
                        "default": "",
                        "pattern": "^[XN]*$",
                        "description": "5-prime pattern where X bases are extracted and N bases are retained",
                    },
                ),
                "script_path": cls._script_input(),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _BctoolsMergePcrDuplicatesContract(_BctoolsBaseContract):
    """Merge PCR duplicates by unique molecular identifier."""

    LEGACY_NODE_ID = "bctools_merge_pcr_duplicates"
    DISPLAY_NAME = "Merge PCR duplicates"
    REQUIRED_CONDA_PACKAGES = ["bctools", "coreutils"]
    DESCRIPTION = "Merge PCR duplicates from BED alignments according to FASTQ unique molecular identifiers."
    SEARCH_ALIASES = _BctoolsBaseContract._base_aliases(
        "Merge PCR duplicates",
        "bctools_merge_pcr_duplicates",
        "merge_pcr_duplicates.py",
        "PCR duplicates",
        "unique molecular identifiers",
    )
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("events",)
    REQUIRED_EXECUTABLES = ["merge_pcr_duplicates.py"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return cls._out_path(inputs, "events.bed")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        return _shell_join(
            [
                cls._script(inputs),
                str(inputs.get("alignments_bed", "")),
                str(inputs.get("barcode_library", "")),
                "--outfile",
                cls._output_path(inputs),
            ]
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return cls._plan_paths(output_dir, "events.bed")

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("alignments_bed", "")).strip():
            return "alignments_bed is required"
        if not str(inputs.get("barcode_library", "")).strip():
            return "barcode_library is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "alignments_bed": ("BED", {"description": "BED6 alignments with read IDs"}),
                "barcode_library": ("FASTQ", {"description": "FASTQ UMI barcode library"}),
            },
            "optional": {"script_path": cls._script_input()},
            "hidden": {"output": ("STRING", {})},
        }

class _BctoolsRemoveTailContract(_BctoolsBaseContract):
    """Remove a fixed-length 3-prime tail from FASTQ reads."""

    LEGACY_NODE_ID = "bctools_remove_tail"
    DISPLAY_NAME = "Remove 3'-end nts"
    DESCRIPTION = "Remove a fixed number of nucleotides from the 3-prime tails of FASTQ reads."
    SEARCH_ALIASES = _BctoolsBaseContract._base_aliases(
        "Remove 3'-end nts",
        "bctools_remove_tail",
        "remove_tail.py",
        "3-prime tail",
        "FASTQ trimming",
    )
    RETURN_TYPES = ("FASTQ",)
    RETURN_NAMES = ("default",)
    REQUIRED_EXECUTABLES = ["remove_tail.py"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return cls._out_path(inputs, "default.fastq")

    @classmethod
    def _length(cls, inputs: dict[str, Any]) -> int:
        value = inputs.get("length", 0)
        if value is None or value == "":
            value = 0
        return int(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        return _shell_join(
            [
                cls._script(inputs),
                str(inputs.get("reads_fastq", "")),
                str(cls._length(inputs)),
                ">",
                cls._output_path(inputs),
            ]
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return cls._plan_paths(output_dir, "default.fastq")

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("reads_fastq", "")).strip():
            return "reads_fastq is required"
        try:
            length = cls._length(inputs)
        except (TypeError, ValueError):
            return "length must be an integer"
        if length < 0:
            return "length must be >= 0"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"reads_fastq": ("FASTQ", {"description": "FASTQ reads"})},
            "optional": {
                "length": ("INT", {"default": 0, "min": 0, "description": "Number of 3-prime bases to remove"}),
                "script_path": cls._script_input(),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _BctoolsRemoveSpuriousEventsContract(_BctoolsBaseContract):
    """Remove low-support crosslinking events caused by UMI errors."""

    LEGACY_NODE_ID = "bctools_remove_spurious_events"
    DISPLAY_NAME = "Remove spurious"
    REQUIRED_CONDA_PACKAGES = ["bctools", "coreutils"]
    DESCRIPTION = "Remove spurious crosslinking events caused by UMI errors from BED intervals."
    SEARCH_ALIASES = _BctoolsBaseContract._base_aliases(
        "Remove spurious",
        "bctools_remove_spurious_events",
        "rm_spurious_events.py",
        "spurious events",
        "crosslinking events",
        "threshold",
    )
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("events_filtered",)
    REQUIRED_EXECUTABLES = ["rm_spurious_events.py"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return cls._out_path(inputs, "events_filtered.bed")

    @classmethod
    def _threshold(cls, inputs: dict[str, Any]) -> float:
        value = inputs.get("threshold", 0.1)
        if value is None or value == "":
            value = 0.1
        return float(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        return _shell_join(
            [
                cls._script(inputs),
                str(inputs.get("events", "")),
                "--threshold",
                str(cls._threshold(inputs)),
                "--outfile",
                cls._output_path(inputs),
            ]
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return cls._plan_paths(output_dir, "events_filtered.bed")

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("events", "")).strip():
            return "events is required"
        try:
            threshold = cls._threshold(inputs)
        except (TypeError, ValueError):
            return "threshold must be a number"
        if threshold < 0:
            return "threshold must be >= 0"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"events": ("BED", {"description": "BED6 crosslinking events"})},
            "optional": {
                "threshold": (
                    "FLOAT",
                    {
                        "default": 0.1,
                        "min": 0,
                        "description": "Fraction of the maximum count used to remove low-support events",
                    },
                ),
                "script_path": cls._script_input(),
            },
            "hidden": {"output": ("STRING", {})},
        }
