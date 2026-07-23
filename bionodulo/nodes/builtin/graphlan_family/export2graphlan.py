"""Focused export2graphlan node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin._variant_assembly_contracts import pin_contract

class Export2GraphlanNode(CommandNode):
    """Convert tabular taxonomic profiles into GraPhlAn tree and annotation files."""

    NODE_ID = "export2graphlan"
    DISPLAY_NAME = "Export to GraPhlAn"
    REQUIRED_CONDA_PACKAGES = ["export2graphlan"]
    CATEGORY = "visualization"
    DESCRIPTION = "Convert MetaPhlAn, LEfSe, or HUMAnN profiles into GraPhlAn tree and annotation inputs."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "export2graphlan",
        "export2graphlan GraPhlAn conversion",
        "GraPhlAn annotation",
        "LEfSe to GraPhlAn",
        "MetaPhlAn tree visualization",
        "taxonomic profile visualization",
    ]
    RETURN_TYPES = ("TXT", "TXT")
    RETURN_NAMES = ("tree", "annotation")
    REQUIRED_EXECUTABLES = ["export2graphlan.py"]
    DOCUMENTATION_URL = "https://github.com/SegataLab/export2graphlan/"
    CITATION_DOIS = ["10.7717/peerj.1029"]
    CITATION_URLS = [f"{DOI_URL}10.7717/peerj.1029"]
    CITATION_TEXT = "Compact graphical representation of phylogenetic data and metadata with GraPhlAn."
    VERSION = "0.20"

    TEXT_OPTIONS = [
        ("annotations", "--annotations"),
        ("external_annotations", "--external_annotations"),
        ("background_levels", "--background_levels"),
        ("background_clades", "--background_clades"),
        ("background_colors", "--background_colors"),
        ("title", "--title"),
    ]
    INT_OPTIONS = [
        ("title_font_size", "--title_font_size"),
        ("def_clade_size", "--def_clade_size"),
        ("min_clade_size", "--min_clade_size"),
        ("max_clade_size", "--max_clade_size"),
        ("def_font_size", "--def_font_size"),
        ("min_font_size", "--min_font_size"),
        ("max_font_size", "--max_font_size"),
        ("annotation_legend_font_size", "--annotation_legend_font_size"),
        ("most_abundant", "--most_abundant"),
        ("least_biomarkers", "--least_biomarkers"),
        ("fname_row", "--fname_row"),
        ("sname_row", "--sname_row"),
        ("metadata_rows", "--metadata_rows"),
        ("stop", "--stop"),
        ("ftop", "--ftop"),
    ]
    FLOAT_OPTIONS = [
        ("abundance_threshold", "--abundance_threshold"),
        ("sperc", "--sperc"),
        ("fperc", "--fperc"),
    ]
    POSITIVE_INT_OPTIONS = {
        "title_font_size",
        "def_clade_size",
        "min_clade_size",
        "max_clade_size",
        "def_font_size",
        "min_font_size",
        "max_font_size",
        "annotation_legend_font_size",
        "most_abundant",
        "least_biomarkers",
        "stop",
        "ftop",
    }
    COMMAND_OPTION_ORDER = [
        *TEXT_OPTIONS,
        ("title_font_size", "--title_font_size"),
        ("def_clade_size", "--def_clade_size"),
        ("min_clade_size", "--min_clade_size"),
        ("max_clade_size", "--max_clade_size"),
        ("def_font_size", "--def_font_size"),
        ("min_font_size", "--min_font_size"),
        ("max_font_size", "--max_font_size"),
        ("annotation_legend_font_size", "--annotation_legend_font_size"),
        ("abundance_threshold", "--abundance_threshold"),
        ("most_abundant", "--most_abundant"),
        ("least_biomarkers", "--least_biomarkers"),
        ("fname_row", "--fname_row"),
        ("sname_row", "--sname_row"),
        ("metadata_rows", "--metadata_rows"),
        ("skip_rows", "--skip_rows"),
        ("sperc", "--sperc"),
        ("fperc", "--fperc"),
        ("stop", "--stop"),
        ("ftop", "--ftop"),
    ]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = [
            "export2graphlan.py",
            "--lefse_input",
            str(inputs.get("lefse_input", "")),
        ]
        _add_if_value(cmd, "--lefse_output", inputs.get("lefse_output"))
        cmd.extend(["-t", f"{out}/tree.txt", "-a", f"{out}/annotation.txt"])
        for name, flag in cls.COMMAND_OPTION_ORDER:
            _add_if_value(cmd, flag, inputs.get(name))
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "tree.txt", out / "annotation.txt"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "lefse_input": ("FILE", {"description": "LEfSe-style, MetaPhlAn, or HUMAnN tabular profile input"}),
            },
            "optional": {
                "lefse_output": ("FILE", {"default": "", "description": "Optional LEfSe biomarker result table"}),
                "annotations": ("STRING", {"default": "", "description": "Comma-separated levels to annotate in the tree"}),
                "external_annotations": (
                    "STRING",
                    {"default": "", "description": "Comma-separated levels that use an external annotation legend"},
                ),
                "background_levels": ("STRING", {"default": "", "description": "Comma-separated levels to shade in the background"}),
                "background_clades": ("STRING", {"default": "", "description": "Comma-separated clades to shade in the background"}),
                "background_colors": ("STRING", {"default": "", "description": "Comma-separated RGB or HSV background colors"}),
                "title": ("STRING", {"default": "", "description": "GraPhlAn plot title"}),
                "title_font_size": ("INT", {"default": "", "min": 1}),
                "def_clade_size": ("INT", {"default": "", "min": 1}),
                "min_clade_size": ("INT", {"default": "", "min": 1}),
                "max_clade_size": ("INT", {"default": "", "min": 1}),
                "def_font_size": ("INT", {"default": "", "min": 1}),
                "min_font_size": ("INT", {"default": "", "min": 1}),
                "max_font_size": ("INT", {"default": "", "min": 1}),
                "annotation_legend_font_size": ("INT", {"default": "", "min": 1}),
                "abundance_threshold": ("FLOAT", {"default": "", "min": 0}),
                "most_abundant": ("INT", {"default": "", "min": 1}),
                "least_biomarkers": ("INT", {"default": "", "min": 1}),
                "fname_row": ("INT", {"default": "", "min": -1, "description": "Feature-name row index; -1 means absent"}),
                "sname_row": ("INT", {"default": "", "min": -1, "description": "Sample-name row index; -1 means absent"}),
                "metadata_rows": ("INT", {"default": "", "min": 0}),
                "skip_rows": ("STRING", {"default": "", "description": "Comma-separated 0-based row indexes to skip"}),
                "sperc": ("FLOAT", {"default": "", "min": 0, "max": 100}),
                "fperc": ("FLOAT", {"default": "", "min": 0, "max": 100}),
                "stop": ("INT", {"default": "", "min": 1}),
                "ftop": ("INT", {"default": "", "min": 1}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("lefse_input", "")).strip():
            return "lefse_input is required"
        for name, _ in cls.INT_OPTIONS:
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if name in cls.POSITIVE_INT_OPTIONS and value < 1:
                return f"{name} must be >= 1"
            if name in {"fname_row", "sname_row"} and value < -1:
                return f"{name} must be >= -1"
            if name == "metadata_rows" and value < 0:
                return "metadata_rows must be >= 0"
        for name, _ in cls.FLOAT_OPTIONS:
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                return f"{name} must be a number"
            if value < 0:
                return f"{name} must be >= 0"
            if name in {"sperc", "fperc"} and value > 100:
                return f"{name} must be <= 100"
        skip_rows = str(inputs.get("skip_rows", "") or "")
        if skip_rows and not re.fullmatch(r"\d+(,\d+)*", skip_rows):
            return "skip_rows must be comma-separated integer row indexes"
        return super().VALIDATE_INPUTS(inputs)

pin_contract(Export2GraphlanNode)

__all__ = ['Export2GraphlanNode']
