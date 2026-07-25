"""Focused bigwig node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.wrapped_core_data_family.evidence import pin_contract

class BBGToBigWigNode(CommandNode):
    """Convert BAM, BED, or GFF coverage to a bigWig track."""

    NODE_ID = "bbgtobigwig"
    DISPLAY_NAME = "BAM BED GFF coverage bigWigs"
    REQUIRED_CONDA_PACKAGES = ["ucsc-bedgraphtobigwig", "bedtools", "coreutils", "python"]
    CATEGORY = "genomics"
    DESCRIPTION = "Convert BAM, BED, or GFF coverage over a reference genome into a bigWig track."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "bbgtobigwig",
        "BAM BED GFF coverage bigWigs",
        "bigWig",
        "bedGraphToBigWig",
        "bedtools genomecov",
        "coverage tracks",
        "JBrowse2",
        "UCSC Genome Browser Utilities",
    ]
    RETURN_TYPES = ("BIGWIG",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["bedtools", "bedGraphToBigWig", "python"]
    DOCUMENTATION_URL = f"{DOI_URL}{BBG_TO_BIGWIG_CITATION_DOI}"
    CITATION_DOIS = [BBG_TO_BIGWIG_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BBG_TO_BIGWIG_CITATION_DOI}"]
    CITATION_TEXT = BBG_TO_BIGWIG_CITATION_TEXT
    VERSION = "0.1"
    SHELL = True

    GENOSRC_OPTIONS = ["indexed", "history"]
    INPUT_FORMAT_OPTIONS = ["auto", "bam", "bed", "gff", "gff3"]

    @classmethod
    def _genosrc(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("genosrc", "history") or "history")

    @classmethod
    def _input_format(cls, inputs: dict[str, Any]) -> str:
        selected = str(inputs.get("input_format", "auto") or "auto").lower()
        if selected != "auto":
            return selected
        ext = _bedtools_ext(inputs.get("input1"), default="")
        if ext == "unsorted.bam":
            return "bam"
        if ext in {"bam", "bed", "gff", "gff3"}:
            return ext
        return ""

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.bigwig"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "ln",
            "-s",
            str(inputs.get("chromfile", "")),
            "./CHROMFILE",
            "&&",
        ]
        input_format = cls._input_format(inputs)
        if input_format in {"gff", "gff3"}:
            cmd.extend(
                [
                    "python",
                    str(inputs.get("converter_script", "gff_to_bed_converter.py") or "gff_to_bed_converter.py"),
                    "<",
                    str(inputs.get("input1", "")),
                    ">",
                    "input2",
                    "&&",
                ]
            )
        else:
            cmd.extend(["ln", "-s", str(inputs.get("input1", "")), "input2", "&&"])
        cmd.extend(["bedtools", "genomecov", "-bg"])
        if input_format == "bam":
            cmd.extend(["-split", "-ibam", "input2"])
        else:
            cmd.extend(["-i", "input2", "-g", "./CHROMFILE"])
        cmd.extend(
            [
                "|",
                "LC_COLLATE=C",
                "sort",
                "-k1,1",
                "-k2,2n",
                ">",
                "temp.bg",
                "&&",
                "bedGraphToBigWig",
                "temp.bg",
                "./CHROMFILE",
                cls._output_path(inputs),
            ]
        )
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.bigwig"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input1", "")).strip():
            return "input1 is required"
        if not str(inputs.get("chromfile", "")).strip():
            return "chromfile is required"
        genosrc = cls._genosrc(inputs)
        if genosrc not in cls.GENOSRC_OPTIONS:
            return f"genosrc must be one of: {', '.join(cls.GENOSRC_OPTIONS)}"
        selected = str(inputs.get("input_format", "auto") or "auto").lower()
        if selected not in cls.INPUT_FORMAT_OPTIONS:
            return f"input_format must be one of: {', '.join(cls.INPUT_FORMAT_OPTIONS)}"
        if not cls._input_format(inputs):
            return "input_format could not be auto-detected from input1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input1": ("FILE", {"description": "BAM, BED, GFF, or GFF3 file to convert to bigWig coverage"}),
                "chromfile": (
                    "FILE",
                    {"description": "Chromosome lengths file or built-in reference genome length table"},
                ),
            },
            "optional": {
                "genosrc": (
                    "STRING",
                    {
                        "default": "history",
                        "options": cls.GENOSRC_OPTIONS,
                        "description": "Whether chromosome lengths come from a built-in/indexed genome or history file",
                    },
                ),
                "input_format": (
                    "STRING",
                    {
                        "default": "auto",
                        "options": cls.INPUT_FORMAT_OPTIONS,
                        "description": "Input format; auto detects from input1 extension",
                    },
                ),
                "converter_script": (
                    "FILE",
                    {
                        "default": "gff_to_bed_converter.py",
                        "advanced": True,
                        "description": "Galaxy helper script that converts GFF/GFF3 to BED before coverage",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

pin_contract(BBGToBigWigNode)

__all__ = ['BBGToBigWigNode']
