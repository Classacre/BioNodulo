"""Shared HISAT2 2.2.2 metadata and index layout."""

from __future__ import annotations

from typing import ClassVar

from bionodulo.nodes.command_node import CommandNode


HISAT2_SMALL_SUFFIXES = tuple(f".{number}.ht2" for number in range(1, 9))
HISAT2_LARGE_SUFFIXES = tuple(suffix.replace(".ht2", ".ht2l") for suffix in HISAT2_SMALL_SUFFIXES)
HISAT2_SUFFIX_FAMILIES = (HISAT2_SMALL_SUFFIXES, HISAT2_LARGE_SUFFIXES)


class HISAT2CommandNode(CommandNode):
    """Pinned metadata shared by the documented HISAT2 operations."""

    CATEGORY = "alignment"
    REQUIRED_CONDA_PACKAGES = ["hisat2"]
    VERSION = "2.2.2"
    GIT_URL = "https://github.com/DaehwanKimLab/hisat2.git"
    GIT_COMMIT = "99583d7536b9ee017ac07de8834017a3bf99a2fe"
    DOCUMENTATION_URL = (
        "https://github.com/DaehwanKimLab/hisat2/blob/99583d7536b9ee017ac07de8834017a3bf99a2fe/docs/_pages/manual.md"
    )
    CITATION_DOIS = ["10.1038/nmeth.3317", "10.1038/s41587-019-0201-4"]
    CITATION_URLS = [f"https://doi.org/{doi}" for doi in CITATION_DOIS]
    CITATION_TEXT = "Hierarchical graph FM-index alignment for spliced sequencing reads."
    SHELL = False

    UPSTREAM_TAG: ClassVar[str] = "v2.2.2"
    UPSTREAM_MANUAL: ClassVar[str] = "docs/_pages/manual.md"
    UPSTREAM_WRAPPER: ClassVar[str] = ""
    UPSTREAM_SOURCE: ClassVar[str] = ""
