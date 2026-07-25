"""Focused VSEARCH dereplication node."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.wrapped_amplicon_trimming_family.evidence import pin_contract

from .adapter import VSearchNodeBase


class VSearchDereplicationNode(VSearchNodeBase):
    """Dereplicate identical FASTA sequences with VSEARCH."""

    NODE_ID = "vsearch_dereplication"
    DISPLAY_NAME = "VSEARCH Dereplication"
    REQUIRED_CONDA_PACKAGES = ["vsearch"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Dereplicate identical FASTA sequences with VSEARCH derep_fulllength and optional abundance filters."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "vsearch",
        "dereplication",
        "derep_fulllength",
        "amplicon dereplication",
        "unique sequences",
        "abundance",
    ]
    RETURN_TYPES = ("FASTA", "TSV")
    RETURN_NAMES = ("dereplicated_sequences", "uclust_output")
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
            "--derep_fulllength",
            str(inputs.get("infile", inputs.get("sequences", ""))),
        ])
        _add_if_value(cmd, "--maxuniquesize", inputs.get("maxuniquesize"))
        _add_if_value(cmd, "--minuniquesize", inputs.get("minuniquesize"))
        cmd.extend(["--output", f"{_out(inputs)}/dereplicated.fasta"])
        if inputs.get("sizein"):
            cmd.append("--sizein")
        if inputs.get("sizeout"):
            cmd.append("--sizeout")
        cmd.extend(["--strand", str(inputs.get("strand", "plus"))])
        _add_if_value(cmd, "--topn", inputs.get("topn"))
        if inputs.get("uc"):
            cmd.extend(["--uc", f"{_out(inputs)}/dereplication.uc"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "dereplicated.fasta"]
        if inputs.get("uc"):
            outputs.append(out / "dereplication.uc")
        return outputs

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Path]:
        names = {
            "dereplicated.fasta": "dereplicated_sequences",
            "dereplication.uc": "uclust_output",
        }
        return {names[path.name]: path for path in planned_paths}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("infile", inputs.get("sequences", ""))).strip():
            return "infile is required"
        if str(inputs.get("strand", "plus")) not in {"plus", "both"}:
            return "strand must be one of: plus, both"
        numeric_values: dict[str, int] = {}
        for name in ("topn", "minuniquesize", "maxuniquesize"):
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < 1:
                return f"{name} must be at least 1"
            numeric_values[name] = value
        if (
            "minuniquesize" in numeric_values
            and "maxuniquesize" in numeric_values
            and numeric_values["minuniquesize"] > numeric_values["maxuniquesize"]
        ):
            return "minuniquesize must be <= maxuniquesize"
        return cls._validate_common(inputs)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"infile": ("FASTA", {"description": "FASTA sequences to dereplicate"})},
            "optional": {
                "topn": ("INT", {"default": "", "min": 1, "description": "Output only the n most abundant sequences"}),
                "sizein": ("BOOLEAN", {"default": False, "description": "Read abundance annotations from input"}),
                "sizeout": ("BOOLEAN", {"default": False, "description": "Write abundance annotations to output"}),
                "strand": ("STRING", {"default": "plus", "options": ["plus", "both"]}),
                "uc": ("BOOLEAN", {"default": False, "description": "Write UCLUST-like dereplication assignments"}),
                "minuniquesize": ("INT", {"default": "", "min": 1, "description": "Minimum abundance to output"}),
                "maxuniquesize": ("INT", {"default": "", "min": 1, "description": "Maximum abundance to output"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


pin_contract(VSearchDereplicationNode)
