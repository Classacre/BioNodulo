"""Focused VSEARCH chimera-detection node."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from .evidence import pin_contract
from .vsearch_adapter import VSearchNodeBase


class VSearchChimeraDetectionNode(VSearchNodeBase):
    """Detect chimeric FASTA sequences with VSEARCH UCHIME modes."""

    NODE_ID = "vsearch_chimera_detection"
    DISPLAY_NAME = "VSEARCH Chimera Detection"
    REQUIRED_CONDA_PACKAGES = ["vsearch"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Detect chimeric FASTA sequences with VSEARCH uchime_denovo or uchime_ref and optional UCHIME reports."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "vsearch",
        "chimera",
        "chimera detection",
        "uchime_denovo",
        "uchime_ref",
        "uchimeout",
        "nonchimeras",
    ]
    RETURN_TYPES = ("FASTA", "FASTA", "STATS_FILE", "TSV")
    RETURN_NAMES = ("chimeras", "nonchimeras", "uchime_alignments", "uchimeout")
    REQUIRED_EXECUTABLES = ["vsearch"]
    DOCUMENTATION_URL = "https://github.com/torognes/vsearch"
    CITATION_DOIS = ["10.7717/peerj.2584"]
    CITATION_URLS = ["https://doi.org/10.7717/peerj.2584"]
    CITATION_TEXT = "VSEARCH: a versatile open source tool for metagenomics."
    VERSION = "2.8.3.0"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = cls._general_command(inputs)
        cmd.extend([
            "--abskew",
            str(inputs.get("abskew", 2.0)),
            "--chimeras",
            f"{_out(inputs)}/chimeras.fasta",
            "--dn",
            str(inputs.get("dn", 1.4)),
            "--mindiffs",
            str(inputs.get("mindiffs", 3)),
            "--mindiv",
            str(inputs.get("mindiv", 0.8)),
            "--minh",
            str(inputs.get("minh", 0.28)),
            "--xn",
            str(inputs.get("xn", 8.0)),
        ])
        if inputs.get("self_param"):
            cmd.append("--self")
        if inputs.get("selfid_param"):
            cmd.append("--selfid")

        detection_mode = str(inputs.get("detection_mode", inputs.get("detection_mode_select", "denovo")))
        if detection_mode == "reference":
            cmd.extend([
                "--uchime_ref",
                str(inputs.get("infile_reference", inputs.get("infile", ""))),
                "--db",
                str(inputs.get("db", "")),
            ])
        else:
            cmd.extend(["--uchime_denovo", str(inputs.get("infile_denovo", inputs.get("infile", "")))])

        outputs = set(_as_list(inputs.get("outputs")))
        if "nonchimeras" in outputs:
            cmd.extend(["--nonchimeras", f"{_out(inputs)}/nonchimeras.fasta"])
        if "uchimealns" in outputs:
            cmd.extend(["--uchimealns", f"{_out(inputs)}/uchime_alignments.txt"])
        if "uchimeout" in outputs:
            cmd.extend(["--uchimeout", f"{_out(inputs)}/uchimeout.tsv"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "chimeras.fasta"]
        requested = set(_as_list(inputs.get("outputs")))
        if "nonchimeras" in requested:
            outputs.append(out / "nonchimeras.fasta")
        if "uchimealns" in requested:
            outputs.append(out / "uchime_alignments.txt")
        if "uchimeout" in requested:
            outputs.append(out / "uchimeout.tsv")
        return outputs

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Path]:
        names = {
            "chimeras.fasta": "chimeras",
            "nonchimeras.fasta": "nonchimeras",
            "uchime_alignments.txt": "uchime_alignments",
            "uchimeout.tsv": "uchimeout",
        }
        return {names[path.name]: path for path in planned_paths}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        detection_mode = str(inputs.get("detection_mode", inputs.get("detection_mode_select", "denovo")))
        if detection_mode not in {"denovo", "reference"}:
            return "detection_mode must be one of: denovo, reference"
        if detection_mode == "denovo":
            if not str(inputs.get("infile_denovo", inputs.get("infile", ""))).strip():
                return "infile_denovo is required for denovo mode"
        else:
            if not str(inputs.get("infile_reference", inputs.get("infile", ""))).strip():
                return "infile_reference is required for reference mode"
            if not str(inputs.get("db", "")).strip():
                return "db is required for reference mode"
        requested = _as_list(inputs.get("outputs"))
        unsupported = [name for name in requested if name not in {"nonchimeras", "uchimealns", "uchimeout"}]
        if unsupported:
            return f"outputs contains unsupported values: {', '.join(unsupported)}"
        for name in ("abskew", "dn", "xn", "mindiv", "minh"):
            try:
                value = float(inputs.get(name, {"abskew": 2.0, "dn": 1.4, "xn": 8.0, "mindiv": 0.8, "minh": 0.28}[name]))
            except (TypeError, ValueError):
                return f"{name} must be a number"
            if value < 0:
                return f"{name} must be >= 0"
        try:
            mindiffs = int(inputs.get("mindiffs", 3))
        except (TypeError, ValueError):
            return "mindiffs must be an integer"
        if mindiffs < 0:
            return "mindiffs must be >= 0"
        return cls._validate_common(inputs)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "detection_mode": ("STRING", {"default": "denovo", "options": ["denovo", "reference"], "description": "Galaxy chimera detection mode"}),
            },
            "optional": {
                "infile_denovo": (
                    "FASTA",
                    {"default": "", "description": "Input FASTA required only for de novo chimera detection"},
                ),
                "infile_reference": (
                    "FASTA",
                    {"default": "", "description": "Input FASTA required only for reference-based chimera detection"},
                ),
                "db": (
                    "FASTA",
                    {"default": "", "description": "Reference database required only for uchime_ref mode"},
                ),
                "abskew": ("FLOAT", {"default": 2.0, "min": 0, "description": "Minimum abundance ratio of parent versus chimera"}),
                "dn": ("FLOAT", {"default": 1.4, "min": 0, "description": "UCHIME no-vote pseudo-count"}),
                "xn": ("FLOAT", {"default": 8.0, "min": 0, "description": "UCHIME no-vote weight"}),
                "mindiffs": ("INT", {"default": 3, "min": 0, "description": "Minimum differences in segment"}),
                "mindiv": ("FLOAT", {"default": 0.8, "min": 0, "description": "Minimum divergence from closest parent"}),
                "minh": ("FLOAT", {"default": 0.28, "min": 0, "description": "Minimum chimera score"}),
                "self_param": ("BOOLEAN", {"default": False, "description": "Exclude identical labels for uchime_ref"}),
                "selfid_param": ("BOOLEAN", {"default": False, "description": "Exclude identical sequences for uchime_ref"}),
                "outputs": (
                    "STRING",
                    {
                        "default": [],
                        "list": True,
                        "options": ["nonchimeras", "uchimealns", "uchimeout"],
                        "description": "Optional Galaxy outputs to request",
                    },
                ),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

pin_contract(VSearchChimeraDetectionNode)
