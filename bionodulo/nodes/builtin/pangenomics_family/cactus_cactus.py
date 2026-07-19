"""Stable owner for the Tools-IUC ``cactus_cactus`` contract."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .evidence import PangenomicsCommandContract


class CactusGalaxyNode(PangenomicsCommandContract):
    """Run the Galaxy Cactus whole-genome multiple alignment wrapper."""

    NODE_ID = "cactus_cactus"
    DISPLAY_NAME = "Cactus"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Whole-genome multiple sequence alignment with Progressive Cactus or Minigraph-Cactus."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "Cactus",
        "cactus_cactus",
        "Progressive Cactus",
        "Minigraph-Cactus",
        "whole-genome multiple alignment",
        "HAL alignment",
        "pangenome graph",
    ]
    RETURN_TYPES = ("HAL", "GFA")
    RETURN_NAMES = ("out_hal", "out_gfa")
    REQUIRED_EXECUTABLES = ["cactus", "cactus-pangenome"]
    REQUIRED_CONDA_PACKAGES = ["cactus"]
    DOCUMENTATION_URL = "https://github.com/ComparativeGenomicsToolkit/cactus"
    CITATION_DOIS = ["10.1038/s41586-020-2871-y"]
    CITATION_URLS = ["https://doi.org/10.1038/s41586-020-2871-y"]
    CITATION_TEXT = "Progressive Cactus is a multiple-genome aligner for the thousand-genome era."
    VERSION = "2.7.1+galaxy0"
    SHELL = True

    MODES = ["interspecies", "intraspecies"]

    @classmethod
    def _mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("aln_mode_select", "interspecies") or "interspecies")

    @classmethod
    def _labels(cls, inputs: dict[str, Any]) -> list[str]:
        value = inputs.get("labels", [])
        if isinstance(value, (list, tuple)):
            return [str(item) for item in value]
        return [item for item in re.split(r"[\s,]+", str(value or "")) if item]

    @classmethod
    def _seqs(cls, inputs: dict[str, Any]) -> list[str]:
        value = inputs.get("in_seqs", [])
        if isinstance(value, (list, tuple)):
            return [str(item) for item in value if str(item)]
        text = str(value or "")
        return [item for item in re.split(r"[\n,]+", text) if item.strip()]

    @classmethod
    def _positive_int(cls, inputs: dict[str, Any], key: str, default: int) -> int | str:
        value = inputs.get(key, default)
        if value in (None, ""):
            value = default
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if parsed <= 0:
            return f"{key} must be greater than zero"
        return parsed

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        seqs = cls._seqs(inputs)
        labels = cls._labels(inputs)
        if not seqs:
            return "at least one input genome FASTA is required"
        if len(labels) != len(seqs):
            return "labels must match in_seqs length"
        if any(not re.fullmatch(r"[0-9A-Za-z_]+", label) for label in labels):
            return "labels may contain only letters, digits, and underscores"
        mode = cls._mode(inputs)
        if mode not in cls.MODES:
            return f"aln_mode_select must be one of: {', '.join(cls.MODES)}"
        if mode == "interspecies" and not str(inputs.get("in_tree", "")).strip():
            return "in_tree is required for interspecies mode"
        if mode == "intraspecies":
            ref_level = str(inputs.get("ref_level", "")).strip()
            if not ref_level:
                return "ref_level is required for intraspecies mode"
            if ref_level not in labels:
                return "ref_level must match one of the labels"
        for key, default in (("max_cores", 4), ("max_memory_mb", 16384)):
            validation = cls._positive_int(inputs, key, default)
            if isinstance(validation, str):
                return validation
        return True

    @classmethod
    def _seq_filename(cls, label: str, fasta: str) -> str:
        suffixes = Path(fasta).suffixes
        if suffixes[-2:] == [".fa", ".gz"]:
            ext = "fa.gz"
        elif suffixes[-2:] == [".fasta", ".gz"]:
            ext = "fasta.gz"
        elif suffixes:
            ext = suffixes[-1].lstrip(".")
        else:
            ext = "fasta"
        return f"{label}.{ext}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = str(inputs.get("output", "."))
        seqfile = f"{out_dir}/seqfile.txt"
        mode = cls._mode(inputs)
        labels = cls._labels(inputs)
        seqs = cls._seqs(inputs)
        max_cores = cls._positive_int(inputs, "max_cores", 4)
        max_memory = cls._positive_int(inputs, "max_memory_mb", 16384)
        assert isinstance(max_cores, int)
        assert isinstance(max_memory, int)

        cmd = ["mkdir", "-p", out_dir, "&&"]
        if mode == "interspecies":
            cmd.extend(["cat", str(inputs.get("in_tree", "")), ">", seqfile, "&&"])
        else:
            cmd.extend(["rm", "-f", seqfile, "&&", "touch", seqfile, "&&"])

        for label, fasta in zip(labels, seqs):
            seq_name = cls._seq_filename(label, fasta)
            cmd.extend(
                [
                    "ln",
                    "-s",
                    fasta,
                    f"{out_dir}/{seq_name}",
                    "&&",
                    "printf",
                    "%s %s\n",
                    label,
                    seq_name,
                    ">>",
                    seqfile,
                    "&&",
                ]
            )

        cmd.extend(["cd", out_dir, "&&"])
        if mode == "intraspecies":
            cmd.extend(
                [
                    "cactus-pangenome",
                    "--reference",
                    str(inputs.get("ref_level", "")),
                    "--binariesMode",
                    "local",
                    "--maxCores",
                    str(max_cores),
                    "--maxMemory",
                    f"{max_memory}M",
                    "--outDir",
                    "./",
                    "--outName",
                    "alignment",
                    "jobStore",
                    "seqfile.txt",
                ]
            )
        else:
            cmd.extend(
                [
                    "cactus",
                    "--binariesMode",
                    "local",
                    "--maxCores",
                    str(max_cores),
                    "--maxMemory",
                    f"{max_memory}M",
                    "--workDir",
                    "./",
                    "jobStore",
                    "seqfile.txt",
                    "alignment.full.hal",
                ]
            )
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        outputs = [node_out / "alignment.full.hal"]
        if cls._mode(inputs) == "intraspecies":
            outputs.append(node_out / "alignment.gfa.gz")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_seqs": ("FASTA_LIST", {"multiple": True, "description": "Input genome FASTA or FASTA.GZ files"}),
                "labels": ("STRING_LIST", {"multiple": True, "description": "Genome labels matching the input FASTA order"}),
            },
            "optional": {
                "aln_mode_select": (
                    "STRING",
                    {
                        "default": "interspecies",
                        "options": cls.MODES,
                        "description": "Between-species Progressive Cactus or within-species Minigraph-Cactus mode",
                    },
                ),
                "in_tree": ("FILE", {"default": "", "description": "Guide tree in Newick/NHX format for interspecies mode"}),
                "ref_level": ("STRING", {"default": "", "description": "Reference genome label for intraspecies mode"}),
                "max_cores": ("INT", {"default": 4, "min": 1, "max": 512, "display": "slider"}),
                "max_memory_mb": ("INT", {"default": 16384, "min": 1, "display": "slider"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
