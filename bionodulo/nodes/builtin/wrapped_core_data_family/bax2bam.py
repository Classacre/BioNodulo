"""Focused bax2bam node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from .evidence import pin_contract

class Bax2BamNode(CommandNode):
    """Convert legacy PacBio bax.h5 basecall files to BAM."""

    NODE_ID = "bax2bam"
    DISPLAY_NAME = "bax2bam"
    REQUIRED_CONDA_PACKAGES = ["bax2bam"]
    CATEGORY = "conversion"
    DESCRIPTION = "Convert PacBio basecall format bax.h5 files into BAM."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "bax2bam",
        "PacBio",
        "bax.h5",
        "basecall format",
        "BAM basecall",
        "subreads",
        "hqregion",
        "polymerase read",
        "scraps BAM",
        "pulse features",
        "Pacific Biosciences",
    ]
    RETURN_TYPES = ("BAM", "BAM", "BAM", "BAM", "BAM")
    RETURN_NAMES = (
        "output_scrap",
        "output_subread",
        "output_hqregion",
        "output_lqregion",
        "output_polymeraseread",
    )
    REQUIRED_EXECUTABLES = ["bax2bam"]
    DOCUMENTATION_URL = BAX2BAM_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [BAX2BAM_CITATION_URL]
    CITATION_TEXT = BAX2BAM_CITATION_TEXT
    VERSION = "0.0.11+galaxy0"
    SHELL = True

    READTYPE_OPTIONS = ["--hqregion", "--polymeraseread", "--subread"]
    PULSEFEATURE_OPTIONS = [
        "DeletionQV",
        "DeletionTag",
        "InsertionQV",
        "IPD",
        "MergeQV",
        "PulseWidth",
        "SubstitutionQV",
        "SubstitutionTag",
    ]
    DEFAULT_PULSEFEATURES = [
        "DeletionQV",
        "DeletionTag",
        "InsertionQV",
        "IPD",
        "MergeQV",
        "PulseWidth",
        "SubstitutionQV",
    ]

    @classmethod
    def _readtype(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("readtype", "--subread") or "--subread")

    @classmethod
    def _pulsefeatures(cls, inputs: dict[str, Any]) -> list[str]:
        selected = inputs.get("pulsefeatures", cls.DEFAULT_PULSEFEATURES)
        values = _as_list(selected)
        return values if values else []

    @classmethod
    def _output_prefix(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["bax2bam"]
        cmd.extend(_as_list(inputs.get("files")))
        cmd.extend(["-o", cls._output_prefix(inputs), cls._readtype(inputs)])
        pulsefeatures = cls._pulsefeatures(inputs)
        if pulsefeatures:
            cmd.append(f"--pulsefeatures={','.join(pulsefeatures)}")
        if inputs.get("losslessframes"):
            cmd.append("--losslessframes")
        if inputs.get("internal"):
            cmd.append("--internal")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        match cls._readtype(inputs):
            case "--hqregion":
                return [out / "output.hqregions.bam", out / "output.lqregions.bam"]
            case "--polymeraseread":
                return [out / "output.polymerase.bam"]
            case _:
                return [out / "output.scraps.bam", out / "output.subreads.bam"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not _as_list(inputs.get("files")):
            return "files is required"
        if cls._readtype(inputs) not in cls.READTYPE_OPTIONS:
            return f"readtype must be one of: {', '.join(cls.READTYPE_OPTIONS)}"
        if any(feature not in cls.PULSEFEATURE_OPTIONS for feature in cls._pulsefeatures(inputs)):
            return "pulsefeatures must be selected from supported PacBio pulse features"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "files": (
                    "FILE",
                    {"is_list": True, "description": "PacBio bax.h5 files from the same movie"},
                ),
            },
            "optional": {
                "readtype": (
                    "STRING",
                    {
                        "default": "--subread",
                        "options": cls.READTYPE_OPTIONS,
                        "description": "Output read type to produce",
                    },
                ),
                "pulsefeatures": (
                    "STRING",
                    {
                        "default": cls.DEFAULT_PULSEFEATURES,
                        "options": cls.PULSEFEATURE_OPTIONS,
                        "is_list": True,
                        "description": "Pulse features to include in the output BAM",
                    },
                ),
                "losslessframes": (
                    "BOOLEAN",
                    {"default": False, "description": "Store full 16-bit IPD and PulseWidth data"},
                ),
                "internal": (
                    "BOOLEAN",
                    {"default": False, "description": "Include non-sequencing ZMWs in the scraps BAM when applicable"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

pin_contract(Bax2BamNode)

__all__ = ['Bax2BamNode']
