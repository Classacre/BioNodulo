"""Shared runtime contract for the generated TaxonKit operation nodes.

TaxonKit is one ``taxonkit`` binary with 11 subcommands for querying and
reformatting NCBI Taxonomy data. Two nodes in this family are hand-written owners
(``taxonkit_name2taxid``, ``taxonkit_profile2cami``) that subclass the contracts in
``taxonomy_family``; the rest are generated from the tool's own cobra ``--help``
tables by ``scripts/generate_subcommand_nodes.py``.

Every one of those operations needs an NCBI taxonomy dump, and that requirement is
easy to lose: the flag is inherited from the root command, so a generator that
skips the ``Global Flags:`` section silently produces nodes that cannot run. The
flag is therefore promoted into each node's parameter list rather than left as an
annotation nobody reads.

Citation verified against Crossref on 2026-09-27: the registry record's DOI
resolves to the TaxonKit software paper (Journal of Genetics and Genomics, 2021).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode

TAXONKIT_VERSION = "0.20.0"
TAXONKIT_DOCUMENTATION_URL = "https://bioinf.shenwei.me/taxonkit/"
TAXONKIT_CITATION_DOIS = ["10.1016/j.jgg.2021.03.006"]
TAXONKIT_CITATION_URLS = [f"https://doi.org/{doi}" for doi in TAXONKIT_CITATION_DOIS]
TAXONKIT_CITATION_TEXT = (
    "TaxonKit: A practical and efficient NCBI taxonomy toolkit."
)
TAXONKIT_KNOWLEDGE = {
    "schema_version": 1,
    "tool_id": "https://bio.tools/taxonkit",
    "topics": [
        {"uri": "http://edamontology.org/topic_0637", "label": "Taxonomy"},
        {"uri": "http://edamontology.org/topic_0622", "label": "Genomics"},
    ],
    "citation_evidence": [
        {
            "identifier": TAXONKIT_CITATION_DOIS[0],
            "source_url": "https://api.crossref.org/works/10.1016/j.jgg.2021.03.006",
            "checked_at": "2026-09-27",
            "note": (
                "Crossref returns 'TaxonKit: A practical and efficient NCBI taxonomy "
                "toolkit', Journal of Genetics and Genomics 2021, Shen Wei and Ren Hong. "
                "Checked rather than trusted, because registry records have carried "
                "wrong publications before."
            ),
        }
    ],
    "reviewed_at": "2026-09-27",
}


class TaxonkitBase(CommandNode):
    """Pinned metadata shared by the generated TaxonKit operation nodes."""

    CATEGORY = "taxonkit"
    REQUIRED_EXECUTABLES = ["taxonkit"]
    REQUIRED_CONDA_PACKAGES = ["taxonkit"]
    CONDA_PACKAGE_CONSTRAINTS = {"taxonkit": f"=={TAXONKIT_VERSION}"}
    VERSION = TAXONKIT_VERSION
    DOCUMENTATION_URL = TAXONKIT_DOCUMENTATION_URL
    CITATION_DOIS = TAXONKIT_CITATION_DOIS
    CITATION_URLS = TAXONKIT_CITATION_URLS
    CITATION_TEXT = TAXONKIT_CITATION_TEXT
    KNOWLEDGE = dict(TAXONKIT_KNOWLEDGE)
    SHELL = False

    OUTPUT_FILENAMES: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        if not cls.OUTPUT_FILENAMES:
            return [node_out]
        return [node_out / filename for filename in cls.OUTPUT_FILENAMES]
