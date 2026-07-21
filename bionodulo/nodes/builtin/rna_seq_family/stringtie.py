"""StringTie 3.0.3 transcript assembly and abundance outputs."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


def _path(value: Any) -> str | None:
    try:
        path = os.fsdecode(os.fspath(value))
    except TypeError:
        return None
    return path if path.strip() else None


class StringTieNode(CommandNode):
    """Assemble and quantify transcripts from coordinate-sorted RNA-seq alignments."""

    NODE_ID = "stringtie"
    DISPLAY_NAME = "StringTie"
    REQUIRED_CONDA_PACKAGES = ["stringtie"]
    CONDA_PACKAGE_CONSTRAINTS = {"stringtie": "3.0.3"}
    PACKAGE_CONSTRAINTS = ("stringtie=3.0.3",)
    CATEGORY = "rna_seq"
    DESCRIPTION = "Assemble transcripts and report gene abundance from coordinate-sorted BAM alignments"
    SEARCH_ALIASES = ["stringtie", "assemble", "transcript", "expression", "rna-seq"]
    RETURN_TYPES = ("GTF", "TSV")
    RETURN_NAMES = ("transcripts", "gene_abundance")
    REQUIRED_EXECUTABLES = ["stringtie"]
    VERSION = "3.0.3"
    GIT_URL = "https://github.com/gpertea/stringtie.git"
    GIT_COMMIT = "3436ad6dfd0ffc806a94086cf747ac6ff2b0dc19"
    DOCUMENTATION_URL = (
        "https://github.com/gpertea/stringtie/blob/"
        f"{GIT_COMMIT}/README.md"
    )
    UPSTREAM_SOURCE = (
        "stringtie.cpp:USAGE,processOptions,main geneabundance output block; "
        "README.md:StringTie options and input/output contract"
    )
    SOURCE_AUTHORITIES = {
        "cli_contract": "stringtie.cpp:processOptions",
        "output_contract": "stringtie.cpp:main geneabundance output block",
        "documentation": DOCUMENTATION_URL,
    }
    AUDIT_STATUS = "contract-checked-no-binary-execution"
    EXIT_SEMANTICS = (
        "StringTie non-zero exits are fatal. A successful run must create a non-empty transcripts GTF "
        "and the gene-abundance table requested with -A, whose header is validated before publication."
    )
    CITATION_DOIS = ["10.1038/nbt.3122"]
    CITATION_URLS = ["https://doi.org/10.1038/nbt.3122"]
    CITATION_TEXT = "StringTie enables improved reconstruction of a transcriptome from RNA-seq reads."
    SHELL = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": (("SAM", "BAM", "CRAM"), {"description": "Coordinate-sorted RNA-seq alignment"}),
                "threads": ("INT", {"default": 1, "min": 1, "display": "slider"}),
            },
            "optional": {
                "gtf": ("GTF", {"default": "", "description": "Optional reference annotation guide"}),
                "fr": ("BOOLEAN", {"default": False, "advanced": True}),
                "rf": ("BOOLEAN", {"default": False, "advanced": True}),
                "cram_reference": (
                    "FASTA",
                    {"default": "", "description": "Optional reference FASTA for CRAM input", "advanced": True},
                ),
                "min_isoform_fraction": (
                    "FLOAT",
                    {"default": 0.01, "min": 0.0, "max": 0.999999, "step": 0.01, "advanced": True},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "transcripts.gtf", node_out / "gene_abundance.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if _path(inputs.get("bam")) is None:
            return "bam must be a non-empty path-like value"
        if inputs.get("gtf") not in (None, "") and _path(inputs.get("gtf")) is None:
            return "gtf must be a non-empty path-like value when supplied"
        threads = inputs.get("threads", 1)
        if isinstance(threads, bool) or not isinstance(threads, int) or threads < 1:
            return "threads must be a positive integer"
        if inputs.get("fr") and inputs.get("rf"):
            return "fr and rf library modes are mutually exclusive"
        fraction = inputs.get("min_isoform_fraction", 0.01)
        if isinstance(fraction, bool) or not isinstance(fraction, (int, float)):
            return "min_isoform_fraction must be a number"
        if not 0 <= float(fraction) < 1:
            return "min_isoform_fraction must be at least 0 and less than 1"
        if inputs.get("cram_reference") not in (None, "") and _path(inputs.get("cram_reference")) is None:
            return "cram_reference must be a non-empty path-like value when supplied"
        for name, value in (
            ("bam", inputs.get("bam")),
            ("gtf", inputs.get("gtf")),
            ("cram_reference", inputs.get("cram_reference")),
        ):
            if value in (None, ""):
                continue
            path = Path(_path(value) or "")
            if not path.is_file():
                return f"{name} is not a materialized file: {path}"
            try:
                if path.stat().st_size == 0:
                    return f"{name} file is empty: {path}"
            except OSError as exc:
                return f"cannot inspect {name} file {path}: {exc}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = ["stringtie", str(inputs.get("bam", ""))]
        if inputs.get("cram_reference"):
            command.extend(["--ref", str(inputs["cram_reference"])])
        if inputs.get("gtf"):
            command.extend(["-G", str(inputs["gtf"])])
        command.extend(
            [
                "-o",
                str(output / "transcripts.gtf"),
                "-A",
                str(output / "gene_abundance.tsv"),
                "-p",
                str(inputs.get("threads", 1)),
            ]
        )
        if inputs.get("fr"):
            command.append("--fr")
        elif inputs.get("rf"):
            command.append("--rf")
        command.extend(["-f", str(inputs.get("min_isoform_fraction", 0.01))])
        return command

    @classmethod
    def _validate_outputs(cls, outputs: list[Path]) -> None:
        """Validate source-defined text output invariants before publication."""
        transcripts, abundance = outputs
        if transcripts.stat().st_size == 0:
            raise RuntimeError("StringTie produced an empty transcripts GTF")
        if abundance.stat().st_size == 0:
            raise RuntimeError("StringTie produced an empty gene-abundance table")
        with abundance.open("r", encoding="utf-8", errors="replace") as handle:
            first_line = handle.readline().rstrip("\r\n")
        expected = "Gene ID\tGene Name\tReference\tStrand\tStart\tEnd\tCoverage\tFPKM\tTPM"
        if first_line != expected:
            raise RuntimeError("StringTie gene-abundance table has an unexpected header")

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        result = await super().run(**kwargs)
        self.__class__._validate_outputs([Path(path) for path in result])
        return result


__all__ = ["StringTieNode"]
