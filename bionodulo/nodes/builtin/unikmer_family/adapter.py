"""Focused UniKmer node owners.

One ``unikmer`` binary with ~24 subcommands for k-mer manipulation in binary
format (``.unik``): encode, count, sort, merge, intersect, diff, split, tsplit.
The operation nodes are generated from the tool's own cobra ``--help`` tables by
``scripts/generate_subcommand_nodes.py``; this module holds the metadata they
share.

UniKmer has no publication or explicit citation instructions in its official
repository/docs, so its software repository is cited directly rather than
borrowing a paper from a related tool.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode

UNIKMER_VERSION = "0.20.0"
UNIKMER_DOCUMENTATION_URL = "https://bioinf.shenwei.me/unikmer/"
UNIKMER_CITATION_URLS = ["https://github.com/shenwei356/unikmer"]
UNIKMER_CITATION_TEXT = (
    "UniKmer: a versatile toolkit for k-mers with taxonomic information (Wei Shen), "
    f"version {UNIKMER_VERSION}."
)
UNIKMER_KNOWLEDGE = {
    "schema_version": 1,
    "topics": [
        {"uri": "http://edamontology.org/topic_0157",
         "label": "Sequence composition, complexity and repeats"},
        {"uri": "http://edamontology.org/topic_0080", "label": "Sequence analysis"},
    ],
    "citation_evidence": [
        {
            "identifier": "UniKmer 0.20.0",
            "source_url": "https://github.com/shenwei356/unikmer",
            "checked_at": "2026-09-29",
            "note": (
                "The official repository identifies UniKmer as a k-mer toolkit and links "
                "its documentation, but provides no DOI, CITATION file, or citation "
                "instructions. Cite the software repository directly; no related-tool paper "
                "is attributed to UniKmer."
            ),
        }
    ],
    "reviewed_at": "2026-09-27",
}


class UnikmerBase(CommandNode):
    """Pinned metadata shared by the UniKmer operation nodes.

    ``PLAN_OUTPUTS`` covers all three output shapes the suite uses: a single named
    file (``--out-file``), stdout captured by the executor, and a directory the tool
    fills (``--out-dir``, used by ``split`` and ``tsplit``). A directory output
    declares no filename, because which files appear inside depends on the input
    k-mer set and the chunk size.
    """

    CATEGORY = "unikmer"
    REQUIRED_EXECUTABLES = ["unikmer"]
    REQUIRED_CONDA_PACKAGES = ["unikmer"]
    CONDA_PACKAGE_CONSTRAINTS = {"unikmer": f"=={UNIKMER_VERSION}"}
    VERSION = UNIKMER_VERSION
    DOCUMENTATION_URL = UNIKMER_DOCUMENTATION_URL
    CITATION_URLS = UNIKMER_CITATION_URLS
    CITATION_TEXT = UNIKMER_CITATION_TEXT
    KNOWLEDGE = dict(UNIKMER_KNOWLEDGE)
    SHELL = False

    OUTPUT_FILENAMES: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        if not cls.OUTPUT_FILENAMES:
            # A directory-shaped output: the node's own folder is the artifact.
            return [node_out]
        return [node_out / filename for filename in cls.OUTPUT_FILENAMES]

    @classmethod
    def VERIFY_OUTPUTS(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        if cls.RETURN_TYPES == ("DIRECTORY",):
            if len(outputs) != 1 or not any(path.is_file() for path in outputs[0].rglob("*")):
                raise RuntimeError(f"{cls.NODE_ID} produced no files in its output directory")
