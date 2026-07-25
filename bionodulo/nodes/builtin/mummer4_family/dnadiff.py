"""MUMmer4 4.0.1 whole-genome comparison with ``dnadiff``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import Mummer4CommandNode, stage_file


class Mummer4DnadiffNode(Mummer4CommandNode):
    """Run the source dnadiff pipeline and expose its unconditional artifacts."""

    NODE_ID = "mummer4_dnadiff"
    DISPLAY_NAME = "MUMmer4 DNAdiff"
    DESCRIPTION = "Compare two closely related genomes and report alignments, SNPs, and breakpoints."
    SEARCH_ALIASES = ["BioNodulo builtin", "MUMmer4", "dnadiff", "genome difference", "assembly comparison"]
    RETURN_TYPES = (
        "STATS_FILE",
        "FILE",
        "FILE",
        "FILE",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
    )
    RETURN_NAMES = (
        "report",
        "delta",
        "one_to_one_delta",
        "many_to_many_delta",
        "one_to_one_coordinates",
        "many_to_many_coordinates",
        "snps",
        "reference_breakpoints",
        "query_breakpoints",
    )
    OUTPUT_FILENAMES = (
        "out.report",
        "out.delta",
        "out.1delta",
        "out.mdelta",
        "out.1coords",
        "out.mcoords",
        "out.snps",
        "out.rdiff",
        "out.qdiff",
    )
    REQUIRED_EXECUTABLES = ["dnadiff", "nucmer", "delta-filter", "show-coords", "show-snps", "show-diff"]
    REQUIRED_PATH_INPUTS = ("reference_sequence", "query_sequence")
    UPSTREAM_SOURCE = "scripts/dnadiff.pl"
    SOURCE_PATHS = (
        UPSTREAM_SOURCE,
        "scripts/Foundation.pm",
        "src/umd/nucmer_cmdline.yaggo",
        "src/umd/nucmer_main.cc",
        "src/tigr/delta-filter.cc",
        "src/tigr/show-coords.cc",
        "src/tigr/show-snps.cc",
        "src/tigr/show-diff.cc",
        "docs/dnadiff.README",
        "README.md",
    )
    EXECUTABLE_VERSION = "1.3"
    OPTIONAL_OUTPUT_FILENAMES = ("out.unref", "out.unqry")
    EXIT_SEMANTICS = (
        "dnadiff exits non-zero on option, dependency, path, FASTA, or child-command failure. "
        "The nine declared artifacts are unconditional; out.unref and out.unqry are emitted "
        "only when the corresponding input contains unaligned sequences."
    )
    RUN_IN_NODE_OUTPUT_DIR = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reference_sequence": ("FASTA", {"description": "Reference multi-FASTA"}),
                "query_sequence": ("FASTA", {"description": "Query multi-FASTA"}),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        node_dir = outputs[0].parent
        stage_file(inputs["reference_sequence"], node_dir / "reference.fa")
        stage_file(inputs["query_sequence"], node_dir / "query.fa")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return cls.checked_command(inputs, "dnadiff", "-p", "out", "reference.fa", "query.fa")
