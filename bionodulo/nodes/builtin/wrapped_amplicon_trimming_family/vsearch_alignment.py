"""Focused VSEARCH all-pairs alignment node."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from .evidence import pin_contract
from .vsearch_adapter import VSEARCH_USERFIELDS, VSearchNodeBase


class VSearchAlignmentNode(VSearchNodeBase):
    """Compute all-pairs global alignments with VSEARCH."""

    NODE_ID = "vsearch_alignment"
    DISPLAY_NAME = "VSEARCH Alignment"
    REQUIRED_CONDA_PACKAGES = ["vsearch"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Compute all-pairs global alignments for FASTA sequences with VSEARCH and optional tabular user fields."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "vsearch",
        "alignment",
        "allpairs_global",
        "pairwise alignment",
        "alnout",
        "userfields",
    ]
    RETURN_TYPES = ("STATS_FILE", "TSV")
    RETURN_NAMES = ("alignments", "userfields")
    REQUIRED_EXECUTABLES = ["vsearch"]
    DOCUMENTATION_URL = "https://github.com/torognes/vsearch"
    CITATION_DOIS = ["10.7717/peerj.2584"]
    CITATION_URLS = ["https://doi.org/10.7717/peerj.2584"]
    CITATION_TEXT = "VSEARCH: a versatile open source tool for metagenomics."
    VERSION = "2.8.3.0"
    USERFIELD_OPTIONS = VSEARCH_USERFIELDS

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = cls._general_command(inputs)
        if inputs.get("acceptall"):
            cmd.append("--acceptall")
        cmd.extend([
            "--id",
            str(inputs.get("id", inputs.get("identity", 0.97))),
            "--iddef",
            str(inputs.get("iddef", 2)),
            "--allpairs_global",
            str(inputs.get("infile", inputs.get("sequences", ""))),
            "--alnout",
            f"{_out(inputs)}/alignments.txt",
        ])
        _add_if_value(cmd, "--query_cov", inputs.get("query_cov"))

        if inputs.get("userfields_output_select") == "yes":
            userfields = _as_list(inputs.get("userfields"))
            if not userfields:
                userfields = ["evalue", "query", "target"]
            cmd.extend([
                "--userfields",
                "+".join(userfields),
                "--userout",
                f"{_out(inputs)}/userfields.tsv",
            ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "alignments.txt"]
        if inputs.get("userfields_output_select") == "yes":
            outputs.append(out / "userfields.tsv")
        return outputs

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Path]:
        names = {
            "alignments.txt": "alignments",
            "userfields.tsv": "userfields",
        }
        return {names[path.name]: path for path in planned_paths}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("infile", inputs.get("sequences", ""))).strip():
            return "infile is required"
        try:
            identity = float(inputs.get("id", inputs.get("identity", 0.97)))
        except (TypeError, ValueError):
            return "id must be a number"
        if not 0 <= identity <= 1:
            return "id must be between 0 and 1"
        if str(inputs.get("iddef", "2")) not in {"0", "1", "2", "3", "4"}:
            return "iddef must be one of: 0, 1, 2, 3, 4"
        query_cov = inputs.get("query_cov")
        if query_cov is not None and str(query_cov) != "":
            try:
                coverage = float(query_cov)
            except (TypeError, ValueError):
                return "query_cov must be a number"
            if not 0 <= coverage <= 1:
                return "query_cov must be between 0 and 1"
        userfields_select = str(inputs.get("userfields_output_select", "no"))
        if userfields_select not in {"no", "yes"}:
            return "userfields_output_select must be one of: no, yes"
        fields = _as_list(inputs.get("userfields"))
        unsupported = [field for field in fields if field not in cls.USERFIELD_OPTIONS]
        if unsupported:
            return f"userfields contains unsupported values: {', '.join(unsupported)}"
        return cls._validate_common(inputs)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "infile": ("FASTA", {"description": "FASTA sequences for all-pairs global alignment"}),
            },
            "optional": {
                "id": ("FLOAT", {"default": 0.97, "min": 0, "max": 1, "description": "Minimum pairwise identity"}),
                "iddef": ("STRING", {"default": "2", "options": ["0", "1", "2", "3", "4"], "description": "VSEARCH identity definition"}),
                "acceptall": ("BOOLEAN", {"default": False, "description": "Output all pairwise alignments"}),
                "query_cov": ("FLOAT", {"default": "", "min": 0, "max": 1, "description": "Minimum aligned query fraction"}),
                "userfields_output_select": ("STRING", {"default": "no", "options": ["no", "yes"], "description": "Write tabular user fields"}),
                "userfields": (
                    "STRING",
                    {
                        "default": ["evalue", "query", "target"],
                        "list": True,
                        "options": list(cls.USERFIELD_OPTIONS),
                        "description": "Fields for optional tabular VSEARCH output",
                    },
                ),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


pin_contract(VSearchAlignmentNode)
