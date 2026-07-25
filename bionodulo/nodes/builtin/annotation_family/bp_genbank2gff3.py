"""Focused genbank gff node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.wrapped_core_data_family.evidence import pin_contract

class BpGenbank2Gff3Node(CommandNode):
    """Convert GenBank flat files to GFF3 with BioPerl."""

    NODE_ID = "bp_genbank2gff3"
    DISPLAY_NAME = "Genbank to GFF3"
    REQUIRED_CONDA_PACKAGES = ["perl-bioperl"]
    CATEGORY = "annotation"
    DESCRIPTION = "Convert GenBank flat files to GFF3 with BioPerl."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "bp_genbank2gff3",
        "Genbank to GFF3",
        "GenBank",
        "GFF3",
        "BioPerl",
        "Unflattener",
        "Sequence Ontology",
        "Bio::Tools::GFF",
    ]
    RETURN_TYPES = ("GFF3",)
    RETURN_NAMES = ("gff3",)
    REQUIRED_EXECUTABLES = ["bp_genbank2gff3.pl"]
    DOCUMENTATION_URL = "https://bioperl.org/"
    CITATION_DOIS = [BP_GENBANK2GFF3_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BP_GENBANK2GFF3_CITATION_DOI}"]
    CITATION_TEXT = BP_GENBANK2GFF3_CITATION_TEXT
    VERSION = "1.1"
    SHELL = True

    SOFILE_OPTIONS = ["__none__", "live", "url"]
    ERROR_THRESHOLDS = ["0", "1", "2", "3"]
    MODELS = ["--CDS", "--noCDS"]

    @classmethod
    def _sofile(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("sofile", "__none__") or "__none__")

    @classmethod
    def _ethresh(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("ethresh", "1") or "1")

    @classmethod
    def _model(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("model", "--CDS") or "--CDS")

    @classmethod
    def _typesource(cls, inputs: dict[str, Any]) -> str:
        value = inputs.get("typesource", "contig")
        if value is None:
            return "contig"
        return str(value)

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/gff3.gff3"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["bp_genbank2gff3.pl"]
        if inputs.get("infer_subfeatures", True) is False:
            cmd.append("--noinfer")
        sofile = cls._sofile(inputs)
        if sofile == "url":
            cmd.extend(["--sofile", str(inputs.get("so_url", ""))])
        elif sofile == "live":
            cmd.extend(["--sofile", "live"])
        cmd.extend(
            [
                "--outdir",
                "-",
                "--ethresh",
                cls._ethresh(inputs),
                cls._model(inputs),
                "--typesource",
                cls._typesource(inputs),
                str(inputs.get("genbank", "")),
                ">",
                cls._output_path(inputs),
            ]
        )
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "gff3.gff3"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("genbank", "")).strip():
            return "genbank is required"
        sofile = cls._sofile(inputs)
        if sofile not in cls.SOFILE_OPTIONS:
            return f"sofile must be one of: {', '.join(cls.SOFILE_OPTIONS)}"
        if sofile == "url" and not str(inputs.get("so_url", "")).strip():
            return "so_url is required when sofile is url"
        ethresh = cls._ethresh(inputs)
        if ethresh not in cls.ERROR_THRESHOLDS:
            return f"ethresh must be one of: {', '.join(cls.ERROR_THRESHOLDS)}"
        model = cls._model(inputs)
        if model not in cls.MODELS:
            return f"model must be one of: {', '.join(cls.MODELS)}"
        if not cls._typesource(inputs).strip():
            return "typesource is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "genbank": ("FILE", {"description": "GenBank flat file to convert to GFF3"}),
            },
            "optional": {
                "infer_subfeatures": (
                    "BOOLEAN",
                    {"default": True, "description": "Infer exon and mRNA subfeatures"},
                ),
                "sofile": (
                    "STRING",
                    {
                        "default": "__none__",
                        "options": cls.SOFILE_OPTIONS,
                        "description": "Sequence Ontology source",
                    },
                ),
                "so_url": (
                    "STRING",
                    {"default": "", "description": "Sequence Ontology OBO URL when sofile is url"},
                ),
                "ethresh": (
                    "STRING",
                    {
                        "default": "1",
                        "options": cls.ERROR_THRESHOLDS,
                        "description": "Error threshold for the BioPerl unflattener",
                    },
                ),
                "model": (
                    "STRING",
                    {"default": "--CDS", "options": cls.MODELS, "description": "GFF3 gene model"},
                ),
                "typesource": (
                    "STRING",
                    {"default": "contig", "description": "Sequence Ontology type for the landmark feature"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

pin_contract(BpGenbank2Gff3Node)

__all__ = ['BpGenbank2Gff3Node']
