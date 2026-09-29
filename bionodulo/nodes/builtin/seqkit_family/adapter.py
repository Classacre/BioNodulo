"""Shared runtime contract for the SeqKit family nodes.

SeqKit is a toolkit of FASTX utilities: one ``seqkit`` binary with ~45
subcommands. The eight hand-written owners next to this file cover the operations
that were needed first; the remaining operations are generated from the tool's own
cobra ``--help`` flag tables by ``scripts/generate_subcommand_nodes.py``.

Metadata here matches what the hand-written owners already declare, so the family
does not end up with two versions or two citation sets.

Grouped under its own ``seqkit`` category, matching the samtools, emboss and csvtk
families: at ~45 operations, folding the suite into the topical ``sequence``
bucket would bury the other tools in it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode

SEQKIT_VERSION = "2.13.0"
SEQKIT_GIT_URL = "https://github.com/galaxyproject/tools-iuc"
# The tools-iuc wrapper revision this family is pinned to, matching the eight
# hand-written owners.
SEQKIT_GIT_COMMIT = "8eb66da1f6f16fde92688ee6c500d2bcdc924a47"
SEQKIT_DOCUMENTATION_URL = "https://bioinf.shenwei.me/seqkit/"
SEQKIT_CITATION_DOIS = ["10.1371/journal.pone.0163962"]
SEQKIT_CITATION_URLS = [f"https://doi.org/{doi}" for doi in SEQKIT_CITATION_DOIS]
SEQKIT_CITATION_TEXT = (
    "SeqKit: a cross-platform and ultrafast toolkit for FASTA/Q file manipulation."
)
SEQKIT_KNOWLEDGE = {
    "schema_version": 1,
    "tool_id": "https://bio.tools/seqkit",
    "topics": [{"uri": "http://edamontology.org/topic_0080", "label": "Sequence analysis"}],
    "citation_evidence": [
        {
            "identifier": SEQKIT_CITATION_DOIS[0],
            "source_url": "https://doi.org/10.1371/journal.pone.0163962",
            "checked_at": "2026-09-27",
            "note": (
                "SeqKit's primary publication (PLOS ONE 2016), already used by the "
                "hand-written seqkit owners. It is the software paper for the suite, "
                "not a version-specific DOI for the pinned 2.13.0 runtime."
            ),
        }
    ],
    "reviewed_at": "2026-09-27",
}


class SeqkitBase(CommandNode):
    """Pinned metadata shared by the SeqKit operation nodes."""

    CATEGORY = "seqkit"
    REQUIRED_EXECUTABLES = ["seqkit"]
    REQUIRED_CONDA_PACKAGES = ["seqkit"]
    CONDA_PACKAGE_CONSTRAINTS = {"seqkit": f"=={SEQKIT_VERSION}"}
    VERSION = SEQKIT_VERSION
    GIT_URL = SEQKIT_GIT_URL
    GIT_COMMIT = SEQKIT_GIT_COMMIT
    DOCUMENTATION_URL = SEQKIT_DOCUMENTATION_URL
    CITATION_DOIS = SEQKIT_CITATION_DOIS
    CITATION_URLS = SEQKIT_CITATION_URLS
    CITATION_TEXT = SEQKIT_CITATION_TEXT
    KNOWLEDGE = dict(SEQKIT_KNOWLEDGE)
    SHELL = False

    OUTPUT_FILENAMES: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        if cls.RETURN_TYPES == ("DIRECTORY",) and not cls.OUTPUT_FILENAMES:
            return [node_out]
        return [node_out / filename for filename in cls.OUTPUT_FILENAMES]

    @classmethod
    def VERIFY_OUTPUTS(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        if cls.RETURN_TYPES == ("DIRECTORY",):
            if len(outputs) != 1 or not any(path.is_file() for path in outputs[0].rglob("*")):
                raise RuntimeError(f"{cls.NODE_ID} produced no files in its output directory")
