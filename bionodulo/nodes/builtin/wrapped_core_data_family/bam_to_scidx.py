"""Focused bam to scidx node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from .evidence import pin_contract

class BamToScidxNode(CommandNode):
    """Convert BAM data to Strand-specific coordinate count ScIdx files."""

    NODE_ID = "bam_to_scidx"
    DISPLAY_NAME = "Convert BAM to ScIdx"
    REQUIRED_CONDA_PACKAGES = ["openjdk"]
    CATEGORY = "chip_seq"
    DESCRIPTION = "Convert BAM alignments to Strand-specific coordinate count ScIdx format."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "bam_to_scidx",
        "BAM to ScIdx",
        "ScIdx",
        "strand-specific coordinate count",
        "ChIP-exo",
        "GeneTrack",
        "MultiGPS",
        "BAMtoscIDX",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["java"]
    DOCUMENTATION_URL = BAM_TO_SCIDX_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [BAM_TO_SCIDX_CITATION_URL]
    CITATION_TEXT = BAM_TO_SCIDX_CITATION_TEXT
    VERSION = "1.0.1"
    SHELL = True

    PROPER_MATE_PAIRING = ["1", "0"]
    READS = ["0", "1", "2"]

    @classmethod
    def _proper_mate_pairing(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("require_proper_mate_pairing", "1") or "1")

    @classmethod
    def _read(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("read", "0") or "0")

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.scidx"

    @classmethod
    def _optional_int(cls, inputs: dict[str, Any], key: str) -> int | None:
        value = inputs.get(key)
        if value is None or str(value) == "":
            return None
        return int(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "ln",
            "-s",
            str(inputs.get("input_bam", "")),
            "localbam.bam",
            "&&",
            "ln",
            "-f",
            "-s",
            str(inputs.get("bam_index", "")),
            "localbam.bam.bai",
            "&&",
            "java",
            "-jar",
            str(inputs.get("jar_path", "BAMtoscIDX.jar") or "BAMtoscIDX.jar"),
            "-b",
            "localbam.bam",
            "-i",
            "localbam.bam.bai",
            "-p",
            cls._proper_mate_pairing(inputs),
            "-r",
            cls._read(inputs),
        ]
        min_insert_size = cls._optional_int(inputs, "min_insert_size")
        if min_insert_size is not None:
            cmd.extend(["-m", str(min_insert_size)])
        max_insert_size = cls._optional_int(inputs, "max_insert_size")
        if max_insert_size is not None:
            cmd.extend(["-M", str(max_insert_size)])
        cmd.extend(["-o", cls._output_path(inputs), "1>/dev/null"])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.scidx"]

    @classmethod
    def _validate_insert_size(cls, inputs: dict[str, Any], key: str) -> bool | str:
        try:
            value = cls._optional_int(inputs, key)
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if value is not None and value < 0:
            return f"{key} must be greater than or equal to 0"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_bam", "")).strip():
            return "input_bam is required"
        if not str(inputs.get("bam_index", "")).strip():
            return "bam_index is required"
        read = cls._read(inputs)
        if read not in cls.READS:
            return f"read must be one of: {', '.join(cls.READS)}"
        proper_mate_pairing = cls._proper_mate_pairing(inputs)
        if proper_mate_pairing not in cls.PROPER_MATE_PAIRING:
            return f"require_proper_mate_pairing must be one of: {', '.join(cls.PROPER_MATE_PAIRING)}"
        for key in ("min_insert_size", "max_insert_size"):
            validation = cls._validate_insert_size(inputs, key)
            if validation is not True:
                return validation
        min_insert_size = cls._optional_int(inputs, "min_insert_size")
        max_insert_size = cls._optional_int(inputs, "max_insert_size")
        if min_insert_size is not None and max_insert_size is not None and max_insert_size < min_insert_size:
            return "max_insert_size must be greater than or equal to min_insert_size"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bam": ("BAM", {"description": "Input BAM file"}),
                "bam_index": ("BAI", {"description": "BAM index file for the input BAM"}),
            },
            "optional": {
                "require_proper_mate_pairing": (
                    "STRING",
                    {
                        "default": "1",
                        "options": cls.PROPER_MATE_PAIRING,
                        "description": "Require proper mate-pairing when filtering by insert size",
                    },
                ),
                "read": (
                    "STRING",
                    {"default": "0", "options": cls.READS, "description": "Read to output: 0 Read1, 1 Read2, or 2 combined"},
                ),
                "min_insert_size": ("INT", {"default": "", "min": 0, "description": "Minimum insert size to output"}),
                "max_insert_size": ("INT", {"default": "", "min": 0, "description": "Maximum insert size to output"}),
                "jar_path": (
                    "FILE",
                    {"default": "BAMtoscIDX.jar", "advanced": True, "description": "Path to BAMtoscIDX.jar"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

pin_contract(BamToScidxNode)

__all__ = ['BamToScidxNode']
