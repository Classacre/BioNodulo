"""MAFFT 7.525 multiple-sequence alignment."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import PhylogenyCommandNode, path_value, validate_choice, validate_int


class MAFFTNode(PhylogenyCommandNode):
    """Align FASTA sequences and capture MAFFT's native stdout alignment."""

    NODE_ID = "mafft"
    DISPLAY_NAME = "MAFFT"
    DESCRIPTION = "Multiple sequence alignment with MAFFT 7.525."
    SEARCH_ALIASES = ["BioNodulo builtin", "MAFFT", "multiple sequence alignment", "MSA"]
    RETURN_TYPES = ("ALIGNMENT",)
    RETURN_NAMES = ("alignment",)
    REQUIRED_EXECUTABLES = ["mafft"]
    REQUIRED_CONDA_PACKAGES = ["mafft"]
    CONDA_PACKAGE_CONSTRAINTS = {"mafft": "7.525"}
    PACKAGE_CONSTRAINT = "mafft = 7.525"
    REQUIRED_PATH_INPUTS = ("input",)
    OUTPUT_FILENAMES = ("alignment.fasta",)
    STDOUT_OUTPUT_INDEX = 0
    VERSION = "7.525"
    SOURCE_URL = "https://mafft.cbrc.jp/alignment/software/mafft-7.525-with-extensions-src.tgz"
    SOURCE_SHA256 = "2876f4adc1a2de4ed206bc40896763bf208bf1a02bda52f8bfdd91cf52d73e4a"
    DOCUMENTATION_URL = "https://mafft.cbrc.jp/alignment/software/manual/manual.html"
    UPSTREAM_SOURCE = "README.md; core/mafft.tmpl"
    SOURCE_AUTHORITIES = {
        "source_archive": (SOURCE_URL, SOURCE_SHA256),
        "version_and_examples": "README.md",
        "argv_parser": "core/mafft.tmpl",
    }
    AUDIT_STATUS = "contract-checked-no-binary-execution"
    EXIT_SEMANTICS = (
        "A non-zero MAFFT exit is fatal; exit zero is accepted only when the captured stdout "
        "alignment exists at alignment.fasta."
    )
    DETERMINISM_SEMANTICS = (
        "MAFFT documents that iterative refinement can vary with multiple threads; use threads=0 "
        "when source-level reproducibility is required."
    )
    CITATION_DOIS = ["10.1093/molbev/mst010"]
    CITATION_URLS = ["https://doi.org/10.1093/molbev/mst010"]
    CITATION_TEXT = "MAFFT multiple sequence alignment software version 7."
    STRATEGIES = ("auto", "linsi", "ginsi", "einsi")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTA", {"description": "Input nucleotide or protein FASTA"}),
            },
            "optional": {
                "threads": (
                    "INT",
                    {"default": 4, "min": -1, "description": "Thread count; -1 auto-detects and 0 is single-threaded"},
                ),
                "strategy": (
                    "STRING",
                    {
                        "default": "auto",
                        "options": list(cls.STRATEGIES),
                        "description": "MAFFT --auto, L-INS-i, G-INS-i, or E-INS-i strategy",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_int(inputs.get("threads", 4), "threads", minimum=-1)
        if validation is not True:
            return validation
        return validate_choice(inputs.get("strategy", "auto"), "strategy", cls.STRATEGIES)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        return [node_dir / "alignment.fasta"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        strategy = str(inputs.get("strategy", "auto"))
        strategy_args = {
            "auto": ["--auto"],
            "linsi": ["--localpair", "--maxiterate", "1000"],
            "ginsi": ["--globalpair", "--maxiterate", "1000"],
            "einsi": ["--genafpair", "--maxiterate", "1000"],
        }[strategy]
        return [
            "mafft",
            "--thread",
            str(inputs.get("threads", 4)),
            *strategy_args,
            path_value(inputs["input"]),
        ]
